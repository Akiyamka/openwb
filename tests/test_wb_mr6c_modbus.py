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


class AddressingTest(unittest.TestCase):
    def test_relay_channel_address(self) -> None:
        self.assertEqual(
            wb_mr6c_modbus.relay_channel_address(
                wb_mr6c_modbus.COIL_RELAY_ON_COMMAND_BASE, 3
            ),
            110,
        )

    def test_input_zero_address(self) -> None:
        self.assertEqual(
            wb_mr6c_modbus.input_register_address(
                wb_mr6c_modbus.REG_INPUT_MODE_BASE, 0
            ),
            16,
        )

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

    def test_invalid_channel(self) -> None:
        with self.assertRaises(wb_mr6c_modbus.InvalidWBMR6CAddressError):
            wb_mr6c_modbus.relay_channel_address(0, 7)


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

