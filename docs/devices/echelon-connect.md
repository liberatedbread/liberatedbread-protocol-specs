# Echelon Connect bikes and Stride treadmills (pre-July-2025 firmware)

> **Status**: Spec available (derived from open clients; not tested on hardware here)
> **Protocol**: BLE (vendor GATT service)
> **Manufacturer**: Echelon Fitness
> **Manufacturer Status**: Active

## Overview

Echelon's Connect bikes have no screen, and its Stride treadmills have only a
basic console. The vendor app normally drives both over BLE. On firmware
released **before July 2025**, they use a plain BLE profile with no
authentication. Two open clients implement it: QZ (qdomyos-zwift, GPL-3.0)
for bikes and treadmills, and Gymnasticon (MIT) for bikes. This page and
`device-specs/devices/echelon-connect.yaml` keep that profile usable for
machines that were never updated and for second-hand machines.

**Scope.** From July 2025, Echelon firmware makes the machine wait for a
server-issued challenge before it streams metrics. This spec does not apply
to machines running that firmware, and it says nothing more about it.

Echelon is still trading. It is listed as *active*, not abandoned.

## Hardware

| Property | Value |
|----------|-------|
| Models | Connect bikes (EX-3, EX-4s, EX-5/5s, EX-7s, EX-15, Connect Sport); Stride treadmills |
| Radio | BLE |
| Category | `fitness` |
| Companion app | Echelon Fit (vendor) |

QZ's compatibility wiki lists EX-3, EX-4s, EX-5/5s and EX-7s as accepting
software resistance changes. It lists the Connect Sport and EX-15 as
manual-knob bikes, which report data but cannot be set. It lists the EX-8s
as not working. No source gives a way to tell these apart over BLE.

## Initial Setup

| Property | Value |
|----------|-------|
| Setup required | No |
| Method | `ble_direct` |
| Advertised name | `ECH…` (bikes), `ECH-STRIDE…`, `ECH-UK-…`, `ECH-FR-…`, `ECH-SD-SPT…`, `STRIDE…`, `STRIDE6S-…` (treadmills) |
| Passphrase protection | not_applicable |
| Confidence | medium (two public clients, not replayed here) |

**Factory reset**: none is described in the sources used. A reset would not
roll back firmware.

**Pairing**: none. Both clients connect, subscribe and write without
bonding. Close the vendor app before connecting.

## Identification

Bikes advertise service `0bf669f0-45f2-11e7-9598-0800200c9a66`. Match on that
service as well as the name: the bare prefix `ECH` also matches other brands'
machines (for example `ECHO_BIKE_…`). Check the specific prefixes first, as
QZ does:

| Prefix | Machine | Covered |
|---|---|---|
| `ECH-EC-SPT` | stair climber | no |
| `ECH-STRIDE`, `ECH-UK-`, `ECH-FR-`, `ECH-SD-SPT`, `STRIDE`, `STRIDE6S-` | Stride treadmill | yes (except Stride 4) |
| `ECH-ROW`, `ROWSPORT`, `ROW-S` | rower | no |
| any other `ECH…` | Connect bike | yes |

Stride 4 units (`STRIDE4…`) need extra initialisation in QZ that is not
documented here.

## Protocol Summary

### BLE Services

| UUID | Name | Description |
|------|------|-------------|
| `0bf669f0-45f2-11e7-9598-0800200c9a66` | advertised service | Scan filter only |
| `0bf669f1-45f2-11e7-9598-0800200c9a66` | vendor service | Holds the three characteristics below |
| `0bf669f2-45f2-11e7-9598-0800200c9a66` | write | All commands, written with response |
| `0bf669f3-45f2-11e7-9598-0800200c9a66` | notify 1 | Subscribed by QZ; contents unrecorded |
| `0bf669f4-45f2-11e7-9598-0800200c9a66` | notify 2 | Metric frames |

### Framing

Every frame in both directions has the same layout:

| Offset | Length | Description |
|--------|--------|-------------|
| 0 | 1 | `0xf0` |
| 1 | 1 | frame type |
| 2 | 1 | payload length |
| 3 | n | payload (multi-byte values big-endian) |
| 3+n | 1 | sum of all earlier bytes, modulo 256 |

### Connecting

1. Subscribe to both notify characteristics.
2. Write `f0 a1 00 91` four times, then `f0 a3 00 93`, then `f0 a1 00 91`.
   QZ copied this sequence from the vendor app's log. The replies are not
   decoded.
