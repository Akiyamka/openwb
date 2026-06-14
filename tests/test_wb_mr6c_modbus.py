from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
import unittest
from pathlib import Path

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "openwb"
    / "wb_mr6c_modbus.py"
)
SPEC = importlib.util.spec_from_file_location("wb_mr6c_modbus", MODULE_PATH)
assert SPEC is not None
assert SPEC.loader is not None
wb_mr6c_modbus = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = wb_mr6c_modbus
SPEC.loader.exec_module(wb_mr6c_modbus)


class FakeTransport:
    def __init__(self) -> None:
        self.coils: dict[int, bool] = {}
        self.discrete_inputs: dict[int, bool] = {}
        self.holding_registers: dict[int, int] = {}
        self.calls: list[tuple[str, int, int | bool, int]] = []

    async def read_coils(
        self, address: int, count: int, device_id: int
    ) -> list[bool]:
        self.calls.append(("read_coils", address, count, device_id))
        return [self.coils.get(address + offset, False) for offset in range(count)]

    async def write_coil(self, address: int, value: bool, device_id: int) -> None:
        self.coils[address] = value
        self.calls.append(("write_coil", address, value, device_id))

    async def read_discrete_inputs(
        self, address: int, count: int, device_id: int
    ) -> list[bool]:
        self.calls.append(("read_discrete_inputs", address, count, device_id))
        return [
            self.discrete_inputs.get(address + offset, False)
            for offset in range(count)
        ]

    async def read_holding_registers(
        self, address: int, count: int, device_id: int
    ) -> list[int]:
        self.calls.append(("read_holding_registers", address, count, device_id))
        return [
            self.holding_registers.get(address + offset, 0)
            for offset in range(count)
        ]

    async def write_register(self, address: int, value: int, device_id: int) -> None:
        self.holding_registers[address] = value
        self.calls.append(("write_register", address, value, device_id))


class ShortHoldingRegisterTransport(FakeTransport):
    def __init__(self, values: list[int]) -> None:
        super().__init__()
        self.values = values

    async def read_holding_registers(
        self, address: int, count: int, device_id: int
    ) -> list[int]:
        return self.values


class StubPymodbusResponse:
    def __init__(
        self,
        *,
        bits: list[bool] | None = None,
        registers: list[int] | None = None,
        error: bool = False,
    ) -> None:
        self.bits = bits or []
        self.registers = registers or []
        self.error = error

    def isError(self) -> bool:  # noqa: N802
        return self.error


class StubPymodbusClient:
    def __init__(self, port: str = "/dev/null", **kwargs: object) -> None:
        self.port = port
        self.kwargs = kwargs
        self.connected = False
        self.connect_result = True
        self.connect_error: Exception | None = None
        self.connect_calls = 0
        self.close_calls = 0
        self.calls: list[tuple[object, ...]] = []
        self.responses: list[StubPymodbusResponse] = []
        self.exceptions: dict[str, Exception] = {}
        self.delay = 0.0
        self.active_requests = 0
        self.max_active_requests = 0

    def queue_response(self, response: StubPymodbusResponse) -> None:
        self.responses.append(response)

    async def connect(self) -> bool:
        self.connect_calls += 1
        if self.connect_error is not None:
            raise self.connect_error
        self.connected = self.connect_result
        return self.connect_result

    def close(self) -> None:
        self.close_calls += 1
        self.connected = False

    async def read_coils(
        self, address: int, *, count: int = 1, device_id: int = 1
    ) -> StubPymodbusResponse:
        return await self._respond("read_coils", address, count, device_id)

    async def write_coil(
        self, address: int, value: bool, *, device_id: int = 1
    ) -> StubPymodbusResponse:
        return await self._respond("write_coil", address, value, device_id)

    async def read_discrete_inputs(
        self, address: int, *, count: int = 1, device_id: int = 1
    ) -> StubPymodbusResponse:
        return await self._respond(
            "read_discrete_inputs", address, count, device_id
        )

    async def read_holding_registers(
        self, address: int, *, count: int = 1, device_id: int = 1
    ) -> StubPymodbusResponse:
        return await self._respond(
            "read_holding_registers", address, count, device_id
        )

    async def write_register(
        self, address: int, value: int, *, device_id: int = 1
    ) -> StubPymodbusResponse:
        return await self._respond("write_register", address, value, device_id)

    async def _respond(self, method: str, *args: object) -> StubPymodbusResponse:
        self.calls.append((method, *args))
        self.active_requests += 1
        self.max_active_requests = max(
            self.max_active_requests, self.active_requests
        )
        try:
            if self.delay:
                await asyncio.sleep(self.delay)
            if method in self.exceptions:
                raise self.exceptions[method]
            if self.responses:
                return self.responses.pop(0)
            if method in {"read_coils", "read_discrete_inputs"}:
                return StubPymodbusResponse(bits=[False] * int(args[1]))
            if method == "read_holding_registers":
                return StubPymodbusResponse(registers=[0] * int(args[1]))
            return StubPymodbusResponse()
        finally:
            self.active_requests -= 1


