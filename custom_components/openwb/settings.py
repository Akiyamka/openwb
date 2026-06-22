"""On-demand settings backend for the openWB integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import TypeVar

from homeassistant.exceptions import HomeAssistantError

from .devices.base import OpenWBDeviceClient
from .wb_mr6c_modbus import (
    InputMode,
    InvalidWBMR6CAddressError,
    InvalidWBMR6CValueError,
    OutputPowerOnMode,
    SafeModeAction,
    SafeModeInputControl,
    SafeState,
    WBMR6CBasicSettings,
    WBMR6CModbusError,
)

_SettingsResultT = TypeVar("_SettingsResultT")


@dataclass(frozen=True, slots=True)
class OpenWBSettingsBackend:
    """Home Assistant-facing on-demand settings operations for one bus."""

    clients: Mapping[int, OpenWBDeviceClient]

    async def read_basic_settings(self, device_id: int) -> WBMR6CBasicSettings:
        """Read the core settings group from one configured device."""
        return await self._execute(
            device_id,
            "read settings from",
            lambda client: client.read_basic_settings(),
        )

    async def read_input_modes(self, device_id: int) -> dict[int, int]:
        """Read input modes for one configured device."""
        return await self._execute(
            device_id,
            "read input modes from",
            lambda client: client.read_input_modes(),
        )

    async def set_input_mode(
        self, device_id: int, input_number: int, mode: InputMode | int
    ) -> None:
        """Set one input mode on a configured device."""
        await self._execute(
            device_id,
            "set input mode on",
            lambda client: client.set_input_mode(input_number, mode),
        )

    async def read_debounce_ms(self, device_id: int) -> dict[int, int]:
        """Read input debounce timeouts from one configured device."""
        return await self._execute(
            device_id,
            "read debounce timeouts from",
            lambda client: client.read_debounce_ms(),
        )

    async def set_debounce_ms(
        self, device_id: int, input_number: int, value: int
    ) -> None:
        """Set one input debounce timeout on a configured device."""
        await self._execute(
            device_id,
            "set debounce timeout on",
            lambda client: client.set_debounce_ms(input_number, value),
        )

    async def read_long_press_ms(self, device_id: int) -> dict[int, int]:
        """Read long-press timeouts from one configured device."""
        return await self._execute(
            device_id,
            "read long-press timeouts from",
            lambda client: client.read_long_press_ms(),
        )

    async def set_long_press_ms(
        self, device_id: int, input_number: int, value: int
    ) -> None:
        """Set one input long-press timeout on a configured device."""
        await self._execute(
            device_id,
            "set long-press timeout on",
            lambda client: client.set_long_press_ms(input_number, value),
        )

    async def read_second_press_wait_ms(self, device_id: int) -> dict[int, int]:
        """Read second-press wait timeouts from one configured device."""
        return await self._execute(
            device_id,
            "read second-press wait timeouts from",
            lambda client: client.read_second_press_wait_ms(),
        )

    async def set_second_press_wait_ms(
        self, device_id: int, input_number: int, value: int
    ) -> None:
        """Set one input second-press wait timeout on a configured device."""
        await self._execute(
            device_id,
            "set second-press wait timeout on",
            lambda client: client.set_second_press_wait_ms(input_number, value),
        )

    async def read_safe_states(self, device_id: int) -> dict[int, bool]:
        """Read relay safe states from one configured device."""
        return await self._execute(
            device_id,
            "read safe states from",
            lambda client: client.read_safe_states(),
        )

    async def set_safe_state(
        self, device_id: int, output: int, state: SafeState | int | bool
    ) -> None:
        """Set one relay safe state on a configured device."""
        await self._execute(
            device_id,
            "set safe state on",
            lambda client: client.set_safe_state(output, state),
        )

    async def read_safe_mode_actions(self, device_id: int) -> dict[int, int]:
        """Read safe-mode output actions from one configured device."""
        return await self._execute(
            device_id,
            "read safe-mode actions from",
            lambda client: client.read_safe_mode_actions(),
        )

    async def set_safe_mode_action(
        self, device_id: int, output: int, action: SafeModeAction | int
    ) -> None:
        """Set one safe-mode output action on a configured device."""
        await self._execute(
            device_id,
            "set safe-mode action on",
            lambda client: client.set_safe_mode_action(output, action),
        )

    async def read_safe_mode_input_controls(self, device_id: int) -> dict[int, int]:
        """Read safe-mode input-control behavior from one configured device."""
        return await self._execute(
            device_id,
            "read safe-mode input controls from",
            lambda client: client.read_safe_mode_input_controls(),
        )

    async def set_safe_mode_input_control(
        self, device_id: int, output: int, control: SafeModeInputControl | int
    ) -> None:
        """Set one safe-mode input-control behavior on a configured device."""
        await self._execute(
            device_id,
            "set safe-mode input control on",
            lambda client: client.set_safe_mode_input_control(output, control),
        )

    async def read_output_power_on_mode(self, device_id: int) -> int:
        """Read output power-on behavior from one configured device."""
        return await self._execute(
            device_id,
            "read output power-on mode from",
            lambda client: client.read_output_power_on_mode(),
        )

    async def set_output_power_on_mode(
        self, device_id: int, mode: OutputPowerOnMode | int
    ) -> None:
        """Set output power-on behavior on a configured device."""
        await self._execute(
            device_id,
            "set output power-on mode on",
            lambda client: client.set_output_power_on_mode(mode),
        )

    async def read_communication_timeout_s(self, device_id: int) -> int:
        """Read the communication-loss timeout from one configured device."""
        return await self._execute(
            device_id,
            "read communication timeout from",
            lambda client: client.read_communication_timeout_s(),
        )

    async def set_communication_timeout_s(self, device_id: int, value: int) -> None:
        """Set the communication-loss timeout on a configured device."""
        await self._execute(
            device_id,
            "set communication timeout on",
            lambda client: client.set_communication_timeout_s(value),
        )

    async def _execute(
        self,
        device_id: int,
        action: str,
        operation: Callable[[OpenWBDeviceClient], Awaitable[_SettingsResultT]],
    ) -> _SettingsResultT:
        client = self.clients.get(device_id)
        if client is None:
            raise HomeAssistantError(
                f"openWB device {device_id} is not configured on this bus"
            )

        try:
            return await operation(client)
        except (InvalidWBMR6CAddressError, InvalidWBMR6CValueError) as err:
            raise HomeAssistantError(
                f"Invalid openWB settings value for device {device_id}: {err}"
            ) from err
        except WBMR6CModbusError as err:
            raise HomeAssistantError(
                f"Unable to {action} openWB device {device_id}"
            ) from err
