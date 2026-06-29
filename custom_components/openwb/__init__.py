"""openWB integration for Home Assistant."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from contextlib import suppress
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import TypeGuard, override

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONFIG_ENTRY_VERSION,
    CONF_BAUDRATE,
    CONF_DEVICE_ID,
    CONF_FIRMWARE_VERSION,
    CONF_MODEL,
    CONF_PARITY,
    CONF_SERIAL_PORT,
    CONF_STOPBITS,
    DOMAIN,
    PARITY_VALUES,
    STOPBITS_VALUES,
    SUBENTRY_TYPE_DEVICE,
)
from .devices import (
    create_device_client,
    device_metadata_from_identification,
    device_model_display_name as _registry_device_model_display_name,
    device_name as _registry_device_name,
    unknown_device_metadata,
)
from .devices.base import OpenWBDeviceClient, OpenWBDeviceMetadata, OpenWBDeviceState
from .mapping_matrix import OpenWBMappingMatrixBackend
from .settings import OpenWBSettingsBackend
from .transport import (
    FastModbusSerialTransport as PymodbusSerialTransport,
    ManagedModbusTransport,
    ModbusTransport,
)
from .wb_mr6c_modbus import (
    COIL_RELAY_COMMAND_BASE,
    DISCRETE_INPUT_STATE_BASE,
    DISCRETE_RELAY_STATE_BASE,
    FastModbusEventPriority,
    FastModbusEventRange,
    FastModbusEventTransport,
    FastModbusRegisterEvent,
    FastModbusRegisterType,
    PressCounterEvent,
    input_level_discrete_input_address,
    is_fast_modbus_event_transport,
    WBMR6CModbusConnectionError,
    WBMR6CModbusError,
    press_counter_delta,
)

_LOGGER = logging.getLogger(__name__)
PLATFORMS: tuple[str, ...] = ("binary_sensor", "event", "switch")
_BUS_UPDATE_INTERVAL = timedelta(seconds=1)
_PRESS_COUNTER_EVENTS = (
    PressCounterEvent.SHORT,
    PressCounterEvent.LONG,
    PressCounterEvent.DOUBLE,
    PressCounterEvent.SHORT_THEN_LONG,
)
PRESS_EVENT_TYPES = ("short", "long", "double", "short-then-long")
_PRESS_COUNTER_EVENT_TYPES = dict(zip(_PRESS_COUNTER_EVENTS, PRESS_EVENT_TYPES))
_FAST_MODBUS_EVENT_DRAIN_LIMIT = 16

WBMR6CDeviceMetadata = OpenWBDeviceMetadata
WBMR6CDeviceState = OpenWBDeviceState


@dataclass(frozen=True, slots=True)
class OpenWBBusConfig:
    """Validated serial bus configuration."""

    serial_port: str
    baudrate: int
    parity: str
    stopbits: int


@dataclass(slots=True)
class OpenWBBusRuntimeData:
    """Runtime data for one openWB serial bus."""

    transport: ManagedModbusTransport
    coordinator: WBMR6CBusCoordinator
    clients: dict[int, OpenWBDeviceClient]
    settings: OpenWBSettingsBackend
    mapping_matrix: OpenWBMappingMatrixBackend
    device_metadata: dict[int, WBMR6CDeviceMetadata]
    remove_coordinator_listener: Callable[[], None]


@dataclass(frozen=True, slots=True)
class WBMR6CPressEvent:
    """Detected press event emitted by the bus coordinator."""

    device_id: int
    input_number: int
    event_type: str
    counter: int
    delta: int
    sequence: int


class WBMR6CBusCoordinator(DataUpdateCoordinator[dict[int, WBMR6CDeviceState]]):
    """Maintain live state for all openWB devices on one serial bus."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        clients: dict[int, OpenWBDeviceClient],
        device_metadata: dict[int, WBMR6CDeviceMetadata],
    ) -> None:
        """Initialize the bus coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} {entry.entry_id}",
            update_interval=_BUS_UPDATE_INTERVAL,
            config_entry=entry,
        )
        self.clients: dict[int, OpenWBDeviceClient] = clients
        self.device_metadata: dict[int, WBMR6CDeviceMetadata] = device_metadata
        self.press_events: dict[tuple[int, int, str], WBMR6CPressEvent] = {}
        self._previous_press_counts: dict[tuple[int, int, str], int] = {}
        self._press_event_sequences: dict[tuple[int, int, str], int] = {}
        self._fast_modbus_configured_devices: set[int] = set()
        self._fast_modbus_disabled_devices: set[int] = set()

    @override
    async def _async_update_data(self) -> dict[int, WBMR6CDeviceState]:
        """Fetch one live-state snapshot for all currently configured devices."""
        data: dict[int, WBMR6CDeviceState] = {}
        connection_errors: dict[int, WBMR6CModbusConnectionError] = {}
        fast_data: dict[int, WBMR6CDeviceState] = {}
        _fast_failed_devices: set[int] = set()

        fast_transport = _fast_modbus_transport_from_clients(self.clients)
        if fast_transport is not None:
            fast_data, _fast_failed_devices = await self._async_fast_modbus_data(
                fast_transport
            )

        for device_id in self.clients:
            if device_id in fast_data:
                data[device_id] = fast_data[device_id]
                continue

            client = self.clients[device_id]
            metadata = self.device_metadata.get(device_id, _UNKNOWN_DEVICE_METADATA)
            try:
                data[device_id] = await _async_read_device_state(client, metadata)
            except WBMR6CModbusConnectionError as err:
                connection_errors[device_id] = err
                _LOGGER.debug(
                    "Skipping unreachable openWB device %s during bus poll: %s",
                    device_id,
                    err,
                )
            except WBMR6CModbusError as err:
                _LOGGER.debug(
                    "Skipping unavailable openWB device %s during bus poll: %s",
                    device_id,
                    err,
                )

        self._update_press_events(data)

        if self.clients and not data and len(connection_errors) == len(self.clients):
            first_error = next(iter(connection_errors.values()))
            raise UpdateFailed(
                "Unable to communicate with any openWB device"
            ) from first_error

        return data

    async def _async_fast_modbus_data(
        self,
        transport: FastModbusEventTransport,
    ) -> tuple[dict[int, WBMR6CDeviceState], set[int]]:
        """Return Fast Modbus state updates and devices that need polling fallback."""
        fast_device_ids = [
            device_id
            for device_id, metadata in self.device_metadata.items()
            if metadata.supports_fast_modbus_events
            and device_id not in self._fast_modbus_disabled_devices
            and _fast_modbus_event_ranges(metadata)
        ]
        if not fast_device_ids:
            return {}, set()

        data: dict[int, WBMR6CDeviceState] = {}
        failed_devices: set[int] = set()
        previous_data = self.data or {}
        for device_id in fast_device_ids:
            client = self.clients.get(device_id)
            metadata = self.device_metadata.get(device_id, _UNKNOWN_DEVICE_METADATA)
            if client is None:
                continue

            if device_id not in self._fast_modbus_configured_devices:
                try:
                    ranges = _fast_modbus_event_ranges(metadata)
                    configuration = await transport.configure_fast_modbus_events(
                        device_id,
                        ranges,
                    )
                    if not _fast_modbus_event_ranges_enabled(
                        ranges,
                        configuration.enabled,
                    ):
                        raise WBMR6CModbusError(
                            "Fast Modbus did not enable all requested events"
                        )
                    self._fast_modbus_configured_devices.add(device_id)
                except WBMR6CModbusError as err:
                    failed_devices.add(device_id)
                    self._fast_modbus_disabled_devices.add(device_id)
                    _LOGGER.debug(
                        "Disabling Fast Modbus events for openWB device %s: %s",
                        device_id,
                        err,
                    )
                    continue

            try:
                previous_state = previous_data.get(device_id)
                if previous_state is None:
                    previous_state = await _async_read_device_state(client, metadata)
                data[device_id] = previous_state
            except WBMR6CModbusError as err:
                failed_devices.add(device_id)
                _LOGGER.debug(
                    "Could not seed Fast Modbus state for openWB device %s: %s",
                    device_id,
                    err,
                )

        if not data:
            return {}, failed_devices

        try:
            events = await _async_drain_fast_modbus_events(transport)
        except WBMR6CModbusError as err:
            _LOGGER.debug(
                "Fast Modbus event poll failed, falling back to standard polling: %s",
                err,
            )
            return {}, set(data) | failed_devices

        for event in events:
            metadata = self.device_metadata.get(event.device_id)
            state = data.get(event.device_id)
            if metadata is None or state is None:
                continue
            if _is_fast_modbus_reset_event(event):
                self._fast_modbus_configured_devices.discard(event.device_id)
                continue
            data[event.device_id] = _apply_fast_modbus_event(state, event, metadata)

        return data, failed_devices

    def _update_press_events(self, data: dict[int, WBMR6CDeviceState]) -> None:
        """Update counter baselines and expose newly detected press events."""
        seen_keys: set[tuple[int, int, str]] = set()

        for device_id, state in data.items():
            for (input_number, event_type), current_count in state.press_counts.items():
                key = (device_id, input_number, event_type)
                seen_keys.add(key)
                previous_count = self._previous_press_counts.get(key)
                self._previous_press_counts[key] = current_count

                delta = press_counter_delta(previous_count, current_count)
                if delta == 0:
                    continue

                sequence = self._press_event_sequences.get(key, 0) + 1
                self._press_event_sequences[key] = sequence
                self.press_events[key] = WBMR6CPressEvent(
                    device_id=device_id,
                    input_number=input_number,
                    event_type=event_type,
                    counter=current_count,
                    delta=delta,
                    sequence=sequence,
                )

        for key in list(self._previous_press_counts):
            if key not in seen_keys:
                del self._previous_press_counts[key]


OpenWBConfigEntry = ConfigEntry[OpenWBBusRuntimeData]


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old openWB config entries."""
    if entry.version >= CONFIG_ENTRY_VERSION:
        return True

    if _bus_config_from_entry_data(entry.data) is None:
        _LOGGER.error(
            "openWB config entry %s cannot be migrated to a serial bus entry; "
            + "remove and re-add the integration",
            entry.entry_id,
        )
        return False

    config_entries_manager = getattr(hass, "config_entries", None)
    update_entry = getattr(config_entries_manager, "async_update_entry", None)
    if callable(update_entry):
        _ = update_entry(entry, version=CONFIG_ENTRY_VERSION)
    elif hasattr(entry, "version"):
        entry.version = CONFIG_ENTRY_VERSION

    return True


