# Bluetooth LED Name Badge

> **Status**: Complete
> **Protocol**: BLE
> **Manufacturer**: Generic (multiple OEMs)
> **Manufacturer Status**: Abandoned

## Overview

Cheap programmable 11x44 monochrome LED dot-matrix badges sold under many brands on AliExpress and distributed at events like 35c3. Extensively reverse engineered by the FOSSASIA community.

## Hardware

| Property | Value |
|----------|-------|
| Display | 11x44 LED matrix (charlieplexing, 24 control pins) |
| Chipset | CH582M (RISC-V) or MM32L062PF (ARM M0) |
| Radio | BLE 4.x |
| FCC ID | Not applicable (generic) |

## Protocol Summary

### BLE Services

| UUID | Name | Description |
|------|------|-------------|
| `0000fee0-0000-1000-8000-00805f9b34fb` | Badge Service | Primary service |
| `0000fee1-0000-1000-8000-00805f9b34fb` | Badge Data | Acknowledged-write characteristic for all data |

### Packet Format

All data is written to the data characteristic as 16-byte acknowledged GATT
writes. Allow a 3-second acknowledgment timeout for each write, wait 300 ms
before the first bitmap-data chunk after the four header chunks, and wait 25 ms
between subsequent chunks. These are the vendor app's documented timings; some
community clients successfully use a simpler 100 ms cadence.

#### Header (64 bytes)

| Offset | Length | Field | Description |
|--------|--------|-------|-------------|
| 0-3 | 4 | Magic | `0x77616E67` ("wang") |
| 4 | 1 | Reserved | `0x00` |
| 5 | 1 | Brightness | `0x00`=100%, `0x10`=75%, `0x20`=50%, `0x40`=25% |
| 6 | 1 | Flash flags | Bitfield: bit N = message N blinks |
| 7 | 1 | Marquee flags | Bitfield: bit N = message N has animated border |
| 8-15 | 8 | Speed+Mode | `(speed << 4) | mode` per message |
| 16-31 | 16 | Message sizes | 2 bytes big-endian per message (up to 8) |
| 38-43 | 6 | Timestamp | YY, MM, DD, HH, MM, SS |

#### Animation Modes (low nibble of speed+mode byte)

| Value | Mode |
|-------|------|
| `0x00` | Scroll left |
| `0x01` | Scroll right |
| `0x02` | Scroll up |
| `0x03` | Scroll down |
| `0x04` | Fixed/static |
| `0x05` | Animation |
| `0x06` | Snowflake/drop-down |
| `0x07` | Picture/curtain |
| `0x08` | Laser |

#### Speed (high nibble): 1-8 (slowest to fastest)

#### Bitmap Data (bytes 64+)

Bitmap data uses 8-column-wide stripes. Each stripe contains one byte per row,
MSB = leftmost pixel and 1 = LED on. An 11-row badge uses 11 bytes per stripe;
12- and 16-row variants use 12 and 16 bytes respectively. The bitmap stream is
zero-padded to a 16-byte write boundary.

### Key Properties

- **No pairing required**
- **Acknowledged writes** with per-write timeouts and inter-chunk timing
- **Stateless** -- each complete transfer replaces all stored messages
- **Persistent** -- messages stored in flash, survive power cycles
- **Max 8 messages**, max 8192 bytes for the complete flash image, **including
  the 64-byte header**; bitmap data therefore has at most 8128 bytes before
  final chunk padding

## Tools Used

- [x] APK decompilation
- [x] Community open-source implementations

## References

- [Nilhcem blog](http://nilhcem.com/iot/reverse-engineering-bluetooth-led-name-badge)
- [FOSSASIA BadgeMagic](https://github.com/fossasia/badgemagic-app)
- [FOSSASIA badgemagic-firmware](https://github.com/fossasia/badgemagic-firmware)
- [M4GNV5/BluetoothLEDBadge](https://github.com/M4GNV5/BluetoothLEDBadge)

## Contributors

- @Nilhcem -- original reverse engineering
- FOSSASIA community -- firmware and multi-platform apps
