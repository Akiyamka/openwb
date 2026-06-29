# Backend Design

This document describes the target backend implementation for the openWB Home Assistant integration.
The official integration speaks MQTT to a Wiren Board controller; this one is the Modbus master itself.

## Goals

- Keep the device-specific Modbus register logic separate from Home Assistant UI/entity code.
- Own a direct serial Modbus connection inside the integration so it can act as the single bus master and later add Wiren Board fast Modbus (see [Modbus Ownership Model](#modbus-ownership-model)).
- Support both control paths on a WB module: **local** button→relay switching (the on-device mapping matrix, instant) and **HA-mediated** automations bound to the same buttons and relays. HA's roles are: switch relays (immediate writes), observe button presses as automation triggers (fast polling), and read/write the mapping matrix configuration.
- Expose relay state/control, button presses, input level, and device settings through native Home Assistant entities.
- Make settings writes explicit, validated, and easy to test without real hardware.
- Keep the backend extensible for other Wiren Board modules.

## Non-Goals

- A Modbus TCP-to-RTU gateway topology is out of scope; the integration connects over a **direct serial (USB-RS485)** link only.
- This integration should not share an RS-485 bus with Home Assistant's built-in `modbus` integration (two masters on one bus do not work — see [Modbus Ownership Model](#modbus-ownership-model)).

## Modbus Ownership Model

> **Decision: Model B — the integration owns its own Modbus connection (one per bus) and is the sole bus master.** Model A (reusing Home Assistant's built-in `modbus` hub) is rejected. Rationale below.

A Modbus RTU (RS-485) bus allows exactly **one master**. The rule is therefore: **one bus, one master.** The integration is that master for each bus it owns — with multiple buses (dongles), there is one master *per bus*, each backed by its own transport. Two candidates for the master role exist on any given bus, and only one can be active.

**Model A — reuse Home Assistant's built-in `modbus` hub.**
The hub object lives in-process in `hass.data` and already owns an open connection, so the config entry would not need its own serial settings. Rejected as the target model because:

- the built-in `modbus` integration exposes **no read services** (only `modbus.write_coil` / `modbus.write_register`), so reads would require calling private `ModbusHub` internals that are not a stable API;
- it cannot speak Wiren Board fast Modbus, which is an explicit future goal.

**Model B — own the connection (target model).**
The integration holds its own `pymodbus` client per bus and is the sole master on each bus. This is the chosen direction because it gives a supported read path, full control over polling, and a place to add fast Modbus later. The cost is that the serial parameters must live in the bus config entry (see [Configuration Model](#configuration-model)).

**Hard constraint:** because Model B makes this integration the bus master, the built-in `modbus` integration must **not** be configured for the same RS-485 bus. If the bus is shared with other devices the user drives through built-in `modbus`, this integration cannot run on it. Mixed-bus support is out of scope.

### Fast Modbus

Wiren Board controllers support a fast Modbus extension (event-driven scan instead of blind polling) that the built-in `modbus` integration does not implement. Owning the transport (Model B) is what makes adopting it possible later. The transport protocol below is intentionally narrow so a fast-Modbus transport can be added behind the same interface without touching the device client or entities.

## Runtime Constraints

- Entity property getters must return cached coordinator data only.
- Modbus I/O should happen in coordinator updates, write handlers, services, or explicit settings flows.
- Entity property getters must not perform Modbus reads/writes directly.
- The backend must provide a fake or in-memory transport path so Home Assistant entities and future UI surfaces can be tested without real WB-MR6C hardware.

## Configuration Model

The real deployment is **several RS-485 buses, each carrying several devices** (multiple USB-RS485 dongles, multiple WB modules per dongle). One serial port allows only one connection, so the model is two-tier:

- **config entry = one bus** (one serial port). It owns the single transport and the shared request lock. Multiple bus entries are allowed (one per dongle).
- **config subentry = one device on that bus** (one Modbus slave address). Each subentry becomes one Home Assistant device with its own entities, sharing the parent bus's transport.

The minimum Home Assistant version is **2026.6.3** (`hacs.json`), so config subentries (`async_get_supported_subentries`, `config_subentry_id` in `async_add_entities`) are available and are the committed mechanism — no single-entry fallback is needed. Older HA versions are not supported.

Bus config entry data (one per serial port):

```json
{
  "serial_port": "/dev/ttyUSB0",
  "baudrate": 9600,
  "parity": "N",
  "stopbits": 2
}
```

Device subentry data (one per WB module on the bus):

```json
{
  "device_id": 1,
  "model": "wb_mr6c_v2"
}
```

`device_id` is the Modbus slave/server address and must be in the `1..247` range. There is no reliable RTU autodiscovery (scanning 1..247 is slow and noisy on the bus), so devices are added manually through the subentry flow.

The main config flow creates a bus and should validate the port opens before creating the entry. The subentry flow adds a device and should validate that the slave address responds. `async_setup_entry` opens the bus transport and raises `ConfigEntryNotReady` if the port cannot be opened (see [Error Handling](#error-handling)).

### Uniqueness

Identity must be scoped to the bus, because the same slave address legitimately exists on different buses:

- **bus** config entry `unique_id`: `wb_mr6c_bus:{serial_port}` (one entry per port; rejects adding the same dongle twice);
- **device** subentry `unique_id`: `{serial_port}:{device_id}` (unique within and across buses);
- a device that physically moves to another dongle is a different identity, which is correct.

## Layering

The final backend should have four layers:

1. Register model
2. Transport adapter
3. Device client
4. Home Assistant runtime integration

Each layer has a narrow responsibility.

## Register Model

The register model is pure Python and contains no Home Assistant imports.

It should define:

- channel/input/output counts;
- coil, discrete input, holding register, and mapping matrix addresses;
- input press-counter register addresses (see below);
- model and firmware-version register addresses (see below);
- enums for documented values;
- helper functions for address calculation;
- validation for channel numbers, input numbers, output numbers, and register values.

This layer is where the Wiren Board documentation is translated into code.

### Input Press Counters

Momentary button presses cannot be caught by polling instantaneous input level. WB-MR6C exposes monotonic per-input event **counters**; a press is detected by comparing the counter against the previous poll (see [Input Behavior](#input-behavior)). These addresses must be added to the register model.

| Counter | Base (inputs 1..6) | Input 0 | Firmware |
| --- | --- | --- | --- |
| Activation (any) | `32` (`0x0020`) | — | base |
| Short press | `464` (`0x01D0`) | `471` | FW 1.17.0+ |
| Long press | `480` (`0x01E0`) | `487` | FW 1.17.0+ |
| Double press | `496` (`0x01F0`) | `503` | FW 1.17.0+ |
| Short-then-long press | `512` (`0x0200`) | `519` | FW 1.17.0+ |

Input 0 sits at `base + 7`, matching the existing `_input_index` convention. All counters are read-only `u16` and wrap at `65535`.

> The addresses above were pulled from the Wiren Board wiki via an automated fetch. **Verify them against the actual register map and firmware before relying on them.** The per-press-type counters require **FW 1.17.0+**, and the relay-state discrete inputs at base `96` require **FW 1.24.0+**; on older firmware the integration must degrade gracefully (omit press events / fall back to command coils for relay state). These features are gated by the firmware read below.

### Identification (model & firmware)

Read once per device at setup (holding registers, function `0x03`) — never on the fast poll:

| Field | Address | Layout |
| --- | --- | --- |
| Model | `200` | 6 registers, one ASCII char each (high byte `0`); e.g. `0x57 0x42 0x4D 0x52 0x36 0x43` → `WBMR6C` |
| Firmware version | `250` | null-terminated ASCII string, up to 16 registers; e.g. `1.3.1` |

(Fast-Modbus firmware extends the model block to registers `200..219`; reading the first 6 works on all firmware.)

Parse the firmware string into a comparable tuple (`"1.17.0" → (1, 17, 0)`) and gate features at setup:

- press counters / press `event` entities — require FW `>= 1.17.0`;
- relay state from discrete inputs `96..101` — require FW `>= 1.24.0`; below that, fall back to the relay command coils as the best available state.

The model read also doubles as the subentry "is this really a WB-MR6C?" validation, and the firmware feeds the device registry `sw_version` (see [Device Registry](#device-registry)).

Primary documentation:

- https://wiki.wirenboard.com/wiki/Relay_Module_Modbus_Management
- https://wiki.wirenboard.com/wiki/I/O_Mapping_Matrix
- https://wiki.wirenboard.com/wiki/Modbus-client (model / firmware register layout)

## Transport Adapter

The device client must use a small transport protocol instead of importing Home Assistant directly.

Target protocol:

```python
class ModbusTransport(Protocol):
    async def read_coils(
        self, address: int, count: int, device_id: int
    ) -> Sequence[bool]: ...

    async def write_coil(
        self, address: int, value: bool, device_id: int
    ) -> None: ...

    async def read_discrete_inputs(
        self, address: int, count: int, device_id: int
    ) -> Sequence[bool]: ...

    async def read_holding_registers(
        self, address: int, count: int, device_id: int
    ) -> Sequence[int]: ...

    async def write_register(
        self, address: int, value: int, device_id: int
    ) -> None: ...
```

Under [Model B](#modbus-ownership-model) the transport is owned by the integration:

- A pymodbus **serial** transport (`AsyncModbusSerialClient` over the USB-RS485 dongle) is the runtime path. Its connection lifecycle is bound to the bus: connect on `async_setup_entry`, close on `async_unload_entry`.
- A future fast-Modbus transport can implement the same protocol without changes above it.
- `PymodbusTcpTransport` (already in the code) is **not** a supported deployment topology — TCP gateways are a non-goal. Keep it only as an optional development helper against a Modbus TCP simulator, or drop it.

The transport must serialize requests (the existing `asyncio.Lock` does this) because one serial port carries a single transaction at a time across all devices on the bus. The lock is held **per transaction**, not across a batch: the coordinator acquires and releases it around each individual read, so a command write from an automation can interleave between two of the coordinator's per-device reads and wait at most one transaction — never a whole poll cycle. This keeps relay commands fast regardless of the poll interval (see [Writes and refresh](#writes-and-refresh)).

A fake transport should be kept for tests and UI development. It should implement the same `ModbusTransport` protocol, store coils/registers in memory, and allow tests to simulate unavailable devices or invalid responses.

## Device Client

The device client should expose WB-MR6C operations in device terms rather than raw Modbus calls.

Target class:

```python
WBMR6CModbus
```

Responsibilities:

- read commanded relay states;
- read actual relay states;
- read input states (level);
- read input press counters;
- read firmware/model identification (to gate FW-dependent features);
- turn relay on/off/toggle;
- read and write input modes;
- read and write debounce, long-press, and second-press timings;
- read and write safe mode settings;
- read and write mapping matrix cells;
- validate values before writing them.

The client should raise integration-specific exceptions, not raw pymodbus exceptions.

Expected exception groups:

- connection/transport errors;
- invalid Modbus responses;
- invalid local arguments.

## Runtime Data

Runtime data is owned by the **bus** config entry (subentries do not have their own `runtime_data`). It holds the one transport for that serial port, the per-bus coordinator, and one device client per subentry:

```python
@dataclass(slots=True)
class OpenWBBusRuntimeData:
    transport: ModbusTransport            # one serial connection for the whole bus
    coordinator: WBMR6CBusCoordinator     # polls every device on the bus
    clients: dict[int, WBMR6CModbus]      # device_id -> device client (one per subentry)
```

Store it on the bus config entry, typed via a `ConfigEntry` alias:

```python
type OpenWBConfigEntry = ConfigEntry[OpenWBBusRuntimeData]

entry.runtime_data = bus_runtime_data
```

When a subentry is added or removed at runtime, register/unregister its client in `clients` and reload so the coordinator picks it up. All clients share the one `transport`, so all bus traffic is serialized through its lock.

Do **not** use `hass.data[DOMAIN][entry_id]`: on HA 2026.6.3+ `entry.runtime_data` is the standard typed container. The current `__init__.py` still uses the old `hass.data` pattern and should migrate to `entry.runtime_data`.

## Coordinator

Use `DataUpdateCoordinator` for frequently read state. There is **one coordinator per bus**, not per device: a single serial port serializes everything anyway, so the bus coordinator polls each of its devices in turn within one update cycle. This keeps bus contention predictable and avoids independent coordinators fighting over the lock.

For each device on the bus the coordinator should poll:

- input press counters — **latency-critical**: WB buttons double as HA automation triggers, and presses are observed only by polling these (see [Input Behavior](#input-behavior));
- input states (instantaneous level), for contacts used as level signals;
- actual relay states;
- relay command coils;
- optionally a small set of diagnostic registers.

Suggested update interval:

```text
~1 second
```

**Two different latencies — don't conflate them:**

- **HA → relay (commands)** are bounded by the *write*, not the poll: when an automation fires (e.g. a Zigbee motion sensor → switch a relay), the backend writes the coil immediately, so the relay reacts sub-second regardless of interval. Optimistic state reflects it in the UI at once.
- **WB button → HA (observation)** is bounded by the *poll interval*: a WB button used as an HA automation trigger is only seen on the next poll. To feel responsive (press a wall button → HA reacts) this must be ~1 s, and presses are read via **counters** so a momentary tap shorter than the interval is never missed.
- **Button → relay** stays instant and local on the module (mapping matrix), unaffected by either.

So the default interval is **~1 s**, driven by how fast HA must observe button presses as automation triggers. Polling is still **strictly sequential** per device within a cycle (one serial wire); the design constraint is fitting the whole bus cycle inside the interval. Settings and mapping matrices are never read on the fast poll.

**Coalesce reads (bulk reads).** Combine contiguous registers/coils/bits of the same Modbus function into one wide transaction instead of one transaction per logical group (e.g. read a contiguous register span in a single call rather than four separate reads). This is the first lever on cycle time on a shared serial bus.

**Cycle budget.** At ~1 s the whole bus must be polled within the interval. At 9600 baud a transaction round-trip is tens of ms, so a handful of devices with coalesced reads fits comfortably; many devices may need a higher bus baud (WB supports up to 115200) or **tiered polling** — read the latency-critical inputs every cycle and relay/diagnostic state less often. Coalescing first, then baud and tiering.

Coordinator data is keyed by device, so one unreachable module does not blank the whole bus:

```python
@dataclass(frozen=True, slots=True)
class WBMR6CDeviceState:
    input_states: dict[int, bool]
    press_counts: dict[tuple[int, str], int]  # (input_number, event) -> count
    relay_states: dict[int, bool]
    relay_commands: dict[int, bool]

# coordinator.data: dict[int, WBMR6CDeviceState]   # device_id -> state
```

**Partial failure:** a read error for one device must not fail the whole update. Catch per-device errors, omit that device from `data` (its entities go unavailable), and keep the rest. Only a port-level failure (the serial connection itself) should fail the coordinator update and mark the entire bus unavailable.

### Writes and refresh

There is **no push** from Modbus and no way to subscribe to a hub's reads — the coordinator is the only update mechanism, and entities subscribe to it via `CoordinatorEntity`.

A relay command does not wait for a poll: the write acquires the per-transaction transport lock, interleaves between the coordinator's per-device reads, and runs within ~one transaction (see [Transport Adapter](#transport-adapter)). So command latency is independent of the poll interval.

Do **not** force `async_request_refresh()` immediately after a one-shot relay write: the relay may not have actuated yet, so the read races the write and the switch visibly bounces back. Instead use **optimistic state** — set the expected `is_on` in memory right after a successful write and let the next scheduled poll confirm or correct it. This gives instant UI feedback without the race and without an extra round trip.

## Entity Model

Recommended initial platforms:

- `switch` for relay outputs 1..6;
- `event` for button **presses** (short/long/double/short-then-long) on inputs 1..6 and input 0 — these are the HA automation triggers, driven by counter deltas (see [Input Behavior](#input-behavior));
- `binary_sensor` for input **level** 1..6 and input 0 (for contacts used as steady on/off signals, not momentary buttons);
- `sensor` for diagnostic read-only values if needed later.

These entities reflect live state, fire button-press events, and issue relay commands — they are the integration's core HA surface, driven by the coordinator.

Device **settings** and the **mapping matrix** are exposed by the device client as read/write operations (see [Settings Backend](#settings-backend) and [Mapping Matrix](#mapping-matrix)). How they are represented or edited in the UI — entities, options flow, a panel — is out of scope for this backend document.

The UI-facing configuration endpoint is allowed to compose those two backend
surfaces when one user action must update both. In particular, editing local
input-to-relay behavior needs both input modes and mapping matrices: legacy
input modes (`0`, `1`, `2`, `3`) define local behavior without matrix cells,
while matrix behavior requires input mode `4` (signal edges) or `6` (button
press types).

## Device Registry

Each device subentry maps to one Home Assistant device; all of that module's entities share it. The device is registered against its subentry (`config_subentry_id`) so HA shows it under the right bus entry.

Identifiers must include the bus, because `device_id` repeats across buses:

```python
identifiers={(DOMAIN, f"{serial_port}:{device_id}")}
```

Suggested metadata:

```python
manufacturer="Wiren Board"
model="WB-MR6C v.2"
name=f"WB-MR6C {device_id}"
```

Populate `model` from the model register and `sw_version` from the firmware string read at setup (see [Identification](#identification-model--firmware)) so the real model and firmware show on the HA device page:

```python
sw_version=firmware    # e.g. "1.3.1", parsed from registers at 250
```

## Entity Unique IDs

Entity unique IDs must be globally stable and **include the bus**, because `device_id` repeats across buses (see [Uniqueness](#uniqueness)). Shape: `{serial_port}:{device_id}:{entity}`.

Examples (for `/dev/ttyUSB0`, device 1):

```text
openwb_ttyUSB0_1_relay_1
openwb_ttyUSB0_1_input_1
openwb_ttyUSB0_1_input_0
openwb_ttyUSB0_1_input_1_press
openwb_ttyUSB0_1_safe_state_1
```

Sanitize the serial port into the id (e.g. `/dev/ttyUSB0` → `ttyUSB0`) but keep enough to stay unique across dongles. Two modules sharing a slave address on different dongles thus get distinct entity ids.

## Relay Switch Behavior

Relay switch entities should represent the actual relay state, not only the command coil.

Recommended behavior:

- `is_on` uses actual relay state from discrete inputs;
- `async_turn_on` writes the one-shot ON coil;
- `async_turn_off` writes the one-shot OFF coil;
- optional `async_toggle` writes the one-shot TOGGLE coil when exposed by UI/service.

After any write (optimistic, see [Writes and refresh](#writes-and-refresh)):

1. perform the Modbus write;
2. set the expected state optimistically and write it to HA immediately;
3. let the next scheduled coordinator poll confirm or correct it.

Do not force an immediate refresh — a one-shot coil write read back too early races the relay actuation.

## Input Behavior

Inputs surface in two complementary ways. Inputs `1..6` and input `0` are both covered; input `0` must be handled explicitly because the documentation treats it as a valid row distinct from `1..6` (and it lives at `base + 7` in counter/matrix layouts).

### Level — `binary_sensor` (read-only)

Reflects the instantaneous input state from discrete inputs. Useful only for inputs wired as steady on/off signals (toggle switches, contacts). A momentary button press will almost never be caught here and should not be modeled this way.

### Presses — `event` (counter-driven)

Buttons double as HA automation triggers, so presses **are** polled every cycle (see [Coordinator](#coordinator)) — from the press counters in the [Register Model](#register-model), not from level, because a momentary tap shorter than the interval would be missed by level polling. The coordinator owns the detection so that what reaches automations is a clean press event, not a raw counter:

1. each poll reads the counters and compares them with the previous poll;
2. a positive delta fires the matching `event` (short / long / double / short-then-long) for that input;
3. handle **wraparound** with `(current - previous) & 0xFFFF`;
4. on the first read after setup/reconnect there is no baseline — record the counter and fire **nothing** (do not emit a press for the initial delta).

The `event` platform is usable as an automation trigger directly; a `device_trigger` can be added later for nicer editor UX without changing the detection logic.

## Settings Backend

Settings reads and writes should be separate from fast polling.

Use explicit methods:

```python
await client.read_basic_settings()
await client.set_input_mode(input_number, mode)
await client.set_debounce_ms(input_number, value)
await client.set_mapping_action(event, input_number, output, action)
```

Do not read all settings and all mapping matrices on every coordinator update; they are read and written on demand, separately from the fast poll. The client exposes these as read/write operations — how they are surfaced or edited in the UI is out of scope for this backend document.

## Mapping Matrix

The mapping matrix holds the on-device button→relay links the WB module acts on locally. It is the main thing HA configures on the input side (see [Goals](#goals)).

**Backend contract (UI is out of scope).** This document defines only what the backend exposes; how the matrix is presented or edited is a UI concern and not covered here. The backend must:

- **read** the current matrix and hand it out as plain data;
- **accept** a desired new matrix from the caller and apply it to the controller, writing **only the changed cells** (diff against the current state to minimise Modbus writes);
- **validate** inputs/outputs/actions locally before writing.

Representation (per event):

```python
dict[tuple[int, int], int]   # (input_number, output_number) -> action
```

For WB-MR6C v.2:

- events: short / long / double / short-then-long press, falling / rising edge;
- inputs: `1..6` and `0`;
- outputs: `1..6`;
- matrix register rows are spaced by 8 because the generic Wiren Board matrix is 8 columns wide.

The matrix is loaded on demand (never on the fast poll): it is large and changes only when the configuration is edited.

The UI-facing write contract for matrix configuration must include the complete
desired input-mode set for the device along with the desired matrix rules. The
backend validates the two together before writing:

- `input_modes` must cover every input exposed by the selected device;
- `input 0` must not be written with modes `0` or `1`;
- mode `5` is unused and must not be written;
- rules for press events require input mode `6`;
- rules for falling/rising edge events require input mode `4`;
- legacy modes may be saved with no matrix rules for that input.

After validation, write the mapping matrices and then write the requested input
modes. This keeps the device's active input mode explicit instead of inferring
it from the presence of non-empty matrix cells.

## Services

Custom services are optional, but useful for development and advanced operations.

Potential services:

- `openwb.refresh`;
- `openwb.relay_toggle`;
- `openwb.write_mapping_action`;
- `openwb.read_mapping_matrix`.

Services should call the same backend client methods used by entities. Do not duplicate register logic in service handlers.

## Error Handling

Transport errors should be converted to Home Assistant-friendly exceptions at the integration boundary:

- a failed serial-port open in the bus `async_setup_entry` raises `ConfigEntryNotReady` so HA retries setup with backoff;
- `async_unload_entry` closes the bus transport so the serial port is released and no master leaks across reloads;
- a per-device read error marks only that device's entities unavailable (omit it from coordinator data); a port-level failure raises `UpdateFailed` and marks the whole bus unavailable;
- write failure raises `HomeAssistantError` with a clear message;
- invalid user input fails before writing to Modbus;
- repeated connection failures should not spam logs — `DataUpdateCoordinator` already logs once and suppresses identical repeats, so no extra throttling is needed.

