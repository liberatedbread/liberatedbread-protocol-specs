# Enphase IQ Battery (Encharge) / IQ System Controller (Enpower) — BLE

> **Status**: Discovery + encrypted status reads supported; other installer flows remain research
> **Protocol**: BLE (Digi XBee 3 BLE + Enphase relay payloads)
> **Manufacturer**: Enphase Energy
> **Manufacturer Status**: Active

## Overview

Enphase Ensemble storage units — the IQ Battery (formerly Encharge) and the
IQ System Controller (formerly Enpower) — advertise BLE beacons named
`Enpower/<serial>` and `Encharg/<serial>`. The BLE interface is provided by
the units' Digi XBee 3 radio (the same radio that runs the 2.4 GHz 802.15.4
site mesh; its Silicon Labs EFR32 base explains the Silabs OUI on the MAC).
Installers use this link to commission the units onto the site; it also
carries live statistics and control. The gateway these units report to is
documented separately in [Enphase Envoy](enphase-envoy.md).

The mobile client supports discovery, the SRP-6a/AES unlock and read-only
status queries **4, 5 and 8**. Provisioning, relay/grid control and other
installer writes are not exposed. No live hardware unlock has been performed,
so this is implementation support rather than a connection guarantee. The
recovered interface is **XBee 3**, not XBee Series 2 / "XBee2". Communications
Kit 2 has a separate, unverified GATT and credential profile and is not covered.

## Hardware

| Property | Value |
|----------|-------|
| Models | IQ Battery 3T/10T/5P (Encharge), IQ System Controller (Enpower), IQ Extender |
| Radio | Digi XBee 3 (Silicon Labs EFR32), BLE + 802.15.4 |
| BLE identity | Name `Enpower/<serial>` / `Encharg/<serial>`; MAC OUI 04:0D:84 observed live |

## Initial Setup

| Property | Value |
|----------|-------|
| Setup required | Yes — installer commissioning |
| Method | `ble_provisioning` (BLE provisioning push) |
| Advertised name | `Enpower/<serial>`, `Encharg/<serial>` |
| Passphrase protection | Four-frame SRP-6a + AES-256-CTR; reviewed Ensemble paths use `030609` |
| Confidence | medium (app-derived; only advertisement verified on hardware) |

Commissioning over BLE: connect to the XBee 3 BLE service and perform the
four-frame SRP-6a unlock (XBee API `0x2C`/response `0xAC`, user `apiservice`).
Reviewed Ensemble provisioning, existing-device link-key verification and live
data all expect `030609`; `password` is confined to separate range-test and
gateway helpers. Verify the 32-byte proof. In phase 4, bytes 32–43 are the
12-byte TX nonce for client→XBee and bytes 44–55 are the 12-byte RX nonce for
XBee→client. Use those direction-specific nonces with the 32-byte session key
for AES-256-CTR and initial remaining counter value 1. Then send User Data Relay frames carrying link key push (frame type 1,
`[0x01][0x10][16 key bytes]`), gateway serial write (type 7), and
pairing/commissioning status polls (types 4/5). The 16-byte 802.15.4 link key is
generated locally. A candidate with 13 zero bytes plus the reserved `03 06 09`
prefix is rejected; that prefix is not a fallback mesh key. Envoy serial derives
and verifies the PAN ID; no separate numeric PAN-ID write is established.

**Factory reset**: not documented. Frame type 2 (`RESET_DEV`) exists but its
effect is unverified — do not poke it on a live site. De-commissioning is
normally done via the gateway by an installer.

**Rebinding**: re-running link-key/Envoy-serial provisioning and PAN-ID
verification re-joins a unit to the site mesh in place; no reset needed.

## Protocol Summary

### BLE Services

