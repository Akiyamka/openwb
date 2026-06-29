"""Device abstractions for supported Wiren Board modules."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Protocol

from ..wb_mr6c_modbus import (
    InputMode,
    MappingAction,
    MappingEvent,
    ModbusTransport,
    OutputPowerOnMode,
    PressCounterEvent,
    SafeModeAction,
    SafeModeInputControl,
    SafeState,
    WBMR6CBasicSettings,
)


@dataclass(frozen=True, slots=True)
class OpenWBDeviceMetadata:
    """Static device metadata retained for polling feature gates."""

    model: str | None
    firmware_version: str | None
    supports_inputs: bool
    supports_press_counters: bool
    supports_mapping_matrix: bool
    supports_relay_one_shot_commands: bool
    supports_relay_state_discrete_inputs: bool
    input_numbers: tuple[int, ...]
    output_numbers: tuple[int, ...]
    press_counter_input_registers: bool
    supports_fast_modbus_events: bool = False


@dataclass(frozen=True, slots=True)
class OpenWBDeviceState:
    """Live state read by the bus coordinator for one device."""

    input_states: dict[int, bool]
    press_counts: dict[tuple[int, str], int]
    relay_states: dict[int, bool]
    relay_commands: dict[int, bool]


class OpenWBDeviceClient(Protocol):
    """Device-level operations used by the Home Assistant runtime."""

    device_id: int

    async def read_model(self) -> str:
        """Read and decode the device model string."""
        ...

    async def read_firmware_version(self) -> str:
        """Read and decode the firmware version string."""
        ...

    async def read_press_counters(
        self,
        event: PressCounterEvent | int,
        input_numbers: Iterable[int],
        *,
        input_registers: bool = False,
    ) -> dict[int, int]:
        """Read press counters for one counter group."""
        ...

    async def read_input_states(
        self, input_numbers: Iterable[int]
    ) -> dict[int, bool]:
        """Read input states for the requested input numbers."""
        ...

    async def read_relay_commands(self) -> dict[int, bool]:
        """Read commanded relay states."""
        ...

    async def read_relay_states(self) -> dict[int, bool]:
        """Read actual relay states."""
        ...

    async def set_relay_command(self, channel: int, value: bool) -> None:
        """Set a persistent relay command."""
        ...

    async def turn_off(self, channel: int) -> None:
        """Send a one-shot relay off command."""
        ...

    async def turn_on(self, channel: int) -> None:
        """Send a one-shot relay on command."""
        ...

    async def toggle(self, channel: int) -> None:
        """Send a one-shot relay toggle command."""
        ...

    async def read_basic_settings(self) -> WBMR6CBasicSettings:
        """Read core on-demand settings."""
        ...

    async def read_output_power_on_mode(self) -> int:
        """Read output power-on behavior."""
        ...

    async def set_output_power_on_mode(
        self, mode: OutputPowerOnMode | int
    ) -> None:
        """Set output power-on behavior."""
        ...

    async def read_communication_timeout_s(self) -> int:
        """Read the communication-loss timeout in seconds."""
        ...

    async def set_communication_timeout_s(self, value: int) -> None:
        """Set the communication-loss timeout in seconds."""
        ...

    async def read_input_modes(self) -> dict[int, int]:
        """Read input modes."""
        ...

    async def set_input_mode(self, input_number: int, mode: InputMode | int) -> None:
        """Set one input mode."""
        ...

    async def read_debounce_ms(self) -> dict[int, int]:
        """Read input debounce timeouts."""
        ...

    async def set_debounce_ms(self, input_number: int, value: int) -> None:
        """Set one input debounce timeout."""
        ...

    async def read_long_press_ms(self) -> dict[int, int]:
        """Read input long-press timeouts."""
        ...

    async def set_long_press_ms(self, input_number: int, value: int) -> None:
        """Set one input long-press timeout."""
        ...

    async def read_second_press_wait_ms(self) -> dict[int, int]:
        """Read input second-press wait timeouts."""
        ...

    async def set_second_press_wait_ms(self, input_number: int, value: int) -> None:
        """Set one input second-press wait timeout."""
        ...

    async def read_safe_states(self) -> dict[int, bool]:
        """Read output safe states."""
        ...

    async def set_safe_state(
        self, output: int, state: SafeState | int | bool
    ) -> None:
        """Set one output safe state."""
        ...

    async def read_safe_mode_actions(self) -> dict[int, int]:
        """Read safe-mode output actions."""
        ...

    async def set_safe_mode_action(
        self, output: int, action: SafeModeAction | int
    ) -> None:
        """Set one safe-mode output action."""
        ...

    async def read_safe_mode_input_controls(self) -> dict[int, int]:
        """Read safe-mode input-control behavior."""
        ...

    async def set_safe_mode_input_control(
        self, output: int, control: SafeModeInputControl | int
    ) -> None:
        """Set one safe-mode input-control behavior."""
        ...

    async def read_mapping_action(
        self, event: MappingEvent | int, input_number: int, output: int
    ) -> int:
        """Read one mapping matrix cell."""
        ...

    async def set_mapping_action(
        self,
        event: MappingEvent | int,
        input_number: int,
        output: int,
        action: MappingAction | int,
    ) -> None:
        """Write one mapping matrix cell."""
        ...

    async def read_mapping_matrix(
        self, event: MappingEvent | int
    ) -> dict[tuple[int, int], int]:
        """Read one full mapping matrix."""
        ...

    async def write_mapping_matrix(
        self,
        event: MappingEvent | int,
        desired_matrix: Mapping[tuple[int, int], MappingAction | int],
    ) -> None:
        """Apply one mapping matrix, writing only changed cells."""
        ...


FirmwareGate = Callable[[str], bool]
DeviceClientFactory = Callable[[ModbusTransport, int], OpenWBDeviceClient]


@dataclass(frozen=True, slots=True)
class OpenWBDeviceDefinition:
    """Static descriptor for one supported Wiren Board model."""

    config_model: str
    raw_model_aliases: frozenset[str]
    display_name: str
    name_prefix: str
    input_numbers: tuple[int, ...]
    output_numbers: tuple[int, ...]
    supports_mapping_matrix: bool
    client_factory: DeviceClientFactory
    press_counter_input_registers: bool = False
    press_counter_firmware_gate: FirmwareGate | None = None
    relay_one_shot_firmware_gate: FirmwareGate | None = None
    relay_state_discrete_inputs_firmware_gate: FirmwareGate | None = None
    fast_modbus_events_firmware_gate: FirmwareGate | None = None

    def matches_model(self, model: str | None) -> bool:
        """Return whether a raw or stored model value belongs to this definition."""
        return model == self.config_model or model in self.raw_model_aliases
