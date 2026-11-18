# LeakSmart Zigbee Water Valve

> **Status**: Spec available; untested on hardware
> **Protocol**: Zigbee Home Automation 1.2
> **Manufacturer**: Waxman Consumer Products Group
> **Manufacturer Status**: Shutdown

## Overview

The LeakSmart whole-home shut-off valve remains usable without the defunct
LeakSmart apps, hubs and clouds. Join it to an owner-controlled Zigbee
coordinator. Endpoint 1 uses standard HA On/Off commands, Power Configuration
battery voltage, and Appliance Events and Alerts for obstruction and self-test
outcomes.

This is not a phone-direct protocol and it is not just an On/Off switch. A safe
coordinator handler must process cluster `0x0B02`, suppress normal automations
during the valve's self-test, and never treat a CLOSED readback as proof that
water stopped. The machine-readable source of truth is
`device-specs/devices/leaksmart-valve-zigbee.yaml`; its independent tests rebuild
every example frame and exercise the safety state machine.

## Hardware

| Property | Value |
|----------|-------|
| Retail models | 8811100 / 8815000 shut-off valve; washing-machine kit 8810100 uses the same Zigbee family |
| Basic manufacturer | `WAXMAN` |
| Basic model identifiers | `House Water Valve - MDL-8810300L`, `House Water Valve - MDL-TBD`, `leakSMART Water Valve v2.10` |
| Radio | Zigbee HA, profile `0x0104`, endpoint 1 |
| Device role | Sleepy end device, **not a router** |
| Power | 9 V adapter plus 4×AA backup |
| Zigbee module | CEL ZICM357SP2; FCC ID W7Z-ZICM357SP2 (modular grant) |
| Category | `irrigation` / whole-home water shut-off valve |
| Companion apps | LeakSmart `com.waxman.mobile.volansys`; LeakSmart Classic `com.waxman.mobile` — both historical and hub/cloud-side only |

Require an exact model string as well as `WAXMAN`. Early MDL-8810300L units can
report manufacturer code `0x1002` or `0x113B`; the other two report `0x113B`.
MDL-TBD and v2.10 include an OTA client and the undecoded manufacturer cluster
`0xFC02`. The older MDL-8810300L adds Groups and Scenes and is not documented
as OTA-capable.

## Initial Setup

| Property | Value |
|----------|-------|
| Setup required | Yes — standard Zigbee joining |
| Method | `hub_pairing` to a replacement Zigbee HA coordinator |
| Vendor account | Not required |
| Passphrase protection | Not applicable; the coordinator delivers the Zigbee network key |
| Confidence | Medium — manual and public drivers, not replayed here |

1. Put the replacement coordinator into permit-join mode.
2. Rapidly press the valve's centre **Link** button **five times**. The blue LED
   should flash.
3. If nothing happens, remove adapter and battery power briefly, restore it and
   retry.
4. Confirm `WAXMAN` and an exact model string during interview.
5. Configure the standard reports, read the current alert state, and only then
   offer an attended open/close operation in a dedicated handler.
6. Recreate leak-to-close locally. Re-pairing does not preserve the old hub's
   rules, and LeakSmart's Zigbee sensors cannot bind directly to the valve.

### Factory reset

The same five-press Link action resets network membership and enters join mode.
It does not document a mechanical calibration reset. The old coordinator and
vendor cloud do not need to be alive. Rebuild reporting and local automations
after every migration. This procedure is manual- and driver-backed but was not
executed by this project.

### Rebinding to a new coordinator

Reset/leave at the valve, join the new coordinator, remove the stale entry from
the old one, and recreate leak-to-close. A separate factory data wipe is not
documented. Add a Zigbee router nearby if radio range is poor; the valve itself
does not route for other devices.

## Pairing

| Property | Value |
|----------|-------|
| Pairing required | Yes — Zigbee network join |
| Security mode | `network_join` |
| Bonding | Required; one Zigbee network at a time |
| PIN source | None |
| One central at a time | One coordinator network |
| Confidence | Medium |

Unpair through the coordinator where supported, or use the five-press reset/join
procedure. No motor operation belongs to discovery, interview or pairing.

## Protocol Summary

All multi-byte ZCL integer fields below are little-endian. General frames use
frame control `0x00` client-to-server / `0x08` server-to-client. Cluster-specific
frames use `0x01` / `0x09` respectively. The examples use invented sequence
numbers and are not radio captures.

### Clusters

| Cluster | Direction | Purpose |
|---------|-----------|---------|
| `0x0000` Basic | Server | Manufacturer/model; Power Source `0x0007` (unreliable on some firmware) |
| `0x0001` Power Configuration | Server | Battery Voltage `0x0020`; optional percentage `0x0021` has compatibility problems |
| `0x0003` Identify | Server (and client on early model) | Identify; Arcus requests 300 seconds |
| `0x0004` / `0x0005` | Server, MDL-8810300L only | Groups / Scenes |
| `0x0006` On/Off | Server | Open, close and state |
| `0x0020` Poll Control | Server | Sleepy-device polling/check-in |
| `0x0B02` Appliance Events and Alerts | Server | Obstruction and self-test events — required |
| `0xFC02` | Server, MDL-TBD/v2.10 only | Manufacturer-specific, undecoded |
| `0x0019` OTA Upgrade | Client, MDL-TBD/v2.10 only | Firmware update; no public Waxman image located |

Arcus configures Poll Control check-in at 28 quarter-seconds (7 seconds), long
poll at 20 and short poll at 2, and answers check-ins without fast polling.

### Open, close and readback

