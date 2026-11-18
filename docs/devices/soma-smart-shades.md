# SOMA Smart Shades 2 / Tilt 2 / Smart Shades 3

> **Status**: Spec Available (untested)
> **Protocol**: BLE GATT, two incompatible generations
> **Manufacturer**: Wazombi Labs OÜ
> **Manufacturer Status**: Active

## Danger: Select the Generation First

**V3's `51 00` is a framed Zigbee-enabled read. A bare `0x51` written to V2's
legacy device service is reported to factory-reset the motor and require the
vendor app for recovery.** Never send V3 frames to V2, never probe with a bare
opcode, and never fall back to the other protocol after a failure.

- **V2**: company ID `0x0370`, manufacturer version below `0x10`, exact local name
  `S`, fixed characteristic values.
- **V3**: company ID `0x0370`, manufacturer version at least `0x10`, normally no
  local name, `type | length | data` framing. Its control service is discovered
  after connection and is not a reliable scan filter.

Persist the selected generation. A missing payload or expected service means stop,
not try the other command map.

## Initial Setup

| Property | Value |
|----------|-------|
| Setup required | No network provisioning; safe travel limits must already exist |
| Method | `ble_direct`, selected as V2 or V3 |
| Passphrase protection | `not_applicable` |
| Confidence | Medium (public clients; no motor replay here) |

V2 accepts one central at a time according to the community client. Close the
vendor app and any bridge first. ATT permissions and bonding are unverified on
both generations; the absence of an app-layer key in public clients is not proof
that every unit accepts unauthenticated writes.

**Factory reset**: No procedure is offered. The V2 bare-`0x51` warning above is
to prevent an accidental reset, not to authorize one.

**Rebinding**: Disconnect the old central and repeat passive generation selection
on the new one. No Wi-Fi rejoin or factory reset is needed.

## Core Protocol

Positions are percent **closed**: 0 is open and 100 is closed. Invert only for a
UI that uses percent open. Tilt 2 uses 0 for closed upwards, 50 for open and 100
for closed downwards.

### V2 — Smart Shades 2 and Tilt 2

| Characteristic | Use |
|----------------|-----|
| `00001525-b87f-490c-92cb-11ba5ea5167c` | Read/notify current position; first byte is percent closed |
| `00001526-b87f-490c-92cb-11ba5ea5167c` | Read/write one-byte target percent closed |
| `00001530-b87f-490c-92cb-11ba5ea5167c` | Motor: stop `00`, stop at next step `01`, step up `68`, up `69`, step down `86`, down `96` |
| `00001531-b87f-490c-92cb-11ba5ea5167c` | Identify/beep: write `01` |
| `0000ba71-b87f-490c-92cb-11ba5ea5167c` | Little-endian uint16 voltage, raw × 10 mV |

Tilt 2 has a separate cover mapping: ordinary open writes target position `0x32`
(50) to `00001526-b87f-490c-92cb-11ba5ea5167c`, rather than issuing motor-up and
ending closed upwards at position 0. Ordinary close remains closed downwards at
100; position 0 is available as an explicit target for closed upwards.

V2 advertisement byte 1 supplies only the Tilt bit `0x80` here. It is not emitted
as battery percentage. The standard battery characteristic also has unresolved
semantics and is not used. The voltage-to-percent conversion in the YAML is an
estimate, not a transmitted percentage.

### V3 — Smart Shades 3

Service `8998a466-a65f-4d49-90b2-927f41c55190` contains command write
`8998a466-a65f-4d49-90b2-927f41c55191` and response read
`8998a466-a65f-4d49-90b2-927f41c55192`.

Requests and replies are `opcode | length | data`. Ordinary calibrated open and
close are the fixed set-position frames `08 01 00` and `08 01 64`. Raw `01 00`
and `02 00` are advanced, explicitly uncalibrated jog operations only: a
calibrated shade ignores them, and an uncalibrated jog must be time-bounded and
followed by stop `03 00`. Get closed percent uses `0a 00`, battery percent uses
`0b 00`, and identify uses `17 00`. After writing, perform a plain GATT read and
verify both opcode and declared length so a stale response is not accepted as
success.

`scripts/test_soma_smart_shades_spec.py` checks generation selection, V2/V3
vectors, entity-to-command mappings, malformed frames and the reset-collision
guard.

## Out of Scope

Calibration and encoder/direction operations, schedules, triggers, OTA, Zigbee
control/reset, SOMA Connect U1, original Tilt and Smart Shades 1, and speculative
battery decoding. No live device calls were made.

## References

- [SOMA community protocol documents](https://github.com/rzuppur/smart-shades-documentation)
- [vanderkley/soma-shades](https://github.com/vanderkley/soma-shades)
- [pete-jorgensen/soma-ble](https://github.com/pete-jorgensen/soma-ble)
- [SOMA Smart Shades 3 installation guide](https://www.somasmarthome.com/install-guide/ss3)
