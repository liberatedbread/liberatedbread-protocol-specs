# Anova Precision Cooker Mini

> **Status**: Spec Available (untested)
> **Protocol**: BLE (JSON wrapped in Base64)
> **Manufacturer**: Anova Applied Electronics
> **Manufacturer Status**: Active

## Overview

The first **Anova Precision Cooker Mini** has a phone-direct BLE protocol that
needs no Anova account or cloud API. It uses UTF-8 JSON objects wrapped in
standard padded Base64, with separate characteristics for setpoint, current
temperature, timer, state, clock and system information.

This is a different protocol from both the original Precision Cooker's ASCII
commands and the [Nano's COBS/protobuf protocol](anova-precision-cooker-nano.md).
It does not cover later Mini/Lite hardware, Wi-Fi models or Anova's cloud API.
The full machine-readable profile is
`device-specs/devices/anova-precision-cooker-mini.yaml`.

Anova's developer pages and MIT reference client are the protocol sources. The
unified Android app 3.6.6 also contains all seven UUIDs in its React Native
bundle, including the `96e3` clock UUID. That static check does not prove current
app-to-Mini compatibility, command framing or a successful hardware connection.
Nobody on this project has driven a Mini from this document.

!!! warning "Remote immersion heating"
    Starting a cook and changing the setpoint are **advanced** commands in the
    spec. Confirm the current unit, value, timer and physical setup with the
    owner present, and keep stop immediately available. No authentic Mini manual
    was recovered, so this page gives no safe temperature range or water-depth
    rule. Follow the cooker's own vendor instructions. A successful BLE write is
    not proof that heating started or stopped; read STATE afterwards.

## Hardware and evidence boundary

| Property | Value |
|----------|-------|
| Model | Precision Cooker Mini (the Mini-specific developer API; called Gen 3 by its reference client) |
| Radio | BLE GATT, local phone-direct |
| Cloud | Not used by the documented BLE protocol |
| Companion app | Anova Culinary, Android `com.anovaculinary.android`; 3.6.6 checked statically for UUIDs only |
| Verification | Official docs/client plus offline fake-transport checks; no hardware capture or live test |
| Out of scope | Original cooker, Nano, A2/A3, later Mini/Lite, Wi-Fi/cloud, firmware update |

## Initial Setup

| Property | Value |
|----------|-------|
| Setup required | No network provisioning |
| Method | `ble_direct` |
| Advertised match | Service `910772a8-a5e7-49a7-bc6d-701e9a783a5c` |
| Passphrase protection | `not_applicable` |
| Confidence | medium (official source, not replayed here) |

1. Scan for the custom service and connect. A user-supplied name prefix is only
   a secondary filter; no fixed Mini advertised name is asserted.
2. Accept the host's pairing request. Anova says refusing it disconnects the
   Mini. No fixed PIN or application key is documented.
3. Verify all six characteristics before sending anything.
4. Set the clock to current UTC with response required.
5. Read STATE and record `temperatureUnit` before interpreting a temperature or
   sending a setpoint.

**Factory reset**: not fully understood. The reference client says a ten-second
top-button hold turns off the light and permits pairing again. It does not say
whether bonds, history, clock, unit or other settings are erased. The spec marks
reset `unknown`; do not present this as a proven full factory reset.

**Rebinding**: there is no router to rejoin. Pair the new host and, only if
needed, use the top-button recovery. Whether the old bond must first be removed
is unknown.

## Pairing

| Property | Value |
|----------|-------|
| Pairing required | **Yes**, per the official Mini client |
| Security mode | Unknown; accepting a prompt does not name the association model |
| Bonding | Required; capacity and reconnect behavior unknown |
| PIN | None documented |
| One central / one bond | Unknown / unknown |
| Confidence | medium for the requirement, low for those details |

No separate pairing-mode button window is documented. Closing other clients is
the first recovery step. No standalone unpair procedure was found, and the
original cooker's fixed `0000` PIN does not apply here.

## Protocol Summary

### GATT map

| Role | UUID | Use |
|---|---|---|
| Service | `910772a8-a5e7-49a7-bc6d-701e9a783a5c` | Advertised match and service verification |
| SET_TEMPERATURE | `0f5639f7-3c4e-47d0-9496-0672c89ea48a` | Setpoint object, write without response |
| CURRENT_TEMPERATURE | `6ffdca46-d6a8-4fb2-8fd9-c6330f1939e3` | Read current bath temperature |
| TIMER | `a2b179f8-944e-436f-a246-c66caaf7061f` | Read running/remaining seconds |
| STATE | `54e53c60-367a-4783-a5c1-b1770c54142b` | Read state; unit/start/stop writes without response |
| SET_CLOCK | `d8a89692-cae8-4b74-96e3-0b99d3637793` | UTC timestamp, write with response |
| SYSTEM_INFO | `153c9432-7c83-4b88-9252-7588229d5473` | Read name, firmware and serial; never publish a real serial |

The overview, API reference, pinned client and app bundle support `96e3` for the
clock. One official BLE page prints `96c3`; retain that as a documentation
conflict until a real GATT table settles it, not as a second address to probe
with writes.

### Encoding

For a command:

1. Build the command's JSON object.
2. Serialize it as UTF-8.
3. Apply standard Base64 with `=` padding.
4. Write the Base64 ASCII bytes to the selected characteristic.

Reverse those steps for a read, requiring valid Base64, UTF-8 and a JSON object.
Legal JSON whitespace is not significant. Malformed input is an error, not an
empty object or zero temperature. No universal MTU, long-write or fragmentation
rule is known.

| Operation | Destination | Logical JSON object |
|---|---|---|
| Set target | SET_TEMPERATURE | `{"setpoint":65.0}` |
| Change unit | STATE | `{"command":"changeUnit","payload":{"temperatureUnit":"C"}}` (or `F`) |
| Start | STATE | `{"command":"start","payload":{"setpoint":65.0,"timer":3600,"cookableId":"recipe123","cookableType":"recipe"}}` |
| Stop | STATE | `{"command":"stop"}` |
| Set clock | SET_CLOCK | `{"currentTime":"2024-02-06T12:00:00+00:00"}` (use actual current UTC) |

Temperatures use the current STATE unit, not a unit embedded in each command.
Start timer values are integer seconds. The reference emits all four start
payload fields; the example recipe strings are not real cloud identifiers and
zero-timer semantics are unknown.

Two exact source vectors are:

| Meaning | Base64 ASCII |
|---|---|
| Set target 65.0 | `eyJzZXRwb2ludCI6IDY1LjB9` |
| Stop | `eyJjb21tYW5kIjogInN0b3AifQ==` |

`scripts/test_anova_precision_cooker_mini.py` independently rebuilds these and
additional synthetic vectors using only the standard library and the spec.

### Responses and limitations

- STATE examples contain `state`, `temperatureUnit`, optional
  `currentTemperature` and a timer object. Only `idle` and `cooking` are
  documented state words; preserve others as unknown.
- CURRENT_TEMPERATURE returns `{"current":65.0}` in the current unit. Do not
  convert Fahrenheit again or replace a failed read with zero.
- TIMER returns `{"running":true,"remaining":3600}`. Standalone timer-write
  payloads and completion semantics are unknown.
- SYSTEM_INFO includes a per-unit serial; use invented values in fixtures.
- `INVALID_TEMP` is the only published example error code. There is no complete
  error catalogue or universal response envelope.
- Polling is demonstrated. Notification support is advertised, but subscription
  requirements and notification schemas are not; do not assume they equal read
  payloads.

## Tools Used

- [x] Anova Mini developer documentation and pinned MIT reference client
- [x] Offline fake-transport and standard-library vector checks
- [x] Static UUID check of the unified Android app bundle
- [ ] Authentic Mini manual, real GATT/notification capture and attended hardware
  verification — still needed

## References

- [Anova Mini overview](https://developer.anovaculinary.com/docs/devices/mini/overview)
- [Anova Mini BLE protocol](https://developer.anovaculinary.com/docs/devices/mini/ble-protocol)
- [Anova Mini commands](https://developer.anovaculinary.com/docs/devices/mini/commands)
- [Anova Mini API reference](https://developer.anovaculinary.com/docs/devices/mini/api-reference)
- [Official MIT Mini reference client](https://github.com/anova-culinary/developer-project-mini)
- [Mini quickstart-guide landing page](https://support.anovaculinary.com/hc/en-us/articles/32668242410765-Anova-Precision-Cooker-Mini-Quickstart-Guides)
- [Original Anova Precision Cooker](anova-precision-cooker.md)
- [Anova Precision Cooker Nano](anova-precision-cooker-nano.md)
- [Pairing, Bonding and Unpairing](../protocols/pairing.md)

## Contributors

- Liberated Bread follow-up: model-scoped spec and independent vectors from the
  cited public sources; no hardware claims.
