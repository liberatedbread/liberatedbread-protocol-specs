# ALLPOWERS R600 (hardware 0.3, read-only)

> **Status**: Identify-only — source-derived, untested; dedicated consumer handler pending
> **Protocol**: BLE GATT
> **Manufacturer**: ALLPOWERS (active)
> **Model**: R600 / AP-SS-005-Pro, hardware revision 0.3 only

## Overview

This profile reads battery, input/output power, remaining time and output state
from an R600 without a vendor account or cloud connection. It deliberately does
not control AC, DC, lighting, charging or firmware. The machine-readable spec is
[`allpowers-r600.yaml`](https://github.com/liberatedbread/liberatedbread-protocol-specs/blob/main/device-specs/devices/allpowers-r600.yaml).

R1500 LITE, R2500 V2 and VOLIX/P1800 are not covered. Their public clients show
materially different packet meanings and masks; do not inherit this decoder or
try alternate characteristics on them. A shared service UUID or broad AP R name
is not proof of an R600.

## Initial Setup and pairing

| Property | Value |
|----------|-------|
| Setup required | No |
| Method | `ble_direct` (medium confidence) |
| BLE pairing/bond | None |
| Credentials | None for this read-only profile |
| Connection recovery | Close the vendor app/other central and reconnect |

Connect and verify the service and both characteristics below. Subscribe to
notifications, then send only the 12-byte status request. Wait at most 10
seconds (a bounded client policy, not a measured device timeout) for raw hardware
byte `0x03` in a command-`0x03` settings notification from the **same GATT
session**. Do not assume the status request elicits settings. A cached setting,
status-only exchange or R600-looking name is not enough. On timeout, malformed
settings or another revision, fail validation, publish no R600 telemetry and
disconnect; never send a settings write or keepalive.

**Factory reset**: unknown. The manual identifies the model but this research
did not establish a reset sequence or what it clears. Do not invent a button
hold or treat output power-cycling as a factory reset.

**Rebinding**: there is no network membership or bond. Disconnect the old
central and repeat the identity and current-session revision checks.

## Protocol Summary

| Role | UUID |
|------|------|
| Service | `0000fff0-0000-1000-8000-00805f9b34fb` |
| Notifications | `0000fff1-0000-1000-8000-00805f9b34fb` |
| Read-request write | `0000fff2-0000-1000-8000-00805f9b34fb` |

The fixed status request is:

```text
a5 65 b1 00 01 06 01 00 00 00 00 00
```

Notifications have `A5 65`, three vendor-envelope bytes, payload length `N` at
offset 5, command at 6, payload at 7 and one XOR byte. Total response length is
`8+N`, and XOR over the complete frame is zero. Reject lengths above 128 and
malformed frames. Notifications can split or coalesce frames, so retain partial
headers. Delete `8+N` bytes only after a successful decode; on checksum or
payload failure discard only the first buffered byte and rescan, because a bad
outer candidate can contain a valid inner STATUS frame. The status request is
not a response and does not follow that length rule.

### Status (`0x01`)

Offsets here are within the payload, not the complete frame.

| Offset | Type | Meaning |
|--------|------|---------|
| 0 | `uint8` | Flags: DC `0x01`, AC `0x02`, light `0x10`; preserve unknown bits |
| 1 | `uint8` | Battery 0–100%; reject larger values |
| 2 | `uint16` big-endian | Input watts |
| 4 | `uint16` big-endian | Output watts |
| 6 | `uint16` big-endian | Remaining minutes |

### Settings and revision (`0x03`)

The six-byte minimum payload carries flags, ECO hours, two reserved bytes,
hardware byte at payload offset 4 and firmware byte at 5. Hardware `0x03` is the
required revision. ECO/work/car-charger bits are telemetry only here. In
particular, the light mask in the separate output-control protocol is `0x20`,
not the status mask `0x10`; no output-control frame is published.

Command `0x35` optionally carries a UTF-8 name. Strip NUL padding and control
characters, trim whitespace and cap at 64 characters.

## Validation and omissions

`scripts/test_allpowers_r600_spec.py` independently rebuilds and parses the
public status/settings fixtures, checks XOR and tests fragmentation,
coalescing, noise recovery and malformed frames. No hardware is contacted.

The profile intentionally omits all output/settings writes, keepalives,
bootloader operations and cross-model support. Reset behavior, notification
cadence, simultaneous-central behavior and other R600 revisions remain open.

## References

- [Pinned public R600 implementation and tests](https://github.com/dedalodaelus/home-assistant-allpowers-ble/tree/2fc2570630c8f6d7229c533060bdd3afef7a33da)
- [R2500 V2 client — compatibility boundary only](https://github.com/R0b0To/allpowers-companion/tree/c19ba2c692cfdae8590fa14fd0b77ec90005f5da)
- [R600/R1500 LITE client — field-difference evidence](https://github.com/mattgorle/allpowers-ble/tree/a63cd36e568757bae5dcee30efb10edad8cf22ac)
- [ALLPOWERS R600 / AP-SS-005-Pro manual (PDF)](https://cdn.shopify.com/s/files/1/0443/1223/2089/files/AP-R600-User_Manuals-2023-01-10_compressed.pdf?v=1678773110), verified as a vendor-hosted PDF on 2026-11-17.
