# Pine64 PineTime with InfiniTime 1.16.0

> **Status**: Spec Available (untested)
> **Protocol**: BLE GATT, with client and server roles on both watch and companion
> **Manufacturer**: Pine Store Limited (PINE64)
> **Manufacturer Status**: Active

## Overview

PineTime can be controlled locally by several open companions without a Pine64
account. This spec is deliberately limited to **InfiniTime 1.16.0**. Proprietary
factory firmware, other open firmware and other InfiniTime versions are not
covered.

The machine-readable spec is `device-specs/devices/pinetime-infinitime.yaml`.
No watch was connected or updated from it.

## Hardware

| Property | Value |
|----------|-------|
| Model | Pine64 PineTime, sealed or developer kit when running InfiniTime 1.16.0 |
| SoC / radio | Nordic nRF52832, Bluetooth 5.0 LE |
| Advertised name | Exactly `InfiniTime` |
| Firmware check | Read `00002a26-0000-1000-8000-00805f9b34fb`; require `1.16.0` |
| FCC ID | 2AWAG-PINETIME |
| Companion | Gadgetbridge, InfiniLink or another open client |

## Initial Setup and Pairing

No provisioning, account or bond is required. Disconnect the old companion,
scan, and read Firmware Revision **before any write**. Subscribe to needed watch
notifications. DFU and BLE FS may additionally be disabled in watch settings;
enable them only for a deliberate operation, preferably until reboot.

**Rebinding:** disconnect the old companion and repeat the firmware and role
checks. No account unbind or reset is needed.

**Factory reset:** not established for InfiniTime 1.16.0. Reboot, firmware
rollback and firmware validation are not factory resets.

## BLE roles are bidirectional

| Surface | Watch role | Companion role |
|---------|------------|----------------|
| CTS `00001805-0000-1000-8000-00805f9b34fb` | Hosts read/write Current Time | Also hosts a service that the watch discovers and reads |
| ANS `00001811-0000-1000-8000-00805f9b34fb` | Accepts New Alert writes and emits custom call events | Also hosts New Alert; the watch discovers and subscribes to it |

Thus a phone cannot merely scan the watch's services and consider time/alerts
complete. For the reverse path, host CTS/ANS on the phone and let the watch act
as GATT client. Current Time is ten bytes: little-endian year, six calendar
bytes, weekday, fractions256 and adjust reason. ANS is category, count, NUL,
then NUL-separated text. Call event `00020001-78fc-48fe-8e23-433b3a1942d0`
notifies 0 decline, 1 accept or 2 mute.

## Watch-hosted surfaces

| Surface | Important details |
|---------|-------------------|
| Battery | `00002a19-0000-1000-8000-00805f9b34fb`, one-byte percentage, read/notify |
| Heart rate | `00002a37-0000-1000-8000-00805f9b34fb`; parse SIG flags, not always two bytes |
| Music | Events `00000001-78fc-48fe-8e23-433b3a1942d0`; status/metadata on siblings |
| Navigation | Icon, narrative, maneuver distance and `uint8` progress on `00010000-78fc-48fe-8e23-433b3a1942d0` |
| Motion | Steps `uint32 LE`; X/Y/Z `int16 LE`, 1024 raw units = 1 g |
| Simple Weather | `00050001-78fc-48fe-8e23-433b3a1942d0`; current v0/v1 and forecast v0 |
| BLE FS | Version `adaf0100-4669-6c65-5472-616e73666572`, transfer `adaf0200-4669-6c65-5472-616e73666572` |
| Legacy DFU | Control `00001531-1212-efde-1523-785feabcd123`, packet `00001532-1212-efde-1523-785feabcd123` |

Simple Weather is the **only** weather layout here; legacy `00040000` is not a
fallback. All multibyte weather integers are little-endian. Current v0 is 49
bytes, current v1 53 with signed sun minutes, forecast v0 36 with five 5-byte
slots. Temperatures are signed `int16` in 0.01 C, locations 32 zero-padded UTF-8
bytes, and forecasts have at most five days. Reject unknown type/version or a
short packet before reading it.

BLE FS v4 commands are read `10`/continue `12`, write `20`/continue `22`,
delete `30`, mkdir `40`, list `50` and move `60`. Responses use `11`, `21`,
`31`, `41`, `51`, `61`; all integer fields are little-endian. Status is signed:
`01` success, negative LittleFS errors. Paths are absolute UTF-8 without a NUL.
Read/list first; file writes/mkdir/delete/move are advanced and optional.

DFU follows nine documented stages: start, three image sizes, init packet,
receipt interval, image chunks, validate and activate. After the start
acknowledgement, request init parameters, **write the matching `.dat` first,
send `02 01` second, and only then wait for `10 02 01`**. Data segments are at
most 20 bytes and receipt counts are little-endian `uint32`. Use only matching
official `.bin` + `.dat`, stop on any missed receipt/CRC failure, and validate
firmware in settings afterward or the previous image may boot. Every update
step is advanced and unverified here.

The complete flow is documentary only. No generic DFU commands, initialization,
bare framing or byte-parameter writes are exposed: one dedicated updater must
own notifications, sequencing, image bytes, receipts, CRC and recovery before
any write is attempted.

## Limitations

Steps are advertised mainly while the screen is on, so this is not reliable
historical activity storage; sleep sync is not claimed. No general factory
reset, maximum-central count or interrupted-DFU recovery was established.

## References

- [InfiniTime 1.16 BLE overview](https://github.com/InfiniTimeOrg/InfiniTime/blob/9ad16304f5fd526b781a760cf1313813d232645e/doc/ble.md)
- [Simple Weather](https://github.com/InfiniTimeOrg/InfiniTime/blob/9ad16304f5fd526b781a760cf1313813d232645e/doc/SimpleWeatherService.md)
- [BLE FS](https://github.com/InfiniTimeOrg/InfiniTime/blob/9ad16304f5fd526b781a760cf1313813d232645e/doc/BLEFS.md)
- [PineTime quick-start guide](https://wiki.pine64.org/wiki/Special:Redirect/file/PineTime_Quick_Start_Guide.pdf)
- [Gadgetbridge PineTime notes](https://gadgetbridge.org/gadgets/wearables/pine64/)
