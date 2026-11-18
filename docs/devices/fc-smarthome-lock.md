# FC SmartHome / Fingerchip BLE Locks

> **Status**: Identify-only spec; untested here
> **Protocol**: BLE GATT, AES-encrypted FC/FD application frames
> **Manufacturer**: Shenzhen Fingerchip / Fingercrystal
> **Manufacturer Status**: Active

## Overview

FC SmartHome, Yi-Lock and eApartment are sibling app identities for
Fingerchip/Fingercrystal locks. The public local client implements identity
verification, session keys, model/firmware/wake metadata, users, history and an
advanced unlock on an L5-class lock. No evidence makes this TTLock or proves
Tuya/TTLock compatibility.

The safe initial scope is **read-only after provisioning**. The first session
needs two values from the owner's cloud device record:

- **`bluetoothKey`**: 32 hex characters decoded to the initial 16-byte AES key;
- **`deviceBindUserId`**: the 32-byte identity expected by VERIFY_IDENTITY.

The latter corrects older comments that called it `deviceuuid`; zeros and a MAC
address are not substitutes. The handshake returns a per-session AES key for
subsequent messages. No general offline method for issuing the initial values
was found. One public client's built-in initial-key fallback matched its tested
L5, but that is one observation, not a general provisioning route.

This catalogue entry is `identify_only`: a dedicated encrypted/session handler
is required, and no generic unlock is exposed. The active implementation's
`USER / 0x04`, command `0x10`, data `0x01` unlock is documentary only as an
**advanced, attended** operation. Do **not** send the stale target's
`SYSTEM / 0x02`, command `0x0E` form.

## Hardware and app identities

| Property | Value |
|----------|-------|
| Live-evidence model | L5-class, third-party author-reported |
| Manual model | E202Pro, used for app-flow/reset evidence only |
| Radio | BLE; some models also have vendor Wi-Fi/cloud service |
| Advertised scan service | `000001fa-0000-1000-8000-00805f9b34fb` |
| Main service / characteristic | `0000ffe0-0000-1000-8000-00805f9b34fb` / `0000ffe1-0000-1000-8000-00805f9b34fb` |
| Apps | FC SmartHome `com.fingercrystal.smarthome`; Yi-Lock `com.fingercrystal.xiaoyi`; eApartment `com.fingercrystal.apartment` |
| Name hints | Smart Lock, FC, Yi, EL, DX, K3, DZ, SL, L5 — candidates, not model proof |

Do not invent a separate K3 package or assume that another Fingerchip/Pineworld
variant accepts the same initial key. Cross-app credential portability is
unverified.

## Initial Setup

| Property | Value |
|----------|-------|
| Setup required | Yes — owner cloud device record |
| Method | `cloud_account` once, then local session negotiation |
| Official onboarding | Account/admin setup; Wi-Fi models also use 2.4 GHz |
| Initial credentials | `bluetoothKey` + `deviceBindUserId`, stored privately |
| Confidence | Medium — public implementation and official manual, not run here |

1. Complete the official account/admin setup and preserve the device record in a
   secret store. Android backup is disabled in the reviewed app, and the public
   client offers no redacted offline export/importer.
2. Manually select the lock; advertised names and services are only filters.
3. Wake it when needed. **4 then #** gives approximately 60 seconds of activity;
   keypad touch/bell or ordinary fingerprint/handle use gives a few seconds.
   Do not repeatedly wake for polling.
4. Subscribe to notifications and retry service discovery if the sleeping GATT
   table is empty/partial. Require a notifiable characteristic. Use FFE0/FFE1 or
   a validated compatible alternative.
5. Make VERIFY_IDENTITY the **first write**, at sequence 1. Do not send a wake
   heartbeat before it. Accept only result `0` or `0xF1`, install the returned
   session key, and validate model/firmware/wake metadata before other queries.

### Factory reset

The official app manual says factory settings delete the device and clear
passwords, fingerprints, cards and message history. Treat cached BLE access as
invalid and provision again through the account. Reset is not an offline
credential-recovery method, and no BLE reset command is recovered or
recommended.

