# Casambi Evolution BLE lighting networks (protocols 10–11)

> **Status**: Spec Available — reported/untested; identify-only until a dedicated consumer exists
> **Protocol**: BLE GATT, encrypted application session
> **Manufacturer**: Casambi Technologies Oy (active)

## Overview

Casambi Evolution is a BLE lighting mesh, not one luminaire model. A controller
connects to a nearby node and that node relays operations through its network.
The machine-readable source is
[`casambi-evolution-ble.yaml`](https://github.com/liberatedbread/liberatedbread-protocol-specs/blob/main/device-specs/devices/casambi-evolution-ble.yaml).

This profile accepts **network protocols 10 and 11 only**. Protocol 12 is not
claimed: the reviewed vendor app recognizes it, but the pinned independent
Evolution client stops at 11 and no live protocol-12 validation exists. Network
protocol, fixture firmware version and firmware grade are separate properties.

Classic is different. Its plaintext-plus-CMAC full-session protocol is documented
in [Casambi Classic BLE](casambi-classic-ble.md); do not send it this page's
ECDH/CTR packets.

## Hardware and discovery

| Property | Value |
|----------|-------|
| Family | Casambi Ready fixtures, drivers, switches and sensors on an Evolution mesh |
| Example public fixture | CBU-DCS DALI Gateway (fixture 9000); generic Board (fixture 1) |
| Radio | BLE; one node is the controller's entry into the mesh |
| Service | `0000fe4d-0000-1000-8000-00805f9b34fb` (`0xFE4D`) |
| Company id | `0x03C3` / 963; bytes `c3 03` on air |
| Companion app | Casambi, Android package `casambi.ambi` |
| FCC ID | Not generalized across partner products; check the exact fixture/module |

FE4D and company `0x03C3` are only a family match shared with Classic. In a short
network advert, byte 6 after the two company-id bytes contains variant flags in
its upper three bits and network protocol in its low five. Accept 10 or 11 here,
5–9 for Classic, and nothing else for this profile. Long unit adverts put that
byte at offset 19 after the company id. The six-byte network id identifies the
mesh; it is not a public IEEE OUI.

The legacy `5a ca` marker selects another UUID scheme. `ca 5c` information
adverts are a separate authenticated-advert mechanism, not NodeInfo or a session
replacement.

## Initial setup and offline boundary

| Property | Value |
|----------|-------|
| Setup required | Yes, for each new controller/cache |
| Easiest existing-cache route | `ble_direct` with a complete warm cache |
| First-time route | `cloud_account` with owner-authorized network credentials |
| Wi-Fi passphrase protection | Not applicable to the BLE mesh |
| Confidence | Medium — public implementations, not replayed here |

A first-time client must obtain and protect:

- the network's 16-byte keyStore entries, key ids and roles;
- units, fixture ids/device ids, groups and scenes;
- every fixture's `stateLength` and complete control definitions, including bit
  offset, bit length, default, read-only flag and engineering min/max;
- a compatible cache version and unexpired fixture entries (28 days in the
  pinned Python clients).

Only then is ordinary in-range control cloud-independent. **A network id,
password or topology without fixture controls is not a warm cache.** A complete
same-version trusted backup is a plausible offline restoration route, not an
official portable export. The Evolution Python cache contains plaintext pickles;
never load one from an untrusted source.

No independent offline first-time provisioner was found. New networks, lost
credentials without a backup, cloud Network History, foreign-fixture unpair keys
and uncached firmware remain vendor-service dependencies.

## Pairing, reset, rejoin and unpairing

| Property | Value |
|----------|-------|
| OS Bluetooth pairing/bonding | Not used |
| Application authorization | Required — keyStore plus authenticated ECDH session |
| Connection exclusivity | Unknown per node; close other clients if connection fails |
| Enter-pairing-mode action | None for an already provisioned network |
| Factory reset | Unknown; no universal Casambi Ready procedure is established |
| Rejoin another mesh | Unpair and recommission; not an in-place router-style change |
| Foreign-unit unpair | Requires a cloud-issued unpair key |

A new ECDH exchange supplies transport encryption, not network authorization.
The client must also verify the network-key authentication response and receive
a nonzero role: User 1, Manager 2 or Admin 3. Denied 0 is not a usable session.

Manager-authorized unpair uses management frame type 2 on characteristic 0002.
For a unit outside the current network's ownership, the app first obtains an
unpair key through `fixture/unpair/v2`. The official recovery workflow coordinates
that operation with a power cycle or partner-switch action; **arbitrary power
cycling alone is not an established factory reset or offline unpair algorithm.**

Preserve and share the complete cache before resetting a controller, especially
for a network that was never shared. Losing the only working copy can strand the
fixtures. Partner hardware may have its own reset procedure, which must be checked
per model rather than guessed.

## GATT profile

| Characteristic | Role |
|----------------|------|
| `c9ffde48-ca5a-0001-ab83-8f519b482f77` | NodeInfo, ECDH/auth, encrypted invocations and state notifications |
| `c9ffde48-ca5a-0002-ab83-8f519b482f77` | Time sync, unpair, hardware configuration and diagnostics |
| `c9ffde48-ca5a-0003-ab83-8f519b482f77` | Advanced OTA transfer and block notifications |

The new UUID scheme has just those three characteristics. Evolution requests ATT
MTU 158 and normally writes without response, while respecting the negotiated
MTU and NodeInfo limit. No fixed characteristic command is exposed to the generic
mobile renderer: encryption, counters, targets and fixture context are mandatory.

## Evolution session

1. **Read NodeInfo** on 0001. It is exactly 23 bytes for this profile:

   | Offset | Type | Meaning |
   |---:|---|---|
   | 0 | `u8` | Type `0x01` |
   | 1 | `u8` | Raw version; mask with `0x1f` (for example `0x2b` means protocol 11) |
   | 2 | `u8` | Node MTU, 1–517 |
   | 3 | `u16be` | Unit id, at most 255 |
   | 5 | `u16be` | Flags; opaque here |
   | 7 | 16 bytes | CTR nonce base |

   Reject short/trailing data, unsupported masked versions, zero/oversized MTU
   and unit ids above 255 before continuing.

2. **Subscribe** on 0001 and receive `02 | pubX_LE[32] | pubY_LE[32]`.
   Validate the P-256 point, then generate a fresh client key pair and send the
   same public-key shape followed by capability `0x0d`. Bluetooth-gateway mode
   may append `0x01`. The pinned Python client uses `0x01` as the capability
   instead of app-corroborated `0x0d`; this discrepancy still needs capture.
3. Require the one-byte type-3 acknowledgement. Derive the transport key:
   take the 32-byte big-endian ECDH X coordinate, reverse it, SHA-256 it, then
   XOR the digest's two 16-byte halves.
4. Send type-4 authentication as encrypted packet counter 1:
   `04 | key_id | SHA-256(network_key || NodeInfo_nonce || transport_key)`.
5. Verify type-5's role and, for an accepted role, its digest:
   `SHA-256(network_key || client_pubX_LE || client_pubY_LE || transport_key)`.
   Only then send type-7 invocations, starting with counter 2.

The type-12 site-key/signature-auth path is not traced end to end and is not
implemented by this profile.

### Encrypted packet format

```text
counter:u32le | AES-128-CTR(payload) | AES-CMAC(transport_key, counter || ciphertext)[16]
```

- Outgoing nonce: `base[0:4] || counter_u32le || base[8:16]`.
- Incoming nonce: `counter_u32le || base[4:16]`.
- For each payload block starting at zero, write its block index little-endian
  at nonce offset 12, AES-encrypt the nonce and XOR it with up to 16 data bytes.
- Maintain independent incoming counter windows for notifications and decrypted
  reads. Accept only `0 < counter - last < 100`.
- Reject frames below 20 bytes, bad/replayed/out-of-window counters and every
  CMAC mismatch before parsing plaintext. Reset keys/counters on reconnect.

The independent vectors cover authentication, an outgoing invocation and an
incoming state packet in both nonce directions, plus tampering and replay.

## Type-7 invocations

A decrypted type-7 batch is `07` followed by complete invocation records. Each
record has a nine-byte big-endian base header, an optional origin-handle byte
and 0–63 payload bytes. Header bits 14:11 hold lifetime (default 5), bit 9 adds
the origin handle, and bits 5:0 hold payload length. Then come opcode, origin,
target and age. Validate every optional field and exact length; a trailing
fragment is malformed.

Targets are `0` for the whole network, `(id << 8) | 1` for a unit, `| 2` for a
group and `| 4` for a scene. For a bitmap target, the value is
`(payload_prefix_length << 8) | 11`; after the original opcode payload prefix,
append a base unit id and a little-endian bitmap. For unit `u >= base`, set bit
`(u-base) % 8` in bitmap byte `(u-base) // 8`.

| Opcode | Operation | Payload and units |
|---:|---|---|
| 1 | SetLevel | `u8` 0–255; percentage is raw × 100/255. Restore-last is `ff 05` |
| 3 | SetTemperature | `u8 = floor(K / 50)`, maximum 12750 K; also enforce fixture limits |
| 5 | SetWhite | `u8` white-channel amount, not Kelvin |
| 7 | SetColorHS | `u16le` hue 0–1023 (`raw × 360/1023` degrees), then `u8` saturation |
| 48 | SetState | Exactly the cached fixture's state length and bit layout; preserve unknown/read-only bits |
| 54 | SetColorXY | `u16le x`, `u16le y`; each is `round(normalized × 65535)` |

The spec includes fresh vectors for all six operations and a bitmap SetLevel to
units 16, 17 and 20. It also checks overlong payloads, truncated headers,
origin handles, state vectors and trailing data.

## Type-6 state and the fixture-cache requirement

Each unit record contains:

```text
unit_id | flags | state_info | [con] | [sid] | [level] | state_vector | padding
```

- Flags bit 0 is on, bit 1 online, bits 2/3/4 add `con`, `sid` and `level`;
  bits 7:6 count padding bytes. Missing level defaults to 255.
- `state_info >> 4` plus one is the state-vector byte length; its low nibble is
  priority.
- State vectors are little-endian bitstreams. The fixture—not a universal byte
  offset—defines each control. Extract `(raw >> offset) & ((1 << length) - 1)`.
- For an 18-bit Evolution RGB control, saturation occupies the low 8 bits and
  hue the high 10. A 22-bit XY control uses 11 bits per coordinate, normalized
  by 2047. Temperature uses the fixture's Kelvin min/max and control width.

Reject short headers, missing extras, short state/padding and trailing records.
If the fixture is missing, expired or has a different state length, retain only
raw bytes and refuse semantic decoding or SetState. Never clear unknown or
read-only controls during read-modify-write.

Public fixture 1 supplies a one-byte dimmer example. Evolution-only public
fixture 9000 supplies the eight-byte dimmer/HS/temperature/color-source/XY
example used by the tests; neither record contains private topology.

## Time, management and OTA

Time sync uses type 7 on characteristic 0002, normally every 120 minutes with a
15-minute floor. Its Evolution layout carries calendar fields, timezone offset
minutes, DST transition/change, signed 16.16 fixed-point latitude/longitude,
reserved microseconds and subsecond time. Do not put an owner's location into a
shared capture.

**OTA is advanced and untested.** Images use a `0xca5a0002` container with an
outer reflected CRC-32, version/device/board/flags/block count, typed blocks,
an add-on field and a 64-byte trailer. Validate every block and exact container
length before subscribing on 0003 and sending PREPARE. Each block replaces its
first word with little-endian CRC-32 of the remainder, then uses BEGIN, DATA,
COMMIT and indexed notifications; final APPLY is `05` without response.

The trailer is presumed to be a P-256 signature, but its algorithm, trust key
and node-side enforcement are unknown. CRC is not signature verification. The
update-mode advertisement, bad-CRC response and interrupted-update recovery are
also unknown. Match image generation, device, board, CPU, grade and variant;
never apply a partial image or assume Nordic DFU defaults. Evolution conversion
has no network-level rollback.

## Validation and omissions

`scripts/test_casambi_evolution_spec.py` uses PyYAML only to read the spec and
otherwise transcribes P-256, AES-128, CTR, CMAC, invocation and state algorithms
with the Python standard library. It checks fresh NodeInfo, both ECDH directions,
transport key, auth digest, outgoing/incoming encrypted packets, every declared
opcode/target, public-fixture state, tampering and malformed inputs. AES and CMAC
are also anchored to standard primitive vectors. No hardware or cloud operation
is performed.

Open work includes protocol 12, the key-exchange capability discrepancy,
type-12 signature auth, universal connection/flag semantics, foreign offline
unpair, physical reset, cache conversion and OTA trust/recovery.

## References

- [Pinned `casambi-bt` 0.3.2 Evolution client](https://github.com/lkempf/casambi-bt/tree/ec23769ab3459abf8ba5f332267900964319d03e)
- [Pinned protocol-10-only `esp32-casambi`](https://github.com/lian/esp32-casambi/tree/2903401ee7bd61ec4c3c697e29178c5d4b1683a2)
- [Vendor Classic versus Evolution article](https://support.casambi.com/support/solutions/articles/12000068796-what-is-classic-and-evolution-)
- [Operation and maintenance manual](https://support.casambi.com/helpdesk/attachments/12159158129), HTTP 200 verified 2026-11-18
- [CBU-DCS DALI Gateway datasheet](https://f.hubspotusercontent40.net/hubfs/7177595/Data%20sheets/English/CBU_DCS_Data-Sheet_EU_EN_2_0_24092021.pdf), HTTP 200 verified 2026-11-18
- [Official paired-device troubleshooting](https://support.casambi.com/support/solutions/articles/12000096173-troubleshooting-paired-devices)
- [Public fixture 9000 control definition](https://api.casambi.com/fixture/9000), HTTP 200 verified 2026-11-18
