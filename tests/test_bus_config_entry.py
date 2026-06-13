from __future__ import annotations

import importlib
import sys
import types
import unittest
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


class AbortFlow(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class ConfigEntryNotReady(Exception):
    """Stub Home Assistant setup retry exception."""


class StubConfigFlow:
    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__()

    def __init__(self) -> None:
        self._unique_id: str | None = None
        self._configured_unique_ids: set[str] = set()

    async def async_set_unique_id(self, unique_id: str) -> None:
        self._unique_id = unique_id

    def _abort_if_unique_id_configured(
        self, updates: dict[str, Any] | None = None
    ) -> None:
        if self._unique_id in self._configured_unique_ids:
            raise AbortFlow("already_configured")

    def async_create_entry(
        self, *, title: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        return {"type": "create_entry", "title": title, "data": data}

    def async_show_form(
        self,
        *,
        step_id: str,
        data_schema: object,
        errors: dict[str, str],
    ) -> dict[str, Any]:
        return {
            "type": "form",
            "step_id": step_id,
            "data_schema": data_schema,
            "errors": errors,
        }


class StubConfigEntry:
    def __init__(self, data: dict[str, Any], *, version: int = 2) -> None:
        self.data = data
        self.entry_id = "bus-entry"
        self.version = version

    def __class_getitem__(cls, item: object) -> type[StubConfigEntry]:
        return cls


class Schema:
    def __init__(self, schema: object) -> None:
        self.schema = schema


class Required(str):
    def __new__(cls, key: str, default: object | None = None) -> Required:
        obj = str.__new__(cls, key)
        obj.default = default
        return obj


class TextSelector:
    def __init__(self, config: object | None = None) -> None:
        self.config = config


class SelectSelector:
    def __init__(self, config: object | None = None) -> None:
        self.config = config


class TextSelectorType:
    NUMBER = "number"


def _install_homeassistant_stubs() -> None:
    homeassistant = types.ModuleType("homeassistant")
    config_entries = types.ModuleType("homeassistant.config_entries")
    config_entries.ConfigEntry = StubConfigEntry
    config_entries.ConfigFlow = StubConfigFlow

    core = types.ModuleType("homeassistant.core")
    core.HomeAssistant = type("HomeAssistant", (), {})

    data_entry_flow = types.ModuleType("homeassistant.data_entry_flow")
    data_entry_flow.FlowResult = dict[str, Any]
    data_entry_flow.AbortFlow = AbortFlow

    exceptions = types.ModuleType("homeassistant.exceptions")
    exceptions.ConfigEntryNotReady = ConfigEntryNotReady

    helpers = types.ModuleType("homeassistant.helpers")
    selector = types.ModuleType("homeassistant.helpers.selector")
    selector.TextSelector = TextSelector
    selector.TextSelectorType = TextSelectorType
    selector.SelectSelector = SelectSelector
    helpers.selector = selector

    voluptuous = types.ModuleType("voluptuous")
    voluptuous.Schema = Schema
    voluptuous.Required = Required

    homeassistant.config_entries = config_entries
    homeassistant.core = core
    homeassistant.data_entry_flow = data_entry_flow
    homeassistant.exceptions = exceptions
    homeassistant.helpers = helpers

    sys.modules["homeassistant"] = homeassistant
    sys.modules["homeassistant.config_entries"] = config_entries
    sys.modules["homeassistant.core"] = core
    sys.modules["homeassistant.data_entry_flow"] = data_entry_flow
    sys.modules["homeassistant.exceptions"] = exceptions
    sys.modules["homeassistant.helpers"] = helpers
    sys.modules["homeassistant.helpers.selector"] = selector
    sys.modules["voluptuous"] = voluptuous


def _module_available(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except ModuleNotFoundError:
        return False


if _module_available("homeassistant.config_entries") or _module_available(
    "voluptuous"
):
    raise unittest.SkipTest(
        "Skipping stubbed bus config tests because Home Assistant or voluptuous "
        "is installed"
    )


_STUBBED_MODULE_NAMES = (
    "homeassistant",
    "homeassistant.config_entries",
    "homeassistant.core",
    "homeassistant.data_entry_flow",
    "homeassistant.exceptions",
    "homeassistant.helpers",
    "homeassistant.helpers.selector",
    "voluptuous",
    "custom_components.openwb",
    "custom_components.openwb.config_flow",
    "custom_components.openwb.const",
)
_MISSING = object()
_ORIGINAL_MODULES = {
    module_name: sys.modules.get(module_name, _MISSING)
    for module_name in _STUBBED_MODULE_NAMES
}


def _restore_stubbed_modules() -> None:
    for module_name, original_module in _ORIGINAL_MODULES.items():
        if original_module is _MISSING:
            sys.modules.pop(module_name, None)
        else:
            sys.modules[module_name] = original_module


unittest.addModuleCleanup(_restore_stubbed_modules)


_install_homeassistant_stubs()

integration = importlib.import_module("custom_components.openwb")
config_flow = importlib.import_module("custom_components.openwb.config_flow")
const = importlib.import_module("custom_components.openwb.const")


class FakeSerialTransport:
    instances: list[FakeSerialTransport] = []
    connect_error: Exception | None = None

    def __init__(
        self,
        port: str,
        *,
        baudrate: int,
        parity: str,
        stopbits: int,
    ) -> None:
        self.port = port
        self.baudrate = baudrate
        self.parity = parity
        self.stopbits = stopbits
        self.connect_calls = 0
        self.close_calls = 0
        FakeSerialTransport.instances.append(self)

    async def connect(self) -> None:
        self.connect_calls += 1
        if FakeSerialTransport.connect_error is not None:
            raise FakeSerialTransport.connect_error

    async def close(self) -> None:
        self.close_calls += 1


class FakeConfigEntriesManager:
    def __init__(self) -> None:
        self.updates: list[tuple[StubConfigEntry, dict[str, Any]]] = []

    def async_update_entry(
        self, entry: StubConfigEntry, **kwargs: Any
    ) -> None:
        self.updates.append((entry, kwargs))
        if "version" in kwargs:
            entry.version = kwargs["version"]


class BusConfigFlowTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        FakeSerialTransport.instances = []
        FakeSerialTransport.connect_error = None
        self.original_transport = config_flow.PymodbusSerialTransport
        config_flow.PymodbusSerialTransport = FakeSerialTransport

    def tearDown(self) -> None:
        config_flow.PymodbusSerialTransport = self.original_transport

    def test_config_flow_version_matches_integration_version(self) -> None:
        self.assertEqual(
            config_flow.OpenWBConfigFlow.VERSION,
            const.CONFIG_ENTRY_VERSION,
        )

    async def test_shows_user_form(self) -> None:
        flow = config_flow.OpenWBConfigFlow()

        result = await flow.async_step_user()

        self.assertEqual(result["type"], "form")
        self.assertEqual(result["errors"], {})

    async def test_creates_bus_entry_with_defaults(self) -> None:
        flow = config_flow.OpenWBConfigFlow()

        result = await flow.async_step_user({const.CONF_SERIAL_PORT: " /dev/ttyUSB0 "})

        self.assertEqual(result["type"], "create_entry")
        self.assertEqual(result["title"], "openWB bus /dev/ttyUSB0")
        self.assertEqual(
            result["data"],
            {
                const.CONF_SERIAL_PORT: "/dev/ttyUSB0",
                const.CONF_BAUDRATE: 9600,
                const.CONF_PARITY: "N",
                const.CONF_STOPBITS: 2,
            },
        )
        self.assertEqual(flow._unique_id, "wb_mr6c_bus:/dev/ttyUSB0")
        self.assertEqual(FakeSerialTransport.instances[0].connect_calls, 1)
        self.assertEqual(FakeSerialTransport.instances[0].close_calls, 1)

    async def test_creates_bus_entry_with_user_values(self) -> None:
        flow = config_flow.OpenWBConfigFlow()

        result = await flow.async_step_user(
            {
                const.CONF_SERIAL_PORT: "/dev/ttyUSB1",
                const.CONF_BAUDRATE: "19200",
                const.CONF_PARITY: "e",
                const.CONF_STOPBITS: "1",
            }
        )

        self.assertEqual(
            result["data"],
            {
                const.CONF_SERIAL_PORT: "/dev/ttyUSB1",
                const.CONF_BAUDRATE: 19200,
                const.CONF_PARITY: "E",
                const.CONF_STOPBITS: 1,
            },
        )
        self.assertEqual(flow._unique_id, "wb_mr6c_bus:/dev/ttyUSB1")
        transport = FakeSerialTransport.instances[0]
        self.assertEqual(transport.port, "/dev/ttyUSB1")
        self.assertEqual(transport.baudrate, 19200)
        self.assertEqual(transport.parity, "E")
        self.assertEqual(transport.stopbits, 1)

    async def test_duplicate_serial_port_aborts(self) -> None:
        flow = config_flow.OpenWBConfigFlow()
        flow._configured_unique_ids = {"wb_mr6c_bus:/dev/ttyUSB0"}

        with self.assertRaisesRegex(AbortFlow, "already_configured") as ctx:
            await flow.async_step_user({const.CONF_SERIAL_PORT: "/dev/ttyUSB0"})

        self.assertEqual(ctx.exception.reason, "already_configured")
        self.assertEqual(FakeSerialTransport.instances, [])

    async def test_connection_failure_returns_form_error(self) -> None:
        flow = config_flow.OpenWBConfigFlow()
        FakeSerialTransport.connect_error = config_flow.WBMR6CModbusConnectionError(
            "boom"
        )

        result = await flow.async_step_user({const.CONF_SERIAL_PORT: "/dev/ttyUSB0"})

        self.assertEqual(result["type"], "form")
        self.assertEqual(result["errors"], {"base": "cannot_connect"})
        self.assertEqual(FakeSerialTransport.instances[0].connect_calls, 1)
        self.assertEqual(FakeSerialTransport.instances[0].close_calls, 1)

    async def test_invalid_serial_settings_return_form_errors(self) -> None:
        flow = config_flow.OpenWBConfigFlow()

        result = await flow.async_step_user(
            {
                const.CONF_SERIAL_PORT: " ",
                const.CONF_BAUDRATE: 9600.5,
                const.CONF_PARITY: "x",
                const.CONF_STOPBITS: "3",
            }
        )
        self.assertEqual(FakeSerialTransport.instances, [])

        self.assertEqual(result["type"], "form")
        self.assertEqual(
            result["errors"],
            {
                const.CONF_SERIAL_PORT: "invalid_serial_port",
                const.CONF_BAUDRATE: "invalid_baudrate",
                const.CONF_PARITY: "invalid_parity",
                const.CONF_STOPBITS: "invalid_stopbits",
            },
        )


class SetupUnloadTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        FakeSerialTransport.instances = []
        FakeSerialTransport.connect_error = None
        self.original_transport = integration.PymodbusSerialTransport
        integration.PymodbusSerialTransport = FakeSerialTransport

    def tearDown(self) -> None:
        integration.PymodbusSerialTransport = self.original_transport

    async def test_setup_opens_serial_transport_and_stores_runtime_data(self) -> None:
        entry = StubConfigEntry(
            {
                const.CONF_SERIAL_PORT: "/dev/ttyUSB0",
                const.CONF_BAUDRATE: 115200,
                const.CONF_PARITY: "O",
                const.CONF_STOPBITS: 1,
            }
        )

        self.assertTrue(
            await integration.async_setup_entry(types.SimpleNamespace(), entry)
        )

        transport = FakeSerialTransport.instances[0]
        self.assertEqual(transport.port, "/dev/ttyUSB0")
        self.assertEqual(transport.baudrate, 115200)
        self.assertEqual(transport.parity, "O")
        self.assertEqual(transport.stopbits, 1)
        self.assertEqual(transport.connect_calls, 1)
        self.assertIs(entry.runtime_data.transport, transport)

    async def test_setup_returns_false_for_unsupported_entry_data(self) -> None:
        entry = StubConfigEntry({"device_id": 1})

        with self.assertLogs(integration.__name__, level="ERROR"):
            self.assertFalse(
                await integration.async_setup_entry(types.SimpleNamespace(), entry)
            )
        self.assertEqual(FakeSerialTransport.instances, [])

    async def test_setup_raises_not_ready_on_connect_failure(self) -> None:
        entry = StubConfigEntry(
            {
                const.CONF_SERIAL_PORT: "/dev/ttyUSB0",
                const.CONF_BAUDRATE: 9600,
                const.CONF_PARITY: "N",
                const.CONF_STOPBITS: 2,
            }
        )
        FakeSerialTransport.connect_error = integration.WBMR6CModbusConnectionError(
            "boom"
        )

        with self.assertRaises(ConfigEntryNotReady):
            await integration.async_setup_entry(types.SimpleNamespace(), entry)

    async def test_unload_closes_transport(self) -> None:
        entry = StubConfigEntry(
            {
                const.CONF_SERIAL_PORT: "/dev/ttyUSB0",
                const.CONF_BAUDRATE: 9600,
                const.CONF_PARITY: "N",
                const.CONF_STOPBITS: 2,
            }
        )
        await integration.async_setup_entry(types.SimpleNamespace(), entry)

        self.assertTrue(
            await integration.async_unload_entry(types.SimpleNamespace(), entry)
        )

        self.assertEqual(FakeSerialTransport.instances[0].close_calls, 1)


class MigrationTest(unittest.IsolatedAsyncioTestCase):
    async def test_migrates_existing_bus_entry_version(self) -> None:
        entry = StubConfigEntry(
            {
                const.CONF_SERIAL_PORT: "/dev/ttyUSB0",
                const.CONF_BAUDRATE: 9600,
                const.CONF_PARITY: "N",
                const.CONF_STOPBITS: 2,
            },
            version=1,
        )
        config_entries_manager = FakeConfigEntriesManager()
        hass = types.SimpleNamespace(config_entries=config_entries_manager)

        self.assertTrue(await integration.async_migrate_entry(hass, entry))
        self.assertEqual(entry.version, const.CONFIG_ENTRY_VERSION)
        self.assertEqual(
            config_entries_manager.updates,
            [(entry, {"version": const.CONFIG_ENTRY_VERSION})],
        )

    async def test_rejects_unsupported_legacy_entry(self) -> None:
        entry = StubConfigEntry({"device_id": 1}, version=1)

        with self.assertLogs(integration.__name__, level="ERROR"):
            self.assertFalse(
                await integration.async_migrate_entry(types.SimpleNamespace(), entry)
            )
        self.assertEqual(entry.version, 1)


if __name__ == "__main__":
    unittest.main()
