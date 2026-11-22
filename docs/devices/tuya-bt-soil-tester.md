# Tuya Bluetooth Soil Tester (zwjcy / SGS01 family)

> **Status**: Spec available; stock encrypted session is identify-only and untested
> **Protocol**: BLE (Tuya BLE single-point, encrypted GATT session)
> **Manufacturer**: Tuya (platform) / Shenzhen HaiHao Electronic (canonical SGS01) + white-label clones
> **Manufacturer Status**: Active

## Overview

The "Tuya Smart Bluetooth Soil Tester / Smart Plant Soil Tester" listings on
Amazon/AliExpress are one Tuya OEM family. The canonical hardware is the
**SGS01** (a.k.a. HZ-SL05, "Connected Home PLANT MONITOR") by Shenzhen HaiHao
Electronic — a 2×AAA probe measuring soil moisture and temperature, marketed as
"works with Alexa & Google". Tuya device category `zwjcy` (soil sensor / plant
monitor) has **no official public DP documentation**; everything below is
community-derived. Near-identical units are certified under category `wsdcg`
with different DP numbering.

It is reverse engineered because Tuya publishes nothing and the stock device
speaks an encrypted session keyed by cloud-issued credentials. SGS01BTHome
offers a cloud-free replacement for SGS01 and a **development** image for
SGS01B; the latter is not production-ready.

## Hardware

| Property | Value |
|----------|-------|
| Model Number | SGS01 / HZ-SL05: `gvygg3m8` (current), `aao3yzhs` (older); SGS01B: `gpkyrocn` |
| Chipset | SGS01: Tuya BT3L; SGS01B: Tuya BTU; both Telink TLSR8250 with 512 KB flash, plus a separate measurement MCU |
| Radio | BLE (single-point, connectable; NOT mesh, NOT passive beacon) |
| FCC ID | None at device level for the white-label goods |

Internals per the haraldapp/SGS01BTHome teardown: the Tuya module owns the
radio and runs stock Tuya BLE firmware; a third-party MCU owns measurement,
button and LED over a Tuya MCU serial UART. Flashing pads are Vcc/GND/SWS
(Telink single-wire, chip type B85); flash above 0x70000 holds factory
MAC/calibration — preserve it when reflashing. SGS01B uses the BTU module, not
BT3L or the ambiguous “BTH” label previously recorded here.

## Initial Setup

| Property | Value |
|----------|-------|
| Setup required | Yes (pairing is mandatory; nothing is readable unpaired) |
| Method | `ble_provisioning` (vendor app + Tuya cloud account), then `ble_direct` with extracted keys |
| Setup AP / advertised name | Manual product selection; classic ≤3 service-data `0xA201`, protocol-4 service-data `0xFD50`, both + manufacturer data `0x07D0` |
| Passphrase protection | not_applicable (BLE; local-key secret + six-byte device_random KDF) |
| Confidence | medium (community implementations + Smart Life SDK decompile; not replayed by this project) |

Stock pairing happens in Smart Life / Tuya Smart with a Tuya cloud account,
which issues the device id and 16-character local key. BLE v3 uses the first
six local-key characters as `secret`: `login_key = MD5(secret)` and
`session_key = MD5(secret || six-byte device_random)`. PAIR carries UUID,
secret and device ID padded to 44 bytes, but UUID is not a session-key input.
For third-party local access, extract the device ID and local key once via a
Tuya IoT developer account (tuya-iot-py-sdk / ha_tuya_ble automate it).

**Factory reset**: remove the device in the vendor app — the app drives an
UNBIND (function code `0x0005`) or DEVICE_RESET (`0x0006`) frame over GATT and
the device returns to pairing-mode advertising. A physical button-hold reset
likely exists (generic Tuya BLE behaviour) but is undocumented for this family —
unverified. Flashing SGS01BTHome over SWS removes Tuya state. Use the stable
SGS01 image only on SGS01; SGS01B has a separate **V1.1Pre2 development image**
which is not production-ready and needs its BTU-specific precautions.

**Rebinding to a new account**: unbind + re-pair; a new device id / local key
pair is issued. There are no network credentials to rotate (the device is
BLE-only).

## Protocol Summary

Advertisements carry device identity only — never sensor readings (ble_monitor
confirms SGS01 cannot be supported passively). **Manual product selection is
required** because the generic BLE schema/mobile matcher has no `service_data`
key. The maintained implementation uses `0xFD50` service data for protocol 4
and falls back to `0xA201` for classic ≤3, both with company ID `0x07D0`.
Those are advertisement records, not advertised GATT service UUIDs and not
soil-specific identity. Confirm product ID and protocol/GATT layout before a
session. All state moves as encrypted Tuya DP frames over protocol-specific
GATT:

### BLE Services

