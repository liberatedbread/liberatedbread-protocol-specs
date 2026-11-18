# Easee Charge Max (local BLE)

> **Status**: Spec Available (capture-backed sources; untested here)
> **Protocol**: BLE GATT, EC-JPAKE and AES-256-GCM
> **Manufacturer**: Easee AS
> **Manufacturer Status**: Active

## Overview

Charge Max supports authenticated local BLE telemetry and control without an
Easee account. The owner needs the charger serial and the PIN printed on its
label or shown in the app—not the account password.

**Scope is Charge Max only.** Easee Home, Charge/Core, Equalizer, Charge Max
Eichrecht and other backplates are not qualified by this document. The upstream
integration physically tested Charge Max; its captured-byte tests are not a
new hardware test by this project.

The safe control surface is deliberately small: charger enable/disable,
temporary dynamic current, LED brightness and Bluetooth advertisement mode.
Installer/fuse/circuit limits, phase changes, Wi-Fi provisioning, RFID,
reboot/self-test, factory reset and firmware operations are excluded.

## Initial Setup

| Property | Value |
|----------|-------|
| Setup required | Serial + owner PIN and authenticated handshake |
| Method | `ble_direct` with an advertising window |
| Discovery | Company ID `3118` (`0x0c26`); vendor service after connect |
| Pairing/bonding | No OS bond required; application EC-JPAKE |
| Connection limit | One BLE central |
| Confidence | High for upstream Charge Max core; unreplayed here |

Long-press the touch button for **5 seconds** to open an advertising window of
a few minutes, or enable Bluetooth always-on in the vendor app. Subscribe to
COMMAND, CONFIG and STATE, request advisory MTU 333, and perform two EC-JPAKE
rounds over HELLO. Then retain the session and serialize one request at a time.

On Linux/BlueZ, the tested charger lacks descriptors needed for notification
subscription. The reported working route is an **active ESPHome Bluetooth
proxy** with 320 ms scan interval and 30 ms window, not a directly attached
adapter or a proxy scanning continuously.

**Factory reset**: command `97` exists but is untested/irreversible upstream;
its effect is not established and it is not offered. No reset is needed to
move a BLE client. Close the old central, open advertising and repeat the
handshake with the current PIN. Wi-Fi re-provisioning is outside this spec.

**Credentials**: keep PIN, serial, session keys and Structure responses out of
logs. Structure can contain account/key material and is never polled here. No
Wi-Fi passphrase is sent by this spec.

## Authentication and record layer

### BLE Services

| UUID | Name | Description |
|------|------|-------------|
| `be312306-9797-2ebc-c947-08eff95544bc` | Easee local service | Container |
| `2f7b83db-ae66-d0be-ae45-78ecf4509b3d` | HELLO | Raw two-round EC-JPAKE exchange |
| `f4ef9f9e-540e-0497-1449-84fe940045be` | COMMAND | Encrypted JSON commands; JSON replies |
| `7d0b575a-5f58-cf9c-c442-2cacd56e4102` | CONFIG | Encrypted poll; plaintext protobuf response `0x40` |
| `992166b7-8cb3-fba7-9f4b-166fb352c50d` | STATE | Encrypted poll; plaintext protobuf response `0x41` |
| `3368fdd0-d18a-61aa-034b-9abc497cbec1` | STRUCTURE | Sensitive; not polled |
| `2737ec9f-2dc1-7a8e-2048-de136057f9ab` | DEBUG | Unknown fields; not named |
| `fe14720f-d849-4f83-5144-d0f5b4f3689d` | TIME | Not exposed on tested Charge Max |

EC-JPAKE uses NIST P-256/secp256r1, Schnorr proofs and SHA-256. The spec gives
curve constants, exact point/scalar encodings, identities `client`/`server`,
proof hashes, both rounds and the final KDF. Round one carries two proofs and
is normally 330 bytes. The server's round two starts `03 00 17`; the client's
has no curve prefix. The resulting key is 32 bytes.

Subsequent requests use AES-256-GCM with an empty AAD, a fresh four-byte
nonce and a 16-byte tag. The binary record is:

```text
nonce[4] || tag[16] || ciphertext[len(plaintext)]
```

Encode that whole record as lowercase ASCII hex before writing. Poll plaintext
is `{"uid":N,"sn":"SERIAL"}`; command arguments are strings, including
lowercase `true`/`false`. Verify every GCM tag and never reuse a nonce under a
session key. Protobuf responses are raw plaintext, not ASCII-hex ciphertext.

The focused standard-library test independently performs P-256 arithmetic,
Schnorr verification and the KDF against the public mbedTLS vector, and
AES-256-GCM against the public Easee vector. It uses only invented/dummy
identifiers.

## Responses and telemetry

CONFIG, STATE, STRUCTURE and DEBUG responses have a six-byte header:

| Offset | Meaning |
|--------|---------|
| 0 | Zero |
| 1 | Type: `0x40` Config, `0x41` State, `0x42` Structure, `0x43` Debug |
| 2–3 | `01 01` in captures; not a field to hard-code as a version gate |
| 4–5 | Big-endian **total** length, header included |
| 6… | Schema-less protobuf, exactly `length - 6` bytes |

Buffer split notifications and split coalesced frames by the declared length.
Decode varints, little-endian float32/float64 and bounded length-delimited
fields; preserve unknown field numbers. Missing voltage or an unknown field is
unknown, not zero. Only the spec's explicit captured zero-when-absent list may
be synthesized, including dynamic current, phase currents, total power and
`isEnabled`.

Telemetry includes total power (kW), session/lifetime energy (kWh), per-phase
current (A), voltages (V), operating state, reason-for-no-current, dynamic
current (A), cable rating (A), firmware and Bluetooth mode. COMMAND replies
are JSON: `code == 1` is accepted; anything else is a refusal even if transport
succeeded. Always confirm accepted writes with fresh Config/State.

## Bounded controls

- **29** sets charger enabled with string `true`/`false`.
- **48** sets temporary dynamic current in whole amperes; `0` pauses and a
  positive value resumes. The protocol's `0–40 A` bound is only a serializer
  sanity limit, not the unit or circuit rating.
- **40** sets LED brightness `0–100 %`.
- **96** selects button-only advertising (`1`) or always-on (`3`).

Before every current write, clamp to the lowest applicable installer circuit
maximum, charger maximum, cable rating, dynamic limit and owner-confirmed
continuous-load limit. Never raise an installer setting over BLE. This client
is not an emergency stop or protective electrical interlock.

## Evidence and limits

The pinned `easee-ble` client supplies authentication, record framing, command
shapes and captured-byte tests; `ha-easee-ble` supplies Charge Max-only
qualification, host/proxy constraints and readback behavior. Vendor app static
review corroborates the authentication family and offline local control. No
charger, account, cloud endpoint or owner credential was used.

Unknown protobuf schema changes, real GATT/advertising variation, notification
fragmentation on every proxy, exact electrical-limit precedence, factory reset,
other models, OCPP and firmware remain open.

- [parrel/easee-ble](https://github.com/parrel/easee-ble/tree/bec7b061fc8199cd150dbb8bbce5ed5112145ede)
- [parrel/ha-easee-ble](https://github.com/parrel/ha-easee-ble/tree/9973cec92660ecd791a9809eb06361bd5b535f1b)
