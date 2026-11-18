# Flowtoys Connect Props (capsule 2 / vision) via Connect Bridge

> **Status**: Research
> **Protocol**: BLE (to bridge) + WiFi/OSC (to bridge) + proprietary nRF24 RF (bridge to props)
> **Manufacturer**: Flowtoys
> **Manufacturer Status**: Active

## Overview

Flowtoys LED flow-arts props — capsule 2.0/2.C light engines (podpoi,
capsule poi, staffs, batons) and vision props (vision poi/staff/club/wand) —
do not speak BLE directly. They use a proprietary 2.4 GHz "flowtoys connect"
radio protocol that runs on nRF24L01+-compatible radios. A hardware "connect
bridge" (ESP32 + nRF24, sold as USB or pocket bridge) translates between the
official "flowtoys connect" mobile app and the props. The app talks to
**groups**, not individual props: every prop in a group shares one 16-bit
radio group ID.

Flowtoys commissioned and published the bridge firmware
([benkuper/FlowtoysConnectBridge](https://github.com/benkuper/FlowtoysConnectBridge))
and a companion app
([benkuper/FlowtoysConnect](https://github.com/benkuper/FlowtoysConnect)),
so most of the protocol is documented by open source; the production app's
newer BLE service UUIDs were recovered from the official APK
(`com.flowtoys.app`).

## Hardware

| Property | Value |
|----------|-------|
| Model Number | capsule 2.0 / 2.C, vision core props, connect bridge (USB / pocket) |
| Chipset | Bridge: ESP32 + nRF24L01+ (props: nRF24-compatible 2.4 GHz radio) |
| Radio | BLE 4.x (bridge↔phone), WiFi 802.11n (bridge), proprietary 2.4 GHz nRF24 (bridge↔props) |
| FCC ID | — |

## Initial Setup

| Property | Value |
|----------|-------|
| Setup required | No (BLE to bridge); grouping required before props are addressable |
| Method | `ble_direct` |
| Setup AP / advertised name | BLE: `FlowConnect <name>`; WiFi fallback AP: `FlowConnect <name>` (WPA2, password `findyourflow`) |
| Passphrase protection | plaintext (WiFi credentials sent cleartext over unencrypted BLE) |
| Confidence | medium (published source; not exercised against hardware here) |

**Grouping props**: from off, hold the prop button ~10 seconds until the
LEDs flash or turn white. Every prop needs a group, even a single one.
There are 5 fixed "public" groups (IDs 1–5) plus private groups with other
16-bit IDs. To have the bridge learn a private group, put the props on their
sync page/mode (page 2 mode 1 on older firmware; the current app says page 5
mode 1) and start sync from the app/bridge.

**Factory reset**: the bridge stores WiFi credentials, its name and learned
group IDs in ESP32 NVS — clearing NVS (reflash) resets it. A prop's group
membership is overwritten by re-grouping (the ~10 s button hold).

**Rebinding to a new network**: in place — send the `n<ssid>,<password>`
command over BLE or the `/wifiSettings` OSC message; no reset needed.

## Protocol Summary

Three hops, any of the first two can drive the third:

1. **BLE → bridge.** Open firmware: Nordic UART Service
   `6e400001-b5a3-f393-e0a9-e50e24dcca9e`; write ASCII commands to
   `6E400002-…`, notifications on `6E400003-…`; the app requests MTU 48.
   Production app: service `49550001-aad5-59bd-934c-023d807e01d5` with
   characteristics `49550002-…`, `49550003-…`, `49550005-…` (roles
   unverified — recovered from the APK's compiled Dart library).
2. **WiFi/OSC → bridge.** Bridge mDNS-advertises `_osc._udp`
   (instance `flowtoysconnect`) and listens for OSC over UDP (firmware
   port 9000; the early app sent to 8888).
3. **nRF24 RF → props.** 250 kbps, channel 2, 3-byte address
   `{0x01, 0x07, 0xF1}`, CRC-16, no auto-ack; a 20-byte packed sync packet
   per group broadcast at ~30 ms cadence. Any nRF24 node can drive props
   directly with these parameters.

### BLE Services

| UUID | Name | Description |
|------|------|-------------|
| `6e400001-b5a3-f393-e0a9-e50e24dcca9e` | Nordic UART (open bridge firmware) | ASCII command channel |
| `6e400002-b5a3-f393-e0a9-e50e24dcca9e` | NUS RX | **Write-with-response only** in the open-firmware declaration |
| `6e400003-b5a3-f393-e0a9-e50e24dcca9e` | NUS TX | Notifications |
| `49550001-aad5-59bd-934c-023d807e01d5` | Flowtoys Connect service (production) | Vendor service; characteristic roles unverified |

The companion app has separately been observed using no-response writes. That
is client behavior, not evidence for a second RX property bit.

### Commands

Commands are ASCII strings with decimal comma-separated fields, terminated by
`\n` or `0xFF`. In the reviewed open-firmware revision, the public-group
transmit loop is disabled: **only learned groups are emitted**. Do not infer
production public-group behavior from this source revision.

#### Command: set pattern

`p<group>,<page>,<mode>,<actives>,<hue>,<sat>,<brightness>,<speed>,<density>,<lfo1>,<lfo2>,<lfo3>,<lfo4>`

| Field | Description |
|-------|-------------|
| group | Learned group ID (0 = all learned groups) |
| page, mode | Effect selector (modes are numbered within pages) |
| actives | Bitmask: bit0 LFO, bit1 hue, bit2 sat, bit3 brightness, bit4 speed, bit5 density |
| hue, sat, brightness, speed, density, lfo1–4 | uint8 0–255 |

Solid colour: page 2, mode 7, actives 255, with HSV hue/sat/brightness.

#### Command: wake / power off / sync / configuration

Lowercase `w<group>` wakes and `z<group>` powers off a learned group.
`s<timeout_seconds>` starts RF sync, `S` stops, and `a` forgets learned groups.
`n<ssid>,<password>` sets WiFi credentials; `g<name>,<mode>` sets bridge name
and radio mode; `r` restarts the bridge.

#### OSC equivalents (UDP)

`/wakeUp` (int group, int isPublic), `/powerOff`, `/sync` (float timeout),
`/stopSync`, `/resetSync`, `/pattern` (14 ints: group, isPublic, page, mode,
actives, hue, sat, brightness, speed, density, lfo1–4), `/wifiSettings`
(2 strings), `/globalConfig` (string name, int mode), `/play`, `/stop`,
`/pause`, `/resume`, `/seek` (float), `/rgb/brightness` (float). The OSC
signature retains its `isPublic` field; the open-firmware public-group emission
limitation above still applies.

#### RF sync packet (bridge → props, 21 bytes, packed)

| Offset | Length | Description |
|--------|--------|-------------|
| 0 | 2 | group ID (uint16, byte-swapped on the wire) |
| 2 | 4 | padding/sequence counter (incremented per change) |
| 6 | 4 | LFO values 1–4 |
| 10 | 5 | global hue, saturation, value, speed, density |
| 15 | 1 | active flags (bit per parameter: lfo/hue/sat/val/speed/density) |
| 16 | 2 | reserved |
| 18 | 1 | page |
| 19 | 1 | mode |
| 20 | 1 | separate command flags (adjust, wakeup, poweroff, force_reload, save, delete, alternate) |

### Wired USB firmware update (reported)

The published desktop updater accepts a `.fwimg` ZIP containing exactly `meta`
(a JSON object with target/version metadata) and `data` (raw firmware). USB HID
uses 64-byte reports, with a zero report-ID byte prepended on host writes and
little-endian fields. `Update` (`0x01`) starts the transfer; `Data` (`0x80`)
carries up to 60 firmware bytes after its four-byte command word. Pad the image
to a multiple of 60 bytes and follow the device's acknowledged write offset.

For Vision/Club, an **advanced** app-mode `AppReset(Bootloader)` request
(command `0xFF`, subject u32le `1`) enters the bootloader. Capsule uses the
vendor's manual button sequence. The product string contains `bootloader` in
update mode. The complete interrupted-update recovery contract remains
**unknown**; do not assume a flash can always be resumed. See the open-source
updater's `brain/FIRMWARE-FORMAT.md` and `brain/HID-PROTOCOL.md`.

## Tools Used

- [x] jadx (official APK decompile) + strings on Flutter `libapp.so`
- [x] Source review of the vendor-published bridge firmware and companion app
- [ ] BLE capture against a production bridge (to pin down the `4955000x` characteristic roles)

## References

- [benkuper/FlowtoysConnectBridge — bridge firmware (ESP32/nRF24)](https://github.com/benkuper/FlowtoysConnectBridge)
- [benkuper/FlowtoysConnect — companion Flutter app](https://github.com/benkuper/FlowtoysConnect)
- [jonglissimo/Flowtoy-Connect-Bridge-OSC-Module — Chataigne OSC module](https://github.com/jonglissimo/Flowtoy-Connect-Bridge-OSC-Module)
- [flowtoys support: bridge & app FAQ](https://flowtoys.com/pages/bridge-app)

## Contributors

- Liberated Bread clean-room pipeline — initial research