| Operation | ZCL request | Example frame | Safety |
|-----------|-------------|---------------|--------|
| Open | On/Off command `0x01`, empty payload | `01 21 01` | **Advanced, attended** |
| Close | On/Off command `0x00`, empty payload | `01 21 00` | **Advanced, attended** |
| Read state | Read Attributes, OnOff `0x0000` | `00 22 00 00 00` | Read-only |
| Read battery | Read Attributes, Battery Voltage `0x0020` | `00 23 00 20 00` | Read-only |
| Get Alerts | Appliance Alerts command `0x00` | `01 24 00` | Read-only |

On means open; Off means close. Wait **five seconds** after an attended motor
command and read OnOff again. Continue to process asynchronous reports and
alerts. Never auto-retry or reverse a suspected stalled motor, and never fire a
command merely because the device was discovered.

A Read Attributes Response carries command `0x01`, then each attribute ID,
status, data type and value. OnOff is Boolean (`0x10`), one byte: `0` closed,
`1` open. Battery Voltage is uint8 (`0x20`) in **0.1 V** units: raw `0x3C` is
6.0 V, raw `0x29` is 4.1 V. Raw `0xFF` is invalid/unknown, not 25.5 V. Check
status and type before publishing.

Suggested reporting configuration from Arcus:

| Reading | Minimum | Maximum | Change |
|---------|--------:|--------:|--------|
| OnOff | 1 s | 300 s | Boolean transition |
| Battery voltage | 3600 s | 43200 s | raw 2 = 0.2 V |
| Basic Power Source | 120 s | 43200 s | enum transition |

Prefer voltage over attribute `0x0021`: Arcus says requesting percentage can
cause problems even though the Hubitat driver configures it. Do not invent a
vendor-certified percentage curve. Arcus uses 4.1 V as an empty threshold and
6.0 V nominal for the AA pack when no device threshold is available.

### Obstruction and self-test events

For Appliance Events and Alerts commands `0x00` (Get Alerts Response), `0x01`
(Alerts Notification) and `0x02` (Events Notification), require at least two
payload bytes and interpret `payload[1]`.

- Commands `0x00`/`0x01`: zero means clear; **any non-zero value is an operation
  failure**, potentially an obstruction.
- Command `0x02` event IDs:
  - `0x80`: self-test/monthly cycle started;
  - `0x81`: operation failure;
  - `0x82`: cycle not performed;
  - `0x83`: cycle succeeded.

On `0x80`, enter cycle suppression. Record raw On/Off changes for diagnostics
but do not emit owner automations and do not actuate in response. Leave
suppression on `0x82` or `0x83`, reporting a maintenance warning or success.
On `0x81`, leave suppression, latch an obstruction and emit a safety fault — not
a normal cycle completion.

A zero alert alone does not clear a latched obstruction: require a subsequent
successful On/Off read as well. Unknown event IDs stay raw and must not be
interpreted as success. Some units may use a cadence other than monthly; the
event semantics do not depend on the wall-clock interval.

### Why CLOSED is not enough

The public Hubitat driver specifically warns that the ball can seize while the
motor still runs and the device reports CLOSED. Test actual water shut-off with
someone attending before depending on the valve for leak protection. A command
acknowledgement, state report or completed monthly cycle does not replace that
test.

## Firmware updates

MDL-TBD and v2.10 expose a Zigbee OTA client. Public driver logs name images in
the `113B-03E8` family, but no public Waxman image, signature policy, rollback
rule or interrupted-update behavior was established. The spec declares this
surface read-only and provides no generic uploader. Do not flash the unrelated
Ayla-generic Salus packages examined during research.

## Cloud and other LeakSmart hardware

Hub 2.0 used Exosite and Hub 3.0 used Ayla. Neither app speaks Zigbee directly,
and the original app route is dead. The valve needs neither cloud once joined
to a replacement coordinator. Hub 3.0 Ayla LAN recovery is conditional on
unproven firmware support and an existing owner-issued key; it is not promised
by this spec.

LeakSmart Wi-Fi sensors have no established operational local API. Zigbee leak
sensor model identity and wet/dry captures remain separate unresolved work;
this page does not silently include them. Flow-metering valve variants and
`0xFC02` are also undecoded.

## Verification and remaining work

No valve, capture, coordinator or actuation was used. All protocol facts are
`reported`; the spec remains `testing: untested`. Independent standard-library
tests cover ZCL request construction, readback type/status checks, voltage and
sentinel decoding, malformed responses, alert/event parsing, monthly-cycle
suppression and obstruction recovery.

The next useful owner-hardware check is a sanitized coordinator/sniffer capture
of join, one attended close/open with a five-second readback, and a controlled
stall that records `0x0B02` without relying on On/Off alone.

## References

- [Arcus/Iris Waxman drivers (pinned)](https://github.com/arcus-smart-home/arcusplatform/tree/a02ad0e9274896806b7d0108ee3644396f3780ad/platform/arcus-containers/driver-services/src/main/resources) — model fingerprints, command/report map, alerts/events, reset and OTA split.
- [Hubitat LeakSmart valve driver (pinned)](https://github.com/tmastersmart/hubitat-code/blob/93edf029ff0886a15b33c808fd732043cddfadfb/leaksmart-water-valve.groovy) — independent corroboration and mechanical-stall warning.
- [LeakSmart 8811100/8815000 installation and operation manual](https://hdsupplysolutions.com/wcsstore/ExtendedSitesCatalogAssetStore/product/fm/additional/30/306995_InstallationGuide-PDF.pdf) — power and five-press reset/join; HTTP 200 verified 2026-11-18.
