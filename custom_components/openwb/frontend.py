"""Frontend panel and websocket API for the openWB integration."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, TypedDict, cast

import voluptuous as vol

from homeassistant.components import panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.components.websocket_api import async_register_command
from homeassistant.components.websocket_api.connection import ActiveConnection
from homeassistant.components.websocket_api.const import (
    ERR_INVALID_FORMAT,
    ERR_NOT_FOUND,
    ERR_NOT_SUPPORTED,
)
from homeassistant.components.websocket_api.decorators import (
    async_response,
    require_admin,
    websocket_command,
)
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .devices import device_model_display_name, device_name
from .devices.base import OpenWBDeviceMetadata
from .mapping_matrix import OpenWBMappingMatrixBackend
from .settings import OpenWBSettingsBackend
from .wb_mr6c_modbus import (
    INPUT_0,
    INPUTS,
    OUTPUTS,
    InputMode,
    MappingAction,
    MappingEvent,
)

PANEL_URL_PATH = DOMAIN
PANEL_WEB_COMPONENT = "openwb-mapping-panel"
PANEL_JS_FILENAME = "openwb-panel.js"
STATIC_URL_PATH = f"/{DOMAIN}_static"
STATIC_DIR = Path(__file__).with_name("frontend")

DATA_FRONTEND_REGISTERED = f"{DOMAIN}_frontend_registered"

_ENTRY_ID_SCHEMA = str
_DEVICE_ID_SCHEMA = vol.All(vol.Coerce(int), vol.Range(min=1, max=247))
_INPUT_NUMBER_SCHEMA = vol.All(vol.Coerce(int), vol.In(INPUTS))
_OUTPUT_SCHEMA = vol.All(vol.Coerce(int), vol.In(OUTPUTS))
_MAPPING_EVENT_SCHEMA = vol.All(
    vol.Coerce(int), vol.In(tuple(int(event) for event in MappingEvent))
)
_MAPPING_ACTION_SCHEMA = vol.All(
    vol.Coerce(int),
    vol.In(
        (
            int(MappingAction.OFF),
            int(MappingAction.ON),
            int(MappingAction.TOGGLE),
        )
    ),
)
_INPUT_MODE_SCHEMA = vol.All(
    vol.Coerce(int),
    vol.In(tuple(int(mode) for mode in InputMode if mode != InputMode.DISABLED)),
)
_MAPPING_RULE_SCHEMA = {
    vol.Required("input_number"): _INPUT_NUMBER_SCHEMA,
    vol.Required("event"): _MAPPING_EVENT_SCHEMA,
    vol.Required("action"): _MAPPING_ACTION_SCHEMA,
    vol.Required("outputs"): vol.All([_OUTPUT_SCHEMA], vol.Length(min=1)),
}
_INPUT_MODE_RULE_SCHEMA = {
    vol.Required("input_number"): _INPUT_NUMBER_SCHEMA,
    vol.Required("mode"): _INPUT_MODE_SCHEMA,
}
_MAPPING_BUTTON_EVENTS = frozenset(
    (
        MappingEvent.SHORT_PRESS,
        MappingEvent.LONG_PRESS,
        MappingEvent.DOUBLE_PRESS,
        MappingEvent.SHORT_THEN_LONG_PRESS,
    )
)
_MAPPING_EDGE_EVENTS = frozenset(
    (MappingEvent.FALLING_EDGE, MappingEvent.RISING_EDGE)
)


class MappingRule(TypedDict):
    """Compact frontend mapping rule."""

    input_number: int
    event: int
    action: int
    outputs: list[int]


class InputModeRule(TypedDict):
    """Compact frontend input mode rule."""

    input_number: int
    mode: int


class OpenWBFrontendRuntime(Protocol):
    """Runtime data surface used by the frontend websocket API."""

    mapping_matrix: OpenWBMappingMatrixBackend
    settings: OpenWBSettingsBackend
    device_metadata: dict[int, OpenWBDeviceMetadata]


async def async_setup_frontend(hass: HomeAssistant) -> None:
    """Register the openWB mapping panel, static assets, and websocket commands."""
    if hass.data.get(DATA_FRONTEND_REGISTERED):
        return

    hass.data[DATA_FRONTEND_REGISTERED] = True
    async_register_command(hass, websocket_openwb_config)
    async_register_command(hass, websocket_read_mapping_matrix)
    async_register_command(hass, websocket_write_mapping_matrix)

    await hass.http.async_register_static_paths(
        [StaticPathConfig(STATIC_URL_PATH, str(STATIC_DIR), False)]
    )
    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=PANEL_URL_PATH,
        webcomponent_name=PANEL_WEB_COMPONENT,
        sidebar_title="openWB",
        sidebar_icon="mdi:electric-switch",
        module_url=f"{STATIC_URL_PATH}/{PANEL_JS_FILENAME}",
        require_admin=True,
        config_panel_domain=DOMAIN,
    )


@websocket_command({"type": f"{DOMAIN}/config"})
@require_admin
@async_response
async def websocket_openwb_config(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, object]
) -> None:
    """Return mapping-capable openWB devices and frontend enum values."""
    connection.send_result(
        _message_id(msg),
        {
            "devices": _mapping_capable_devices(hass),
            "events": [
                {"value": int(event), "key": event.name.lower()}
                for event in MappingEvent
            ],
            "actions": [
                {"value": int(action), "key": action.name.lower()}
                for action in (
                    MappingAction.OFF,
                    MappingAction.ON,
                    MappingAction.TOGGLE,
                )
            ],
        },
    )


@websocket_command(
    {
        "type": f"{DOMAIN}/mapping_matrix/read",
        vol.Required("entry_id"): _ENTRY_ID_SCHEMA,
        vol.Required("device_id"): _DEVICE_ID_SCHEMA,
    }
)
@require_admin
@async_response
async def websocket_read_mapping_matrix(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, object]
) -> None:
    """Read all mapping matrices for one openWB device."""
    msg_id = _message_id(msg)
    entry_id = _message_str(msg, "entry_id")
    device_id = _message_int(msg, "device_id")
    runtime = _runtime_for_entry(hass, entry_id)
    if runtime is None:
        connection.send_error(
            msg_id, ERR_NOT_FOUND, "openWB config entry not found"
        )
        return

    metadata = runtime.device_metadata.get(device_id)
    if metadata is None:
        connection.send_error(msg_id, ERR_NOT_FOUND, "openWB device not found")
        return

    if not metadata.supports_mapping_matrix:
        connection.send_error(
            msg_id,
            ERR_NOT_SUPPORTED,
            "openWB device does not support mapping matrix",
        )
        return

    input_numbers = _sorted_input_numbers(metadata.input_numbers)
    output_numbers = tuple(metadata.output_numbers)
    matrices: dict[str, list[dict[str, int]]] = {}
    for event in MappingEvent:
        matrix = await runtime.mapping_matrix.read_mapping_matrix(device_id, event)
        matrices[str(int(event))] = _serialize_matrix(
            matrix, input_numbers, output_numbers
        )
    input_modes = await runtime.settings.read_input_modes(device_id)

    connection.send_result(
        msg_id,
        {
            "device": _serialize_device(entry_id, device_id, metadata),
            "input_modes": _serialize_input_modes(input_modes, input_numbers),
            "matrices": matrices,
        },
    )


@websocket_command(
    {
        "type": f"{DOMAIN}/mapping_matrix/write",
        vol.Required("entry_id"): _ENTRY_ID_SCHEMA,
        vol.Required("device_id"): _DEVICE_ID_SCHEMA,
        vol.Required("mappings"): [_MAPPING_RULE_SCHEMA],
        vol.Required("input_modes"): [_INPUT_MODE_RULE_SCHEMA],
    }
)
@require_admin
@async_response
async def websocket_write_mapping_matrix(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, object]
) -> None:
    """Write all mapping matrices for one openWB device from compact UI rules."""
    msg_id = _message_id(msg)
    entry_id = _message_str(msg, "entry_id")
    device_id = _message_int(msg, "device_id")
    runtime = _runtime_for_entry(hass, entry_id)
    if runtime is None:
        connection.send_error(
            msg_id, ERR_NOT_FOUND, "openWB config entry not found"
        )
        return

    metadata = runtime.device_metadata.get(device_id)
    if metadata is None:
        connection.send_error(msg_id, ERR_NOT_FOUND, "openWB device not found")
        return

    if not metadata.supports_mapping_matrix:
        connection.send_error(
            msg_id,
            ERR_NOT_SUPPORTED,
            "openWB device does not support mapping matrix",
        )
        return

    matrices = _empty_matrices()
    mapping_rules = _message_mapping_rules(msg)
    input_modes = _message_input_modes(msg)
    input_numbers = set(metadata.input_numbers)
    if (
        input_modes is None
        or set(input_modes) != input_numbers
        or not _input_modes_match_mapping_rules(mapping_rules, input_modes)
    ):
        connection.send_error(
            msg_id,
            ERR_INVALID_FORMAT,
            "openWB input mode does not match mapping events",
        )
        return

    for mapping in mapping_rules:
        event = MappingEvent(mapping["event"])
        action = MappingAction(mapping["action"])
        input_number = mapping["input_number"]
        for output in mapping["outputs"]:
            matrices[event][(input_number, output)] = action

    for event, matrix in matrices.items():
        await runtime.mapping_matrix.write_mapping_matrix(device_id, event, matrix)

    for input_number, mode in input_modes.items():
        await runtime.settings.set_input_mode(device_id, input_number, mode)

    connection.send_result(msg_id)


def _mapping_capable_devices(hass: HomeAssistant) -> list[dict[str, object]]:
    devices: list[dict[str, object]] = []
    for entry in hass.config_entries.async_entries(DOMAIN):
        runtime = getattr(entry, "runtime_data", None)
        if runtime is None:
            continue

        runtime_data = cast(OpenWBFrontendRuntime, runtime)
        for device_id, metadata in runtime_data.device_metadata.items():
            if not metadata.supports_mapping_matrix:
                continue
            devices.append(_serialize_device(entry.entry_id, device_id, metadata))
    return devices


def _runtime_for_entry(
    hass: HomeAssistant, entry_id: str
) -> OpenWBFrontendRuntime | None:
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.entry_id == entry_id:
            runtime = getattr(entry, "runtime_data", None)
            if runtime is None:
                return None
            return cast(OpenWBFrontendRuntime, runtime)
    return None


def _serialize_device(
    entry_id: str,
    device_id: int,
    metadata: OpenWBDeviceMetadata,
) -> dict[str, object]:
    return {
        "entry_id": entry_id,
        "device_id": device_id,
        "name": device_name(metadata.model, device_id),
        "model": device_model_display_name(metadata.model),
        "firmware_version": metadata.firmware_version,
        "input_numbers": list(_sorted_input_numbers(metadata.input_numbers)),
        "output_numbers": list(metadata.output_numbers),
    }


def _serialize_matrix(
    matrix: dict[tuple[int, int], int],
    input_numbers: tuple[int, ...],
    output_numbers: tuple[int, ...],
) -> list[dict[str, int]]:
    return [
        {
            "input_number": input_number,
            "output": output,
            "action": int(matrix.get((input_number, output), MappingAction.NONE)),
        }
        for input_number in input_numbers
        for output in output_numbers
    ]


def _serialize_input_modes(
    input_modes: dict[int, int],
    input_numbers: tuple[int, ...],
) -> list[dict[str, int]]:
    return [
        {"input_number": input_number, "mode": int(input_modes[input_number])}
        for input_number in input_numbers
        if input_number in input_modes
    ]


def _input_modes_match_mapping_rules(
    mapping_rules: list[MappingRule],
    input_modes: dict[int, InputMode],
) -> bool:
    if not _input_modes_are_valid(input_modes):
        return False

    for mapping in mapping_rules:
        event = MappingEvent(mapping["event"])
        input_number = mapping["input_number"]
        mode = _input_mode_for_mapping_event(event)
        if mode is None:
            return False

        if input_modes.get(input_number) is not mode:
            return False
    return True


def _input_mode_for_mapping_event(event: MappingEvent) -> InputMode | None:
    if event in _MAPPING_BUTTON_EVENTS:
        return InputMode.MAPPING_MATRIX_BUTTON
    if event in _MAPPING_EDGE_EVENTS:
        return InputMode.MAPPING_MATRIX_EDGE
    return None


def _input_modes_are_valid(input_modes: dict[int, InputMode]) -> bool:
    for input_number, mode in input_modes.items():
        if mode is InputMode.DISABLED:
            return False
        if input_number == INPUT_0 and mode in {
            InputMode.MOMENTARY,
            InputMode.LATCHING,
        }:
            return False
    return True


def _empty_matrices() -> dict[MappingEvent, dict[tuple[int, int], MappingAction]]:
    return {
        event: {
            (input_number, output): MappingAction.NONE
            for input_number in INPUTS
            for output in OUTPUTS
        }
        for event in MappingEvent
    }


def _sorted_input_numbers(input_numbers: tuple[int, ...]) -> tuple[int, ...]:
    return tuple(sorted(input_numbers))


def _message_id(msg: dict[str, object]) -> int:
    msg_id = msg["id"]
    if not isinstance(msg_id, int):
        raise TypeError("Invalid websocket message id")
    return msg_id


def _message_str(msg: dict[str, object], key: str) -> str:
    value = msg[key]
    if not isinstance(value, str):
        raise TypeError(f"Invalid websocket {key}")
    return value


def _message_int(msg: dict[str, object], key: str) -> int:
    value = msg[key]
    if not isinstance(value, int):
        raise TypeError(f"Invalid websocket {key}")
    return value


def _message_mapping_rules(msg: dict[str, object]) -> list[MappingRule]:
    return cast(list[MappingRule], msg["mappings"])


def _message_input_modes(msg: dict[str, object]) -> dict[int, InputMode] | None:
    raw_input_modes = msg["input_modes"]
    input_modes: dict[int, InputMode] = {}
    for item in cast(list[InputModeRule], raw_input_modes):
        input_number = item["input_number"]
        input_mode = InputMode(item["mode"])
        if input_number in input_modes and input_modes[input_number] is not input_mode:
            return None
        input_modes[input_number] = input_mode
    return input_modes
