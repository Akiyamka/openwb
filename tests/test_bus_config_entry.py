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


class HomeAssistantError(Exception):
    """Stub Home Assistant user-facing exception."""


class UpdateFailed(Exception):
    """Stub Home Assistant coordinator update failure."""


class DataUpdateCoordinator:
    """Stub Home Assistant DataUpdateCoordinator."""

    def __init__(
        self,
        hass: Any,
        logger: Any,
        *,
        name: str,
        update_interval: Any | None = None,
        config_entry: Any | None = None,
        **kwargs: Any,
    ) -> None:
        self.hass = hass
        self.logger = logger
        self.name = name
        self.update_interval = update_interval
        self.config_entry = config_entry
        self.kwargs = kwargs
        self.data: Any = None
        self.async_config_entry_first_refresh_calls = 0
        self.async_request_refresh_calls = 0
        self.last_update_success = True
        self.listeners: list[Any] = []

    async def async_config_entry_first_refresh(self) -> None:
        self.async_config_entry_first_refresh_calls += 1
        self.data = await self._async_update_data()

    async def async_request_refresh(self) -> None:
        self.async_request_refresh_calls += 1
        self.data = await self._async_update_data()

    def async_add_listener(self, update_callback: Any) -> Any:
        self.listeners.append(update_callback)

        def remove_listener() -> None:
            self.listeners.remove(update_callback)

        return remove_listener


class CoordinatorEntity:
    """Stub Home Assistant CoordinatorEntity."""

    def __init__(self, coordinator: DataUpdateCoordinator) -> None:
        self.coordinator = coordinator
        self.async_write_ha_state_calls = 0

    @property
    def available(self) -> bool:
        return bool(getattr(self.coordinator, "last_update_success", True))

    def async_write_ha_state(self) -> None:
        self.async_write_ha_state_calls += 1

    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()


class SwitchEntity:
    """Stub Home Assistant SwitchEntity."""

    @property
    def unique_id(self) -> str | None:
        return getattr(self, "_attr_unique_id", None)

    @property
    def name(self) -> str | None:
        return getattr(self, "_attr_name", None)

    @property
    def device_info(self) -> dict[str, Any] | None:
        return getattr(self, "_attr_device_info", None)


def callback(func: Any) -> Any:
    """Stub Home Assistant callback decorator."""
    return func


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


class StubConfigSubentryFlow:
    def __init__(self) -> None:
        self.context = {"source": "user"}
        self._entry: StubConfigEntry | None = None

    @property
    def source(self) -> str:
        return self.context["source"]

    def _get_entry(self) -> StubConfigEntry:
        assert self._entry is not None
        return self._entry

    def async_create_entry(
        self,
        *,
        title: str | None = None,
        data: dict[str, Any],
        unique_id: str | None = None,
    ) -> dict[str, Any]:
        return {
            "type": "create_entry",
            "title": title,
            "data": data,
            "unique_id": unique_id,
        }

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


class StubConfigSubentry:
    def __init__(
        self,
        *,
        data: dict[str, Any],
        unique_id: str | None = None,
        subentry_type: str = "device",
        title: str = "Device",
    ) -> None:
        self.data = data
        self.unique_id = unique_id
        self.subentry_type = subentry_type
        self.title = title


class StubConfigEntry:
    def __init__(
        self,
        data: dict[str, Any],
        *,
        version: int = 2,
        subentries: dict[str, StubConfigSubentry] | None = None,
    ) -> None:
        self.data = data
        self.entry_id = "bus-entry"
        self.version = version
        self.subentries = subentries or {}
        self.update_listeners: list[Any] = []
        self.unload_callbacks: list[Any] = []

    def __class_getitem__(cls, item: object) -> type[StubConfigEntry]:
        return cls

    def add_update_listener(self, listener: Any) -> Any:
        self.update_listeners.append(listener)

        def remove_listener() -> None:
            self.update_listeners.remove(listener)

        return remove_listener

    def async_on_unload(self, callback: Any) -> None:
        self.unload_callbacks.append(callback)


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
    components = types.ModuleType("homeassistant.components")
    switch_component = types.ModuleType("homeassistant.components.switch")
    switch_component.SwitchEntity = SwitchEntity
    components.switch = switch_component

    config_entries = types.ModuleType("homeassistant.config_entries")
    config_entries.ConfigEntry = StubConfigEntry
    config_entries.ConfigFlow = StubConfigFlow
    config_entries.ConfigSubentryFlow = StubConfigSubentryFlow

    core = types.ModuleType("homeassistant.core")
    core.callback = callback
    core.HomeAssistant = type("HomeAssistant", (), {})

    data_entry_flow = types.ModuleType("homeassistant.data_entry_flow")
    data_entry_flow.FlowResult = dict[str, Any]
    data_entry_flow.AbortFlow = AbortFlow

    exceptions = types.ModuleType("homeassistant.exceptions")
    exceptions.ConfigEntryNotReady = ConfigEntryNotReady
    exceptions.HomeAssistantError = HomeAssistantError

    helpers = types.ModuleType("homeassistant.helpers")
    selector = types.ModuleType("homeassistant.helpers.selector")
    update_coordinator = types.ModuleType("homeassistant.helpers.update_coordinator")
    selector.TextSelector = TextSelector
    selector.TextSelectorType = TextSelectorType
    selector.SelectSelector = SelectSelector
    helpers.selector = selector
    update_coordinator.DataUpdateCoordinator = DataUpdateCoordinator
    update_coordinator.CoordinatorEntity = CoordinatorEntity
    update_coordinator.UpdateFailed = UpdateFailed
    helpers.update_coordinator = update_coordinator

    voluptuous = types.ModuleType("voluptuous")
    voluptuous.Schema = Schema
    voluptuous.Required = Required

    homeassistant.config_entries = config_entries
    homeassistant.components = components
    homeassistant.core = core
    homeassistant.data_entry_flow = data_entry_flow
    homeassistant.exceptions = exceptions
    homeassistant.helpers = helpers

    sys.modules["homeassistant"] = homeassistant
    sys.modules["homeassistant.components"] = components
    sys.modules["homeassistant.components.switch"] = switch_component
    sys.modules["homeassistant.config_entries"] = config_entries
    sys.modules["homeassistant.core"] = core
    sys.modules["homeassistant.data_entry_flow"] = data_entry_flow
    sys.modules["homeassistant.exceptions"] = exceptions
    sys.modules["homeassistant.helpers"] = helpers
    sys.modules["homeassistant.helpers.selector"] = selector
    sys.modules["homeassistant.helpers.update_coordinator"] = update_coordinator
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
    "homeassistant.components",
    "homeassistant.components.switch",
    "homeassistant.config_entries",
    "homeassistant.core",
    "homeassistant.data_entry_flow",
    "homeassistant.exceptions",
    "homeassistant.helpers",
    "homeassistant.helpers.selector",
    "homeassistant.helpers.update_coordinator",
    "voluptuous",
    "custom_components.openwb",
    "custom_components.openwb.config_flow",
    "custom_components.openwb.const",
    "custom_components.openwb.switch",
    "custom_components.openwb.wb_mr6c_modbus",
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
modbus = importlib.import_module("custom_components.openwb.wb_mr6c_modbus")
switch_platform = importlib.import_module("custom_components.openwb.switch")


