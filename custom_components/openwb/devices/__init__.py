"""Registry of supported Wiren Board device models."""

from __future__ import annotations

from ..wb_mr6c_modbus import INPUTS, OUTPUTS, ModbusTransport
from .base import (
    FirmwareGate,
    OpenWBDeviceClient,
    OpenWBDeviceDefinition,
    OpenWBDeviceMetadata,
)
from .wb_mcm8 import DEFINITION as WB_MCM8_DEFINITION
from .wb_mr6c_v2 import DEFINITION as WB_MR6C_V2_DEFINITION
from .wb_mr6cu_v2 import DEFINITION as WB_MR6CU_V2_DEFINITION

DEVICE_DEFINITIONS: tuple[OpenWBDeviceDefinition, ...] = (
    WB_MR6C_V2_DEFINITION,
    WB_MR6CU_V2_DEFINITION,
    WB_MCM8_DEFINITION,
)
DEFAULT_DEVICE_DEFINITION = WB_MR6C_V2_DEFINITION

_DEFINITIONS_BY_CONFIG_MODEL = {
    definition.config_model: definition for definition in DEVICE_DEFINITIONS
}
_DEFINITIONS_BY_RAW_MODEL = {
    raw_model: definition
    for definition in DEVICE_DEFINITIONS
    for raw_model in definition.raw_model_aliases
}

SUPPORTED_MODELS = frozenset(_DEFINITIONS_BY_RAW_MODEL)
SUPPORTED_CONFIG_MODELS = frozenset(_DEFINITIONS_BY_CONFIG_MODEL)


def device_definition_for_model(
    model: str | None,
) -> OpenWBDeviceDefinition | None:
    """Return a device definition by raw model string or stored config model id."""
    if model is None:
        return None
    return _DEFINITIONS_BY_CONFIG_MODEL.get(model) or _DEFINITIONS_BY_RAW_MODEL.get(
        model
    )


def config_model_for_model(model: str | None) -> str | None:
    """Return the stored config model id for a raw or already-stored model."""
    definition = device_definition_for_model(model)
    if definition is None:
        return None
    return definition.config_model


def config_model_for_raw_model(model: str | None) -> str | None:
    """Return the stored config model id for a raw Modbus model string."""
    if model is None:
        return None
    definition = _DEFINITIONS_BY_RAW_MODEL.get(model)
    if definition is None:
        return None
    return definition.config_model


def create_device_client(
    transport: ModbusTransport,
    device_id: int,
    model: str | None = None,
) -> OpenWBDeviceClient:
    """Create a high-level client for a configured device."""
    definition = device_definition_for_model(model) or DEFAULT_DEVICE_DEFINITION
    return definition.client_factory(transport, device_id)


def device_metadata_from_identification(
    model: str | None,
    firmware_version: str | None,
) -> OpenWBDeviceMetadata:
    """Build runtime metadata from stored/refreshed model and firmware values."""
    definition = device_definition_for_model(model) or DEFAULT_DEVICE_DEFINITION
    input_numbers = definition.input_numbers
    output_numbers = definition.output_numbers

    return OpenWBDeviceMetadata(
        model=model,
        firmware_version=firmware_version,
        supports_inputs=bool(input_numbers),
        supports_press_counters=(
            bool(input_numbers)
            and _gate_supports(
                definition.press_counter_firmware_gate, firmware_version
            )
        ),
        supports_mapping_matrix=definition.supports_mapping_matrix,
        supports_relay_one_shot_commands=(
            bool(output_numbers)
            and _gate_supports(
                definition.relay_one_shot_firmware_gate, firmware_version
            )
        ),
        supports_relay_state_discrete_inputs=(
            bool(output_numbers)
            and _gate_supports(
                definition.relay_state_discrete_inputs_firmware_gate,
                firmware_version,
            )
        ),
        input_numbers=input_numbers,
        output_numbers=output_numbers,
        press_counter_input_registers=definition.press_counter_input_registers,
        supports_fast_modbus_events=_gate_supports(
            definition.fast_modbus_events_firmware_gate,
            firmware_version,
        ),
    )


def unknown_device_metadata() -> OpenWBDeviceMetadata:
    """Return conservative fallback metadata for legacy entries without a model."""
    return OpenWBDeviceMetadata(
        model=None,
        firmware_version=None,
        supports_inputs=True,
        supports_press_counters=False,
        supports_mapping_matrix=True,
        supports_relay_one_shot_commands=False,
        supports_relay_state_discrete_inputs=False,
        input_numbers=INPUTS,
        output_numbers=OUTPUTS,
        press_counter_input_registers=False,
        supports_fast_modbus_events=False,
    )


def input_numbers_for_model(model: str | None) -> tuple[int, ...]:
    """Return input numbers exposed by the model."""
    definition = device_definition_for_model(model) or DEFAULT_DEVICE_DEFINITION
    return definition.input_numbers


def output_numbers_for_model(model: str | None) -> tuple[int, ...]:
    """Return relay output numbers exposed by the model."""
    definition = device_definition_for_model(model) or DEFAULT_DEVICE_DEFINITION
    return definition.output_numbers


def supports_mapping_matrix_for_model(model: str | None) -> bool:
    """Return whether the model supports input-to-output mapping matrices."""
    definition = device_definition_for_model(model) or DEFAULT_DEVICE_DEFINITION
    return definition.supports_mapping_matrix


def press_counter_input_registers_for_model(model: str | None) -> bool:
    """Return whether press counters must be read from input registers."""
    definition = device_definition_for_model(model) or DEFAULT_DEVICE_DEFINITION
    return definition.press_counter_input_registers


def device_model_display_name(model: str | None) -> str:
    """Return a Home Assistant device-info model name."""
    definition = device_definition_for_model(model)
    if definition is None:
        return model or DEFAULT_DEVICE_DEFINITION.display_name
    return definition.display_name


def device_name(model: str | None, device_id: int) -> str:
    """Return a Home Assistant device display name."""
    definition = device_definition_for_model(model) or DEFAULT_DEVICE_DEFINITION
    return f"{definition.name_prefix} {device_id}"


def _gate_supports(gate: FirmwareGate | None, firmware_version: str | None) -> bool:
    if gate is None or firmware_version is None:
        return False
    try:
        return bool(gate(firmware_version))
    except ValueError:
        return False
