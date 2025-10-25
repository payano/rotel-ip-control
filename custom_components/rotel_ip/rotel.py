from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable

from .const import DEFAULT_PORT, DEFAULT_PROFILE_KEY
from .profiles import PROFILES

_LOGGER = logging.getLogger(__name__)


def _parse_line(line: str) -> dict[str, Any] | None:
    """Parse a Rotel ASCII line (without trailing '$') into a dict.

    Examples:
      power=on             -> {"power": "on"}
      volume=45            -> {"volume": "45"}
      source=cd            -> {"source": "cd"}
    """
    line = line.strip().strip("$")
    if not line or "=" not in line:
        return None
    parts = [p for p in line.replace(" ", "").split(",") if p]
    out: dict[str, Any] = {}
    for part in parts:
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.lower()] = v.lower()
    return out or None


class RotelClient:
    """Asyncio TCP client for Rotel ASCII protocol (port defaults to profile/9590)."""

    def __init__(self, host: str, port: int | None = None, profile_key: str | None = None) -> None:
        self._host = host
        self._profile_key = profile_key or DEFAULT_PROFILE_KEY
        self._port = port or PROFILES[self._profile_key].port or DEFAULT_PORT
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._task: asyncio.Task | None = None
        self._listeners: set[Callable[[dict[str, Any]], None]] = set()
        self._connected_evt = asyncio.Event()
        self._closing = False

    # Public API
    @property
    def connected(self) -> bool:
        return self._writer is not None and not self._writer.is_closing()

    @property
    def profile(self):
        return PROFILES[self._profile_key]

    async def connect(self) -> None:
        if self.connected:
            return
        _LOGGER.debug("Connecting to Rotel at %s:%s", self._host, self._port)
        self._reader, self._writer = await asyncio.open_connection(self._host, self._port)
        self._connected_evt.set()
        self._task = asyncio.create_task(self._reader_loop())

    async def ensure_connected(self) -> None:
        if not self.connected:
            await self.connect()

    async def close(self) -> None:
        self._closing = True
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._writer:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except Exception:  # noqa: BLE001
                pass
        self._reader = None
        self._writer = None
        self._connected_evt.clear()
        self._closing = False

    def add_listener(self, cb: Callable[[dict[str, Any]], None]) -> Callable[[], None]:
        self._listeners.add(cb)

        def _unsub():
            self._listeners.discard(cb)

        return _unsub

    async def command(self, cmd: str) -> None:
        await self.ensure_connected()
        await self._send(cmd)

    async def query(self, q: str) -> str | None:
        """Send a query like 'model?' and return the value part before '$'."""
        fut: asyncio.Future[str | None] = asyncio.get_running_loop().create_future()

        def _once(msg: dict[str, Any]):
            if not fut.done():
                if len(msg) == 1:
                    fut.set_result(next(iter(msg.values())))
                else:
                    fut.set_result(str(msg))

        unsub = self.add_listener(_once)
        try:
            await self._send(q)
            try:
                return await asyncio.wait_for(fut, timeout=2.0)
            except asyncio.TimeoutError:
                return None
        finally:
            unsub()

    async def enable_push_updates(self) -> None:
        try:
            await self._send(self.profile.commands["push_on"])
        except Exception:  # noqa: BLE001
            _LOGGER.debug("Push enable command failed (may be unsupported)")

    async def refresh_all(self) -> None:
        for key in ("power_query", "volume_query", "mute_query", "source_query"):
            cmd = self.profile.commands.get(key)
            if not cmd:
                continue
            try:
                await self._send(cmd)
                await asyncio.sleep(0.05)
            except Exception:  # noqa: BLE001
                pass

    # Internal
    async def _send(self, cmd: str) -> None:
        if not cmd.endswith("!") and not cmd.endswith("?"):
            # Most commands end with '!' or '?'
            _LOGGER.debug("Sending atypical command: %s", cmd)
        if not self.connected:
            raise RuntimeError("Not connected")
        data = cmd.encode("ascii")
        self._writer.write(data)
        await self._writer.drain()

    async def _reader_loop(self):
        backoff = 1.0
        buf = b""
        while not self._closing:
            try:
                assert self._reader is not None
                chunk = await self._reader.read(1024)
                if not chunk:
                    raise ConnectionError("Rotel connection closed")
                buf += chunk
                # Split by RX terminator (default '$')
                term = self.profile.terminator_rx.encode()
                while term in buf:
                    head, buf = buf.split(term, 1)
                    if not head:
                        continue
                    try:
                        line = head.decode("ascii", errors="ignore")
                    except Exception:  # noqa: BLE001
                        continue
                    msg = _parse_line(line)
                    if msg:
                        for cb in list(self._listeners):
                            try:
                                cb(msg)
                            except Exception:  # noqa: BLE001
                                _LOGGER.exception("Listener errored")
                backoff = 1.0  # reset on success
            except Exception as exc:  # noqa: BLE001
                _LOGGER.warning("Rotel reader error: %s", exc)
                await self._reconnect_with_backoff(backoff)
                backoff = min(backoff * 2, 30.0)

    async def _reconnect_with_backoff(self, delay: float):
        try:
            await self.close()
        except Exception:  # noqa: BLE001
            pass
        await asyncio.sleep(delay)
        try:
            await self.connect()
            await self.enable_push_updates()
            await self.refresh_all()
        except Exception as exc:  # noqa: BLE001
            _LOGGER.warning("Reconnect failed: %s", exc)