class FakeSerialTransport:
    instances: list[FakeSerialTransport] = []
    connect_error: Exception | None = None
    initial_coils: dict[tuple[int, int], bool] = {}
    initial_discrete_inputs: dict[tuple[int, int], bool] = {}
    initial_holding_registers: dict[tuple[int, int], int] = {}
    initial_unavailable_devices: set[int] = set()

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
        self.coils = dict(FakeSerialTransport.initial_coils)
        self.discrete_inputs = dict(FakeSerialTransport.initial_discrete_inputs)
        self.holding_registers = dict(FakeSerialTransport.initial_holding_registers)
        self.unavailable_devices = set(FakeSerialTransport.initial_unavailable_devices)
        self.response_error_devices: set[int] = set()
        self.calls: list[tuple[str, int, int | bool, int]] = []
        self.connect_calls = 0
        self.close_calls = 0
        FakeSerialTransport.instances.append(self)

    async def connect(self) -> None:
        self.connect_calls += 1
        if FakeSerialTransport.connect_error is not None:
            raise FakeSerialTransport.connect_error

    async def close(self) -> None:
        self.close_calls += 1

    def set_coil(self, address: int, value: bool, *, device_id: int) -> None:
        self.coils[(device_id, address)] = bool(value)

    def set_discrete_input(
        self, address: int, value: bool, *, device_id: int
    ) -> None:
        self.discrete_inputs[(device_id, address)] = bool(value)

    def set_holding_register(self, address: int, value: int, *, device_id: int) -> None:
        self.holding_registers[(device_id, address)] = value

    async def read_coils(
        self, address: int, count: int, device_id: int
    ) -> list[bool]:
        self.calls.append(("read_coils", address, count, device_id))
        self._check_device(device_id)
        return [
            self.coils.get((device_id, address + offset), False)
            for offset in range(count)
        ]

    async def write_coil(self, address: int, value: bool, device_id: int) -> None:
        self.calls.append(("write_coil", address, value, device_id))
        self._check_device(device_id)
        self.coils[(device_id, address)] = bool(value)

    async def read_discrete_inputs(
        self, address: int, count: int, device_id: int
    ) -> list[bool]:
        self.calls.append(("read_discrete_inputs", address, count, device_id))
        self._check_device(device_id)
        return [
            self.discrete_inputs.get((device_id, address + offset), False)
            for offset in range(count)
        ]

    async def read_holding_registers(
        self, address: int, count: int, device_id: int
    ) -> list[int]:
        self.calls.append(("read_holding_registers", address, count, device_id))
        self._check_device(device_id)
        return [
            self.holding_registers.get((device_id, address + offset), 0)
            for offset in range(count)
        ]

    async def write_register(self, address: int, value: int, device_id: int) -> None:
        self.calls.append(("write_register", address, value, device_id))
        self._check_device(device_id)
        self.holding_registers[(device_id, address)] = value

    def _check_device(self, device_id: int) -> None:
        if device_id in self.unavailable_devices:
            raise integration.WBMR6CModbusConnectionError("device unavailable")
        if device_id in self.response_error_devices:
            raise modbus.WBMR6CModbusResponseError("device response error")


