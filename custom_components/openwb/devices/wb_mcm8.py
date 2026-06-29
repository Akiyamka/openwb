"""WB-MCM8 device descriptor."""

from __future__ import annotations

from ..const import MODEL_WB_MCM8
from ..wb_mr6c_modbus import (
    MCM8_INPUTS,
    MCM8_MODEL,
    WBMR6CModbus,
    WBMCM8_MODEL,
    firmware_supports_mcm8_fast_modbus_events,
    firmware_supports_mcm8_press_counters,
)
from .base import OpenWBDeviceDefinition


DEFINITION = OpenWBDeviceDefinition(
    config_model=MODEL_WB_MCM8,
    raw_model_aliases=frozenset((WBMCM8_MODEL, MCM8_MODEL)),
    display_name="WB-MCM8",
    name_prefix="WB-MCM8",
    input_numbers=MCM8_INPUTS,
    output_numbers=(),
    supports_mapping_matrix=False,
    client_factory=lambda transport, device_id: WBMR6CModbus(
        transport, device_id=device_id
    ),
    press_counter_input_registers=True,
    press_counter_firmware_gate=firmware_supports_mcm8_press_counters,
    fast_modbus_events_firmware_gate=firmware_supports_mcm8_fast_modbus_events,
)
