# Felicita Arc

> **Status**: Spec Available — source-derived, untested on hardware
> **Protocol**: BLE GATT
> **Manufacturer**: Felicita Coffee (active)

## Overview

Felicita Arc streams weight and battery and accepts tare/timer operations over
phone-direct BLE without an account or cloud brew history. The machine-readable
spec is [`felicita-arc.yaml`](https://github.com/liberatedbread/liberatedbread-protocol-specs/blob/main/device-specs/devices/felicita-arc.yaml).

This is Arc only. Parallel, non-S Pearl and other Felicita models are not
asserted compatible, and Acaia's separate protocol is not reused.

## Initial Setup and pairing

| Property | Value |
|----------|-------|
| Setup required | No |
| Method | `ble_direct` (medium confidence) |
| BLE pairing/bond | None |
| Credentials | None |
| Connection recovery | Close the other app, wake and reconnect |

Match a case-insensitive `Felicita` name prefix, then require service
`0000ffe0-0000-1000-8000-00805f9b34fb` after connecting; that 16-bit service is
not unique discovery proof. Subscribe to
`0000ffe1-0000-1000-8000-00805f9b34fb` and wait for one valid frame before
marking the scale ready.

**Factory reset**: unknown. Display sleep/disconnect, tare, timer reset and
power-cycling are not established factory resets.

**Rebinding**: disconnect the old central, wake/reconnect the scale and repeat
service and first-frame validation. No Wi-Fi network or bond is involved.

## Protocol Summary

The same FFE1 characteristic carries notifications and one-byte writes. Use
write-with-response for commands, as the defensive public plugin does; the
actual on-air write properties still need capture.

### Exact 18-byte notification

Reject any short or long frame and any non-ASCII-digit in the weight field.
Reserved bytes have no invented checksum or flags.

| Offset | Length | Meaning |
|--------|--------|---------|
| 0–1 | 2 | Reserved/header, semantics unknown |
| 2 | 1 | ASCII `-` (`0x2d`) makes weight negative; other values leave magnitude positive |
| 3–8 | 6 | Six ASCII digits, integer hundredths of a gram |
| 9–14 | 6 | Reserved, preserve |
| 15 | 1 | Battery encoding, valid only at 129–158 inclusive |
| 16–17 | 2 | Reserved, preserve |

Weight is `int(ASCII bytes 3–8) / 100` grams, negated only when byte 2 is `0x2d`.
Battery is:

```text
round((raw - 129) * 100 / 29) percent
```

Raw 129 is 0% and raw 158 is 100%. Any other byte is unknown: retain the last
valid battery value or null initially, never clamp it into a fake endpoint.
An invalid battery byte does not invalidate an otherwise valid weight.

### Commands

| Hex | Operation |
|-----|-----------|
| `54` | Tare |
| `52` | Timer start |
| `53` | Timer stop |
| `43` | Timer reset |

These are user-invoked one-byte writes only. No sleep, firmware or settings
command is declared; display sleep in the public driver is a disconnect.

## Validation and omissions

`scripts/test_felicita_arc_spec.py` uses synthetic frames to check positive and
negative weight, all battery endpoints, invalid raw values, short/long frames,
non-digits and inert command encodings. No scale is contacted.

Open questions include the reserved bytes, standard Battery Service presence,
write properties, notification cadence, reconnect after sleep, factory reset,
firmware update and other Felicita models. The plugin's two-second silence
watchdog is provisional host policy, not a protocol requirement.

## References

- [Reaprime at the pinned commit — Arc driver and defensive plugin](https://github.com/tadelv/reaprime/tree/b4acf861051607464976c6c237add448604bb681)
