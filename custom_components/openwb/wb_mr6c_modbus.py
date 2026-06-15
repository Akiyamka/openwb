"""Modbus backend for supported Wiren Board Modbus modules."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Protocol, Sequence

DEFAULT_DEVICE_ID = 1
DEFAULT_MODBUS_TCP_PORT = 502
DEFAULT_SERIAL_BAUDRATE = 9600
DEFAULT_SERIAL_BYTESIZE = 8
DEFAULT_SERIAL_PARITY = "N"
DEFAULT_SERIAL_STOPBITS = 2

CHANNEL_COUNT = 6
RELAY_COUNT = CHANNEL_COUNT
INPUT_CHANNEL_COUNT = CHANNEL_COUNT
CHANNELS = tuple(range(1, CHANNEL_COUNT + 1))
INPUT_0 = 0
INPUTS = (1, 2, 3, 4, 5, 6, 0)
OUTPUTS = CHANNELS
MCM8_INPUT_COUNT = 8
MCM8_INPUTS = tuple(range(1, MCM8_INPUT_COUNT + 1))
MAPPING_MATRIX_ROW_SPACING = 8
REGISTER_U16_MAX = 0xFFFF
PRESS_COUNTER_MODULO = REGISTER_U16_MAX + 1
WBMR6C_MODEL = "WBMR6C"
MR6C_MODEL = "MR6C"
WBMR6CU_MODEL = "WBMR6CU"
MR6CU_MODEL = "MR6CU"
WBMCM8_MODEL = "WBMCM8"
MCM8_MODEL = "MCM8"
SUPPORTED_MODELS = frozenset(
    (
        WBMR6C_MODEL,
        MR6C_MODEL,
        WBMR6CU_MODEL,
        MR6CU_MODEL,
        WBMCM8_MODEL,
        MCM8_MODEL,
    )
)

COIL_RELAY_COMMAND_BASE = 0
COIL_RELAY_OFF_COMMAND_BASE = 100
COIL_RELAY_ON_COMMAND_BASE = 108
COIL_RELAY_TOGGLE_COMMAND_BASE = 116

DISCRETE_INPUT_STATE_BASE = 0
DISCRETE_INPUT_LEVEL_BASE = DISCRETE_INPUT_STATE_BASE
DISCRETE_RELAY_STATE_BASE = 96

REG_PRESS_COUNTER_ACTIVATION_BASE = 32
REG_PRESS_COUNTER_SHORT_BASE = 464
REG_PRESS_COUNTER_LONG_BASE = 480
REG_PRESS_COUNTER_DOUBLE_BASE = 496
REG_PRESS_COUNTER_SHORT_THEN_LONG_BASE = 512

REG_MAPPING_SHORT_PRESS_BASE = 544
REG_MAPPING_LONG_PRESS_BASE = 608
REG_MAPPING_DOUBLE_PRESS_BASE = 672
REG_MAPPING_SHORT_THEN_LONG_PRESS_BASE = 736
REG_MAPPING_FALLING_EDGE_BASE = 800
REG_MAPPING_RISING_EDGE_BASE = 864

REG_OUTPUT_POWER_ON_MODE = 6
REG_COMMUNICATION_TIMEOUT_S = 8
REG_INPUT_MODE_BASE = 9
REG_INPUT_DEBOUNCE_MS_BASE = 20
REG_MODEL_BASE = 200
REG_MODEL_LENGTH = 6
REG_MODEL_MAX_LENGTH = 20
REG_FIRMWARE_VERSION_BASE = 250
REG_FIRMWARE_VERSION_MAX_LENGTH = 16
REG_SAFE_STATE_BASE = 930
REG_SAFE_MODE_ACTION_BASE = 938
REG_SAFE_MODE_INPUT_CONTROL_BASE = 946
REG_LONG_PRESS_MS_BASE = 1100
REG_SECOND_PRESS_WAIT_MS_BASE = 1140

MIN_FIRMWARE_PRESS_COUNTERS = (1, 17, 0)
MIN_FIRMWARE_MCM8_PRESS_COUNTERS = (1, 3, 2)
MIN_FIRMWARE_RELAY_STATE_DISCRETE_INPUTS = (1, 24, 0)
MIN_FIRMWARE_RELAY_ONE_SHOT_COMMANDS = (1, 26, 0)


class WBMR6CModbusError(Exception):
    """Base error for WB-MR6C Modbus operations."""


class WBMR6CModbusConnectionError(WBMR6CModbusError):
    """Raised when the Modbus transport cannot communicate with the device."""


class WBMR6CModbusResponseError(WBMR6CModbusError):
    """Raised when the device returns an invalid or error response."""


class InvalidWBMR6CAddressError(ValueError):
    """Raised when a relay channel, input, output, or register is invalid."""


class InvalidWBMR6CValueError(ValueError):
    """Raised when a local WB-MR6C register value is invalid."""


class RelayOneShotCommand(IntEnum):
    """One-shot relay command coil groups."""

    OFF = COIL_RELAY_OFF_COMMAND_BASE
    ON = COIL_RELAY_ON_COMMAND_BASE
    TOGGLE = COIL_RELAY_TOGGLE_COMMAND_BASE


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


class PressCounterEvent(IntEnum):
    """Input press-counter register bases."""

    ACTIVATION = REG_PRESS_COUNTER_ACTIVATION_BASE
    SHORT = REG_PRESS_COUNTER_SHORT_BASE
    LONG = REG_PRESS_COUNTER_LONG_BASE
    DOUBLE = REG_PRESS_COUNTER_DOUBLE_BASE
    SHORT_THEN_LONG = REG_PRESS_COUNTER_SHORT_THEN_LONG_BASE


class MappingEvent(IntEnum):
    """Mapping matrix register bases."""

    SHORT_PRESS = REG_MAPPING_SHORT_PRESS_BASE
    LONG_PRESS = REG_MAPPING_LONG_PRESS_BASE
    DOUBLE_PRESS = REG_MAPPING_DOUBLE_PRESS_BASE
    SHORT_THEN_LONG_PRESS = REG_MAPPING_SHORT_THEN_LONG_PRESS_BASE
    FALLING_EDGE = REG_MAPPING_FALLING_EDGE_BASE
    RISING_EDGE = REG_MAPPING_RISING_EDGE_BASE


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

    async def read_input_registers(
        self, address: int, count: int, device_id: int
    ) -> Sequence[int]:
        """Read input register values."""

    async def write_register(self, address: int, value: int, device_id: int) -> None:
        """Write a single holding register."""


class _PymodbusTransportAdapter:
    """Shared async pymodbus transport behavior."""

    def __init__(self, client: Any, connection_name: str) -> None:
        """Initialize the transport adapter."""
        self._client = client
        self._connection_name = connection_name
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        """Open the Modbus connection if needed."""
        try:
            if self._client.connected:
                return

            connected = await self._client.connect()
        except Exception as err:  # noqa: BLE001
            raise WBMR6CModbusConnectionError(
                f"Unable to connect to Modbus transport {self._connection_name}"
            ) from err

        if not connected:
            raise WBMR6CModbusConnectionError(
                f"Unable to connect to Modbus transport {self._connection_name}"
            )

    async def close(self) -> None:
        """Close the Modbus connection."""
        try:
            self._client.close()
        except Exception as err:  # noqa: BLE001
            raise WBMR6CModbusConnectionError(
                f"Unable to close Modbus transport {self._connection_name}"
            ) from err

    async def read_coils(
        self, address: int, count: int, device_id: int
    ) -> Sequence[bool]:
        """Read coil values."""
        response = await self._execute(
            "read_coils", address, count=count, device_id=device_id
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
            "read_discrete_inputs", address, count=count, device_id=device_id
        )
        return _extract_bits(response, count)

    async def read_holding_registers(
        self, address: int, count: int, device_id: int
    ) -> Sequence[int]:
        """Read holding register values."""
        response = await self._execute(
            "read_holding_registers", address, count=count, device_id=device_id
        )
        return _extract_registers(response, count)

    async def read_input_registers(
        self, address: int, count: int, device_id: int
    ) -> Sequence[int]:
        """Read input register values."""
        response = await self._execute(
            "read_input_registers", address, count=count, device_id=device_id
        )
        return _extract_registers(response, count)

    async def write_register(self, address: int, value: int, device_id: int) -> None:
        """Write a single holding register."""
        _validate_register_value(value)
        await self._execute("write_register", address, value, device_id=device_id)

    async def _execute(
        self, method_name: str, *args: Any, device_id: int, **kwargs: Any
    ) -> Any:
        async with self._lock:
            await self.connect()

            try:
                method = getattr(self._client, method_name)
                response = await method(*args, **kwargs, device_id=device_id)
            except Exception as err:  # noqa: BLE001
                raise WBMR6CModbusConnectionError(
                    f"Modbus request failed: {method_name}"
                ) from err

            is_error = getattr(response, "isError", None)
            response_is_error = (
                is_error
                if isinstance(is_error, bool)
                else callable(is_error) and is_error()
            )
            if response is None or response_is_error:
                raise WBMR6CModbusResponseError(
                    f"Modbus request returned an error: {method_name}"
                )

            return response


class PymodbusSerialTransport(_PymodbusTransportAdapter):
    """Supported async Modbus RTU serial transport backed by pymodbus."""

    def __init__(
        self,
        port: str,
        *,
        baudrate: int = DEFAULT_SERIAL_BAUDRATE,
        bytesize: int = DEFAULT_SERIAL_BYTESIZE,
        parity: str = DEFAULT_SERIAL_PARITY,
        stopbits: int = DEFAULT_SERIAL_STOPBITS,
        timeout: float = 3.0,
        retries: int = 3,
        client_factory: Callable[..., Any] | None = None,
    ) -> None:
        """Initialize the serial RTU transport."""
        try:
            if client_factory is None:
                from pymodbus.client import AsyncModbusSerialClient

                client_factory = AsyncModbusSerialClient

            client = client_factory(
                port,
                baudrate=baudrate,
                bytesize=bytesize,
                parity=parity,
                stopbits=stopbits,
                timeout=timeout,
                retries=retries,
            )
        except Exception as err:  # noqa: BLE001
            raise WBMR6CModbusConnectionError(
                f"Unable to create serial Modbus client for {port}"
            ) from err

        super().__init__(client, f"serial port {port}")


class PymodbusTcpTransport(_PymodbusTransportAdapter):
    """Optional development Modbus TCP transport backed by pymodbus."""

    def __init__(
        self,
        host: str,
        port: int = DEFAULT_MODBUS_TCP_PORT,
        *,
        timeout: float = 3.0,
        retries: int = 3,
    ) -> None:
        """Initialize the transport."""
        try:
            from pymodbus.client import AsyncModbusTcpClient

            client = AsyncModbusTcpClient(
                host,
                port=port,
                timeout=timeout,
                retries=retries,
            )
        except Exception as err:  # noqa: BLE001
            raise WBMR6CModbusConnectionError(
                f"Unable to create TCP Modbus client for {host}:{port}"
            ) from err

        super().__init__(client, f"TCP {host}:{port}")


class FakeModbusTransport:
    """In-memory Modbus transport for tests and UI development."""

    def __init__(
        self,
        *,
        unavailable_devices: Iterable[int] | None = None,
        response_error_devices: Iterable[int] | None = None,
        short_response_devices: Iterable[int] | None = None,
    ) -> None:
        """Initialize an empty in-memory bus."""
        self.coils: dict[tuple[int, int], bool] = {}
        self.discrete_inputs: dict[tuple[int, int], bool] = {}
        self.holding_registers: dict[tuple[int, int], int] = {}
        self.input_registers: dict[tuple[int, int], int] = {}
        self.calls: list[tuple[str, int, int | bool, int]] = []
        self.writes: list[tuple[str, int, int | bool, int]] = []
        self.unavailable_devices = set(unavailable_devices or ())
        self.response_error_devices = set(response_error_devices or ())
        self.short_response_devices = set(short_response_devices or ())
        self.connected = False

    async def connect(self) -> None:
        """Mark the fake transport connected."""
        self.connected = True

    async def close(self) -> None:
        """Mark the fake transport closed."""
        self.connected = False

    def set_coil(
        self, address: int, value: bool, device_id: int = DEFAULT_DEVICE_ID
    ) -> None:
        """Set a fake coil value."""
        self.coils[(device_id, address)] = bool(value)

    def set_discrete_input(
        self, address: int, value: bool, device_id: int = DEFAULT_DEVICE_ID
    ) -> None:
        """Set a fake discrete input value."""
        self.discrete_inputs[(device_id, address)] = bool(value)

    def set_holding_register(
        self, address: int, value: int, device_id: int = DEFAULT_DEVICE_ID
    ) -> None:
        """Set a fake holding register value."""
        _validate_register_value(value)
        self.holding_registers[(device_id, address)] = value

    def set_input_register(
        self, address: int, value: int, device_id: int = DEFAULT_DEVICE_ID
    ) -> None:
        """Set a fake input register value."""
        _validate_register_value(value)
        self.input_registers[(device_id, address)] = value

    async def read_coils(
        self, address: int, count: int, device_id: int
    ) -> Sequence[bool]:
        """Read fake coil values."""
        self.calls.append(("read_coils", address, count, device_id))
        self._check_device(device_id)
        values = [
            self.coils.get((device_id, address + offset), False)
            for offset in range(count)
        ]
        return self._maybe_short_response(values, device_id)

    async def write_coil(self, address: int, value: bool, device_id: int) -> None:
        """Write a fake coil value."""
        self.calls.append(("write_coil", address, value, device_id))
        self._check_device(device_id)
        self.coils[(device_id, address)] = bool(value)
        self.writes.append(("write_coil", address, value, device_id))

    async def read_discrete_inputs(
        self, address: int, count: int, device_id: int
    ) -> Sequence[bool]:
        """Read fake discrete input values."""
        self.calls.append(("read_discrete_inputs", address, count, device_id))
        self._check_device(device_id)
        values = [
            self.discrete_inputs.get((device_id, address + offset), False)
            for offset in range(count)
        ]
        return self._maybe_short_response(values, device_id)

    async def read_holding_registers(
        self, address: int, count: int, device_id: int
    ) -> Sequence[int]:
        """Read fake holding register values."""
        self.calls.append(("read_holding_registers", address, count, device_id))
        self._check_device(device_id)
        values = [
            self.holding_registers.get((device_id, address + offset), 0)
            for offset in range(count)
        ]
        return self._maybe_short_response(values, device_id)

    async def read_input_registers(
        self, address: int, count: int, device_id: int
    ) -> Sequence[int]:
        """Read fake input register values."""
        self.calls.append(("read_input_registers", address, count, device_id))
        self._check_device(device_id)
        values = [
            self.input_registers.get((device_id, address + offset), 0)
            for offset in range(count)
        ]
        return self._maybe_short_response(values, device_id)

    async def write_register(self, address: int, value: int, device_id: int) -> None:
        """Write a fake holding register value."""
        _validate_register_value(value)
        self.calls.append(("write_register", address, value, device_id))
        self._check_device(device_id)
        self.holding_registers[(device_id, address)] = value
        self.writes.append(("write_register", address, value, device_id))

    def _check_device(self, device_id: int) -> None:
        if device_id in self.unavailable_devices:
            raise WBMR6CModbusConnectionError(
                f"Fake Modbus device {device_id} is unavailable"
            )
        if device_id in self.response_error_devices:
            raise WBMR6CModbusResponseError(
                f"Fake Modbus device {device_id} returned an error"
            )

    def _maybe_short_response(
        self, values: list[bool] | list[int], device_id: int
    ) -> Sequence[bool] | Sequence[int]:
        if device_id in self.short_response_devices:
            return values[:-1]
        return values


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
    long_press_ms: dict[int, int]
    second_press_wait_ms: dict[int, int]
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

    async def read_input_states(
        self, input_numbers: Iterable[int] = INPUTS
    ) -> dict[int, bool]:
        """Read input states for the requested input numbers."""
        input_numbers_tuple = tuple(input_numbers)
        if not input_numbers_tuple:
            return {}

        values = await self.transport.read_discrete_inputs(
            DISCRETE_INPUT_STATE_BASE, 8, self.device_id
        )
        if len(values) < 8:
            raise WBMR6CModbusResponseError("Not enough input values returned")
        return {
            input_number: bool(values[_input_state_index(input_number)])
            for input_number in input_numbers_tuple
        }

    async def read_press_counters(
        self,
        event: PressCounterEvent | int,
        input_numbers: Iterable[int] = INPUTS,
        *,
        input_registers: bool = False,
    ) -> dict[int, int]:
        """Read press counters for one counter group."""
        counter_event = _validate_press_counter_event(event)
        input_numbers_tuple = tuple(input_numbers)
        if not input_numbers_tuple:
            return {}

        if counter_event is PressCounterEvent.ACTIVATION:
            if input_registers:
                raise InvalidWBMR6CAddressError(
                    "Activation counters from input-register-only devices are not "
                    "exposed by read_press_counters"
                )
            values = await self.transport.read_holding_registers(
                int(counter_event), CHANNEL_COUNT, self.device_id
            )
            if len(values) < CHANNEL_COUNT:
                raise WBMR6CModbusResponseError(
                    "Not enough activation counter values returned"
                )
            return {channel: int(values[channel - 1]) for channel in CHANNELS}

        read_registers = (
            self.transport.read_input_registers
            if input_registers
            else self.transport.read_holding_registers
        )
        values = await read_registers(
            int(counter_event), MAPPING_MATRIX_ROW_SPACING, self.device_id
        )
        if len(values) < MAPPING_MATRIX_ROW_SPACING:
            raise WBMR6CModbusResponseError("Not enough press counter values returned")
        return {
            input_number: int(values[_input_state_index(input_number)])
            for input_number in input_numbers_tuple
        }

    async def read_model(self) -> str:
        """Read and decode the device model string."""
        return await self._read_ascii_registers(
            REG_MODEL_BASE,
            REG_MODEL_MAX_LENGTH,
            decode_model_registers,
            fallback_count=REG_MODEL_LENGTH,
        )

    async def read_firmware_version(self) -> str:
        """Read and decode the firmware version string."""
        return await self._read_ascii_registers(
            REG_FIRMWARE_VERSION_BASE,
            REG_FIRMWARE_VERSION_MAX_LENGTH,
            decode_firmware_registers,
        )

    async def _read_ascii_registers(
        self,
        address: int,
        count: int,
        decoder: Callable[[Sequence[int]], str],
        *,
        fallback_count: int | None = None,
    ) -> str:
        counts = (count,) if fallback_count is None else (count, fallback_count)
        last_error: WBMR6CModbusResponseError | None = None

        for read_registers in (
            self.transport.read_holding_registers,
            self.transport.read_input_registers,
        ):
            for current_count in counts:
                try:
                    return decoder(
                        await read_registers(address, current_count, self.device_id)
                    )
                except WBMR6CModbusResponseError as err:
                    last_error = err
                    continue

        if last_error is not None:
            raise last_error
        return ""

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
            relay_command_coil_address(channel),
            value,
            self.device_id,
        )

    async def turn_off(self, channel: int) -> None:
        """Send a one-shot relay off command."""
        await self.transport.write_coil(
            relay_off_command_coil_address(channel),
            True,
            self.device_id,
        )

    async def turn_on(self, channel: int) -> None:
        """Send a one-shot relay on command."""
        await self.transport.write_coil(
            relay_on_command_coil_address(channel),
            True,
            self.device_id,
        )

    async def toggle(self, channel: int) -> None:
        """Send a one-shot relay toggle command."""
        await self.transport.write_coil(
            relay_toggle_command_coil_address(channel),
            True,
            self.device_id,
        )

    async def read_basic_settings(self) -> WBMR6CBasicSettings:
        """Read core settings that are expected on the first UI settings screen."""
        return WBMR6CBasicSettings(
            output_power_on_mode=await self.read_output_power_on_mode(),
            communication_timeout_s=await self.read_communication_timeout_s(),
            input_modes=await self.read_input_modes(),
            debounce_ms=await self.read_debounce_ms(),
            long_press_ms=await self.read_long_press_ms(),
            second_press_wait_ms=await self.read_second_press_wait_ms(),
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

    async def read_output_power_on_mode(self) -> int:
        """Read the output behavior after device power-up."""
        return await self.read_register(REG_OUTPUT_POWER_ON_MODE)

    async def set_output_power_on_mode(
        self, mode: OutputPowerOnMode | int
    ) -> None:
        """Set the output behavior after device power-up."""
        await self.write_register(
            REG_OUTPUT_POWER_ON_MODE,
            int(_validate_output_power_on_mode(mode)),
        )

    async def read_communication_timeout_s(self) -> int:
        """Read the communication-loss timeout in seconds."""
        return await self.read_register(REG_COMMUNICATION_TIMEOUT_S)

    async def set_communication_timeout_s(self, value: int) -> None:
        """Set the communication-loss timeout in seconds."""
        _validate_value_range(value, 1, 65534, "communication_timeout_s")
        await self.write_register(REG_COMMUNICATION_TIMEOUT_S, value)

    async def read_input_modes(self) -> dict[int, int]:
        """Read input modes for inputs 1..6 and 0."""
        return await self._read_input_registers(REG_INPUT_MODE_BASE)

    async def set_input_mode(self, input_number: int, mode: InputMode | int) -> None:
        """Set mode for one input."""
        validated_mode = _validate_input_mode_for_input(input_number, mode)
        await self.write_register(
            input_register_address(REG_INPUT_MODE_BASE, input_number),
            int(validated_mode),
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
        value = (
            int(bool(state))
            if isinstance(state, bool)
            else int(_validate_safe_state(state))
        )
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
            int(_validate_safe_mode_action(action)),
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
            int(_validate_safe_mode_input_control(control)),
        )

    async def read_mapping_action(
        self, event: MappingEvent | int, input_number: int, output: int
    ) -> int:
        """Read one mapping matrix cell."""
        address = mapping_register_address(event, input_number, output)
        values = await self.transport.read_holding_registers(
            address, 1, self.device_id
        )
        if not values:
            raise WBMR6CModbusResponseError(
                f"No value returned for register {address}"
            )
        return _mapping_action_response_value(values[0])

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
            mapping_action_value(action),
        )

    async def read_mapping_matrix(
        self, event: MappingEvent | int
    ) -> dict[tuple[int, int], int]:
        """Read one mapping matrix for inputs 1..6/0 and outputs 1..6."""
        base_address = int(_validate_mapping_event(event))
        values = await self.transport.read_holding_registers(
            base_address,
            MAPPING_MATRIX_ROW_SPACING * MAPPING_MATRIX_ROW_SPACING,
            self.device_id,
        )
        if len(values) < MAPPING_MATRIX_ROW_SPACING * MAPPING_MATRIX_ROW_SPACING:
            raise WBMR6CModbusResponseError(
                "Not enough mapping matrix values returned"
            )

        matrix: dict[tuple[int, int], int] = {}
        for input_number in INPUTS:
            row = _input_index(input_number)
            for output in OUTPUTS:
                matrix[(input_number, output)] = _mapping_action_response_value(
                    values[row * MAPPING_MATRIX_ROW_SPACING + output - 1]
                )
        return matrix

    async def write_mapping_matrix(
        self,
        event: MappingEvent | int,
        desired_matrix: Mapping[tuple[int, int], MappingAction | int],
    ) -> None:
        """Apply a complete mapping matrix, writing only changed cells."""
        mapping_event = _validate_mapping_event(event)
        desired = _validate_mapping_matrix(desired_matrix)
        current = await self.read_mapping_matrix(mapping_event)

        for input_number in INPUTS:
            for output in OUTPUTS:
                key = (input_number, output)
                action = desired[key]
                if current[key] == action:
                    continue
                await self.write_register(
                    mapping_register_address(mapping_event, input_number, output),
                    action,
                )

    async def _read_input_registers(self, base_address: int) -> dict[int, int]:
        values = await self.transport.read_holding_registers(
            base_address, 8, self.device_id
        )
        if len(values) < 8:
            raise WBMR6CModbusResponseError("Not enough input register values returned")
        return {
            input_number: int(values[_input_index(input_number)])
            for input_number in INPUTS
        }


def relay_channel_address(base_address: int, channel: int) -> int:
    """Return an address offset for relay channel/output 1..6."""
    _validate_channel(channel)
    return base_address + channel - 1


def relay_command_coil_address(output: int) -> int:
    """Return the persistent relay command coil address for output 1..6."""
    return relay_channel_address(COIL_RELAY_COMMAND_BASE, output)


def relay_off_command_coil_address(output: int) -> int:
    """Return the one-shot OFF command coil address for output 1..6."""
    return relay_one_shot_command_address(RelayOneShotCommand.OFF, output)


def relay_on_command_coil_address(output: int) -> int:
    """Return the one-shot ON command coil address for output 1..6."""
    return relay_one_shot_command_address(RelayOneShotCommand.ON, output)


def relay_toggle_command_coil_address(output: int) -> int:
    """Return the one-shot TOGGLE command coil address for output 1..6."""
    return relay_one_shot_command_address(RelayOneShotCommand.TOGGLE, output)


def relay_one_shot_command_address(
    command: RelayOneShotCommand | int, output: int
) -> int:
    """Return a one-shot relay command coil address for output 1..6."""
    return relay_channel_address(
        int(_validate_relay_one_shot_command(command)), output
    )


def relay_state_discrete_input_address(output: int) -> int:
    """Return the relay-state discrete input address for output 1..6."""
    return relay_channel_address(DISCRETE_RELAY_STATE_BASE, output)


def input_level_discrete_input_address(input_number: int) -> int:
    """Return the input-level discrete input address for input 1..8 or 0."""
    return DISCRETE_INPUT_LEVEL_BASE + _input_state_index(input_number)


def input_register_address(base_address: int, input_number: int) -> int:
    """Return an address offset for input 1..6 or input 0."""
    return base_address + _input_index(input_number)


def press_counter_register_address(
    event: PressCounterEvent | int, input_number: int
) -> int:
    """Return a press-counter holding register address."""
    counter_event = _validate_press_counter_event(event)
    if counter_event is PressCounterEvent.ACTIVATION and input_number == INPUT_0:
        raise InvalidWBMR6CAddressError(
            "Activation press counters exist only for inputs 1..6"
        )
    return input_register_address(int(counter_event), input_number)


def activation_counter_register_address(input_number: int) -> int:
    """Return the activation counter address for input 1..6."""
    return press_counter_register_address(PressCounterEvent.ACTIVATION, input_number)


def short_press_counter_register_address(input_number: int) -> int:
    """Return the short-press counter address for input 1..6 or 0."""
    return press_counter_register_address(PressCounterEvent.SHORT, input_number)


def long_press_counter_register_address(input_number: int) -> int:
    """Return the long-press counter address for input 1..6 or 0."""
    return press_counter_register_address(PressCounterEvent.LONG, input_number)


def double_press_counter_register_address(input_number: int) -> int:
    """Return the double-press counter address for input 1..6 or 0."""
    return press_counter_register_address(PressCounterEvent.DOUBLE, input_number)


def short_then_long_press_counter_register_address(input_number: int) -> int:
    """Return the short-then-long counter address for input 1..6 or 0."""
    return press_counter_register_address(
        PressCounterEvent.SHORT_THEN_LONG, input_number
    )


def mapping_register_address(
    event: MappingEvent | int, input_number: int, output: int
) -> int:
    """Return a mapping matrix register address."""
    _validate_output(output)
    base_address = int(_validate_mapping_event(event))
    return (
        base_address
        + _input_index(input_number) * MAPPING_MATRIX_ROW_SPACING
        + output
        - 1
    )


def mapping_action_value(action: MappingAction | int) -> int:
    """Return a validated mapping action register value."""
    return int(_validate_mapping_action(action))


def _validate_mapping_matrix(
    matrix: Mapping[tuple[int, int], MappingAction | int],
) -> dict[tuple[int, int], int]:
    if not isinstance(matrix, Mapping):
        raise InvalidWBMR6CValueError("Mapping matrix must be a mapping")

    expected_keys = {
        (input_number, output) for input_number in INPUTS for output in OUTPUTS
    }
    validated: dict[tuple[int, int], int] = {}
    for key, action in matrix.items():
        if not isinstance(key, tuple) or len(key) != 2:
            raise InvalidWBMR6CAddressError(
                "Mapping matrix keys must be (input_number, output) tuples"
            )

        input_number, output = key
        _input_index(input_number)
        _validate_output(output)
        validated[(input_number, output)] = mapping_action_value(action)

    if set(validated) != expected_keys:
        missing = expected_keys - set(validated)
        extra = set(validated) - expected_keys
        details = []
        if missing:
            details.append(f"missing cells: {sorted(missing)!r}")
        if extra:
            details.append(f"unexpected cells: {sorted(extra)!r}")
        raise InvalidWBMR6CValueError(
            "Mapping matrix must contain every input/output cell"
            + (f" ({'; '.join(details)})" if details else "")
        )

    return validated


def _mapping_action_response_value(value: Any) -> int:
    try:
        return mapping_action_value(value)
    except InvalidWBMR6CValueError as err:
        raise WBMR6CModbusResponseError(
            f"Invalid mapping action returned by device: {value!r}"
        ) from err


def decode_model_registers(registers: Sequence[int]) -> str:
    """Decode the model string from holding register 200."""
    if len(registers) < REG_MODEL_LENGTH:
        raise WBMR6CModbusResponseError("Not enough model registers returned")
    return _decode_ascii_registers(registers[:REG_MODEL_MAX_LENGTH])


def decode_firmware_registers(registers: Sequence[int]) -> str:
    """Decode the null-terminated firmware string from holding register 250."""
    if len(registers) < REG_FIRMWARE_VERSION_MAX_LENGTH:
        raise WBMR6CModbusResponseError("Not enough firmware registers returned")
    return _decode_ascii_registers(registers[:REG_FIRMWARE_VERSION_MAX_LENGTH])


def parse_firmware_version(version: str) -> tuple[int, int, int]:
    """Parse a firmware version string into a comparable three-part tuple."""
    parts: list[int] = []
    for raw_part in version.strip().split("."):
        digits = []
        for char in raw_part:
            if not char.isdigit():
                break
            digits.append(char)
        if not digits:
            break
        parts.append(int("".join(digits)))
        if len(parts) == 3:
            break

    if not parts:
        raise InvalidWBMR6CValueError(f"Invalid firmware version: {version!r}")

    while len(parts) < 3:
        parts.append(0)
    return parts[0], parts[1], parts[2]


def firmware_supports_press_counters(
    version: str | Sequence[int],
) -> bool:
    """Return whether firmware supports per-press input counters."""
    return _firmware_version_tuple(version) >= MIN_FIRMWARE_PRESS_COUNTERS


def firmware_supports_mcm8_press_counters(
    version: str | Sequence[int],
) -> bool:
    """Return whether WB-MCM8 firmware supports per-press input counters."""
    return _firmware_version_tuple(version) >= MIN_FIRMWARE_MCM8_PRESS_COUNTERS


def firmware_supports_relay_state_discrete_inputs(
    version: str | Sequence[int],
) -> bool:
    """Return whether firmware supports relay-state discrete inputs 96..101."""
    return _firmware_version_tuple(version) >= MIN_FIRMWARE_RELAY_STATE_DISCRETE_INPUTS


def firmware_supports_relay_one_shot_commands(
    version: str | Sequence[int],
) -> bool:
    """Return whether firmware supports one-shot relay commands 100/108/116."""
    return _firmware_version_tuple(version) >= MIN_FIRMWARE_RELAY_ONE_SHOT_COMMANDS


def press_counter_delta(previous: int | None, current: int) -> int:
    """Return a u16 press-counter delta, treating None as initial baseline."""
    _validate_register_value(current)
    if previous is None:
        return 0
    _validate_register_value(previous)
    return (current - previous) % PRESS_COUNTER_MODULO


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


def _decode_ascii_registers(registers: Sequence[int]) -> str:
    chars: list[str] = []
    for register in registers:
        if not _is_int_value(register) or not 0 <= register <= REGISTER_U16_MAX:
            raise WBMR6CModbusResponseError(
                f"Invalid ASCII register value: {register!r}"
            )

        high_byte = register >> 8
        low_byte = register & 0xFF
        if high_byte != 0:
            raise WBMR6CModbusResponseError(
                f"ASCII register high byte must be 0: {register!r}"
            )
        if low_byte == 0:
            break
        if low_byte > 0x7F:
            raise WBMR6CModbusResponseError(
                f"Register value is not ASCII: {register!r}"
            )
        chars.append(chr(low_byte))
    return "".join(chars)


def _firmware_version_tuple(version: str | Sequence[int]) -> tuple[int, int, int]:
    if isinstance(version, str):
        return parse_firmware_version(version)

    parts = list(version[:3])
    if not parts:
        raise InvalidWBMR6CValueError("Firmware version tuple cannot be empty")

    for part in parts:
        if not _is_int_value(part) or part < 0:
            raise InvalidWBMR6CValueError(
                f"Invalid firmware version component: {part!r}"
            )

    while len(parts) < 3:
        parts.append(0)
    return int(parts[0]), int(parts[1]), int(parts[2])


def _input_index(input_number: int) -> int:
    if _is_int_value(input_number) and input_number in range(1, CHANNEL_COUNT + 1):
        return input_number - 1
    if _is_int_value(input_number) and input_number == INPUT_0:
        return 7
    raise InvalidWBMR6CAddressError(
        f"Invalid WB-MR6C input {input_number}; expected 1..6 or 0"
    )


def _input_state_index(input_number: int) -> int:
    if _is_int_value(input_number) and input_number in range(1, MCM8_INPUT_COUNT + 1):
        return input_number - 1
    if _is_int_value(input_number) and input_number == INPUT_0:
        return 7
    raise InvalidWBMR6CAddressError(
        f"Invalid WB input {input_number}; expected 1..8 or 0"
    )


def _validate_channel(channel: int) -> None:
    if not _is_int_value(channel) or channel not in CHANNELS:
        raise InvalidWBMR6CAddressError(
            f"Invalid WB-MR6C channel {channel}; expected 1..6"
        )


def _validate_output(output: int) -> None:
    if not _is_int_value(output) or output not in OUTPUTS:
        raise InvalidWBMR6CAddressError(
            f"Invalid WB-MR6C output {output}; expected 1..6"
        )


def _validate_relay_one_shot_command(
    command: RelayOneShotCommand | int,
) -> RelayOneShotCommand:
    if not _is_int_value(command):
        raise InvalidWBMR6CAddressError(
            f"Invalid WB-MR6C one-shot relay command {command!r}"
        )
    try:
        return RelayOneShotCommand(command)
    except ValueError as err:
        raise InvalidWBMR6CAddressError(
            f"Invalid WB-MR6C one-shot relay command {command!r}"
        ) from err


def _validate_press_counter_event(
    event: PressCounterEvent | int,
) -> PressCounterEvent:
    if not _is_int_value(event):
        raise InvalidWBMR6CAddressError(
            f"Invalid WB-MR6C press-counter event {event!r}"
        )
    try:
        return PressCounterEvent(event)
    except ValueError as err:
        raise InvalidWBMR6CAddressError(
            f"Invalid WB-MR6C press-counter event {event!r}"
        ) from err


def _validate_mapping_event(event: MappingEvent | int) -> MappingEvent:
    if not _is_int_value(event):
        raise InvalidWBMR6CAddressError(
            f"Invalid WB-MR6C mapping event {event!r}"
        )
    try:
        return MappingEvent(event)
    except ValueError as err:
        raise InvalidWBMR6CAddressError(
            f"Invalid WB-MR6C mapping event {event!r}"
        ) from err


def _validate_mapping_action(action: MappingAction | int) -> MappingAction:
    if not _is_int_value(action):
        raise InvalidWBMR6CValueError(
            f"Invalid WB-MR6C mapping action {action!r}"
        )
    try:
        return MappingAction(action)
    except ValueError as err:
        raise InvalidWBMR6CValueError(
            f"Invalid WB-MR6C mapping action {action!r}"
        ) from err


def _validate_input_mode(mode: InputMode | int) -> InputMode:
    if not _is_int_value(mode):
        raise InvalidWBMR6CValueError(f"Invalid WB-MR6C input mode {mode!r}")
    try:
        return InputMode(mode)
    except ValueError as err:
        raise InvalidWBMR6CValueError(
            f"Invalid WB-MR6C input mode {mode!r}"
        ) from err


def _validate_input_mode_for_input(
    input_number: int,
    mode: InputMode | int,
) -> InputMode:
    _input_index(input_number)
    input_mode = _validate_input_mode(mode)
    if input_mode is InputMode.DISABLED:
        raise InvalidWBMR6CValueError(
            f"Invalid WB-MR6C input mode {mode!r}; value 5 is unused"
        )
    if input_number == INPUT_0 and input_mode in {
        InputMode.MOMENTARY,
        InputMode.LATCHING,
    }:
        raise InvalidWBMR6CValueError(
            f"Invalid WB-MR6C input 0 mode {mode!r}; expected 2, 3, 4, or 6"
        )
    return input_mode


def _validate_output_power_on_mode(
    mode: OutputPowerOnMode | int,
) -> OutputPowerOnMode:
    if not _is_int_value(mode):
        raise InvalidWBMR6CValueError(
            f"Invalid WB-MR6C output power-on mode {mode!r}"
        )
    try:
        return OutputPowerOnMode(mode)
    except ValueError as err:
        raise InvalidWBMR6CValueError(
            f"Invalid WB-MR6C output power-on mode {mode!r}"
        ) from err


def _validate_safe_state(state: SafeState | int) -> SafeState:
    if not _is_int_value(state):
        raise InvalidWBMR6CValueError(f"Invalid WB-MR6C safe state {state!r}")
    try:
        return SafeState(state)
    except ValueError as err:
        raise InvalidWBMR6CValueError(
            f"Invalid WB-MR6C safe state {state!r}"
        ) from err


def _validate_safe_mode_action(action: SafeModeAction | int) -> SafeModeAction:
    if not _is_int_value(action):
        raise InvalidWBMR6CValueError(
            f"Invalid WB-MR6C safe-mode action {action!r}"
        )
    try:
        return SafeModeAction(action)
    except ValueError as err:
        raise InvalidWBMR6CValueError(
            f"Invalid WB-MR6C safe-mode action {action!r}"
        ) from err


def _validate_safe_mode_input_control(
    control: SafeModeInputControl | int,
) -> SafeModeInputControl:
    if not _is_int_value(control):
        raise InvalidWBMR6CValueError(
            f"Invalid WB-MR6C safe-mode input control {control!r}"
        )
    try:
        return SafeModeInputControl(control)
    except ValueError as err:
        raise InvalidWBMR6CValueError(
            f"Invalid WB-MR6C safe-mode input control {control!r}"
        ) from err


def _validate_register_value(value: int) -> None:
    _validate_value_range(value, 0, REGISTER_U16_MAX, "register value")


def _validate_value_range(value: int, minimum: int, maximum: int, name: str) -> None:
    if not _is_int_value(value) or not minimum <= value <= maximum:
        raise InvalidWBMR6CValueError(
            f"{name} must be between {minimum} and {maximum}"
        )


def _is_int_value(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)
