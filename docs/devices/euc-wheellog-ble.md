# Electric Unicycles (WheelLog)

> **Status**: Spec available, reported and untested on hardware by this project
> **Protocol**: BLE serial write/notify stream
> **Manufacturers**: King Song, Gotway/Begode, Veteran/Leaperkim and Ninebot
> **Manufacturer status**: Active

## Overview

WheelLog decodes King Song, Gotway/Begode, Veteran/Leaperkim and Ninebot Z
electric unicycles locally over BLE. No vendor cloud is needed on this control
path. Other brands' service and characteristic UUIDs are module-specific and
unasserted. The Ninebot Z has a reported Nordic-UART transport below, but that
shared transport is not advertisement identity; always select the wheel model
manually and confirm its protocol after connecting.

King Song uses a 20-byte `AA 55` frame with packet type at byte 16.
Gotway/Begode uses a 24-byte `55 AA` frame with a `5A 5A 5A 5A` footer and type
at byte 18. Veteran/Leaperkim uses `DC 5A 5C`, a length byte and big-endian
telemetry. Their existing entries in the spec are unchanged. InMotion's legacy
and V2 protocols have a [separate spec and guide](inmotion-euc.md).

The machine-readable source of truth is
`device-specs/devices/euc-wheellog-ble.yaml`.

## Ninebot Z: a distinct WheelLog variant

The Ninebot Z decoder is **not** the
[Ninebot/Segway e-scooter protocol](ninebot-segway-ble.md). They share the NUS
trio and the `5A A5` header, clear payload length, `L + 9` accounting and
little-endian-checksum envelope. The Z is distinguished by its repeating-XOR
session transform, role addresses and telemetry payloads, not by different
outer length semantics. Do not send the scooter's register commands to a Z
wheel or the Z's requests to a scooter.

The Z addition is read-only: identification, live telemetry and BMS telemetry.
It deliberately declares no vehicle-setting, calibration, power, light, lock,
alarm, speed-limit or firmware writes.

### Reported transport and model selection

WheelLog's constants and Ninebot Z GATT fingerprint entries report:

| Role | UUID |
|---|---|
| Nordic-UART service | `6e400001-b5a3-f393-e0a9-e50e24dcca9e` |
| RX / write | `6e400002-b5a3-f393-e0a9-e50e24dcca9e` |
| TX / notify | `6e400003-b5a3-f393-e0a9-e50e24dcca9e` |

This is reported post-connect transport, not an observed advertisement rule.
The same trio appears on Ninebot/Segway scooters, InMotion V2 and unrelated
UART peripherals. Do not scan-match it. A person must manually select the
Ninebot Z before any GATT write, then use only the documented read requests and
confirm the Z role addresses and payload layout. Stop if the response belongs
to the scooter register protocol. Neither NUS nor the outer frame is protocol
confirmation by itself.

### Frame, checksum and reassembly

A frame contains:

| Frame offset | Contents |
|---|---|
| 0-1 | Clear header `5A A5` |
| 2 | Clear payload length `L`, an unsigned byte |
| 3 onward | Transformed body: source, destination, command, parameter, `L` payload bytes and a two-byte little-endian checksum |

The complete frame is **`L + 9` bytes**. Before applying the session transform,
the body after the header is:

```text
L | source | destination | command | parameter | payload[L] | checksum_u16_le
```

The checksum is computed over the plaintext `L` through final payload byte,
excluding the header and checksum:

```text
checksum = (~sum(those_bytes)) & 0xffff
```

The obfuscation is reversible repeating XOR, not authentication or secure
encryption. Start each connection with a 16-byte all-zero key. Leave body byte
zero (`L`) unchanged; for every later body index `i >= 1`:

```text
transformed[i] = plaintext[i] XOR session_key[(i - 1) mod 16]
```

Apply the same operation to decode and encode. The checksum is calculated
before obfuscation on writes and checked after obfuscation removal on reads.

