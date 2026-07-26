# Common OBD-II / Vehicle Diagnostic Patterns

Cars, motorcycles and an increasing number of "smart" powersports vehicles expose a
diagnostic connector. Unlike a BLE gadget, almost nothing interesting on that connector
is standardised: the legislated OBD-II layer only covers emissions data. Everything an
owner actually wants — service interval reset, TPMS programming, ABS bleed, live sensor
data — sits in manufacturer-specific territory on top of the same transport.

That is the same shape as the rest of this repo: an open transport, a closed application
layer, and a paid tool in between.

!!! warning "Vehicles are safety-critical"
    The [clean-room rules](../CLEANROOM_RULES.md) exclude safety-critical devices. That
    exclusion applies in full to anything that steers, stops or propels: **do not** write
    to ABS, immobiliser, throttle or engine-map memory as part of protocol research, and
    never probe a vehicle that is moving or that someone else is about to ride. Read-only
    diagnostics on a stationary vehicle you own, on a stand, with the engine off, is the
    only mode of work described here.

## Layer cake

| Layer | What lives there | Standards |
|-------|------------------|-----------|
| Connector | Physical socket and pinout | SAE J1962 (16-pin, cars + older bikes), ISO 19689 (6-pin, Euro 5 bikes) |
| Physical/link | Signalling on the wire | ISO 9141-2, ISO 14230-4 (K-line), ISO 11898 (CAN), SAE J1850 |
| Transport | Segmentation of >7 byte payloads | ISO 15765-2 ("ISO-TP") |
| Application (legislated) | Emissions data, DTCs | ISO 15765-4 / SAE J1979 — "OBD-II modes" `01`–`0A` |
| Application (manufacturer) | Everything else | ISO 14229 ("UDS"), or a vendor dialect of KWP2000 |

The useful rule of thumb: **if a function is not emissions-related, it is not in the
OBD-II mode list, and you are looking at UDS or a vendor dialect.**

## Connectors

### SAE J1962 (16-pin)

The familiar trapezoid. Pins that matter:

| Pin | Signal |
|-----|--------|
| 4 | Chassis ground |
| 5 | Signal ground |
| 6 | CAN-H (ISO 15765-4) |
| 7 | K-line (ISO 9141-2 / ISO 14230-4) |
| 14 | CAN-L (ISO 15765-4) |
| 15 | L-line (rarely populated) |
| 16 | Battery +12 V (usually unswitched) |

Manufacturer-discretionary pins (1, 3, 8, 9, 11, 12, 13) are where vendors hide extra
buses. Do not assume they are unused.

### ISO 19689 (6-pin)

Euro 5 pushed motorcycles onto a compact sealed connector — JST MWT series, water-tight,
mounted under the seat per EU regulation 44/2014. Community-reported pinout
(**unverified against the paywalled standard**):

| Pin | Signal |
|-----|--------|
| 2 | CAN-H |
| 3 | Ground |
| 4 | Battery +12 V |
| 5 | CAN-L |

Pins 1 and 6 are optional/manufacturer-defined; K-line appears on one of them for bikes
that still carry a K-line ECU. 6-pin-to-J1962 adapter leads are commodity parts, which
means a bike with the new connector is still reachable with a normal OBD-II adapter —
provided the vendor did not also move the data.

## ISO-TP framing

Any UDS payload longer than 7 bytes is segmented by ISO 15765-2. This is the single most
common reason a cheap adapter "connects but the function fails".

| Frame | First byte(s) | Meaning |
|-------|---------------|---------|
| Single | `0L` | `L` = payload length (1–7), payload follows |
| First | `1LLL` | 12-bit total length, 6 payload bytes follow |
| Flow control | `3S BS ST` | Receiver's clear-to-send, block size, separation time |
| Consecutive | `2N` | `N` = sequence number 1–15, wrapping |

An 8-byte request therefore leaves the tester as two frames with a flow-control frame
coming back from the ECU in between. Clone ELM327 firmware frequently gets the transmit
side of this wrong, or ignores the ECU's requested separation time, which is why vendor
tools specify particular adapters by name.

## Application layer: the two dialects

### Legislated OBD-II modes

| Mode | Function |
|------|----------|
| `01` | Current powertrain data (PIDs) |
| `03` | Stored DTCs |
| `04` | Clear DTCs / MIL |
| `09` | Vehicle info (`09 02` = VIN) |

Broadcast request ID is `0x7DF` (functional); ECUs answer on `0x7E8`–`0x7EF`. Physical
addressing to the first ECU is `0x7E0` → `0x7E8`.

### UDS (ISO 14229) — where the interesting functions live

