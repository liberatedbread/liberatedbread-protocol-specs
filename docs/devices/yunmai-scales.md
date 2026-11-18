# YUNMAI Mini / SE / X / Mini 2S

> **Status**: Spec Available (untested; one sanitized public Mini 2S capture)
> **Protocol**: BLE connected GATT or passive broadcast, depending on model
> **Manufacturer**: YUNMAI
> **Manufacturer Status**: Active

## Overview

YUNMAI scales can report weight and impedance without a vendor account. The
protocol is **not shared across the range**:

| Model | Transport and identity |
|-------|------------------------|
| Mini | GATT; `YUNMAI-SIGNAL*`, `YUNMAI-ISM*`, `YUNMAI-ISC2P*`, exact `YUNMAI-Scale-3` |
| SE | GATT; `YUNMAI-ISSE*` |
| X `YMBS-M268` | Nameless broadcast, service `00001320-0000-1000-8000-00805f9b34fb`, signature `0b 74 17` |
| Mini 2S `M1827CH` | Same broadcast layout, signature `06 52 11` |

Mini 2 Wi-Fi, Mini 2, Color, Pro, 3G and other regional models in the vendor
app are not automatically supported. The machine-readable spec is
`device-specs/devices/yunmai-scales.yaml`. No new measurement was collected.

## Setup, pairing and privacy

No pairing, bond, Wi-Fi or account is used. For X/Mini 2S simply step on the
scale and listen. For Mini/SE, connect and subscribe to
`0000ffe4-0000-1000-8000-00805f9b34fb`, write an owner-selected profile/time
on `0000ffe9-0000-1000-8000-00805f9b34fb`, query protocol version, then step on.

Persist the connected profile's nonzero 16-bit user ID. A final response whose
four-byte target does not match it must trigger profile resynchronization or
reconnect, never attachment to whichever local user is active.

**Broadcasts are not private radio traffic.** Any compatible receiver in range
can read weight/impedance. Address echo validates identity; it is not encryption.
Body-composition estimates are not medical measurements.

**Factory reset:** unknown; no official model-specific manual was found and
battery removal is not asserted to clear profiles/history.

**Rebinding:** a new connected client provisions its own user ID/profile. A
broadcast client just scans. No account unbind or reset is required.

## Connected Mini / SE

Measurement service is `0000ffe0-0000-1000-8000-00805f9b34fb`; command service
is `0000ffe5-0000-1000-8000-00805f9b34fb`.

```
request:  0d | packet_size | command | payload | XOR
response: 0d | protocol_version | packet_size | response_type | payload | XOR
```

XOR covers every byte after the leading `0d` through the byte before the
checksum. Packet size is the entire frame including leader/checksum. Commands
include set-user `10`, set-time `11` and protocol query `13`; time is `uint32
BE` UNIX seconds.

Response type `01` is live/unstable and ignored; `02` is final. Common final
fields are timestamp `uint32 BE` at 5, target ID `uint32 BE` at 9, weight
`uint16 BE` at 13 in 0.01 kg, and impedance `uint16 BE` at 15 in ohms.

| Protocol | Exact final length | Boundary |
|----------|--------------------|----------|
| Below `1e` (`13` documented) | 18 bytes | No inline composition field |
| `1e` / `1f` | 20 bytes | Additional vendor `uint16 BE` at 17; not a clinical claim |
| `20` and above | Unknown | Reject; never read beyond an 18-byte buffer |

Timestamps before 1980-01-01 UTC fall back to host receive time. Complete
history, profile and unit management are not claimed merely because command
constants exist.

## Broadcast X / Mini 2S

The 16-byte manufacturer AD structure is:

| Bytes | Meaning |
|-------|---------|
| 0–5 | Device address reversed (first two become Android's manufacturer ID) |
| 6–8 | Model signature above |
| 9 | Unknown per-weigh-in byte; ignored for decoding/rearming |
| 10 | State: 01 live, 02 stable, 03 final |
| 11–12 | Weight `uint16 BE`, 0.01 kg |
| 13–14 | Impedance `uint16 BE`, ohms; zero until final |
| 15 | XOR of bytes 9–14 |

After Android strips the manufacturer ID, exactly 14 payload bytes remain.
Validate length, signature, checksum and the reversed address echo before
assigning a result. Service `0x1320` alone is only a saved-candidate hint, not
identity.

Start armed. Live/stable frames rearm without publishing a final. Publish one
valid state-03 final, then disarm and suppress repeated finals until a later
live/stable frame. Unknown states never publish or rearm. A zero final impedance
still permits weight-only reporting.

The sole captured evidence is openScale's public Mini 2S final fixture with
**all address-echo bytes zeroed**: final state, session `7f`, weight 87.65 kg,
impedance 354 ohms, XOR `00`. It establishes that layout only. International X
and connected Mini/SE still need owner captures; every other test vector is
invented.

## References

- [openScale pinned implementation](https://github.com/oliexdev/openScale/tree/35a67c7eea706d0c0cbd6a48b98f7b352960d0a1)
- [Connected Mini / SE handler](https://github.com/oliexdev/openScale/blob/35a67c7eea706d0c0cbd6a48b98f7b352960d0a1/android_app/app/src/main/java/com/health/openscale/core/bluetooth/scales/YunmaiHandler.kt)
- [Broadcast X / Mini 2S handler](https://github.com/oliexdev/openScale/blob/35a67c7eea706d0c0cbd6a48b98f7b352960d0a1/android_app/app/src/main/java/com/health/openscale/core/bluetooth/scales/YunmaiXHandler.kt)

No official model-specific manual was established, so no manual link is offered.
