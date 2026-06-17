"""Device abstractions for supported Wiren Board modules."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any, Protocol


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

    async def read_firmware_version(self) -> str:
        """Read and decode the firmware version string."""

    async def read_press_counters(
        self,
        event: Any,
        input_numbers: Iterable[int],
        *,
        input_registers: bool = False,
    ) -> dict[int, int]:
        """Read press counters for one counter group."""

    async def read_input_states(
        self, input_numbers: Iterable[int]
    ) -> dict[int, bool]:
        """Read input states for the requested input numbers."""

    async def read_relay_commands(self) -> dict[int, bool]:
        """Read commanded relay states."""

    async def read_relay_states(self) -> dict[int, bool]:
        """Read actual relay states."""

    async def set_relay_command(self, channel: int, value: bool) -> None:
        """Set a persistent relay command."""

    async def turn_off(self, channel: int) -> None:
        """Send a one-shot relay off command."""

    async def turn_on(self, channel: int) -> None:
        """Send a one-shot relay on command."""

    async def toggle(self, channel: int) -> None:
        """Send a one-shot relay toggle command."""


FirmwareGate = Callable[[str], bool]
DeviceClientFactory = Callable[[Any, int], OpenWBDeviceClient]


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

    def matches_model(self, model: str | None) -> bool:
        """Return whether a raw or stored model value belongs to this definition."""
        return model == self.config_model or model in self.raw_model_aliases
