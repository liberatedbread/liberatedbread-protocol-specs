# Inkbird IBS-TH1 / IBS-TH2 Thermometer-Hygrometer

> **Status**: Complete (parser-library-derived)
> **Protocol**: BLE (passive advertisements + optional GATT poll)
> **Manufacturer**: Inkbird
> **Manufacturer Status**: Active

## Overview

Cheap battery BLE temperature/humidity sensors (IBS-TH1, IBS-TH2, and the
IBS-P01B pool thermometer) that broadcast every reading in BLE
advertisements — no connection, pairing or account needed. Documented from
the Bluetooth-Devices/inkbird-ble parser library (which backs the Home
Assistant core `inkbird` integration) and its capture-pinned test suite,
plus a jadx decompile of the official Engbird app v2.3.9
(`com.inkbird.engbird`) which confirmed the layouts and documented the
connected-mode characteristics. The older `com.inkbird.inkbird` package is
delisted from Google Play and all public mirrors as of 2026-08.

## Hardware

| Property | Value |
|----------|-------|
| Model Number | IBS-TH1, IBS-TH2, IBS-P01B |
| Radio | BLE 4.x (legacy advertising) |
| Advertised name | `sps` (IBS-TH1), `tps` (IBS-TH2/P01B) |
| Advertised service | `0000fff0-0000-1000-8000-00805f9b34fb` |

## Initial Setup

| Property | Value |
|----------|-------|
| Setup required | No |
| Method | `ble_direct` (passive scan) |
| Setup AP / advertised name | `sps` / `tps` |
| Passphrase protection | not_applicable |
| Confidence | high (production parser library + captured advertisements) |

**Factory reset**: none documented, and none needed — the device holds no
credentials or bindings. Removing the battery for 10+ seconds is the only
meaningful reset.

**Rebinding**: in place, trivially. The sensor is broadcast-only; any client
can listen, and switching controllers is just scanning from the new one.

## Protocol Summary

Advertisement quirk: **there is no company ID** — the temperature occupies
the company-ID position of the manufacturer-data AD structure, so BLE stacks
report the temperature itself as the "manufacturer id" and every new reading
looks like a new manufacturer-data entry. Match on name + service UUID +
9-byte length, never on a company id.

### Manufacturer data (9 bytes, on-air AD content)

| Offset | Length | Description |
|--------|--------|-------------|
| 0 | 2 | Temperature, s16 LE, /100 °C (`fc 07` → 0x07FC → 20.44 °C) |
| 2 | 2 | Humidity, u16 LE, /100 % (`c7 12` → 48.07 %) |
| 4 | 1 | Channel-layout selector (0-3) — picks which bytes carry internal vs external-probe values |
| 5 | 2 | Secondary channel value, s16 LE, /100 (external temp or humidity per the selector byte) |
| 7 | 1 | Battery percent (`0x56` → 86) |
| 8 | 1 | Onboarding route: `0x06` connects for one live `fff2` read; other values, including `0x08`, stay advertisement-only |

Byte 8 is a client-routing flag, not evidence of a hardware revision. Example
frame `fc 07 c7 12 00 c8 3d 56 06` → 20.44 °C, 48.07 %, 86 %, with the
connected-onboarding route. Decoded humidity above 100 % marks a corrupt
packet — drop it whole.

### BLE Services

| UUID | Name | Description |
|------|------|-------------|
| `0000fff0-0000-1000-8000-00805f9b34fb` | Inkbird Sensor Service | Shared with the iBBQ family — not sufficient for identification |
| `0000fff2-0000-1000-8000-00805f9b34fb` | Sensor data (read) | Optional poll: temp s16 LE /100 @ bytes 0-1, humidity @ bytes 2-3, probe indicator @ byte 4; no battery byte |
| `0000fff1-0000-1000-8000-00805f9b34fb` | Config (read/write) | 16-byte block: calibration offsets (x0.01) @ 1-2/3-4/5-6, logging interval u32 LE seconds @ 7-10, firmware version chars @ 11/13, CRC16-Modbus of bytes 0-13 @ 14-15 on writes |
| `0000fff6-0000-1000-8000-00805f9b34fb` | History data (notify) | Compressed endpoints plus raw remainder, 20-byte notification padding, CRC16 trailer |
| `0000fff8-0000-1000-8000-00805f9b34fb` | History command (write) | 2/1/7 = temp header/content/CRC; 4/3/8 = humidity header/content/CRC |
| `0000fff9-0000-1000-8000-00805f9b34fb` | Control (write) | `0x01` clear logged history, `0x06` graceful disconnect |

For `count` history samples, each complete group of ten becomes two signed
little-endian endpoints. Thus `compressed_len = ((count - count % 10) / 10) *
4`. The compressed bytes are zero-padded to 20-byte notification boundaries;
the raw signed-LE remainder (`count % 10` samples) starts at
`ceil(compressed_len / 20) * 20`, not at `compressed_len`. Reassemble the
meaningful compressed bytes followed immediately by the meaningful remainder
and CRC16-Modbus only those bytes—never the notification padding. The separate
six-byte header is `count u32le` plus CRC16 of its first four bytes.

### Firmware update (reported, not hardware-tested)

SHB accepts Intel HEX (`.hex`/`.hex16`). On the normal device, an acknowledged
write of `01 02` to `5833ff02-9b8b-5191-6142-22a4536ef123` requests OTA entry
for those images (`01 03` selects resource images). The app then disconnects
and rescans for `PPlusOTA` at the normal address with its last octet
incremented modulo 256: `(last + 1) & 0xff` (`ff` → `00`). SHB
uses service `5833ff01-9b8b-5191-6142-22a4536ef123`, command `…ff02…`, notify
`5833ff03-…`, and no-response bulk data `5833ff04-…`. SLB accepts raw binary
and uses service `0000feb3-0000-1000-8000-00805f9b34fb`, acknowledged command
`0000fed5-…`, no-response data `0000fed7-…`, and notify `0000fed8-…`.

Firmware URLs come from `POST https://api-inkbird.com/api/bleDevice/firmware`.
Do not infer that OTA UUIDs are advertised or that images are unsigned:
advertisement contents and signature enforcement remain unknown.

Note the fff0 service is shared with the iBBQ BBQ thermometers
(spec `device-specs/devices/ibbq-meat-thermo.yaml`), and the
IBT/IBBQ-4BW line uses a completely different `0000ff00` ASCII-hex protocol
(spec `device-specs/devices/inkbird-bbq-thermometer.yaml`).
Discriminate by name + manufacturer-data length + service UUID.

## Tools Used

- [ ] Bluetooth-Devices/inkbird-ble parser + tests (no hardware capture done here)
- [ ] jadx decompile of Engbird v2.3.9 (`com.inkbird.engbird`) — layout confirmations, fff1/fff6/fff8/fff9, OTA

## References

- [Bluetooth-Devices/inkbird-ble](https://github.com/Bluetooth-Devices/inkbird-ble)
- [Ernst79/bleparser inkbird.py](https://github.com/Ernst79/bleparser/blob/c42ae922e1abed2720c7fac993777e1bd59c0c93/package/bleparser/inkbird.py)
- [ble_monitor](https://github.com/custom-components/ble_monitor)
- [Home Assistant inkbird integration](https://www.home-assistant.io/integrations/inkbird)

## Contributors

- @kimi - spec from third-party parser sources
