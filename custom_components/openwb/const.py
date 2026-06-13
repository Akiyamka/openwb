"""Constants for the openWB integration."""

DOMAIN = "openwb"
CONFIG_ENTRY_VERSION = 2

CONF_BAUDRATE = "baudrate"
CONF_PARITY = "parity"
CONF_SERIAL_PORT = "serial_port"
CONF_STOPBITS = "stopbits"

DEFAULT_BAUDRATE = 9600
DEFAULT_PARITY = "N"
DEFAULT_STOPBITS = 2

PARITY_VALUES = ("N", "E", "O")
STOPBITS_VALUES = (1, 2)
