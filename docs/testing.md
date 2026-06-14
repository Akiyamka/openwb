# Testing

Run the default fake/stub-only tests without hardware:

```sh
python -m unittest discover -s tests
```

Real WB-MR6C/WB-MR6CU smoke tests are opt-in and read-only. They open a direct Modbus RTU serial connection, so no other Modbus master should be using the same RS-485 bus.

Install the integration dependencies before running these tests from a bare checkout:

```sh
python -m pip install pymodbus==3.11.2 pyserial==3.5
```

```sh
OPENWB_REAL_DEVICE_TESTS=1 OPENWB_SERIAL_PORT=/dev/ttyUSB0 python -m unittest discover -s tests -p 'test_wb_mr6c_real_device.py'
```

Environment variables:

- `OPENWB_REAL_DEVICE_TESTS=1` enables real-device tests.
- `OPENWB_SERIAL_PORT=/dev/ttyUSB0` is required when enabled.
- `OPENWB_DEVICE_ID=1` defaults to `1`.
- `OPENWB_BAUDRATE=9600` defaults to `9600`.
- `OPENWB_PARITY=N` defaults to `N`.
- `OPENWB_STOPBITS=2` defaults to `2`.
- `OPENWB_TIMEOUT=3.0` defaults to `3.0`.

The real-device smoke tests connect and close the serial transport, read the model and firmware registers, read relay command coils, read input states only for WB-MR6C devices, and read relay-state discrete inputs only when the firmware reports support for them.

When reporting results, include the full test command, serial settings, device address, test output, and the printed line that starts with `openWB real-device smoke result:`. That line includes the decoded model, firmware, relay command states, input states when present, and relay states if supported by the device firmware.
