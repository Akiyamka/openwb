"""Modbus backend for Wiren Board WB-MR6C v.2."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Protocol, Sequence

DEFAULT_DEVICE_ID = 1
DEFAULT_MODBUS_TCP_PORT = 502

CHANNEL_COUNT = 6
CHANNELS = tuple(range(1, CHANNEL_COUNT + 1))
INPUTS = (1, 2, 3, 4, 5, 6, 0)
OUTPUTS = CHANNELS

COIL_RELAY_COMMAND_BASE = 0
COIL_RELAY_OFF_COMMAND_BASE = 100
COIL_RELAY_ON_COMMAND_BASE = 108
COIL_RELAY_TOGGLE_COMMAND_BASE = 116

DISCRETE_INPUT_STATE_BASE = 0
DISCRETE_RELAY_STATE_BASE = 96

REG_OUTPUT_POWER_ON_MODE = 6
REG_COMMUNICATION_TIMEOUT_S = 8
REG_INPUT_MODE_BASE = 9
REG_INPUT_DEBOUNCE_MS_BASE = 20
REG_SAFE_STATE_BASE = 930
REG_SAFE_MODE_ACTION_BASE = 938
REG_SAFE_MODE_INPUT_CONTROL_BASE = 946
REG_LONG_PRESS_MS_BASE = 1100
REG_SECOND_PRESS_WAIT_MS_BASE = 1140


class WBMR6CModbusError(Exception):
    """Base error for WB-MR6C Modbus operations."""


class WBMR6CModbusConnectionError(WBMR6CModbusError):
    """Raised when the Modbus transport cannot communicate with the device."""


class WBMR6CModbusResponseError(WBMR6CModbusError):
    """Raised when the device returns an invalid or error response."""


class InvalidWBMR6CAddressError(ValueError):
    """Raised when a relay channel, input, output, or register is invalid."""


class OutputPowerOnMode(IntEnum):
    """Output behavior after device power-up."""

    SAFE_STATE = 0
    RESTORE_LAST_STATE = 1
    FOLLOW_INPUT = 2


class InputMode(IntEnum):
    """Input mode values used by WB-MR6C v.2."""

    MOMENTARY = 0
    LATCHING = 1
    DISABLE_ALL_OUTPUTS = 2
    FREQUENCY = 3
    MAPPING_MATRIX_EDGE = 4
    DISABLED = 5
    MAPPING_MATRIX_BUTTON = 6


class MappingAction(IntEnum):
    """Mapping matrix action values."""

    NONE = 0
    OFF = 1
    ON = 2
    TOGGLE = 3


class MappingEvent(IntEnum):
    """Mapping matrix register bases."""

    SHORT_PRESS = 544
    LONG_PRESS = 608
    DOUBLE_PRESS = 672
    SHORT_THEN_LONG_PRESS = 736
    FALLING_EDGE = 800
    RISING_EDGE = 864


class SafeState(IntEnum):
    """Safe-state relay value."""

    OFF = 0
    ON = 1


class SafeModeAction(IntEnum):
    """Action applied to an output in safe mode."""

    KEEP_CURRENT_STATE = 0
    SET_SAFE_STATE = 1


class SafeModeInputControl(IntEnum):
    """Input control behavior while safe mode is active."""

    DO_NOT_BLOCK = 0
    BLOCK_IN_SAFE_MODE = 1
    ALLOW_ONLY_IN_SAFE_MODE = 2


class ModbusTransport(Protocol):
    """Minimal async Modbus transport required by the WB-MR6C backend."""

    async def read_coils(
        self, address: int, count: int, device_id: int
    ) -> Sequence[bool]:
        """Read coil values."""

    async def write_coil(self, address: int, value: bool, device_id: int) -> None:
        """Write a single coil value."""

    async def read_discrete_inputs(
        self, address: int, count: int, device_id: int
    ) -> Sequence[bool]:
        """Read discrete input values."""

    async def read_holding_registers(
        self, address: int, count: int, device_id: int
    ) -> Sequence[int]:
        """Read holding register values."""

    async def write_register(self, address: int, value: int, device_id: int) -> None:
        """Write a single holding register."""


class PymodbusTcpTransport:
    """Async Modbus TCP transport backed by pymodbus."""

    def __init__(
        self,
        host: str,
        port: int = DEFAULT_MODBUS_TCP_PORT,
        *,
        timeout: float = 3.0,
        retries: int = 3,
    ) -> None:
        """Initialize the transport."""
        from pymodbus.client import AsyncModbusTcpClient

        self._client = AsyncModbusTcpClient(
            host,
            port=port,
            timeout=timeout,
            retries=retries,
        )
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        """Open the Modbus TCP connection if needed."""
        if self._client.connected:
            return

        if not await self._client.connect():
            raise WBMR6CModbusConnectionError("Unable to connect to Modbus device")

    async def close(self) -> None:
        """Close the Modbus TCP connection."""
        self._client.close()

    async def read_coils(
        self, address: int, count: int, device_id: int
    ) -> Sequence[bool]:
        """Read coil values."""
        response = await self._execute(
            "read_coils", address, count, device_id=device_id
        )
        return _extract_bits(response, count)

    async def write_coil(self, address: int, value: bool, device_id: int) -> None:
        """Write a single coil value."""
        await self._execute("write_coil", address, value, device_id=device_id)

    async def read_discrete_inputs(
        self, address: int, count: int, device_id: int
    ) -> Sequence[bool]:
        """Read discrete input values."""
        response = await self._execute(
            "read_discrete_inputs", address, count, device_id=device_id
        )
        return _extract_bits(response, count)

    async def read_holding_registers(
        self, address: int, count: int, device_id: int
    ) -> Sequence[int]:
        """Read holding register values."""
        response = await self._execute(
            "read_holding_registers", address, count, device_id=device_id
        )
        return _extract_registers(response, count)

    async def write_register(self, address: int, value: int, device_id: int) -> None:
        """Write a single holding register."""
        _validate_register_value(value)
        await self._execute("write_register", address, value, device_id=device_id)

    async def _execute(
        self, method_name: str, *args: Any, device_id: int
    ) -> Any:
        async with self._lock:
            await self.connect()
            method = getattr(self._client, method_name)

            try:
                response = await method(*args, device_id=device_id)
            except Exception as err:  # noqa: BLE001
                raise WBMR6CModbusConnectionError(
                    f"Modbus request failed: {method_name}"
                ) from err

            is_error = getattr(response, "isError", None)
            if response is None or (callable(is_error) and is_error()):
                raise WBMR6CModbusResponseError(
                    f"Modbus request returned an error: {method_name}"
                )

            return response


@dataclass(frozen=True, slots=True)
class WBMR6CRelaySnapshot:
    """Current relay commands, relay states, and input states."""

    commands: dict[int, bool]
    states: dict[int, bool]
    inputs: dict[int, bool]


@dataclass(frozen=True, slots=True)
class WBMR6CBasicSettings:
    """Core settings used by the UI settings screen."""

    output_power_on_mode: int
    communication_timeout_s: int
    input_modes: dict[int, int]
    debounce_ms: dict[int, int]
    safe_states: dict[int, bool]
    safe_mode_actions: dict[int, int]
    safe_mode_input_controls: dict[int, int]


@dataclass(slots=True)
class WBMR6CModbus:
    """High-level WB-MR6C v.2 Modbus commands."""

    transport: ModbusTransport
    device_id: int = DEFAULT_DEVICE_ID

    async def read_relay_commands(self) -> dict[int, bool]:
        """Read commanded relay states from coils 0..5."""
        values = await self.transport.read_coils(
            COIL_RELAY_COMMAND_BASE, CHANNEL_COUNT, self.device_id
        )
        return _channel_bool_map(values)

    async def read_relay_states(self) -> dict[int, bool]:
        """Read actual relay states from discrete inputs 96..101."""
        values = await self.transport.read_discrete_inputs(
            DISCRETE_RELAY_STATE_BASE, CHANNEL_COUNT, self.device_id
        )
        return _channel_bool_map(values)

    async def read_input_states(self) -> dict[int, bool]:
        """Read input states for inputs 1..6 and 0."""
        values = await self.transport.read_discrete_inputs(
            DISCRETE_INPUT_STATE_BASE, 8, self.device_id
        )
        return {
            input_number: bool(values[_input_index(input_number)])
            for input_number in INPUTS
        }

    async def read_snapshot(self) -> WBMR6CRelaySnapshot:
        """Read relay commands, actual relay states, and input states."""
        commands, states, inputs = await asyncio.gather(
            self.read_relay_commands(),
            self.read_relay_states(),
            self.read_input_states(),
        )
        return WBMR6CRelaySnapshot(commands=commands, states=states, inputs=inputs)

    async def set_relay_command(self, channel: int, value: bool) -> None:
        """Set the persistent relay command coil for a channel."""
        await self.transport.write_coil(
            relay_channel_address(COIL_RELAY_COMMAND_BASE, channel),
            value,
            self.device_id,
        )

    async def turn_off(self, channel: int) -> None:
        """Send a one-shot relay off command."""
        await self.transport.write_coil(
            relay_channel_address(COIL_RELAY_OFF_COMMAND_BASE, channel),
            True,
            self.device_id,
        )

    async def turn_on(self, channel: int) -> None:
        """Send a one-shot relay on command."""
        await self.transport.write_coil(
            relay_channel_address(COIL_RELAY_ON_COMMAND_BASE, channel),
            True,
            self.device_id,
        )

    async def toggle(self, channel: int) -> None:
        """Send a one-shot relay toggle command."""
        await self.transport.write_coil(
            relay_channel_address(COIL_RELAY_TOGGLE_COMMAND_BASE, channel),
            True,
            self.device_id,
        )

    async def read_basic_settings(self) -> WBMR6CBasicSettings:
        """Read core settings that are expected on the first UI settings screen."""
        return WBMR6CBasicSettings(
            output_power_on_mode=await self.read_register(REG_OUTPUT_POWER_ON_MODE),
            communication_timeout_s=await self.read_register(
                REG_COMMUNICATION_TIMEOUT_S
            ),
            input_modes=await self.read_input_modes(),
            debounce_ms=await self.read_debounce_ms(),
            safe_states=await self.read_safe_states(),
            safe_mode_actions=await self.read_safe_mode_actions(),
            safe_mode_input_controls=await self.read_safe_mode_input_controls(),
        )

    async def read_register(self, address: int) -> int:
        """Read a single holding register."""
        values = await self.transport.read_holding_registers(
            address, 1, self.device_id
        )
        if not values:
            raise WBMR6CModbusResponseError(f"No value returned for register {address}")
        return int(values[0])

    async def write_register(self, address: int, value: int) -> None:
        """Write a single holding register."""
        _validate_register_value(value)
        await self.transport.write_register(address, value, self.device_id)

    async def read_input_modes(self) -> dict[int, int]:
        """Read input modes for inputs 1..6 and 0."""
        return await self._read_input_registers(REG_INPUT_MODE_BASE)

    async def set_input_mode(self, input_number: int, mode: InputMode | int) -> None:
        """Set mode for one input."""
        await self.write_register(
            input_register_address(REG_INPUT_MODE_BASE, input_number),
            int(InputMode(mode)),
        )

    async def read_debounce_ms(self) -> dict[int, int]:
        """Read debounce timeout in milliseconds for inputs 1..6 and 0."""
        return await self._read_input_registers(REG_INPUT_DEBOUNCE_MS_BASE)

    async def set_debounce_ms(self, input_number: int, value: int) -> None:
        """Set debounce timeout in milliseconds for one input."""
        _validate_value_range(value, 0, 2000, "debounce_ms")
        await self.write_register(
            input_register_address(REG_INPUT_DEBOUNCE_MS_BASE, input_number),
            value,
        )

    async def read_long_press_ms(self) -> dict[int, int]:
        """Read long-press timeout in milliseconds for inputs 1..6 and 0."""
        return await self._read_input_registers(REG_LONG_PRESS_MS_BASE)

    async def set_long_press_ms(self, input_number: int, value: int) -> None:
        """Set long-press timeout in milliseconds for one input."""
        _validate_value_range(value, 500, 5000, "long_press_ms")
        await self.write_register(
            input_register_address(REG_LONG_PRESS_MS_BASE, input_number),
            value,
        )

    async def read_second_press_wait_ms(self) -> dict[int, int]:
        """Read second-press wait timeout in milliseconds for inputs 1..6 and 0."""
        return await self._read_input_registers(REG_SECOND_PRESS_WAIT_MS_BASE)

    async def set_second_press_wait_ms(self, input_number: int, value: int) -> None:
        """Set second-press wait timeout in milliseconds for one input."""
        _validate_value_range(value, 0, 2000, "second_press_wait_ms")
        await self.write_register(
            input_register_address(REG_SECOND_PRESS_WAIT_MS_BASE, input_number),
            value,
        )

    async def read_safe_states(self) -> dict[int, bool]:
        """Read safe states for outputs 1..6."""
        values = await self.transport.read_holding_registers(
            REG_SAFE_STATE_BASE, CHANNEL_COUNT, self.device_id
        )
        return _channel_bool_map(values)

    async def set_safe_state(self, output: int, state: SafeState | int | bool) -> None:
        """Set safe state for one output."""
        value = int(bool(state)) if isinstance(state, bool) else int(SafeState(state))
        await self.write_register(
            relay_channel_address(REG_SAFE_STATE_BASE, output), value
        )

    async def read_safe_mode_actions(self) -> dict[int, int]:
        """Read safe-mode actions for outputs 1..6."""
        values = await self.transport.read_holding_registers(
            REG_SAFE_MODE_ACTION_BASE, CHANNEL_COUNT, self.device_id
        )
        return _channel_int_map(values)

    async def set_safe_mode_action(
        self, output: int, action: SafeModeAction | int
    ) -> None:
        """Set safe-mode action for one output."""
        await self.write_register(
            relay_channel_address(REG_SAFE_MODE_ACTION_BASE, output),
            int(SafeModeAction(action)),
        )

    async def read_safe_mode_input_controls(self) -> dict[int, int]:
        """Read safe-mode input controls for outputs 1..6."""
        values = await self.transport.read_holding_registers(
            REG_SAFE_MODE_INPUT_CONTROL_BASE, CHANNEL_COUNT, self.device_id
        )
        return _channel_int_map(values)

    async def set_safe_mode_input_control(
        self, output: int, control: SafeModeInputControl | int
    ) -> None:
        """Set safe-mode input control for one output."""
        await self.write_register(
            relay_channel_address(REG_SAFE_MODE_INPUT_CONTROL_BASE, output),
            int(SafeModeInputControl(control)),
        )

    async def read_mapping_action(
        self, event: MappingEvent | int, input_number: int, output: int
    ) -> int:
        """Read one mapping matrix cell."""
        return await self.read_register(
            mapping_register_address(event, input_number, output)
        )

    async def set_mapping_action(
        self,
        event: MappingEvent | int,
        input_number: int,
        output: int,
        action: MappingAction | int,
    ) -> None:
        """Write one mapping matrix cell."""
        await self.write_register(
            mapping_register_address(event, input_number, output),
            int(MappingAction(action)),
        )

    async def read_mapping_matrix(
        self, event: MappingEvent | int
    ) -> dict[tuple[int, int], int]:
        """Read one mapping matrix for inputs 1..6/0 and outputs 1..6."""
        base_address = int(MappingEvent(event))
        values = await self.transport.read_holding_registers(
            base_address, 64, self.device_id
        )

        matrix: dict[tuple[int, int], int] = {}
        for input_number in INPUTS:
            row = _input_index(input_number)
            for output in OUTPUTS:
                matrix[(input_number, output)] = int(values[row * 8 + output - 1])
        return matrix

    async def _read_input_registers(self, base_address: int) -> dict[int, int]:
        values = await self.transport.read_holding_registers(
            base_address, 8, self.device_id
        )
        return {
            input_number: int(values[_input_index(input_number)])
            for input_number in INPUTS
        }


def relay_channel_address(base_address: int, channel: int) -> int:
    """Return an address offset for relay channel/output 1..6."""
    _validate_channel(channel)
    return base_address + channel - 1


def input_register_address(base_address: int, input_number: int) -> int:
    """Return an address offset for input 1..6 or input 0."""
    return base_address + _input_index(input_number)


def mapping_register_address(
    event: MappingEvent | int, input_number: int, output: int
) -> int:
    """Return a mapping matrix register address."""
    _validate_output(output)
    base_address = int(MappingEvent(event))
    return base_address + _input_index(input_number) * 8 + output - 1


def _extract_bits(response: Any, count: int) -> Sequence[bool]:
    bits = getattr(response, "bits", None)
    if bits is None or len(bits) < count:
        raise WBMR6CModbusResponseError("Modbus response did not contain enough bits")
    return [bool(value) for value in bits[:count]]


def _extract_registers(response: Any, count: int) -> Sequence[int]:
    registers = getattr(response, "registers", None)
    if registers is None or len(registers) < count:
        raise WBMR6CModbusResponseError(
            "Modbus response did not contain enough registers"
        )
    return [int(value) for value in registers[:count]]


def _channel_bool_map(values: Sequence[Any]) -> dict[int, bool]:
    if len(values) < CHANNEL_COUNT:
        raise WBMR6CModbusResponseError("Not enough channel values returned")
    return {channel: bool(values[channel - 1]) for channel in CHANNELS}


def _channel_int_map(values: Sequence[Any]) -> dict[int, int]:
    if len(values) < CHANNEL_COUNT:
        raise WBMR6CModbusResponseError("Not enough channel values returned")
    return {channel: int(values[channel - 1]) for channel in CHANNELS}


def _input_index(input_number: int) -> int:
    if input_number in range(1, CHANNEL_COUNT + 1):
        return input_number - 1
    if input_number == 0:
        return 7
    raise InvalidWBMR6CAddressError(
        f"Invalid WB-MR6C input {input_number}; expected 1..6 or 0"
    )


def _validate_channel(channel: int) -> None:
    if channel not in CHANNELS:
        raise InvalidWBMR6CAddressError(
            f"Invalid WB-MR6C channel {channel}; expected 1..6"
        )


def _validate_output(output: int) -> None:
    if output not in OUTPUTS:
        raise InvalidWBMR6CAddressError(
            f"Invalid WB-MR6C output {output}; expected 1..6"
        )


def _validate_register_value(value: int) -> None:
    _validate_value_range(value, 0, 0xFFFF, "register value")


def _validate_value_range(value: int, minimum: int, maximum: int, name: str) -> None:
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
