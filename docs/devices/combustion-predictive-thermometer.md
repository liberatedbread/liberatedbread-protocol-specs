# Combustion Predictive Thermometer (Probe V1 / V2+)

> **Status**: Spec Available (source-derived, untested)
> **Protocol**: BLE GATT and passive manufacturer advertisements
> **Manufacturer**: Combustion Inc.
> **Manufacturer Status**: Active

## Overview

The Predictive Probe contains eight thermistors and works directly with a
phone; a cloud account is optional. Passive advertisements carry current
temperatures, Probe Status adds logs/prediction/alarms, and a UART service
provides commands. This page covers **Probe V1 and V2+ only**.

MeatNet Display/Booster nodes, Giant Grill Gauge and Engine use separate
profiles. Their data must not be fed into the Probe parser just because they
share the Nordic UART UUID. Product type `1` selects a Probe; type `2` is
repeated MeatNet data, and types `3`–`6` are the other products.

## Initial Setup

| Property | Value |
|----------|-------|
| Setup required | No |
| Method | `ble_direct`; passive scan or connect |
| Advertised service | `00000100-caab-3792-3d44-97ae51c1407a` |
| Manufacturer ID | `0x09c7`, product type `1` |
| Pairing | None |
| Confidence | Medium — public DRAFT specification plus source review |

Remove the probe from its charger. It advertises continuously and accepts up
to three BLE connections, becoming unconnectable when all three are occupied.
Normal advertisements are about 250 ms apart; Instant Read repeats 100/100/50
ms delays. Subscribe to Probe Status, and subscribe to UART TX before any RX
request.

Probe V1 uses normal radio power (`+0 dBm`). V2+ uses `+8 dBm` when the high
radio-power preference bit is set. At the same distance, V2+ can therefore
show roughly 8 dB stronger RSSI; that is not a protocol-generation test by
itself. Read model/hardware/firmware information when selecting behavior.

**Factory reset**: unknown. UART type `0x0a` resets only the current cook:
prediction and log buffers are cleared and a new session starts immediately.
It is an advanced, destructive action in the spec, not a factory reset or bond
wipe.

**Rebinding**: no bond or network membership exists. A new client can scan or
connect whenever a connection slot is free; close one existing client if all
three slots are occupied.

## Protocol Summary

### BLE Services

| UUID | Name | Description |
|------|------|-------------|
| `0000180a-0000-1000-8000-00805f9b34fb` | Device Information | Manufacturer, model, serial, hardware and firmware |
| `00000100-caab-3792-3d44-97ae51c1407a` | Probe Status service | Current status container |
| `00000101-caab-3792-3d44-97ae51c1407a` | Probe Status | Read/notify 94-byte old or 100-byte new status |
| `6e400001-b5a3-f393-e0a9-e50e24dcca9e` | UART transport | Probe requests/responses, not MeatNet framing |
| `6e400002-b5a3-f393-e0a9-e50e24dcca9e` | UART RX | Client writes requests |
| `6e400003-b5a3-f393-e0a9-e50e24dcca9e` | UART TX | Read/notifications from probe |

### Temperature and status

The temperature block is 13 bytes: eight consecutive unsigned 13-bit values
in one little-endian 104-bit integer. For thermistor `i` from 1 through 8:

```text
raw = (int.from_bytes(block, "little") >> (13 * (i - 1))) & 0x1fff
temperature_c = raw * 0.05 - 20
```

The documented measurement range is -20 through 369 °C (`raw <= 7780`); reject
larger values. In Instant Read only T1 is valid. The zeroes in T2–T8 are
placeholders, not real -20 °C readings.

Probe Status starts with two little-endian uint32 log sequence numbers, then
the 13 temperature bytes. Subsequent blocks carry mode/ID, battery/virtual
sensors, prediction, food-safety configuration/status, overheating,
preferences, eleven high-alarm records and eleven low-alarm records. Every
alarm record is uint16 LE: set/tripped/alarming in bits 0–2, temperature in
bits 3–15 as `raw * 0.1 - 20 °C`. Record order is T1–T8, Core, Surface,
Ambient.

Older firmware stops after the low-alarm array at **94 bytes**. Current status
adds a uint32 LE session ID and uint16 LE sample period in milliseconds for
**100 bytes**. Missing or zero session IDs are normal, including the initial
notification after subscribing. Prediction fields are packed least-significant
bit first: state/mode/type, setpoint and heat-start in 0.1 °C, a 17-bit seconds
value, and estimated core as `raw * 0.1 - 20 °C`.

### UART framing

```text
request:  ca fe | crc16 LE | type | payload length | payload
response: ca fe | crc16 LE | type | success | payload length | payload
```

CRC is CRC-16/CCITT-FALSE (polynomial `0x1021`, initial `0xffff`, no
reflection or final XOR), stored little-endian. Request coverage is type,
length and payload. Response coverage additionally includes the success byte.
Read the stream until `7 + payload_length` bytes are available, verify CRC,
then handle any coalesced next frame. Do not assume a notification boundary
is a response boundary, and do not import MeatNet's longer headers or Hunter's
JSON fragmenter.

The spec defines session reads, bounded log reads, packed prediction setting,
over-temperature read, high/low alarm configuration and alarm silencing.
Examples include `ca fe 5c 48 03 00` for session information and
`ca fe ca 21 03 01 06 78 56 34 12 e8 03` for a successful response with an
invented session and 1000 ms period. Its focused standard-library test checks
packed sensors, old/new status, prediction/alarm fields, CRC, and split,
coalesced and malformed UART data.

## Evidence and limits

The vendor specification is explicitly **DRAFT**. This spec uses its pinned
public version, vendor app 3.3.13 static review for endian/CRC behavior, and a
pinned community integration for the thermistor decoder. No probe was driven.
Request segmentation above the ATT payload, log pacing, exact model/version
strings, food-safety validation and DFU remain open. The Nordic UART service
is not evidence of a DFU bootloader interface.

- [Predictive Probe BLE specification (pinned)](https://github.com/combustion-inc/combustion-documentation/blob/89f2f24d1563b5279dee8b1ef23bac2beeddca85/probe_ble_specification.rst)
- [MeatNet Node BLE specification (pinned)](https://github.com/combustion-inc/combustion-documentation/blob/89f2f24d1563b5279dee8b1ef23bac2beeddca85/meatnet_node_ble_specification.rst)
- [legrego/homeassistant-combustion](https://github.com/legrego/homeassistant-combustion/tree/1e6764dd38b9b36ee0caea92d7c07611fde731f6)
- [Combustion vendor FAQ](https://combustion.inc/pages/faq)