def _serial_transport_for_client(
    client: StubPymodbusClient,
) -> wb_mr6c_modbus.PymodbusSerialTransport:
    return wb_mr6c_modbus.PymodbusSerialTransport(
        "/dev/ttyUSB0", client_factory=lambda *args, **kwargs: client
    )


def _complete_mapping_matrix(action: int = 0) -> dict[tuple[int, int], int]:
    return {
        (input_number, output): action
        for input_number in wb_mr6c_modbus.INPUTS
        for output in wb_mr6c_modbus.OUTPUTS
    }


class ManifestTest(unittest.TestCase):
    def test_manifest_version(self) -> None:
        manifest_path = MODULE_PATH.parent / "manifest.json"
        manifest = json.loads(manifest_path.read_text())

        self.assertEqual(manifest["version"], "0.9.2")


class AddressingTest(unittest.TestCase):
    def test_counts(self) -> None:
        self.assertEqual(wb_mr6c_modbus.RELAY_COUNT, 6)
        self.assertEqual(wb_mr6c_modbus.INPUT_CHANNEL_COUNT, 6)
        self.assertEqual(wb_mr6c_modbus.INPUTS, (1, 2, 3, 4, 5, 6, 0))

    def test_relay_channel_address(self) -> None:
        self.assertEqual(
            wb_mr6c_modbus.relay_channel_address(
                wb_mr6c_modbus.COIL_RELAY_ON_COMMAND_BASE, 3
            ),
            110,
        )

    def test_relay_and_input_discrete_addresses(self) -> None:
        self.assertEqual(wb_mr6c_modbus.relay_command_coil_address(1), 0)
        self.assertEqual(wb_mr6c_modbus.relay_command_coil_address(6), 5)
        self.assertEqual(wb_mr6c_modbus.relay_off_command_coil_address(1), 100)
        self.assertEqual(wb_mr6c_modbus.relay_on_command_coil_address(6), 113)
        self.assertEqual(wb_mr6c_modbus.relay_toggle_command_coil_address(5), 120)
        self.assertEqual(wb_mr6c_modbus.relay_state_discrete_input_address(1), 96)
        self.assertEqual(wb_mr6c_modbus.relay_state_discrete_input_address(6), 101)
        self.assertEqual(wb_mr6c_modbus.input_level_discrete_input_address(1), 0)
        self.assertEqual(wb_mr6c_modbus.input_level_discrete_input_address(6), 5)
        self.assertEqual(wb_mr6c_modbus.input_level_discrete_input_address(0), 7)

    def test_input_zero_address(self) -> None:
        self.assertEqual(
            wb_mr6c_modbus.input_register_address(
                wb_mr6c_modbus.REG_INPUT_MODE_BASE, 0
            ),
            16,
        )

    def test_press_counter_addresses(self) -> None:
        self.assertEqual(wb_mr6c_modbus.activation_counter_register_address(1), 32)
        self.assertEqual(wb_mr6c_modbus.activation_counter_register_address(6), 37)
        self.assertEqual(wb_mr6c_modbus.short_press_counter_register_address(1), 464)
        self.assertEqual(wb_mr6c_modbus.short_press_counter_register_address(6), 469)
        self.assertEqual(wb_mr6c_modbus.short_press_counter_register_address(0), 471)
        self.assertEqual(wb_mr6c_modbus.long_press_counter_register_address(0), 487)
        self.assertEqual(wb_mr6c_modbus.double_press_counter_register_address(0), 503)
        self.assertEqual(
            wb_mr6c_modbus.short_then_long_press_counter_register_address(0), 519
        )

        with self.assertRaises(wb_mr6c_modbus.InvalidWBMR6CAddressError):
            wb_mr6c_modbus.activation_counter_register_address(0)

    def test_mapping_matrix_address(self) -> None:
        for event in wb_mr6c_modbus.MappingEvent:
            self.assertEqual(
                wb_mr6c_modbus.mapping_register_address(event, 1, 1),
                int(event),
            )
            self.assertEqual(
                wb_mr6c_modbus.mapping_register_address(event, 6, 6),
                int(event) + 5 * wb_mr6c_modbus.MAPPING_MATRIX_ROW_SPACING + 5,
            )
            self.assertEqual(
                wb_mr6c_modbus.mapping_register_address(event, 0, 6),
                int(event) + 7 * wb_mr6c_modbus.MAPPING_MATRIX_ROW_SPACING + 5,
            )

        self.assertEqual(
            wb_mr6c_modbus.mapping_register_address(
                wb_mr6c_modbus.MappingEvent.SHORT_PRESS, 1, 1
            ),
            544,
        )
        self.assertEqual(
            wb_mr6c_modbus.mapping_register_address(
                wb_mr6c_modbus.MappingEvent.SHORT_PRESS, 0, 6
            ),
            605,
        )
        self.assertEqual(
            wb_mr6c_modbus.mapping_register_address(
                wb_mr6c_modbus.MappingEvent.LONG_PRESS, 2, 3
            ),
            618,
        )
        self.assertEqual(
            wb_mr6c_modbus.mapping_register_address(
                wb_mr6c_modbus.MappingEvent.RISING_EDGE, 0, 1
            ),
            920,
        )

    def test_invalid_channel(self) -> None:
        with self.assertRaises(wb_mr6c_modbus.InvalidWBMR6CAddressError):
            wb_mr6c_modbus.relay_channel_address(0, 7)

        with self.assertRaises(wb_mr6c_modbus.InvalidWBMR6CAddressError):
            wb_mr6c_modbus.input_register_address(0, 7)

        with self.assertRaises(wb_mr6c_modbus.InvalidWBMR6CAddressError):
            wb_mr6c_modbus.relay_state_discrete_input_address(0)

    def test_invalid_mapping_values(self) -> None:
        with self.assertRaises(wb_mr6c_modbus.InvalidWBMR6CAddressError):
            wb_mr6c_modbus.mapping_register_address(999, 1, 1)

        with self.assertRaises(wb_mr6c_modbus.InvalidWBMR6CAddressError):
            wb_mr6c_modbus.mapping_register_address(
                wb_mr6c_modbus.MappingEvent.SHORT_PRESS, 7, 1
            )

        with self.assertRaises(wb_mr6c_modbus.InvalidWBMR6CAddressError):
            wb_mr6c_modbus.mapping_register_address(
                wb_mr6c_modbus.MappingEvent.SHORT_PRESS, 1, 7
            )

        with self.assertRaises(wb_mr6c_modbus.InvalidWBMR6CValueError):
            wb_mr6c_modbus.mapping_action_value(4)


