"""Config flow for the openWB integration."""

from __future__ import annotations

from contextlib import suppress
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    CONFIG_ENTRY_VERSION,
    CONF_BAUDRATE,
    CONF_DEVICE_ID,
    CONF_FIRMWARE_VERSION,
    CONF_MODEL,
    CONF_PARITY,
    CONF_SERIAL_PORT,
    CONF_STOPBITS,
    DEFAULT_BAUDRATE,
    DEFAULT_PARITY,
    DEFAULT_STOPBITS,
    DOMAIN,
    MODEL_WB_MR6C_V2,
    PARITY_VALUES,
    STOPBITS_VALUES,
    SUBENTRY_TYPE_DEVICE,
)
from .wb_mr6c_modbus import (
    ModbusTransport,
    PymodbusSerialTransport,
    WBMR6C_MODEL,
    WBMR6CModbus,
    WBMR6CModbusConnectionError,
    WBMR6CModbusResponseError,
)


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SERIAL_PORT): selector.TextSelector(),
        vol.Required(CONF_BAUDRATE, default=str(DEFAULT_BAUDRATE)): (
            selector.TextSelector(
                {
                    "type": selector.TextSelectorType.NUMBER,
                }
            )
        ),
        vol.Required(CONF_PARITY, default=DEFAULT_PARITY): selector.SelectSelector(
            {
                "options": list(PARITY_VALUES),
            }
        ),
        vol.Required(CONF_STOPBITS, default=str(DEFAULT_STOPBITS)): (
            selector.SelectSelector(
                {
                    "options": [str(value) for value in STOPBITS_VALUES],
                }
            )
        ),
    }
)

STEP_DEVICE_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE_ID): selector.TextSelector(
            {
                "type": selector.TextSelectorType.NUMBER,
            }
        )
    }
)


class OpenWBConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for openWB."""

    VERSION = CONFIG_ENTRY_VERSION

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: config_entries.ConfigEntry
    ) -> dict[str, type[config_entries.ConfigSubentryFlow]]:
        """Return subentries supported by openWB bus entries."""
        return {SUBENTRY_TYPE_DEVICE: OpenWBDeviceSubentryFlow}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            data, errors = _validate_bus_config(user_input)

            if not errors:
                serial_port = data[CONF_SERIAL_PORT]

                await self.async_set_unique_id(f"wb_mr6c_bus:{serial_port}")
                self._abort_if_unique_id_configured()

                if not await _async_can_open_serial_bus(data):
                    errors["base"] = "cannot_connect"
                else:
                    return self.async_create_entry(
                        title=f"openWB bus {serial_port}", data=data
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )


class OpenWBDeviceSubentryFlow(config_entries.ConfigSubentryFlow):
    """Handle an openWB device subentry flow."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle manual device subentry setup."""
        errors: dict[str, str] = {}

        if user_input is not None:
            device_id = _parse_device_id(user_input.get(CONF_DEVICE_ID))

            if device_id is None:
                errors[CONF_DEVICE_ID] = "invalid_device_id"
            else:
                entry = self._get_entry()
                serial_port = _parse_serial_port(entry.data.get(CONF_SERIAL_PORT))

                if serial_port is None:
                    errors["base"] = "invalid_bus_config"
                elif _has_device_id_subentry(entry, device_id, serial_port):
                    errors[CONF_DEVICE_ID] = "duplicate_device_id"
                else:
                    model, firmware_version, error = (
                        await _async_read_device_identification(entry, device_id)
                    )
                    if error is not None:
                        errors["base"] = error
                    elif model != WBMR6C_MODEL:
                        errors["base"] = "unexpected_model"
                    else:
                        return self.async_create_entry(
                            title=f"WB-MR6C {device_id}",
                            data={
                                CONF_DEVICE_ID: device_id,
                                CONF_MODEL: MODEL_WB_MR6C_V2,
                                CONF_FIRMWARE_VERSION: firmware_version,
                            },
                            unique_id=_device_subentry_unique_id(
                                serial_port, device_id
                            ),
                        )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_DEVICE_DATA_SCHEMA,
            errors=errors,
        )


def _validate_bus_config(
    user_input: dict[str, Any],
) -> tuple[dict[str, str | int], dict[str, str]]:
    """Validate and normalize serial bus configuration input."""
    errors: dict[str, str] = {}

    serial_port = _parse_serial_port(user_input.get(CONF_SERIAL_PORT))
    if serial_port is None:
        errors[CONF_SERIAL_PORT] = "invalid_serial_port"

    baudrate = _parse_positive_int(user_input.get(CONF_BAUDRATE, DEFAULT_BAUDRATE))
    if baudrate is None:
        errors[CONF_BAUDRATE] = "invalid_baudrate"

    parity = _parse_parity(user_input.get(CONF_PARITY, DEFAULT_PARITY))
    if parity is None:
        errors[CONF_PARITY] = "invalid_parity"

    stopbits = _parse_stopbits(user_input.get(CONF_STOPBITS, DEFAULT_STOPBITS))
    if stopbits is None:
        errors[CONF_STOPBITS] = "invalid_stopbits"

    if errors:
        return {}, errors

    assert serial_port is not None
    assert baudrate is not None
    assert parity is not None
    assert stopbits is not None
    return {
        CONF_SERIAL_PORT: serial_port,
        CONF_BAUDRATE: baudrate,
        CONF_PARITY: parity,
        CONF_STOPBITS: stopbits,
    }, {}


