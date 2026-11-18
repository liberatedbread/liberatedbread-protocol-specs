# Adaprox Fingerbot / Fingerbot Plus (BLE)

> **Status**: Spec available; identify-only and untested
> **Protocol**: Tuya BLE v3, encrypted GATT session
> **Manufacturer**: Adaprox
> **Manufacturer Status**: Active

## Overview and safety boundary

This page covers three reported protocol-3 products: `ltak7e1p`,
`y6kttvd6` and `blliqpsj`. It does not treat every “Fingerbot” advertisement as
supported, and it does not include CubeTouch or other Tuya protocol
generations. The physical model/product-ID/GATT/DP association is still
reported pending a real device-info and GATT dump.

The Fingerbot moves a real arm and operates the button or switch to which it is
attached. Keep the mechanism and controlled appliance under direct observation
for every actuation and for the first firing of any timer or loop. Do not test
on a heater, cooker, door, power tool or other hazardous load. The spec is
`identify_only`: a dedicated stateful encrypted-session handler is required,
and this project does not offer unattended actuation.

## Initial setup, credentials and lifecycle

| Property | Value |
|----------|-------|
| Setup required | Yes — vendor binding, then device-ID/local-key export |
| Method | `ble_provisioning` in the vendor app, followed by `ble_direct` with a dedicated v3 client |
| Advertisement evidence | Documentary only: service data `0xA201` + company `0x07D0` (generic Tuya); manual product-ID/GATT selection required |
| Passphrase protection | `not_applicable` (BLE; no Wi-Fi credential) |
| Confidence | Medium for the public implementations, low for un dumped model/layout associations; no project hardware run |

Bind in the applicable Adaprox/Tuya app, then export the device ID and
16-character local key from the owner’s Tuya IoT project. These are
password-equivalent credentials; do not log them, PAIR payloads, derived
session keys, owner MAC addresses or account data. The vectors below use an
invented key only.

For a local session, take the first six local-key characters as `secret`:

```text
login_key   = MD5(secret)
session_key = MD5(secret || six-byte device_random)
```

Device-info uses security flag 4 and `login_key`. PAIR and subsequent DP
traffic use flag 5 and `session_key`. PAIR carries UUID, secret and device ID
padded to 44 bytes, but UUID is not a session-key input.

**Rebinding:** there is no Wi-Fi network to rejoin. Moving accounts requires an
unbind/reset, a new vendor binding, export of replacement credentials and a new
local session.

**Factory reset:** the reported route is vendor-app removal/reset (Tuya
UNBIND `0x0005` or DEVICE_RESET `0x0006`). No universal physical button hold is
asserted. Reset invalidates the current local credential; whether all stored
schedules survive is unknown, so do not use reset as a schedule-clearing
operation.

**Recovery:** close other companion/local connections before connecting. If a
unit belongs to somebody else’s account, guessing its local key is not a
recovery route; the owner must unbind it or it must be reset.

## Discovery and protocol-3 GATT

Advertisements identify only the Tuya BLE platform, not a Fingerbot. A201
service data with company `0x07D0` is shared with the soil tester and other
Tuya products, and the generic schema/mobile matcher has no `service_data`
key. **Manual selection is required**: do not auto-select this spec for another
Tuya product. Confirm the product ID and expected protocol-3 GATT layout after
connection. Do not probe layouts by actuating the arm.

| Role | Protocol-3 UUID |
|------|-----------------|
| Service | `00001910-0000-1000-8000-00805f9b34fb` |
| Host write | `00002b11-0000-1000-8000-00805f9b34fb` |
| Device notify | `00002b10-0000-1000-8000-00805f9b34fb` |

Subscribe before sending device-info. Notifications are fragments, not complete
packets. If the expected protocol-3 service is absent, stop rather than
substituting endpoints from another Tuya protocol generation.

## Wire envelope and fragmentation

The plaintext before encryption is:

```text
sequence u32be | response-to u32be | function u16be |
data-length u16be | data | CRC16 u16be
```

CRC is CRC-16/MODBUS (reflected polynomial `0xA001`, initial `0xffff`, no final
xor) over sequence through data, appended big-endian. The standard check value
for ASCII `123456789` is `0x4b37`. Append zero bytes after CRC to the next AES
block boundary, without a length byte and without another block when already
aligned. Encrypt with AES-128-CBC under the flag-selected key and a fresh
16-byte IV. The encrypted envelope is:

```text
security-flag u8 | IV[16] | ciphertext
```

On 20-byte GATT writes, fragment with unsigned base-128 varints (seven payload
bits, continuation bit `0x80`):

```text
first:  packet-number=0 varint | total-envelope-length varint |
        protocol-nibble | envelope prefix
later:  increasing packet-number varint | next envelope bytes
```

Reassemble exactly the declared envelope length, rejecting missing,
out-of-order and oversized fragments before decrypting. Verify the declared
data length and CRC; only then discard the zero padding after the CRC.

**Unresolved nibble:** the vendor protocol-3 framing reports `0x20`, while the
maintained community implementation emits `0x30` for v3. Do not silently
normalize one to the other. The frozen vector retains the community `0x30`.

### Independent frozen vector

With invented local key `abcdef0123456789`, secret `abcdef`, IV
`000102030405060708090a0b0c0d0e0f`, sequence 1, response-to 0, empty
device-info function `0x0000`, and flag 4:

```text
login key MD5:       e80b5017098950fc58aad83c8c14978e
plaintext + CRC:     0000000100000000000000009269
zero padding:        0000
encrypted envelope:  04000102030405060708090a0b0c0d0e0ff8bc69d43b1f0e3bf28ac34ec4aa2723
```

