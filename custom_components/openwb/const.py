"""Constants for the openWB integration."""

DOMAIN = "openwb"
CONFIG_ENTRY_VERSION = 2

CONF_BAUDRATE = "baudrate"
CONF_DEVICE_ID = "device_id"
CONF_FIRMWARE_VERSION = "firmware_version"
CONF_MODEL = "model"
CONF_PARITY = "parity"
CONF_SERIAL_PORT = "serial_port"
CONF_STOPBITS = "stopbits"

MODEL_WB_MR6C_V2 = "wb_mr6c_v2"
SUBENTRY_TYPE_DEVICE = "device"

DEFAULT_BAUDRATE = 9600
DEFAULT_PARITY = "N"
DEFAULT_STOPBITS = 2

PARITY_VALUES = ("N", "E", "O")
STOPBITS_VALUES = (1, 2)
