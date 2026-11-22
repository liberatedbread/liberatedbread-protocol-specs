# Fossil Hybrid HR / Gen 6 Hybrid (Skagen, Citizen CZ)

> **Status**: Spec available (derived from open clients; not tested on hardware here)
> **Protocol**: BLE GATT vendor service, key-authenticated session, AES-128-CTR file transfer
> **Manufacturer**: Fossil Group (Fossil, Skagen; Citizen CZ Smart hybrid)
> **Manufacturer Status**: Abandoned (Fossil left smartwatches in 2024; the key service still runs)

## Overview

The Hybrid HR and Gen 6 Hybrid are e-ink hybrids. They have real hands over a
round e-paper display, three buttons, and battery life measured in weeks.
Skagen sells the same hardware as the Jorn Hybrid HR and Jorn Gen 6, and
Citizen's CZ Smart hybrid (Gen 2) behaves like the Gen 6. The phone talks to
the watch directly over BLE. Almost everything useful, from setting the time
to syncing activity, needs an application-layer session authenticated with a
**16-byte AES-128 key that is unique to each watch**.

The vendor app gets that key from Fossil's cloud when it pairs the watch.
That is why this spec matters now. Fossil left the smartwatch business in
2024 and has said updates will continue only "for the next few years". It has
announced no date for the key service. Once that service stops, a watch whose
owner never exported the key can no longer be set up by anyone. With the key
in hand, everything on this page is local, and no cloud is involved again.

**If you own one of these watches, export its key now.** Gadgetbridge
documents a way for an owner to get their own watch's key from their own
account. This page does not describe any account API. Keep the key in a
password manager. Re-pairing with the vendor app can replace the key, and so
can one firmware version (DN1.0.2.21r), so export it again after either.

