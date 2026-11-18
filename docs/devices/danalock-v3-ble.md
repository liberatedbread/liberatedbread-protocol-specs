# Danalock V3 (DMI BLE)

> **Status**: Identify-only spec; untested here
> **Protocol**: BLE GATT, DMI framed reliable stream, TLS 1.2 and AFI
> **Manufacturer**: Danalock / Salto Home Solution ApS (formerly Poly-Control)
> **Manufacturer Status**: Active

## Overview

Danalock V3 supports direct local BLE, but not as a plaintext UART and not
without credentials. Its DMI protocol layers escaped frames, a window-one
reliable transport, TLS 1.2, and AFI commands. A cached, unexpired AFI login
token can operate offline. Passive encrypted advertisements use a **separate**
broadcast key.

This catalogue entry is `identify_only`: no generic entity, no plaintext
command, no insecure TLS mode, and no automatic actuation. A dedicated client
must implement the complete transport and certificate checks. `LockOperate` is
documentary for an **advanced, attended** operation only.

The public implementation author reports live verification on **BTZE only**.
Compatibility with BT, BTZB/BTZBE and dual-mode BTHK is not independently
verified. The Z-Wave, Zigbee and HomeKit routes below are alternatives for
owners, not claims that every variant speaks this DMI profile.

## Hardware and variants

| Variant | Local continuity route |
|---------|------------------------|
| BT | Cached unexpired DMI login token; no standard-hub fallback established |
| BTZE / BTZU | Z-Wave + BLE. BTZE is EU and the community-verified DMI variant; BTZU is US. Z-Wave JS is an independent local route. |
| BTZB / BTZBE | Zigbee + BLE. Zigbee2MQTT supports V3-BTZB/V3-BTZBE locally; DMI compatibility is unverified here. |
| BTHK dual-mode | Preserve HomeKit pairing material and use local HomeKit. Firmware 2.7.5 adds account-based DMI, not proof of community-client compatibility. |

The lock itself has no Wi-Fi. Danabridge is needed only for out-of-range vendor
cloud relay, not for an in-range direct BLE session.

## Initial Setup and credentials

| Property | Value |
|----------|-------|
| Setup required | Yes — cloud-signed enrollment or owner-authorized grant export |
| Later offline use | Cached unexpired AFI login token; separate broadcast key for passive state |
| Pairing mode | Application-layer enrollment, not general local PIN pairing |
| Passphrase protection | Not applicable; no lock Wi-Fi |
| Confidence | Medium — public implementation and official docs, not run here |

A replacement client needs:

- six-byte DMI lock serial and a local six-byte controller DMI address;
- the opaque **AFI login token**, with `valid_from`, `valid_to` and permissions;
- the separate 16-byte **broadcast key** only if passive advertisement decode is
  wanted;
- the public DMI trust anchor for full server-certificate validation.

Keep real tokens, broadcast keys, serials and owner certificates out of logs and
shared fixtures. An AFI grant is time/permission-limited bearer authority, not
the CA or permanent ownership. One integration's 12-hour refresh schedule is
not evidence of a 12-hour token TTL; default/max lifetime, rotation and
predecessor revocation remain unknown.

Normal enrollment is cloud-signed. There is no established local self-keying
route and no replacement service that can mint lock-accepted tokens without an
authority the lock already trusts. App-less Danapad pairing is different: it
deletes existing PINs and prevents later addition to the Danalock app.

### Factory reset

The official click-command guide assigns **ten pinhole-button clicks** to factory
reset. It deletes all user settings and is not a way to obtain an independent
login token. Re-enrollment still needs the vendor signing service or a supported
radio-specific controller. Check dual-radio pairing/calibration effects before
resetting. This procedure is official-source-backed but was not run here.

### Rejoining

A client with an accepted unexpired token reconnects without cloud access. Start
a fresh RPD/TLS session, validate the certificate, repeat AFI login and use
read-only requests first. Expiry or rejection needs a fresh owner-authorized
grant, not insecure mode or a reset workaround.

