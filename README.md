# OpenWB for Home Assistant

Open Source Home Assistant integration with wirenboard modules in HACS format.

## Status

Under development, not ready for production

Supported modules:

- WB-MR6C v.2
- WB-MR6CU v.2

## Modbus Documentation

- [WB-MR6CU v.2](https://wiki.wirenboard.com/wiki/WB-MR6CU_v.2_Modbus_Relay_Modules)
- [Relay Module Modbus Management](https://wiki.wirenboard.com/wiki/Relay_Module_Modbus_Management)
- [I/O Mapping Matrix](https://wiki.wirenboard.com/wiki/I/O_Mapping_Matrix)

## Installation with HACS

1. In Home Assistant, open HACS.
2. Open the three-dot menu and choose **Custom repositories**.
3. Add this repository URL and select **Integration** as the category.
4. Install **openWB** from HACS.
5. Restart Home Assistant.
6. Go to **Settings** -> **Devices & services** -> **Add integration** and search for **openWB**.

## Development Installation

Copy `custom_components/openwb` into your Home Assistant `custom_components` directory and restart Home Assistant:

```text
config/
  custom_components/
    openwb/
```

After copying the integration, use the step-by-step testing guide:

- [Testing after custom_components installation](docs/testing.md)

Backend architecture:

- [Backend design](docs/backend-design.md)
