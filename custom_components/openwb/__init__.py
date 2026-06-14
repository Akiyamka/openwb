"""openWB integration for Home Assistant."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from contextlib import suppress
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any, Mapping

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
    SUBENTRY_TYPE_DEVICE,
    PARITY_VALUES,
    STOPBITS_VALUES,
)
from .wb_mr6c_modbus import (
    PressCounterEvent,
    ModbusTransport,
    PymodbusSerialTransport,
    WBMR6CModbus,
    WBMR6CModbusConnectionError,
    WBMR6CModbusError,
    firmware_supports_press_counters,
    firmware_supports_relay_state_discrete_inputs,
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

    transport: ModbusTransport
    coordinator: WBMR6CBusCoordinator
    clients: dict[int, WBMR6CModbus]
    device_metadata: dict[int, WBMR6CDeviceMetadata]
    remove_coordinator_listener: Callable[[], None]


@dataclass(frozen=True, slots=True)
class WBMR6CDeviceMetadata:
    """Static device metadata retained for polling feature gates."""

    model: str | None
    firmware_version: str | None
    supports_press_counters: bool
    supports_relay_state_discrete_inputs: bool


@dataclass(frozen=True, slots=True)
class WBMR6CDeviceState:
    """Live WB-MR6C state read by the bus coordinator."""

    input_states: dict[int, bool]
    press_counts: dict[tuple[int, str], int]
    relay_states: dict[int, bool]
    relay_commands: dict[int, bool]


@dataclass(frozen=True, slots=True)
class WBMR6CPressEvent:
    """Detected press event emitted by the bus coordinator."""

    device_id: int
    input_number: int
    event_type: str
    counter: int
    delta: int
    sequence: int


class WBMR6CBusCoordinator(DataUpdateCoordinator):
    """Poll all WB-MR6C devices on one serial bus sequentially."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        clients: dict[int, WBMR6CModbus],
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
        self.clients = clients
        self.device_metadata = device_metadata
        self.press_events: dict[tuple[int, int, str], WBMR6CPressEvent] = {}
        self._previous_press_counts: dict[tuple[int, int, str], int] = {}
        self._press_event_sequences: dict[tuple[int, int, str], int] = {}

    async def _async_update_data(self) -> dict[int, WBMR6CDeviceState]:
        """Fetch one live-state snapshot for all currently configured devices."""
        data: dict[int, WBMR6CDeviceState] = {}
        connection_errors: dict[int, WBMR6CModbusConnectionError] = {}
        for device_id in self.clients:
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
            "remove and re-add the integration",
            entry.entry_id,
        )
        return False

    config_entries_manager = getattr(hass, "config_entries", None)
    update_entry = getattr(config_entries_manager, "async_update_entry", None)
    if callable(update_entry):
        update_entry(entry, version=CONFIG_ENTRY_VERSION)
    elif hasattr(entry, "version"):
        entry.version = CONFIG_ENTRY_VERSION

    return True


async def async_setup_entry(hass: HomeAssistant, entry: OpenWBConfigEntry) -> bool:
    """Set up openWB from a config entry."""
    bus_config = _bus_config_from_entry_data(entry.data)
    if bus_config is None:
        _LOGGER.error(
            "openWB config entry %s is missing serial bus settings; remove and "
            "re-add the integration",
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
        async_on_unload(add_update_listener(_async_reload_entry))


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload an openWB bus entry so runtime clients match subentries."""
    await hass.config_entries.async_reload(entry.entry_id)


def _bus_config_from_entry_data(data: Mapping[str, Any]) -> OpenWBBusConfig | None:
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


def _is_positive_int(value: Any) -> bool:
    """Return whether value is a positive integer, excluding bool."""
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


async def _async_device_clients_from_subentries(
    entry: ConfigEntry,
    transport: ModbusTransport,
) -> tuple[dict[int, WBMR6CModbus], dict[int, WBMR6CDeviceMetadata]]:
    """Create one client and metadata record for each configured device subentry."""
    clients: dict[int, WBMR6CModbus] = {}
    device_metadata: dict[int, WBMR6CDeviceMetadata] = {}

    for subentry_data in _device_subentry_data(entry):
        device_id = _device_id_from_subentry_data(subentry_data)
        if device_id is None:
            _LOGGER.warning(
                "Skipping openWB device subentry with invalid device id: %s",
                subentry_data.get(CONF_DEVICE_ID),
            )
            continue

        client = WBMR6CModbus(transport, device_id=device_id)
        clients[device_id] = client
        device_metadata[device_id] = await _async_device_metadata(
            client,
            subentry_data,
        )

    return clients, device_metadata


def _device_subentry_data(entry: ConfigEntry) -> Iterable[Mapping[str, Any]]:
    """Yield raw data for configured device subentries on a bus entry."""
    for subentry in getattr(entry, "subentries", {}).values():
        subentry_type = getattr(subentry, "subentry_type", SUBENTRY_TYPE_DEVICE)
        if subentry_type != SUBENTRY_TYPE_DEVICE:
            continue

        data = getattr(subentry, "data", {})
        if isinstance(data, Mapping):
            yield data


def _device_id_from_subentry_data(data: Mapping[str, Any]) -> int | None:
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
    client: WBMR6CModbus,
    subentry_data: Mapping[str, Any],
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

    return WBMR6CDeviceMetadata(
        model=model,
        firmware_version=firmware_version,
        supports_press_counters=_supports_press_counters(firmware_version),
        supports_relay_state_discrete_inputs=(
            _supports_relay_state_discrete_inputs(firmware_version)
        ),
    )


async def _async_read_device_state(
    client: WBMR6CModbus,
    metadata: WBMR6CDeviceMetadata,
) -> WBMR6CDeviceState:
    """Read one device state snapshot, honoring firmware-dependent features."""
    press_counts: dict[tuple[int, str], int] = {}
    if metadata.supports_press_counters:
        for event in _PRESS_COUNTER_EVENTS:
            counter_values = await client.read_press_counters(event)
            for input_number, count in counter_values.items():
                press_counts[(input_number, _PRESS_COUNTER_EVENT_TYPES[event])] = count

    input_states = await client.read_input_states()
    relay_commands = await client.read_relay_commands()

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


def _non_empty_string(value: Any) -> str | None:
    """Return stripped non-empty strings only."""
    if isinstance(value, str):
        value = value.strip()
        if value:
            return value
    return None


def _supports_press_counters(firmware_version: str | None) -> bool:
    """Return whether firmware metadata enables press-counter polling."""
    if firmware_version is None:
        return False
    try:
        return firmware_supports_press_counters(firmware_version)
    except ValueError:
        return False


def _supports_relay_state_discrete_inputs(firmware_version: str | None) -> bool:
    """Return whether firmware metadata enables actual relay-state polling."""
    if firmware_version is None:
        return False
    try:
        return firmware_supports_relay_state_discrete_inputs(firmware_version)
    except ValueError:
        return False


_UNKNOWN_DEVICE_METADATA = WBMR6CDeviceMetadata(
    model=None,
    firmware_version=None,
    supports_press_counters=False,
    supports_relay_state_discrete_inputs=False,
)