Z-Wave and Zigbee moves use their own exclude/include processes. For BTZE/BTZU,
enroll in the app first if BLE is also wanted; hub-first disables BLE. HomeKit
needs the preserved pairing code and accounts for single-controller pairing.

## Discovery and advertisements

DMI manufacturer data uses company ID **456 / `0x01C8`** (`C8 01` in the AD
structure). It identifies the broader DMI family, including devices that are not
this lock. Do not auto-activate lock control from it, from the DMI UART service,
or from an encrypted broadcast. Manually select the exact model/radio variant.

A normal manufacturer payload is 24 bytes:

| Offset | Size | Meaning |
|--------|------|---------|
| 0 | 1 | Version `2` = DMI state; `3` = DFU, no ordinary controls |
| 1 | 6 | DMI serial — authoritative identity, not the rotating BLE address |
| 7 | 1 | Reserved |
| 8 | 16 | AES-128-CBC status, zero IV, using the broadcast key |

The decrypted 16-byte block starts with CRC-16/CCITT-FALSE over bytes 2–15,
stored little-endian. Then come a little-endian update counter and device flags,
a raw battery byte, and little-endian lock flags. Lock bit 0 means locked; other
bits cover calibration, blocked, brake-and-go-back, auto-lock and twist assist.
Battery scaling is device-defined: do not label the raw byte a percentage. CBC
has no authentication tag; the inner CRC detects corruption but is not a
cryptographic authenticity boundary.

The login token plays no role in this decryption, and the broadcast key plays no
role in AFI login.

## Protocol Summary

### GATT

| UUID | Role |
|------|------|
| `bce90001-c6eb-4ff8-bb6b-91cf6443c685` | DMI service |
| `bce90002-c6eb-4ff8-bb6b-91cf6443c685` | Framed writes, without response |
| `bce90003-c6eb-4ff8-bb6b-91cf6443c685` | Framed notifications |

Split writes into at most 20-byte chunks; no larger MTU is required. Notification
boundaries are arbitrary and must be reassembled before parsing.

### DMI frame and escaping

Wire form is `C0 <escaped logical frame> C1`:

- `C0 → C2 40`
- `C1 → C2 41`
- `C2 → C2 42`

The public decoder tolerantly maps escaped `C2 B` to `B | 0x80` and preserves a
trailing lone `C2`; canonical writers emit only the three pairs above.

The logical frame is:

```text
00 F1 | destination[6] | source[6] | type | ports | seq_ack | payload | crc[2]
```

Types are data/empty ACK `0`, SYN `1` and FIN `2`. The ports byte packs receiver
in the high nibble and sender in the low nibble. The lock uses port 2; the client
chooses a random four-bit port. `seq_ack` packs sender sequence low and next
expected peer sequence high, both modulo 16.

CRC is **CRC-16/CCITT-FALSE**: polynomial `0x1021`, initial `0xFFFF`, not
reflected, no final XOR, stored **little-endian** over every logical byte before
the CRC. ASCII `123456789` gives `0x29B1`. Require minimum length 19, magic
`00 F1` and valid CRC. Discard noise, buffer partial frames, emit glued frames in
order and drop malformed/bad-CRC input.

### RPD reliable sequencing

Initial sequence numbers are random four-bit values.

- SYN consumes the sender sequence immediately. The peer SYN acknowledges the
  initiator's ISN+1.
- Sending data does not advance the sender sequence. Only a data-path frame
  whose ACK equals current own sequence+1 advances it.
- Empty ACKs do not consume sequence numbers. SYN/FIN ACK nibbles are handshake
  bookkeeping, not data acknowledgements.
- Deliver non-empty data only in order, then increment the receiver's expected
  sequence. Drop duplicates and out-of-order data silently without re-ACKing.