async def async_setup_entry(hass: HomeAssistant, entry: OpenWBConfigEntry) -> bool:
    """Set up openWB from a config entry."""
    bus_config = _bus_config_from_entry_data(entry.data)
    if bus_config is None:
        _LOGGER.error(
            "openWB config entry %s is missing serial bus settings; remove and "
            + "re-add the integration",
            entry.entry_id,
        )
        return False

    try:
        transport = PymodbusSerialTransport(
            bus_config.serial_port,
            baudrate=bus_config.baudrate,
            parity=bus_config.parity,
            stopbits=bus_config.stopbits,
        )
        await transport.connect()
    except WBMR6CModbusConnectionError as err:
        raise ConfigEntryNotReady(
            f"Unable to open openWB serial bus {bus_config.serial_port}"
        ) from err

    remove_coordinator_listener: Callable[[], None] | None = None
    try:
        clients, device_metadata = await _async_device_clients_from_subentries(
            entry,
            transport,
        )
        coordinator = WBMR6CBusCoordinator(hass, entry, clients, device_metadata)
        remove_coordinator_listener = coordinator.async_add_listener(
            _noop_coordinator_listener
        )
        entry.runtime_data = OpenWBBusRuntimeData(
            transport=transport,
            coordinator=coordinator,
            clients=clients,
            settings=OpenWBSettingsBackend(clients),
            mapping_matrix=OpenWBMappingMatrixBackend(clients, device_metadata),
            device_metadata=device_metadata,
            remove_coordinator_listener=remove_coordinator_listener,
        )
        await coordinator.async_config_entry_first_refresh()
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except BaseException:
        if remove_coordinator_listener is not None:
            remove_coordinator_listener()
        with suppress(WBMR6CModbusConnectionError):
            await transport.close()
        raise

    _register_entry_update_reload_listener(entry)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: OpenWBConfigEntry) -> bool:
    """Unload an openWB config entry."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False

    entry.runtime_data.remove_coordinator_listener()
    await entry.runtime_data.transport.close()
    return True


def _noop_coordinator_listener() -> None:
    """Keep the bus coordinator active before entity platforms subscribe."""


def _register_entry_update_reload_listener(entry: ConfigEntry) -> None:
    """Reload the bus entry after config entry or subentry changes."""
    add_update_listener = getattr(entry, "add_update_listener", None)
    async_on_unload = getattr(entry, "async_on_unload", None)
    if callable(add_update_listener) and callable(async_on_unload):
        _ = async_on_unload(add_update_listener(_async_reload_entry))


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload an openWB bus entry so runtime clients match subentries."""
    _ = await hass.config_entries.async_reload(entry.entry_id)


