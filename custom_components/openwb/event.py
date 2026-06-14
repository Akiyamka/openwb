"""Input press event entities for the openWB integration."""

from __future__ import annotations

from collections.abc import Callable, Mapping
import logging

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import (
    PRESS_EVENT_TYPES,
    OpenWBConfigEntry,
    WBMR6CDeviceMetadata,
    WBMR6CDeviceState,
    WBMR6CPressEvent,
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
    """Set up input press event entities for one openWB bus entry."""
    serial_port = str(entry.data[CONF_SERIAL_PORT])

    for config_subentry_id, device_id in _device_subentries(entry):
        if device_id not in entry.runtime_data.clients:
            _LOGGER.debug(
                "Skipping openWB input press events for device %s without runtime "
                "client",
                device_id,
            )
            continue

        metadata = entry.runtime_data.device_metadata.get(device_id)
        if metadata is not None and not metadata.supports_inputs:
            _LOGGER.debug(
                "Skipping openWB input press events for device %s without inputs",
                device_id,
            )
            continue

        if not metadata or not metadata.supports_press_counters:
            _LOGGER.debug(
                "Skipping openWB input press events for device %s without press "
                "counter support",
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
            for input_number in INPUTS
            for event_type in PRESS_EVENT_TYPES
        ]
        async_add_entities(entities, config_subentry_id=config_subentry_id)


class OpenWBInputPressEvent(CoordinatorEntity, EventEntity):
    """Event entity for one WB-MR6C input press counter."""

    _attr_has_entity_name = True

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
        self._device_id = device_id
        self._input_number = input_number
        self._event_type = event_type

        event_slug = event_type.replace("-", "_")
        device_identifier = f"{serial_port}:{device_id}"
        self._attr_unique_id = (
            f"{device_identifier}:input_{input_number}_press_{event_slug}"
        )
        self._attr_name = f"Input {input_number} {event_type} press"
        self._attr_event_types = [event_type]
        self._attr_device_info = {
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
        self._last_event_sequence = (
            current_event.sequence if current_event is not None else None
        )

    @property
    def available(self) -> bool:
        """Return whether coordinator data has this device/input counter."""
        state = self._device_state
        return (
            super().available
            and state is not None
            and (self._input_number, self._event_type) in state.press_counts
        )

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
        if not isinstance(data, Mapping):
            return None
        state = data.get(self._device_id)
        if isinstance(state, WBMR6CDeviceState):
            return state
        return None

    @property
    def _press_event(self) -> WBMR6CPressEvent | None:
        events = getattr(self.coordinator, "press_events", {})
        if not isinstance(events, Mapping):
            return None
        event = events.get((self._device_id, self._input_number, self._event_type))
        if isinstance(event, WBMR6CPressEvent):
            return event
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
