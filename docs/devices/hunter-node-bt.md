# Hunter NODE-BT (two-station core)

> **Status**: Spec Available (upstream two-station hardware evidence; untested here)
> **Protocol**: BLE GATT, application-PIN authentication
> **Manufacturer**: Hunter Industries
> **Manufacturer Status**: Active

## Overview

NODE-BT valve controllers work directly with a phone: no Wi-Fi, hub, vendor
cloud or OS Bluetooth bond is required. The documented core covers controller,
state and sensor reads, configuration and logs, timed station starts, stored
program starts and stop-all.

Only the **NODE-BT-200** core has upstream physical evidence, on controller
firmware 2.2A, bootloader 1.00 and Bluetooth firmware 1.02. NODE-BT-100,
100-LS, 100-VALVE and 400 are identified in the spec but are not silently
claimed compatible. The separate legacy HunterBTT family is out of scope.

## Initial Setup

| Property | Value |
|----------|-------|
| Setup required | Owner PIN required on every connection |
| Method | `ble_direct`, owner-selected candidate + full GATT verification |
| Discovery | No safe automatic matcher; NUS is shared |
| Pairing/bonding | None; security is application-layer |
| Default PIN | Numeric `0` (`0000`) only when no user passcode was set |
| Confidence | High for the cited two-station core; not replayed by this project |

Use the owner's four-digit PIN; do not publish it or a PIN challenge response.
Ask the owner to identify the NODE-BT candidate, then **verify the complete
GATT before any write**: PIN service
`0ed3e3d3-8cd8-4f29-8fec-a7d3a2c5443e` and characteristic
`4c9dbe52-3566-4dfc-a299-4ea1353970e2`, plus the message service and its
request/response characteristics. Generic NUS by itself must not be selected
as Hunter and must receive no PIN or JSON writes. After verification, enable
message-response indications and PIN notifications, then authenticate. Run
one transaction at a time under a per-controller lock and disconnect when idle.

Advertisements can be intermittent and cached addresses can go stale. Bound
retries and re-verify the complete GATT instead of assuming a fixed name,
address or NUS identity. Close the official app and other integrations first.

**Factory reset**: unknown. The app has a factory-reset request, but its effect
on PIN, programs and logs was deliberately not tested. It is not offered as an
onboarding procedure. A normal migration needs only the existing PIN.

**Rebinding**: no network or OS bond exists. Close the old client, rediscover
and repeat the application PIN exchange; no reset is needed.

## PIN Authentication

PIN packets are six bytes, little-endian: type, result, uint16 random
challenge and uint16 PIN response. Transform every byte before sending and
after receiving:

```text
transform(b) = b XOR 0xac if b != 0 else 0
```

Zero therefore stays zero; this is not ordinary XOR and is not encryption.
**It is also not an involution at `0xac`**: plaintext `00` and `ac` both emit
`00`, and applying the transform twice to `ac` yields `00`, not `ac`. No
alternate vendor decode for `ac` is established. If either random-challenge
byte is `00` or `ac`, reject the type-2 packet as ambiguous and restart login
for a fresh challenge instead of guessing or authenticating with the wrong
value. Expected packet type/result fields are validated separately.

The login sequence is:

1. Write type 1 plaintext `01 00 00 00 00 00`, which becomes
   `ad 00 00 00 00 00 00`.
2. Receive type 2 with a random challenge; reject an ambiguous challenge as
   described above.
3. Write type 3 with the same challenge and `pin XOR random` in the PIN field,
   transformed bytewise.
4. Require type 4 with result `0`. Any other result is a failure, and its
   meaning is not established.

For an invented challenge `0x1234` and default numeric PIN 0, plaintext
`03 00 34 12 34 12` becomes `af 00 98 be 98 be`. This vector is synthetic and
contains no owner credential.

## Protocol Summary

### BLE Services