The expected two writes, shown concatenated, are:

```text
00213004000102030405060708090a0b0c0d0e0f01f8bc69d43b1f0e3bf28ac34ec4aa2723
```

They split into 20 and 17 bytes: the first ends after the IV, and the second
starts with packet number `01`. `scripts/test_adaprox_fingerbot.py` rebuilds the
plaintext, CRC, AES-CBC ciphertext and both fragments independently; it never
uses a real credential or performs actuation.

## Datapoint layouts

Protocol-3 DP records are:

```text
DP id u8 | type u8 | payload-length u8 | payload
```

Types are RAW 0, BOOL 1, VALUE 2, STRING 3, ENUM 4 and BITMAP 5. VALUE/ENUM
values decode as signed big-endian integers of the declared length; VALUE
writes are signed four-byte big-endian. This record rule is not generalized to
DP_V4.

DP2 is the mode-dependent action: attended push in push/click mode, switch
on/off in switch mode, and start/stop in program mode. Read DP8 and current
state first. **DP2 is the push operation for every covered layout.** DP101 is
only original `ltak7e1p`’s reported alternative to DP2 push, per
[ha_tuya_ble issue #9](https://github.com/PlusPlus-ua/ha_tuya_ble/issues/9);
do not assert it for the other products or send it as an additional push.

Other shared controls are mode DP8 (0 click/push, 1 switch, 2 program), down
movement DP9, up movement DP15, inversion DP11 and battery DP12. Down/up
movement is reported as 50–100% and 0–50% respectively; battery is 0–100%.
Tap-enable DP17 is reported on original `ltak7e1p` and Plus, not Plus-only and
not asserted for `y6kttvd6`.

| Layout | Product ID | Sustain DP10 | Raw timer | Four week programs | DP121 |
|--------|------------|--------------|-----------|--------------------|-------|
| `original_tenths` | `ltak7e1p` | raw × 0.1 s, raw 0–100 | DP111 | DP112–115 | Original-model support not asserted |
| `adaprox_low_schedule` | `y6kttvd6` | raw × 0.1 s, raw 0–100 | DP3 | DP4–7 | Reported only; representation/availability needs a dump |
| `plus_seconds` | `blliqpsj` | raw seconds, 0–10 | DP111 | DP112–115 | Reported Plus loop control; read before writing |

Do not import the `adaptive_movement` meaning used for DP121 on other
category-`kg` products.

All actuation, movement, sustain, timer, week-program and loop commands in the
spec are `advanced`. The layout-specific sustain scaling matters: a raw value
of 50 means 5 seconds on the first two layouts, while raw 5 means 5 seconds on
Plus. Treating them alike can produce a tenfold hold.

### Raw timer and week payloads

A raw timer is exactly five bytes:

```text
operation u8 | seconds u32be
```

A week program is also five bytes:

```text
operation u8 | days+enable u8 | hour u8 | minute u8 | second u8
```

Reported operation codes are 0 cancel, 1 click, 2 switch-on, 3 switch-off,
4 program-on and 5 program-off. The timer fixture for click after 300 seconds
is `010000012c`. The week fixture `0181061e00` uses `0x81` only as an opaque
encoding example. **Weekday bit ordering and the enable-bit position are not
established and are deliberately not guessed.**

Timers, week programs and loops can actuate after the phone disconnects. Build
and decode these payloads offline first, then test only on an inert installation
with a person present.

## Separate optional legacy plaintext

A separate legacy ASB/ABB report uses ASCII `*<code><payload>$`. Its transport
UUIDs, product applicability and code meanings are unknown. It is not the Tuya
encrypted DP protocol and not SwitchBot. Do not send those frames to `0x2B11`,
wrap them in Tuya AES/fragmentation, or parse either protocol with the other’s
handler. No legacy commands are declared.

## Firmware and unresolved work

Only generic reported Tuya OTA functions `0x000C–0x0010` are recorded. No image,
signature rule, bootloader identity, interruption recovery or production
firmware update is established. The update command is advanced; do not test it
on an installed actuator.

Remaining evidence needed: real GATT/device-info dumps for each product,
especially `y6kttvd6`’s DP3/4–7 mapping; fragment-nibble acceptance; weekday
bits; DP121 representation outside Plus; physical reset and schedule survival;
legacy ASB/ABB transport; and model-specific OTA/recovery. Protocol 4 and
CubeTouch require separate evidence and specifications.

## References

- [redphx/poc-tuya-ble-fingerbot](https://github.com/redphx/poc-tuya-ble-fingerbot) — protocol-3 transport and DP action proof of concept
- [PlusPlus-ua/python-tuya-ble](https://github.com/PlusPlus-ua/python-tuya-ble) — independent transport implementation
- [timlaing/ha_tuya_ble product descriptors](https://github.com/timlaing/ha_tuya_ble/tree/main/custom_components/tuya_ble/device_descriptors) — per-product controls and sustain scaling
- [Original-product DP report](https://github.com/PlusPlus-ua/ha_tuya_ble/issues/9) — `ltak7e1p`, including DP111/112–115
- [Adaprox Plus loop guide](https://www.adaprox.io/blogs/articles/set-up-a-loop-program-for-fingerbot-plus) — vendor feature documentation
- Machine-readable spec: `device-specs/devices/adaprox-fingerbot.yaml`

## Contributors

- Liberated Bread clean-room protocol transcription and independent synthetic vectors
