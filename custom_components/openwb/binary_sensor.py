"""Input level binary sensors for the openWB integration."""

from __future__ import annotations

from collections.abc import Callable, Mapping
import logging
from typing import override

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import (
    OpenWBConfigEntry,
    WBMR6CBusCoordinator,
    WBMR6CDeviceMetadata,
    WBMR6CDeviceState,
    device_model_display_name,
    device_name,
)
from . import _device_id_from_subentry_data
from .const import CONF_SERIAL_PORT, DOMAIN, SUBENTRY_TYPE_DEVICE
from .wb_mr6c_modbus import INPUTS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OpenWBConfigEntry,
    async_add_entities: Callable[..., None],
) -> None:
    """Set up input level binary sensors for one openWB bus entry."""
    serial_port = str(entry.data[CONF_SERIAL_PORT])

    for config_subentry_id, device_id in _device_subentries(entry):
        if device_id not in entry.runtime_data.clients:
            _LOGGER.debug(
                "Skipping openWB input binary sensors for device %s without "
                + "runtime client",
                device_id,
            )
            continue

        metadata = entry.runtime_data.device_metadata.get(device_id)
        input_numbers = metadata.input_numbers if metadata is not None else INPUTS
        if not input_numbers:
            _LOGGER.debug(
                "Skipping openWB input binary sensors for device %s without inputs",
                device_id,
            )
            continue

        entities = [
            OpenWBInputBinarySensor(
                entry=entry,
                serial_port=serial_port,
                device_id=device_id,
                input_number=input_number,
                metadata=metadata,
            )
            for input_number in input_numbers
        ]
        async_add_entities(entities, config_subentry_id=config_subentry_id)


class OpenWBInputBinarySensor(
    CoordinatorEntity[WBMR6CBusCoordinator], BinarySensorEntity
):
    """Binary sensor entity for one WB-MR6C input level."""

    _attr_has_entity_name: bool = True

    def __init__(
        self,
        *,
        entry: OpenWBConfigEntry,
        serial_port: str,
        device_id: int,
        input_number: int,
        metadata: WBMR6CDeviceMetadata | None,
    ) -> None:
        """Initialize an input level binary sensor."""
        super().__init__(entry.runtime_data.coordinator)
        self._device_id: int = device_id
        self._input_number: int = input_number

        device_identifier = f"{serial_port}:{device_id}"
        self._attr_unique_id: str | None = f"{device_identifier}:input_{input_number}"
        self._attr_name: str | None = f"Input {input_number}"
        self._attr_device_info: DeviceInfo | None = {
            "identifiers": {(DOMAIN, device_identifier)},
            "manufacturer": "Wiren Board",
            "model": device_model_display_name(
                metadata.model if metadata else None
            ),
            "name": device_name(metadata.model if metadata else None, device_id),
        }
        if metadata and metadata.firmware_version:
            self._attr_device_info["sw_version"] = metadata.firmware_version

    @property
    @override
    def available(self) -> bool:  # pyright: ignore[reportIncompatibleVariableOverride]
        """Return whether coordinator data has this device and input."""
        state = self._device_state
        return (
            super().available
            and state is not None
            and self._input_number in state.input_states
        )

    @property
    @override
    def is_on(self) -> bool | None:  # pyright: ignore[reportIncompatibleVariableOverride]
        """Return the cached input level."""
        state = self._device_state
        if state is None:
            return None
        return state.input_states.get(self._input_number)

    @property
    def _device_state(self) -> WBMR6CDeviceState | None:
        data = self.coordinator.data
        if not isinstance(data, Mapping):
            return None
        state = data.get(self._device_id)
        if isinstance(state, WBMR6CDeviceState):
            return state
        return None


def _device_subentries(entry: OpenWBConfigEntry) -> list[tuple[str, int]]:
    """Return configured device subentry ids and device ids."""
    devices: list[tuple[str, int]] = []
    for config_subentry_id, subentry in getattr(entry, "subentries", {}).items():
        subentry_type = getattr(subentry, "subentry_type", SUBENTRY_TYPE_DEVICE)
        if subentry_type != SUBENTRY_TYPE_DEVICE:
            continue

        data = getattr(subentry, "data", {})
        if not isinstance(data, Mapping):
            continue

        device_id = _device_id_from_subentry_data(data)
        if device_id is None:
            continue

        subentry_id = getattr(subentry, "subentry_id", None) or config_subentry_id
        devices.append((subentry_id, device_id))
    return devices
