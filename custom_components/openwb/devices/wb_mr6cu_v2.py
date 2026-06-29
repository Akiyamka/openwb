"""WB-MR6CU v.2 device descriptor."""

from __future__ import annotations

from ..const import MODEL_WB_MR6CU_V2
from ..wb_mr6c_modbus import (
    MR6CU_MODEL,
    OUTPUTS,
    WBMR6CModbus,
    WBMR6CU_MODEL,
    firmware_supports_fast_modbus_events,
    firmware_supports_relay_one_shot_commands,
    firmware_supports_relay_state_discrete_inputs,
)
from .base import OpenWBDeviceDefinition


DEFINITION = OpenWBDeviceDefinition(
    config_model=MODEL_WB_MR6CU_V2,
    raw_model_aliases=frozenset((WBMR6CU_MODEL, MR6CU_MODEL)),
    display_name="WB-MR6CU v.2",
    name_prefix="WB-MR6CU",
    input_numbers=(),
    output_numbers=OUTPUTS,
    supports_mapping_matrix=False,
    client_factory=lambda transport, device_id: WBMR6CModbus(
        transport, device_id=device_id
    ),
    relay_one_shot_firmware_gate=firmware_supports_relay_one_shot_commands,
    relay_state_discrete_inputs_firmware_gate=(
        firmware_supports_relay_state_discrete_inputs
    ),
    fast_modbus_events_firmware_gate=firmware_supports_fast_modbus_events,
)