| UUID | Name | Description |
|------|------|-------------|
| `53da53b9-0447-425a-b9ea-9837505eb59a` | Digi XBee 3 BLE | Stock XBee 3 BLE service (public Digi protocol) |
| `7dddca00-3e05-4651-9254-44074792c590` | TX | Client writes XBee API frames |
| `f9279ee9-2cd0-410c-81cc-adf11e4e5aea` | RX | Device notifies XBee API frames (CCCD 0x2902) |

XBee API frame types in play (public digi-xbee-java): `0x2C` BLE Unlock,
`0xAC` BLE Unlock Response, `0x2D` User Data Relay (client→device), `0xAD`
User Data Relay Output (device→client). After the four-frame SRP-6a unlock,
both directions use AES-256-CTR with the verified 32-byte session key and their
own 12-byte nonce. Enphase payloads ride in the relay frames' user-data field,
addressed to the radio's serial interface (micropython interface on the IQ
Extender).

### Enphase provisioning frames (inside User Data Relay)

Byte 0 = frame type. Polls are `[type, 0]`, but write byte 1 can be a length:
`[01][10][16 key bytes]` is 18 bytes, and gateway serial is length-prefixed.
Responses echo the type and carry the payload from byte 2 on.

| Type | Name | Purpose |
|------|------|---------|
| 1 | LINK_KEY | Push 16-byte site link key (`[01][10][key]`) |
| 2 | RESET_DEV | Device reset (effect unverified) |
| 3 | RELAY_STATES | Read relay states (Enpower) |
| 4 | ZB_PAIRING_STATUS | 802.15.4 pairing status |
| 5 | ZB_COMMISSIONING_STATUS | Commissioning status |
| 6 | ZB_READ_LINK_KEY | Read back stored link key |
| 7 | Gateway serial write | Write gateway serial |
| 8 | ZB_READ_ENVOY_SN | Read gateway serial (PAN ID derivation/verify) |
| 9 | READ_ENPOWER_TELEM | Read Enpower telemetry |

The gateway-serial write is `[07][one-byte serial length][serial ASCII]`, so its
total length is the gateway serial length plus two. The read requests are
`06 00` (link key), `08 00` (Envoy serial) and `09 00` (Enpower telemetry).
Responses drop those first two bytes before parsing.

### Object-model protobuf layer

A richer proto2 protocol (Wire classes in the app) shares the same relay
channel. Envelope `EnsObjMdlMessage`: `protover` (field 1, required,
VERSION_1_0), `timestamp` (field 2, required uint64), then a oneof payload at
tags 3–63: inventory (42/43), poll (13/14 — live statistics; request is
`{serial_num, dm_group_id}`), subscribe/publish (7–10), relay control
(17/18), secondary control (15/16), grid status (27/28), Encharge SoC/phase
config (32/33), sleep mode (38/39), BMU stats (40/41), manual override
(60/61), events, memfault diagnostics, and more — the full tag table is in
the spec. DeviceType enum: ALL_DEVICES=0, ENCHARGE_DEVICE=13,
ENCHARGE_MICRO=14, ENCHARGE_CTRL=15, ENCHARGE_BMU=16, ENPOWER_DEVICE=17,
ENPOWER_CTRL=18, ENBRIDGE_DEVICE=19.

Live statistics decode to per-unit records: aggregated power, state of
charge, active/ready microinverter counts, LED status, BMU state, available
charge/discharge power, and phase-line assignment, with nested per-BMU and
per-PCU statistics.

## Tools Used

- jadx decompile of Enphase Installer Toolkit 4.12.0 (`com.enphase.installer`)
- Passive BT scan of the owner's site (2026-08-18)
- Digi XBee 3 BLE documentation + digi-xbee-java (public prior art)

## References

- Digi XBee 3 BLE interface (XBee 3 user guide; digi-xbee-java `APIFrameType`)
- Machine-readable spec: `device-specs/devices/enphase-iqbattery-ble.yaml`
- Related: [Enphase Envoy](enphase-envoy.md) (gateway LAN + BLE surfaces)

## Contributors

- Liberated Bread clean-room research, 2026-08