def _bus_config_from_entry_data(data: Mapping[str, object]) -> OpenWBBusConfig | None:
    """Return validated bus config entry data, or None for unsupported entries."""
    serial_port = data.get(CONF_SERIAL_PORT)
    baudrate = data.get(CONF_BAUDRATE)
    parity = data.get(CONF_PARITY)
    stopbits = data.get(CONF_STOPBITS)

    if not isinstance(serial_port, str) or not serial_port.strip():
        return None
    if not _is_positive_int(baudrate):
        return None
    if not isinstance(parity, str) or parity not in PARITY_VALUES:
        return None
    if not _is_positive_int(stopbits) or stopbits not in STOPBITS_VALUES:
        return None

    return OpenWBBusConfig(
        serial_port=serial_port,
        baudrate=baudrate,
        parity=parity,
        stopbits=stopbits,
    )


def _is_positive_int(value: object) -> TypeGuard[int]:
    """Return whether value is a positive integer, excluding bool."""
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


async def _async_device_clients_from_subentries(
    entry: ConfigEntry,
    transport: ModbusTransport,
) -> tuple[dict[int, OpenWBDeviceClient], dict[int, WBMR6CDeviceMetadata]]:
    """Create one client and metadata record for each configured device subentry."""
    clients: dict[int, OpenWBDeviceClient] = {}
    device_metadata: dict[int, WBMR6CDeviceMetadata] = {}

    for subentry_data in _device_subentry_data(entry):
        device_id = device_id_from_subentry_data(subentry_data)
        if device_id is None:
            _LOGGER.warning(
                "Skipping openWB device subentry with invalid device id: %s",
                subentry_data.get(CONF_DEVICE_ID),
            )
            continue

        stored_model = _non_empty_string(subentry_data.get(CONF_MODEL))
        identification_client = create_device_client(
            transport, device_id, stored_model
        )
        metadata = await _async_device_metadata(
            identification_client,
            subentry_data,
        )
        clients[device_id] = create_device_client(
            transport, device_id, metadata.model
        )
        device_metadata[device_id] = metadata

    return clients, device_metadata


