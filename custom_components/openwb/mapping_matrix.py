"""On-demand mapping matrix backend for the openWB integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import TypeVar

from homeassistant.exceptions import HomeAssistantError

from .devices.base import OpenWBDeviceClient, OpenWBDeviceMetadata
from .wb_mr6c_modbus import (
    InvalidWBMR6CAddressError,
    InvalidWBMR6CValueError,
    MappingAction,
    MappingEvent,
    WBMR6CModbusError,
)

_MappingResultT = TypeVar("_MappingResultT")


@dataclass(frozen=True, slots=True)
class OpenWBMappingMatrixBackend:
    """Home Assistant-facing mapping matrix operations for one bus."""

    clients: Mapping[int, OpenWBDeviceClient]
    device_metadata: Mapping[int, OpenWBDeviceMetadata]

    async def read_mapping_action(
        self, device_id: int, event: MappingEvent | int, input_number: int, output: int
    ) -> int:
        """Read one mapping matrix cell from a configured device."""
        return await self._execute(
            device_id,
            "read mapping action from",
            lambda client: client.read_mapping_action(event, input_number, output),
        )

    async def set_mapping_action(
        self,
        device_id: int,
        event: MappingEvent | int,
        input_number: int,
        output: int,
        action: MappingAction | int,
    ) -> None:
        """Write one mapping matrix cell on a configured device."""
        await self._execute(
            device_id,
            "set mapping action on",
            lambda client: client.set_mapping_action(
                event, input_number, output, action
            ),
        )

    async def read_mapping_matrix(
        self, device_id: int, event: MappingEvent | int
    ) -> dict[tuple[int, int], int]:
        """Read one full mapping matrix from a configured device."""
        return await self._execute(
            device_id,
            "read mapping matrix from",
            lambda client: client.read_mapping_matrix(event),
        )

    async def write_mapping_matrix(
        self,
        device_id: int,
        event: MappingEvent | int,
        desired_matrix: Mapping[tuple[int, int], MappingAction | int],
    ) -> None:
        """Apply one full mapping matrix through the device diff-write client."""
        await self._execute(
            device_id,
            "write mapping matrix on",
            lambda client: client.write_mapping_matrix(event, desired_matrix),
        )

    async def _execute(
        self,
        device_id: int,
        action: str,
        operation: Callable[[OpenWBDeviceClient], Awaitable[_MappingResultT]],
    ) -> _MappingResultT:
        client = self.clients.get(device_id)
        if client is None:
            raise HomeAssistantError(
                f"openWB device {device_id} is not configured on this bus"
            )

        metadata = self.device_metadata.get(device_id)
        if metadata is not None and not metadata.supports_mapping_matrix:
            raise HomeAssistantError(
                f"openWB device {device_id} does not support mapping matrix"
            )

        try:
            return await operation(client)
        except (InvalidWBMR6CAddressError, InvalidWBMR6CValueError) as err:
            raise HomeAssistantError(
                f"Invalid openWB mapping matrix value for device {device_id}: {err}"
            ) from err
        except WBMR6CModbusError as err:
            raise HomeAssistantError(
                f"Unable to {action} openWB device {device_id}"
            ) from err