- An in-order FIN consumes the receiver sequence, so its final ACK is FIN+1.
  Constructing FIN does not consume the sender sequence.

Use a window of one and retransmit the identical pending frame up to three times
at 2000 ms intervals. SYN-ACK timeout is 4500 ms and teardown timeout 6000 ms.
The spec includes a complete two-endpoint sequence vector plus duplicate,
out-of-order, wrong-ACK and FIN cases.

### TLS 1.2 and certificates

The phone is TLS client and the lock is server. The compatible profile selects:

- TLS 1.2, `ECDHE-ECDSA-AES-256-GCM-SHA384` (`0xC02C`);
- P-256 with an uncompressed 65-byte public point and ECDSA-SHA512 key-exchange
  signature;
- extended master secret, computed from the complete ClientHello through
  ClientKeyExchange transcript, including handshake headers;
- AES-256-GCM records with eight-byte explicit per-direction counters starting
  at 1 for application data. The 96-bit nonce is the direction's four-byte fixed
  IV followed by that explicit counter.

AAD is exactly **13 bytes**:

```text
sequence_uint64_be || record_type_uint8 || version_uint16_be || plaintext_length_uint16_be
```

The final length is the **plaintext** length, excluding the eight-byte explicit
nonce and 16-byte GCM tag. It is not the five-byte TLS header and not the
encrypted body length. The spec carries independent encrypted Finished and
application-data known-answer vectors with ciphertext, tag and full record,
plus negative tests for the old five-byte-AAD mistake and sequence mismatches.

The client Finished uses a handshake record with nonce 0 and plaintext
`14 00 00 0c` plus 12 verify bytes. Accept the lock Finished in an
application-data record with nonce 0. Reject wrong cipher/group, missing EMS,
bad signatures/tags and unexpected ordering.

The lock sends a CertificateRequest, but the compatible client returns an
**empty certificate list**:

```text
0b 00 00 03 00 00 00
```

Authentication then happens with AFI `AuthorityLogin` inside the encrypted
channel. This is **not mandatory mutual-certificate TLS**.

Certificate verification is mandatory. Never disable it and never treat public
CN/serial data as authentication. A client must:

1. pin the exact public DMI intermediate by its SHA-256 fingerprint
   `f6e1b0c175d9d971acc18d94117a237515adee39c6d02c0a013523093b500d64`;
2. verify every chain signature and the leaf's ECDSA proof;
3. require leaf CN and X.509 serial to match the connected lock serial;
4. check leaf/anchor validity, CA Basic Constraints and key usage, rejecting an
   expired leaf or non-CA anchor;
5. handle the public anchor's unusual year-zero-to-9999 interval with a
   DMI-aware parser rather than skipping validation, and document that no
   revocation mechanism has been established.

The reviewed HA integration disables verification, and the library's optional
secure mode omits some validity/constraint checks. Neither meets this spec's
required profile.

### AFI application messages

```text
request: 01 | class | function | payload
result:  02 | class | function | status | payload
event:   03 | class | event | payload
```

There is no request ID; send one request at a time and match results in order.
Primitive numbers/enums use unsigned LEB128. Fixed uint16/uint32 fields are
little-endian where stated. TLV tags/lengths are varints, while integers inside
TLV values are shortest big-endian.

After TLS, send `AuthorityLogin` (class 1, function 1) with the opaque token
appended. Require status 0. Then set UTC (class 3, function 1, uint32 LE epoch)
and start with read-only calls:

| Operation | Class/function | Request |
|-----------|----------------|---------|
| Device information | 2 / 2 | `01 02 02` |
| Lock state | 4 / 5 | `01 04 05` |
| Lock settings | 4 / 6 | `01 04 06` plus the declared zeroed TLV members |
| Power source | 10 / 1 | `01 0a 01` |

