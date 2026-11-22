# Withings Body / Nokia Body WBS06 — incoming Bluetooth Classic

> **Status**: Spec Available (untested here; identify-only consumer integration)
> **Protocol**: Incoming Bluetooth Classic BR/EDR RFCOMM, FragFsm and WPP
> **Manufacturer**: Withings (earlier units branded Nokia)
> **Manufacturer Status**: Active

## Overview

WBS06 does not synchronize measurements through the WBS12/WBS13 BLE GATT
profiles. In Bluetooth mode, after a weigh-in, **the scale initiates a
Bluetooth Classic connection to a companion listener**. The host must already
be paired, registered and waiting. A generic outbound SPP client is the wrong
architecture.

The required host is Linux with BlueZ and a local BR/EDR-capable adapter.
CoreBluetooth has no RFCOMM server transport, and an ESPHome BLE proxy cannot
provide Classic pairing or an incoming BlueZ profile. Failure to register the
listener is an explicit setup failure, never a reason to pretend a BLE
fallback exists.

Only these values are published:

- weight (measurement type 1, exponent-scaled kilograms);
- UTC weigh-in time;
- scale battery percentage, plus host-side last successful sync time.

WBS06 does not provide body-composition measurements in this integration.
No fat/muscle/water/bone/heart-rate or other composition sensor should be
created from an unknown type. `SYNC_OK` is never sent or echoed.

The stock local session does not delete measurements or write association,
roster/user, unit, Wi-Fi, clock, setup or firmware state. WBS06 v551 and
WBS05S firmware-patch claims, YourOwnWeigh replacement services and OTA are
all outside this spec.

## Hardware and host requirements