def _device_subentry_data(entry: ConfigEntry) -> Iterable[Mapping[str, object]]:
    """Yield raw data for configured device subentries on a bus entry."""
    for subentry in entry.subentries.values():
        if subentry.subentry_type != SUBENTRY_TYPE_DEVICE:
            continue

        data: Mapping[str, object] = subentry.data
        yield data


def device_id_from_subentry_data(data: Mapping[str, object]) -> int | None:
    """Return a valid Modbus device id from subentry data, if present."""
    device_id = data.get(CONF_DEVICE_ID)
    if (
        isinstance(device_id, int)
        and not isinstance(device_id, bool)
        and 1 <= device_id <= 247
    ):
        return device_id
    return None


async def _async_device_metadata(
    client: OpenWBDeviceClient,
    subentry_data: Mapping[str, object],
) -> WBMR6CDeviceMetadata:
    """Read model and firmware metadata for one configured device."""
    stored_model = _non_empty_string(subentry_data.get(CONF_MODEL))
    stored_firmware_version = _non_empty_string(
        subentry_data.get(CONF_FIRMWARE_VERSION)
    )

    try:
        model = _non_empty_string(await client.read_model())
    except WBMR6CModbusError as err:
        _LOGGER.debug(
            "Could not refresh openWB device %s model during setup: %s",
            client.device_id,
            err,
        )
        model = stored_model

    try:
        firmware_version = _non_empty_string(await client.read_firmware_version())
    except WBMR6CModbusError as err:
        _LOGGER.debug(
            "Could not refresh openWB device %s firmware during setup: %s",
            client.device_id,
            err,
        )
        firmware_version = stored_firmware_version

    model = model or stored_model
    firmware_version = firmware_version or stored_firmware_version

    return device_metadata_from_identification(model, firmware_version)