class IdentificationTest(unittest.TestCase):
    def test_decode_model_and_firmware(self) -> None:
        model_registers = [ord(char) for char in "WBMR6C"]
        extended_model_registers = [ord(char) for char in "WBMR6CU"] + [0]
        compact_model_registers = [ord(char) for char in "MR6CU"] + [0]
        firmware_registers = [ord(char) for char in "1.24.0"] + [0] * 10

        self.assertEqual(
            wb_mr6c_modbus.decode_model_registers(model_registers), "WBMR6C"
        )
        self.assertEqual(
            wb_mr6c_modbus.decode_model_registers(extended_model_registers),
            "WBMR6CU",
        )
        self.assertEqual(
            wb_mr6c_modbus.decode_model_registers(compact_model_registers),
            "MR6CU",
        )
        self.assertEqual(
            wb_mr6c_modbus.SUPPORTED_MODELS,
            frozenset(("WBMR6C", "MR6C", "WBMR6CU", "MR6CU")),
        )
        self.assertEqual(
            wb_mr6c_modbus.decode_firmware_registers(firmware_registers), "1.24.0"
        )

        with self.assertRaises(wb_mr6c_modbus.WBMR6CModbusResponseError):
            wb_mr6c_modbus.decode_firmware_registers([ord("1"), 0])

    def test_firmware_version_parsing_and_gates(self) -> None:
        self.assertEqual(
            wb_mr6c_modbus.parse_firmware_version("1.17.0"), (1, 17, 0)
        )
        self.assertEqual(
            wb_mr6c_modbus.parse_firmware_version("1.24"), (1, 24, 0)
        )
        self.assertFalse(wb_mr6c_modbus.firmware_supports_press_counters("1.16.9"))
        self.assertTrue(wb_mr6c_modbus.firmware_supports_press_counters("1.17.0"))
        self.assertFalse(
            wb_mr6c_modbus.firmware_supports_relay_state_discrete_inputs("1.23.9")
        )
        self.assertTrue(
            wb_mr6c_modbus.firmware_supports_relay_state_discrete_inputs((1, 24, 0))
        )

    def test_press_counter_delta(self) -> None:
        self.assertEqual(wb_mr6c_modbus.press_counter_delta(None, 42), 0)
        self.assertEqual(wb_mr6c_modbus.press_counter_delta(5, 8), 3)
        self.assertEqual(wb_mr6c_modbus.press_counter_delta(0xFFFF, 0), 1)
        self.assertEqual(wb_mr6c_modbus.press_counter_delta(10, 10), 0)

        with self.assertRaises(wb_mr6c_modbus.InvalidWBMR6CValueError):
            wb_mr6c_modbus.press_counter_delta(0, 0x10000)


