# Backend Implementation Plan

This plan follows `docs/backend-design.md` and treats the current implementation as disposable. The target backend owns a direct serial Modbus RTU connection per RS-485 bus. A TCP gateway/helper path is not part of the supported product scope.

## Version Strategy

The integration should move through pre-`1.0` backend increments before declaring the first stable version:

- `0.1.x` to `0.3.x`: backend foundation and serial bus ownership.
- `0.4.x` to `0.7.x`: usable Home Assistant runtime with relay, input, and press-event entities.
- `0.8.x` to `0.10.x`: settings, mapping matrix backend, and mapping matrix UI.
- `1.0.0`: first stable backend/UI release after stabilization and test coverage.

Minimum supported Home Assistant version: `2026.6.3`.

## Phases

| Phase | App Version | Scope | Result |
| --- | --- | --- | --- |
| 1. Pure device register model | `0.1.0` | Implement the WB-MR6C v2 register model as pure Python: relay coils, discrete inputs, holding registers, input `0`, press counters, mapping matrix addresses, enums, helpers, and validation. | Device-specific Modbus knowledge is isolated from Home Assistant code. |
| 2. Serial transport layer | `0.2.0` | Define the narrow `ModbusTransport` protocol. Implement a serial RTU transport using `AsyncModbusSerialClient`, with one per-bus request lock held per transaction. Keep an in-memory fake transport for tests and UI development. | The integration can act as the only Modbus RTU master for one RS-485 bus. |
| 3. Bus config entry | `0.3.0` | Add the main config flow where one config entry represents one serial bus. Store `serial_port`, `baudrate`, `parity`, and `stopbits`. Use unique id `wb_mr6c_bus:{serial_port}`. Open the serial port during setup and close it on unload. Raise `ConfigEntryNotReady` on port-open failure. | Home Assistant can add and manage one RS-485 bus. |
| 4. Device subentries | `0.4.0` | Add a config subentry flow where one subentry represents one WB module on the bus. Validate `device_id` in `1..247`, reject duplicate addresses on the same bus, read model register `200`, and read firmware register `250`. | Multiple WB-MR6C devices can be attached to one bus entry. |
| 5. Runtime data and bus coordinator | `0.5.0` | Move runtime state to typed `entry.runtime_data`. Add `OpenWBBusRuntimeData` with the shared transport, one bus-level coordinator, and one device client per subentry. Poll each device sequentially, key data by `device_id`, handle per-device read failures without failing the whole bus, and gate firmware-dependent features. | The backend continuously reads live state for every reachable device on the bus. |
| 6. Relay switch entities | `0.6.0` | Add `switch` entities for relay outputs `1..6`. Read actual relay state where firmware supports it, fall back to command coils on older firmware, write one-shot ON/OFF/TOGGLE commands, and use optimistic state after successful writes without forcing an immediate refresh. | The first practical HA surface exists: users can control WB relays. |
| 7. Input level and press events | `0.7.0` | Add `binary_sensor` entities for input levels `1..6` and input `0`. Add `event` entities for short, long, double, and short-then-long presses using press-counter deltas. Handle counter wraparound and suppress events on the first baseline read. | WB buttons can be used as Home Assistant automation triggers. |
| 8. Settings backend | `0.8.0` | Add explicit on-demand client methods for input modes, debounce time, long-press time, second-press wait time, safe states, safe-mode actions, and safe-mode input controls. Validate all values before writing and translate backend errors to Home Assistant-friendly exceptions at the integration boundary. | Device settings can be read and changed without poll-loop coupling. |
| 9. Mapping matrix backend | `0.9.0` | Add on-demand read support for mapping matrices and diff-write support that writes only changed cells. Validate events, inputs, outputs, and actions before writing. Optional development services may call the same backend methods. | The backend can configure local on-device button-to-relay behavior. |
| 10. Mapping matrix configuration UI | `0.10.0` | Add a Home Assistant UI surface for editing the mapping matrix. The UI should load matrix data on demand, show inputs `1..6` and `0`, expose supported events and outputs, validate edits before save, preview pending changes, and submit only changed cells through the backend. | Users can configure local WB button-to-relay mappings without editing raw registers. |
| 11. Stabilization | `1.0.0` | Finalize cycle-budget behavior, coalesced reads, reload/unload behavior, firmware degradation paths, logging, documentation, and Home Assistant tests for config flow, subentries, entities, partial failure, writes, press events, and matrix UI behavior. | First stable release with the backend and matrix configuration workflow complete. |

## MVP Boundary

The first practically usable MVP is `0.7.0`: at that point the integration has bus setup, device subentries, live polling, relay switches, input levels, and button press events.

The first stable version should be `1.0.0`, not an earlier `0.x` release, because the core product goal includes both Home Assistant-mediated control and local on-device mapping matrix configuration.