| Property | Value |
|----------|-------|
| Model | WBS06, Withings Body / Nokia Body |
| Measurement radio | Bluetooth Classic BR/EDR, scale-initiated |
| Host | Linux + BlueZ + local BR/EDR adapter |
| Credentials | Existing 32-character `kl`, Classic Just Works bond, configured scale address |
| Incompatible | CoreBluetooth/iOS/iPadOS; ESPHome BLE proxy; BLE-only adapters |
| Manual | [Exact WBS06 guide at manuals.plus](https://manuals.plus/withings/withings-wbs06-digital-wi-fi-smart-scale-user-manual) |

The manual link returned HTTP 403 browser blocking when checked on
2026-11-18. Repository policy distinguishes that response from a dead link.
The manual is not evidence for the Classic protocol bytes.

## Initial setup and pairing

Use the vendor app's Wi-Fi configuration flow to select Bluetooth/no-Wi-Fi
mode; this spec sends no Wi-Fi command. Supply the existing 32-character
association key (`kl`) through a secret store. If necessary, retrieve that
existing key once from the owner's account with the public integration's
helper, refusing ambiguous accounts containing several WBS06 scales. Daily
reads need no cloud connection.

Start Classic pairing on the BlueZ host, then hold the scale's underside
button for about three seconds and keep it in setup mode until Just Works
pairing finishes. No PIN is required. Do not initiate pairing automatically
when a measurement socket arrives.

BlueZ should retain a Classic BR/EDR bond and trust. The scale can display
“Setup failed” despite a valid bond and a later authenticated weigh-in. Use
the host bond and verified WPP session as the result, not that display alone.

**Factory reset:** the on-scale Reset menu wipes setup and is not a pairing
repair. Preserve association data first. `kl`/bond restoration is required,
and stored-record retention is unknown. This procedure is reported, not run
by this project.

**Rebinding:** a replacement listener needs the same `kl`, a fresh Classic
bond and both SDP registrations. Battery loss can require re-pairing/key
restoration. Reset is not required simply to move hosts.

## BlueZ listener lifecycle

Register both service UUIDs as native BlueZ `Profile1` server profiles:

- `00000001-e1ba-dfb7-c7f0-da2b149de289`
- `00009990-0000-1000-8000-00805f9b34fb`

These are **host services**, not evidence that the scale accepts an outgoing
host connection to the same UUIDs. Register each through
`org.bluez.ProfileManager1` with server role and channel 0 so BlueZ allocates
and publishes an RFCOMM channel. The public implementation sets
`RequireAuthentication=false` and `RequireAuthorization=false`; the earlier
Classic bond and subsequent WPP proof remain mandatory.

One profile pair is shared by configured WBS06 scales. For each accepted
D-Bus file descriptor:

1. validate the BlueZ device path and route by the configured Classic
   address;
2. reject an unknown address or a second simultaneous socket for the same
   scale;
3. take ownership of the descriptor and process only that socket;
4. re-register profiles after BlueZ restart or `Release`, with bounded retry;
5. close sockets and unregister profiles during shutdown, without changing
   system-wide SDP configuration.

There is no safe passive discovery matcher in this spec. A generic Body name,
SPP UUID or Withings OUI is not identity. Application-level WPP verification
is required even for the expected address and an existing bond.

## FragFsm framing

The stream starts with the scale's two-byte RESET:

```text
01 00
```

The public client allows ten seconds for RESET and then settles for 0.5
seconds before WPP. It logs and continues if RESET is absent; a stricter
client may fail closed. Either way, the socket alone never authorizes reads.

Each DATA frame wraps one complete WPP message:

```text
01 01 | wpp_length:u16be | WPP bytes
```

Length is 1–65535 and excludes the four-byte FragFsm header. Host writes use
the same wrapper. There is no checksum.

RFCOMM reads are arbitrary fragments. Maintain one persistent buffer and
handle split RESET, split headers/payloads and multiple frames in one read.
Reject an unknown version/operation, zero DATA length or malformed WPP. Do
not scan for another `01` inside measurement bytes; close and reconnect on
framing errors.

## WPP and mutual authentication

WPP itself is:

```text
01 | command:u16be | payload_length:u16be | TLV...
TLV = type:u16be | length:u16be | value
```

Variable strings/byte arrays inside a TLV carry a one-byte length prefix.
Use exact bounds and reassemble multiple WPP messages by the declared length.
Bit `0x4000` marks device-initiated requests. A stored-record list ends with
TLV 256 and zero length.

Send PROBE with `{os=1, app=1, version=8050004}` and OS-version field 34.
Normal mode returns a 16-byte challenge and advertised MAC string. Preserve
the MAC string exactly, including case and separators. The association key is
exactly 32 ASCII characters. For each challenge:

```text
SHA1(challenge || exact_MAC_string_ASCII || kl_ASCII)
```

Answer the scale's challenge and send a fresh independent 16-byte client
challenge in command 296. The response carries object 291 (length 20 plus the
raw answer) and object 290 (length-prefixed exact MAC string and client
challenge). Require the scale's 20-byte answer to the client challenge and
compare in constant time. The public WBS06 flow uses a 15-second
authentication timeout.

A setup-mode PROBE reply without a challenge is not an authenticated session.
On any missing/wrong proof, issue no battery or stored-measurement read and
no `SYNC_OK`.

## Read-only measurement session

After both proofs verify:

1. Request battery with command 261. Object 263 is big-endian uint16 percent;
   retain the last valid value on failure rather than displaying zero.
2. Request connection reason with command 273. Object 280 is big-endian
   uint16: 1 button, 2 weigh-in.
3. Request stored state with command 271 and object 276 `{action=0, rc=0}`.
   Object 277 is `{count:int16be, oldest_time:int32be,
   wifi_configured:int8be}`.
4. If records exist, request all with `action=1` and collect through NULL
   TLV 256. `action=2` deletes and is prohibited.
5. Do not send `SYNC_OK`. Send `DISCONNECT` (272) without waiting for an
   answer and close the accepted socket.

Last successful sync advances after every verified session, including one
without new measurements.

Metadata object 278 is `uid:u32be`, `valid:u8`, `slot_count:u8`, that many
big-endian user IDs, `attrib:u8`, and `time:u32be`. Only the first `valid`
IDs matter. `time` is UTC Unix seconds. Invalid metadata drops its following
values rather than misattributing them to the previous group.

Data object 279 is exactly eight bytes: `value:int32be | type:u16be |
exponent:int16be`. Decode with decimal arithmetic as
`value × 10^exponent`; `72345e-3 = 72.345 kg`. Preserve groups by
`(time, attributed_user)` and deduplicate measurement types within each group.
The attributed user is the first nonzero valid user ID or `0` for guest/
unknown; `uid` is not required as a stable identity key. Across whole-store
rereads, suppress samples by `(attributed_user, time, measurement type)`, so
Bob 90 kg, guest 55 kg and another user 65 kg at one timestamp all survive.

Only type 1 becomes a WBS06 weight value. The synthetic fat-ratio vector in
the machine spec proves generic exponent parsing, **not** WBS06 composition
support.

## Verification and exclusions

The source is withings-local v0.5.0 at
`52cfaa1f9157972373d34ce3021dbcd481c2f907`, including its native RFCOMM
listener, WPP codec/auth/measures and WBS06 guide. Upstream reports one real
scale completing fresh Classic pairing, RFCOMM, FragFsm, mutual WPP
authentication and weight/battery delivery. That result is reported here; no
scale or owner data was used for this spec.

`scripts/test_withings_local_protocols.py` independently reproduces SHA-1,
authentication and WPP vectors, exact-MAC handling, exponent/deduplication
and fragmented/coalesced FragFsm frames with synthetic values only. Its
same-timestamp regression preserves Bob, guest and Alice with attribution,
then suppresses only identical per-user/time/type records on reread.

Open questions are the stock firmware matrix (upstream did not state a
version for its successful scale), RESET optionality, reset retention and
battery-loss behavior. No WBS06 v551/WBS05S patch, YourOwnWeigh replacement
service, BLE composition path or other-model compatibility is claimed.

## References

- [withings-local WBS06 guide at the pinned revision](https://github.com/pierosavi/withings-local/blob/52cfaa1f9157972373d34ce3021dbcd481c2f907/docs/wbs06.md)
- [Native BlueZ RFCOMM listener](https://github.com/pierosavi/withings-local/blob/52cfaa1f9157972373d34ce3021dbcd481c2f907/custom_components/withings_local/rfcomm.py)
- [Shared WPP implementation](https://github.com/pierosavi/withings-local/tree/52cfaa1f9157972373d34ce3021dbcd481c2f907/src/withings_wpp)
- [WBS12/WBS13 BLE guide](withings-body-smart-comp-ble.md), a different transport
- Machine-readable listener and vectors: `device-specs/devices/withings-body-wbs06-classic.yaml`
