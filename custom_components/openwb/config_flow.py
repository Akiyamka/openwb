"""Config flow for the openWB integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    CONF_DEVICE_ID,
    DEFAULT_DEVICE_ID,
    DOMAIN,
)


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE_ID, default=str(DEFAULT_DEVICE_ID)): (
            selector.TextSelector(
                {
                    "type": selector.TextSelectorType.NUMBER,
                }
            )
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
            device_id = _parse_device_id(user_input.get(CONF_DEVICE_ID))

            if device_id is None:
                errors[CONF_DEVICE_ID] = "invalid_device_id"
            else:
                data = {CONF_DEVICE_ID: device_id}

                await self.async_set_unique_id(f"wb_mr6c:{device_id}")
                self._abort_if_unique_id_configured(updates=data)

                return self.async_create_entry(
                    title=f"WB-MR6C {device_id}", data=data
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )


def _parse_device_id(value: Any) -> int | None:
    """Parse and validate a Modbus device address."""
    try:
        device_id = int(value)
    except (TypeError, ValueError):
        return None

    if 1 <= device_id <= 247:
        return device_id
    return None
