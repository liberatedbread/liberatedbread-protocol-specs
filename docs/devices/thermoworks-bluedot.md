# ThermoWorks BlueDOT (read-only)

> **Status**: Spec Available — source-derived, untested on hardware
> **Protocol**: BLE GATT
> **Manufacturer**: ThermoWorks, Inc (active)

## Overview

BlueDOT supports direct offline temperature/alarm monitoring without a
ThermoWorks Cloud account. A client subscribes, waits for one exact 20-byte
notification, then disconnects. No commands are sent. The machine-readable spec
is [`thermoworks-bluedot.yaml`](https://github.com/liberatedbread/liberatedbread-protocol-specs/blob/main/device-specs/devices/thermoworks-bluedot.yaml).

Signals, Billows and every RFX product are outside this document. RFX MEAT uses
a separate RF link to its gateway and must not be described as phone-direct BLE.
The ThermoWorks Smoke IP integration is also unrelated.

**Food safety**: this community decode is not the only check to use for
doneness. Confirm with a calibrated thermometer and published safe minimums.
Disconnected probes and malformed notifications must not leave a stale reading
displayed as current.

## Initial Setup and pairing

| Property | Value |
|----------|-------|
| Setup required | No |
| Method | `ble_direct` (medium confidence) |
| BLE pairing/bond | None |
| Credentials | None |
| Notification wait | Up to 10 seconds, then disconnect |

Match the case-sensitive `BlueDOT` name prefix. Connect and subscribe to
`783f2991-23e0-4bdc-ac16-78601bd84b39` by characteristic UUID across the whole
GATT table. Its parent service UUID is unknown; do not assert that the same UUID
is a service or use it as an advertisement filter.

**Factory reset**: unknown. No verified BlueDOT reset procedure was acquired,
and procedures from other ThermoWorks products are not substitutes.

**Rebinding**: disconnect the previous client, then connect and subscribe from
the new one. Require a fresh exact-length notification before publishing state;
there is no Wi-Fi membership or bond.

## Protocol Summary

The only assigned UUID is notification characteristic
`783f2991-23e0-4bdc-ac16-78601bd84b39`. Reject every value whose length is not
exactly 20 bytes.

| Offset | Length | Type | Meaning |
|--------|--------|------|---------|
| 0 | 1 | `uint8` | Probe status: 0 connected, 3 disconnected |
| 1–4 | 4 | signed `int32` little-endian | Current temperature, whole device-selected degrees |
| 5–8 | 4 | signed `int32` little-endian | Alarm temperature, same encoding |
| 9 | 1 | flag | Alarm silenced, nonzero true |
| 10 | 1 | flag | Alarm disabled, nonzero true |
| 11 | 1 | enum | Units: 0 Celsius, 1 Fahrenheit |
| 12 | 1 | unknown | Preserve; do not decode |
| 13–18 | 6 | bytes | Device address identifier; sanitize, display order unasserted |
| 19 | 1 | flag | Alarm active, nonzero true |

When byte 11 is 0, values are already Celsius. When it is 1, convert with
`(F - 32) * 5 / 9`. Other unit codes must not silently select Celsius. The
signed fields preserve negative temperatures. Unknown probe statuses are not
connected.

The public integration's 30-second minimum advertisement-triggered poll and
60-second fallback are host policies, not device timing requirements. Always
stop notifications and disconnect cleanly so another client can read the probe.

## Validation and omissions

`scripts/test_thermoworks_bluedot_spec.py` uses synthetic vectors with a
documentation-range identifier to verify exact length, signed little-endian
values, Celsius/Fahrenheit conversion, alarm flags, probe disconnect and
malformed/truncated frames. No heating, fan, alarm or other command exists in
the tests.

Byte 12, address order, unknown status/unit codes, parent service, actual
connection limits, reset and firmware behavior remain open. Signals, Billows,
RFX and all control writes are deliberately omitted.

## References

- [jamesshannon/thermoworks-ha at the pinned commit](https://github.com/jamesshannon/thermoworks-ha/tree/c235a525f883cc22b0a8e1bd7ee626d077316443) — BlueDOT parser, tests and one-notification read-only session.
