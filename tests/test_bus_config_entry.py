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

    def __class_getitem__(cls, item: object) -> type[DataUpdateCoordinator]:
        return cls

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

    def __class_getitem__(cls, item: object) -> type[CoordinatorEntity]:
        return cls

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


class BinarySensorEntity:
    """Stub Home Assistant BinarySensorEntity."""

    @property
    def unique_id(self) -> str | None:
        return getattr(self, "_attr_unique_id", None)

    @property
    def name(self) -> str | None:
        return getattr(self, "_attr_name", None)

    @property
    def device_info(self) -> dict[str, Any] | None:
        return getattr(self, "_attr_device_info", None)


class EventEntity:
    """Stub Home Assistant EventEntity."""

    @property
    def unique_id(self) -> str | None:
        return getattr(self, "_attr_unique_id", None)

    @property
    def name(self) -> str | None:
        return getattr(self, "_attr_name", None)

    @property
    def event_types(self) -> list[str] | None:
        return getattr(self, "_attr_event_types", None)

    @property
    def device_info(self) -> dict[str, Any] | None:
        return getattr(self, "_attr_device_info", None)

    def _trigger_event(
        self, event_type: str, event_attributes: dict[str, Any] | None = None
    ) -> None:
        triggered_events = getattr(self, "triggered_events", None)
        if triggered_events is None:
            triggered_events = []
            self.triggered_events = triggered_events
        triggered_events.append((event_type, event_attributes or {}))


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


class TextSelectorConfig:
    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs


class SelectSelector:
    def __init__(self, config: object | None = None) -> None:
        self.config = config


class SelectSelectorConfig:
    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs


class TextSelectorType:
    NUMBER = "number"


def _install_homeassistant_stubs() -> None:
    homeassistant = types.ModuleType("homeassistant")
    components = types.ModuleType("homeassistant.components")
    binary_sensor_component = types.ModuleType("homeassistant.components.binary_sensor")
    binary_sensor_component.BinarySensorEntity = BinarySensorEntity
    event_component = types.ModuleType("homeassistant.components.event")
    event_component.EventEntity = EventEntity
    switch_component = types.ModuleType("homeassistant.components.switch")
    switch_component.SwitchEntity = SwitchEntity
    components.binary_sensor = binary_sensor_component
    components.event = event_component
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
    device_registry = types.ModuleType("homeassistant.helpers.device_registry")
    entity_platform = types.ModuleType("homeassistant.helpers.entity_platform")
    selector = types.ModuleType("homeassistant.helpers.selector")
    update_coordinator = types.ModuleType("homeassistant.helpers.update_coordinator")
    device_registry.DeviceInfo = dict[str, Any]
    entity_platform.AddConfigEntryEntitiesCallback = Any
    selector.TextSelector = TextSelector
    selector.TextSelectorConfig = TextSelectorConfig
    selector.TextSelectorType = TextSelectorType
    selector.SelectSelector = SelectSelector
    selector.SelectSelectorConfig = SelectSelectorConfig
    helpers.device_registry = device_registry
    helpers.entity_platform = entity_platform
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
    sys.modules["homeassistant.components.binary_sensor"] = binary_sensor_component
    sys.modules["homeassistant.components.event"] = event_component
    sys.modules["homeassistant.components.switch"] = switch_component
    sys.modules["homeassistant.config_entries"] = config_entries
    sys.modules["homeassistant.core"] = core
    sys.modules["homeassistant.data_entry_flow"] = data_entry_flow
    sys.modules["homeassistant.exceptions"] = exceptions
    sys.modules["homeassistant.helpers"] = helpers
    sys.modules["homeassistant.helpers.device_registry"] = device_registry
    sys.modules["homeassistant.helpers.entity_platform"] = entity_platform
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
    "homeassistant.components.binary_sensor",
    "homeassistant.components.event",
    "homeassistant.components.switch",
    "homeassistant.config_entries",
    "homeassistant.core",
    "homeassistant.data_entry_flow",
    "homeassistant.exceptions",
    "homeassistant.helpers",
    "homeassistant.helpers.device_registry",
    "homeassistant.helpers.entity_platform",
    "homeassistant.helpers.selector",
    "homeassistant.helpers.update_coordinator",
    "voluptuous",
    "custom_components.openwb",
    "custom_components.openwb.binary_sensor",
    "custom_components.openwb.config_flow",
    "custom_components.openwb.const",
    "custom_components.openwb.event",
    "custom_components.openwb.mapping_matrix",
    "custom_components.openwb.settings",
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
binary_sensor_platform = importlib.import_module("custom_components.openwb.binary_sensor")
config_flow = importlib.import_module("custom_components.openwb.config_flow")
const = importlib.import_module("custom_components.openwb.const")
event_platform = importlib.import_module("custom_components.openwb.event")
modbus = importlib.import_module("custom_components.openwb.wb_mr6c_modbus")
switch_platform = importlib.import_module("custom_components.openwb.switch")


