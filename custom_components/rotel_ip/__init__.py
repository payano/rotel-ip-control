from __future__ import annotations

import asyncio
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_HOST, CONF_PORT, Platform

from .const import DOMAIN, PLATFORMS, CONF_PROFILE
from .rotel import RotelClient

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    host = entry.data[CONF_HOST]
    port = entry.data.get(CONF_PORT)
    profile_key = entry.data.get(CONF_PROFILE)

    client = RotelClient(host, port, profile_key)

    # Establish connection early so config flow's test aligns with runtime
    await client.connect()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = client

    await hass.config_entries.async_forward_entry_setups(entry, [Platform.MEDIA_PLAYER])

    async def _handle_stop(event):
        await client.close()

    entry.async_on_unload(hass.bus.async_listen_once("homeassistant_stop", _handle_stop))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, [Platform.MEDIA_PLAYER])

    client: RotelClient | None = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    if client:
        await client.close()

    return unloaded

