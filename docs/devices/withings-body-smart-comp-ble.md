# Withings Body Smart WBS13 and Body Comp WBS12 — local BLE

> **Status**: Spec Available (untested here; identify-only consumer integration)
> **Protocol**: BLE GATT, Withings WPP with mutual SHA-1 authentication
> **Manufacturer**: Withings
> **Manufacturer Status**: Active

## Overview

Two model profiles share a read-only measurement protocol, but their
advertising, GATT endpoints and completion behavior are different:

| Property | Body Smart WBS13 | Body Comp WBS12 |
|----------|------------------|-----------------|
| WPP model | `0x10` | `0x12` |
| Discovery | WITH service and/or Body Smart name | FD77 service data and Body Comp name |
| GATT service | `00000020-5749-5448-0010-000000000000` | `00000000-0000-5749-5448-494e47530000` |
| WPP characteristic | `00000024-5749-5448-0010-000000000000` | `00000004-0000-5749-5448-494e47530000` |
| `SYNC_OK` | Send after a complete read; echo device requests | **Never send or echo** |
| Evidence | Author's scale, firmware 1311 | One community scale, firmware 1311/bootloader 2 |

The newer WITHINGS service is shared with other products and is not a WBS12
identity filter. Do not probe WBS13 endpoints on WBS12 or vice versa. Other
scales and watches are outside this spec; WBS06 uses its own incoming
Bluetooth Classic transport.

Once the owner has supplied an existing 32-character association key (`kl`),
stored measurements can be read locally without a cloud round trip. The spec
never deletes records and declares no association, roster/user, unit, Wi-Fi,
clock, setup or firmware writes. A separate phone app can still reach and
clear the scale first; this spec does not control that behavior.

## Hardware and manuals

