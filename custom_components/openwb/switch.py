"""Relay switch entities for the openWB integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
import logging
from typing import cast, override

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import (
    OpenWBConfigEntry,
    WBMR6CBusCoordinator,
    WBMR6CDeviceMetadata,
    WBMR6CDeviceState,
    device_model_display_name,
    device_id_from_subentry_data,
    device_name,
)
from .const import CONF_SERIAL_PORT, DOMAIN, SUBENTRY_TYPE_DEVICE
from .devices.base import OpenWBDeviceClient
from .wb_mr6c_modbus import OUTPUTS, WBMR6CModbusError

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: OpenWBConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up relay switch entities for one openWB bus entry."""
    serial_port_value = cast(object, entry.data[CONF_SERIAL_PORT])
    serial_port = str(serial_port_value)

    for config_subentry_id, device_id in _device_subentries(entry):
        client = entry.runtime_data.clients.get(device_id)
        if client is None:
            _LOGGER.debug(
                "Skipping openWB switch entities for device %s without runtime client",
                device_id,
            )
            continue

        metadata = entry.runtime_data.device_metadata.get(device_id)
        output_numbers = metadata.output_numbers if metadata is not None else OUTPUTS
        if not output_numbers:
            _LOGGER.debug(
                "Skipping openWB switch entities for device %s without relay outputs",
                device_id,
            )
            continue

        entities = [
            OpenWBRelaySwitch(
                entry=entry,
                client=client,
                serial_port=serial_port,
                device_id=device_id,
                output=output,
                metadata=metadata,
            )
            for output in output_numbers
        ]
        async_add_entities(entities, config_subentry_id=config_subentry_id)


class OpenWBRelaySwitch(CoordinatorEntity[WBMR6CBusCoordinator], SwitchEntity):
    """Switch entity for one WB-MR6C relay output."""

    _attr_has_entity_name: bool = True

    def __init__(
        self,
        *,
        entry: OpenWBConfigEntry,
        client: OpenWBDeviceClient,
        serial_port: str,
        device_id: int,
        output: int,
        metadata: WBMR6CDeviceMetadata | None,
    ) -> None:
        """Initialize a relay switch entity."""
        super().__init__(entry.runtime_data.coordinator)
        self._client: OpenWBDeviceClient = client
        self._device_id: int = device_id
        self._output: int = output
        self._supports_relay_one_shot_commands: bool = (
            metadata.supports_relay_one_shot_commands if metadata else False
        )
        self._optimistic_state: bool | None = None

        device_identifier = f"{serial_port}:{device_id}"
        self._attr_unique_id: str | None = f"{device_identifier}:relay_{output}"
        self._attr_name: str | None = f"Relay {output}"
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
        """Return whether coordinator data has this device and output."""
        state = self._device_state
        return (
            super().available
            and state is not None
            and self._output in state.relay_states
        )

    @property
    @override
    def is_on(self) -> bool | None:  # pyright: ignore[reportIncompatibleVariableOverride]
        """Return the cached relay state."""
        if self._optimistic_state is not None:
            return self._optimistic_state

        state = self._device_state
        if state is None:
            return None
        return state.relay_states.get(self._output)

    @override
    async def async_turn_on(self, **kwargs: object) -> None:
        """Turn the relay output on."""
        if self._supports_relay_one_shot_commands:
            await self._async_write_relay("turn on", self._client.turn_on, True)
            return

        await self._async_write_relay(
            "turn on",
            lambda output: self._client.set_relay_command(output, True),
            True,
        )

    @override
    async def async_turn_off(self, **kwargs: object) -> None:
        """Turn the relay output off."""
        if self._supports_relay_one_shot_commands:
            await self._async_write_relay("turn off", self._client.turn_off, False)
            return

        await self._async_write_relay(
            "turn off",
            lambda output: self._client.set_relay_command(output, False),
            False,
        )

    @override
    async def async_toggle(self, **kwargs: object) -> None:
        """Toggle the relay output."""
        current_state = self.is_on
        optimistic_state = None if current_state is None else not current_state
        if not self._supports_relay_one_shot_commands:
            if optimistic_state is None:
                raise HomeAssistantError(
                    f"Unable to toggle openWB relay {self._output} "
                    + f"on device {self._device_id} without a current relay state"
                )
            await self._async_write_relay(
                "toggle",
                lambda output: self._client.set_relay_command(
                    output, optimistic_state
                ),
                optimistic_state,
            )
            return

        await self._async_write_relay(
            "toggle", self._client.toggle, optimistic_state
        )

    @override
    def _handle_coordinator_update(self) -> None:
        """Clear optimistic state when a scheduled poll supplies fresh data."""
        self._optimistic_state = None
        super()._handle_coordinator_update()

    @property
    def _device_state(self) -> WBMR6CDeviceState | None:
        data = self.coordinator.data
        state = data.get(self._device_id)
        if isinstance(state, WBMR6CDeviceState):
            return state
        return None

    async def _async_write_relay(
        self,
        action: str,
        write_method: Callable[[int], Awaitable[None]],
        optimistic_state: bool | None,
    ) -> None:
        try:
            await write_method(self._output)
        except WBMR6CModbusError as err:
            raise HomeAssistantError(
                f"Unable to {action} openWB relay {self._output} "
                + f"on device {self._device_id}"
            ) from err

        self._optimistic_state = optimistic_state
        self.async_write_ha_state()


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