class FakeSerialTransport:
    instances: list[FakeSerialTransport] = []
    connect_error: Exception | None = None
    initial_coils: dict[tuple[int, int], bool] = {}
    initial_discrete_inputs: dict[tuple[int, int], bool] = {}
    initial_holding_registers: dict[tuple[int, int], int] = {}
    initial_input_registers: dict[tuple[int, int], int] = {}
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
        self.input_registers = dict(FakeSerialTransport.initial_input_registers)
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

    def set_input_register(self, address: int, value: int, *, device_id: int) -> None:
        self.input_registers[(device_id, address)] = value

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

    async def read_input_registers(
        self, address: int, count: int, device_id: int
    ) -> list[int]:
        self.calls.append(("read_input_registers", address, count, device_id))
        self._check_device(device_id)
        return [
            self.input_registers.get((device_id, address + offset), 0)
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
        self.input_registers: dict[tuple[int, int], int] = {}
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

    async def read_input_registers(
        self, address: int, count: int, device_id: int
    ) -> list[int]:
        self.calls.append(("read_input_registers", address, count, device_id))
        if self.read_error is not None:
            raise self.read_error
        return [
            self.input_registers.get((device_id, address + offset), 0)
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
    input_registers: bool = False,
) -> None:
    _set_ascii_registers(
        transport,
        device_id=device_id,
        base_address=modbus.REG_MODEL_BASE,
        length=modbus.REG_MODEL_MAX_LENGTH,
        value=model,
        input_registers=input_registers,
    )
    _set_ascii_registers(
        transport,
        device_id=device_id,
        base_address=modbus.REG_FIRMWARE_VERSION_BASE,
        length=modbus.REG_FIRMWARE_VERSION_MAX_LENGTH,
        value=firmware_version,
        input_registers=input_registers,
    )


def _seed_serial_identification(
    *,
    device_id: int,
    model: str = "WBMR6C",
    firmware_version: str = "1.24.0",
    input_registers: bool = False,
) -> None:
    seed = types.SimpleNamespace(
        holding_registers=FakeSerialTransport.initial_holding_registers,
        input_registers=FakeSerialTransport.initial_input_registers,
    )
    _set_ascii_registers(
        seed,
        device_id=device_id,
        base_address=modbus.REG_MODEL_BASE,
        length=modbus.REG_MODEL_MAX_LENGTH,
        value=model,
        input_registers=input_registers,
    )
    _set_ascii_registers(
        seed,
        device_id=device_id,
        base_address=modbus.REG_FIRMWARE_VERSION_BASE,
        length=modbus.REG_FIRMWARE_VERSION_MAX_LENGTH,
        value=firmware_version,
        input_registers=input_registers,
    )


def _set_ascii_registers(
    transport: Any,
    *,
    device_id: int,
    base_address: int,
    length: int,
    value: str,
    input_registers: bool = False,
) -> None:
    registers = (
        transport.input_registers if input_registers else transport.holding_registers
    )
    for offset in range(length):
        register_value = ord(value[offset]) if offset < len(value) else 0
        registers[(device_id, base_address + offset)] = register_value


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
        self.assertEqual(result["title"], "openWB RS-485 /dev/ttyUSB0")
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
        self.assertEqual(result["title"], "Modbus module 32")
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
                (
                    "read_holding_registers",
                    modbus.REG_MODEL_BASE,
                    modbus.REG_MODEL_MAX_LENGTH,
                    32,
                ),
                (
                    "read_holding_registers",
                    modbus.REG_FIRMWARE_VERSION_BASE,
                    16,
                    32,
                ),
            ],
        )

    async def test_device_subentry_accepts_mr6cu_model_alias(self) -> None:
        transport = FakeDeviceTransport()
        _set_device_identification(
            transport,
            device_id=32,
            model=modbus.MR6CU_MODEL,
        )
        flow = _device_flow(_bus_entry(transport=transport))

        result = await flow.async_step_user({const.CONF_DEVICE_ID: "32"})

        self.assertEqual(result["type"], "create_entry")
        self.assertEqual(
            result["data"],
            {
                const.CONF_DEVICE_ID: 32,
                const.CONF_MODEL: const.MODEL_WB_MR6CU_V2,
                const.CONF_FIRMWARE_VERSION: "1.24.0",
            },
        )

    async def test_device_subentry_accepts_mcm8_model_alias(self) -> None:
        transport = FakeDeviceTransport()
        _set_device_identification(
            transport,
            device_id=32,
            model=modbus.MCM8_MODEL,
            firmware_version="1.3.2",
        )
        flow = _device_flow(_bus_entry(transport=transport))

        result = await flow.async_step_user({const.CONF_DEVICE_ID: "32"})

        self.assertEqual(result["type"], "create_entry")
        self.assertEqual(
            result["data"],
            {
                const.CONF_DEVICE_ID: 32,
                const.CONF_MODEL: const.MODEL_WB_MCM8,
                const.CONF_FIRMWARE_VERSION: "1.3.2",
            },
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
        FakeSerialTransport.initial_input_registers = {}
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
        self.assertIsInstance(
            entry.runtime_data.settings,
            integration.OpenWBSettingsBackend,
        )
        self.assertIs(entry.runtime_data.settings.clients, entry.runtime_data.clients)
        self.assertIsInstance(
            entry.runtime_data.mapping_matrix,
            integration.OpenWBMappingMatrixBackend,
        )
        self.assertIs(
            entry.runtime_data.mapping_matrix.clients,
            entry.runtime_data.clients,
        )
        self.assertIs(
            entry.runtime_data.mapping_matrix.device_metadata,
            entry.runtime_data.device_metadata,
        )
        self.assertEqual(entry.runtime_data.coordinator.data, {})
        self.assertEqual(
            entry.runtime_data.coordinator.listeners,
            [integration._noop_coordinator_listener],
        )
        self.assertEqual(entry.update_listeners, [integration._async_reload_entry])
        self.assertEqual(len(entry.unload_callbacks), 1)
        self.assertEqual(
            hass.config_entries.forwarded_entry_setups,
            [(entry, ("binary_sensor", "event", "switch"))],
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
                (
                    "read_holding_registers",
                    modbus.REG_MODEL_BASE,
                    modbus.REG_MODEL_MAX_LENGTH,
                    32,
                ),
                (
                    "read_holding_registers",
                    modbus.REG_FIRMWARE_VERSION_BASE,
                    16,
                    32,
                ),
                (
                    "read_holding_registers",
                    modbus.REG_MODEL_BASE,
                    modbus.REG_MODEL_MAX_LENGTH,
                    33,
                ),
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

    async def test_wb_mr6cu_setup_skips_input_polling(self) -> None:
        _seed_serial_identification(
            device_id=32,
            model=modbus.MR6CU_MODEL,
            firmware_version="1.24.0",
        )
        entry = StubConfigEntry(
            {
                const.CONF_SERIAL_PORT: "/dev/ttyUSB0",
                const.CONF_BAUDRATE: 9600,
                const.CONF_PARITY: "N",
                const.CONF_STOPBITS: 2,
            },
            subentries={
                "device-32": _device_subentry(
                    32,
                    firmware_version="1.24.0",
                    model=const.MODEL_WB_MR6CU_V2,
                )
            },
        )

        await integration.async_setup_entry(_hass(), entry)

        metadata = entry.runtime_data.device_metadata[32]
        self.assertEqual(metadata.model, modbus.MR6CU_MODEL)
        self.assertFalse(metadata.supports_inputs)
        self.assertFalse(metadata.supports_press_counters)
        self.assertFalse(metadata.supports_mapping_matrix)
        self.assertTrue(metadata.supports_relay_state_discrete_inputs)

        state = entry.runtime_data.coordinator.data[32]
        self.assertEqual(state.input_states, {})
        self.assertEqual(state.press_counts, {})
        self.assertEqual(
            FakeSerialTransport.instances[0].calls,
            [
                (
                    "read_holding_registers",
                    modbus.REG_MODEL_BASE,
                    modbus.REG_MODEL_MAX_LENGTH,
                    32,
                ),
                (
                    "read_holding_registers",
                    modbus.REG_FIRMWARE_VERSION_BASE,
                    16,
                    32,
                ),
                ("read_coils", modbus.COIL_RELAY_COMMAND_BASE, 6, 32),
                ("read_discrete_inputs", modbus.DISCRETE_RELAY_STATE_BASE, 6, 32),
            ],
        )

    async def test_wb_mcm8_setup_reads_inputs_and_skips_relay_polling(self) -> None:
        _seed_serial_identification(
            device_id=32,
            model=modbus.MCM8_MODEL,
            firmware_version="1.3.2",
        )
        FakeSerialTransport.initial_discrete_inputs[(32, 7)] = True
        FakeSerialTransport.initial_input_registers[
            (32, modbus.REG_PRESS_COUNTER_SHORT_BASE + 7)
        ] = 8
        entry = StubConfigEntry(
            {
                const.CONF_SERIAL_PORT: "/dev/ttyUSB0",
                const.CONF_BAUDRATE: 9600,
                const.CONF_PARITY: "N",
                const.CONF_STOPBITS: 2,
            },
            subentries={
                "device-32": _device_subentry(
                    32,
                    firmware_version="1.3.2",
                    model=const.MODEL_WB_MCM8,
                )
            },
        )

        await integration.async_setup_entry(_hass(), entry)

        metadata = entry.runtime_data.device_metadata[32]
        self.assertEqual(metadata.model, modbus.MCM8_MODEL)
        self.assertEqual(metadata.input_numbers, modbus.MCM8_INPUTS)
        self.assertEqual(metadata.output_numbers, ())
        self.assertTrue(metadata.supports_inputs)
        self.assertTrue(metadata.supports_press_counters)
        self.assertFalse(metadata.supports_mapping_matrix)
        self.assertFalse(metadata.supports_relay_one_shot_commands)
        self.assertFalse(metadata.supports_relay_state_discrete_inputs)
        self.assertTrue(metadata.press_counter_input_registers)

        state = entry.runtime_data.coordinator.data[32]
        self.assertTrue(state.input_states[8])
        self.assertNotIn(0, state.input_states)
        self.assertEqual(state.press_counts[(8, "short")], 8)
        self.assertEqual(state.relay_commands, {})
        self.assertEqual(state.relay_states, {})

        calls = FakeSerialTransport.instances[0].calls
        self.assertIn(
            ("read_input_registers", modbus.REG_PRESS_COUNTER_SHORT_BASE, 8, 32),
            calls,
        )
        self.assertIn(
            ("read_discrete_inputs", modbus.DISCRETE_INPUT_STATE_BASE, 8, 32),
            calls,
        )
        self.assertNotIn(("read_coils", modbus.COIL_RELAY_COMMAND_BASE, 6, 32), calls)
        self.assertNotIn(
            ("read_discrete_inputs", modbus.DISCRETE_RELAY_STATE_BASE, 6, 32),
            calls,
        )

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

    async def test_coordinator_applies_fast_modbus_events_without_standard_poll(
        self,
    ) -> None:
        transport = modbus.FakeModbusTransport()
        transport.set_holding_register(
            modbus.REG_PRESS_COUNTER_SHORT_BASE,
            1,
            device_id=32,
        )
        client = modbus.WBMR6CModbus(transport, device_id=32)
        metadata = _metadata(
            firmware_version="1.24.0",
            supports_press_counters=True,
            supports_relay_state_discrete_inputs=True,
            supports_fast_modbus_events=True,
        )
        coordinator = integration.WBMR6CBusCoordinator(
            _hass(),
            _bus_entry(),
            {32: client},
            {32: metadata},
        )

        await coordinator.async_request_refresh()

        self.assertIn(
            ("configure_fast_modbus_events", 32),
            transport.fast_event_calls,
        )
        self.assertEqual(coordinator.data[32].press_counts[(1, "short")], 1)
        transport.calls.clear()
        transport.fast_event_calls.clear()
        transport.queue_fast_modbus_event(
            modbus.FastModbusRegisterEvent(
                device_id=32,
                flag=1,
                remaining=0,
                register_type=int(modbus.FastModbusRegisterType.HOLDING_REGISTER),
                address=modbus.REG_PRESS_COUNTER_SHORT_BASE,
                value=2,
                payload=(2).to_bytes(2, "little"),
            )
        )
        transport.queue_fast_modbus_event(
            modbus.FastModbusRegisterEvent(
                device_id=32,
                flag=1,
                remaining=0,
                register_type=int(modbus.FastModbusRegisterType.DISCRETE_INPUT),
                address=modbus.DISCRETE_INPUT_STATE_BASE,
                value=True,
                payload=b"\x01",
            )
        )

        await coordinator.async_request_refresh()

        self.assertEqual(transport.calls, [])
        self.assertIn(("read_fast_modbus_events", 0), transport.fast_event_calls)
        self.assertEqual(coordinator.data[32].press_counts[(1, "short")], 2)
        self.assertTrue(coordinator.data[32].input_states[1])
        event = coordinator.press_events[(32, 1, "short")]
        self.assertEqual(event.counter, 2)
        self.assertEqual(event.delta, 1)

    async def test_incomplete_fast_modbus_configuration_falls_back_to_polling(
        self,
    ) -> None:
        class PartialFastConfigTransport(modbus.FakeModbusTransport):
            async def configure_fast_modbus_events(
                self,
                device_id: int,
                ranges: Sequence[modbus.FastModbusEventRange],
            ) -> modbus.FastModbusEventConfiguration:
                self.fast_event_calls.append(
                    ("configure_fast_modbus_events", device_id)
                )
                return modbus.FastModbusEventConfiguration(device_id, frozenset())

        transport = PartialFastConfigTransport()
        transport.set_holding_register(
            modbus.REG_PRESS_COUNTER_SHORT_BASE,
            3,
            device_id=32,
        )
        client = modbus.WBMR6CModbus(transport, device_id=32)
        metadata = _metadata(
            firmware_version="1.24.0",
            supports_press_counters=True,
            supports_relay_state_discrete_inputs=True,
            supports_fast_modbus_events=True,
        )
        coordinator = integration.WBMR6CBusCoordinator(
            _hass(),
            _bus_entry(),
            {32: client},
            {32: metadata},
        )

        await coordinator.async_request_refresh()

        self.assertIn(
            ("configure_fast_modbus_events", 32),
            transport.fast_event_calls,
        )
        self.assertNotIn(("read_fast_modbus_events", 0), transport.fast_event_calls)
        self.assertIn(
            ("read_holding_registers", modbus.REG_PRESS_COUNTER_SHORT_BASE, 8, 32),
            transport.calls,
        )
        self.assertEqual(coordinator.data[32].press_counts[(1, "short")], 3)

        transport.calls.clear()
        transport.fast_event_calls.clear()
        transport.set_holding_register(
            modbus.REG_PRESS_COUNTER_SHORT_BASE,
            4,
            device_id=32,
        )

        await coordinator.async_request_refresh()

        self.assertNotIn(
            ("configure_fast_modbus_events", 32),
            transport.fast_event_calls,
        )
        self.assertNotIn(("read_fast_modbus_events", 0), transport.fast_event_calls)
        self.assertIn(
            ("read_holding_registers", modbus.REG_PRESS_COUNTER_SHORT_BASE, 8, 32),
            transport.calls,
        )
        self.assertEqual(coordinator.data[32].press_counts[(1, "short")], 4)

    async def test_press_counter_increment_updates_coordinator_press_event(self) -> None:
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

        transport.set_holding_register(
            modbus.REG_PRESS_COUNTER_SHORT_BASE,
            1,
            device_id=32,
        )
        await entry.runtime_data.coordinator.async_request_refresh()

        event = entry.runtime_data.coordinator.press_events[(32, 1, "short")]
        self.assertEqual(event.event_type, "short")
        self.assertEqual(event.counter, 1)
        self.assertEqual(event.delta, 1)
        self.assertNotIn((32, 1, "long"), entry.runtime_data.coordinator.press_events)

    async def test_press_counter_wraparound_updates_coordinator_press_event(self) -> None:
        FakeSerialTransport.initial_holding_registers = {
            (32, modbus.REG_PRESS_COUNTER_SHORT_BASE): 0xFFFF
        }
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

        transport.set_holding_register(
            modbus.REG_PRESS_COUNTER_SHORT_BASE,
            0,
            device_id=32,
        )
        await entry.runtime_data.coordinator.async_request_refresh()

        event = entry.runtime_data.coordinator.press_events[(32, 1, "short")]
        self.assertEqual(event.counter, 0)
        self.assertEqual(event.delta, 1)

    async def test_first_press_counter_baseline_after_setup_fires_nothing(self) -> None:
        FakeSerialTransport.initial_holding_registers = {
            (32, modbus.REG_PRESS_COUNTER_SHORT_BASE): 7
        }
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

        self.assertEqual(entry.runtime_data.coordinator.press_events, {})

    async def test_first_press_counter_baseline_after_reconnect_fires_nothing(
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

        transport.unavailable_devices.add(32)
        with self.assertRaises(UpdateFailed):
            await entry.runtime_data.coordinator.async_request_refresh()

        transport.unavailable_devices.clear()
        transport.set_holding_register(
            modbus.REG_PRESS_COUNTER_SHORT_BASE,
            4,
            device_id=32,
        )
        await entry.runtime_data.coordinator.async_request_refresh()

        self.assertEqual(entry.runtime_data.coordinator.press_events, {})

        transport.set_holding_register(
            modbus.REG_PRESS_COUNTER_SHORT_BASE,
            5,
            device_id=32,
        )
        await entry.runtime_data.coordinator.async_request_refresh()
        self.assertEqual(
            entry.runtime_data.coordinator.press_events[(32, 1, "short")].delta,
            1,
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
            [(entry, ("binary_sensor", "event", "switch"))],
        )


class FakeSettingsClient:
    def __init__(self) -> None:
        self.basic_settings = modbus.WBMR6CBasicSettings(
            output_power_on_mode=1,
            communication_timeout_s=10,
            input_modes={1: 6, 0: 4},
            debounce_ms={1: 50, 0: 100},
            long_press_ms={1: 1000, 0: 1500},
            second_press_wait_ms={1: 300, 0: 400},
            safe_states={1: True},
            safe_mode_actions={1: 1},
            safe_mode_input_controls={1: 2},
        )
        self.calls: list[tuple[Any, ...]] = []
        self.error: Exception | None = None

    async def read_basic_settings(self) -> Any:
        await self._maybe_raise()
        self.calls.append(("read_basic_settings",))
        return self.basic_settings

    async def read_output_power_on_mode(self) -> int:
        await self._maybe_raise()
        self.calls.append(("read_output_power_on_mode",))
        return 1

    async def set_output_power_on_mode(self, mode: object) -> None:
        await self._call("set_output_power_on_mode", mode)

    async def read_communication_timeout_s(self) -> int:
        await self._maybe_raise()
        self.calls.append(("read_communication_timeout_s",))
        return 10

    async def set_communication_timeout_s(self, value: int) -> None:
        await self._call("set_communication_timeout_s", value)

    async def read_input_modes(self) -> dict[int, int]:
        await self._maybe_raise()
        self.calls.append(("read_input_modes",))
        return {1: 6, 0: 4}

    async def set_input_mode(self, input_number: int, mode: object) -> None:
        await self._call("set_input_mode", input_number, mode)

    async def read_debounce_ms(self) -> dict[int, int]:
        await self._maybe_raise()
        self.calls.append(("read_debounce_ms",))
        return {1: 50, 0: 100}

    async def set_debounce_ms(self, input_number: int, value: int) -> None:
        await self._call("set_debounce_ms", input_number, value)

    async def read_long_press_ms(self) -> dict[int, int]:
        await self._maybe_raise()
        self.calls.append(("read_long_press_ms",))
        return {1: 1000, 0: 1500}

    async def set_long_press_ms(self, input_number: int, value: int) -> None:
        await self._call("set_long_press_ms", input_number, value)

    async def read_second_press_wait_ms(self) -> dict[int, int]:
        await self._maybe_raise()
        self.calls.append(("read_second_press_wait_ms",))
        return {1: 300, 0: 400}

    async def set_second_press_wait_ms(self, input_number: int, value: int) -> None:
        await self._call("set_second_press_wait_ms", input_number, value)

    async def read_safe_states(self) -> dict[int, bool]:
        await self._maybe_raise()
        self.calls.append(("read_safe_states",))
        return {1: True}

    async def set_safe_state(self, output: int, state: object) -> None:
        await self._call("set_safe_state", output, state)

    async def read_safe_mode_actions(self) -> dict[int, int]:
        await self._maybe_raise()
        self.calls.append(("read_safe_mode_actions",))
        return {1: 1}

    async def set_safe_mode_action(self, output: int, action: object) -> None:
        await self._call("set_safe_mode_action", output, action)

    async def read_safe_mode_input_controls(self) -> dict[int, int]:
        await self._maybe_raise()
        self.calls.append(("read_safe_mode_input_controls",))
        return {1: 2}

    async def set_safe_mode_input_control(
        self, output: int, control: object
    ) -> None:
        await self._call("set_safe_mode_input_control", output, control)

    async def _call(self, method: str, *args: object) -> None:
        await self._maybe_raise()
        self.calls.append((method, *args))

    async def _maybe_raise(self) -> None:
        if self.error is not None:
            raise self.error


class SettingsBackendTest(unittest.IsolatedAsyncioTestCase):
    async def test_read_settings_uses_on_demand_client(self) -> None:
        client = FakeSettingsClient()
        backend = integration.OpenWBSettingsBackend({32: client})

        basic_settings = await backend.read_basic_settings(32)
        input_modes = await backend.read_input_modes(32)
        debounce_ms = await backend.read_debounce_ms(32)
        long_press_ms = await backend.read_long_press_ms(32)
        second_press_wait_ms = await backend.read_second_press_wait_ms(32)
        safe_states = await backend.read_safe_states(32)
        safe_mode_actions = await backend.read_safe_mode_actions(32)
        safe_mode_input_controls = await backend.read_safe_mode_input_controls(32)
        output_power_on_mode = await backend.read_output_power_on_mode(32)
        communication_timeout_s = await backend.read_communication_timeout_s(32)

        self.assertIs(basic_settings, client.basic_settings)
        self.assertEqual(input_modes[0], 4)
        self.assertEqual(debounce_ms[1], 50)
        self.assertEqual(long_press_ms[0], 1500)
        self.assertEqual(second_press_wait_ms[1], 300)
        self.assertTrue(safe_states[1])
        self.assertEqual(safe_mode_actions[1], 1)
        self.assertEqual(safe_mode_input_controls[1], 2)
        self.assertEqual(output_power_on_mode, 1)
        self.assertEqual(communication_timeout_s, 10)
        self.assertEqual(
            client.calls,
            [
                ("read_basic_settings",),
                ("read_input_modes",),
                ("read_debounce_ms",),
                ("read_long_press_ms",),
                ("read_second_press_wait_ms",),
                ("read_safe_states",),
                ("read_safe_mode_actions",),
                ("read_safe_mode_input_controls",),
                ("read_output_power_on_mode",),
                ("read_communication_timeout_s",),
            ],
        )

    async def test_write_settings_use_explicit_client_methods(self) -> None:
        client = FakeSettingsClient()
        backend = integration.OpenWBSettingsBackend({32: client})

        await backend.set_input_mode(32, 0, modbus.InputMode.MAPPING_MATRIX_EDGE)
        await backend.set_debounce_ms(32, 0, 75)
        await backend.set_long_press_ms(32, 0, 1200)
        await backend.set_second_press_wait_ms(32, 0, 350)
        await backend.set_safe_state(32, 6, modbus.SafeState.ON)
        await backend.set_safe_mode_action(
            32,
            3,
            modbus.SafeModeAction.SET_SAFE_STATE,
        )
        await backend.set_safe_mode_input_control(
            32,
            6,
            modbus.SafeModeInputControl.ALLOW_ONLY_IN_SAFE_MODE,
        )
        await backend.set_output_power_on_mode(
            32,
            modbus.OutputPowerOnMode.RESTORE_LAST_STATE,
        )
        await backend.set_communication_timeout_s(32, 15)

        self.assertEqual(
            client.calls,
            [
                ("set_input_mode", 0, modbus.InputMode.MAPPING_MATRIX_EDGE),
                ("set_debounce_ms", 0, 75),
                ("set_long_press_ms", 0, 1200),
                ("set_second_press_wait_ms", 0, 350),
                ("set_safe_state", 6, modbus.SafeState.ON),
                (
                    "set_safe_mode_action",
                    3,
                    modbus.SafeModeAction.SET_SAFE_STATE,
                ),
                (
                    "set_safe_mode_input_control",
                    6,
                    modbus.SafeModeInputControl.ALLOW_ONLY_IN_SAFE_MODE,
                ),
                (
                    "set_output_power_on_mode",
                    modbus.OutputPowerOnMode.RESTORE_LAST_STATE,
                ),
                ("set_communication_timeout_s", 15),
            ],
        )

    async def test_missing_device_raises_home_assistant_error(self) -> None:
        backend = integration.OpenWBSettingsBackend({})

        with self.assertRaisesRegex(HomeAssistantError, "not configured"):
            await backend.read_basic_settings(32)

    async def test_modbus_error_raises_home_assistant_error(self) -> None:
        client = FakeSettingsClient()
        client.error = modbus.WBMR6CModbusConnectionError("boom")
        backend = integration.OpenWBSettingsBackend({32: client})

        with self.assertRaisesRegex(HomeAssistantError, "Unable to read settings"):
            await backend.read_basic_settings(32)

    async def test_invalid_setting_raises_home_assistant_error_before_modbus_write(
        self,
    ) -> None:
        transport = modbus.FakeModbusTransport()
        client = modbus.WBMR6CModbus(transport, device_id=32)
        backend = integration.OpenWBSettingsBackend({32: client})

        with self.assertRaisesRegex(HomeAssistantError, "Invalid openWB settings"):
            await backend.set_debounce_ms(32, 1, 2001)

        self.assertEqual(transport.calls, [])


def _complete_mapping_matrix(action: int = 0) -> dict[tuple[int, int], int]:
    return {
        (input_number, output): action
        for input_number in modbus.INPUTS
        for output in modbus.OUTPUTS
    }


class FakeMappingClient:
    def __init__(self) -> None:
        self.matrix = _complete_mapping_matrix()
        self.matrix[(1, 1)] = int(modbus.MappingAction.TOGGLE)
        self.calls: list[tuple[Any, ...]] = []
        self.error: Exception | None = None

    async def read_mapping_action(
        self, event: object, input_number: int, output: int
    ) -> int:
        await self._maybe_raise()
        self.calls.append(("read_mapping_action", event, input_number, output))
        return self.matrix[(input_number, output)]

    async def set_mapping_action(
        self, event: object, input_number: int, output: int, action: object
    ) -> None:
        await self._call("set_mapping_action", event, input_number, output, action)

    async def read_mapping_matrix(self, event: object) -> dict[tuple[int, int], int]:
        await self._maybe_raise()
        self.calls.append(("read_mapping_matrix", event))
        return dict(self.matrix)

    async def write_mapping_matrix(
        self,
        event: object,
        desired_matrix: dict[tuple[int, int], object],
    ) -> None:
        await self._call("write_mapping_matrix", event, desired_matrix)

    async def _call(self, method: str, *args: object) -> None:
        await self._maybe_raise()
        self.calls.append((method, *args))

    async def _maybe_raise(self) -> None:
        if self.error is not None:
            raise self.error


class MappingMatrixBackendTest(unittest.IsolatedAsyncioTestCase):
    async def test_read_mapping_action_and_matrix_use_on_demand_client(self) -> None:
        client = FakeMappingClient()
        backend = integration.OpenWBMappingMatrixBackend(
            {32: client},
            {32: _metadata()},
        )

        action = await backend.read_mapping_action(
            32,
            modbus.MappingEvent.SHORT_PRESS,
            1,
            1,
        )
        matrix = await backend.read_mapping_matrix(
            32,
            modbus.MappingEvent.SHORT_PRESS,
        )

        self.assertEqual(action, modbus.MappingAction.TOGGLE)
        self.assertEqual(matrix[(1, 1)], modbus.MappingAction.TOGGLE)
        self.assertEqual(
            client.calls,
            [
                (
                    "read_mapping_action",
                    modbus.MappingEvent.SHORT_PRESS,
                    1,
                    1,
                ),
                ("read_mapping_matrix", modbus.MappingEvent.SHORT_PRESS),
            ],
        )

    async def test_writes_use_explicit_mapping_client_methods(self) -> None:
        client = FakeMappingClient()
        backend = integration.OpenWBMappingMatrixBackend(
            {32: client},
            {32: _metadata()},
        )
        desired = _complete_mapping_matrix(int(modbus.MappingAction.ON))

        await backend.set_mapping_action(
            32,
            modbus.MappingEvent.SHORT_PRESS,
            1,
            2,
            modbus.MappingAction.OFF,
        )
        await backend.write_mapping_matrix(
            32,
            modbus.MappingEvent.LONG_PRESS,
            desired,
        )

        self.assertEqual(
            client.calls,
            [
                (
                    "set_mapping_action",
                    modbus.MappingEvent.SHORT_PRESS,
                    1,
                    2,
                    modbus.MappingAction.OFF,
                ),
                ("write_mapping_matrix", modbus.MappingEvent.LONG_PRESS, desired),
            ],
        )

    async def test_unsupported_device_rejects_before_client_io(self) -> None:
        client = FakeMappingClient()
        backend = integration.OpenWBMappingMatrixBackend(
            {32: client},
            {
                32: _metadata(
                    supports_mapping_matrix=False,
                    output_numbers=(),
                )
            },
        )

        with self.assertRaisesRegex(HomeAssistantError, "does not support"):
            await backend.read_mapping_matrix(32, modbus.MappingEvent.SHORT_PRESS)

        self.assertEqual(client.calls, [])

    async def test_missing_device_raises_home_assistant_error(self) -> None:
        backend = integration.OpenWBMappingMatrixBackend({}, {})

        with self.assertRaisesRegex(HomeAssistantError, "not configured"):
            await backend.read_mapping_matrix(32, modbus.MappingEvent.SHORT_PRESS)

    async def test_modbus_error_raises_home_assistant_error(self) -> None:
        client = FakeMappingClient()
        client.error = modbus.WBMR6CModbusConnectionError("boom")
        backend = integration.OpenWBMappingMatrixBackend(
            {32: client},
            {32: _metadata()},
        )

        with self.assertRaisesRegex(HomeAssistantError, "Unable to read mapping"):
            await backend.read_mapping_matrix(32, modbus.MappingEvent.SHORT_PRESS)

    async def test_invalid_matrix_value_raises_before_modbus_call(self) -> None:
        transport = modbus.FakeModbusTransport()
        client = modbus.WBMR6CModbus(transport, device_id=32)
        backend = integration.OpenWBMappingMatrixBackend(
            {32: client},
            {32: _metadata()},
        )
        desired = _complete_mapping_matrix()
        desired[(1, 1)] = 4

        with self.assertRaisesRegex(HomeAssistantError, "Invalid openWB mapping"):
            await backend.write_mapping_matrix(
                32,
                modbus.MappingEvent.SHORT_PRESS,
                desired,
            )

        self.assertEqual(transport.calls, [])

    async def test_write_mapping_matrix_writes_only_changed_cells(self) -> None:
        transport = modbus.FakeModbusTransport()
        current = _complete_mapping_matrix()
        current[(1, 1)] = int(modbus.MappingAction.OFF)
        current[(0, 6)] = int(modbus.MappingAction.TOGGLE)
        for (input_number, output), action in current.items():
            transport.set_holding_register(
                modbus.mapping_register_address(
                    modbus.MappingEvent.SHORT_PRESS,
                    input_number,
                    output,
                ),
                action,
                device_id=32,
            )

        desired = dict(current)
        desired[(1, 1)] = int(modbus.MappingAction.ON)
        desired[(2, 3)] = int(modbus.MappingAction.OFF)
        client = modbus.WBMR6CModbus(transport, device_id=32)
        backend = integration.OpenWBMappingMatrixBackend(
            {32: client},
            {32: _metadata()},
        )
        transport.calls.clear()

        await backend.write_mapping_matrix(
            32,
            modbus.MappingEvent.SHORT_PRESS,
            desired,
        )

        self.assertEqual(
            transport.writes,
            [
                ("write_register", 544, int(modbus.MappingAction.ON), 32),
                ("write_register", 554, int(modbus.MappingAction.OFF), 32),
            ],
        )
        self.assertEqual(
            transport.calls,
            [
                (
                    "read_holding_registers",
                    modbus.REG_MAPPING_SHORT_PRESS_BASE,
                    modbus.MAPPING_MATRIX_ROW_SPACING
                    * modbus.MAPPING_MATRIX_ROW_SPACING,
                    32,
                ),
                ("write_register", 544, int(modbus.MappingAction.ON), 32),
                ("write_register", 554, int(modbus.MappingAction.OFF), 32),
            ],
        )


class FakeSwitchCoordinator:
    def __init__(
        self,
        data: dict[int, integration.WBMR6CDeviceState],
        press_events: dict[tuple[int, int, str], integration.WBMR6CPressEvent]
        | None = None,
    ) -> None:
        self.data = data
        self.press_events = press_events or {}
        self.last_update_success = True
        self.async_request_refresh_calls = 0

    async def async_request_refresh(self) -> None:
        self.async_request_refresh_calls += 1


class FakeRelayClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int] | tuple[str, int, bool]] = []
        self.error: Exception | None = None

    async def turn_on(self, output: int) -> None:
        await self._call("turn_on", output)

    async def turn_off(self, output: int) -> None:
        await self._call("turn_off", output)

    async def toggle(self, output: int) -> None:
        await self._call("toggle", output)

    async def set_relay_command(self, output: int, value: bool) -> None:
        if self.error is not None:
            raise self.error
        self.calls.append(("set_relay_command", output, value))

    async def _call(self, method: str, output: int) -> None:
        if self.error is not None:
            raise self.error
        self.calls.append((method, output))


def _metadata(
    *,
    model: str | None = "WBMR6C",
    firmware_version: str | None = "1.24.0",
    supports_inputs: bool = True,
    supports_press_counters: bool = True,
    supports_mapping_matrix: bool = True,
    supports_relay_one_shot_commands: bool = False,
    supports_relay_state_discrete_inputs: bool = True,
    supports_fast_modbus_events: bool = False,
    input_numbers: tuple[int, ...] | None = None,
    output_numbers: tuple[int, ...] | None = None,
    press_counter_input_registers: bool = False,
) -> integration.WBMR6CDeviceMetadata:
    if input_numbers is None:
        if not supports_inputs:
            input_numbers = ()
        elif model in {modbus.MCM8_MODEL, modbus.WBMCM8_MODEL, const.MODEL_WB_MCM8}:
            input_numbers = modbus.MCM8_INPUTS
        else:
            input_numbers = modbus.INPUTS
    if output_numbers is None:
        if model in {modbus.MCM8_MODEL, modbus.WBMCM8_MODEL, const.MODEL_WB_MCM8}:
            output_numbers = ()
        else:
            output_numbers = modbus.OUTPUTS

    return integration.WBMR6CDeviceMetadata(
        model=model,
        firmware_version=firmware_version,
        supports_inputs=supports_inputs,
        supports_press_counters=supports_press_counters,
        supports_mapping_matrix=supports_mapping_matrix,
        supports_relay_one_shot_commands=supports_relay_one_shot_commands,
        supports_relay_state_discrete_inputs=supports_relay_state_discrete_inputs,
        input_numbers=input_numbers,
        output_numbers=output_numbers,
        press_counter_input_registers=press_counter_input_registers,
        supports_fast_modbus_events=supports_fast_modbus_events,
    )


def _device_state(
    relay_states: dict[int, bool] | None = None,
    *,
    input_states: dict[int, bool] | None = None,
    press_counts: dict[tuple[int, str], int] | None = None,
) -> integration.WBMR6CDeviceState:
    return integration.WBMR6CDeviceState(
        input_states=dict(input_states or {}),
        press_counts=dict(press_counts or {}),
        relay_states=dict(relay_states or {}),
        relay_commands={},
    )


def _switch_entry(
    *,
    serial_port: str = "/dev/ttyUSB0",
    device_id: int = 32,
    relay_states: dict[int, bool] | None = None,
    supports_relay_one_shot_commands: bool = False,
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
        device_metadata={
            device_id: _metadata(
                supports_relay_one_shot_commands=supports_relay_one_shot_commands
            )
        },
    )
    return entry, client, coordinator


def _relay_switch(
    *,
    serial_port: str = "/dev/ttyUSB0",
    device_id: int = 32,
    output: int = 1,
    relay_states: dict[int, bool] | None = None,
    supports_relay_one_shot_commands: bool = False,
) -> tuple[
    switch_platform.OpenWBRelaySwitch,
    FakeRelayClient,
    FakeSwitchCoordinator,
]:
    entry, client, coordinator = _switch_entry(
        serial_port=serial_port,
        device_id=device_id,
        relay_states=relay_states,
        supports_relay_one_shot_commands=supports_relay_one_shot_commands,
    )
    metadata = _metadata(
        supports_relay_one_shot_commands=supports_relay_one_shot_commands
    )
    entity = switch_platform.OpenWBRelaySwitch(
        entry=entry,
        client=client,
        serial_port=serial_port,
        device_id=device_id,
        output=output,
        metadata=metadata,
    )
    return entity, client, coordinator


def _input_binary_sensor(
    *,
    serial_port: str = "/dev/ttyUSB0",
    device_id: int = 32,
    input_number: int = 1,
    input_states: dict[int, bool] | None = None,
) -> tuple[binary_sensor_platform.OpenWBInputBinarySensor, FakeSwitchCoordinator]:
    entry = _bus_entry(
        serial_port=serial_port,
        subentries={"device-32": _device_subentry(device_id)},
    )
    coordinator = FakeSwitchCoordinator(
        {device_id: _device_state(input_states=input_states)}
    )
    entry.runtime_data = types.SimpleNamespace(
        coordinator=coordinator,
        clients={device_id: object()},
        device_metadata={device_id: _metadata()},
    )
    entity = binary_sensor_platform.OpenWBInputBinarySensor(
        entry=entry,
        serial_port=serial_port,
        device_id=device_id,
        input_number=input_number,
        metadata=_metadata(),
    )
    return entity, coordinator


def _input_press_event(
    *,
    serial_port: str = "/dev/ttyUSB0",
    device_id: int = 32,
    input_number: int = 1,
    event_type: str = "short",
    press_counts: dict[tuple[int, str], int] | None = None,
    press_events: dict[tuple[int, int, str], integration.WBMR6CPressEvent]
    | None = None,
) -> tuple[event_platform.OpenWBInputPressEvent, FakeSwitchCoordinator]:
    entry = _bus_entry(
        serial_port=serial_port,
        subentries={"device-32": _device_subentry(device_id, firmware_version="1.24.0")},
    )
    coordinator = FakeSwitchCoordinator(
        {device_id: _device_state(press_counts=press_counts)},
        press_events=press_events,
    )
    entry.runtime_data = types.SimpleNamespace(
        coordinator=coordinator,
        clients={device_id: object()},
        device_metadata={device_id: _metadata()},
    )
    entity = event_platform.OpenWBInputPressEvent(
        entry=entry,
        serial_port=serial_port,
        device_id=device_id,
        input_number=input_number,
        event_type=event_type,
        metadata=_metadata(),
    )
    return entity, coordinator


class BinarySensorPlatformTest(unittest.IsolatedAsyncioTestCase):
    async def test_setup_creates_seven_input_sensors_per_device_subentry(self) -> None:
        entry = _bus_entry(
            subentries={
                "subentry-32": _device_subentry(32),
                "subentry-33": _device_subentry(33),
            }
        )
        entry.runtime_data = types.SimpleNamespace(
            coordinator=FakeSwitchCoordinator(
                {
                    32: _device_state(
                        input_states={input_number: False for input_number in modbus.INPUTS}
                    ),
                    33: _device_state(
                        input_states={input_number: False for input_number in modbus.INPUTS}
                    ),
                }
            ),
            clients={32: object(), 33: object()},
            device_metadata={32: _metadata(), 33: _metadata()},
        )
        add_calls: list[tuple[list[Any], dict[str, Any]]] = []

        def async_add_entities(entities: list[Any], **kwargs: Any) -> None:
            add_calls.append((entities, kwargs))

        await binary_sensor_platform.async_setup_entry(
            types.SimpleNamespace(), entry, async_add_entities
        )

        self.assertEqual(len(add_calls), 2)
        self.assertEqual([len(entities) for entities, _ in add_calls], [7, 7])
        self.assertEqual(
            [kwargs["config_subentry_id"] for _, kwargs in add_calls],
            ["subentry-32", "subentry-33"],
        )
        unique_ids = [
            entity.unique_id for entities, _ in add_calls for entity in entities
        ]
        self.assertIn("/dev/ttyUSB0:32:input_1", unique_ids)
        self.assertIn("/dev/ttyUSB0:32:input_0", unique_ids)
        self.assertIn("/dev/ttyUSB0:33:input_6", unique_ids)
        self.assertEqual(len(set(unique_ids)), 14)

    async def test_setup_skips_input_sensors_for_wb_mr6cu(self) -> None:
        entry = _bus_entry(
            subentries={
                "subentry-32": _device_subentry(32),
                "subentry-33": _device_subentry(
                    33,
                    model=const.MODEL_WB_MR6CU_V2,
                ),
            }
        )
        entry.runtime_data = types.SimpleNamespace(
            coordinator=FakeSwitchCoordinator(
                {
                    32: _device_state(
                        input_states={
                            input_number: False for input_number in modbus.INPUTS
                        }
                    ),
                    33: _device_state(),
                }
            ),
            clients={32: object(), 33: object()},
            device_metadata={
                32: _metadata(),
                33: _metadata(
                    model=modbus.MR6CU_MODEL,
                    supports_inputs=False,
                    supports_press_counters=False,
                    supports_mapping_matrix=False,
                ),
            },
        )
        add_calls: list[tuple[list[Any], dict[str, Any]]] = []

        def async_add_entities(entities: list[Any], **kwargs: Any) -> None:
            add_calls.append((entities, kwargs))

        await binary_sensor_platform.async_setup_entry(
            types.SimpleNamespace(), entry, async_add_entities
        )

        self.assertEqual(len(add_calls), 1)
        self.assertEqual(add_calls[0][1]["config_subentry_id"], "subentry-32")
        self.assertEqual(len(add_calls[0][0]), 7)

    async def test_setup_creates_eight_input_sensors_for_wb_mcm8(self) -> None:
        entry = _bus_entry(
            subentries={
                "subentry-32": _device_subentry(
                    32,
                    firmware_version="1.3.2",
                    model=const.MODEL_WB_MCM8,
                )
            }
        )
        entry.runtime_data = types.SimpleNamespace(
            coordinator=FakeSwitchCoordinator(
                {
                    32: _device_state(
                        input_states={
                            input_number: False
                            for input_number in modbus.MCM8_INPUTS
                        }
                    )
                }
            ),
            clients={32: object()},
            device_metadata={
                32: _metadata(
                    model=modbus.MCM8_MODEL,
                    firmware_version="1.3.2",
                    supports_mapping_matrix=False,
                    supports_relay_state_discrete_inputs=False,
                )
            },
        )
        add_calls: list[tuple[list[Any], dict[str, Any]]] = []

        def async_add_entities(entities: list[Any], **kwargs: Any) -> None:
            add_calls.append((entities, kwargs))

        await binary_sensor_platform.async_setup_entry(
            types.SimpleNamespace(), entry, async_add_entities
        )

        self.assertEqual(len(add_calls), 1)
        self.assertEqual(len(add_calls[0][0]), 8)
        unique_ids = [entity.unique_id for entity in add_calls[0][0]]
        self.assertIn("/dev/ttyUSB0:32:input_8", unique_ids)
        self.assertNotIn("/dev/ttyUSB0:32:input_0", unique_ids)
        self.assertEqual(add_calls[0][0][0].device_info["model"], "WB-MCM8")
        self.assertEqual(add_calls[0][0][0].device_info["name"], "WB-MCM8 32")

    async def test_is_on_reads_coordinator_input_state_without_io(self) -> None:
        entity, coordinator = _input_binary_sensor(
            input_number=2,
            input_states={2: True},
        )

        self.assertTrue(entity.is_on)
        self.assertEqual(coordinator.async_request_refresh_calls, 0)

    async def test_unavailable_when_device_or_input_missing_from_data(self) -> None:
        entity, coordinator = _input_binary_sensor(
            input_number=2,
            input_states={2: True},
        )

        self.assertTrue(entity.available)

        coordinator.data = {}
        self.assertFalse(entity.available)
        self.assertIsNone(entity.is_on)

        coordinator.data = {32: _device_state(input_states={1: True})}
        self.assertFalse(entity.available)
        self.assertIsNone(entity.is_on)


class EventPlatformTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        FakeSerialTransport.instances = []
        FakeSerialTransport.connect_error = None
        FakeSerialTransport.initial_coils = {}
        FakeSerialTransport.initial_discrete_inputs = {}
        FakeSerialTransport.initial_holding_registers = {}
        FakeSerialTransport.initial_input_registers = {}
        FakeSerialTransport.initial_unavailable_devices = set()
        self.original_transport = integration.PymodbusSerialTransport
        integration.PymodbusSerialTransport = FakeSerialTransport

    def tearDown(self) -> None:
        integration.PymodbusSerialTransport = self.original_transport

    async def test_setup_creates_press_events_only_for_supported_firmware(self) -> None:
        entry = _bus_entry(
            subentries={
                "subentry-32": _device_subentry(32, firmware_version="1.24.0"),
                "subentry-33": _device_subentry(33, firmware_version="1.16.9"),
            }
        )
        entry.runtime_data = types.SimpleNamespace(
            coordinator=FakeSwitchCoordinator(
                {
                    32: _device_state(
                        press_counts={
                            (input_number, event_type): 0
                            for input_number in modbus.INPUTS
                            for event_type in integration.PRESS_EVENT_TYPES
                        }
                    ),
                    33: _device_state(),
                }
            ),
            clients={32: object(), 33: object()},
            device_metadata={
                32: _metadata(supports_press_counters=True),
                33: _metadata(
                    firmware_version="1.16.9",
                    supports_press_counters=False,
                ),
            },
        )
        add_calls: list[tuple[list[Any], dict[str, Any]]] = []

        def async_add_entities(entities: list[Any], **kwargs: Any) -> None:
            add_calls.append((entities, kwargs))

        await event_platform.async_setup_entry(
            types.SimpleNamespace(), entry, async_add_entities
        )

        self.assertEqual(len(add_calls), 1)
        self.assertEqual(len(add_calls[0][0]), 28)
        self.assertEqual(add_calls[0][1]["config_subentry_id"], "subentry-32")
        unique_ids = [entity.unique_id for entity in add_calls[0][0]]
        self.assertIn("/dev/ttyUSB0:32:input_1_press_short", unique_ids)
        self.assertIn(
            "/dev/ttyUSB0:32:input_0_press_short_then_long",
            unique_ids,
        )
        self.assertEqual(len(set(unique_ids)), 28)
        self.assertEqual(add_calls[0][0][0].event_types, ["short"])

    async def test_setup_skips_press_events_for_wb_mr6cu(self) -> None:
        entry = _bus_entry(
            subentries={
                "subentry-32": _device_subentry(32, firmware_version="1.24.0"),
                "subentry-33": _device_subentry(
                    33,
                    firmware_version="1.24.0",
                    model=const.MODEL_WB_MR6CU_V2,
                ),
            }
        )
        entry.runtime_data = types.SimpleNamespace(
            coordinator=FakeSwitchCoordinator(
                {
                    32: _device_state(
                        press_counts={
                            (input_number, event_type): 0
                            for input_number in modbus.INPUTS
                            for event_type in integration.PRESS_EVENT_TYPES
                        }
                    ),
                    33: _device_state(),
                }
            ),
            clients={32: object(), 33: object()},
            device_metadata={
                32: _metadata(supports_press_counters=True),
                33: _metadata(
                    model=modbus.MR6CU_MODEL,
                    supports_inputs=False,
                    supports_press_counters=False,
                    supports_mapping_matrix=False,
                ),
            },
        )
        add_calls: list[tuple[list[Any], dict[str, Any]]] = []

        def async_add_entities(entities: list[Any], **kwargs: Any) -> None:
            add_calls.append((entities, kwargs))

        await event_platform.async_setup_entry(
            types.SimpleNamespace(), entry, async_add_entities
        )

        self.assertEqual(len(add_calls), 1)
        self.assertEqual(add_calls[0][1]["config_subentry_id"], "subentry-32")
        self.assertEqual(len(add_calls[0][0]), 28)

    async def test_setup_creates_press_events_for_wb_mcm8_inputs(self) -> None:
        entry = _bus_entry(
            subentries={
                "subentry-32": _device_subentry(
                    32,
                    firmware_version="1.3.2",
                    model=const.MODEL_WB_MCM8,
                )
            }
        )
        entry.runtime_data = types.SimpleNamespace(
            coordinator=FakeSwitchCoordinator(
                {
                    32: _device_state(
                        press_counts={
                            (input_number, event_type): 0
                            for input_number in modbus.MCM8_INPUTS
                            for event_type in integration.PRESS_EVENT_TYPES
                        }
                    )
                }
            ),
            clients={32: object()},
            device_metadata={
                32: _metadata(
                    model=modbus.MCM8_MODEL,
                    firmware_version="1.3.2",
                    supports_mapping_matrix=False,
                    supports_relay_state_discrete_inputs=False,
                    press_counter_input_registers=True,
                )
            },
        )
        add_calls: list[tuple[list[Any], dict[str, Any]]] = []

        def async_add_entities(entities: list[Any], **kwargs: Any) -> None:
            add_calls.append((entities, kwargs))

        await event_platform.async_setup_entry(
            types.SimpleNamespace(), entry, async_add_entities
        )

        self.assertEqual(len(add_calls), 1)
        self.assertEqual(len(add_calls[0][0]), 32)
        unique_ids = [entity.unique_id for entity in add_calls[0][0]]
        self.assertIn("/dev/ttyUSB0:32:input_8_press_short", unique_ids)
        self.assertNotIn("/dev/ttyUSB0:32:input_0_press_short", unique_ids)

    async def test_counter_increment_fires_correct_event_entity_only(self) -> None:
        entry = StubConfigEntry(
            {
                const.CONF_SERIAL_PORT: "/dev/ttyUSB0",
                const.CONF_BAUDRATE: 9600,
                const.CONF_PARITY: "N",
                const.CONF_STOPBITS: 2,
            },
            subentries={"subentry-32": _device_subentry(32, firmware_version="1.24.0")},
        )
        await integration.async_setup_entry(_hass(), entry)
        add_calls: list[tuple[list[Any], dict[str, Any]]] = []

        def async_add_entities(entities: list[Any], **kwargs: Any) -> None:
            add_calls.append((entities, kwargs))

        await event_platform.async_setup_entry(
            types.SimpleNamespace(), entry, async_add_entities
        )
        entities = add_calls[0][0]
        short_entity = next(
            entity
            for entity in entities
            if entity.unique_id == "/dev/ttyUSB0:32:input_1_press_short"
        )
        long_entity = next(
            entity
            for entity in entities
            if entity.unique_id == "/dev/ttyUSB0:32:input_1_press_long"
        )
        transport = FakeSerialTransport.instances[0]
        transport.calls.clear()

        transport.set_holding_register(
            modbus.REG_PRESS_COUNTER_SHORT_BASE,
            1,
            device_id=32,
        )
        await entry.runtime_data.coordinator.async_request_refresh()
        calls_after_refresh = list(transport.calls)
        short_entity._handle_coordinator_update()
        long_entity._handle_coordinator_update()

        self.assertEqual(
            short_entity.triggered_events,
            [
                (
                    "short",
                    {"device_id": 32, "input": 1, "counter": 1, "delta": 1},
                )
            ],
        )
        self.assertFalse(hasattr(long_entity, "triggered_events"))
        self.assertEqual(transport.calls, calls_after_refresh)

    async def test_event_entity_available_only_when_counter_data_present(self) -> None:
        entity, coordinator = _input_press_event(
            press_counts={(1, "short"): 0},
        )

        self.assertTrue(entity.available)

        coordinator.data = {}
        self.assertFalse(entity.available)

        coordinator.data = {32: _device_state(press_counts={(1, "long"): 0})}
        self.assertFalse(entity.available)

    async def test_event_entity_does_not_refire_stale_event(self) -> None:
        entity, coordinator = _input_press_event(
            press_counts={(1, "short"): 1},
        )
        coordinator.press_events[(32, 1, "short")] = integration.WBMR6CPressEvent(
            device_id=32,
            input_number=1,
            event_type="short",
            counter=1,
            delta=1,
            sequence=1,
        )

        entity._handle_coordinator_update()
        entity._handle_coordinator_update()

        self.assertEqual(
            entity.triggered_events,
            [
                (
                    "short",
                    {"device_id": 32, "input": 1, "counter": 1, "delta": 1},
                )
            ],
        )


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
                "model": "WB-MR6C v.2",
                "name": "WB-MR6C 32",
                "sw_version": "1.24.0",
            },
        )

    async def test_wb_mr6cu_device_info_uses_relay_only_model_name(self) -> None:
        entry = _bus_entry(
            subentries={
                "subentry-32": _device_subentry(
                    32,
                    model=const.MODEL_WB_MR6CU_V2,
                )
            }
        )
        client = FakeRelayClient()
        entry.runtime_data = types.SimpleNamespace(
            coordinator=FakeSwitchCoordinator(
                {32: _device_state({output: False for output in modbus.OUTPUTS})}
            ),
            clients={32: client},
            device_metadata={
                32: _metadata(
                    model=modbus.MR6CU_MODEL,
                    supports_inputs=False,
                    supports_press_counters=False,
                    supports_mapping_matrix=False,
                )
            },
        )
        add_calls: list[tuple[list[Any], dict[str, Any]]] = []

        def async_add_entities(entities: list[Any], **kwargs: Any) -> None:
            add_calls.append((entities, kwargs))

        await switch_platform.async_setup_entry(
            types.SimpleNamespace(), entry, async_add_entities
        )

        self.assertEqual(add_calls[0][0][0].device_info["model"], "WB-MR6CU v.2")
        self.assertEqual(add_calls[0][0][0].device_info["name"], "WB-MR6CU 32")

    async def test_setup_skips_relay_switches_for_wb_mcm8(self) -> None:
        entry = _bus_entry(
            subentries={
                "subentry-32": _device_subentry(
                    32,
                    firmware_version="1.3.2",
                    model=const.MODEL_WB_MCM8,
                )
            }
        )
        entry.runtime_data = types.SimpleNamespace(
            coordinator=FakeSwitchCoordinator(
                {
                    32: _device_state(
                        input_states={
                            input_number: False
                            for input_number in modbus.MCM8_INPUTS
                        }
                    )
                }
            ),
            clients={32: FakeRelayClient()},
            device_metadata={
                32: _metadata(
                    model=modbus.MCM8_MODEL,
                    firmware_version="1.3.2",
                    supports_mapping_matrix=False,
                    supports_relay_state_discrete_inputs=False,
                )
            },
        )
        add_calls: list[tuple[list[Any], dict[str, Any]]] = []

        def async_add_entities(entities: list[Any], **kwargs: Any) -> None:
            add_calls.append((entities, kwargs))

        await switch_platform.async_setup_entry(
            types.SimpleNamespace(), entry, async_add_entities
        )

        self.assertEqual(add_calls, [])

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

    async def test_turn_on_and_off_use_command_coils_without_one_shot_support(
        self,
    ) -> None:
        entity, client, coordinator = _relay_switch(
            output=3,
            relay_states={3: False},
        )

        await entity.async_turn_on()

        self.assertEqual(client.calls, [("set_relay_command", 3, True)])
        self.assertTrue(entity.is_on)
        self.assertEqual(entity.async_write_ha_state_calls, 1)
        self.assertEqual(coordinator.async_request_refresh_calls, 0)

        await entity.async_turn_off()

        self.assertEqual(
            client.calls,
            [
                ("set_relay_command", 3, True),
                ("set_relay_command", 3, False),
            ],
        )
        self.assertFalse(entity.is_on)
        self.assertEqual(entity.async_write_ha_state_calls, 2)
        self.assertEqual(coordinator.async_request_refresh_calls, 0)

    async def test_toggle_uses_command_coil_inverse_without_one_shot_support(
        self,
    ) -> None:
        entity, client, coordinator = _relay_switch(
            output=4,
            relay_states={4: False},
        )

        await entity.async_toggle()

        self.assertEqual(client.calls, [("set_relay_command", 4, True)])
        self.assertTrue(entity.is_on)
        self.assertEqual(entity.async_write_ha_state_calls, 1)
        self.assertEqual(coordinator.async_request_refresh_calls, 0)

    async def test_new_firmware_uses_one_shot_relay_commands(self) -> None:
        entity, client, _coordinator = _relay_switch(
            output=3,
            relay_states={3: False},
            supports_relay_one_shot_commands=True,
        )

        await entity.async_turn_on()
        await entity.async_turn_off()
        await entity.async_toggle()

        self.assertEqual(client.calls, [("turn_on", 3), ("turn_off", 3), ("toggle", 3)])

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
