# openScale-documented BLE Body Scales

> **Status**: Spec Available (unverified) — active vendors; openScale documents the protocols
> **Protocol**: BLE
> **Manufacturer**: Beurer / Sanitas / SilverCrest, Medisana, Trisa (openScale documents 85 scales)
> **Manufacturer Status**: Active

## Overview

Three BLE body-scale families openScale documents that are not already here — Beurer/Sanitas, Medisana BS444 and Trisa Body Analyze 4.0. Local BLE reads, no cloud.

## Protocol Summary

All offsets below apply only after reassembling one complete measurement from
its notification fragments.

- **Beurer/Sanitas:** service `0xFFE0`, characteristic `0xFFE1`, 22-byte
  big-endian record. Fields are Unix seconds (0–3), weight and bone in 50 g
  units (4–5 and 14–15), impedance (6–7), fat/water/muscle in 0.1% (8–13),
  raw BMR/AMR (16–19; units unresolved), and BMI in 0.1 (20–21).
- **Medisana BS444:** service `0x78b2`, indicate `0x8a21`/`0x8a22`, trigger
  `02 7b 7b f6 0d`. The 19-byte public example has weight at bytes 1–2 LE
  with `/100` scaling **only in kg mode**, seconds since 2010 at 5–8 LE, and
  user ID at 13. Non-kg divisors and body-composition masks remain unresolved.
- **Trisa Body Analyze 4.0:** service **`0x7802`**, not `0x78b2`, with an XOR
  challenge-response. Its compact layout uses 24-bit little-endian mantissas
  and signed exponents. The public `df 28 1e 00 fe …` example decodes to
  mantissa 7720 and exponent −2, or 77.20 kg. Timestamp, R1, R2, user and
  status fields occur in that order only when their flags are present, so R2
  follows R1 when present and otherwise immediately follows the timestamp (or
  the fixed weight header). The complete example is 20 bytes; shorter records
  compact rather than retaining fixed offsets.

Beurer's BF800 live records can set timestamp bit 31 as a flag. Mask it with
`0x7fffffff` before decoding Unix seconds; the saved record may carry the same
value with the bit clear.

See `device-specs/devices/openscale-body-scales.yaml` for the full machine-readable spec.

## References

- <https://github.com/oliexdev/openScale/wiki/Supported-scales-in-openScale>
- <https://github.com/oliexdev/openScale/wiki/Medisana-BS444>
- <https://github.com/oliexdev/openScale/wiki/Trisa-Body-Analyze>
