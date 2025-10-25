from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, CONF_MODEL, CONF_NAME
from .rotel import RotelClient

_LOGGER = logging.getLogger(__name__)


SUPPORTED_FEATURES = (
    MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.TURN_ON
    | MediaPlayerEntityFeature.TURN_OFF
    | MediaPlayerEntityFeature.SELECT_SOURCE
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    client: RotelClient = hass.data[DOMAIN][entry.entry_id]

    entity = RotelIPMediaPlayer(
        client=client,
        name=entry.data.get(CONF_NAME),
        model=entry.data.get(CONF_MODEL),
        host=entry.data.get(CONF_HOST),
        port=entry.data.get(CONF_PORT),
    )

    async_add_entities([entity])


class RotelIPMediaPlayer(MediaPlayerEntity):
    _attr_should_poll = False
    _attr_supported_features = SUPPORTED_FEATURES

    def __init__(self, client: RotelClient, name: str | None, model: str | None, host: str, port: int | None):
        self._client = client
        self._profile = client.profile
        self._attr_name = name or "Rotel Amplifier"
        self._model = model or "Rotel"
        self._host = host
        self._port = port

        # Internal state
        self._is_on: bool | None = None
        self._muted: bool = False
        self._volume_raw: int | None = None  # raw scale according to profile
        self._source: str | None = None
        self._sources = list(self._profile.sources.keys())

    async def async_added_to_hass(self) -> None:
        # Register listener for push updates
        @callback
        def _handle_update(msg: dict[str, Any]):
            changed = False
            if "power" in msg:
                self._is_on = msg["power"] == "on"
                changed = True
            if "mute" in msg:
                self._muted = msg["mute"] == "on"
                changed = True
            if "volume" in msg:
                try:
                    self._volume_raw = int(msg["volume"])  # raw scale
                except (TypeError, ValueError):
                    pass
                else:
                    changed = True
            if "source" in msg:
                self._source = msg["source"]
                changed = True

            if changed:
                self.async_write_ha_state()

        self._unsub = self._client.add_listener(_handle_update)

        # Prime state
        await self._client.ensure_connected()
        await self._client.enable_push_updates()
        await self._client.refresh_all()

    async def async_will_remove_from_hass(self) -> None:
        if hasattr(self, "_unsub") and self._unsub:
            self._unsub()

    # Device metadata
    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._host}:{self._port}")},
            name=self.name,
            manufacturer="Rotel",
            model=self._model,
        )

    # Core state
    @property
    def state(self) -> MediaPlayerState | None:
        if self._is_on is None:
            return None
        return MediaPlayerState.ON if self._is_on else MediaPlayerState.OFF

    @property
    def available(self) -> bool:
        return self._client.connected

    @property
    def is_volume_muted(self) -> bool | None:
        return self._muted

    @property
    def volume_level(self) -> float | None:
        if self._volume_raw is None:
            return None
        lo, hi = self._profile.volume_range
        span = max(1, hi - lo)
        return max(0.0, min(1.0, (self._volume_raw - lo) / span))

    @property
    def source(self) -> str | None:
        return self._source

    @property
    def source_list(self) -> list[str] | None:
        return self._sources

    # Commands
    async def async_turn_on(self) -> None:
        await self._client.command(self._profile.commands["power_on"])

    async def async_turn_off(self) -> None:
        await self._client.command(self._profile.commands["power_off"])

    async def async_mute_volume(self, mute: bool) -> None:
        await self._client.command(self._profile.commands["mute_on" if mute else "mute_off"])

    async def async_set_volume_level(self, volume: float) -> None:
        lo, hi = self._profile.volume_range
        span = hi - lo
        raw = int(round(max(0.0, min(1.0, volume)) * span + lo))
        template = self._profile.volume_set_template
        cmd = template.format(value=max(lo, min(hi, raw)))
        await self._client.command(cmd)

    async def async_select_source(self, source: str) -> None:
        s = source.lower()
        cmd = self._profile.sources.get(s)
        if not cmd:
            _LOGGER.debug("Unknown source %s, falling back to literal", s)
            cmd = f"{s}!"
        await self._client.command(cmd)

