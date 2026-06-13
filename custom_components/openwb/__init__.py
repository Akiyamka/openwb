"""openWB integration for Home Assistant."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up openWB from a config entry."""
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = dict(entry.data)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an openWB config entry."""
    domain_data: dict[str, Any] = hass.data.get(DOMAIN, {})
    domain_data.pop(entry.entry_id, None)

    if not domain_data:
        hass.data.pop(DOMAIN, None)

    return True