| Protocol | Service | Write | Notify |
|----------|---------|-------|--------|
| ≤3 | `00001910-0000-1000-8000-00805f9b34fb` | `00002b11-0000-1000-8000-00805f9b34fb` | `00002b10-0000-1000-8000-00805f9b34fb` |
| 4 | `0000fd50-0000-1000-8000-00805f9b34fb` | `00000001-0000-1001-8001-00805f9b07d0` | `00000002-0000-1001-8001-00805f9b07d0` |

Do not combine protocol 3 with the protocol-4 service, or put `0x2B11`/`0x2B10`
on `0xFD50`. Select the endpoint set from the reported protocol version before
PAIR or OTA. The v3 KDF above is not generalized to protocol 4.

Default ATT MTU 20; frames are chunked/reassembled by the protocol layer. The
full packet framing (sequence numbers, ACKs, encryption) is implemented in
[python-tuya-ble](https://github.com/PlusPlus-ua/python-tuya-ble) and is
deliberately not restated here — treat it as the executable reference for v3,
not proof of a protocol-4 session.

### Commands

Commands are function codes inside the encrypted frame. The v3 set is
`0x0000` DEVICE_INFO, `0x0001` PAIR, `0x0002` DPS query/set, `0x0003`
DEVICE_STATUS, `0x0005`/`0x0006` UNBIND/DEVICE_RESET and `0x000C..0x0010`
OTA. Device-to-host reports are `0x8001` and time requests are
`0x8011`/`0x8012`. PAIR carries UUID + secret + device ID padded to 44 bytes,
but the session KDF uses secret + device_random, not UUID.

Protocol 4 has separately reported DPS_V4 `0x0027` and DP-report-V4 `0x8006`
on its own endpoints. Those codes do not make the v3 one-byte DP length or KDF
applicable to protocol 4.

BLE v3 DP types: RAW=0, BOOL=1, VALUE=2, STRING=3, ENUM=4, BITMAP=5. Records
are `[dp id u8][type u8][length u8][payload]`. VALUE and ENUM decode as signed
big-endian integers of the declared length; VALUE writes use signed four-byte
big-endian. DP_V4 is not generalized. Vector
`05 02 04 ff ff ff f6 03 02 04 00 00 00 32` decodes DP5 = -10 (-1.0 °C) and
DP3 = 50 (% moisture).

### DP map (zwjcy, product `gvygg3m8`) — reported, not byte-verified

| DP | Cloud code | Type | Meaning |
|----|-----------|------|---------|
| 3 | `humidity` | value 0–100 % | Soil moisture |
| 5 | `temp_current` | value, ÷10 | Temperature, °C |
| 14 | `battery_state` | enum low/normal/high | Coarse battery |
| 15 | `battery_percentage` | value % | Battery |

SGS01B (`gpkyrocn`) has a community descriptor with the same DP IDs and
scaling. Keep that as a per-model **reported** boundary: neither this DP map nor
the v3 session behavior has been replayed by this project on SGS01B.

`wsdcg`-category variants: `ojzlzzsw` uses temp DP 1 (÷10), moisture DP 2,
battery-state DP 3, battery-% DP 4; `tv6peegl` uses temp DP 101, moisture
DP 102, no documented battery DPs.

## Hub / cloud

Phone nearby: direct BLE, no hub. Remote access / Alexa / Google / cloud
automations: requires a Tuya Bluetooth (or multi-mode) gateway. Without Tuya
cloud, stock firmware cannot be (re)paired — the local key is cloud-issued —
but an already-paired unit with extracted keys keeps working locally forever
(ha_tuya_ble). SGS01BTHome removes keys, pairing and cloud on SGS01. For
SGS01B, only the V1.1Pre2 development image is available; do not describe that
work-in-progress as a production-ready rescue path.

## Tools Used

- [ ] jadx decompile of Smart Life 7.9.0 (BLE SDK transport constants)
- [ ] Community sources: python-tuya-ble, garnser/ha_tuya_ble, haraldapp/SGS01BTHome, Home Assistant Tuya integration

## References

- [python-tuya-ble — protocol reference implementation](https://github.com/PlusPlus-ua/python-tuya-ble)
- [garnser/ha_tuya_ble — local BLE integration with DP maps](https://github.com/garnser/ha_tuya_ble)
- [haraldapp/SGS01BTHome — teardown + BTHome replacement firmware](https://github.com/haraldapp/SGS01BTHome)
- [ble_monitor issue #1161 — no passive broadcast](https://github.com/custom-components/ble_monitor/issues/1161)
- [HA issue #93536 — zwjcy cloud schema](https://github.com/home-assistant/core/issues/93536)
- [HA discussion #949 — product id lineage](https://github.com/home-assistant/core/discussions/949)

## Contributors

- Liberated Bread clean-room research — initial spec
