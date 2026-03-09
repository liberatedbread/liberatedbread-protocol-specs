# AdMore Light Bar Pro

> **Status**: Research
> **Protocol**: BLE
> **Manufacturer**: AdMore Lighting Inc.
> **Manufacturer Status**: Active (app-dependent — settings require AdMore Connect app)

## Overview

The AdMore Light Bar Pro is a Bluetooth-enabled motorcycle brake light bar that provides
tail light, brake light, progressive amber turn signals, hazard flasher, and license plate
illumination. The PRO model includes an accelerometer for deceleration-triggered brake light
activation and a BLE interface for configuring settings via the free AdMore Connect app.

This device is being reverse engineered so the community can build an open replacement for
the proprietary AdMore Connect app, ensuring long-term configurability of owned hardware
independent of the vendor's app availability.

## Hardware

| Property | Value |
|----------|-------|
| Model | Light Bar Pro (8") |
| SKU | LED8020-BT (clear) / LED8020-BT-SMK (smoked) |
| LEDs | 81 bi-color (red/amber) Cree + 3 center amber strobe + 3 white (plate) |
| Dimensions | 7.9 x 1.3 x 0.7 in (20 x 3.2 x 1.8 cm) |
| Housing | Weatherproof aluminum, powder-coated bracket |
| Voltage | 12V DC (motorcycle electrical system) |
| Wiring | 5-wire: brake, taillight, left signal, right signal, ground |
| Radio | BLE (chipset TBD) |
| FCC ID | TBD |
| Compatibility | All 12V motorcycles/scooters; CANBUS compatible |
| Origin | Calgary, Alberta, Canada |

## Protocol Summary

### BLE Services

!!! note "Research in progress"
    UUIDs below are placeholders. Actual values to be discovered via GATT enumeration
    and APK static analysis.

| UUID | Name | Properties | Description |
|------|------|------------|-------------|
| `TBD` | Control Service | — | Primary custom service for settings |
| `TBD` | Command Characteristic | write | Write setting commands to device |
| `TBD` | Status Characteristic | read, notify | Read current settings / acknowledgments |
| `TBD` | Firmware Characteristic | read | Read firmware version |

### Known App-Controllable Settings

| Setting | Type | Range (hypothesized) | Description |
|---------|------|---------------------|-------------|
| Brake light brightness | uint8 | 0–100 or 0–255 | Intensity of brake light LEDs |
| Brake light flash count | uint8 | 0–N | Number of flashes before going solid |
| Brake light flash speed | uint8 | enum or 0–N | Speed of brake light flashing |
| License plate LED | bool | on/off | Toggle white license plate illumination |
| Accelerometer sensitivity | uint8 | 0–100 or enum | Deceleration threshold for auto-brake activation |
| Running light brightness | uint8 | 0–100 or 0–255 | Intensity of always-on running lights |
| Taillight brightness | uint8 | 0–100 or 0–255 | Intensity of taillight LEDs |

### Commands

!!! warning "Hypothesized format"
    Command structure is not yet confirmed. The format below is a hypothesis based on
    common BLE device patterns documented in [Common BLE Patterns](../protocols/ble-common.md).

#### Command: Set Setting

Hypothesized request format (single write to command characteristic):

| Offset | Length | Description |
|--------|--------|-------------|
| 0 | 1 | Command ID (one per setting — TBD) |
| 1 | 1 | Value |

Alternatively, a framed format:

| Offset | Length | Description |
|--------|--------|-------------|
| 0 | 1 | Header / start byte |
| 1 | 1 | Command ID |
| 2 | 1 | Payload length |
| 3 | N | Payload (setting value) |
| 3+N | 1 | Checksum (XOR or sum mod 256) |

#### Command: Read Settings

Hypothesized: read from status characteristic returns all current setting values in a
fixed-length byte array, or individual reads per setting.

#### Command: Firmware Version

Hypothesized: read from firmware characteristic returns a version string or structured
version bytes.

## Tools Used

- [ ] nRF Connect — GATT enumeration and characteristic discovery
- [ ] Android HCI snoop log — capture BLE traffic during app usage
- [ ] Wireshark — analyze HCI snoop / PCAP captures
- [ ] tools/pcap_parser.py — parse ATT PDUs from captures
- [ ] apkeep / jadx — static APK analysis for UUIDs and command constants

## References

- [AdMore Light Bar Pro product page](https://admorelighting.com/product/admore-light-bar-pro/)
- [AdMore Connect on Google Play](https://play.google.com/store/apps/details?id=com.admorelighting.lightbar)
- [AdMore Connect App Help](https://admorelighting.com/admore-connect-app-help/)
- [Rider Magazine review (2024)](https://ridermagazine.com/2024/12/17/admore-light-bar-pro-motorcycle-lighting-system-review/)
- [Motorcycle Mojo review (2023)](https://motorcyclemojo.com/2023/07/admore-light-bar-pro-revisited/)

## Contributors

- OpenGreenIoT community — initial research
