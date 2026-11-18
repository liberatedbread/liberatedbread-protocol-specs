# Spotify Car Thing with Bridgething

> **Status**: Spec Available, untested
> **Protocol**: Bluetooth Classic RFCOMM, iAP2, WebSocket
> **Integration**: Identify-only until a bespoke typed-envelope consumer exists
> **Manufacturer**: Spotify hardware; Bridgething replacement daemon
> **Manufacturer Status**: Stock service ended; custom firmware required

## Overview

This guide applies **only to a Car Thing already running the Bridgething custom
firmware/daemon**. It does not describe a control protocol present in Spotify's
stock firmware, and finding a stock Car Thing does not establish compatibility.
Install the daemon using the [Bridgething project](https://github.com/JoeyEamigh/bridgething)
before following the protocol material here. Installation and firmware images
are outside this document's scope.

The machine-readable spec is
[`spotify-car-thing-bridgething.yaml`](https://github.com/liberatedbread/liberatedbread-protocol-specs/blob/main/device-specs/devices/spotify-car-thing-bridgething.yaml).
It carries the directional catalogue of 122 typed commands, the request
catalogue, payload field signatures, and upstream golden frames. All facts are
reported from the published replacement project; nothing was replayed against
hardware for this guide.

## Initial setup, pairing, and rebinding

1. Install Bridgething with the upstream release and installation guide. Keep
   any owner data that guide says to preserve.
2. Pair the daemon from the host's Bluetooth settings. The source establishes a
   paired RFCOMM peer but does not document the physical discoverability action
   or its window.
3. Open RFCOMM channel 1 for custom service
   `dead0000-854d-408e-81f0-fb6147f918fd`. One paired gateway peer is allowed
   per connection.
4. Exchange DEAD v2 frames as described below.

A new gateway is a Bluetooth rebinding operation, not Wi-Fi provisioning. Close
the current gateway and use the daemon's connection UI plus host-side forget
and pair controls. Bond limits and whether a daemon-side operation can revoke a
single bond are unknown. A factory reset is not the prescribed fix.

**Factory reset:** unknown. A typed `system.factoryReset` request exists, but
its physical entry and full erase scope are not established. Do not send it as
a setup shortcut or infer that it reinstalls firmware.

**Credentials:** no application token is defined for RFCOMM. The host manages
any Bluetooth link keys. No Wi-Fi passphrase is used by this spec.

## iPhone and iPad: iAP2, not CoreBluetooth

CoreBluetooth has no RFCOMM API, so it cannot open the control channel. The
replacement daemon provides an alternative iAP2 ExternalAccessory channel with:

| Property | Value |
|---|---|
| EA protocol id | `1` |
| Protocol name | `com.bridgething.gateway` |
| Payload | The same DEAD v2 stream, after the iAP2 link is up |

An iOS client must declare that protocol string and use ExternalAccessory. This
is custom-daemon behavior, not a claim about the stock Spotify accessory.

## Transport boundaries

| Surface | Address | Wire format |
|---|---|---|
| Gateway over RFCOMM | Custom UUID above, channel 1 | DEAD v2 frames in an arbitrary byte stream |
| Gateway over iAP2 | Protocol above | The same DEAD v2 byte stream |
| Network gateway | `ws://<address>:8892/` | Binary WebSocket messages containing only complete DEAD v2 frames |
| Modern local webapp | `ws://<address>:8891/` | One unframed JSON (text) or MessagePack (binary) envelope per message |
| Stock webapp translation | `ws://<address>:8890/` | Stock string methods and untyped JSON translated by the custom daemon |

Ports 8891 and 8892 are different APIs, not alternate addresses for one API.
Port 8890 is a compatibility boundary, not the modern gateway and not proof
that the custom daemon is optional. A network gateway message may contain
several complete frames but no partial trailing frame; the daemon closes the
connection on a partial frame. Its message limit is 1 MiB.

**Network exposure is unresolved.** The sources do not establish bind addresses,
authentication, authorization, TLS, or WebSocket-origin checks for ports
8890-8892. Keep them on a trusted network and do not expose them publicly.

## DEAD v2 framing

RFCOMM and iAP2 reads can split one frame or coalesce several. Buffer until the
declared payload is complete.

| Offset | Size | Meaning |
|---:|---:|---|
| 0 | 2 | Magic `de ad` |
| 2 | 1 | Version `02` |
| 3 | 1 | Compression: `00` none, `01` gzip |
| 4 | 1 | Encoding: `00` MessagePack named maps, `01` JSON |
| 5 | 1 | Priority: `00` normal, `01` bulk, `02` background; unknown decodes as normal |
| 6 | 2 | Reserved: zero on encode, ignored on decode |
| 8 | 8 | Unsigned big-endian payload length **after compression** |
| 16 | N | One typed envelope |

The frame payload limit is 16 MiB, including after gzip expansion. On bad
magic, an unknown version, or an over-limit declared length, scan forward to
the next `de ad`; preserve a trailing `de` across reads so split magic is not
lost. A bad body is a failed item, not a new length to guess.

Normal-lane payloads larger than 16,256 bytes are gzipped once, but only kept
if smaller. Bulk and background traffic does not automatically gzip. Receivers
must still accept gzip on every lane. The writer drains normal, then bulk,
then background traffic. The daemon fragments transfers at 4 KiB and caps an
in-memory transfer at 256 KiB.

## Envelopes, correlation, and errors

Every message has a fresh UUID, `meta.kind`, and typed `data`:

```json
{
  "id": "01924f2b-1f7e-7c1a-9f3a-6b2d9e5a4c18",
  "meta": { "kind": "request" },
  "data": {
    "type": "library",
    "data": {
      "event": "browse",
      "data": { "nodeId": null, "limit": 14, "offset": 0 }
    }
  }
}
```

MessagePack uses named maps. Every upstream UUID-typed field serializes as 16
raw binary bytes, never as a UTF-8 string; JSON uses a lowercase hyphenated UUID
string. This applies recursively to `id`, `requestId`, `transferId`, `webapp`,
`connectionId`, `streamId`, `tunnelId`, `launcher`, and `overlay`, including TTS,
WebSocket, stream, tunnel, and webapp-slot payloads. Asset `id` fields are the
exception: they are `String` and remain MessagePack strings even when their value
is a canonical UUID. Sibling `requestId` and `TransferRef.id` fields remain
16-byte binary. The containing payload type and field path decide which
representation applies.

The outer `type` selects a surface and the inner `event` selects its variant;
`meta.kind` must be legal for that variant. These are typed envelopes, not
arbitrary JSON method calls.

A response gets a fresh `id` and puts the request's UUID in
`meta.data.requestId`. Answer every request exactly once. Successful commands
normally have no response. The daemon request timeout is 60 seconds and the SDK
timeout is 30 seconds.

`data.type=error` carries a `WireError`: `unsupported`, `unimplemented`,
`malformed` with a reason, or `handlerFailed` with a reason. A predictable
request failure can instead use its own domain-error reply variant. A failed
webapp command can therefore produce an otherwise unmatched error response;
do not mistake that for request success.

Large values use `TransferBody`: inline bytes or a `TransferRef`. Stream bytes
arrive as `transfer.fragment` events with `transferId`, `offset`, and `bytes`.
Require ascending offsets without gaps, overlap, or bytes beyond `totalSize`,
and honor `transfer.abandon`.

## Typed operations and stock translation

The spec's `protocol_details.typed_command_catalogue` lists each command by
**direction, surface, event, and payload type**. This matters because the same
spelling can be a command in one direction and a response or event in another.
The request catalogue separately records request and response types. Advanced
firmware, uninstall, reboot, power-off, and factory-reset operations are marked
rather than presented as routine media controls.

The stock webapp needs a gateway that answers `library.browse`,
`library.resolveContext`, and `asset.request`, and pushes `player.snapshot` and
`player.queueChanged`. The custom daemon translates those modern operations to
the stock interface on port 8890. A modern client should use the typed gateway
or webapp surface instead of reimplementing that legacy JSON dialect.

## Verification and remaining unknowns

`scripts/test_bridgething_spec.py` uses an independent standard-library
MessagePack/DEAD codec and the spec's upstream golden fixtures. It checks exact
re-encoding, split/coalesced reads, resynchronization, frame/network/gzip caps,
compression decisions, UUID correlation, typed errors, and transfer-fragment
ordering. These are host-side source checks, not hardware verification.

Still unresolved: physical installation/reset scope, pairing UI and bond
limits, network listener access control, and deeply nested payload enums beyond
the version-pinned named types transcribed in the spec. Use the matching
Bridgething generated bindings before extending those operations.

## References

- [Bridgething replacement project](https://github.com/JoeyEamigh/bridgething)
- [Wire protocol](https://github.com/JoeyEamigh/bridgething/blob/3f313b655ebd0aea74d194c1349a56a1c13490be/docs/protocol.md)
- [Golden frames](https://github.com/JoeyEamigh/bridgething/blob/3f313b655ebd0aea74d194c1349a56a1c13490be/crates/lib/fixtures/golden.json)
- [Stock webapp contract](https://github.com/JoeyEamigh/bridgething/blob/3f313b655ebd0aea74d194c1349a56a1c13490be/docs/stock-webapp-gateway-contract.md)