async def _async_read_device_state(
    client: OpenWBDeviceClient,
    metadata: WBMR6CDeviceMetadata,
) -> WBMR6CDeviceState:
    """Read one device state snapshot, honoring firmware-dependent features."""
    press_counts: dict[tuple[int, str], int] = {}
    if metadata.supports_press_counters:
        for event in _PRESS_COUNTER_EVENTS:
            counter_values = await client.read_press_counters(
                event,
                metadata.input_numbers,
                input_registers=metadata.press_counter_input_registers,
            )
            for input_number, count in counter_values.items():
                press_counts[(input_number, _PRESS_COUNTER_EVENT_TYPES[event])] = count

    input_states = (
        await client.read_input_states(metadata.input_numbers)
        if metadata.supports_inputs
        else {}
    )
    relay_commands = (
        await client.read_relay_commands() if metadata.output_numbers else {}
    )

    if metadata.supports_relay_state_discrete_inputs:
        relay_states = await client.read_relay_states()
    else:
        relay_states = dict(relay_commands)

    return WBMR6CDeviceState(
        input_states=input_states,
        press_counts=press_counts,
        relay_states=relay_states,
        relay_commands=relay_commands,
    )


def _fast_modbus_transport_from_clients(
    clients: Mapping[int, OpenWBDeviceClient],
) -> FastModbusEventTransport | None:
    """Return the shared transport if it supports Fast Modbus events."""
    for client in clients.values():
        transport = getattr(client, "transport", None)
        if is_fast_modbus_event_transport(transport):
            return transport
    return None


def _fast_modbus_event_ranges(
    metadata: WBMR6CDeviceMetadata,
) -> tuple[FastModbusEventRange, ...]:
    """Build Fast Modbus register-change ranges for live-state data."""
    ranges: list[FastModbusEventRange] = []

    if metadata.supports_inputs and metadata.input_numbers:
        input_count = max(
            input_level_discrete_input_address(input_number)
            for input_number in metadata.input_numbers
        ) + 1
        ranges.append(
            FastModbusEventRange(
                FastModbusRegisterType.DISCRETE_INPUT,
                DISCRETE_INPUT_STATE_BASE,
                (FastModbusEventPriority.LOW,) * input_count,
            )
        )

    if metadata.output_numbers:
        ranges.append(
            FastModbusEventRange(
                FastModbusRegisterType.COIL,
                COIL_RELAY_COMMAND_BASE,
                (FastModbusEventPriority.LOW,) * len(metadata.output_numbers),
            )
        )
        if metadata.supports_relay_state_discrete_inputs:
            ranges.append(
                FastModbusEventRange(
                    FastModbusRegisterType.DISCRETE_INPUT,
                    DISCRETE_RELAY_STATE_BASE,
                    (FastModbusEventPriority.LOW,) * len(metadata.output_numbers),
                )
            )

    if metadata.supports_press_counters and metadata.input_numbers:
        register_type = (
            FastModbusRegisterType.INPUT_REGISTER
            if metadata.press_counter_input_registers
            else FastModbusRegisterType.HOLDING_REGISTER
        )
        input_count = _press_counter_event_range_count(metadata.input_numbers)
        for event in _PRESS_COUNTER_EVENTS:
            ranges.append(
                FastModbusEventRange(
                    register_type,
                    int(event),
                    (FastModbusEventPriority.HIGH,) * input_count,
                )
            )

    return tuple(ranges)


def _fast_modbus_event_ranges_enabled(
    ranges: tuple[FastModbusEventRange, ...],
    enabled: frozenset[tuple[int, int]],
) -> bool:
    """Return whether the device enabled every requested fast-event register."""
    expected = {
        (int(range_item.register_type), address)
        for range_item in ranges
        for address in range(
            range_item.address,
            range_item.address + len(tuple(range_item.priorities)),
        )
    }
    return expected <= enabled


def _press_counter_event_range_count(input_numbers: tuple[int, ...]) -> int:
    indexes = [
        _input_register_event_index(input_number, input_numbers)
        for input_number in input_numbers
    ]
    return max(indexes) + 1


async def _async_drain_fast_modbus_events(
    transport: FastModbusEventTransport,
) -> tuple[FastModbusRegisterEvent, ...]:
    """Read pending Fast Modbus events until the bus reports none."""
    events: list[FastModbusRegisterEvent] = []
    for _attempt in range(_FAST_MODBUS_EVENT_DRAIN_LIMIT):
        packet_events = await transport.read_fast_modbus_events()
        if not packet_events:
            break
        events.extend(packet_events)
    return tuple(events)


