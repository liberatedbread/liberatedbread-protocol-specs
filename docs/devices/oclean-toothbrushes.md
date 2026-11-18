# Oclean BLE Smart Toothbrushes

> **Status**: Spec Available (untested here; upstream X/Air 1 core evidence)
> **Protocol**: BLE GATT
> **Manufacturer**: Oclean / Zhuhai Ice Bear Smart Home Technology
> **Manufacturer Status**: Active

## Overview

Oclean brushes can synchronize battery, model/firmware, clock and session records
directly over BLE without an Oclean account. The protocol has incompatible model
families, so a client must read the exact Device Information model ID before any
command write.

Upstream reports tested core sync on Oclean X (`OCLEANY3M`, including the Y3MH
hardware variant) and battery/core behavior on Air 1 (`OCLEANA1`). Other models
are partial. This project did not connect to a brush or collect real brushing
history; all vectors in the new spec and tests are invented.

## Initial Setup

| Property | Value |
|----------|-------|
| Setup required | No for core local BLE sync |
| Method | `ble_direct` after exact model selection |
| Passphrase protection | `not_applicable` |
| Confidence | Medium; model-specific evidence varies |

Close Oclean Care + before polling. It can hold notification subscriptions and its
own sync can clear or race the brush's session buffer. Poll, then disconnect.

**Factory reset**: No reset procedure is offered. Factory-reset and brush-head
reset writes are excluded from safe sync and are never used for discovery.

**Rebinding**: Disconnect the old client, read the model ID again and use the same
route. No network rejoin or new credential is needed, but previously buffered
sessions are not guaranteed to survive another client's sync.

## Pairing

The upstream X/Air 1 local clients need no pairing, bonding or account. ATT
permissions on partial models and Type F are not asserted.

## Mandatory Model Routing

| Route | Exact model IDs / status | Command path |
|-------|--------------------------|--------------|
| Type 0 | Reserved; no confirmed current production mapping. **OCLEANY3M and OCLEANY3 are not Type 0.** | Time `020e` and status/device/session `0303`/`0202`/`030201`/`0308` on `fbb85`; older pages `0309`; notify `fbb86` plus change-info |
| Type 1 | `OCLEANY3M`, `OCLEANY3MH`, X Pro/Elite families, `OCLEANA1e/f`, `OCLEANY2` on firmware >=1.0.0.4, and the full list in the YAML | Time `0201` on `fbb85`; ordinary queries and `0307` on write-only `fbb89`; notify `fbb86` and `fbb90`; no `0309` |
| Type Z1 | `OCLEANY5` | Time and ordinary queries on `fbb85`; sessions `0307` on `fbb89`; notify `fbb86` and `fbb90` |
| Air 1 legacy | `OCLEANA1`, `OCLEANA1a`–`d` | Type 0 time, ordinary queries on `fbb85`, sessions on `fbb89`; direct reads from `fbb86` when it has no CCCD |
| Type F | Separate Wi-Fi-capable family; no model mapping or sync claim | Service `0000aaaa-0000-1000-8000-00805f9b34fb`, reserved write `0000bbb2-0000-1000-8000-00805f9b34fb`, notify `0000bbb3-0000-1000-8000-00805f9b34fb`; no fallback from standard models |

Unknown model IDs fail closed in this spec; do not send speculative Type 1
commands. `fbb89` is write-only on tested Type 1 units, so never subscribe to it.

Air 1 fallback: after the route queries, wait 1.5 seconds and directly read
`fbb86` up to six times at one-second intervals. `0302` payload byte 0 is a
battery fallback. Empty reads are not sessions.

## Core Data and Session Framing

- **Battery**: standard one-byte Battery Level, `0303` payload byte 3, and `0302`
  payload byte 0 as model-specific fallbacks. Values above 100 are invalid.
- **Device settings**: `030201` returns `0302`. The current layout has bind state
  at payload byte 4 and mode at byte 5, clock at 16–21, timezone-table index at
  24, and brush-head counters through byte 31. Do not apply the older byte-6/byte-8
  bind/mode layout.
- **Time**: Type 0/Air 1 use `020e` plus uint32 big-endian Unix seconds. Type 1/Z1
  use `0201` plus local YY MM DD HH mm ss, Sunday-zero weekday and a 1-based index
  into the YAML's 33-entry timezone table.
- **Simple `0308`**: year/date/time, signed quarter-hour timezone, programme ID,
  little-endian brush-head wear and pressure. Core fields require 18 bytes; the
  complete record is 20.
- **Extended `0308`**: a big-endian record length of at least 32, then durations,
  raw pressure/zone values, timezone, score and scheme fields. Never reinterpret a
  failed extended header as a simple record.
- **Type 1 inline `0307`**: `0307 | *B# | count_u16be | inline data`. Count zero
  with nonzero year supplies only the inline core; clear stale score/area/pressure
  enrichment instead of carrying it over.
- **Type 1 fragmented X records**: after that header, append raw continuation
  bytes until `count × 42` record bytes exist. There is **no record-length word**
  in the tested profile. Flush only complete records and drop a final partial one.
  Durations are scheduled/valid big-endian seconds; use valid when plausible.
- **Y3MH `XX03`**: score in byte 0, `03 03` at 1–2, five `ff` bytes at 4–8, then
  local date/time, programme and reported duration. The last two bytes are not a
  verified valid-duration substitute.

Programme IDs have no offline name mapping. Scores, pressure, zone values and
coverage are not medical or dental-health conclusions. Polling the `0303` status
byte does not reliably detect every short active-brushing interval.

`scripts/test_oclean_toothbrushes_spec.py` independently checks routing, time
encodings, layouts, fragmentation, duplicate handling, malformed records and the
Air 1 fallback contract without real health history.

## Out of Scope

Type F sync and Wi-Fi provisioning, cloud account APIs, programme-name lookup,
settings/programme writes, calibration, factory/brush-head resets, OTA, real-time
active-brushing detection and every unverified model-specific record variant. No
model-specific official manual was verified.

## References

- [deniskie/ha-oclean-integration](https://github.com/deniskie/ha-oclean-integration)
- [Oclean Home Assistant community discussion](https://community.home-assistant.io/t/custom-integration-oclean-toothbrush/989627)
- [Oclean Care + on Google Play](https://play.google.com/store/apps/details?id=com.yunding.noopsychebrushforeign)