| UUID | Name | Description |
|------|------|-------------|
| `6e400001-b5a3-f393-e0a9-e50e24dcca9e` | Message service | Advertised scan filter |
| `6e400002-b5a3-f393-e0a9-e50e24dcca9e` | Message request | Acknowledged writes on tested firmware |
| `6e400003-b5a3-f393-e0a9-e50e24dcca9e` | Message response | Read/indicate JSON fragments |
| `0ed3e3d3-8cd8-4f29-8fec-a7d3a2c5443e` | PIN service | Application authentication |
| `4c9dbe52-3566-4dfc-a299-4ea1353970e2` | PIN challenge/response | Read, write without response, notify |

Requests are compact UTF-8 JSON split into consecutive writes of **at most 20
bytes**, with no checksum, outer sequence number or trailing NUL. Responses
are UTF-8 JSON fragments terminated by the first NUL. Accumulate through that
NUL (a 64 KiB client limit includes it), reject malformed/trailing data, and
require `Status: 0` for a write. Only zero is known success.

### Reads and timed operations

```json
{"Read":"All"}
{"Read":"Section_Controller"}
{"Read":"Section_State"}
{"Read":"Section_Sensor"}
{"Read":"Log"}
{"Read":"LastRun"}
{"Manual":{"StationNumber":1,"RunTime":60}}
{"Manual":{"ProgramLetter":"A"}}
{"Manual":{"StopAll":true}}
```

`Read All` omitted live `State` on firmware 2.2A, so always read
`Section_State` separately. `Controller.StationCount` determines physical
stations even when the response contains four station objects and four
runtimes. Runtimes and remaining time are seconds; `NextWaterTime` is minutes
after local midnight.

The controller owns a manual timer after BLE disconnects. A dropped link does
not leave the valve open beyond the accepted duration. If a start
acknowledgement is lost after transmission, read live state before deciding;
**never blindly repeat watering**. Stop-all does not need cached state.

### Schedules and the combined-write defect

Programs A/B/C live on the controller. `StartTimes` has eight entries in
minutes after midnight, with `65535` disabled. Enabled entries are sorted and
compacted, so positions are not stable slot IDs. `RunTime` contains per-station
seconds; preserve the array shape and all unknown fields returned by that
controller. New names are conservatively limited to 14 UTF-8 bytes.

Every edit is read-modify-verify under one lock:

1. Fresh `Read All`; save the complete original program and validate stations.
2. Send a narrow patch only for intended fields and require status `0`.
3. Read All again and compare the complete merged object, including unknown
   fields and unchanged arrays.
4. A lost acknowledgement or failed comparison is **unverified**, not a cue to
   retry automatically.

**Never put `StartTimes` and `RunTime` in the same write.** On the tested
firmware, a combined clear acknowledged success but produced two midnight
starts instead of eight disabled entries. A separate narrow start-time clear
worked. To replace both, zero and verify runtimes first, edit and verify
starts/days/name second, then write and verify desired runtimes third.

Controller `CurrentTime` encodes local wall-clock fields against a naive
1970-01-01 epoch, not UTC Unix time. Use the configured controller timezone
explicitly. `IntervalDayNext` uses different app conversion behavior, and log,
LastRun and device-generated timestamp semantics remain open.

## Evidence and limits

Two pinned public implementations and the vendor product/support pages back
the spec. No controller or irrigation write was performed here. One-/four-
station models, wrong-PIN behavior, nonzero statuses, live state enums,
proxies, factory reset and OTA remain open. The focused standard-library test
covers the PIN transform, JSON fragmentation/reassembly, clock encoding and
the separate schedule-write rule with split/coalesced/malformed inputs.

- [Hunter NODE-BT product page](https://www.hunterindustries.com/irrigation-product/controllers/node-bt)
- [Hunter NODE-BT support](https://hunter.direct/nodebthelp)
- [Hunter US catalog (PDF)](https://d7.hunterindustries.com/sites/default/files/Hunter_Catalog_US.pdf)
- [jpmeijers/home-assistant-hunter-node-bt](https://github.com/jpmeijers/home-assistant-hunter-node-bt/tree/2d5460d1218c642c4dc169f42af22f67d5554bac)
- [filipejrcorreia/hunter-node-bt](https://github.com/filipejrcorreia/hunter-node-bt/tree/bc24f23119bc1642e723ae000b7029b854d60117)
