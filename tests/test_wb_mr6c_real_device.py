from __future__ import annotations

import importlib.util
import os
import sys
import unittest
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "openwb"
    / "wb_mr6c_modbus.py"
)
SPEC = importlib.util.spec_from_file_location(
    "wb_mr6c_modbus_real_device", MODULE_PATH
)
assert SPEC is not None
assert SPEC.loader is not None
wb_mr6c_modbus = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = wb_mr6c_modbus
SPEC.loader.exec_module(wb_mr6c_modbus)


@dataclass(frozen=True, slots=True)
class RealDeviceConfig:
    port: str
    device_id: int
    baudrate: int
    parity: str
    stopbits: int
    timeout: float


class RealDeviceConfigError(ValueError):
    """Raised when real-device test environment variables are invalid."""


def _real_device_config_from_env(
    env: Mapping[str, str] = os.environ,
) -> RealDeviceConfig | None:
    if env.get("OPENWB_REAL_DEVICE_TESTS") != "1":
        return None

    port = env.get("OPENWB_SERIAL_PORT", "").strip()
    if not port:
        raise RealDeviceConfigError(
            "OPENWB_REAL_DEVICE_TESTS=1 requires OPENWB_SERIAL_PORT, "
            "for example /dev/ttyUSB0"
        )

    return RealDeviceConfig(
        port=port,
        device_id=_parse_int_env(env, "OPENWB_DEVICE_ID", 1, minimum=1, maximum=247),
        baudrate=_parse_int_env(env, "OPENWB_BAUDRATE", 9600, minimum=1),
        parity=_parse_parity_env(env),
        stopbits=_parse_int_env(env, "OPENWB_STOPBITS", 2, minimum=1),
        timeout=_parse_float_env(env, "OPENWB_TIMEOUT", 3.0, minimum=0.1),
    )


