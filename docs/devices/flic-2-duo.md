# Flic 2 and Flic Duo

> **Status**: Spec Available (untested; vendor-published protocol)
> **Protocol**: BLE GATT with application pairing and authenticated sessions
> **Manufacturer**: Shortcut Labs AB
> **Manufacturer Status**: Active

## Overview

Flic 2 and Flic Duo can pair directly with a third-party phone or computer and
deliver reliable button events without a cloud account. The vendor publishes the
protocol and an official SDK. The consumer Flic app's initial onboarding is a
separate flow and does require an account and Internet access.

**Scope is direct Flic 2/Duo only.** Flic 1, Flic Twist and all Flic Hub
transports/APIs are excluded. One button has one active central, while multiple
apps on that central use independent pairings and logical connection IDs.

## Initial Setup

| Property | Value |
|----------|-------|
| Setup required | Yes — a per-app Full Verify on first use |
| Method | `ble_provisioning`; Quick Verify on later connections |
| Passphrase protection | `not_applicable` (no Wi-Fi; persistent per-app pairing key) |
| Confidence | Medium (official protocol, no hardware replay here) |

Enable **Public mode** and verify the complete advertisement. The reviewed source
does not establish a model-neutral physical sequence for entering Public mode, so
do not rely on an invented press count. Private mode advertises only flags and is
not suitable for initial pairing.

Full Verify validates the button's Ed25519 identity, uses fresh X25519/random
material, and creates a per-app 32-bit pairing identifier and 128-bit pairing key.
Store both securely. Later connections use Quick Verify with fresh session keys.
Duo uses discriminator `0x40` for Quick Verify and `0x80` in Full Verify secret
derivation.

**Factory reset / unpairing**: No factory-reset or device-side per-app revocation
procedure is established. Deleting the host's own record is always possible.
Quick Verify negative response 6 is spoofable and is not proof of removal; the
authenticated Test If Really Unpaired exchange must succeed before deleting a
pairing.

**Rebinding**: The same app reconnects with Quick Verify. A different app needs a
new Full Verify and its own pairing record; do not copy credentials between apps.
Disconnect the old central first.

## Advertising and GATT

Public name: exactly `F2`, two firmware decimal digits, then four URL-safe-base64
characters encoding the low 24 address bits in big-endian order. Public mode also
advertises service `00420000-8f59-4420-870d-84f3b617e493` and a company-`0x030f`
scan response containing `02`, the top 24 address bits little-endian and flags.
The YAML includes a synthetic address reconstruction example.

| UUID | Role |
|------|------|
| `00420000-8f59-4420-870d-84f3b617e493` | Control service |
| `00420001-8f59-4420-870d-84f3b617e493` | Host writes without response |
| `00420002-8f59-4420-870d-84f3b617e493` | Button notifications |

Negotiate ATT MTU 140 when possible (137-byte characteristic values). Reassembled
packets are capped at 129 bytes. Fragmentation repeats byte 0 and sets its high
bit on every fragment except the last. Byte 0 also carries the logical connection
ID, newly-assigned flag and optional multiple-packet flag. Drop packets for other
logical IDs without consuming counters or events.

## Authenticated Sessions

After session establishment, every packet carries a five-byte Chaskey-LTS
signature over `counter_u64le || direction_u64le || opcode || data`. Direction is
0 from button and 1 toward button. Counters start at zero independently in each
direction and advance only after successful processing. Require the expected
counter, reject replays and terminate on a bad signature. Signatures authenticate;
they do not encrypt payloads. BLE Just Works bonding is an optional additional
layer, not the Flic security mechanism.

The YAML specifies subkeys, padding, all 16 permutation rounds, full/quick session
derivation and official-SDK-checked synthetic vectors. It also includes the
Ed25519 public key and the recovered-two-bit verification procedure needed for
Full Verify Response 1.

## Reliable Button Events

Initialize event delivery before expecting events. Base Flic 2 uses opcode 23 with
persisted `event_count` and `boot_id`, then opcode-12 notifications. Event items
pack a 48-bit boot timestamp (1/32768-second units), event encoding and queue
flags into eight bytes. Acknowledge qualifying click events once per packet with
opcode 16 after processing and storing the count.

Duo uses opcode 35 with counters for big button 0 and small button 1, millisecond
timestamps, and opcode-32 bitstream notifications. Its decoder includes variable
counter/timestamp widths, queue completion, gestures and signed accelerometer
axes. Acknowledge with opcode 36 containing **both** counters.

Push-twist uses opcode 37 to enable and opcode 33 for updates. The signed int32le
angle delta uses 65536 units per turn, positive to the right; it is relative, not
an absolute angle. Raw direct-BLE events are documented, not hub-specific dimming.
Battery response opcode 20 carries uint16le raw voltage, decoded as
`raw × 3.6 / 1024` volts, not a percentage.

`scripts/test_flic_2_duo_spec.py` independently checks advertising, fragment
reassembly, Chaskey vectors, full/quick derivation, replay rejection, reliable
acknowledgements and malformed Duo bitstreams.

## Firmware and Remaining Boundaries

Flic 2 and Duo have different documented firmware flows and backends, both gated
behind signed sessions. They are declared as reported update surfaces, not as
fixed frames to replay. No firmware request was made, and image signature
internals and distinct DFU advertising remain unknown.

## References

- [Official Flic 2 Protocol Specification](https://github.com/50ButtonsEach/flic2-documentation/wiki/Flic-2-Protocol-Specification)
- [Official Flic Duo Protocol Specification](https://github.com/50ButtonsEach/flic2-documentation/wiki/Flic-Duo-Protocol-Specification)
- [Official flic2lib-android](https://github.com/50ButtonsEach/flic2lib-android)
- [Flic setup and account FAQ](https://flic.io/start)
