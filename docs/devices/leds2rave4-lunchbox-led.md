# LEDs2RAVE4 / Lunchbox Dream LED (SP107E/SP110E)

> **Status**: Complete
> **Protocol**: BLE
> **Manufacturer**: SPLED
> **Manufacturer Status**: Unsupported

## Overview

SPI LED pixel controllers used in the LEDs2RAVE4/Lunchbox Dream LED product family. The SP107E ("LED Chord") and SP110E ("LED Hue") share BLE UUIDs but have different command sets. SP107E adds music-reactive and matrix modes.

## Hardware

| Property | Value |
|----------|-------|
| Models | SP107E (LED Chord), SP110E (LED Hue) |
| Chipset | Unknown |
| Radio | BLE |
| Supported LED ICs | WS2811, SK6812, APA102, and 23 more (see IC table) |

## Protocol Summary

### BLE Services

| UUID | Name | Description |
|------|------|-------------|
| `0xFFE0` | LED Control Service | Primary service |
| `0xFFE1` | Control | Write commands, receive notifications |

### Command Format

All commands are 4 bytes: `[data1] [data2] [data3] [cmd_byte]`

### SP110E Commands

| Command | Bytes | Description |
|---------|-------|-------------|
| Power On | `00 00 00 AA` | Turn on |
| Power Off | `00 00 00 AB` | Turn off |
| Set Color | `RR GG BB 1E` | Set static RGB color |
| Set Brightness | `VV 00 00 2A` | Brightness 0x00-0xFF |
| Set Effect | `VV 00 00 2C` | 0x01-0x78=dynamic, 0x79=static |
| Set Speed | `VV 00 00 03` | Speed 0x01-0xBA |
| Set Chip Type | `VV 00 00 1C` | IC model index |
| Set Chip Order | `VV 00 00 3C` | RGB sequence 0x00-0x05 |
| Set Pixel Count | `HI LO 00 2D` | Big-endian, 1-1024 |
| Query Status | `00 00 00 10` | Returns 12 bytes |

### SP107E Commands

| Command | Bytes | Description |
|---------|-------|-------------|
| Power On | `00 00 00 AA` | Turn on |
| Power Off | `00 00 00 BB` | Turn off (note: `0xBB`, not `0xAB`) |
| Set Color | `RR GG BB 0C` | Set static RGB color |
| Set Brightness | `VV 00 00 0A` | Brightness 0x00-0xFF |
| Set Effect | `VV 00 00 08` | 0x01-0xB4=dynamic, 0xB5=static |
| Set Speed | `VV 00 00 09` | Speed 0x01-0xBA |
| Set Sensitivity | `VV 00 00 13` | Audio input gain 1-165 |
| Query Status | `00 00 00 02` | Returns 26 bytes (2 packets) |

### Discovery

- SP107E advertises as `"SP107E"`, SP110E as `"SP110E"`
- Dream LED Skin 2.0 devices: `"LBXDRMSKIN_LED_"` prefix

## Tools Used

- [x] Community open-source implementations

## References

- [SP110E Protocol Gist](https://gist.github.com/mbullington/37957501a07ad065b67d4e8d39bfe012)
- [UniLED HA Integration](https://github.com/monty68/uniled)
- [SP110E-HASS](https://github.com/roslovets/SP110E-HASS)

## Contributors

- @mbullington -- SP110E protocol documentation
- @monty68 -- UniLED Home Assistant integration