The machine-readable spec is
[`device-specs/devices/fossil-hybrid-hr.yaml`](https://github.com/liberatedbread/liberatedbread-protocol-specs/blob/main/device-specs/devices/fossil-hybrid-hr.yaml).
Its synthetic vectors are rebuilt by `scripts/test_fossil_hybrid_hr_spec.py`.

## Hardware

| Property | Value |
|----------|-------|
| Models | Hybrid HR 42 mm (Collider etc.), Hybrid HR 38 mm (Monroe etc.), Gen 6 Hybrid 44/45 mm and Wellness, Skagen Jorn 42/38 mm Gen 6, Citizen CZ Gen2 (JX1xxx 44 mm, JX2xxx 42.5 mm) |
| Hardware revision (from firmware string) | `DN1.0` HR 42 mm · `IV0.0` HR 38 mm · `VA0.0` Gen 6 and Jorn 42 mm · `WA0.0` Jorn 38 mm |
| Radio | BLE only |
| Category | `wearable` / hybrid smartwatch |
| Companion apps | Fossil Smartwatches (vendor); Citizen's app for the CZ; Gadgetbridge (Android) and Hybridge (iOS) as open replacements |
| Not covered | Fossil Q hybrids without a display, and Misfit-era Q watches. They share the service UUID but use no key and unencrypted files. Gen 6 Wear OS smartwatches are unrelated. |

## Initial setup

| Property | Value |
|----------|-------|
| Setup required | Yes: the owner's 16-byte key |
| Method | `ble_direct` with the key. If the key is not held yet, a one-time owner export (`cloud_account`) first |
| Advertised name | `Hybrid HR…` (prefix), `Fossil Gen. 6 Hybrid`. Skagen and Citizen names not recorded |
| Passphrase protection | Not applicable (no Wi-Fi) |
| Confidence | Medium (two public clients; not run here) |

1. Disconnect the vendor app, scan for service
   `3dda0001-957f-7d4a-34a6-74696673696d`, and connect.
2. Subscribe to `3dda0002`…`3dda0007`, then read Firmware Revision `2a26`. That
   service UUID is shared with the older Q hybrids, so **classify by the
   firmware prefix before writing anything**. `IV0`, `VA`, `WA`, or a `1` as
   the third character (`DN1.0…`) means this spec applies.
3. Request MTU 512 and read the device-info file for the supported file
   versions.
4. Run the key handshake (below).
5. On firmware 2.22 and later the watch may ask the wearer to confirm the new
   phone with a button press within 30 seconds.
6. Set the time (an encrypted configuration write).

Gadgetbridge suggests updating the watch with the vendor app before
switching. Later firmware moved functions into separately installed watch
apps, and third parties cannot redistribute those.

**Factory reset:** Gadgetbridge's Hybrid HR support sends a BLE reset frame,
`02 f1 23 ff ff ff ff ff` on `3dda0002`. Nobody has established what it
clears, whether the key survives, or whether the watch can be set up again
without the vendor's key service. Treat it as possibly one-way. No button
procedure was found in the reviewed sources.

**Rebinding:** a new phone needs the same key and a fresh handshake. No reset
is needed.

## Pairing

| Property | Value |
|----------|-------|
| Pairing required | Yes, application-layer key handshake |
| Security mode | `app_layer` |
| Bonding | `optional`. The clients ask whether the watch is bonded (`01 16`) and request a bond (`02 16`) after confirmation |
| PIN source | None; the key is supplied out of band |
| One central at a time | Unknown; disconnect the vendor app first |
| Confidence | Medium |

There is no pairing window. To withdraw a client, delete its copy of the key.
No BLE command that removes a key or a bond is documented.

## Protocol summary

### BLE services

| UUID | Name | Role |
|------|------|------|
| `3dda0001-957f-7d4a-34a6-74696673696d` | Fossil hybrid vendor service | Container |
| `3dda0002-957f-7d4a-34a6-74696673696d` | Basic commands | Hands, bond query, factory reset |
| `3dda0003-957f-7d4a-34a6-74696673696d` | File control | Open/close/lookup/delete and status replies |
| `3dda0004-957f-7d4a-34a6-74696673696d` | File data | Sequence-numbered packets, AES-CTR for encrypted files |
| `3dda0005-957f-7d4a-34a6-74696673696d` | Authentication | Key handshake, on-watch confirmation |
| `3dda0006-957f-7d4a-34a6-74696673696d` | Events | Buttons, calls, music, JSON requests from watch apps |
| `3dda0007-957f-7d4a-34a6-74696673696d` | Auxiliary notify | Subscribed; role on the HR not established |
| `0000180a-…` / `2a26`, `2a24` | Device Information | Firmware string (identity), model number |
| `0000180f-…` / `2a19` | Battery | Percent |
| `108b5094-4c03-e51c-555e-105d1a1155f0` | Voice assistant | Unfinished Alexa support in Gadgetbridge |

All multi-byte integers are little-endian, except the CTR counter.

### Key handshake (on `3dda0005`)

| Step | Direction | Bytes |
|------|-----------|-------|
| 1 | phone → watch | `02 01 01` + `phone_random` (8 fresh random bytes) |
| 2 | watch → phone | byte 1 = `01`. Bytes 4–19 = AES-128(key, `watch_random ‖ phone_random`) |
| 3 | phone → watch | `02 02 01` + AES-128(key, `phone_random ‖ watch_random`) |
| 4 | watch → phone | `03 02 <result>`. 0 is success |

AES here is a single 16-byte block. The clients call it CBC with a zero IV,
which for one block is the same as ECB. Decrypting step 2 must give back
`phone_random` in its second half. If it does not, the key is wrong. Keep both
random numbers, because they seed the file IV. Both clients repeat the
handshake before **every** encrypted transfer.

### File layer

A file is named by a 16-bit handle, `major << 8 | minor`, sent minor first.
Some majors: `0x01` activity, `0x05` JSON/UI (minor is a rolling index),
`0x07` assets, `0x08` configuration, `0x09` notification play, `0x0a` alarms,
`0x0b` device info, `0x0c` notification filter, `0x15` watch apps, and
`0x00ff` firmware.

| Operation | Request on `3dda0003` | Reply (low nibble of byte 0) |
|-----------|-----------------------|------------------------------|
| Get | `01 <handle> 00000000 ffffffff` | `1`: handle, status, size u32. Then data on `3dda0004`, then `8`: status, CRC-32 at byte 8 |
| Lookup | `02 ff <major>` | `2`: size (0 = empty). The data's first two bytes are the concrete handle |
| Put | `03 <handle> 00000000 <len u32> <len u32>` | `3` (5 bytes, status). Stream packets, then `8` with CRC-32 |
| Close | `04 <handle>` | `4`: status |
| Delete | `0b <handle>` | `8b`: status |
| Timeout | — | `9` |

Data packets are `[flag][payload]`, sized to one ATT write (MTU − 3, at most
512, minus the flag byte). Flag bits 0–5 are a sequence number that wraps at
64, and bit 7 marks the last packet of a download. The CRC-32 the watch
reports is the standard zlib CRC over everything streamed.

Most files are a **container**: handle u16, file version u16, offset u32 (0),
length u32, payload, then CRC-32C (Castagnoli) of the payload. That is
16 bytes of overhead. The device-info file says which file version each
major expects. JSON pushes, watch apps (`.wapp`, which are already
containers) and firmware go up raw.

### Encrypted files

The configuration file (`0x08`) and the activity file (`0x01`) are
encrypted with AES-128-CTR under the watch key. The whole packet is
encrypted, flag byte included. The IV is 16 bytes:

```
00 00 | phone_random[0..5] (byte 7 incremented by 1) | 00 | watch_random[0..6]
```

- **Upload:** build the container (with file version `0x0002`). Then encrypt
  every packet on its own, starting from the same IV each time. The open
  request announces the plaintext length, and the CRC-32 reply covers the
  plaintext.
- **Download:** packet *N* is decrypted from IV + *step* × *N*, where the
  addition is to the big-endian u32 in IV bytes 12–15. The watch does not
  announce the step. Clients find it on packet 1 by trying 0x1e–0x2f until
  the decrypted flag byte reads `01` (or `81` for a final packet). The usual
  value is 0x1f.

Restarting at the same IV means the packets of one upload share keystream.
That is a weakness of the protocol as reported, not something to "fix" on
the client side, because the watch expects it.

### Operations carried by the file layer

| Operation | How |
|-----------|-----|
| Time sync | Encrypted put to `0x0800` of config item `0x0c`: UTC epoch u32, milliseconds u16, UTC offset minutes s16 |
| Settings | Same file: step goal `0x03`, vibration `0x0a`, units `0x10`, inactivity warning `0x09`, second time zone `0x11`, auto workout recognition `0x14` |
| Battery / steps readback | Lookup `02 ff 08`, then an encrypted get. Item `0x0d` holds millivolts u16 and percent u8, and `0x02` holds the step count |
| Notifications | Plain container put to `0x0900`: length, type (call, text, notification, …), flags, ids, CRC-32 of the app package, NUL-terminated title, sender and message |
| Call / dismiss / quick reply | Watch events on `3dda0006` (type `04`), answered with notification-file puts |
| Activity sync | Lookup `02 ff 01`, handshake, encrypted get, parse, then delete the handle. File version 22, start timestamp at offset 8, then a marker stream (heart rate variant) or 4-byte minute records |
| Buttons | Raw JSON put to `0x05xx`: `{"push":{"set":{"master._.config.buttons":[{"button_evt":"top_short_press_release","name":"weatherApp"}, …]}}}` |
| Hands | On `3dda0002`: take control `02 15 01 01 00 00`, move `02 15 03 …`, release `02 15 02 00 00`, save calibration `02 f2 0e` |
| Find watch | `02 06 30 75 00 00 00` on `3dda0005` vibrates and waits up to 30 s for a press (firmware 2.22+) |
| Watch apps | List with lookup `02 ff 15`. Install a `.wapp` raw to `0x15fe`, remove with delete `0x15<minor>` |
| Firmware | Raw put to `0x00ff`. The watch applies the image and reboots |

The YAML's `protocol_details` has the exact byte layouts and worked vectors:
the handshake, a time write, a battery read, a notification, a button push
and a hand move.

### Firmware update

Firmware is streamed as an ordinary file to OTA handle `0x00ff`. There is no
separate bootloader mode to enter. The images are not public, so Gadgetbridge
users capture the vendor's own image. Whether the bootloader checks a
signature, and what an interrupted update leaves behind, are unknown. The
`DN1.0.2.21r` image is documented to invalidate the stored key. Choose
the image for your hardware prefix.

## Why there are no entities

Every useful operation needs the key handshake, the file state machine and,
for configuration and activity, CTR encryption. A generic renderer cannot
do any of that. The spec is therefore `identify_only`, and its commands are
documented vocabulary for a dedicated handler.

## Open questions

- A scrubbed GATT dump per hardware revision, and the advertisement contents
  (is `3dda0001` always present? what do the Skagen and Citizen units call
  themselves?).
- The unmapped bytes in the handshake challenge and the transfer-complete
  frame.
- Which plain files the watch accepts before authentication.
- How the download IV step is derived, rather than searched for.
- What a factory reset does to the key.
- Firmware signing and recovery from an interrupted update.

## Sources

- [Gadgetbridge: Fossil device page](https://gadgetbridge.org/gadgets/wearables/fossil/)
  and [Fossil Hybrid firmware notes](https://gadgetbridge.org/internals/specifics/fossil-hybrid/)
- [Gadgetbridge qhybrid source at 160beab4](https://codeberg.org/Freeyourgadget/Gadgetbridge/src/commit/160beab417a034e7ee07a65152c70213b16f9e2b/app/src/main/java/nodomain/freeyourgadget/gadgetbridge/service/devices/qhybrid)
  (AGPL-3.0). Facts were derived from it; no code was copied.
- [Hybridge at f4b07f9d](https://github.com/jfoucher/Hybridge/tree/f4b07f9dd12e187ce7310ed34941d7a8e4424401)
  (MIT, iOS), used as an independent cross-check.
- [Gadgetbridge: using a Fossil watch's key](https://gadgetbridge.org/basics/pairing/fossil-server/),
  the owner-facing export route.

All example keys, random numbers and addresses in the spec are invented
(`0f1e2d3c4b5a69788796a5b4c3d2e1f0`, `00:00:5e:00:53:2a`).