Device information returns seven varints (product, three hardware and three
firmware components) followed by a NUL-terminated UTF-8 firmware identifier.
Power Source returns TLV data; validate actual members before assigning units.
Status `0x41` means not logged in and `0x5E..0x73` covers token-validity
failures. Expiry requires a fresh grant.

`LockOperate` is class 4, function 1: varint 2 unlocks and 3 locks. It is
**advanced and attended**, never bound to a generic entity. Send one intentional
operation only after manual selection, full validation and successful login;
require its result/state and never auto-replay.

## Alternative local routes

- **BTZE/BTZU:** Z-Wave JS identifies V3-BTZE as manufacturer `0x010E`, product
  type/id `0x0009/0x0001`. It is a genuine local controller route.
- **BTZB/BTZBE:** Zigbee2MQTT provides lock/state, battery, PIN users, action
  events and OTA without Danabridge or the vendor cloud. BTZB is the older
  Zigbee 1.2 module and cannot be Zigbee-updated; BTZBE is Zigbee 3.0/updateable.
- **BTHK:** use Apple Home or Home Assistant HomeKit Device locally, preserving
  the pairing code and accounting for one controller and RF quality.
- **Danapad:** app-less pairing can preserve PIN use with a supported hub but
  deletes existing PINs and prevents later app enrollment. It is not DMI
  self-keying.

These are survival notes only; no additional unimplemented specs are claimed.

## Firmware updates

Public Nordic secure-DFU packages declare ECDSA-P256-SHA256 signatures and their
init hashes match the images. Actual vendor signature verification, target
bootloader enforcement, anti-downgrade behavior and interrupted-update recovery
were not established. DFU advertisements use manufacturer payload version 3 and
retain the DMI serial; ordinary controls must stop. No uploader is provided.

## Verification and remaining work

No lock, account, real credential or live operation was used. All protocol facts
are `reported`; the spec is `testing: untested`. Independent tests cover DMI CRC
and escaping, fragmented/glued/noisy/bad streams, RPD sequencing and duplicates,
broadcast AES/CRC/flags, AFI varints/TLVs/commands, TLS PRF and the empty client
certificate message. Every fixture is synthetic.

Remaining questions include token TTL/rotation/revocation, DMI compatibility
outside BTZE, a maintained complete-X.509 client, raw battery scaling, offline
enrollment, bootloader policy and Danabridge trust enforcement.

## References

- [pydanalock-ble 0.10.0 (pinned)](https://github.com/buggy-shep/pydanalock-ble/tree/ec3bec0c2da580c08d69d33bc923063222db60cf) — DMI/RPD/TLS/AFI/broadcast source and synthetic fixtures.
- [Danalock BLE HA integration 0.10.0 (pinned)](https://github.com/buggy-shep/danalock-ble-ha-integration/tree/9d12d7f1f961c4ac36d6417e6dbee15d838d6ce2) — BTZE-only author evidence and current persistence/TLS limitations.
- [Official Danalock general information](https://support.saltosystems.com/danalock/danalock/general-information/) and [click-command installation guide 226565](https://support.saltosystems.com/installation-guides/226565.pdf) — serial, firmware and reset controls; both returned HTTP 200 on 2026-11-18.
- [Official Bluetooth guidance](https://support.saltosystems.com/danalock/danalock/bluetooth/), [Z-Wave guidance](https://support.saltosystems.com/danalock/danalock/zwave/) and [Zigbee guidance](https://support.saltosystems.com/danalock/danalock/zigbee/) — variant and local-route boundaries.
- [Z-Wave JS BTZE config (pinned)](https://github.com/zwave-js/node-zwave-js/blob/b00e8e35ad67b3f2b6ac53bee74c38709782d154/packages/config/config/devices/0x010e/danalock_v3-btze.json) and [Zigbee2MQTT converter (pinned)](https://github.com/Koenkk/zigbee-herdsman-converters/blob/89ab46f435273bee930cec78e2f2d050e6fa5af8/src/devices/danalock.ts) — independent alternative routes.
