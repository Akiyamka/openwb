"""Input press event entities for the openWB integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import cast, override

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import (
    PRESS_EVENT_TYPES,
    OpenWBConfigEntry,
    WBMR6CBusCoordinator,
    WBMR6CDeviceMetadata,
    WBMR6CDeviceState,
    WBMR6CPressEvent,
    device_model_display_name,
    device_id_from_subentry_data,
    device_name,
)
from .const import CONF_SERIAL_PORT, DOMAIN, SUBENTRY_TYPE_DEVICE
from .wb_mr6c_modbus import INPUTS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: OpenWBConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up input press event entities for one openWB bus entry."""
    serial_port_value = cast(object, entry.data[CONF_SERIAL_PORT])
    serial_port = str(serial_port_value)

    for config_subentry_id, device_id in _device_subentries(entry):
        if device_id not in entry.runtime_data.clients:
            _LOGGER.debug(
                "Skipping openWB input press events for device %s without runtime "
                + "client",
                device_id,
            )
            continue

        metadata = entry.runtime_data.device_metadata.get(device_id)
        input_numbers = metadata.input_numbers if metadata is not None else INPUTS
        if not input_numbers:
            _LOGGER.debug(
                "Skipping openWB input press events for device %s without inputs",
                device_id,
            )
            continue

        if not metadata or not metadata.supports_press_counters:
            _LOGGER.debug(
                "Skipping openWB input press events for device %s without press "
                + "counter support",
                device_id,
            )
            continue

        entities = [
            OpenWBInputPressEvent(
                entry=entry,
                serial_port=serial_port,
                device_id=device_id,
                input_number=input_number,
                event_type=event_type,
                metadata=metadata,
            )
            for input_number in input_numbers
            for event_type in PRESS_EVENT_TYPES
        ]
        async_add_entities(entities, config_subentry_id=config_subentry_id)


class OpenWBInputPressEvent(CoordinatorEntity[WBMR6CBusCoordinator], EventEntity):
    """Event entity for one WB-MR6C input press counter."""

    _attr_has_entity_name: bool = True

    def __init__(
        self,
        *,
        entry: OpenWBConfigEntry,
        serial_port: str,
        device_id: int,
        input_number: int,
        event_type: str,
        metadata: WBMR6CDeviceMetadata | None,
    ) -> None:
        """Initialize an input press event entity."""
        super().__init__(entry.runtime_data.coordinator)
        self._device_id: int = device_id
        self._input_number: int = input_number
        self._event_type: str = event_type

        event_slug = event_type.replace("-", "_")
        device_identifier = f"{serial_port}:{device_id}"
        self._attr_unique_id: str | None = (
            f"{device_identifier}:input_{input_number}_press_{event_slug}"
        )
        self._attr_name: str | None = f"Input {input_number} {event_type} press"
        self._attr_event_types: list[str] = [event_type]
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

        current_event = self._press_event
        self._last_event_sequence: int | None = (
            current_event.sequence if current_event is not None else None
        )

    @property
    @override
    def available(self) -> bool:  # pyright: ignore[reportIncompatibleVariableOverride]
        """Return whether coordinator data has this device/input counter."""
        state = self._device_state
        return (
            super().available
            and state is not None
            and (self._input_number, self._event_type) in state.press_counts
        )

    @override
    def _handle_coordinator_update(self) -> None:
        """Fire a Home Assistant event when the coordinator detects a new press."""
        event = self._press_event
        if event is not None and event.sequence != self._last_event_sequence:
            self._last_event_sequence = event.sequence
            self._trigger_event(
                event.event_type,
                {
                    "device_id": event.device_id,
                    "input": event.input_number,
                    "counter": event.counter,
                    "delta": event.delta,
                },
            )
        super()._handle_coordinator_update()

    @property
    def _device_state(self) -> WBMR6CDeviceState | None:
        data = self.coordinator.data
        state = data.get(self._device_id)
        if isinstance(state, WBMR6CDeviceState):
            return state
        return None

    @property
    def _press_event(self) -> WBMR6CPressEvent | None:
        events = self.coordinator.press_events
        event = events.get((self._device_id, self._input_number, self._event_type))
        return event


def _device_subentries(entry: OpenWBConfigEntry) -> list[tuple[str, int]]:
    """Return configured device subentry ids and device ids."""
    devices: list[tuple[str, int]] = []
    for config_subentry_id, subentry in entry.subentries.items():
        if subentry.subentry_type != SUBENTRY_TYPE_DEVICE:
            continue

        data: Mapping[str, object] = subentry.data

        device_id = device_id_from_subentry_data(data)
        if device_id is None:
            continue

        devices.append((config_subentry_id, device_id))
    return devices