| Service | Name | Typical use in an owner-facing function |
|---------|------|------------------------------------------|
| `10` | DiagnosticSessionControl | `10 03` extended session — unlocks non-default services |
| `27` | SecurityAccess | `27 01` request seed, `27 02` send key |
| `22` | ReadDataByIdentifier | `22 <DID hi> <DID lo>` — read a value (odometer, service counter) |
| `2E` | WriteDataByIdentifier | `2E <DID> <data>` — write a value |
| `31` | RoutineControl | `31 01 <RID>` start a routine (bleed, calibrate, **reset**) |
| `3E` | TesterPresent | `3E 00` keepalive so the session does not time out |
| `11` | ECUReset | `11 01` hard reset |

A positive response echoes the service byte `+ 0x40` (`22` → `62`). A negative response
is `7F <service> <NRC>`; `7F .. 31` = request out of range, `7F .. 33` = security access
denied, `7F .. 7F` = service not supported in active session. Those three NRCs tell you
most of what you need while probing.

**The shape of nearly every "reset" function** is therefore:

```text
10 03                    -> 50 03 ...          enter extended session
27 01                    -> 67 01 <seed>       request seed        (if locked)
27 02 <key>              -> 67 02              answer challenge    (if locked)
3E 00 (every ~2 s)       -> 7E 00              keep session alive
31 01 <RID> [params]     -> 71 01 <RID> ...    run the reset routine
   or
2E <DID> <new value>     -> 6E <DID>           write the new counter
```

Finding the function means finding which of those last two it is, and with which
identifier. That is a search problem, not a cryptography problem.

## Adapters

| Adapter | Chipset | Notes |
|---------|---------|-------|
| OBDLink LX / MX+ | STN110/STN2120 | Correct multi-frame TX and flow control; the adapter vendor tools name explicitly |
| Vgate vLinker MC+ | ELM327 v4.3.2-class | Reported working for some vendor tools, not all functions |
| Generic "ELM327 v1.5" clone | Cloned firmware | Fine for mode `01`/`03`; unreliable for multi-frame UDS writes |
| SocketCAN interface (CANable, Kvaser, PCAN) | Native CAN | Best for research — full frame visibility, no AT-command layer in the way |

Useful ELM327/STN AT commands when probing:

```text
ATZ            reset
ATE0           echo off
ATSP6          protocol 6 = ISO 15765-4, 11-bit, 500 kbit/s
ATSH 7E0       set request header (physical addressing)
ATCRA 7E8      accept only this response ID
ATFCSH 7E0     flow-control header
ATFCSD 30 00 00  flow-control data (BS=0, STmin=0)
ATFCSM 1       use our flow control settings
ATST 64        timeout 100 ms
ATCAF0         CAN formatting off — raw frames, you do ISO-TP yourself
```

`ATCAF0` is the one that matters for research: with auto-formatting off you see exactly
what a vendor tool would have to send.

## Capture methodology

Ranked cheapest-first. The first option needs no CAN hardware at all and reuses the
Android capture workflow already used elsewhere in this repo.

1. **btsnoop the tool↔adapter link.** Vendor Android tools (TuneECU and friends) talk to
   a Bluetooth adapter over RFCOMM/SPP. Enable *Developer options → Enable Bluetooth HCI
   snoop log*, run the paid function once, pull `btsnoop_hci.log`, and open it in
   Wireshark. Because the ELM327 protocol is ASCII, the AT commands **and** the hex
   payloads are directly readable in the RFCOMM stream. This yields the exact request
   bytes without touching the vehicle bus.
2. **Passive CAN log across a known-good run.** T-tap CAN-H/CAN-L at the diagnostic
   connector, `candump -L can0 > before.log` while idle, run the vendor function, and
   diff. Vendor tool traffic is physically addressed, so filtering to `0x7E0`/`0x7E8`
   cuts the noise immediately.
3. **DID sweep.** With the vehicle stationary, walk `22 <DID>` across the manufacturer
   range and record every DID that answers `62`. Values that look like the odometer, the
   service-due distance, or a date are the write targets. Read-only, reversible, and it
   maps the address space before anything is written.
4. **Routine enumeration — last, and with care.** `31 01 <RID>` *executes* things. Do not
   sweep it blindly. Only invoke an RID recovered from an actual capture.

## What to write down

For each function, this repo wants the derived facts, not the vendor's binary:

- transport (`ISO 15765-4`, bitrate, 11- or 29-bit), request/response CAN IDs
- session and security prerequisites
- the request bytes, the positive response, and observed NRCs on failure
- which ECU actually owns the data (engine ECU vs instrument cluster vs ABS module)
- timing constraints (keepalive interval, post-write settle time)

## Worked examples

- [OBD-II Bluetooth Adapters](../devices/obd2-bluetooth-adapter.md) — the dongle itself:
  GATT families, Classic SPP, the AT/ST command set, and how to capture through it
- [Triumph Tiger 900](../devices/triumph-tiger-900.md) — service interval reset (SIA)