def _parse_int_env(
    env: Mapping[str, str],
    name: str,
    default: int,
    *,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    raw_value = env.get(name, str(default)).strip()
    try:
        value = int(raw_value)
    except ValueError as err:
        raise RealDeviceConfigError(
            f"{name} must be an integer, got {raw_value!r}"
        ) from err

    if minimum is not None and value < minimum:
        raise RealDeviceConfigError(f"{name} must be >= {minimum}, got {value}")
    if maximum is not None and value > maximum:
        raise RealDeviceConfigError(f"{name} must be <= {maximum}, got {value}")
    return value


def _parse_float_env(
    env: Mapping[str, str],
    name: str,
    default: float,
    *,
    minimum: float | None = None,
) -> float:
    raw_value = env.get(name, str(default)).strip()
    try:
        value = float(raw_value)
    except ValueError as err:
        raise RealDeviceConfigError(
            f"{name} must be a float, got {raw_value!r}"
        ) from err

    if minimum is not None and value < minimum:
        raise RealDeviceConfigError(f"{name} must be >= {minimum}, got {value}")
    return value


def _parse_parity_env(env: Mapping[str, str]) -> str:
    parity = env.get("OPENWB_PARITY", "N").strip().upper()
    if parity not in {"N", "E", "O"}:
        raise RealDeviceConfigError(
            f"OPENWB_PARITY must be one of N, E, or O, got {parity!r}"
        )
    return parity


class RealDeviceConfigTest(unittest.TestCase):
    def test_real_device_tests_are_disabled_by_default(self) -> None:
        self.assertIsNone(_real_device_config_from_env({}))

    def test_enabled_real_device_tests_require_serial_port(self) -> None:
        with self.assertRaisesRegex(RealDeviceConfigError, "OPENWB_SERIAL_PORT"):
            _real_device_config_from_env({"OPENWB_REAL_DEVICE_TESTS": "1"})

    def test_real_device_config_uses_defaults(self) -> None:
        config = _real_device_config_from_env(
            {"OPENWB_REAL_DEVICE_TESTS": "1", "OPENWB_SERIAL_PORT": "/dev/ttyUSB0"}
        )

        self.assertEqual(
            config,
            RealDeviceConfig(
                port="/dev/ttyUSB0",
                device_id=1,
                baudrate=9600,
                parity="N",
                stopbits=2,
                timeout=3.0,
            ),
        )

    def test_real_device_config_accepts_overrides(self) -> None:
        config = _real_device_config_from_env(
            {
                "OPENWB_REAL_DEVICE_TESTS": "1",
                "OPENWB_SERIAL_PORT": "/dev/ttyUSB1",
                "OPENWB_DEVICE_ID": "12",
                "OPENWB_BAUDRATE": "19200",
                "OPENWB_PARITY": "e",
                "OPENWB_STOPBITS": "1",
                "OPENWB_TIMEOUT": "1.5",
            }
        )

        self.assertEqual(
            config,
            RealDeviceConfig(
                port="/dev/ttyUSB1",
                device_id=12,
                baudrate=19200,
                parity="E",
                stopbits=1,
                timeout=1.5,
            ),
        )

    def test_real_device_config_rejects_invalid_values(self) -> None:
        with self.assertRaisesRegex(RealDeviceConfigError, "OPENWB_DEVICE_ID"):
            _real_device_config_from_env(
                {
                    "OPENWB_REAL_DEVICE_TESTS": "1",
                    "OPENWB_SERIAL_PORT": "/dev/ttyUSB0",
                    "OPENWB_DEVICE_ID": "0",
                }
            )

        with self.assertRaisesRegex(RealDeviceConfigError, "OPENWB_PARITY"):
            _real_device_config_from_env(
                {
                    "OPENWB_REAL_DEVICE_TESTS": "1",
                    "OPENWB_SERIAL_PORT": "/dev/ttyUSB0",
                    "OPENWB_PARITY": "bad",
                }
            )


class WBMR6CRealDeviceSmokeTest(unittest.IsolatedAsyncioTestCase):
    config: RealDeviceConfig

    @classmethod
    def setUpClass(cls) -> None:
        try:
            config = _real_device_config_from_env()
        except RealDeviceConfigError as err:
            raise unittest.SkipTest(str(err)) from err

        if config is None:
            raise unittest.SkipTest(
                "Set OPENWB_REAL_DEVICE_TESTS=1 and OPENWB_SERIAL_PORT to run "
                "WB-MR6C real-device smoke tests"
            )

        cls.config = config

    async def test_serial_transport_connect_close_lifecycle(self) -> None:
        transport = self._transport()
        try:
            await transport.connect()
        finally:
            await transport.close()

    async def test_read_identity_and_read_only_state(self) -> None:
        transport = self._transport()
        client = wb_mr6c_modbus.WBMR6CModbus(
            transport,
            device_id=self.config.device_id,
        )
        relay_states: dict[int, bool] | None = None

        try:
            model = await client.read_model()
            firmware = await client.read_firmware_version()
            firmware_tuple = wb_mr6c_modbus.parse_firmware_version(firmware)
            relay_commands = await client.read_relay_commands()
            input_states = await client.read_input_states()

            self.assertTrue(model, "Model register returned an empty string")
            self.assertEqual(
                model,
                "WBMR6C",
                f"Expected WB-MR6C model identity, got {model!r}",
            )
            self.assertTrue(firmware, "Firmware register returned an empty string")
            self.assertEqual(len(firmware_tuple), 3)
            self._assert_channel_bool_map(relay_commands)
            self._assert_input_bool_map(input_states)

            if wb_mr6c_modbus.firmware_supports_relay_state_discrete_inputs(
                firmware_tuple
            ):
                relay_states = await client.read_relay_states()
                self._assert_channel_bool_map(relay_states)
        finally:
            await transport.close()

        relay_state_report = relay_states if relay_states is not None else "not read"
        print(
            "WB-MR6C real-device smoke result: "
            f"port={self.config.port!r}, device_id={self.config.device_id}, "
            f"model={model!r}, firmware={firmware!r}, "
            f"relay_commands={relay_commands}, input_states={input_states}, "
            f"relay_states={relay_state_report}"
        )

    def _transport(self) -> wb_mr6c_modbus.PymodbusSerialTransport:
        return wb_mr6c_modbus.PymodbusSerialTransport(
            self.config.port,
            baudrate=self.config.baudrate,
            parity=self.config.parity,
            stopbits=self.config.stopbits,
            timeout=self.config.timeout,
        )

    def _assert_channel_bool_map(self, values: dict[int, bool]) -> None:
        self.assertEqual(set(values), set(wb_mr6c_modbus.CHANNELS))
        for value in values.values():
            self.assertIsInstance(value, bool)

    def _assert_input_bool_map(self, values: dict[int, bool]) -> None:
        self.assertEqual(set(values), set(wb_mr6c_modbus.INPUTS))
        for value in values.values():
            self.assertIsInstance(value, bool)


if __name__ == "__main__":
    unittest.main()
