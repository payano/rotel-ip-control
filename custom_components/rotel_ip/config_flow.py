from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT

from .const import (
    DOMAIN,
    DEFAULT_PORT,
    DEFAULT_NAME,
    CONF_MODEL,
    CONF_NAME,
    CONF_PROFILE,
    DEFAULT_PROFILE_KEY,
)
from .rotel import RotelClient
from .profiles import select_profile


class RotelIPConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            port = user_input.get(CONF_PORT) or DEFAULT_PORT

            # Connection test: try to connect and query model
            try:
                client = RotelClient(host, port, DEFAULT_PROFILE_KEY)
                await client.connect()
                # Query model using the default profile's command
                model = await client.query("model?")
                await client.close()

                profile_key = select_profile(model)

                await self.async_set_unique_id(f"rotel_ip_{host}_{port}")
                self._abort_if_unique_id_configured()

                data = {
                    CONF_HOST: host,
                    CONF_PORT: port,
                    CONF_MODEL: model or "unknown",
                    CONF_NAME: user_input.get(CONF_NAME) or DEFAULT_NAME,
                    CONF_PROFILE: profile_key,
                }
                return self.async_create_entry(title=data[CONF_NAME], data=data)
            except Exception:  # noqa: BLE001
                errors["base"] = "cannot_connect"

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_import(self, import_config):
        # Support YAML import if ever added (not required). Forward to UI step.
        return await self.async_step_user(import_config)