The manual depicts E202Pro, not the community-tested L5, so this is app-flow
evidence rather than a universal physical/reset-command procedure. It was not
executed by this project.

### Rebinding

A cached initial key and bind identity can negotiate a new local session without
cloud contact while accepted. A new independent client still needs an
owner-authorized record. Start each fresh connection at sequence 1 and perform
read-only verification first. Do not reset merely to resolve a busy connection.

## Protocol Summary

### Outer FC/FD frames

Both versions end in `0xFE`:

| Version | Start | Inner length |
|---------|-------|--------------|
| v1 | `0xFC` | `8 + data_length` |
| v2 | `0xFD` | `9 + data_length`, including trailing inner XOR |

```text
byte 0      start (FC/FD)
byte 1      pid / package index
bytes 2–3   total frame length, uint16 little-endian, start through end
bytes 4…    AES-encrypted inner message, zero-filled to a 16-byte multiple
byte -2     outer XOR checksum
byte -1     FE
```

Outer checksum is `pid XOR length_low XOR length_high XOR every encrypted byte`.
Use AES-128-ECB with the initial key before handshake and the returned session
key afterward. Zero-fill only to the next block boundary; an aligned message
gets no extra block. Inner length, not padding, determines the real data, and
every byte after it must be zero.

Reassemble by the outer total length rather than assuming one notification per
frame. Require length of at least 22, a nonzero multiple-of-16 ciphertext, `FE`,
and a valid checksum before decrypting. Split writes into at most 20-byte
write-without-response chunks with about 20 ms between chunks. The public parser
uses a 1024-byte defensive ceiling; never allocate an unbounded buffer from a
hostile length.

### Inner messages

```text
bytes 0–1   inner length, uint16 little-endian
bytes 2–5   sequence, uint32 little-endian
byte 6      category: SYSTEM 02, USER 04, RECORD 08, WARN 10, SPECIAL F0
byte 7      command
bytes 8…    data
v2 only     trailing inner XOR
```

Normal v2 inner XOR is `length_low XOR length_high XOR category XOR command XOR
every data byte`. The special Android heartbeat additionally XORs all four
sequence bytes; do not apply that variant to other messages. Validate inner
length, v2 XOR and zero-fill.

Sequence starts at 1 per connection. After a response, the next request uses
**response.sequence + 1**, modulo `2^32`, not just the previous local value + 1.
A failed identity handshake retries on a fresh connection at 1. Read-only
retries reuse the identical frame/sequence; unlock is never auto-retried.

### VERIFY_IDENTITY

Category `0x02`, command `0x08`, sequence 1. The 39-byte request payload is:

| Offset | Size | Meaning |
|--------|------|---------|
| 0 | 32 | `deviceBindUserId` as ASCII, truncated/padded with NUL |
| 32 | 1 | Year − 2000 |
| 33–37 | 5 | Month, day, hour, minute, second |
| 38 | 1 | Signed timezone hours, positive for UTC+N; negative values use two's complement |

Accepted result codes are `0` and `0xF1`. Response fields are:

| Offset | Size | Meaning |
|--------|------|---------|
| 0 | 1 | Result |
| 1 | 16 | Raw per-session AES key — never log |
| 17 | 12 | MAC text — redact |
| 29 | 3 | Protocol-version text |
| 32 | 8 | Model text |
| 40 | 15 | Firmware text |
| 55 | 2 | Wake source, **big-endian** |
| 57 | 15 | Optional fingerprint-module version text |

Reject short responses, other result codes, invalid text or truncated required
fields before switching keys or publishing metadata.

### Read-only queries

**Device information is deliberately excluded for now.** The active HA method
uses SYSTEM command `0x03`, while the older library labels READ_INFO `0x04`.
No capture resolves that conflict, and battery/item types are unknown. Do not
issue either opcode or expose a battery sensor. The handshake already supplies
model, firmware and wake source.

