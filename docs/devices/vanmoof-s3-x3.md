# VanMoof S3 / X3 — legacy local BLE

> **Status**: Spec Available (untested on hardware; identify-only consumer integration)
> **Protocol**: BLE GATT, legacy `6acc55` profile with AES-128-ECB
> **Manufacturer**: VanMoof
> **Manufacturer Status**: Active after the 2023 bankruptcy and acquisition

## Overview

This page covers **only S3 and X3 bicycles exposing the legacy `6acc55`
service family**. It does not cover S2/X2, S4/X4, S5/A5, S6 or the newer
`8e7f1a5x` protocol generation. A model name alone is not enough: enumerate
the exact endpoints before authenticating, and stop if they are absent.

An owner who already exported the bicycle's 16-byte encryption key and
one-byte user key ID can use the protocol locally without a cloud session.
Those credentials are per-owner/per-bicycle secrets. This repository contains
no real key, account token, bicycle address, frame number or owner telemetry.

The implemented surface is deliberately small:

- authenticated motor and module battery percentages;
- total distance and current speed;
- lock state;
- attended lock, unlock and bell-tone selection, each with authenticated
  readback.

Assist, lights, alarm, speed-limit, region, arbitrary sound, backup-code,
reset/bonding and OTA operations are omitted. The spec is `identify_only`
until a consumer implements the encrypted session and attended-control flow;
a generic renderer must not send the documented command bodies as plaintext.

## Hardware

