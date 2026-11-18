# Blackmagic Cinema Cameras with Bluetooth

> **Status**: Spec Available (source-derived, untested)
> **Protocol**: BLE GATT
> **Manufacturer**: Blackmagic Design
> **Manufacturer Status**: Active

## Overview

Blackmagic publishes a local Bluetooth remote-control protocol for cinema
cameras that document Bluetooth support. The current Pocket Cinema Camera 4K,
6K G2 and 6K Pro advertise this capability. Other bodies must be qualified by
their own manuals and the runtime model/version reads; the shared SDI command
table alone does not prove that a camera has a Bluetooth radio.

The link carries camera control, timecode and status. It does not carry video,
recording media or a firmware image, and needs no cloud account.

## Initial Setup

| Property | Value |
|----------|-------|
| Setup required | Bonding required before encrypted control |
| Method | `ble_direct` plus a camera-displayed six-digit PIN |
| Discovery | Service `291d567a-6d75-11e6-8b77-86f30ca893d3` |
| Passphrase protection | `not_applicable` (no Wi-Fi) |
| Confidence | Medium — vendor documentation, not replayed here |

Power the camera, scan for the vendor service, and read **Camera Model** and
**Protocol Version** before enabling features. Subscribe to Incoming Camera
Control, Camera Status and Timecode. An encrypted-characteristic write starts
bonding; the camera displays a six-digit PIN in its Bluetooth Setup menu for
entry on the host. Do not use a recording or media-changing command as the
pairing probe. The manual's example is Camera Power On (`01`), which should be
used only when powering on is acceptable.

Wait for the status bits for versions verified and initial payload, preferably
Camera Ready, before relying on the initial parameter cache.

**Factory reset**: unknown. The public protocol defines neither a factory
reset nor an unpair procedure, and does not establish which bonds or settings
a camera-menu reset clears. Do not treat a general settings reset as a proven
Bluetooth reset.

**Rebinding**: there is no Wi-Fi network to rejoin. Close competing clients,
rediscover the service and repeat the PIN flow on a new host. For a stale bond,
forget only that host/camera pairing in the OS before bonding again.

## Pairing

| Property | Value |
|----------|-------|
| Pairing required | Yes, for encrypted characteristics |
| Security mode | `passkey_entry` |
| Bonding | Required |
| PIN source | Camera screen, six digits |
| One central at a time | Unknown |
| One bond at a time | Unknown |
| Confidence | Medium |

Seeing the service without a bond is not a working control session. Outgoing
and Incoming Camera Control, Timecode and Camera Status require encryption.
No camera-side unpair route is established.

## Protocol Summary

### BLE Services

| UUID | Name | Description |
|------|------|-------------|
| `0000180a-0000-1000-8000-00805f9b34fb` | Device Information | Manufacturer and runtime camera model |
| `291d567a-6d75-11e6-8b77-86f30ca893d3` | Blackmagic Camera Service | Control, status, timecode, name and version |
| `5dd3465f-1aee-4299-8493-d2eca2f8e1bb` | Outgoing Camera Control | Host writes CCU commands; encrypted |
| `b864e140-76a0-416a-bf30-5876504537d9` | Incoming Camera Control | CCU notifications; encrypted |
| `6d8f2110-86f1-41bf-9afb-451d87e976c8` | Timecode | Four-byte BCD `HHMMSSFF`; encrypted |
| `7fe8691d-95dc-4fc5-8abd-ca74339b51b9` | Camera Status | Power/pair/cache flags and power writes; encrypted |
| `ffac0c52-c9fb-41a0-b063-cc76282eb89c` | Device Name | UTF-8 name, at most 32 characters |
| `8f1fd018-b508-456f-8f82-3d392bee2706` | Protocol Version | Read before feature selection; encoding is undocumented |

Camera Status is a bitmask: power `0x01`, connected `0x02`, paired `0x04`,
versions verified `0x08`, initial payload `0x10`, ready `0x20`. Writing `00`
powers off and is deliberately marked advanced in the spec; `01` powers on.

### CCU command framing

Each command has an eight-byte header, typed data and zero alignment padding:

| Offset | Width | Meaning |
|--------|-------|---------|
| 0 | 1 | Destination (`255` broadcasts) |
| 1 | 1 | Payload length **plus four**, excluding header and padding |
| 2 | 1 | Command ID (`0` = change configuration) |
| 3 | 1 | Reserved, zero |
| 4 | 1 | Category/group |
| 5 | 1 | Parameter |
| 6 | 1 | Data type |
| 7 | 1 | Operation (`0` assign, `1` offset/toggle) |
| 8… | variable | Typed elements, numeric values little-endian |

Type `0` is void/boolean, `1` int8, `2` int16, `3` int32, `4` int64, `5` UTF-8
without a terminator, and `128` signed 5.11 fixed16. Fixed16 divides the signed
little-endian integer by 2048. Pad the complete packet to a four-byte boundary
with zeros; those zeros do not count in the length byte. Unknown command IDs
are skipped by that same length-plus-alignment rule and are never decoded as
command `0`. Data types `129`–`255` and operations `128`–`255` are likewise
vendor-specific envelopes to skip, not errors. Only command `0` with known
types and operations is typed-decoded; reserved types `6`–`127` and operations
`2`–`127` remain invalid for this spec. Coalesced tests place each unknown
form before a known valid packet.

The spec includes autofocus, OIS, focus, exposure, manual white balance and a
zebra offset, with official packet examples. Camera 4.9-era gain (group 1,
parameter 1), signed-dB gain (parameter 13) and ISO (parameter 14) are separate
and gated on model/version evidence. Do not try all three as fallbacks.

Example: broadcast OIS on is
`ff 05 00 00 00 06 00 00 01 00 00 00`. The independent focused test rebuilds
that and the other vendor examples, including fixed-point signs and padding,
and exercises split, coalesced and malformed input without camera contact.

## Evidence and limits

The spec is based on Blackmagic's August 2025 developer protocol (framing and
examples on pages 96–105, BLE on pages 109–110), the March 2025 Pocket manual,
and two pinned open-source clients. No hardware was used. Notification
fragmentation, Protocol Version encoding, per-model feature versions, bond
limits, unpair/reset and firmware update details remain open.

- [Blackmagic Camera Control developer protocol (PDF)](https://documents.blackmagicdesign.com/DeveloperManuals/BlackmagicCameraControl.pdf?_v=1539929000000)
- [Pocket Cinema Camera installation and operation manual (PDF)](https://documents.blackmagicdesign.com/UserManuals/BlackmagicPocketCinemaCameraManual.pdf)
- [coral/blackmagic-camera-control](https://github.com/coral/blackmagic-camera-control/tree/46cb0fa63e2e8fb83116efccebfcb4f9b66be630)
- [coral/blackmagic-camera-protocol](https://github.com/coral/blackmagic-camera-protocol/tree/21125e3b52ee30030452e571d8e4e215df44bbe4)
