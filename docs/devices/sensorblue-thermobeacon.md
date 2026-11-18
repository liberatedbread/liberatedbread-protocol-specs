# SensorBlue ThermoBeacon Hygrometers

> **Status**: Spec Available (untested)
> **Protocol**: Passive BLE advertisements
> **Manufacturer**: SensorBlue / SEVEN-LIKE (OEM relationship unresolved)
> **Manufacturer Status**: Active

## Overview

SensorBlue WS03/WS07/WS08 and ThermoBeacon devices can provide live temperature,
humidity and battery voltage without a connection or cloud account. The passive
parser requires advertised service UUID `0000fff0-0000-1000-8000-00805f9b34fb`
and one numeric manufacturer key: `0x10`, `0x11`, `0x14`, `0x15`, `0x18`, `0x1b`
or `0x30`.

Those numbers are **not** proven mappings to WS03, WS07 or WS08. Do not infer a
retail model from one. The shared `fff0` UUID is not sufficient identification by
itself.

## Initial Setup

| Property | Value |
|----------|-------|
| Setup required | No — power the sensor and scan |
| Method | `ble_direct`, passive only |
| Passphrase protection | `not_applicable` |
| Confidence | Medium (public parser and fixtures; no new scan) |

**Factory reset**: Unknown. No reset was established. Passive monitoring holds no
host credential or network binding to clear.

**Rebinding**: Start the same scan on the replacement controller. No old phone,
factory reset or credentials are needed.

## Pairing

No pairing or bonding is needed for the passive stream. Connected history and
settings are a different surface and are not implemented by this spec.

## 20-Byte Measurement Record

Prepend the scanner's numeric key as a little-endian uint16 to the manufacturer
payload. Decode measurements only when the result is exactly 20 bytes. A 22-byte
record identifies the family but produces no measurement here; other lengths are
rejected.

| Offset | Type | Meaning |
|--------|------|---------|
| 0 | uint8 | Numeric device ID; no retail-model mapping |
| 3, bit 7 | flag | Raw button event (library maps it to an occupancy-style event) |
| 10–11 | uint16 LE | Battery millivolts |
| 12–13 | int16 LE | Temperature in 1/16 °C, signed |
| 14–15 | uint16 LE | Humidity in 1/16 % RH |

Discard the whole measurement if temperature exceeds 100 °C or humidity exceeds
100 %. Battery percentage is a piecewise estimate, not a transmitted field; the
exact estimate rules are in the YAML and any UI must label the result estimated.
Millivolts are the authoritative battery value.

`scripts/test_sensorblue_thermobeacon_spec.py` checks public sanitized and
synthetic boundary vectors, signed values, invalid ranges and both packet lengths.

## Out of Scope

The 22-byte record's additional semantics, connected history/settings/calibration,
all writes, TomatoClock and any guessed numeric-ID-to-retail-model mapping. No
standalone official manual was verified.

## References

- [Bluetooth-Devices/thermobeacon-ble](https://github.com/Bluetooth-Devices/thermobeacon-ble)
- [Home Assistant ThermoBeacon integration](https://www.home-assistant.io/integrations/thermobeacon/)
- [Sensor Blue on Google Play](https://play.google.com/store/apps/details?id=com.beyondtel.sensorblue)