BLE notifications do not preserve frame boundaries. Buffer across them, scan
for `5A A5`, read the clear length and wait for exactly `L + 9` bytes. A header
pattern inside a collecting frame is payload, not a new frame. Reject a bad
checksum without decoding the payload, then resume scanning. Several frames
may arrive together, and either byte of the header may be in a different
notification.

### Addresses and read-only session messages

Protocol addresses are role identifiers, not Bluetooth MAC addresses:

| Role | Address |
|---|---:|
| BMS 1 | `0x11` |
| BMS 2 | `0x12` |
| Main controller | `0x14` |
| Session-key generator | `0x16` |
| Phone/client | `0x3e` |

Ordinary reads use command `0x01`; their replies use `0x04`. The key request
uses `0x5b`. For an ordinary read, the request's one-byte payload is the desired
response payload length, while the request's own `L` is one.

| Operation | Destination / parameter | Request payload | Expected response |
|---|---|---|---|
| Initial BLE-version read | Controller / `0x68` | `02` | Controller, parameter `0x68` |
| Key-request constructor | Key generator / `0x00`, command `0x5b` | empty | Decoder branch accepts `0x00`; sole upstream sample is `0x01` and unhandled |
| Controller serial | Controller / `0x10` | `0e` | 14-byte ASCII serial |
| Live telemetry | Controller / `0xb0` | `20` | 32-byte live payload |
| BMS identity | BMS 1 or 2 / `0x10` | `22` | 34-byte identity payload |
| BMS status | BMS 1 or 2 / `0x30` | `18` | 24-byte status payload |
| BMS cells | BMS 1 or 2 / `0x40` | `20` | 32-byte cell payload |

The decoder starts with 16 zero transform bytes. Its source-code branch for a
key-generator reply with parameter `0x00` copies the payload into that transform
key. This is only an accepted decoder branch, **not an established over-the-air
response selector**. The sole upstream key-reply sample instead has parameter
`0x01`, does not match that branch and is not installed as a key. Real key
installation and the request order therefore remain pending an owner-authorized
read-only capture. No working negotiation is claimed.

### Live telemetry

Offsets below are into the 32-byte payload, not the outer frame. Multi-byte
integers are little-endian. Decoded value is `raw × scale + value_offset`.

| Offset | Type | Field | Scale / offset | Decoded unit |
|---:|---|---|---|---|
| 0 | `uint16` | Error code | 1 | code |
| 2 | `uint16` | Alarm code | 1 | code |
| 4 | `uint16` | Controller status | 1 | code |
| 6 | 2 bytes | Reserved / unread | — | — |
| 8 | `uint16` | Battery | 1 | `%` |
| 10 | `uint16` | Speed | 0.01 | `km/h` |
| 12 | `uint16` | Average speed | 0.01 | `km/h` |
| 14 | `uint32` | Total distance | 1 | `m` |
| 18 | `uint16` | Trip distance | 10 | `m` |
| 20 | `uint16` | Operating time | 1 | `s` (reported; not consumed by the decoder) |
| 22 | `int16` | Temperature | 0.1 | `C` |
| 24 | `uint16` | Pack voltage | 0.01 | `V` |
| 26 | `int16` | Pack current | 0.01 | `A` |
| 28 | `uint16` | Duplicate speed | 0.01 | `km/h` |
| 30 | `uint16` | Duplicate average speed | 0.01 | `km/h` |

The source identifies offsets 28 and 30 as duplicates of 10 and 12 and does not
consume them.

### BMS identity layout (`0x10`, 34 bytes)

Both BMS addresses use the same layout:

- Bytes 0-13: 14-byte ASCII serial.
- Bytes 14-15: version formatted as hexadecimal byte 15, high nibble of byte
  14, low nibble of byte 14, joined with dots. Bytes `23 01` mean `1.2.3`.
- Bytes 16-17 and 18-19: factory and actual capacity, `uint16` little-endian,
  scale 1, reported in `mAh`.