class FakeDeviceTransport:
    instances: list[FakeDeviceTransport] = []
    connect_error: Exception | None = None
    read_error: Exception | None = None

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.args = args
        self.kwargs = kwargs
        self.holding_registers: dict[tuple[int, int], int] = {}
        self.calls: list[tuple[str, int, int, int]] = []
        self.connect_calls = 0
        self.close_calls = 0
        self.connect_error = FakeDeviceTransport.connect_error
        self.read_error = FakeDeviceTransport.read_error
        FakeDeviceTransport.instances.append(self)

    async def connect(self) -> None:
        self.connect_calls += 1
        if self.connect_error is not None:
            raise self.connect_error

    async def close(self) -> None:
        self.close_calls += 1

    async def read_holding_registers(
        self, address: int, count: int, device_id: int
    ) -> list[int]:
        self.calls.append(("read_holding_registers", address, count, device_id))
        if self.read_error is not None:
            raise self.read_error
        return [
            self.holding_registers.get((device_id, address + offset), 0)
            for offset in range(count)
        ]

    async def read_coils(
        self, address: int, count: int, device_id: int
    ) -> list[bool]:
        raise NotImplementedError

    async def write_coil(self, address: int, value: bool, device_id: int) -> None:
        raise NotImplementedError

    async def read_discrete_inputs(
        self, address: int, count: int, device_id: int
    ) -> list[bool]:
        raise NotImplementedError

    async def write_register(self, address: int, value: int, device_id: int) -> None:
        raise NotImplementedError


def _set_device_identification(
    transport: FakeDeviceTransport,
    *,
    device_id: int,
    model: str = "WBMR6C",
    firmware_version: str = "1.24.0",
) -> None:
    _set_ascii_registers(
        transport,
        device_id=device_id,
        base_address=modbus.REG_MODEL_BASE,
        length=modbus.REG_MODEL_LENGTH,
        value=model,
    )
    _set_ascii_registers(
        transport,
        device_id=device_id,
        base_address=modbus.REG_FIRMWARE_VERSION_BASE,
        length=modbus.REG_FIRMWARE_VERSION_MAX_LENGTH,
        value=firmware_version,
    )


def _seed_serial_identification(
    *,
    device_id: int,
    model: str = "WBMR6C",
    firmware_version: str = "1.24.0",
) -> None:
    seed = types.SimpleNamespace(
        holding_registers=FakeSerialTransport.initial_holding_registers
    )
    _set_ascii_registers(
        seed,
        device_id=device_id,
        base_address=modbus.REG_MODEL_BASE,
        length=modbus.REG_MODEL_LENGTH,
        value=model,
    )
    _set_ascii_registers(
        seed,
        device_id=device_id,
        base_address=modbus.REG_FIRMWARE_VERSION_BASE,
        length=modbus.REG_FIRMWARE_VERSION_MAX_LENGTH,
        value=firmware_version,
    )


def _set_ascii_registers(
    transport: Any,
    *,
    device_id: int,
    base_address: int,
    length: int,
    value: str,
) -> None:
    for offset in range(length):
        register_value = ord(value[offset]) if offset < len(value) else 0
        transport.holding_registers[(device_id, base_address + offset)] = (
            register_value
        )


def _bus_entry(
    *,
    serial_port: str = "/dev/ttyUSB0",
    transport: FakeDeviceTransport | None = None,
    subentries: dict[str, StubConfigSubentry] | None = None,
) -> StubConfigEntry:
    entry = StubConfigEntry(
        {
            const.CONF_SERIAL_PORT: serial_port,
            const.CONF_BAUDRATE: 9600,
            const.CONF_PARITY: "N",
            const.CONF_STOPBITS: 2,
        },
        subentries=subentries,
    )
    if transport is not None:
        entry.runtime_data = types.SimpleNamespace(transport=transport)
    return entry


def _device_subentry(
    device_id: int,
    *,
    firmware_version: str = "1.16.9",
    model: str = const.MODEL_WB_MR6C_V2,
) -> StubConfigSubentry:
    return StubConfigSubentry(
        data={
            const.CONF_DEVICE_ID: device_id,
            const.CONF_MODEL: model,
            const.CONF_FIRMWARE_VERSION: firmware_version,
        },
        unique_id=f"/dev/ttyUSB0:{device_id}",
    )


def _device_flow(entry: StubConfigEntry) -> config_flow.OpenWBDeviceSubentryFlow:
    flow = config_flow.OpenWBDeviceSubentryFlow()
    flow._entry = entry
    return flow


class FakeConfigEntriesManager:
    def __init__(self) -> None:
        self.updates: list[tuple[StubConfigEntry, dict[str, Any]]] = []
        self.reloads: list[str] = []
        self.forwarded_entry_setups: list[tuple[StubConfigEntry, tuple[str, ...]]] = []
        self.unloaded_platforms: list[tuple[StubConfigEntry, tuple[str, ...]]] = []
        self.unload_platforms_result = True

    def async_update_entry(
        self, entry: StubConfigEntry, **kwargs: Any
    ) -> None:
        self.updates.append((entry, kwargs))
        if "version" in kwargs:
            entry.version = kwargs["version"]

    async def async_reload(self, entry_id: str) -> None:
        self.reloads.append(entry_id)

    async def async_forward_entry_setups(
        self, entry: StubConfigEntry, platforms: tuple[str, ...]
    ) -> None:
        self.forwarded_entry_setups.append((entry, tuple(platforms)))

    async def async_unload_platforms(
        self, entry: StubConfigEntry, platforms: tuple[str, ...]
    ) -> bool:
        self.unloaded_platforms.append((entry, tuple(platforms)))
        return self.unload_platforms_result


