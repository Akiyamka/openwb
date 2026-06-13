"""openWB integration for Home Assistant."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any, Mapping

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import (
    CONFIG_ENTRY_VERSION,
    CONF_BAUDRATE,
    CONF_PARITY,
    CONF_SERIAL_PORT,
    CONF_STOPBITS,
    PARITY_VALUES,
    STOPBITS_VALUES,
)
from .wb_mr6c_modbus import (
    ModbusTransport,
    PymodbusSerialTransport,
    WBMR6CModbusConnectionError,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class OpenWBBusConfig:
    """Validated serial bus configuration."""

    serial_port: str
    baudrate: int
    parity: str
    stopbits: int


@dataclass(slots=True)
class OpenWBBusRuntimeData:
    """Runtime data for one openWB serial bus."""

    transport: ModbusTransport


OpenWBConfigEntry = ConfigEntry[OpenWBBusRuntimeData]


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old openWB config entries."""
    if entry.version >= CONFIG_ENTRY_VERSION:
        return True

    if _bus_config_from_entry_data(entry.data) is None:
        _LOGGER.error(
            "openWB config entry %s cannot be migrated to a serial bus entry; "
            "remove and re-add the integration",
            entry.entry_id,
        )
        return False

    config_entries_manager = getattr(hass, "config_entries", None)
    update_entry = getattr(config_entries_manager, "async_update_entry", None)
    if callable(update_entry):
        update_entry(entry, version=CONFIG_ENTRY_VERSION)
    elif hasattr(entry, "version"):
        entry.version = CONFIG_ENTRY_VERSION

    return True


async def async_setup_entry(hass: HomeAssistant, entry: OpenWBConfigEntry) -> bool:
    """Set up openWB from a config entry."""
    bus_config = _bus_config_from_entry_data(entry.data)
    if bus_config is None:
        _LOGGER.error(
            "openWB config entry %s is missing serial bus settings; remove and "
            "re-add the integration",
            entry.entry_id,
        )
        return False

    try:
        transport = PymodbusSerialTransport(
            bus_config.serial_port,
            baudrate=bus_config.baudrate,
            parity=bus_config.parity,
            stopbits=bus_config.stopbits,
        )
        await transport.connect()
    except WBMR6CModbusConnectionError as err:
        raise ConfigEntryNotReady(
            f"Unable to open openWB serial bus {bus_config.serial_port}"
        ) from err

    entry.runtime_data = OpenWBBusRuntimeData(transport=transport)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: OpenWBConfigEntry) -> bool:
    """Unload an openWB config entry."""
    await entry.runtime_data.transport.close()
    return True


def _bus_config_from_entry_data(data: Mapping[str, Any]) -> OpenWBBusConfig | None:
    """Return validated bus config entry data, or None for unsupported entries."""
    serial_port = data.get(CONF_SERIAL_PORT)
    baudrate = data.get(CONF_BAUDRATE)
    parity = data.get(CONF_PARITY)
    stopbits = data.get(CONF_STOPBITS)

    if not isinstance(serial_port, str) or not serial_port.strip():
        return None
    if not _is_positive_int(baudrate):
        return None
    if not isinstance(parity, str) or parity not in PARITY_VALUES:
        return None
    if not _is_positive_int(stopbits) or stopbits not in STOPBITS_VALUES:
        return None

    return OpenWBBusConfig(
        serial_port=serial_port,
        baudrate=baudrate,
        parity=parity,
        stopbits=stopbits,
    )


def _is_positive_int(value: Any) -> bool:
    """Return whether value is a positive integer, excluding bool."""
    return isinstance(value, int) and not isinstance(value, bool) and value > 0
