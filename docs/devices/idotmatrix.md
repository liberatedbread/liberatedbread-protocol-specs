# iDotMatrix Pixel Display

> **Status**: Complete
> **Protocol**: BLE
> **Manufacturer**: iDotMatrix
> **Manufacturer Status**: Unsupported

## Overview

Small RGB pixel displays in 16x16 or 32x32 sizes. Supports static images, GIF animations, text, clock, countdown, and graffiti (pixel-by-pixel drawing). Cloud content library is optional.

## Hardware

| Property | Value |
|----------|-------|
| Display | 16x16 or 32x32 RGB LED matrix |
| Chipset | Unknown |
| Radio | BLE |
| FCC ID | Not documented |

## Protocol Summary

### BLE Service and Characteristics

Post-connect public GATT captures list primary service
`000000fa-0000-1000-8000-00805f9b34fb`, containing:

| UUID | Name | Properties |
|------|------|------------|
| `0000fa02-0000-1000-8000-00805f9b34fb` | Write Data | Write, write without response |
| `0000fa03-0000-1000-8000-00805f9b34fb` | Notify/Ack Data | Notify only |

Advertisements contain flags and the local name prefix `"IDM-"`; they do not
advertise `0x00FA`. Scan by IDM name, then discover the primary service after
connecting. The `0xFEE9` service and its library-default characteristics are
negative evidence from unused app configuration, not an alternative transport
observed on this hardware.

### Commands

Variable-length byte arrays written to characteristic `0xFA02`.

| Command | Bytes | Description |
|---------|-------|-------------|
| Screen On | `05 00 07 01 01` | Turn display on |
| Screen Off | `05 00 07 01 00` | Turn display off |
| Freeze | `04 00 03 00` | Freeze/unfreeze display |
| Set Brightness | `05 00 04 80 VV` | Brightness 5-100% |
| Flip Screen | `05 00 06 80 VV` | 0=normal, 1=rotated 180 |
| Set Speed | `05 00 03 01 VV` | Animation speed |
| DIY Mode | `05 00 04 01 VV` | 0=disable, 1=enable image mode |
| Set Time | `0B 00 01 80 YY MM DD WW HH mm SS` | Set clock |
| Set Password | `08 00 04 02 01 HH MM LL` | 6-digit password |
| Draw Pixel | `0A 00 05 01 MM RR GG BB XX YY` | Mode, RGB888 and zero-based x/y |

A public capture proves the one-pixel graffiti command
`0a 00 05 01 00 ff 00 00 1f 1f`: mode 0, red `(255,0,0)`, at `(31,31)`.
Only the short RGB888 pixel command is established; a complete raw framebuffer
upload remains unobserved.

### Framed Upload Protocol

GIF, image and text uploads use the same primary `0x00FA` service and `0xFA02`
characteristic as the short commands. Each frame has a 16-byte header followed
by at most 4096 payload bytes:

| Offset | Length | Field |
|--------|--------|-------|
| 0-1 | 2 | Total frame length, header included (uint16, **little-endian**) |
| 2 | 1 | Command type: `1`=GIF, `2`=Image, `3`=Text/MultiColor, `6`=Phrase |
| 3 | 1 | Sub-type: `0x00` in framed uploads |
| 4 | 1 | Chunk flag: `0x00`=first, `0x02`=continuation |
| 5-8 | 4 | Total payload length across the transfer, excluding every header (uint32, **little-endian**) |
| 9-12 | 4 | CRC32 of the payload only, excluding every header (`zlib`/standard CRC32, **little-endian**) |
| 13-14 | 2 | Time/delay (uint16, **little-endian**) |
| 15 | 1 | Speed/type byte |
| 16+ | var | Payload (image / GIF / text data) |

For a GIF chunk, bytes `[2..3]` are therefore `0x01 0x00`; for an image, `0x02 0x00`.
Public frames independently confirm the boundaries: one 50-byte frame declares
frame length 50 and payload length 34 with CRC32 `0x10907ec7`; another 234-byte
frame declares payload length 218 with CRC32 `0xe72b5848`. The BLE layer splits
frames into 509-byte writes when MTU is negotiated, else 18-byte writes, pacing
GIF/image writes at 20 ms and text writes at 50 ms. `0xFA03` notifications gate
subsequent frames; the characteristic does not support reads.

## Tools Used

- [x] APK decompilation
- [x] Community open-source implementations

## References

- [derkalle4/python3-idotmatrix-library](https://github.com/derkalle4/python3-idotmatrix-library) (archived)
- [8none1/idotmatrix](https://github.com/8none1/idotmatrix)
- [markusressel/idotmatrix-api-client](https://github.com/markusressel/idotmatrix-api-client)
- [adriantukendorf/iDotMatrix-HomeAssistant — HACS integration](https://github.com/adriantukendorf/iDotMatrix-HomeAssistant)

## Contributors

- @derkalle4 -- Python library (original)
- @8none1 -- alternative implementation
- @markusressel -- API client
