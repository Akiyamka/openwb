"""WB-MR6C v.2 device descriptor."""

from __future__ import annotations

from ..const import MODEL_WB_MR6C_V2
from ..wb_mr6c_modbus import (
    INPUTS,
    MR6C_MODEL,
    OUTPUTS,
    WBMR6C_MODEL,
    WBMR6CModbus,
    firmware_supports_fast_modbus_events,
    firmware_supports_press_counters,
    firmware_supports_relay_one_shot_commands,
    firmware_supports_relay_state_discrete_inputs,
)
from .base import OpenWBDeviceDefinition


DEFINITION = OpenWBDeviceDefinition(
    config_model=MODEL_WB_MR6C_V2,
    raw_model_aliases=frozenset((WBMR6C_MODEL, MR6C_MODEL)),
    display_name="WB-MR6C v.2",
    name_prefix="WB-MR6C",
    input_numbers=INPUTS,
    output_numbers=OUTPUTS,
    supports_mapping_matrix=True,
    client_factory=lambda transport, device_id: WBMR6CModbus(
        transport, device_id=device_id
    ),
    press_counter_firmware_gate=firmware_supports_press_counters,
    relay_one_shot_firmware_gate=firmware_supports_relay_one_shot_commands,
    relay_state_discrete_inputs_firmware_gate=(
        firmware_supports_relay_state_discrete_inputs
    ),
    fast_modbus_events_firmware_gate=firmware_supports_fast_modbus_events,
)