3. **Bike:** write `f0 b0 01 01 a2` to start the stream. Gymnasticon sends
   only this frame after subscribing.
   **Treadmill:** QZ sends `f0 a4 00 94` *before* step 2. Never send
   `f0 b0 01 01 a2` while connecting to a treadmill: on a treadmill it starts
   the belt.
4. Optionally poll every 2 s with `f0 a0 01 <counter> <sum>`, where the
   counter runs 1–255 and skips 0. QZ always polls. Gymnasticon never polls a
   bike and still receives data.

### Commands

| Frame | Bike | Treadmill |
|---|---|---|
| `f0 b0 01 01 a2` | start stream | start belt, followed by `f0 d0 01 00 c1` and `f0 d0 01 11 d2` |
| `f0 b0 01 00 a1` | not used | stop belt |
| `f0 b1 01 <v> <sum>` | set resistance 1–32 (motorised models) | set incline 0–15 |
| `f0 b2 02 <hi> <lo> <sum>` | not used | set speed, km/h × 1000 big-endian (QZ limit 22 km/h) |

### Notifications

| Type | Family | Layout |
|---|---|---|
| `0xd1` | bike (13 bytes) | bytes 3–4 elapsed s (BE); 7–8 distance raw/100, unit unconfirmed; byte 10 cadence rpm |
| `0xd1` | treadmill | byte 11 heart rate bpm, 0 = none |
| `0xd2` | bike | byte 3 resistance level 1–32, sent only on change |
| `0xd2` | treadmill | byte 3 incline |
| `0xd3` | treadmill | bytes 3–4 speed raw/1000 km/h (BE); probably mph on consoles set to miles |
| `0xd0` | treadmill | meaning unknown |

**Treadmills expect acknowledgements.** Write every `0xd0`, `0xd2` and `0xd3`
frame straight back to the write characteristic unchanged, as QZ does.

Bikes do **not** report power, speed or heart rate. Gymnasticon estimates power
as `round(7.228958 × 1.090112^resistance × 1.015343^cadence)`. QZ uses a
resistance-by-cadence table, and estimates speed as `0.37497622 × cadence` km/h.
These are estimates, not readings.

## Safety

Treadmill speed, incline and start commands move the belt and deck under the
user. The spec marks them `advanced` and carries a `safety_advisory`. Send them
only when the user asks, with the safety key attached. Because
`f0 b0 01 01 a2` and `f0 b1 …` mean different things on bikes and treadmills,
identify the family from the name before sending anything beyond the shared
initialisation.

## Validation and remaining gaps

`scripts/test_echelon_connect_spec.py` rebuilds every example write from the
stated frame layout and decodes the example notifications with the stated
offsets and scales. All test values are invented.

Still unknown:

- how to tell, over BLE alone, which firmware a machine runs;
- the a1/a3/a4 replies and the `0xd0` frame;
- which frames use notify 1;
- the distance unit;
- the incline unit;
- the treadmill `0xd1` length;
- whether polling is required;
- Stride 4;
- rowers and the stair climber.

No physical machine was used.

## Tools Used

- Source reading of the open clients listed below (no captures)

## References

- [qdomyos-zwift (QZ, GPL-3.0)](https://github.com/cagnulein/qdomyos-zwift), pinned at `49be559ae85c1571a4a2323224e06e96c2867d32` (2025-06-30): `src/devices/echelonconnectsport/echelonconnectsport.cpp`, `src/devices/echelonstride/echelonstride.cpp`, `src/devices/bluetooth.cpp`
- [QZ issue #62: Echelon BLE log](https://github.com/cagnulein/qdomyos-zwift/issues/62)
- [QZ Equipment Compatibility wiki](https://github.com/cagnulein/qdomyos-zwift/wiki/Equipment-Compatibility)
- [Gymnasticon PR #76: Echelon bike client (MIT)](https://github.com/ptx2/gymnasticon/pull/76), `src/bikes/echelon.js` at `82aea215b92eef0152208964ab4c4f309bbd9df5`
- [Ars Technica, July 2025: firmware update hinders Echelon equipment's offline use](https://arstechnica.com/gadgets/2025/07/firmware-update-hinders-echelon-smart-home-gym-equipments-ability-to-work-offline/)

## Contributors

- Initial spec from public open-source clients
