"""Config flow for the openWB integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_DEVICE_ID,
    CONF_HOST,
    CONF_PORT,
    DEFAULT_DEVICE_ID,
    DEFAULT_PORT,
    DOMAIN,
)


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=65535)
        ),
        vol.Optional(CONF_DEVICE_ID, default=DEFAULT_DEVICE_ID): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=247)
        ),
    }
)


class OpenWBConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for openWB."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()

            if not host:
                errors["base"] = "host_required"
            else:
                data = {
                    CONF_HOST: host,
                    CONF_PORT: user_input.get(CONF_PORT, DEFAULT_PORT),
                    CONF_DEVICE_ID: user_input.get(
                        CONF_DEVICE_ID, DEFAULT_DEVICE_ID
                    ),
                }

                await self.async_set_unique_id(
                    (
                        f"{data[CONF_HOST].lower()}:"
                        f"{data[CONF_PORT]}:{data[CONF_DEVICE_ID]}"
                    )
                )
                self._abort_if_unique_id_configured(updates=data)

                return self.async_create_entry(title=data[CONF_HOST], data=data)

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