class PymodbusSerialTransportTest(unittest.IsolatedAsyncioTestCase):
    async def test_serial_transport_passes_settings_and_lifecycle(self) -> None:
        clients: list[StubPymodbusClient] = []

        def factory(port: str, **kwargs: object) -> StubPymodbusClient:
            client = StubPymodbusClient(port, **kwargs)
            clients.append(client)
            return client

        transport = wb_mr6c_modbus.PymodbusSerialTransport(
            "/dev/ttyUSB0",
            baudrate=115200,
            parity="E",
            stopbits=1,
            timeout=1.5,
            retries=1,
            client_factory=factory,
        )

        await transport.connect()
        await transport.close()

        self.assertEqual(clients[0].port, "/dev/ttyUSB0")
        self.assertEqual(clients[0].kwargs["baudrate"], 115200)
        self.assertEqual(clients[0].kwargs["bytesize"], 8)
        self.assertEqual(clients[0].kwargs["parity"], "E")
        self.assertEqual(clients[0].kwargs["stopbits"], 1)
        self.assertEqual(clients[0].kwargs["timeout"], 1.5)
        self.assertEqual(clients[0].kwargs["retries"], 1)
        self.assertEqual(clients[0].connect_calls, 1)
        self.assertEqual(clients[0].close_calls, 1)
        self.assertFalse(clients[0].connected)

    async def test_serial_transport_reads_and_writes(self) -> None:
        client = StubPymodbusClient()
        transport = _serial_transport_for_client(client)

        client.queue_response(StubPymodbusResponse(bits=[True, False, True]))
        client.queue_response(StubPymodbusResponse(bits=[False, True]))
        client.queue_response(StubPymodbusResponse(registers=[12, 34]))

        self.assertEqual(await transport.read_coils(10, 3, 32), [True, False, True])
        self.assertEqual(
            await transport.read_discrete_inputs(20, 2, 32), [False, True]
        )
        self.assertEqual(await transport.read_holding_registers(30, 2, 32), [12, 34])

        await transport.write_coil(40, True, 32)
        await transport.write_register(50, 65535, 32)

        self.assertIn(("read_coils", 10, 3, 32), client.calls)
        self.assertIn(("read_discrete_inputs", 20, 2, 32), client.calls)
        self.assertIn(("read_holding_registers", 30, 2, 32), client.calls)
        self.assertIn(("write_coil", 40, True, 32), client.calls)
        self.assertIn(("write_register", 50, 65535, 32), client.calls)

    async def test_serial_transport_serializes_requests(self) -> None:
        client = StubPymodbusClient()
        client.connected = True
        client.delay = 0.01
        transport = _serial_transport_for_client(client)

        await asyncio.gather(
            transport.read_coils(0, 1, 1),
            transport.read_holding_registers(0, 1, 2),
            transport.write_coil(0, True, 3),
        )

        self.assertEqual(client.max_active_requests, 1)
        self.assertEqual(len(client.calls), 3)

    async def test_serial_transport_converts_connection_errors(self) -> None:
        client = StubPymodbusClient()
        client.connect_result = False
        transport = _serial_transport_for_client(client)

        with self.assertRaises(wb_mr6c_modbus.WBMR6CModbusConnectionError):
            await transport.connect()

        client = StubPymodbusClient()
        client.connected = True
        client.exceptions["read_coils"] = RuntimeError("boom")
        transport = _serial_transport_for_client(client)

        with self.assertRaises(wb_mr6c_modbus.WBMR6CModbusConnectionError):
            await transport.read_coils(0, 1, 1)

    async def test_serial_transport_converts_response_errors(self) -> None:
        client = StubPymodbusClient()
        client.connected = True
        transport = _serial_transport_for_client(client)

        client.queue_response(StubPymodbusResponse(error=True))
        with self.assertRaises(wb_mr6c_modbus.WBMR6CModbusResponseError):
            await transport.read_coils(0, 1, 1)

        client.queue_response(StubPymodbusResponse(bits=[True]))
        with self.assertRaises(wb_mr6c_modbus.WBMR6CModbusResponseError):
            await transport.read_discrete_inputs(0, 2, 1)

        client.queue_response(StubPymodbusResponse(registers=[1]))
        with self.assertRaises(wb_mr6c_modbus.WBMR6CModbusResponseError):
            await transport.read_holding_registers(0, 2, 1)

    async def test_serial_transport_validates_register_values(self) -> None:
        client = StubPymodbusClient()
        client.connected = True
        transport = _serial_transport_for_client(client)

        with self.assertRaises(wb_mr6c_modbus.InvalidWBMR6CValueError):
            await transport.write_register(0, 0x10000, 1)

        self.assertEqual(client.calls, [])


class FakeModbusTransportTest(unittest.IsolatedAsyncioTestCase):
    async def test_fake_transport_stores_values_per_device(self) -> None:
        transport = wb_mr6c_modbus.FakeModbusTransport()
        await transport.connect()

        transport.set_coil(0, True, device_id=32)
        transport.set_coil(0, False, device_id=33)
        transport.set_discrete_input(7, True, device_id=32)
        transport.set_holding_register(200, 123, device_id=32)

        self.assertTrue(transport.connected)
        self.assertEqual(await transport.read_coils(0, 1, 32), [True])
        self.assertEqual(await transport.read_coils(0, 1, 33), [False])
        self.assertEqual(await transport.read_discrete_inputs(7, 1, 32), [True])
        self.assertEqual(await transport.read_holding_registers(200, 1, 32), [123])

        await transport.write_coil(1, True, 32)
        await transport.write_register(201, 456, 32)

        self.assertTrue(transport.coils[(32, 1)])
        self.assertEqual(transport.holding_registers[(32, 201)], 456)
        self.assertIn(("write_coil", 1, True, 32), transport.writes)
        self.assertIn(("write_register", 201, 456, 32), transport.writes)

        await transport.close()
        self.assertFalse(transport.connected)

    async def test_fake_transport_simulates_failure_responses(self) -> None:
        unavailable = wb_mr6c_modbus.FakeModbusTransport(
            unavailable_devices={32}
        )
        with self.assertRaises(wb_mr6c_modbus.WBMR6CModbusConnectionError):
            await unavailable.read_coils(0, 1, 32)

        response_error = wb_mr6c_modbus.FakeModbusTransport(
            response_error_devices={32}
        )
        with self.assertRaises(wb_mr6c_modbus.WBMR6CModbusResponseError):
            await response_error.read_coils(0, 1, 32)

        short = wb_mr6c_modbus.FakeModbusTransport(short_response_devices={32})
        client = wb_mr6c_modbus.WBMR6CModbus(short, device_id=32)
        with self.assertRaises(wb_mr6c_modbus.WBMR6CModbusResponseError):
            await client.read_relay_commands()