def _hass() -> types.SimpleNamespace:
    return types.SimpleNamespace(config_entries=FakeConfigEntriesManager())


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


class DeviceSubentryFlowTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        FakeDeviceTransport.instances = []
        FakeDeviceTransport.connect_error = None
        FakeDeviceTransport.read_error = None

    def test_bus_flow_reports_supported_device_subentry_type(self) -> None:
        entry = _bus_entry()

        supported_types = config_flow.OpenWBConfigFlow.async_get_supported_subentry_types(
            entry
        )

        self.assertIs(
            supported_types[const.SUBENTRY_TYPE_DEVICE],
            config_flow.OpenWBDeviceSubentryFlow,
        )

    async def test_device_subentry_creates_entry_after_identification_read(
        self,
    ) -> None:
        transport = FakeDeviceTransport()
        _set_device_identification(transport, device_id=32)
        flow = _device_flow(_bus_entry(transport=transport))

        result = await flow.async_step_user({const.CONF_DEVICE_ID: "32"})

        self.assertEqual(result["type"], "create_entry")
        self.assertEqual(result["title"], "WB-MR6C 32")
        self.assertEqual(result["unique_id"], "/dev/ttyUSB0:32")
        self.assertEqual(
            result["data"],
            {
                const.CONF_DEVICE_ID: 32,
                const.CONF_MODEL: const.MODEL_WB_MR6C_V2,
                const.CONF_FIRMWARE_VERSION: "1.24.0",
            },
        )
        self.assertEqual(
            transport.calls,
            [
                ("read_holding_registers", modbus.REG_MODEL_BASE, 6, 32),
                (
                    "read_holding_registers",
                    modbus.REG_FIRMWARE_VERSION_BASE,
                    16,
                    32,
                ),
            ],
        )

    async def test_invalid_device_id_returns_form_error(self) -> None:
        transport = FakeDeviceTransport()
        flow = _device_flow(_bus_entry(transport=transport))

        for invalid_device_id in ("0", "248", "not-a-number", True):
            result = await flow.async_step_user(
                {const.CONF_DEVICE_ID: invalid_device_id}
            )
            self.assertEqual(result["type"], "form")
            self.assertEqual(
                result["errors"], {const.CONF_DEVICE_ID: "invalid_device_id"}
            )

        self.assertEqual(transport.calls, [])

    async def test_duplicate_device_id_on_same_bus_is_rejected_before_read(
        self,
    ) -> None:
        transport = FakeDeviceTransport()
        entry = _bus_entry(
            transport=transport,
            subentries={
                "existing": StubConfigSubentry(
                    data={const.CONF_DEVICE_ID: 32},
                    unique_id="/dev/ttyUSB0:32",
                )
            },
        )
        flow = _device_flow(entry)

        result = await flow.async_step_user({const.CONF_DEVICE_ID: "32"})

        self.assertEqual(result["type"], "form")
        self.assertEqual(
            result["errors"], {const.CONF_DEVICE_ID: "duplicate_device_id"}
        )
        self.assertEqual(transport.calls, [])

    async def test_wrong_model_returns_form_error(self) -> None:
        transport = FakeDeviceTransport()
        _set_device_identification(transport, device_id=32, model="NOTMR6")
        flow = _device_flow(_bus_entry(transport=transport))

        result = await flow.async_step_user({const.CONF_DEVICE_ID: "32"})

        self.assertEqual(result["type"], "form")
        self.assertEqual(result["errors"], {"base": "unexpected_model"})

    async def test_transport_read_failure_returns_form_error(self) -> None:
        transport = FakeDeviceTransport()
        transport.read_error = config_flow.WBMR6CModbusConnectionError("boom")
        flow = _device_flow(_bus_entry(transport=transport))

        result = await flow.async_step_user({const.CONF_DEVICE_ID: "32"})

        self.assertEqual(result["type"], "form")
        self.assertEqual(result["errors"], {"base": "cannot_connect"})

    async def test_transport_response_failure_returns_form_error(self) -> None:
        transport = FakeDeviceTransport()
        transport.read_error = config_flow.WBMR6CModbusResponseError("short")
        flow = _device_flow(_bus_entry(transport=transport))

        result = await flow.async_step_user({const.CONF_DEVICE_ID: "32"})

        self.assertEqual(result["type"], "form")
        self.assertEqual(result["errors"], {"base": "cannot_validate_device"})

    async def test_transport_connect_failure_returns_form_error(self) -> None:
        original_transport = config_flow.PymodbusSerialTransport
        config_flow.PymodbusSerialTransport = FakeDeviceTransport
        FakeDeviceTransport.connect_error = config_flow.WBMR6CModbusConnectionError(
            "boom"
        )
        flow = _device_flow(_bus_entry())

        try:
            result = await flow.async_step_user({const.CONF_DEVICE_ID: "32"})
        finally:
            config_flow.PymodbusSerialTransport = original_transport

        self.assertEqual(result["type"], "form")
        self.assertEqual(result["errors"], {"base": "cannot_connect"})
        self.assertEqual(FakeDeviceTransport.instances[0].connect_calls, 1)
        self.assertEqual(FakeDeviceTransport.instances[0].close_calls, 1)

    async def test_same_device_id_on_different_bus_is_allowed(self) -> None:
        transport = FakeDeviceTransport()
        _set_device_identification(transport, device_id=32)
        entry = _bus_entry(serial_port="/dev/ttyUSB1", transport=transport)
        flow = _device_flow(entry)

        result = await flow.async_step_user({const.CONF_DEVICE_ID: "32"})

        self.assertEqual(result["type"], "create_entry")
        self.assertEqual(result["unique_id"], "/dev/ttyUSB1:32")


class SetupUnloadTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        FakeSerialTransport.instances = []
        FakeSerialTransport.connect_error = None
        FakeSerialTransport.initial_coils = {}
        FakeSerialTransport.initial_discrete_inputs = {}
        FakeSerialTransport.initial_holding_registers = {}
        FakeSerialTransport.initial_unavailable_devices = set()
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
        hass = _hass()

        self.assertTrue(await integration.async_setup_entry(hass, entry))

        transport = FakeSerialTransport.instances[0]
        self.assertEqual(transport.port, "/dev/ttyUSB0")
        self.assertEqual(transport.baudrate, 115200)
        self.assertEqual(transport.parity, "O")
        self.assertEqual(transport.stopbits, 1)
        self.assertEqual(transport.connect_calls, 1)
        self.assertIs(entry.runtime_data.transport, transport)
        self.assertIsInstance(
            entry.runtime_data.coordinator,
            integration.WBMR6CBusCoordinator,
        )
        self.assertEqual(entry.runtime_data.clients, {})
        self.assertEqual(entry.runtime_data.coordinator.data, {})
        self.assertEqual(
            entry.runtime_data.coordinator.listeners,
            [integration._noop_coordinator_listener],
        )
        self.assertEqual(entry.update_listeners, [integration._async_reload_entry])
        self.assertEqual(len(entry.unload_callbacks), 1)
        self.assertEqual(
            hass.config_entries.forwarded_entry_setups,
            [(entry, ("switch",))],
        )

    async def test_setup_creates_shared_transport_and_clients_per_subentry(
        self,
    ) -> None:
        entry = StubConfigEntry(
            {
                const.CONF_SERIAL_PORT: "/dev/ttyUSB0",
                const.CONF_BAUDRATE: 9600,
                const.CONF_PARITY: "N",
                const.CONF_STOPBITS: 2,
            },
            subentries={
                "device-32": _device_subentry(32),
                "device-33": _device_subentry(33),
            },
        )

        self.assertTrue(
            await integration.async_setup_entry(_hass(), entry)
        )

        transport = FakeSerialTransport.instances[0]
        runtime = entry.runtime_data
        self.assertIs(runtime.transport, transport)
        self.assertEqual(set(runtime.clients), {32, 33})
        self.assertIs(runtime.clients[32].transport, transport)
        self.assertIs(runtime.clients[33].transport, transport)
        self.assertEqual(set(runtime.coordinator.data), {32, 33})
        self.assertEqual(
            transport.calls,
            [
                ("read_holding_registers", modbus.REG_MODEL_BASE, 6, 32),
                (
                    "read_holding_registers",
                    modbus.REG_FIRMWARE_VERSION_BASE,
                    16,
                    32,
                ),
                ("read_holding_registers", modbus.REG_MODEL_BASE, 6, 33),
                (
                    "read_holding_registers",
                    modbus.REG_FIRMWARE_VERSION_BASE,
                    16,
                    33,
                ),
                ("read_discrete_inputs", modbus.DISCRETE_INPUT_STATE_BASE, 8, 32),
                ("read_coils", modbus.COIL_RELAY_COMMAND_BASE, 6, 32),
                ("read_discrete_inputs", modbus.DISCRETE_INPUT_STATE_BASE, 8, 33),
                ("read_coils", modbus.COIL_RELAY_COMMAND_BASE, 6, 33),
            ],
        )

    async def test_setup_refreshes_stale_subentry_metadata(self) -> None:
        _seed_serial_identification(device_id=32, firmware_version="1.24.0")
        entry = StubConfigEntry(
            {
                const.CONF_SERIAL_PORT: "/dev/ttyUSB0",
                const.CONF_BAUDRATE: 9600,
                const.CONF_PARITY: "N",
                const.CONF_STOPBITS: 2,
            },
            subentries={"device-32": _device_subentry(32, firmware_version="1.16.9")},
        )

        await integration.async_setup_entry(_hass(), entry)

        metadata = entry.runtime_data.device_metadata[32]
        self.assertEqual(metadata.model, "WBMR6C")
        self.assertEqual(metadata.firmware_version, "1.24.0")
        self.assertTrue(metadata.supports_press_counters)
        self.assertTrue(metadata.supports_relay_state_discrete_inputs)

    async def test_coordinator_omits_failed_device_and_keeps_other_devices(
        self,
    ) -> None:
        entry = StubConfigEntry(
            {
                const.CONF_SERIAL_PORT: "/dev/ttyUSB0",
                const.CONF_BAUDRATE: 9600,
                const.CONF_PARITY: "N",
                const.CONF_STOPBITS: 2,
            },
            subentries={
                "device-32": _device_subentry(32),
                "device-33": _device_subentry(33),
            },
        )
        await integration.async_setup_entry(_hass(), entry)
        transport = FakeSerialTransport.instances[0]
        transport.calls.clear()
        transport.unavailable_devices.add(33)

        await entry.runtime_data.coordinator.async_request_refresh()

        self.assertEqual(set(entry.runtime_data.coordinator.data), {32})
        self.assertEqual(
            transport.calls,
            [
                ("read_discrete_inputs", modbus.DISCRETE_INPUT_STATE_BASE, 8, 32),
                ("read_coils", modbus.COIL_RELAY_COMMAND_BASE, 6, 32),
                ("read_discrete_inputs", modbus.DISCRETE_INPUT_STATE_BASE, 8, 33),
            ],
        )

    async def test_coordinator_fails_when_all_devices_have_connection_errors(
        self,
    ) -> None:
        entry = StubConfigEntry(
            {
                const.CONF_SERIAL_PORT: "/dev/ttyUSB0",
                const.CONF_BAUDRATE: 9600,
                const.CONF_PARITY: "N",
                const.CONF_STOPBITS: 2,
            },
            subentries={
                "device-32": _device_subentry(32),
                "device-33": _device_subentry(33),
            },
        )
        await integration.async_setup_entry(_hass(), entry)
        transport = FakeSerialTransport.instances[0]
        transport.calls.clear()
        transport.unavailable_devices.update({32, 33})

        with self.assertRaises(UpdateFailed):
            await entry.runtime_data.coordinator.async_request_refresh()

    async def test_setup_failure_closes_transport_and_removes_listener(self) -> None:
        FakeSerialTransport.initial_unavailable_devices = {32, 33}
        entry = StubConfigEntry(
            {
                const.CONF_SERIAL_PORT: "/dev/ttyUSB0",
                const.CONF_BAUDRATE: 9600,
                const.CONF_PARITY: "N",
                const.CONF_STOPBITS: 2,
            },
            subentries={
                "device-32": _device_subentry(32),
                "device-33": _device_subentry(33),
            },
        )

        with self.assertRaises(UpdateFailed):
            await integration.async_setup_entry(_hass(), entry)

        transport = FakeSerialTransport.instances[0]
        self.assertEqual(transport.close_calls, 1)
        self.assertEqual(entry.runtime_data.coordinator.listeners, [])
        self.assertEqual(entry.update_listeners, [])

    async def test_entry_update_listener_reloads_bus_entry(self) -> None:
        entry = StubConfigEntry(
            {
                const.CONF_SERIAL_PORT: "/dev/ttyUSB0",
                const.CONF_BAUDRATE: 9600,
                const.CONF_PARITY: "N",
                const.CONF_STOPBITS: 2,
            }
        )
        await integration.async_setup_entry(_hass(), entry)
        config_entries_manager = FakeConfigEntriesManager()
        hass = types.SimpleNamespace(config_entries=config_entries_manager)

        await entry.update_listeners[0](hass, entry)

        self.assertEqual(config_entries_manager.reloads, ["bus-entry"])

    async def test_old_firmware_omits_press_counters(self) -> None:
        entry = StubConfigEntry(
            {
                const.CONF_SERIAL_PORT: "/dev/ttyUSB0",
                const.CONF_BAUDRATE: 9600,
                const.CONF_PARITY: "N",
                const.CONF_STOPBITS: 2,
            },
            subentries={"device-32": _device_subentry(32, firmware_version="1.16.9")},
        )

        await integration.async_setup_entry(_hass(), entry)

        state = entry.runtime_data.coordinator.data[32]
        self.assertEqual(state.press_counts, {})
        self.assertNotIn(
            ("read_holding_registers", modbus.REG_PRESS_COUNTER_SHORT_BASE, 8, 32),
            FakeSerialTransport.instances[0].calls,
        )

    async def test_old_firmware_falls_back_relay_states_to_command_coils(
        self,
    ) -> None:
        entry = StubConfigEntry(
            {
                const.CONF_SERIAL_PORT: "/dev/ttyUSB0",
                const.CONF_BAUDRATE: 9600,
                const.CONF_PARITY: "N",
                const.CONF_STOPBITS: 2,
            },
            subentries={"device-32": _device_subentry(32, firmware_version="1.23.9")},
        )
        await integration.async_setup_entry(_hass(), entry)
        transport = FakeSerialTransport.instances[0]
        transport.calls.clear()
        transport.set_coil(modbus.COIL_RELAY_COMMAND_BASE, True, device_id=32)
        transport.set_discrete_input(
            modbus.DISCRETE_RELAY_STATE_BASE,
            False,
            device_id=32,
        )

        await entry.runtime_data.coordinator.async_request_refresh()

        state = entry.runtime_data.coordinator.data[32]
        self.assertTrue(state.relay_commands[1])
        self.assertTrue(state.relay_states[1])
        self.assertNotIn(
            ("read_discrete_inputs", modbus.DISCRETE_RELAY_STATE_BASE, 6, 32),
            transport.calls,
        )

    async def test_new_firmware_reads_actual_relay_states_and_press_counters(
        self,
    ) -> None:
        entry = StubConfigEntry(
            {
                const.CONF_SERIAL_PORT: "/dev/ttyUSB0",
                const.CONF_BAUDRATE: 9600,
                const.CONF_PARITY: "N",
                const.CONF_STOPBITS: 2,
            },
            subentries={"device-32": _device_subentry(32, firmware_version="1.24.0")},
        )
        await integration.async_setup_entry(_hass(), entry)
        transport = FakeSerialTransport.instances[0]
        transport.calls.clear()
        transport.set_coil(modbus.COIL_RELAY_COMMAND_BASE, False, device_id=32)
        transport.set_discrete_input(
            modbus.DISCRETE_RELAY_STATE_BASE,
            True,
            device_id=32,
        )
        transport.set_holding_register(
            modbus.REG_PRESS_COUNTER_SHORT_BASE,
            7,
            device_id=32,
        )

        await entry.runtime_data.coordinator.async_request_refresh()

        state = entry.runtime_data.coordinator.data[32]
        self.assertFalse(state.relay_commands[1])
        self.assertTrue(state.relay_states[1])
        self.assertEqual(state.press_counts[(1, "short")], 7)
        self.assertIn(
            ("read_discrete_inputs", modbus.DISCRETE_RELAY_STATE_BASE, 6, 32),
            transport.calls,
        )

    async def test_setup_returns_false_for_unsupported_entry_data(self) -> None:
        entry = StubConfigEntry({"device_id": 1})

        with self.assertLogs(integration.__name__, level="ERROR"):
            self.assertFalse(
                await integration.async_setup_entry(_hass(), entry)
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
            await integration.async_setup_entry(_hass(), entry)

    async def test_unload_closes_transport(self) -> None:
        entry = StubConfigEntry(
            {
                const.CONF_SERIAL_PORT: "/dev/ttyUSB0",
                const.CONF_BAUDRATE: 9600,
                const.CONF_PARITY: "N",
                const.CONF_STOPBITS: 2,
            }
        )
        hass = _hass()
        await integration.async_setup_entry(hass, entry)
        coordinator = entry.runtime_data.coordinator
        self.assertEqual(coordinator.listeners, [integration._noop_coordinator_listener])

        self.assertTrue(await integration.async_unload_entry(hass, entry))

        self.assertEqual(FakeSerialTransport.instances[0].close_calls, 1)
        self.assertEqual(coordinator.listeners, [])
        self.assertEqual(
            hass.config_entries.unloaded_platforms,
            [(entry, ("switch",))],
        )


class FakeSwitchCoordinator:
    def __init__(self, data: dict[int, integration.WBMR6CDeviceState]) -> None:
        self.data = data
        self.last_update_success = True
        self.async_request_refresh_calls = 0

    async def async_request_refresh(self) -> None:
        self.async_request_refresh_calls += 1


class FakeRelayClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []
        self.error: Exception | None = None

    async def turn_on(self, output: int) -> None:
        await self._call("turn_on", output)

    async def turn_off(self, output: int) -> None:
        await self._call("turn_off", output)

    async def toggle(self, output: int) -> None:
        await self._call("toggle", output)

    async def _call(self, method: str, output: int) -> None:
        if self.error is not None:
            raise self.error
        self.calls.append((method, output))


def _metadata(
    *, model: str | None = "WBMR6C", firmware_version: str | None = "1.24.0"
) -> integration.WBMR6CDeviceMetadata:
    return integration.WBMR6CDeviceMetadata(
        model=model,
        firmware_version=firmware_version,
        supports_press_counters=True,
        supports_relay_state_discrete_inputs=True,
    )


def _device_state(
    relay_states: dict[int, bool] | None = None,
) -> integration.WBMR6CDeviceState:
    return integration.WBMR6CDeviceState(
        input_states={},
        press_counts={},
        relay_states=dict(relay_states or {}),
        relay_commands={},
    )


def _switch_entry(
    *,
    serial_port: str = "/dev/ttyUSB0",
    device_id: int = 32,
    relay_states: dict[int, bool] | None = None,
) -> tuple[StubConfigEntry, FakeRelayClient, FakeSwitchCoordinator]:
    entry = _bus_entry(
        serial_port=serial_port,
        subentries={"device-32": _device_subentry(device_id)},
    )
    client = FakeRelayClient()
    coordinator = FakeSwitchCoordinator({device_id: _device_state(relay_states)})
    entry.runtime_data = types.SimpleNamespace(
        coordinator=coordinator,
        clients={device_id: client},
        device_metadata={device_id: _metadata()},
    )
    return entry, client, coordinator


def _relay_switch(
    *,
    serial_port: str = "/dev/ttyUSB0",
    device_id: int = 32,
    output: int = 1,
    relay_states: dict[int, bool] | None = None,
) -> tuple[
    switch_platform.OpenWBRelaySwitch,
    FakeRelayClient,
    FakeSwitchCoordinator,
]:
    entry, client, coordinator = _switch_entry(
        serial_port=serial_port,
        device_id=device_id,
        relay_states=relay_states,
    )
    entity = switch_platform.OpenWBRelaySwitch(
        entry=entry,
        client=client,
        serial_port=serial_port,
        device_id=device_id,
        output=output,
        metadata=_metadata(),
    )
    return entity, client, coordinator


class SwitchPlatformTest(unittest.IsolatedAsyncioTestCase):
    async def test_setup_creates_six_relay_switches_per_device_subentry(self) -> None:
        entry = _bus_entry(
            subentries={
                "subentry-32": _device_subentry(32),
                "subentry-33": _device_subentry(33),
            }
        )
        clients = {32: FakeRelayClient(), 33: FakeRelayClient()}
        entry.runtime_data = types.SimpleNamespace(
            coordinator=FakeSwitchCoordinator(
                {
                    32: _device_state({output: False for output in modbus.OUTPUTS}),
                    33: _device_state({output: False for output in modbus.OUTPUTS}),
                }
            ),
            clients=clients,
            device_metadata={32: _metadata(), 33: _metadata()},
        )
        add_calls: list[tuple[list[Any], dict[str, Any]]] = []

        def async_add_entities(entities: list[Any], **kwargs: Any) -> None:
            add_calls.append((entities, kwargs))

        await switch_platform.async_setup_entry(
            types.SimpleNamespace(), entry, async_add_entities
        )

        self.assertEqual(len(add_calls), 2)
        self.assertEqual([len(entities) for entities, _ in add_calls], [6, 6])
        self.assertEqual(
            [kwargs["config_subentry_id"] for _, kwargs in add_calls],
            ["subentry-32", "subentry-33"],
        )
        unique_ids = [
            entity.unique_id for entities, _ in add_calls for entity in entities
        ]
        self.assertIn("/dev/ttyUSB0:32:relay_1", unique_ids)
        self.assertIn("/dev/ttyUSB0:33:relay_6", unique_ids)
        self.assertEqual(len(set(unique_ids)), 12)
        self.assertEqual(
            add_calls[0][0][0].device_info,
            {
                "identifiers": {(const.DOMAIN, "/dev/ttyUSB0:32")},
                "manufacturer": "Wiren Board",
                "model": "WBMR6C",
                "name": "WB-MR6C 32",
                "sw_version": "1.24.0",
            },
        )

    async def test_is_on_reads_coordinator_data_without_client_io(self) -> None:
        entity, client, _coordinator = _relay_switch(
            output=2,
            relay_states={2: True},
        )

        self.assertTrue(entity.is_on)
        self.assertEqual(client.calls, [])

    async def test_unavailable_when_device_or_output_missing_from_data(self) -> None:
        entity, _client, coordinator = _relay_switch(
            output=2,
            relay_states={2: True},
        )

        self.assertTrue(entity.available)

        coordinator.data = {}
        self.assertFalse(entity.available)
        self.assertIsNone(entity.is_on)

        coordinator.data = {32: _device_state({1: True})}
        self.assertFalse(entity.available)
        self.assertIsNone(entity.is_on)

    async def test_turn_on_and_off_call_backend_and_set_optimistic_state(self) -> None:
        entity, client, coordinator = _relay_switch(
            output=3,
            relay_states={3: False},
        )

        await entity.async_turn_on()

        self.assertEqual(client.calls, [("turn_on", 3)])
        self.assertTrue(entity.is_on)
        self.assertEqual(entity.async_write_ha_state_calls, 1)
        self.assertEqual(coordinator.async_request_refresh_calls, 0)

        await entity.async_turn_off()

        self.assertEqual(client.calls, [("turn_on", 3), ("turn_off", 3)])
        self.assertFalse(entity.is_on)
        self.assertEqual(entity.async_write_ha_state_calls, 2)
        self.assertEqual(coordinator.async_request_refresh_calls, 0)

    async def test_toggle_calls_backend_and_sets_optimistic_inverse(self) -> None:
        entity, client, coordinator = _relay_switch(
            output=4,
            relay_states={4: False},
        )

        await entity.async_toggle()

        self.assertEqual(client.calls, [("toggle", 4)])
        self.assertTrue(entity.is_on)
        self.assertEqual(entity.async_write_ha_state_calls, 1)
        self.assertEqual(coordinator.async_request_refresh_calls, 0)

    async def test_coordinator_update_clears_optimistic_state(self) -> None:
        entity, _client, coordinator = _relay_switch(
            output=3,
            relay_states={3: False},
        )

        await entity.async_turn_on()
        coordinator.data = {32: _device_state({3: False})}
        entity._handle_coordinator_update()

        self.assertFalse(entity.is_on)

    async def test_write_failure_raises_home_assistant_error(self) -> None:
        entity, client, coordinator = _relay_switch(
            output=3,
            relay_states={3: False},
        )
        client.error = modbus.WBMR6CModbusConnectionError("boom")

        with self.assertRaises(HomeAssistantError):
            await entity.async_turn_on()

        self.assertFalse(entity.is_on)
        self.assertEqual(entity.async_write_ha_state_calls, 0)
        self.assertEqual(coordinator.async_request_refresh_calls, 0)

    async def test_unique_ids_include_bus_device_and_output(self) -> None:
        first, _client, _coordinator = _relay_switch(
            serial_port="/dev/ttyUSB0",
            device_id=32,
            output=1,
            relay_states={1: False},
        )
        second, _client, _coordinator = _relay_switch(
            serial_port="/dev/ttyUSB1",
            device_id=32,
            output=1,
            relay_states={1: False},
        )

        self.assertEqual(first.unique_id, "/dev/ttyUSB0:32:relay_1")
        self.assertEqual(second.unique_id, "/dev/ttyUSB1:32:relay_1")
        self.assertNotEqual(first.unique_id, second.unique_id)


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
                await integration.async_migrate_entry(_hass(), entry)
            )
        self.assertEqual(entry.version, 1)


if __name__ == "__main__":
    unittest.main()