def _apply_fast_modbus_event(
    state: WBMR6CDeviceState,
    event: FastModbusRegisterEvent,
    metadata: WBMR6CDeviceMetadata,
) -> WBMR6CDeviceState:
    """Merge one Fast Modbus register-change event into a cached state."""
    input_states = dict(state.input_states)
    press_counts = dict(state.press_counts)
    relay_states = dict(state.relay_states)
    relay_commands = dict(state.relay_commands)

    if event.value is None:
        return state

    if event.register_type == int(FastModbusRegisterType.DISCRETE_INPUT):
        input_number = _input_number_for_discrete_event(event.address, metadata)
        if input_number is not None:
            input_states[input_number] = bool(event.value)
        output = _output_for_relay_state_event(event.address, metadata)
        if output is not None:
            relay_states[output] = bool(event.value)

    if event.register_type == int(FastModbusRegisterType.COIL):
        output = _output_for_relay_command_event(event.address, metadata)
        if output is not None:
            relay_commands[output] = bool(event.value)
            if not metadata.supports_relay_state_discrete_inputs:
                relay_states[output] = bool(event.value)

    if event.register_type in {
        int(FastModbusRegisterType.HOLDING_REGISTER),
        int(FastModbusRegisterType.INPUT_REGISTER),
    }:
        press_key = _press_counter_key_for_register_event(event, metadata)
        if press_key is not None:
            press_counts[press_key] = int(event.value)

    return WBMR6CDeviceState(
        input_states=input_states,
        press_counts=press_counts,
        relay_states=relay_states,
        relay_commands=relay_commands,
    )


def _is_fast_modbus_reset_event(event: FastModbusRegisterEvent) -> bool:
    return event.register_type == 0x0F and event.address == 0


def _input_number_for_discrete_event(
    address: int,
    metadata: WBMR6CDeviceMetadata,
) -> int | None:
    if not metadata.supports_inputs:
        return None
    for input_number in metadata.input_numbers:
        if address == input_level_discrete_input_address(input_number):
            return input_number
    return None


def _output_for_relay_state_event(
    address: int,
    metadata: WBMR6CDeviceMetadata,
) -> int | None:
    output = address - DISCRETE_RELAY_STATE_BASE + 1
    if output in metadata.output_numbers:
        return output
    return None


def _output_for_relay_command_event(
    address: int,
    metadata: WBMR6CDeviceMetadata,
) -> int | None:
    output = address - COIL_RELAY_COMMAND_BASE + 1
    if output in metadata.output_numbers:
        return output
    return None


def _press_counter_key_for_register_event(
    event: FastModbusRegisterEvent,
    metadata: WBMR6CDeviceMetadata,
) -> tuple[int, str] | None:
    if not metadata.supports_press_counters:
        return None
    expected_register_type = (
        int(FastModbusRegisterType.INPUT_REGISTER)
        if metadata.press_counter_input_registers
        else int(FastModbusRegisterType.HOLDING_REGISTER)
    )
    if event.register_type != expected_register_type:
        return None

    for counter_event in _PRESS_COUNTER_EVENTS:
        index = event.address - int(counter_event)
        if index < 0:
            continue
        input_number = _input_number_for_register_event_index(
            index,
            metadata.input_numbers,
        )
        if input_number is not None:
            return input_number, _PRESS_COUNTER_EVENT_TYPES[counter_event]
    return None


def _input_number_for_register_event_index(
    index: int,
    input_numbers: tuple[int, ...],
) -> int | None:
    for input_number in input_numbers:
        if _input_register_event_index(input_number, input_numbers) == index:
            return input_number
    return None


def _input_register_event_index(
    input_number: int,
    input_numbers: tuple[int, ...],
) -> int:
    if input_number == 0:
        return 7
    if 8 in input_numbers and input_number == 8:
        return 7
    return input_number - 1


def _non_empty_string(value: object) -> str | None:
    """Return stripped non-empty strings only."""
    if isinstance(value, str):
        value = value.strip()
        if value:
            return value
    return None


def device_model_display_name(model: str | None) -> str:
    """Return a Home Assistant device-info model name."""
    return _registry_device_model_display_name(model)


def device_name(model: str | None, device_id: int) -> str:
    """Return a Home Assistant device display name."""
    return _registry_device_name(model, device_id)


_UNKNOWN_DEVICE_METADATA = unknown_device_metadata()


async def async_setup(hass: HomeAssistant, _config: Mapping[str, object]) -> bool:
    """Set up integration-level frontend assets and websocket commands."""
    from .frontend import async_setup_frontend

    await async_setup_frontend(hass)
    return True