async def _async_can_open_serial_bus(data: dict[str, str | int]) -> bool:
    """Return whether the configured serial bus can be opened."""
    try:
        transport = PymodbusSerialTransport(
            str(data[CONF_SERIAL_PORT]),
            baudrate=int(data[CONF_BAUDRATE]),
            parity=str(data[CONF_PARITY]),
            stopbits=int(data[CONF_STOPBITS]),
        )
        try:
            await transport.connect()
        except WBMR6CModbusConnectionError:
            with suppress(WBMR6CModbusConnectionError):
                await transport.close()
            return False

        await transport.close()
    except WBMR6CModbusConnectionError:
        return False

    return True


async def _async_read_device_identification(
    entry: config_entries.ConfigEntry, device_id: int
) -> tuple[str | None, str | None, str | None]:
    """Read model and firmware metadata for a device subentry."""
    transport: ModbusTransport | None = None
    close_transport = False

    try:
        transport, close_transport = _device_validation_transport(entry)
        if close_transport:
            await transport.connect()  # type: ignore[attr-defined]

        client = WBMR6CModbus(transport, device_id=device_id)
        model = await client.read_model()
        firmware_version = await client.read_firmware_version()
    except WBMR6CModbusConnectionError:
        return None, None, "cannot_connect"
    except WBMR6CModbusResponseError:
        return None, None, "cannot_validate_device"
    finally:
        if close_transport and transport is not None:
            with suppress(WBMR6CModbusConnectionError):
                await transport.close()  # type: ignore[attr-defined]

    return model, firmware_version, None


def _device_validation_transport(
    entry: config_entries.ConfigEntry,
) -> tuple[ModbusTransport, bool]:
    """Return a transport for subentry validation and whether it should close."""
    runtime_data = getattr(entry, "runtime_data", None)
    runtime_transport = getattr(runtime_data, "transport", None)
    if runtime_transport is not None:
        return runtime_transport, False

    data, errors = _validate_bus_config(dict(entry.data))
    if errors:
        raise WBMR6CModbusConnectionError("Invalid openWB bus config entry data")

    return (
        PymodbusSerialTransport(
            str(data[CONF_SERIAL_PORT]),
            baudrate=int(data[CONF_BAUDRATE]),
            parity=str(data[CONF_PARITY]),
            stopbits=int(data[CONF_STOPBITS]),
        ),
        True,
    )


def _has_device_id_subentry(
    entry: config_entries.ConfigEntry, device_id: int, serial_port: str
) -> bool:
    """Return whether the parent bus already has this Modbus device address."""
    unique_id = _device_subentry_unique_id(serial_port, device_id)
    for subentry in getattr(entry, "subentries", {}).values():
        if getattr(subentry, "unique_id", None) == unique_id:
            return True
        data = getattr(subentry, "data", {})
        if data.get(CONF_DEVICE_ID) == device_id:
            return True

    return False


def _device_subentry_unique_id(serial_port: str, device_id: int) -> str:
    """Return the bus-scoped device subentry unique id."""
    return f"{serial_port}:{device_id}"


def _parse_device_id(value: Any) -> int | None:
    """Parse and validate a Modbus device id in the RTU slave range."""
    device_id = _parse_positive_int(value)
    if device_id is not None and 1 <= device_id <= 247:
        return device_id
    return None


def _parse_serial_port(value: Any) -> str | None:
    """Parse and validate a serial device path/name."""
    if not isinstance(value, str):
        return None

    serial_port = value.strip()
    return serial_port or None


def _parse_positive_int(value: Any) -> int | None:
    """Parse and validate a positive integer form value."""
    if isinstance(value, bool):
        return None

    if isinstance(value, int):
        parsed_value = value
    elif isinstance(value, str):
        try:
            parsed_value = int(value.strip())
        except ValueError:
            return None
    else:
        return None

    if parsed_value > 0:
        return parsed_value
    return None


def _parse_parity(value: Any) -> str | None:
    """Parse and validate serial parity."""
    if not isinstance(value, str):
        return None

    parity = value.strip().upper()
    if parity in PARITY_VALUES:
        return parity
    return None


def _parse_stopbits(value: Any) -> int | None:
    """Parse and validate serial stop bits."""
    stopbits = _parse_positive_int(value)
    if stopbits in STOPBITS_VALUES:
        return stopbits
    return None