- Bytes 20-21: not interpreted by the source.
- Bytes 22-23 and 24-25: full-cycle and charge counts, `uint16` little-endian.
- Bytes 26-31: not interpreted by the source.
- Bytes 32-33: packed manufacture date, `uint16` little-endian. Year is
  `2000 + (raw >> 9)`, month is `(raw >> 5) & 0x0f`, and day is `raw & 0x1f`.

Capacity units and the exact key negotiation remain reported rather than
hardware-confirmed.

### BMS status layout (`0x30`, 24 bytes)

| Offset | Type | Field | Scale / offset | Decoded unit |
|---:|---|---|---|---|
| 0 | `uint16` | BMS status | 1 | code |
| 2 | `uint16` | Remaining capacity | 1 | `mAh` (reported) |
| 4 | `uint16` | Remaining charge | 1 | `%` |
| 6 | `int16` | Current | 0.01 | `A` |
| 8 | `uint16` | Voltage | 0.01 | `V` |
| 10 | `int8` | Temperature 1 | raw − 20 | `C` |
| 11 | `int8` | Temperature 2 | raw − 20 | `C` |
| 12 | `uint16` | Balance bitmap | 1 | bitmap |
| 14 | 8 bytes | Reserved / unread | — | — |
| 22 | `uint16` | Health | 1 | `%` |

All multi-byte values in this table are little-endian. The signed current and
signed one-byte temperature representations are load-bearing.

### BMS cell layout (`0x40`, 32 bytes)

Sixteen consecutive `uint16` little-endian cell voltages occupy offsets 0-31;
scale each by 0.001 to volts. Start with 14 cells. A nonzero cell 15 at offset
28 increases the count to 15, and a nonzero cell 16 at offset 30 increases it
to 16. Trailing zero cells are absent.

### Codec proof

`scripts/test_ninebot_z_spec.py` independently transcribes the framing, XOR,
checksum, reassembly and payload layouts using only the standard library. It
checks all ten synthetic codec-only vectors, every split point of a live frame,
noise and bad checksum recovery, coalesced frames, both BMS addresses and
14-/16-cell cases. The transform key and every controller/BMS serial in the
vectors are invented. A separate evidence test records that the sole upstream
`0x01` key sample is unhandled and that installation remains pending capture.
These tests establish codec implementability, not negotiation or hardware
verification.

## Setup, pairing, reset and rebinding

Manually select the exact wheel before any GATT write. Power it, connect to its
reported BLE serial characteristic and subscribe to notifications. No link-layer
pairing secret is documented. The Ninebot Z transform value is obfuscation
material, not an owner credential, and its real installation is still pending
capture.

No BLE factory-reset procedure is established for this family. There is no
Wi-Fi membership to rejoin: a new BLE client connects independently. Close the
previous client before connecting another if the wheel accepts only one central.

## References

- [WheelLog Android](https://github.com/Wheellog/Wheellog.Android)
- [WheelLog Ninebot Z decoder, pinned source](https://github.com/Wheellog/Wheellog.Android/blob/1b3707973e3b4528bd88778f9ebdf7a79817cf3f/app/src/main/java/com/cooper/wheellog/utils/NinebotZAdapter.java)
- [WheelLog BLE constants, pinned source](https://github.com/Wheellog/Wheellog.Android/blob/1b3707973e3b4528bd88778f9ebdf7a79817cf3f/app/src/main/java/com/cooper/wheellog/utils/Constants.kt)
- [WheelLog GATT fingerprints, pinned source](https://github.com/Wheellog/Wheellog.Android/blob/1b3707973e3b4528bd88778f9ebdf7a79817cf3f/app/src/main/res/raw/bluetooth_services.json)
- [WheelLog Ninebot Z decoder tests, pinned source](https://github.com/Wheellog/Wheellog.Android/blob/1b3707973e3b4528bd88778f9ebdf7a79817cf3f/app/src/test/java/com/cooper/wheellog/utils/NinebotZAdapterTest.kt)
