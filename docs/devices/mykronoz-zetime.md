# MyKronoz ZeTime

> **Status**: Spec Available (untested)
> **Protocol**: BLE GATT
> **Manufacturer**: MyKronoz
> **Manufacturer Status**: Unsupported (vendor app delisted)

## Overview

ZeTime is a hybrid analog/digital watch whose serial/info reads and time sync
work without the delisted vendor app or a cloud account. This entry covers
**ZeTime only**, not ZeFit, ZeRound or other MyKronoz families.

The machine-readable spec is `device-specs/devices/mykronoz-zetime.yaml`.
ZeTimeConnect's author reports discovery, serial/info and time sync working on
one 2017-firmware watch. Notification/weather writes and raw history were not
validated upstream, and this project has not driven a watch.

## Initial Setup and Pairing

| Property | Value |
|----------|-------|
| Setup required | No |
| Method | `ble_direct` |
| Advertised name | Prefix `ZeTime#` |
| Pairing / bond | None |
| Confidence | Medium from a working open implementation; not replayed here |

Disconnect the phone already holding the watch; a connected ZeTime normally
stops advertising. Connect and verify service
`00006006-0000-1000-8000-00805f9b34fb` and all four characteristics. Subscribe
to responses and spontaneous requests, then read the 12-byte serial before any
write. Address characteristics by UUID, not old numeric handles.

| Characteristic | Role |
|----------------|------|
| `00008001-0000-1000-8000-00805f9b34fb` | Fragmented phone message bodies, write without response |
| `00008002-0000-1000-8000-00805f9b34fb` | Phone writes `03` to commit; watch response notifications |
| `00008003-0000-1000-8000-00805f9b34fb` | Answers to watch requests; formats unresolved |
| `00008004-0000-1000-8000-00805f9b34fb` | Spontaneous music/find-phone/call requests |

**Factory reset:** unknown. The documented upper+lower-button route enters
analog calibration; it is not asserted to erase settings or history.

**Rebinding:** no account unbind or reset is needed. Disconnect the old client,
optionally forget its convenience entry, then rediscover and read serial/info.
Gadgetbridge's initial-mode guidance may help a watch stuck in its install
animation, but that path was not consistently reproduced.

## Protocol Summary

Every message uses this envelope and is committed with `03` on `8002`:

```
6f | subject:u8 | type:u8 | payload_length:u16 LE | payload | 8f
```

Split writes into at most 20-byte chunks and leave about 20 ms between chunks.
Types `70` request, `71` phone write and `80` watch response. Match a response
by subject as well as type. A notification is only a fragment: reassemble each
stream independently, reject impossible lengths/end markers and resynchronize
one byte at a time. Never merge `8002` responses with `8004` spontaneous
requests.

| Subject | Surface | Boundary |
|---------|---------|----------|
| `02` | 12-byte ASCII serial | Hardware-checked upstream |
| `04` | 12-byte local time/timezone | Hardware-checked upstream |
| `52` | Four `u16 LE` pending-history counts | Public note; raw history not collected |
| `54` / `56` / `61` | Activity / sleep / heart-rate pages | Layouts declared; full sync unverified |
| `76` | Notification type/count/UTF-8 lengths/text/timestamp | Write not validated upstream |
| `77` | Four 5-byte weather blocks and UTF-8 location | Write and later-day semantics unresolved |
| `d0` | Music commands/status | Keep spontaneous `8004` traffic separate |

The time payload is little-endian year, month/day/hour/minute/second, three
format/calibration/unit bytes, **signed timezone-hour** and absolute
**timezone-minute** bytes. UTC-09:30 encodes hour `-9`, minute `30`; do not use
the older fixed suffix that hard-codes UTC+1. Time sync does not mechanically
calibrate the analog hands.

Weather blocks are unit byte, signed current/min/max Celsius bytes and icon.
The public envelope has four blocks, but exact J+1–J+3 meaning is unknown;
repeating one forecast is not declared correct. History records remain raw
unless the spec's widths are needed: activity is 22 bytes, sleep/heart-rate 7,
all with little-endian page/epoch fields. No complete history sync is claimed.

## Out of scope

Battery read, analog-hand calibration, user profile/goals, complete `8003`
answers, firmware update and other watch models. Shared DFU constants in an
archived app are not permission to flash ZeTime.

## References

- [Gadgetbridge ZeTime protocol analysis](https://gadgetbridge.org/internals/specifics/zetime-protocol/)
- [Gadgetbridge ZeTime model/setup notes](https://gadgetbridge.org/gadgets/wearables/mykronoz/)
- [ZeTimeConnect implementation](https://github.com/BretzelCoder/ZeTimeConnect/tree/22f34c8948e48200904a36bd19d414fdf6bbbd76)

No model-specific vendor manual was established, so no manual link is offered.
