# Pix Backpack / Pix Mini

> **Status**: In Progress
> **Protocol**: BLE
> **Manufacturer**: Pix Inc.
> **Manufacturer Status**: Shutdown (vendor defunct, app delisted from Google Play)

## Overview

The **Pix Backpack** (Kickstarter 2018) is a backpack with a 16×20 RGB LED matrix
sewn into the back panel; the **Pix Mini** (2019) is a smaller kids' variant. Both
were driven by the vendor's **Pix** app (`style.pix.app`), a React Native app that
has since vanished from the Play Store along with the vendor. The good news: the
hardware never needed the cloud. Every control function — image and animation
upload, brightness, scrolling text, widgets, games — is plain local BLE with no
pairing, no account and no encryption. The full machine-readable protocol is in
[`device-specs/devices/pix-backpack.yaml`](https://github.com/liberatedbread/liberatedbread-protocol-specs/blob/main/device-specs/devices/pix-backpack.yaml).

The vendor cloud only ever hosted the content marketplace, a news feed, and
firmware files — all replaceable or unnecessary.

## Hardware

| Property | Value |
|----------|-------|
| Models | Pix Backpack (16×20 matrix), Pix Mini (geometry unconfirmed) |
| Chipset | Unknown — ESP32-class suspected (BLE + Wi-Fi combo, Wi-Fi OTA); unconfirmed |
| Radio | BLE (control); Wi-Fi used only by the device itself during firmware OTA |
| Power | External USB power bank (no internal battery) |
| FCC ID | Unknown |

## Initial Setup

| Property | Value |
|----------|-------|
| Setup required | No |
| Method | `ble_direct` |
| Advertised name | `pix <12-hex-MAC>` (e.g. `pix a1b2c3d4e5f6`) |
| Passphrase protection | plaintext (only during OTA — see below) |
| Confidence | medium (from app analysis; not yet exercised against hardware here) |

Plug the backpack's internal USB cable into a power bank — the display powers on
and advertises immediately. Scan for the `pix …` name (or the `0100` service
UUID), connect from inside your app, and read the matrix width, height and max
frame count from the device. There is no pairing, PIN, or account.

**Factory reset**: none exists — and there is little to reset, since the device
holds no accounts or keys. The only persistent state is the saved animation,
which you can erase over BLE (frame count 0, then save-to-flash). A hardware
reset procedure is unknown.

**Rebinding to a new controller**: just connect from the new phone — nothing binds
the backpack to a controller. Expect one BLE connection at a time, so disconnect
the old phone first.

## Protocol Summary

### BLE Services

| UUID | Name | Description |
|------|------|-------------|
| `00000100-e984-11e7-b78e-ffd6fcc3450f` | Pix RPC (legacy base) | Main service, legacy firmware |
| `00000100-e984-11e7-b78e-ffd6fcc34510` | Pix RPC (V1 base) | Main service, current firmware |
| `00000100-9552-4325-8021-a85f8136a5c4` | Pix RPC (Mini) | Mini variant — unconfirmed |

Both original bases expose the same characteristics; pick the legacy base only if
the device actually advertises it, otherwise V1. Characteristics (16-bit part,
same under each base): `0101` RPC write, `0103`/`0104`/`0105` width/height/max
frames (read), `0106` brightness (write, one byte 0–255), `0107`/`0108`/`0109`
OTA, `0110` demo. Standard Device Information `180A` gives firmware (`2A26`) and
hardware (`2A27`) revision strings.

### Commands

Every command is a write to `0101`: `[callId, opcode, payload…]` — `callId` is a
rolling counter, and there is **no checksum, no encryption and no ACK**.

| Opcode | Name | Payload |
|--------|------|---------|
| 0 | SET_FRAME | frame index (u16LE), offset (u16LE, =0), frame bytes |
| 1 | SET_PALETTE | start color index, RGB888 bytes (≤160 colors per call) |
| 2 | SET_FRAME_COUNT | count (0 = erase) |
| 3 | SET_FRAMES_DURATIONS | offset (u16LE), per-frame milliseconds (u16LE each; default 80) |
| 4 | SET_ANIMATION_DIRECTION | 0 normal / 1 alternate / 2 normal-stop / 3 alternate-stop |
| 5 | SAVE_TO_PERSISTENT_MEMORY | — (saved content autostarts on boot) |
| 7 | SET_CONFIG | offset (u16LE), config bytes (≤512 per call); first byte = render mode |
| 8 | SET_INPUT | input id (rolling), command (widget/game input) |
| 9 | RESTART | — |

Render modes (first SET_CONFIG byte): 0 blank, 1 animation, 2 scrolling text,
3 OTA progress, 6 clock, 7 bike, 8 countdown, 9 stopwatch, 16–18 games.

### Image / animation upload

Frames are **one byte per pixel — an index into an RGB888 palette** — row-major,
320 bytes per frame at 16×20. Upload sequence (all fire-and-forget writes):

1. Blank the screen (SET_CONFIG mode 0) and erase (SET_FRAME_COUNT 0).
2. Upload the palette (SET_PALETTE; a second call at index 160 if >160 colors).
3. Upload each frame (SET_FRAME).
4. Set durations, direction, then the real frame count.
5. Optionally SAVE_TO_PERSISTENT_MEMORY so it plays on boot.

Scrolling text works by uploading 8×20 font sprites as ordinary frames and then a
text config naming the sprite sequence.

### Firmware OTA (rescue notes)

Unusually, the **device** downloads its own firmware over Wi-Fi: the phone writes
a config blob (Wi-Fi SSID/password, host, **port 80**, path, image size, MD5) to
`0108`, arms `0107`, and the backpack joins that network and plain-HTTP GETs the
image. That makes OTA rescuable — any HTTP server on port 80 serving an image
with the matching size/MD5 will do — but no firmware image is publicly archived,
the image format is unknown, and a bad flash can brick the backpack. Note the
passphrase crosses the BLE link in cleartext; use a throwaway hotspot.

## Open Questions

- Does the RPC characteristic stream responses if you subscribe to notifications?
  (The vendor app never does.)
- Real max-frame count and palette cap; partial-frame writes via SET_FRAME offset.
- Config layouts for the clock/bike/timer widgets and the three games.
- Pix Mini matrix geometry and whether its characteristic layout matches.
- Chip family and firmware image format (needs an FCC ID or an archived image).

## Tools Used

- [x] APK static analysis (React Native bundle)
- [ ] HCI snoop of connect + upload (pending — no live capture yet)

## References

- [PIX: Interactive Animated LED Backpack (Hackster)](https://www.hackster.io/news/pix-interactive-animated-led-backpack-d29f09a138c2)
- [Pix Mini press release (2019)](http://www.prweb.com/releases/pix_mini_the_first_smart_backpack_for_kids_more_than_doubles_goal_to_raise_37_000_and_counting_on_kickstarter/prweb16375233.htm)
- [pix.style via the Wayback Machine](https://web.archive.org/web/2019*/pix.style)

## Contributors

- Liberated Bread research team — initial app analysis and protocol mapping
