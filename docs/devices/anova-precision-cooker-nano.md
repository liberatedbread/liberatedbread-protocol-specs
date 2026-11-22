# Anova Precision Cooker Nano

> **Status**: Spec Available (untested)
> **Protocol**: BLE (COBS-framed proto2)
> **Manufacturer**: Anova Applied Electronics
> **Manufacturer Status**: Active

## Overview

The BLE **Anova Precision Cooker Nano** uses a custom TX/RX/ASYNC service. A
logical command has a two-byte domain/type header and an optional proto2 payload;
the whole packet is COBS-encoded and followed by a zero delimiter. The official
client splits the framed result into writes of at most 20 bytes.

This is not the original cooker's ASCII protocol or the
[Mini's JSON/Base64 protocol](anova-precision-cooker-mini.md). Nano 3.0/Wi-Fi,
other Anova generations, bulk transfer, reset and cloud APIs are outside this
profile. The complete machine-readable version is
`device-specs/devices/anova-precision-cooker-nano.yaml`.

The executable MIT client and actual proto2 schema are primary. Cached web tables
conflict with them on the configuration domain and every normal opcode; this spec
uses the executable domain `0x00` map and preserves the conflict. The unified
Android app 3.6.6 corroborates all four UUIDs, but not the framing or live model
compatibility. No Nano was driven by this project.

!!! warning "Remote immersion heating"
    Starting a cook and changing its setpoint are **advanced** commands. Confirm
    the current unit, value, timer and physical setup with the owner present and
    keep stop available. No authentic Nano manual was recovered, so no safe
    temperature range or water-depth rule is asserted. A raw response or the
    reference client's optimistic local cooking flag is not proof of heating or
    stopping.

## Hardware and evidence boundary

| Property | Value |
|----------|-------|
| Model | BLE Precision Cooker Nano |
| Radio | BLE GATT, local phone-direct |
| Cloud | Not used by the official local client |
| Companion app | Anova Culinary, Android `com.anovaculinary.android`; 3.6.6 checked statically for UUIDs only |
| Verification | Official executable source/schema plus offline checks; no live test |
| Out of scope | Mini, original cooker, Nano 3.0/Wi-Fi, bulk transfer, firmware/reset, cloud |

## Initial Setup

| Property | Value |
|----------|-------|
| Setup required | No network provisioning |
| Method | `ble_direct` |
| Advertised match | Service `0e140000-0af1-4582-a242-773e63054c68` |
| Passphrase protection | `not_applicable` |
| Confidence | medium for the local flow, low for bonding details |

1. Scan for the service and connect. The 2019 third-party capture used the name
   `Nano`, but the official client matches the service, not that name alone.
2. Subscribe to RX first and ASYNC second.
3. A dedicated client must COBS-encode `get_temperature_unit` before sending it
   and wait with a timeout; no generic handler is provided by this spec.
4. Serialize later commands one at a time with stale-response rejection. ASYNC is
   logged for analysis, not decoded into a guessed state.

**Factory reset**: unknown. No physical procedure was recovered. A bulk-domain
reset message exists in the schema but is excluded; it is not an owner reset
procedure or evidence of what is cleared. Do not borrow the Mini's button hold.

**Rebinding**: there is no router to rejoin. Connect from the new host. Whether
an old bond must be removed, and how, is unknown; no reset is asserted necessary.

## Pairing

| Property | Value |
|----------|-------|
| Pairing required | **Unknown** |
| Security mode / bonding | Unknown / unknown |
| PIN or app key | None documented |
| One central / one bond | Unknown / unknown |
| Confidence | low |

The official client does not demonstrate whether every command works unbonded.
Do not inherit the original cooker's `0000` PIN or the Mini's explicit pairing
and reset flows. Start recovery with a read-only connection and unit request,
not a bulk-domain write.

## Protocol Summary

### GATT map

| Role | UUID | Use |
|---|---|---|
| Service | `0e140000-0af1-4582-a242-773e63054c68` | Advertised match |
| TX | `0e140001-0af1-4582-a242-773e63054c68` | Sequential command chunks |
| RX | `0e140002-0af1-4582-a242-773e63054c68` | Notifications carrying command responses |
| ASYNC | `0e140003-0af1-4582-a242-773e63054c68` | Notifications subscribed but not decoded by the official client |

The exact TX property set/write-response mode was not captured. Discover it
instead of forcing write-without-response. RX/ASYNC notification roles are
source-established.

### Framing and response handling

```text
[domain: 1 byte][message type: 1 byte][optional proto2 payload]
    -> COBS encode
    -> append 00 delimiter
    -> split encoded bytes, including delimiter, into <=20-byte TX writes
```

COBS is framing, not checksum or authentication. Use a strict decoder after
removing the delimiter. RX uses the source heuristic of completing on a chunk
shorter than 20 bytes or ending in zero, but needs a timeout, size bound, one
request in flight and stale-response rejection. Do not strip response headers by
searching for an arbitrary protobuf tag inside the body.

### Command map

All rows use configuration domain `0x00`. This catalogue is **documentary only**:
no `anova_nano_cobs` handler exists, and the spec has no executable
`value`/`template` fields or generic entity bindings. Logical packets live in
`protocol_details.logical_commands`; the final COBS/on-wire vectors are below.
A future dedicated client must perform the framing above. Start and stop must
never be emitted as raw logical packets, and a write result is not proof of an
on/off state.

| Operation | Type | Payload / response |
|---|---:|---|
| Set target | `0x03` | `IntegerValue.value = truncate(temperature x 10)` in current unit |
| Get target | `0x04` | Empty request; IntegerValue, raw tenths |
| Get sensors | `0x05` | Empty request; SensorValueList |
| Set unit | `0x06` | IntegerValue `0` = 0.1 °C, `1` = 0.1 °F |
| Get unit | `0x07` | Empty request; IntegerValue UnitType |
| Start | `0x0a` | Empty; advanced, no validated state response |
| Stop | `0x0b` | Empty; ordinary recovery command |
| Set timer | `0x10` | IntegerValue **minutes** |
| Get timer | `0x12` | Empty request; IntegerValue minutes |
| Get firmware | `0x1a` | Empty request; FirmwareInfo |

The timer is minutes in the executable method, README and prompts. A source-file
comment saying seconds is an internal error. The client's unused temperature
limits are not promoted to operating limits.

Exact source-generated vectors include:

| Meaning | Raw domain/type/payload | Framed bytes |
|---|---|---|
| Get unit | `00 07` | `01 02 07 00` |
| Get sensors | `00 05` | `01 02 05 00` |
| Start | `00 0a` | `01 02 0a 00` |
| Stop | `00 0b` | `01 02 0b 00` |
| Set target 65.5 | `00 03 08 8f 05` | `01 05 03 08 8f 05 00` |
| Set 0.1 °C | `00 06 08 00` | `01 03 06 08 01 00` |
| Set 60-minute timer | `00 10 08 3c` | `01 04 10 08 3c 00` |
| Get firmware | `00 1a` | `01 02 1a 00` |

`IntegerValue` is proto2 field 1, signed `int32`: tag `08` followed by a varint,
not a fixed-width integer. `scripts/test_anova_precision_cooker_nano.py`
independently rebuilds every frame and parses a synthetic sensor response.

### Units, sensors and unknown state

| UnitType | Meaning | Numeric temperature decode |
|---:|---|---|
| 0 / 1 | 0.1 °C / 0.1 °F | raw / 10 |
| 4 / 5 | 0.01 °C / 0.01 °F | raw / 100 |
| 6 / 7 | whole °C / °F | raw unchanged |
| 2 | Motor speed | Raw; motor-dependent unit unknown |
| 3 | Boolean | Zero false, nonzero true |

Sensor types are water (0), heater (1), triac (2), unused (3), internal (4),
water low (5), water leak (6) and motor speed (7). Preserve every entry and its
own unit. Water temperature is type 0 only; missing water data or an unknown unit
is an error/unknown, never zero or a default Fahrenheit fallback.

ASYNC is not a recovered state channel: the client only logs it. DeviceState and
alert messages in the schema are capture candidates, not proof of the ASYNC
envelope. MessageError values 0–8 likewise lack a documented error envelope.
Bulk transfer, system reset, message spoof and firmware operations are excluded.

## Tools Used

- [x] Anova Nano developer pages, actual MIT client and proto2 schema
- [x] Independent standard-library COBS/varint/sensor vectors and malformed-input
  checks
- [x] Static UUID check of the unified Android app bundle
- [ ] Authentic Nano manual, read-only hardware capture, pairing/ASYNC
  confirmation and attended stop/start verification — still needed

## References

- [Anova Nano overview](https://developer.anovaculinary.com/docs/devices/nano/overview)
- [Anova Nano BLE protocol](https://developer.anovaculinary.com/docs/devices/nano/ble-protocol)
- [Anova Nano implementation example](https://developer.anovaculinary.com/docs/devices/nano/implementation-example)
- [Official MIT Nano client and schema](https://github.com/anova-culinary/developer-project-nano)
- [Nano quickstart-guide landing page](https://support.anovaculinary.com/hc/en-us/articles/360003905251-The-Anova-Precision-Cooker-Nano-Quick-Start-Guide)
- [Third-party Nano capture discussion](https://github.com/neilpa/circulate/issues/7)
- [Original Anova Precision Cooker](anova-precision-cooker.md)
- [Anova Precision Cooker Mini](anova-precision-cooker-mini.md)
- [Pairing, Bonding and Unpairing](../protocols/pairing.md)

## Contributors

- Liberated Bread follow-up: model-scoped spec and independent vectors from the
  cited public sources; no hardware claims.
