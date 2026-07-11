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

### BLE Characteristics

| UUID | Name | Properties |
|------|------|------------|
| `0000fa02-0000-1000-8000-00805f9b34fb` | Write Data | Write |
| `0000fa03-0000-1000-8000-00805f9b34fb` | Read Data | Read |

Device advertised name prefix: `"IDM-"`

### Commands

Variable-length bytearrays written to `0xFA02`.

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

### GIF Upload Protocol

GIF files are split into 4096-byte chunks with a 16-byte header per chunk:

| Offset | Length | Field |
|--------|--------|-------|
| 0-1 | 2 | Total chunk length (LE) |
| 2-3 | 2 | Fixed: `0x01 0x00` |
| 4 | 1 | `0x00` for first chunk, `0x02` for subsequent |
| 5-8 | 4 | Total GIF file length (LE) |
| 9-12 | 4 | CRC32 of entire GIF file (LE) |
| 13 | 1 | Fixed: `0x05` |
| 14-15 | 2 | Fixed: `0x00 0x0D` |
| 16+ | var | GIF data chunk |

Each chunk is sent with `write_gatt_char(..., response=True)` for acknowledgment.

### Image Upload

PNG files split into 4096-byte chunks with 9-byte header:

| Offset | Length | Field |
|--------|--------|-------|
| 0-1 | 2 | Total data length + chunk count (LE) |
| 2-3 | 2 | Fixed: `0x00 0x00` |
| 4 | 1 | `0x00` for first chunk, `0x02` for subsequent |
| 5-8 | 4 | Total PNG file length (LE, signed int) |
| 9+ | var | PNG data chunk |

## Tools Used

- [x] APK decompilation
- [x] Community open-source implementations

## References

- [derkalle4/python3-idotmatrix-library](https://github.com/derkalle4/python3-idotmatrix-library) (archived)
- [8none1/idotmatrix](https://github.com/8none1/idotmatrix)
- [markusressel/idotmatrix-api-client](https://github.com/markusressel/idotmatrix-api-client)

## Contributors

- @derkalle4 -- Python library (original)
- @8none1 -- alternative implementation
- @markusressel -- API client
