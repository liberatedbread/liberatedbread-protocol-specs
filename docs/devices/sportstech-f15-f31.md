# Sportstech F15 / F31 treadmill (read-only)

> **Status**: Identify-only — public-capture evidence, untested; dedicated consumer handler pending
> **Protocol**: BLE GATT, delimited XOR telemetry
> **Manufacturer**: Sportstech (active)

## Overview

F15/F31 exposes local status notifications over BLE without a FitShow account
or cloud workout. This profile decodes telemetry only; the physical console and
safety key remain authoritative. The machine-readable spec is
[`sportstech-f15-f31.yaml`](https://github.com/liberatedbread/liberatedbread-protocol-specs/blob/main/device-specs/devices/sportstech-f15-f31.yaml).

F31 support is reported by the independent implementation but is not separately
captured here. Other FitShow/Sportstech bikes, ellipticals, rowers and treadmills
are excluded: their characteristics and payloads can differ materially.

## Initial Setup and pairing

| Property | Value |
|----------|-------|
| Setup required | No |
| Method | `ble_direct` (medium confidence) |
| BLE pairing/bond | None |
| Credentials | None |
| Safety | Keep the belt stationary and safety key under owner control |

Select the treadmill manually; no automatic identity matcher is asserted.
Connect, verify the endpoints and subscribe to FFF1. FFF0 is widely reused and
is not an identification signal, so a selected candidate must also produce the
documented delimited/checksummed frames. If a poll is needed, send only
`02 51 51 03` on FFF2; do not send any initialization, authorization or belt
command.

**Factory reset**: unknown. Removing the safety key is not a factory reset. No
genuine F15/F31 manual was acquired, so no generic Sportstech procedure is
substituted.

**Rebinding**: disconnect the previous central and revalidate the frame dialect.
There is no treadmill Wi-Fi membership, client credential or vendor
authorization exchange in this read-only path.

## Protocol Summary

| Role | UUID |
|------|------|
| Service | `0000fff0-0000-1000-8000-00805f9b34fb` |
| Notifications | `0000fff1-0000-1000-8000-00805f9b34fb` |
| Status-poll write | `0000fff2-0000-1000-8000-00805f9b34fb` |

Frames start `0x02`, end `0x03` and carry XOR in the penultimate byte. XOR covers
bytes 1 through `len-3` inclusive, excluding start, checksum and end. Reject bad
delimiters, lengths above 108, bad XOR, unknown types and truncation. Buffer
fragmented/coalesced input and do not mistake an embedded `0x03` for a valid
terminator before expected length and checksum checks pass.

### Full 17-byte status

| Offset | Type | Meaning |
|--------|------|---------|
| 0 | `0x02` | Start delimiter |
| 1 | `0x51` | Status marker |
| 2 | `uint8` | Mode: 0 stopped, 2 starting, 3 running, 4 stopping |
| 3 | `uint8 × 0.1 km/h` | Speed |
| 4 | raw byte | Incline unresolved; no unit/entity published |
| 5–6 | `uint16` little-endian | Elapsed seconds |
| 7–8 | `uint16 × 0.001 km` little-endian | Distance |
| 9–10 | raw bytes | Energy unresolved; do not label cal/kcal or scale |
| 11–12 | bytes | Reserved |
| 13–14 | `uint16` little-endian | Heart rate bpm |
| 15 | `uint8` | XOR |
| 16 | `0x03` | End delimiter |

Accept only the exact pairs `(stopped, 5)`, `(starting, 6)`, `(running, 17)` and
`(stopping, 17)`; reject cross-combinations and truncation even with valid XOR.
The five-byte stopped frame carries delimiter, marker, mode, XOR and end only.
The six-byte starting frame additionally has unresolved raw byte `0x05` at
offset 3; return it as `offset_3_raw` rather than decoding it as speed. Publish mode and the
public decoder's compatibility zeroes for speed/heart rate on valid short
frames; leave full-frame-only elapsed/distance unavailable and never read beyond
the payload.

Public running vector
`02 51 03 0d 00 20 00 09 00 03 00 00 00 53 00 26 03`
decodes to running, 1.3 km/h, 32 seconds, 0.009 km and 83 bpm. The stopping
vector checks 1.0 km/h, 33 seconds and 84 bpm.

## Validation and omissions

`scripts/test_sportstech_f15_f31_spec.py` checks all four public fixtures,
short stopped/starting frames, fragmentation/coalescing, bad delimiters,
unknown types, bad XOR and truncated fields. The only command encoding is the
inert status poll; nothing starts, stops or changes a belt.

Incline and energy units are deliberately omitted pending console-labelled
evidence. F31 capture, additional frame lengths, factory reset, authorization,
firmware and every motion-control operation remain open.

## References

- [syssi/esphome-treadmill-f15 at the pinned commit](https://github.com/syssi/esphome-treadmill-f15/tree/6e1617c1e505433ecb4c52ba9c99eff3097bcc22) — implementation, public capture and four fixtures.
- [QZ Sportstech rower — separate protocol boundary](https://github.com/cagnulein/qdomyos-zwift/tree/afd4f90db35ed7ee29c76a6c19b84de4cf558922/src/devices/sportstechrower)