| Property | Value |
|----------|-------|
| Models | Body Smart WBS13 and Body Comp WBS12 only |
| Radio | BLE; scale also has separately managed Wi-Fi |
| Category | `scale` / body composition |
| Credentials | Existing 32-character `kl`, six-digit BLE pairing bond |
| Body Smart/Comp joint manual | [100-page FCC exhibit](https://fccid.co/api/files/s1/xnawbs13_usersmanual_6451828_a55b101ab1.pdf) |
| Body Smart vendor guide | [Withings-hosted PDF](https://media.withings.com/kits/guides/2023/body-smart/AW_IFU_WBS13_ALL_INT_K_.pdf) |

Both PDF links returned HTTP 200 with `application/pdf` on 2026-11-18.
Manuals explain owner setup, not WPP bytes.

## Initial setup

| Property | Value |
|----------|-------|
| Setup required | Existing association key, Bluetooth mode and model-specific pairing |
| Primary method | `ble_direct` with an already exported `kl` |
| Alternative | One-time owner-account `kl` retrieval; no per-reading cloud dependency |
| Wi-Fi credentials sent by this spec | None |
| Setup confidence | High (working public implementation); not replayed here |

Use the vendor app's Wi-Fi configuration flow to select Bluetooth/no-Wi-Fi
mode. This spec never sends that command itself. An idle scale in Wi-Fi mode
need not advertise after a weigh-in, so Bluetooth mode is the documented
route. Coexistence of paired BLE and Wi-Fi operation across firmware remains
unresolved.

Supply `kl` through a secret store. It is 32 ASCII characters and is not the
factory/session secret in a probe reply or TLS private-key material. If no
export exists, the public integration can retrieve the owner's existing
association key once through their account. This does not provision a reset
scale, create a roster or generate a new association.

Pair as follows:

- **WBS13:** hold the underside button for about three seconds and enter the
  six-digit code shown on the scale; roughly 30 seconds is reported.
- **WBS12:** briefly press the underside button and enter the six-digit code
  using a host agent capable of keyboard/display pairing. Subscribing before
  pairing can hang.

The scale can subsequently display “Setup failed” even when the host stored a
valid bond. Verify the bond and an authenticated measurement session rather
than treating that display alone as the result.

**Factory reset:** the on-scale menu's Reset entry wipes setup. Use it only
when setup loss is intended; it is not a pairing repair. Preserve association
data first. Bond/`kl` restoration will be needed, and stored-record retention
is unknown. The procedure is reported from the public guide, not run here.

**Rebinding:** preserve `kl`, pair the new local host and leave other readers
disconnected. Battery loss can require re-pairing/key restoration. Reset is
not needed merely to change readers.

## Pairing versus authentication

BLE bonding and WPP authentication are separate. A stored bond or successful
GATT subscribe/write does not prove that either peer knows `kl`. A setup-mode
probe reply without a challenge is not an authenticated normal-mode session;
do not read stored measurements in that state.

The WPP message grammar is:

```text
message = 01 | command:u16be | payload_length:u16be | TLV...
TLV     = type:u16be | length:u16be | value
```

Variable strings and byte arrays inside a TLV have a one-byte length prefix.
Notifications are fragments, not message boundaries: buffer using the WPP
length, reject malformed/trailing data and handle back-to-back messages.
Command bit `0x4000` marks a device-initiated request. A multi-message list
ends with TLV type 256 and zero length.

### Mutual SHA-1 exchange

Normal mode answers PROBE with a 16-byte challenge and an advertised MAC
string. Preserve that string **exactly**, including case and separators; never
normalize it. For either side's challenge:

```text
answer = SHA1(challenge_bytes || exact_MAC_string_ASCII || kl_ASCII)
```

The client answers the scale's challenge and includes its own fresh,
independent 16-byte challenge. The response uses command 296 with:

1. object 291: one-byte length 20 followed by the raw client SHA-1 answer;
2. object 290: length-prefixed exact MAC string and length-prefixed client
   challenge.

The scale replies with its own 20-byte proof. Compare it in constant time to
the expected answer for the client challenge. If either side's proof is
missing, malformed or wrong, send no battery or stored-measurement request
and no `SYNC_OK`.

## Read-only session

After strict mutual verification:

1. **Battery:** command 261, empty payload. Object 263 is a big-endian uint16
   percentage. A failed read retains the last valid value, never zero.
2. **Connection reason:** command 273. Object 280 is big-endian uint16:
   1 button, 2 weigh-in.
3. **Stored state:** command 271 with object 276 `{action=0, rc=0}`. Object
   277 is `{count:int16be, oldest_time:int32be, wifi_configured:int8be}`.
4. **All records:** if count is positive, repeat with `action=1` and collect
   through the NULL TLV. `action=2` is destructive and prohibited.
5. **Completion:** WBS13 sends `SYNC_OK` (277) after a successful complete
   read and echoes a device-initiated one. WBS12 does neither. Finish with
   `DISCONNECT` (272), not a settings write.

Errors use object 272 `{command:u16be, error:int32be}`. Surface busy (-2),
unsupported (-3), rejected (-4), unauthenticated (-5), invalid arguments (-8)
and arguments not set (-9); do not blindly retry.

### Stored measurements

Metadata object 278 contains:

```text
uid:u32be | valid:u8 | slot_count:u8 |
user_ids[slot_count]:u32be each | attrib:u8 | time:u32be
```

`time` is UTC Unix seconds and applies to following data. Only the first
`valid` user IDs are meaningful; later slots can contain junk. A malformed
metadata record invalidates its following values rather than attaching them
to the previous person/group.

Data object 279 is exactly eight bytes:

```text
value:int32be | type:u16be | exponent:int16be
```

Decode with decimal arithmetic as `value × 10^exponent`, preserving the raw
triple. The required synthetic example is `72345e-3 = 72.345 kg` for weight;
`215e-1 = 21.5%` for fat ratio.

Every sync returns the whole store and one weigh-in can be split across
groups. First preserve groups by **`(time, attributed_user)`**, where the
attributed user is the first nonzero valid user ID or `0` for guest/unknown.
Deduplicate measurement types **within each group**, retaining `user_ids` and
`attrib` for attribution; `uid` is not required as a stable identity key.

Across syncs, suppress already published samples by
**`(attributed_user, time, measurement type)`**. This prevents whole-store
rereads from becoming new history without collapsing different people. For
example, invented Bob at 90 kg, guest at 55 kg and Alice at 65 kg at one
timestamp all survive with their attribution. Guest/unknown `0` is distinct
from every named user at that timestamp.

| Type | Measurement | Unit |
|------|-------------|------|
| 1 | Weight | kg |
| 5 | Fat-free mass | kg |
| 6 | Fat ratio | % |
| 8 | Fat mass | kg |
| 11 | Heart rate | bpm |
| 76 | Muscle mass | kg |
| 77 | Body water mass | kg |
| 88 | Bone mass | kg |
| 170 | Visceral fat | dimensionless index |
| 226 | Basal metabolic rate | kcal (upstream spelling) |
| 227 | Metabolic age | years |

Unknown types retain raw value/type/exponent with no guessed unit. WBS12's
reported 177, 178, 189, 201–203 and 207, and TLV 2451, remain undecoded.

## Advertising details

WBS13's WITH UUID grammar is
`000000SS-5749-5448-MMMM-<12 hex>`; `MMMM=0010` selects this model.

WBS12 uses FD77 service data. Its first big-endian uint16 has version in the
high nibble and model in the low 12 bits. Following TLV header bytes pack type
in the high nibble and length in the low nibble. Type 1 is a flags byte:
bit 0 installed, bit 1 sync requested, bit 2 wake-up. Connect for measurement
sync when installed and sync requested are both set. Type 2 setup addresses
and type 3 identity hashes must not be published.

## Verification and limits

The source is withings-local v0.5.0 at
`52cfaa1f9157972373d34ce3021dbcd481c2f907`, including its WPP codec,
authentication, measurement and device-profile code and documentation. This
project did not contact hardware or use real credentials, addresses or health
data.

`scripts/test_withings_local_protocols.py` independently checks SHA-1 and
mutual-proof layouts, exact-MAC behavior, WPP bounds/fragmentation, exponent
scaling, per-user/time/type deduplication, model routing and FragFsm. Its
regression preserves Bob, guest and Alice at one timestamp and suppresses only
their identical records on a reread. Fixtures use a placeholder MAC, invented
key/challenges and invented measurements.

Remaining work includes more WBS12 units/firmware, unknown type meanings,
reset retention, battery-loss pairing and clarification of Wi-Fi/BLE
coexistence. No local association/roster replacement is claimed.

## References

- [withings-local protocol notes at the pinned revision](https://github.com/pierosavi/withings-local/blob/52cfaa1f9157972373d34ce3021dbcd481c2f907/docs/protocol.md)
- [withings-local read-only WPP implementation](https://github.com/pierosavi/withings-local/tree/52cfaa1f9157972373d34ce3021dbcd481c2f907/src/withings_wpp)
- Machine-readable profiles and vectors: `device-specs/devices/withings-body-smart-comp-ble.yaml`
- [WBS06 Classic guide](withings-body-wbs06-classic.md), a different transport