| Property | Value |
|----------|-------|
| Models | S3 and X3, only with the legacy service set |
| Radio | BLE; no Wi-Fi provisioning in this profile |
| Category | `vehicle` / e-bike |
| Identity filter | `6acc5500-e631-4069-944d-b8ca7598ad50`, then GATT enumeration |
| Companion evidence | pymoof and VanMoofKit at the pinned revisions in the spec |
| Manual | [25-page S3/X3 FCC owner-manual exhibit](https://fccid.co/api/files/s1/2awdq_vm_es3_sec_a_usersmanual_5127900_86012cac9b.pdf) |

## Initial setup

| Property | Value |
|----------|-------|
| Setup required | Yes: owner key and user key ID must already be available |
| Offline method | `ble_direct` with previously exported credentials |
| Alternative | One-time owner-account export (`cloud_account`), availability untested |
| Wi-Fi passphrase | Not applicable |
| Setup confidence | High (working public clients), but not replayed by this project |

For an existing export, store the 16-byte key and user key ID in a secret
store. Scan for the security service, enumerate the exact endpoints, then:

1. Read exactly two challenge bytes.
2. Encrypt `challenge || 00 * 14` using AES-128-ECB and the owner key.
3. Append clear bytes `00 00 00 <user_key_id>` and write the resulting 20
   bytes with response to the key-index characteristic.
4. **Do not call that write success authentication.** Read and decrypt motor
   battery level, requiring block-aligned ciphertext and a value from 0 to
   100. Only then enable telemetry or attended controls.

If the owner has no export, use an owner-controlled account exporter for
their own bicycle and retain the result offline. This pass did not establish
whether the current account service issues keys for every account. Never use
another person's key or treat key export as an account/lock bypass.

**Factory reset:** unknown. No reset, backup-code or rekey procedure is
published here, and a procedure from another VanMoof generation must not be
substituted. Preserve the owner's existing recovery method.

**Rebinding:** a replacement client needs the same exported key and user key
ID, followed by a fresh authenticated session. No factory reset or network
rejoin is needed merely to add a reader.

## Pairing and session lifecycle

| Property | Value |
|----------|-------|
| Pairing required | Application-layer owner authentication on every connection |
| Security mode | `app_layer` |
| OS bonding | None required by the reviewed clients; current firmware unverified |
| PIN source | No BLE PIN; 16-byte key plus one-byte user key ID from owner export |
| One central at a time | Unknown; close other clients if busy |
| Unpairing | Delete the client's stored credential; no BLE unpair/rekey command is declared |

There is no pairing window. Application authentication replaces it. A GATT
write response proves delivery only. Authenticated reads establish that the
session is usable.

## Protocol summary

### Services used

| Service | Characteristic | Meaning |
|---------|----------------|---------|
| `6acc5500-e631-4069-944d-b8ca7598ad50` | `6acc5501-e631-4069-944d-b8ca7598ad50` | Fresh two-byte plaintext challenge |
| Same | `6acc5502-e631-4069-944d-b8ca7598ad50` | 20-byte authentication write |
| `6acc5520-e631-4069-944d-b8ca7598ad50` | `6acc5521-e631-4069-944d-b8ca7598ad50` | Encrypted lock state, read/write |
| `6acc5530-e631-4069-944d-b8ca7598ad50` | `6acc5531-e631-4069-944d-b8ca7598ad50` | Encrypted uint32-LE distance |
| Same | `6acc5532-e631-4069-944d-b8ca7598ad50` | Encrypted uint8 speed |
| `6acc5540-e631-4069-944d-b8ca7598ad50` | `6acc5541-e631-4069-944d-b8ca7598ad50` | Encrypted motor battery percent |
| Same | `6acc5543-e631-4069-944d-b8ca7598ad50` | Encrypted module battery percent |
| `6acc5570-e631-4069-944d-b8ca7598ad50` | `6acc5574-e631-4069-944d-b8ca7598ad50` | Encrypted bell tone, read/write |

All other characteristics in those service groups are outside this bounded
profile, including backup-code, alarm, assist and firmware surfaces.

### Strict encryption

The cipher is AES-128-ECB with a 16-byte owner key, no IV and **zero padding**,
not CBC or PKCS#7. Require a fresh, exactly two-byte challenge for
authentication and again for every ordinary write. Reject short and long
challenges rather than normalizing them.

For an ordinary command body `command_data`:

```text
plaintext  = nonce[2] || command_data || zero_bytes_to_next_16_byte_boundary
ciphertext = AES-128-ECB(owner_key, plaintext)
```

The two nonce bytes count toward block length. If the input is already
aligned, add no extra block. Do not append the authentication suffix to an
ordinary command. Write with response.

Protected reads must contain nonempty whole AES blocks. Decrypt, parse only
the declared field and ignore the expected zero padding; never convert the
whole padded plaintext to an integer. Reject malformed values and unknown
enums instead of substituting zero.

### Telemetry values

| Reading | Plaintext field | Decode |
|---------|-----------------|--------|
| Motor battery | byte 0, uint8 | 0–100 % |
| Module battery | byte 0, uint8 | 0–100 % |
| Distance | bytes 0–3, uint32 little-endian | Hectometres; `raw × 0.1 km` (raw 1234 = 123.4 km) |
| Speed | byte 0, uint8 | Integer km/h (`0x19` = 25 km/h) |
| Lock state | byte 0, enum | 0 unlocked, 1 locked, 2 awaiting unlock |
| Bell tone | byte 0, enum | `0x16` bell, `0x17` party, `0x18` boat |

State 2 is both a transitional read state and VanMoofKit's
`awaitingUnlock` command. This spec follows that client's unlock command
`0x02`; pymoof's generic setter instead accepts `0x00` for its unlocked enum.
No physical capture establishes pymoof's `0x00` as an unlock command here, so
it is not declared. Unlocked `0x00` is the required final readback, not the
command selected by this spec.

### Attended writes

Lock and unlock send command bodies `01` and `02` respectively through the
fresh-challenge encryption routine. Bell-tone selection sends one of `16`,
`17` or `18` hexadecimal. Every write has all of these gates:

1. the bicycle is owner-authorized, stationary and attended;
2. the owner explicitly confirms that operation;
3. an authenticated read has already succeeded in this session;
4. a fresh two-byte nonce is read for this write;
5. the same characteristic is read and decrypted afterwards, and must report
   the requested state or tone.

Unlock has a transitional exception to the last rule: after sending `0x02`,
poll once per second for at most five attempts. Accept `0x02` only while the
unlock is pending and require `0x00` by the final attempt. A sequence such as
`2, 2, 0` succeeds; `2, 1` fails immediately, and five attempts without `0`
time out. The one-second initial delay follows VanMoofKit's post-write read;
the five-attempt ceiling is a conservative client-side bound, not an observed
firmware constant.

If readback is absent, malformed, unexpectedly locked or times out, report an
unconfirmed result; do not retry blindly and do not infer success from the
GATT response.

## Verification and remaining work

The source research reviewed pymoof at
`b77518cd4dc813905802f14364c461b31ac88356` and VanMoofKit at
`d258b2575115f11ccfcfbcb8ecf6dd3c740c30fc`. On 2026-11-02, 14 upstream tests
and 110 independent offline AES/fake-GATT assertions passed. No bicycle,
owner credential or live BLE exchange was used.

`scripts/test_vanmoof_s3_x3_spec.py` independently rebuilds the spec's NIST,
authentication, ordinary-command and telemetry fixtures with OpenSSL. Its
unlock-specific vector checks the `0x02` command and a decrypted `2, 2, 0`
readback sequence, plus locked-state rejection and the five-attempt timeout.
All keys and nonces in those fixtures are invented. The tests also enforce the
model/write allowlist and attended advanced-command metadata.

The evidence disagreement is explicit: VanMoofKit's named `unlock()` writes
`awaitingUnlock` (`0x02`), whereas pymoof's generic setter accepts its unlocked
enum (`0x00`). Neither client's fake-GATT path proves what a bicycle accepts.
The spec therefore adopts the named VanMoofKit operation and does not claim
`0x00` as an established unlock command.

Still needed: a privacy-scrubbed GATT dump tied to exact firmware, captured
authentication acceptance and unlock/readback behavior resolving the `0x00`
versus `0x02` client disagreement, current key-export availability, and
hardware confirmation of connection/bonding behavior. None of those gaps
should be filled from another VanMoof generation.

## References

- [VanMoof S3 & X3 user manual (FCC exhibit)](https://fccid.co/api/files/s1/2awdq_vm_es3_sec_a_usersmanual_5127900_86012cac9b.pdf)
- [pymoof at the reviewed revision](https://github.com/quantsini/pymoof/tree/b77518cd4dc813905802f14364c461b31ac88356)
- [VanMoofKit at the reviewed revision](https://github.com/SvenTiigi/VanMoofKit/tree/d258b2575115f11ccfcfbcb8ecf6dd3c740c30fc)
- Machine-readable details and synthetic vectors: `device-specs/devices/vanmoof-s3-x3.yaml`