**Registered users:** USER `0x04`, command `0x01`, empty data. A zero/status byte
precedes 22-byte records:

| Offset | Type | Meaning |
|--------|------|---------|
| 0 | uint16 LE | User ID |
| 2 | byte | Enabled when 1; preserve other raw values |
| 3 | byte | User type, unresolved |
| 4 | byte | Attributes, unresolved |
| 5 | uint32 LE | Start-time raw value; epoch/unit unresolved |
| 9 | uint32 LE | End-time raw value; epoch/unit unresolved |
| 13 | 9 bytes | Undecoded |

Continue pagination with response `pid` until zero. Reject a trailing partial
record instead of silently producing plausible users.

**Unlock/alarm history:** USER `0x04`, command `0x12`, data `0x01`. After a
zero/status byte, records contain uint32-LE raw timestamp, two model bytes,
record type, and user ID. The ID is one byte in the 8-byte form and uint16 LE in
the 9-byte form. The public client chooses 9-byte records when the remaining
length is divisible by 9 and at most 54, otherwise 8; this is a heuristic, not a
universal model guarantee. Continue while `pid` is nonzero and reject partial
records. Preserve raw history privately and redact user identities in research.

### Advanced unlock documentary only

The active, verified client uses:

```text
category = USER (0x04)
command  = 0x10
data     = 0x01
```

A second `0x18` form carries a uint16-LE user ID but is outside the minimal safe
scope. Latch and beep are unsupported, and the client's lock alias performs no
physical locking action.

Only after identity and read-only checks, while the lock is awake and someone is
attending the door, may a dedicated client send one intentional unlock and check
its result/event. No generic entity, unattended automation or timed-out replay
is allowed. **The stale target form `SYSTEM/0x02`, command `0x0E`, data `0x01`
must not be sent.**

## Other channels and firmware

Raw TCP port 4067 and the proposed NAT/DNS redirect were not demonstrated end to
end. Alink CoAP over UDP 5683 and gateway/LAN registration were also not
validated. Do not present either as a working local unlock route or assume the
BLE framing transfers unchanged.

No public lock firmware image was found. Management-asset searches produced no
artifact URL or trustworthy version/hash, so no update procedure is declared.
The public Python cloud client disables normal certificate/hostname checks and
uses legacy TLS settings; a replacement must instead use ordinary CA/hostname
validation and supported TLS. Those cloud-client choices are unrelated to BLE
session encryption.

## Verification and remaining work

No lock, account, real key, bind identity or live operation was used. All facts
are `reported`; the spec is `testing: untested`. A fixed public app-bundle frame
corroborates only outer framing/checksum, not an over-the-air session. Every
vector in the spec is newly generated with invented values.

Independent tests cover v1/v2 AES frames, zero-fill, normal/Android XOR,
fragmentation, noise, glued/corrupt frames, inner length/padding, handshake
response fields, users/history and malformed records, response-sequence and
pagination rules, and the documentary unlock/stale-opcode boundary.

Still needed: offline bind-identity issuance, other-model key uniqueness and
dialects, info/battery commands, timestamp/user semantics, reset credential
rotation, characteristic fallback behavior, raw TCP/CoAP evidence and firmware.

## References

- [FC SmartHome public client and tests (pinned)](https://github.com/JuanmanDev/fc-smart-home-assistant/tree/e2f66d547e40fd4cfb9544f52bbc8eb98a5ac21c) — framing, handshake, users/history, wake handling and offline golden tests.
- [Official FC SmartHome app manual](https://m.media-amazon.com/images/I/A1m9Nhsf74L.pdf) — account/admin flow, 4+# wake and destructive factory settings for the depicted E202Pro; HTTP 200 verified 2026-11-18.
- [Home Assistant origin discussion](https://community.home-assistant.io/t/custom-integration-fc-smarthome-fingerchip-fingercrystal-yi-lock-eapartment-full-reverse-engineering-hacs-release/1025721) — community background; the pinned source/tests are the protocol basis.