class WBMR6CModbusTest(unittest.IsolatedAsyncioTestCase):
    async def test_read_snapshot(self) -> None:
        transport = FakeTransport()
        transport.coils[0] = True
        transport.coils[5] = True
        transport.discrete_inputs[96] = True
        transport.discrete_inputs[101] = True
        transport.discrete_inputs[0] = True
        transport.discrete_inputs[7] = True

        client = wb_mr6c_modbus.WBMR6CModbus(transport, device_id=32)
        snapshot = await client.read_snapshot()

        self.assertTrue(snapshot.commands[1])
        self.assertTrue(snapshot.commands[6])
        self.assertTrue(snapshot.states[1])
        self.assertTrue(snapshot.states[6])
        self.assertTrue(snapshot.inputs[1])
        self.assertTrue(snapshot.inputs[0])

    async def test_one_shot_commands(self) -> None:
        transport = FakeTransport()
        client = wb_mr6c_modbus.WBMR6CModbus(transport, device_id=32)

        await client.turn_on(3)
        await client.turn_off(4)
        await client.toggle(5)

        self.assertIn(("write_coil", 110, True, 32), transport.calls)
        self.assertIn(("write_coil", 103, True, 32), transport.calls)
        self.assertIn(("write_coil", 120, True, 32), transport.calls)

    async def test_set_mapping_action(self) -> None:
        transport = FakeTransport()
        client = wb_mr6c_modbus.WBMR6CModbus(transport, device_id=32)

        await client.set_mapping_action(
            wb_mr6c_modbus.MappingEvent.SHORT_PRESS,
            input_number=0,
            output=6,
            action=wb_mr6c_modbus.MappingAction.TOGGLE,
        )

        self.assertEqual(transport.holding_registers[605], 3)
        self.assertIn(("write_register", 605, 3, 32), transport.calls)

    async def test_set_mapping_action_validates_arguments(self) -> None:
        transport = FakeTransport()
        client = wb_mr6c_modbus.WBMR6CModbus(transport, device_id=32)

        with self.assertRaises(wb_mr6c_modbus.InvalidWBMR6CAddressError):
            await client.set_mapping_action(999, 1, 1, wb_mr6c_modbus.MappingAction.ON)

        with self.assertRaises(wb_mr6c_modbus.InvalidWBMR6CAddressError):
            await client.set_mapping_action(
                wb_mr6c_modbus.MappingEvent.SHORT_PRESS,
                7,
                1,
                wb_mr6c_modbus.MappingAction.ON,
            )

        with self.assertRaises(wb_mr6c_modbus.InvalidWBMR6CAddressError):
            await client.set_mapping_action(
                wb_mr6c_modbus.MappingEvent.SHORT_PRESS,
                1,
                7,
                wb_mr6c_modbus.MappingAction.ON,
            )

        with self.assertRaises(wb_mr6c_modbus.InvalidWBMR6CValueError):
            await client.set_mapping_action(
                wb_mr6c_modbus.MappingEvent.SHORT_PRESS,
                1,
                1,
                4,
            )

        self.assertEqual(transport.calls, [])

    async def test_read_mapping_action_rejects_invalid_device_value(self) -> None:
        transport = FakeTransport()
        transport.holding_registers[544] = 4
        client = wb_mr6c_modbus.WBMR6CModbus(transport, device_id=32)

        with self.assertRaises(wb_mr6c_modbus.WBMR6CModbusResponseError):
            await client.read_mapping_action(
                wb_mr6c_modbus.MappingEvent.SHORT_PRESS,
                input_number=1,
                output=1,
            )

    async def test_read_mapping_matrix_returns_all_documented_cells(self) -> None:
        transport = FakeTransport()
        for input_number in wb_mr6c_modbus.INPUTS:
            for output in wb_mr6c_modbus.OUTPUTS:
                action = (input_number + output) % 4
                transport.holding_registers[
                    wb_mr6c_modbus.mapping_register_address(
                        wb_mr6c_modbus.MappingEvent.SHORT_PRESS,
                        input_number,
                        output,
                    )
                ] = action

        client = wb_mr6c_modbus.WBMR6CModbus(transport, device_id=32)
        matrix = await client.read_mapping_matrix(
            wb_mr6c_modbus.MappingEvent.SHORT_PRESS
        )

        self.assertEqual(set(matrix), set(_complete_mapping_matrix()))
        for input_number in wb_mr6c_modbus.INPUTS:
            for output in wb_mr6c_modbus.OUTPUTS:
                self.assertEqual(
                    matrix[(input_number, output)],
                    (input_number + output) % 4,
                )
        self.assertIn(("read_holding_registers", 544, 64, 32), transport.calls)

    async def test_write_mapping_matrix_writes_only_changed_cells(self) -> None:
        transport = FakeTransport()
        current = _complete_mapping_matrix()
        current[(1, 1)] = 1
        current[(0, 6)] = 3
        for (input_number, output), action in current.items():
            transport.holding_registers[
                wb_mr6c_modbus.mapping_register_address(
                    wb_mr6c_modbus.MappingEvent.SHORT_PRESS,
                    input_number,
                    output,
                )
            ] = action

        desired = dict(current)
        desired[(1, 1)] = 2
        desired[(2, 3)] = 1
        client = wb_mr6c_modbus.WBMR6CModbus(transport, device_id=32)

        await client.write_mapping_matrix(
            wb_mr6c_modbus.MappingEvent.SHORT_PRESS,
            desired,
        )

        writes = [call for call in transport.calls if call[0] == "write_register"]
        self.assertEqual(
            writes,
            [
                ("write_register", 544, 2, 32),
                ("write_register", 554, 1, 32),
            ],
        )

    async def test_write_mapping_matrix_skips_unchanged_cells(self) -> None:
        transport = FakeTransport()
        desired = _complete_mapping_matrix()
        for (input_number, output), action in desired.items():
            transport.holding_registers[
                wb_mr6c_modbus.mapping_register_address(
                    wb_mr6c_modbus.MappingEvent.SHORT_PRESS,
                    input_number,
                    output,
                )
            ] = action

        client = wb_mr6c_modbus.WBMR6CModbus(transport, device_id=32)

        await client.write_mapping_matrix(
            wb_mr6c_modbus.MappingEvent.SHORT_PRESS,
            desired,
        )

        writes = [call for call in transport.calls if call[0] == "write_register"]
        self.assertEqual(writes, [])
        self.assertEqual(
            transport.calls,
            [("read_holding_registers", 544, 64, 32)],
        )

    async def test_write_mapping_matrix_validates_before_modbus_calls(self) -> None:
        transport = FakeTransport()
        client = wb_mr6c_modbus.WBMR6CModbus(transport, device_id=32)

        with self.assertRaises(wb_mr6c_modbus.InvalidWBMR6CAddressError):
            await client.write_mapping_matrix(999, _complete_mapping_matrix())

        desired = _complete_mapping_matrix()
        desired[(1, 1)] = 4
        with self.assertRaises(wb_mr6c_modbus.InvalidWBMR6CValueError):
            await client.write_mapping_matrix(
                wb_mr6c_modbus.MappingEvent.SHORT_PRESS,
                desired,
            )

        desired = _complete_mapping_matrix()
        desired[(7, 1)] = 0
        with self.assertRaises(wb_mr6c_modbus.InvalidWBMR6CAddressError):
            await client.write_mapping_matrix(
                wb_mr6c_modbus.MappingEvent.SHORT_PRESS,
                desired,
            )

        desired = _complete_mapping_matrix()
        del desired[(0, 6)]
        with self.assertRaises(wb_mr6c_modbus.InvalidWBMR6CValueError):
            await client.write_mapping_matrix(
                wb_mr6c_modbus.MappingEvent.SHORT_PRESS,
                desired,
            )

        self.assertEqual(transport.calls, [])

    async def test_read_press_counters(self) -> None:
        transport = FakeTransport()
        transport.holding_registers[32] = 10
        transport.holding_registers[37] = 60
        transport.holding_registers[464] = 11
        transport.holding_registers[471] = 70

        client = wb_mr6c_modbus.WBMR6CModbus(transport, device_id=32)
        activation = await client.read_press_counters(
            wb_mr6c_modbus.PressCounterEvent.ACTIVATION
        )
        short = await client.read_press_counters(wb_mr6c_modbus.PressCounterEvent.SHORT)

        self.assertEqual(activation[1], 10)
        self.assertEqual(activation[6], 60)
        self.assertNotIn(0, activation)
        self.assertEqual(short[1], 11)
        self.assertEqual(short[0], 70)

    async def test_read_model_and_firmware(self) -> None:
        transport = FakeTransport()
        for offset, char in enumerate("WBMR6CU"):
            transport.holding_registers[200 + offset] = ord(char)
        for offset, char in enumerate("1.24.0"):
            transport.holding_registers[250 + offset] = ord(char)
        transport.holding_registers[257] = 0

        client = wb_mr6c_modbus.WBMR6CModbus(transport, device_id=32)

        self.assertEqual(await client.read_model(), "WBMR6CU")
        self.assertEqual(await client.read_firmware_version(), "1.24.0")
        self.assertIn(
            (
                "read_holding_registers",
                wb_mr6c_modbus.REG_MODEL_BASE,
                wb_mr6c_modbus.REG_MODEL_MAX_LENGTH,
                32,
            ),
            transport.calls,
        )

    async def test_read_firmware_rejects_short_response(self) -> None:
        transport = ShortHoldingRegisterTransport([ord("1"), 0])
        client = wb_mr6c_modbus.WBMR6CModbus(transport, device_id=32)

        with self.assertRaises(wb_mr6c_modbus.WBMR6CModbusResponseError):
            await client.read_firmware_version()

    async def test_read_mapping_matrix_rejects_short_response(self) -> None:
        transport = ShortHoldingRegisterTransport([0] * 10)
        client = wb_mr6c_modbus.WBMR6CModbus(transport, device_id=32)

        with self.assertRaises(wb_mr6c_modbus.WBMR6CModbusResponseError):
            await client.read_mapping_matrix(wb_mr6c_modbus.MappingEvent.SHORT_PRESS)

    async def test_invalid_enum_setters_raise_backend_value_error(self) -> None:
        transport = FakeTransport()
        client = wb_mr6c_modbus.WBMR6CModbus(transport, device_id=32)

        with self.assertRaises(wb_mr6c_modbus.InvalidWBMR6CValueError):
            await client.set_output_power_on_mode(3)

        with self.assertRaises(wb_mr6c_modbus.InvalidWBMR6CValueError):
            await client.set_input_mode(1, 99)

        with self.assertRaises(wb_mr6c_modbus.InvalidWBMR6CValueError):
            await client.set_input_mode(1, wb_mr6c_modbus.InputMode.DISABLED)

        with self.assertRaises(wb_mr6c_modbus.InvalidWBMR6CValueError):
            await client.set_input_mode(0, wb_mr6c_modbus.InputMode.MOMENTARY)

        with self.assertRaises(wb_mr6c_modbus.InvalidWBMR6CValueError):
            await client.set_input_mode(0, wb_mr6c_modbus.InputMode.LATCHING)

        with self.assertRaises(wb_mr6c_modbus.InvalidWBMR6CValueError):
            await client.set_safe_state(1, 2)

        with self.assertRaises(wb_mr6c_modbus.InvalidWBMR6CValueError):
            await client.set_safe_mode_action(1, 2)

        with self.assertRaises(wb_mr6c_modbus.InvalidWBMR6CValueError):
            await client.set_safe_mode_input_control(1, 3)

    async def test_invalid_setting_ranges_raise_backend_value_error(self) -> None:
        transport = FakeTransport()
        client = wb_mr6c_modbus.WBMR6CModbus(transport, device_id=32)

        with self.assertRaises(wb_mr6c_modbus.InvalidWBMR6CValueError):
            await client.set_communication_timeout_s(0)

        with self.assertRaises(wb_mr6c_modbus.InvalidWBMR6CValueError):
            await client.set_debounce_ms(1, 2001)

        with self.assertRaises(wb_mr6c_modbus.InvalidWBMR6CValueError):
            await client.set_long_press_ms(1, 499)

        with self.assertRaises(wb_mr6c_modbus.InvalidWBMR6CValueError):
            await client.set_second_press_wait_ms(1, 2001)

        self.assertEqual(transport.calls, [])

    async def test_invalid_setting_addresses_raise_backend_address_error(self) -> None:
        transport = FakeTransport()
        client = wb_mr6c_modbus.WBMR6CModbus(transport, device_id=32)

        with self.assertRaises(wb_mr6c_modbus.InvalidWBMR6CAddressError):
            await client.set_input_mode(7, wb_mr6c_modbus.InputMode.MOMENTARY)

        with self.assertRaises(wb_mr6c_modbus.InvalidWBMR6CAddressError):
            await client.set_debounce_ms(7, 50)

        with self.assertRaises(wb_mr6c_modbus.InvalidWBMR6CAddressError):
            await client.set_long_press_ms(7, 1000)

        with self.assertRaises(wb_mr6c_modbus.InvalidWBMR6CAddressError):
            await client.set_second_press_wait_ms(7, 300)

        with self.assertRaises(wb_mr6c_modbus.InvalidWBMR6CAddressError):
            await client.set_safe_state(7, wb_mr6c_modbus.SafeState.OFF)

        with self.assertRaises(wb_mr6c_modbus.InvalidWBMR6CAddressError):
            await client.set_safe_mode_action(
                7,
                wb_mr6c_modbus.SafeModeAction.KEEP_CURRENT_STATE,
            )

        with self.assertRaises(wb_mr6c_modbus.InvalidWBMR6CAddressError):
            await client.set_safe_mode_input_control(
                7,
                wb_mr6c_modbus.SafeModeInputControl.DO_NOT_BLOCK,
            )

        self.assertEqual(transport.calls, [])

    async def test_read_input_scoped_settings_include_input_zero(self) -> None:
        transport = FakeTransport()
        for input_number in wb_mr6c_modbus.INPUTS:
            input_index = 7 if input_number == 0 else input_number - 1
            transport.holding_registers[
                wb_mr6c_modbus.REG_INPUT_MODE_BASE + input_index
            ] = input_number + 10
            transport.holding_registers[
                wb_mr6c_modbus.REG_INPUT_DEBOUNCE_MS_BASE + input_index
            ] = input_number + 20
            transport.holding_registers[
                wb_mr6c_modbus.REG_LONG_PRESS_MS_BASE + input_index
            ] = input_number + 30
            transport.holding_registers[
                wb_mr6c_modbus.REG_SECOND_PRESS_WAIT_MS_BASE + input_index
            ] = input_number + 40

        client = wb_mr6c_modbus.WBMR6CModbus(transport, device_id=32)

        input_modes = await client.read_input_modes()
        debounce_ms = await client.read_debounce_ms()
        long_press_ms = await client.read_long_press_ms()
        second_press_wait_ms = await client.read_second_press_wait_ms()

        self.assertEqual(set(input_modes), set(wb_mr6c_modbus.INPUTS))
        self.assertEqual(input_modes[1], 11)
        self.assertEqual(input_modes[6], 16)
        self.assertEqual(input_modes[0], 10)
        self.assertEqual(debounce_ms[0], 20)
        self.assertEqual(long_press_ms[0], 30)
        self.assertEqual(second_press_wait_ms[0], 40)
        self.assertIn(("read_holding_registers", 9, 8, 32), transport.calls)
        self.assertIn(("read_holding_registers", 20, 8, 32), transport.calls)
        self.assertIn(("read_holding_registers", 1100, 8, 32), transport.calls)
        self.assertIn(("read_holding_registers", 1140, 8, 32), transport.calls)

    async def test_read_input_scoped_settings_reject_short_response(self) -> None:
        transport = ShortHoldingRegisterTransport([0] * 7)
        client = wb_mr6c_modbus.WBMR6CModbus(transport, device_id=32)

        with self.assertRaises(wb_mr6c_modbus.WBMR6CModbusResponseError):
            await client.read_input_modes()

    async def test_read_safe_mode_settings_reject_short_response(self) -> None:
        transport = ShortHoldingRegisterTransport([0] * 5)
        client = wb_mr6c_modbus.WBMR6CModbus(transport, device_id=32)

        with self.assertRaises(wb_mr6c_modbus.WBMR6CModbusResponseError):
            await client.read_safe_states()

        with self.assertRaises(wb_mr6c_modbus.WBMR6CModbusResponseError):
            await client.read_safe_mode_actions()

        with self.assertRaises(wb_mr6c_modbus.WBMR6CModbusResponseError):
            await client.read_safe_mode_input_controls()

    async def test_setting_setters_write_register_addresses_and_values(self) -> None:
        transport = FakeTransport()
        client = wb_mr6c_modbus.WBMR6CModbus(transport, device_id=32)

        await client.set_output_power_on_mode(
            wb_mr6c_modbus.OutputPowerOnMode.RESTORE_LAST_STATE
        )
        await client.set_communication_timeout_s(15)
        await client.set_input_mode(0, wb_mr6c_modbus.InputMode.MAPPING_MATRIX_EDGE)
        await client.set_debounce_ms(0, 75)
        await client.set_long_press_ms(0, 1200)
        await client.set_second_press_wait_ms(0, 350)
        await client.set_safe_state(6, wb_mr6c_modbus.SafeState.ON)
        await client.set_safe_mode_action(
            3,
            wb_mr6c_modbus.SafeModeAction.SET_SAFE_STATE,
        )
        await client.set_safe_mode_input_control(
            6,
            wb_mr6c_modbus.SafeModeInputControl.ALLOW_ONLY_IN_SAFE_MODE,
        )

        self.assertIn(("write_register", 6, 1, 32), transport.calls)
        self.assertIn(("write_register", 8, 15, 32), transport.calls)
        self.assertIn(("write_register", 16, 4, 32), transport.calls)
        self.assertIn(("write_register", 27, 75, 32), transport.calls)
        self.assertIn(("write_register", 1107, 1200, 32), transport.calls)
        self.assertIn(("write_register", 1147, 350, 32), transport.calls)
        self.assertIn(("write_register", 935, 1, 32), transport.calls)
        self.assertIn(("write_register", 940, 1, 32), transport.calls)
        self.assertIn(("write_register", 951, 2, 32), transport.calls)

    async def test_read_basic_settings(self) -> None:
        transport = FakeTransport()
        transport.holding_registers[6] = 1
        transport.holding_registers[8] = 10
        transport.holding_registers[9] = 6
        transport.holding_registers[16] = 4
        transport.holding_registers[20] = 50
        transport.holding_registers[27] = 100
        transport.holding_registers[1100] = 1000
        transport.holding_registers[1107] = 1500
        transport.holding_registers[1140] = 300
        transport.holding_registers[1147] = 400
        transport.holding_registers[930] = 1
        transport.holding_registers[938] = 1
        transport.holding_registers[946] = 2

        client = wb_mr6c_modbus.WBMR6CModbus(transport, device_id=32)
        settings = await client.read_basic_settings()

        self.assertEqual(settings.output_power_on_mode, 1)
        self.assertEqual(settings.communication_timeout_s, 10)
        self.assertEqual(settings.input_modes[1], 6)
        self.assertEqual(settings.input_modes[0], 4)
        self.assertEqual(settings.debounce_ms[1], 50)
        self.assertEqual(settings.debounce_ms[0], 100)
        self.assertEqual(settings.long_press_ms[1], 1000)
        self.assertEqual(settings.long_press_ms[0], 1500)
        self.assertEqual(settings.second_press_wait_ms[1], 300)
        self.assertEqual(settings.second_press_wait_ms[0], 400)
        self.assertTrue(settings.safe_states[1])
        self.assertEqual(settings.safe_mode_actions[1], 1)
        self.assertEqual(settings.safe_mode_input_controls[1], 2)


if __name__ == "__main__":
    unittest.main()
