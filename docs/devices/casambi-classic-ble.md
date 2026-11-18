# Casambi Classic BLE lighting networks (protocols 5–9)

> **Status**: Spec Available — reported/untested; identify-only until a dedicated full-session consumer exists
> **Protocol**: BLE GATT, plaintext application frames with AES-CMAC
> **Manufacturer**: Casambi Technologies Oy (active)

## Overview

This page documents the **app-corroborated full-network Classic API** for
protocols 5, 6, 7, 8 and 9 using the new UUID scheme. The machine-readable source
is [`casambi-classic-ble.yaml`](https://github.com/liberatedbread/liberatedbread-protocol-specs/blob/main/device-specs/devices/casambi-classic-ble.yaml).
For the encrypted Evolution generation, see
[Casambi Evolution BLE](casambi-evolution-ble.md).

Two other interfaces are deliberately not mixed into this document:

- the separate `CasambiDevice`/direct API writes raw opcodes to FE3D or FE4D
  characteristics, with a different challenge/sequence description. FE3D was
  not found in the reviewed vendor app and this path was not independently
  validated. Its direct opcodes, MD5 payloads and golden vectors are excluded;
- the legacy CA5A/CA52-family header is uncertain because the recovered builder
  appears to overwrite its own type/MAC slot. It needs capture and has no
  commands here.

**Classic does not encrypt its command or state payloads.** Visitor frames add a
four-byte AES-CMAC and manager frames a sixteen-byte CMAC. That provides
integrity, not confidentiality. Evolution's NodeInfo, P-256 ECDH, AES-CTR and
type-7 invocations do not belong on this API.

## Hardware and discovery

| Property | Value |
|----------|-------|
| Family | Casambi Ready fixtures/drivers on a Classic full-network mesh |
| Example public hardware | CBU-PWM4 and generic Board; no universal model claim |
| Radio | BLE GATT; one nearby node relays into the mesh |
| Service | `0000fe4d-0000-1000-8000-00805f9b34fb` (`0xFE4D`) |
| Company id | `0x03C3` / 963; bytes `c3 03` on air |
| Companion app | Casambi, Android package `casambi.ambi`; the reviewed release still has the Classic path |
| FCC ID | Check each partner fixture/module; no family-wide id is asserted |

FE4D and company `0x03C3` are shared with Evolution. For a short network advert,
byte 6 after the company-id bytes has network protocol in its low five bits.
Accept 5–9 for this spec, 10–11 for Evolution and nothing else here. Long unit
adverts use offset 19 for that byte after validating their layout. The direct
client's reversed-address passive-beacon parser is not this full-session
discovery grammar or an OUI.

## Initial setup and warm-cache boundary

| Property | Value |
|----------|-------|
| Setup required | Yes, for each new full-session controller/cache |
| Existing-cache route | `ble_direct` with a complete compatible Classic JSON cache |
| First-time route | `cloud_account` with owner-authorized credentials |
| Wi-Fi passphrase protection | Not applicable to the BLE mesh |
| Confidence | Medium — app and public client, no hardware replay here |

A first-time client downloads the network's `visitorKey`, optional `managerKey`,
protocol, units, groups, scenes and every referenced fixture definition. A
complete offline cache has `.cachever = 4` (or a documented equivalent), network
id, network JSON, `casambi_lookup.json`, `casambi_session.json` and
`casambi_types.json`.

**A cached network id does not prove offline readiness.** The pinned clients can
still request a missing or 28-day-expired fixture even in `force_offline` mode.
Keys remain plaintext hex in the JSON cache; use the intended 0700 directory and
0600 file permissions and preserve the whole same-version directory. Legacy
`keys.pck`, `session.pck` and `types.pck` files are ignored, not migrated as
objects or treated as interchangeable with Evolution/Android/ESP32 backups.

No offline first-time key/topology issuer, cloud replacement, Network History
replacement or lost-credential recovery was found. Foreign unpair and uncached
firmware also remain vendor-service operations.

## Pairing, reset, rejoin and unpairing

| Property | Value |
|----------|-------|
| OS Bluetooth pairing/bonding | Not used |
| Application authorization | Required — cloud-provisioned visitor/manager key plus CMAC |
| Connection exclusivity | Unknown for the full session; close other clients on failure |
| Enter-pairing-mode action | None for an already provisioned network |
| Factory reset | Unknown; no universal Casambi Ready procedure is established |
| Rejoin another mesh | Unpair and recommission, not an in-place network-setting change |
| Foreign-unit unpair | Requires `fixture/unpair` cloud authorization |

Manager-authorized unpair is management frame type 2 on characteristic 0002.
Foreign fixtures need a cloud-issued key before that write. The official guided
recovery's timed power-cycle/partner-switch action does not make arbitrary power
cycling a reset or an offline unpair implementation.

Classic operation type 53 is a manager-authorized network Reset operation, not
proof of a universal physical factory reset or its cleared-state list. Deleting
the controller's cache is not a fixture reset. Preserve/share the full cache
before losing the old controller or network, particularly an unshared network.

## GATT profile

| Characteristic | Role |
|----------------|------|
| `c9ffde48-ca5a-0001-ab83-8f519b482f77` | Connection-hash read, signed full-session writes, plaintext state/config/response notifications |
| `c9ffde48-ca5a-0002-ab83-8f519b482f77` | Visitor-signed time sync, manager-signed unpair, unsigned hardware configuration |
| `c9ffde48-ca5a-0003-ab83-8f519b482f77` | Advanced Classic OTA transfer |

Classic normally uses ATT MTU 23 and writes with response; larger frames can use
write-without-response within the negotiated budget. No fixed generic GATT
command is declared because every write needs the current connection hash,
selector, role, sequence and operation context.

## Full-session connection and envelope

The first read on 0001 returns eight bytes, or thirteen in the gateway form:

| Offset | Type | Meaning |
|---:|---|---|
| 0 | 8 bytes | Per-connection hash used as the CMAC prefix |
| 8 | `u8` | Unit id, when present |
| 9 | `u8` | Flags low, when present |
| 10 | `u8` | Nonzero MTU, when present |
| 11 | `u8` | Protocol 5–9, when present |
| 12 | `u8` | Flags high; combined flags are `low | (high << 8)` |

Reject other lengths, zero MTU and protocols outside 5–9. The connection hash is
not an ECDH secret or Evolution's 16-byte nonce and must be reread on reconnect.
Subscribe, then sign and send startup payload `00 01 0b` with sequence 1 using
the ordinary visitor role (or an explicitly administrative queue's role).

Every new-scheme signed envelope is:

```text
key_selector | CMAC | sequence:u16be | [frame_type] | payload
CMAC input = connection_hash[8] || sequence || optional_frame_type || payload
```

| Selector | Key and tag | Use |
|---:|---|---|
| 1 | No key, no MAC bytes | Explicitly unauthenticated management such as hardware-config request `01 05` |
| 2 | 16-byte visitor key, first 4 CMAC bytes | Ordinary commands and time sync |
| 3 | 16-byte manager key, full 16-byte CMAC | Administrative and unpair operations |

The selector is not included in the CMAC input. Sequence is **16-bit big-endian**,
not the direct API's one-byte sequence. It runs from 1 through 65535 and skips
zero on wrap. Command origin is a separate `u8` rolling through 1–255. Validate
selector, all MAC/sequence bytes, nonzero sequence and CMAC in constant time
before parsing a payload.

## Classic operation records

Ordinary operation records follow the envelope sequence directly, without a
frame-type byte. Total length is 4–16 bytes:

```text
0xf0 | (total_length - 1) | type_flags | origin | [target_id] | lifetime(200) | payload
```

Outgoing records always set origin flag `0x40`; a unit/group/scene target also
sets `0x80`. Whole-network targets have no target id. SetTemperature, SetColor,
SetVertical and SetWhite do not accept scene targets in the pinned full-session
map. Reject bad length markers, missing origin/target/lifetime, invalid
operation/target combinations and truncated payloads.

Core operation types are:

| Scope | Level | Temperature | RGB color | Vertical | White |
|---|---:|---:|---:|---:|---:|
| Scene | 1 | 2 | 3 | — | — |
| Whole network | 4 | 5 | 6 | 22 | 23 |
| Unit | 7 | 8 | 9 | 24 | 25 |
| Group | 26 | 27 | 28 | 29 | 30 |

- Level/white are `u8` 0–255; percent is raw × 100/255. Vertical is a
  fixture-directed top/bottom balance.
- Temperature is `floor(K / 50)` in one byte, maximum 12750 K, with fixture
  limits enforced separately.
- Classic color is three `u8` channels in R, G, B order—not Evolution HS.
- Ordinary restore-on is `ff 01 00 00 01`; the specialized scene-level payload
  is `level || 00 00 01`. Evolution's `ff 05` is not interchangeable.

The spec's 16 relevant public golden vectors cover all 16 network/unit/group/
scene combinations implemented by the full-session operation map. Other types
are declared with boundaries in the YAML: manager DeleteNode 10, SetFirmwareVersion
11, SetRadioMode 12 and Reset 53; Extended Upgrade 16; timers 15; parameters,
sensors, calibration, incoming button/presence events and vendor-specific records.
Destructive/model-specific operations are advanced and are not generic controls.

## Direct state and incoming state

A direct-state write uses frame type 6:

```text
unit_id | flags_and_length | [scene_id] | state_vector
```

The low nibble is exact state length and bit 6 adds the scene id. Require the
optional id, exact state bytes and a matching cached fixture `stateLength`.

Incoming first bytes `00` and `ff` mark configuration and debug text, not unit
state. `f0` starts a response: responding unit, origin and remaining state.
Other records carry unit id and flags; low nibble is state length, bit 4 is a
source flag, bit 5 adds level, bit 6 adds source, and **bit 7 is the
app-corroborated on flag**. The pinned Python client calls that bit online and
hardcodes on=True; the YAML records the discrepancy instead of hiding it. A
redacted app-session capture is still wanted.

Fixture definitions are mandatory for semantic state decoding and read-modify-
write. Missing metadata permits only raw-byte retention. Reject empty/truncated
headers, missing extras, short state and trailing data; never emit a partial
unit update.

## Time sync, management and OTA

Classic time sync uses type 7 with visitor CMAC on characteristic 0002. Its
calendar/timezone/DST layout differs from Evolution: reported coordinate fields
are two three-byte values plus a final latitude-high byte. That coordinate
packing needs capture, so do not generate location sync by borrowing Evolution's
signed 16.16 fields. Omitting location sync is safer than sending a guess.

**OTA is advanced and untested.** Classic uses the `0xca5a0002` container,
outer CRC-32, typed blocks and a 64-byte trailer on characteristic 0003. PREPARE
starts the transfer; each block receives a little-endian CRC-32 of bytes 4
onward before BEGIN/DATA/COMMIT, and APPLY `05` follows the last acknowledged
block. Match Classic generation, board, CPU, device, flags and variant.

The app validates container CRC, not the trailer's trust root. Signature
algorithm/enforcement, bad-block behavior, update-mode appearance and
interruption recovery remain unknown. Never apply an incomplete image or assume
Nordic DFU behavior. Classic operation type 16 starts an advanced Evolution
conversion. Returning requires individually unpairing every unit, restoring
Classic firmware and creating/programming a new Classic network; there is no
network-level rollback.

## Validation and omissions

`scripts/test_casambi_classic_spec.py` reads the spec with PyYAML and otherwise
uses only the standard library for AES-CMAC, envelopes, operation records,
connection info and state parsing. It reproduces all three relevant visitor/
manager CMAC fixtures and all 16 full-session operation fixtures, checks sequence
zero/wrap boundaries, and exercises malformed signatures, frames, versions,
states and fixture misses. Direct/FE3D opcodes and `protected_mesh_xor` are not
part of the suite.

Open work includes legacy framing, direct-API interoperability, Classic location
packing, bit-7 capture reconciliation, universal reset/foreign unpair, cache
conversion and OTA trust/recovery.

## References

- [Pinned full-session `casambi-classic-ble`](https://github.com/hellqvio86/casambi-classic-ble/tree/98ebe25bd95897c24ee471c5f011dfaf62ecda12)
- [Pinned Classic Home Assistant integration](https://github.com/hellqvio86/casambi-classic-bt-hass/tree/428b192a6d051bb8c836f3279337e91595a24c7f)
- [Vendor Classic versus Evolution article](https://support.casambi.com/support/solutions/articles/12000068796-what-is-classic-and-evolution-)
- [Casambi app user guide, February 2026](https://support.casambi.com/helpdesk/attachments/12179447849), HTTP 200 verified 2026-11-18
- [Operation and maintenance manual](https://support.casambi.com/helpdesk/attachments/12159158129), HTTP 200 verified 2026-11-18
- [CBU-PWM4 datasheet](https://7177595.fs1.hubspotusercontent-na1.net/hubfs/7177595/Data%20sheets/CBU_PWM4_Data-Sheet_EU_EN_2_0.pdf), HTTP 200 verified 2026-11-18
- [Official paired-device troubleshooting](https://support.casambi.com/support/solutions/articles/12000096173-troubleshooting-paired-devices)
- [Public Board fixture 1 control definition](https://api.casambi.com/fixture/1), HTTP 200 verified 2026-11-18
