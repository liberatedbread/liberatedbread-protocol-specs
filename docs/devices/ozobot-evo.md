# Ozobot Evo — native RPC, memory and watchers

> **Status**: Spec Available — official-source-derived, untested on hardware
> **Protocol**: BLE GATT, current native RPC; separate legacy negotiation
> **Manufacturer**: Ozobot / Ozo Edu Inc. (active)

## Overview

Current Evo supports direct read-only virtual-memory access and sensor watchers
without an Ozobot account. This profile covers identification, memory reads,
watchers and long-RPC integrity, not robot movement. The machine-readable spec
is [`ozobot-evo.yaml`](https://github.com/liberatedbread/liberatedbread-protocol-specs/blob/main/device-specs/devices/ozobot-evo.yaml).

Current and legacy endpoints are not aliases. Choose by the enumerated GATT
table and firmware evidence, not just the `OzoEvo` name. Ari (advertised product
5) is out of scope.

## Initial Setup and pairing

| Property | Value |
|----------|-------|
| Setup required | No |
| Method | `ble_direct`, native or legacy variant (medium confidence) |
| BLE pairing/bond | None |
| Credentials | None |
| MTU / direct packet | 23 / 20-byte ATT payload |

For current units, enable notifications, follow the official stop-on-open
boundary and read `watchersInfo` before allocating watchers. Stop-execution with
request ID 0 stops current programs and is an **advanced recovery action**, not
a hidden read or factory reset.

**Factory reset**: unknown. Stop-execution, watcher teardown, disconnecting and
the legacy stop-file sequence are not factory resets.

**Rebinding**: disable all watchers/regions, disconnect, then rediscover by
manufacturer device ID where possible and negotiate the generation again.
Legacy addresses may change. No bond or Wi-Fi credential is involved.

## Discovery

Manufacturer company ID is `0x03eb` (decimal 1003). The payload after the
company-ID bytes is:

| Offset | Meaning |
|--------|---------|
| 0 | Packet ID, must be zero |
| 1–16 | Stable device ID; sanitize in logs |
| 17–21 | Unparsed/reserved |
| 22 | Product: 0 or 4 Evo, 5 Ari |
| 23 | Version major with high bit masked |
| 24 | Version minor |
| 25–26 | Optional patch `uint16` little-endian |

Require at least 25 bytes for product/major/minor and 27 for a full patch. Use
the 16-byte device ID rather than a changeable address when available.

| Generation | Service | Characteristics |
|------------|---------|-----------------|
| Current native | `8903136c-5f13-4548-a885-c58779136801` | Bidirectional RPC `8903136c-5f13-4548-a885-c58779136802` |
| Legacy, negotiation only | `8903136c-5f13-4548-a885-c58779136701` | Drive `8903136c-5f13-4548-a885-c58779136702`, control `8903136c-5f13-4548-a885-c58779136703` |

Do not send native RPC to legacy endpoints or legacy bytes to native ones. No
legacy motion or initialization sequence is published.

## Native RPC

Every packet begins with a little-endian `uint16` message ID. Generated scalar
fields are little-endian. Direct packets fit 20 bytes and are written without
response; do not assume one notification is a frame fragment to concatenate.
Long RPC uses the staging algorithm below instead.

| Operation | Request / response ID | Layout |
|-----------|-----------------------|--------|
| MemRead | 1 / 2 | Request address `uint32`, length `uint16`; response result `uint8`, length `uint16`, data |
| MemWrite, long-RPC staging only | 3 / 4 | Address `uint32`, length `uint16`, data; response result |
| StopExecution | 120 / 121 | Four-byte request ID; zero stops all |
| WatcherSetup | 122 / 123 | Watcher ID, flags, minimum/maximum period `uint16` ms; response status |
| WatcherRegionSetup | 124 / 125 | Watcher ID, region ID, address `uint16`, size `uint8`, flags; response status |
| LongRPCExtensionExecute | 126 / 127 | Length `uint16`, CRC32 `uint32`; response status + returned length/CRC |
| WatcherDirty event | 260 | Watcher ID then region data in ascending region ID |

Result zero means success for memory I/O and calls. Require exact lengths before
using a response or event.

### Request IDs

The logical request ID has source 2 (BLE) in its high byte and a three-byte
big-endian counter below it, but the whole `uint32` is serialized little-endian.
Counter 1 is therefore integer `0x02000001` and wire bytes `01 00 00 02`.
Request ID zero is the special stop-all value.

### Read-only memory

Useful addresses include firmware version `0x1002c`, watcher metadata `0x10073`,
line color `0x56`, surface color `0x64`, IR proximity `0x76`, charger state
`0xb7`, battery state `0xbc`, button `0xc4` and per-watcher update counters at
`0x0400 + watcherID`. Their exact struct layouts and enum values are declared in
the spec. Battery voltage has no established unit, so only remaining percent is
exposed; do not invent a voltage scale.

### Watchers

`watchersInfo` gives watcher and region counts. Add a one-byte update-counter
region with `DoNotSetDirty`, configure watched regions, then enable with flags
`Enabled | DisableWhenDisconnected` (3), minimum 40 ms and maximum zero. At MTU
23 all regions in one watcher must fit the 17-byte `WatcherDirty` data budget.

On every exit, clear each region with address/size zero and region flags 3,
then disable the watcher with setup flags zero and periods zero. Disconnect
cleanup is a backstop, not a substitute for explicit teardown.

### Long RPC and CRC32

Serialize the request once. Stage it at `0x6000` in chunks of at most
`20-8 = 12` bytes with MemWrite. Send message 126 with total length and standard
CRC32 (`binascii.crc32`/`zlib.crc32` compatible). After a successful response,
read the result from `0x6000` in chunks of at most `20-5 = 15` bytes and require
the returned length and CRC32 to match before decoding. These staging writes
are transport operations, not motion commands.

## Validation and omissions

`scripts/test_ozobot_evo_spec.py` independently checks advertisement parsing,
request IDs, MemRead, watcher vectors, malformed/truncated packets, long-RPC
chunks and CRC failures. It includes only an inert stop-all encoding and no
movement operation.

Factory reset, battery voltage unit, current/legacy auto-negotiation, legacy
read-only commands, firmware update, calibration, file execution, LED/tone and
all driving APIs remain outside scope.

## References

- [Official Ozobot Python libraries (pinned)](https://github.com/ozobot/python-libraries/tree/9c09f5e8137bdffb6a93068b26d5a71420e67984)
- [Official Ari & Evo Python SDK documentation](https://docs.ozobot.com/python/linefollower/index.html)
- [Legacy independent client (pinned; boundary evidence only)](https://github.com/raphaelbink/raspberry-pi-ozobot-evo/tree/5de09556efa06565c7941bcec285840e76a391a1)
