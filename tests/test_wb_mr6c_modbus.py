from __future__ import annotations

import importlib.util
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
        return [self.coils.get(address + offset, False) for offset in range(count)]

    async def write_coil(self, address: int, value: bool, device_id: int) -> None:
        self.coils[address] = value
        self.calls.append(("write_coil", address, value, device_id))

    async def read_discrete_inputs(
        self, address: int, count: int, device_id: int
    ) -> list[bool]:
        return [
            self.discrete_inputs.get(address + offset, False)
            for offset in range(count)
        ]

    async def read_holding_registers(
        self, address: int, count: int, device_id: int
    ) -> list[int]:
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
        firmware_registers = [ord(char) for char in "1.24.0"] + [0] * 10

        self.assertEqual(
            wb_mr6c_modbus.decode_model_registers(model_registers), "WBMR6C"
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
        for offset, char in enumerate("WBMR6C"):
            transport.holding_registers[200 + offset] = ord(char)
        for offset, char in enumerate("1.24.0"):
            transport.holding_registers[250 + offset] = ord(char)
        transport.holding_registers[257] = 0

        client = wb_mr6c_modbus.WBMR6CModbus(transport, device_id=32)

        self.assertEqual(await client.read_model(), "WBMR6C")
        self.assertEqual(await client.read_firmware_version(), "1.24.0")

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
            await client.set_input_mode(1, 99)

        with self.assertRaises(wb_mr6c_modbus.InvalidWBMR6CValueError):
            await client.set_safe_state(1, 2)

        with self.assertRaises(wb_mr6c_modbus.InvalidWBMR6CValueError):
            await client.set_safe_mode_action(1, 2)

        with self.assertRaises(wb_mr6c_modbus.InvalidWBMR6CValueError):
            await client.set_safe_mode_input_control(1, 3)

    async def test_read_basic_settings(self) -> None:
        transport = FakeTransport()
        transport.holding_registers[6] = 1
        transport.holding_registers[8] = 10
        transport.holding_registers[9] = 6
        transport.holding_registers[16] = 4
        transport.holding_registers[20] = 50
        transport.holding_registers[27] = 100
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
        self.assertTrue(settings.safe_states[1])
        self.assertEqual(settings.safe_mode_actions[1], 1)
        self.assertEqual(settings.safe_mode_input_controls[1], 2)


if __name__ == "__main__":
    unittest.main()
