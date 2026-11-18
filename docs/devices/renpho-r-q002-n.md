# RENPHO R-Q002 N exercise bike (read-only)

> **Status**: Spec Available — public-capture evidence, untested on hardware
> **Protocol**: BLE FTMS + Cycling Power; conditional CSC
> **Manufacturer**: RENPHO / Joicom corporation (active)

## Overview

The R-Q002 N exposes standard local telemetry without an AI Gym account,
course, racing service or proprietary UART session. This guide adds only the
model-specific resistance scale and capture findings; the shared FTMS reference
spec is unchanged. The machine-readable spec is
[`renpho-r-q002-n.yaml`](https://github.com/liberatedbread/liberatedbread-protocol-specs/blob/main/device-specs/devices/renpho-r-q002-n.yaml).

A public HCI capture attached to QZ issue 2401 confirms FTMS and Cycling Power
Service. It does **not** contain Cycling Speed and Cadence Service. The open QZ
driver subscribes to CSC when present, so this spec retains CSC as a conditional
standard endpoint and does not mislabel it capture-verified.

## Initial Setup and pairing

| Property | Value |
|----------|-------|
| Setup required | No |
| Method | `ble_direct` (medium confidence) |
| BLE pairing/bond | None required by the reviewed local path |
| Credentials | None |
| Control writes | None |

Select the bike as an R-Q002 N candidate, close competing fitness apps, connect
and enumerate the services. Subscribe only to telemetry. FTMS is shared by many
manufacturers and does not uniquely identify this model; no reliable advertised
local name was established, so the spec does not invent one.

**Factory reset**: unknown. No exact manual or reset procedure was acquired.
Stopping a workout, power-cycling the console or deleting an OS bond is not a
documented factory reset.

**Rebinding**: disconnect the old central, reconnect and enumerate services
again. No bike network or account credential is involved in this path.

## Protocol Summary

| Role | UUID | Evidence |
|------|------|----------|
| Fitness Machine Service | `00001826-0000-1000-8000-00805f9b34fb` | Capture-confirmed |
| Indoor Bike Data | `00002ad2-0000-1000-8000-00805f9b34fb` | Capture-confirmed primary stream |
| FTMS Control Point — do not use | `00002ad9-0000-1000-8000-00805f9b34fb` | Enumerated, deliberately unused |
| Cycling Power Service | `00001818-0000-1000-8000-00805f9b34fb` | Capture-confirmed |
| Cycling Power Measurement | `00002a63-0000-1000-8000-00805f9b34fb` | Capture-confirmed |
| Cycling Speed and Cadence Service | `00001816-0000-1000-8000-00805f9b34fb` | Conditional, source-reported only |
| CSC Measurement | `00002a5b-0000-1000-8000-00805f9b34fb` | Conditional, source-reported only |

### Indoor Bike Data

Read flags as little-endian `uint16` and consume fields in standard order.
Instantaneous speed is present when More Data (bit 0) is **clear**. Reject a
payload truncated in any selected field or carrying unhandled flags/trailing
bytes.

| Flag | Field and decode |
|------|------------------|
| 0 clear | Instantaneous speed `uint16 / 100 km/h` |
| 1 | Average speed `uint16 / 100 km/h` |
| 2 | Instantaneous cadence `uint16 / 2 rpm` |
| 3 | Average cadence `uint16 / 2 rpm` |
| 4 | Total distance `uint24` metres |
| 5 | Resistance raw `uint16`; R-Q002 normalized value is **raw / 2** |
| 6 | Instantaneous power **signed** `int16` watts |
| 7 | Average power **signed** `int16` watts |
| 8 | Five-byte energy group: total `uint16` kcal, hourly `uint16` kcal/h, per-minute `uint8` kcal/min |
| 9 | Heart rate `uint8` bpm |
| 10 | Metabolic equivalent `uint8 / 10` MET |
| 11 | Elapsed time `uint16` seconds |
| 12 | Remaining time `uint16` seconds |

The capture vector `64 00 68 01 6a 00 83 00 49 00` decodes to 3.60 km/h,
53 rpm, raw resistance 131 (65.5 normalized) and 73 W. A separate synthetic
vector checks `-2 W`, every optional field and the energy group. The energy
group must consume all five bytes before heart rate is read.

Accept device distance only when bit 4 is present. Any speed-integrated
replacement is host-estimated and must be labelled as such. Do not implement the
open driver's optional UI resistance doubling or its knob-to-automatic-control
feedback loop.

### Cycling Power and conditional CSC

Cycling Power Measurement always starts with flags followed by signed
little-endian `int16` instantaneous power at offset 2. One captured measurement
has a still-unexplained trailing byte, which is not decoded.

When CSC is genuinely enumerated, its standard flags add wheel revolution data
(`uint32` plus `uint16` event time) for bit 0 and crank revolution data (`uint16`
plus `uint16` event time) for bit 1, all little-endian. Event times are in
1/1024-second units. Validate those groups before accepting their values.

## Validation and omissions

`scripts/test_renpho_r_q002_n_spec.py` uses only standard-library parsing. It
checks the public sample, signed power, all optional fields, five-byte energy
accounting, CSC truncation and malformed Indoor Bike Data. No motion command is
encoded or sent.

Control Point operations, resistance writes, ERG, calibration, firmware,
sessions and other RENPHO models are excluded. Reset, exact advertised name,
negative-power behavior on hardware and one Cycling Power trailing byte remain
open.

## References

- [Public R-Q002 N capture — QZ issue 2401](https://github.com/cagnulein/qdomyos-zwift/issues/2401)
- [Pinned QZ RENPHO driver](https://github.com/cagnulein/qdomyos-zwift/tree/afd4f90db35ed7ee29c76a6c19b84de4cf558922/src/devices/renphobike)
- [Bluetooth SIG Fitness Machine Service 1.0](https://www.bluetooth.com/specifications/specs/fitness-machine-service-1-0/)
