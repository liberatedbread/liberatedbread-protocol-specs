# OBD-II Bluetooth Adapters (ELM327 / STN)

> **Status**: Complete (adapter link layer) / In Progress (per-model GATT coverage)
> **Protocol**: Bluetooth Classic SPP or BLE GATT, carrying an ASCII ELM327 command set
> **Manufacturer**: Generic (ELM327 clones), ScanTool.net (OBDLink), Vgate, LELink and others
> **Manufacturer Status**: Active (clones are unsupported and undocumented; firmware is cloned from a discontinued Elm Electronics part)

## Overview

Every vehicle target in this repo is reached through one of these dongles, so the
adapter deserves its own spec: it is the transport under the transport. The vehicle-side
protocol is [OBD-II / UDS](../protocols/obd2-common.md); the phone-side protocol is a
Bluetooth serial link carrying **ASCII text**.

That ASCII property is what makes these adapters so useful for reverse engineering.
Capture the Bluetooth link between a vendor app and the dongle and you can read the
vendor's diagnostic requests directly — no decryption, no protobuf, no obfuscation. A
btsnoop HCI log of a paid tool doing a paid function is a plain-text transcript of the
protocol it is charging for.

## Hardware

| Property | Value |
|----------|-------|
| Original part | Elm Electronics ELM327 (discontinued; the market is clones) |
| Quality chipsets | ScanTool STN110 / STN2120 (OBDLink LX / MX+ / CX) |
| Link | Bluetooth Classic SPP (RFCOMM), BLE GATT, or dual-mode |
| Vehicle side | ISO 15765-4 CAN, ISO 9141-2, ISO 14230-4, SAE J1850 |
| Power | Parasitic from OBD pin 16 (unswitched +12 V on most vehicles) |

!!! warning "Leave nothing plugged in"
    Pin 16 is usually unswitched. Cheap dongles do not sleep reliably and will flatten a
    battery over a week — especially on a motorcycle. Unplug after each session.

## Protocol Summary

### Link layer 1: Bluetooth Classic (SPP)

| Property | Value |
|----------|-------|
| Profile | Serial Port Profile over RFCOMM, usually channel 1 |
| Advertised names | `OBDII`, `OBDII-BT`, `V-LINK`, `Vgate`, `OBDLink LX`, `OBDLink MX+` |
| Pairing PIN | `1234`, `0000` or `6789` depending on firmware |
| Linux bind | `sudo rfcomm bind 0 <mac> 1` → `/dev/rfcomm0` |

Generic Bluetooth Classic dongles **cannot** be used from an iPhone — iOS requires BLE or
an MFi-certified Classic device (OBDLink MX+ and vLinker FS are MFi). Android apps such
as Torque Pro require Classic SPP and will not see a BLE-only adapter. This split is why
most vendor tools are Android-first.

### Link layer 2: BLE GATT

BLE adapters expose a two-characteristic serial pipe: write your ASCII command to one,
receive the reply as notifications on the other. Three families cover almost the whole
market:

| Family | Service | Notify (adapter → phone) | Write (phone → adapter) | Seen on |
|--------|---------|--------------------------|-------------------------|---------|
| A | `0000fff0-0000-1000-8000-00805f9b34fb` | `0000fff1-…` | `0000fff2-…` | OBDLink CX and a large share of generic adapters |
| B | `000018f0-0000-1000-8000-00805f9b34fb` | `00002af0-…` | `00002af1-…` | Vgate iCar Pro 2S BLE, LELink2 |
| C | `0000ffe0-0000-1000-8000-00805f9b34fb` | `0000ffe1-…` | `0000ffe1-…` (same characteristic) | HM-10-module clones (community-reported) |

Family C is the same HM-10 serial pass-through pattern documented for the
[MoTool Slacker](motool-slacker.md) — a single bidirectional characteristic rather than a
pair. A client that wants to work with arbitrary hardware should probe for all three
rather than hardcoding one.

Notes that matter in practice:

- Enable notifications via the standard CCCD (`0x2902`) before writing anything.
- Replies arrive **split across notifications** and are only complete when the `>` prompt
  byte appears. Buffer until `>`, do not parse per-notification.
- MTU is often 20 bytes; long replies (a `ATI` banner, a multi-line CAN response) always
  span several notifications.
- No authentication, no encryption, no pairing on most BLE adapters. Anyone in range of a
  plugged-in dongle has the same access the owner does.

### Application layer: the ELM327 command set

Two request kinds share one channel, distinguished by prefix:

| Prefix | Meaning | Example |
|--------|---------|---------|
| `AT…` | Adapter configuration | `ATSP6` — select ISO 15765-4, 11-bit, 500 kbit/s |
| `ST…` | STN-only extensions | `STP33` — STN protocol select |
| hex digits | Payload sent to the vehicle | `22F190` — UDS ReadDataByIdentifier |

Commands are `\r`-terminated. Replies end with `>`.

| Command | Effect |
|---------|--------|
| `ATZ` | Reset; returns the firmware banner (`ELM327 v1.5`, `STN2120 …`) |
| `ATI` | Identify without resetting |
| `ATE0` / `ATL0` / `ATS0` | Echo, linefeeds, spaces off — do this first when scripting |
| `ATRV` | Adapter's estimate of battery voltage (approximate; not from the ECU) |
| `ATSP<n>` / `ATDP` | Set / display protocol |
| `ATSH <hhh>` | Set request header (physical ECU addressing, e.g. `ATSH 7E0`) |
| `ATCRA <hhh>` | Filter received frames to one response ID |
| `ATFCSH` / `ATFCSD` / `ATFCSM` | Flow-control header, data and mode for multi-frame ISO-TP |
| `ATCAF0` | CAN auto-formatting **off** — raw frames, ISO-TP is yours to do |
| `ATST <hh>` | Response timeout |

### Capability tier

Which tier a dongle belongs to decides which functions it can run. See
[classifying OBD-II devices](../protocols/obd2-common.md#classifying-obd-ii-devices) for
the full capability matrix.

| Class | Typical hardware | Runs `basic` commands | Runs `advanced` commands |
|-------|------------------|-----------------------|--------------------------|
| `basic-clone` | "ELM327 v2.1" clones | Yes | No — multi-frame transmit and flow control are unreliable |
| `standards-elm327` | Genuine ELM327 v1.4/1.5 | Yes | Partly — firmware-dependent |
| `advanced-stn` | OBDLink LX / MX+ / CX | Yes | Yes |
| `native-can` | SocketCAN, PCAN, Kvaser | Yes | Yes, plus bus sniffing |

The spec's baseline profile is `standards-elm327`, because that is what the whole family
can be relied on to do; anything needing `multiframe_tx` or `flow_control` should be
matched against an `advanced-stn` adapter specifically.

### Telling a good adapter from a clone

Clone firmware reports a version banner it did not earn (`ELM327 v2.1` on a v1.4 core is
common) and typically fails on:

- multi-frame ISO-TP **transmit** — the direction needed for a UDS write
- honouring an ECU's requested separation time in flow control
- custom headers via `ATSH` on some protocols

Single-frame reads (`03` for DTCs, `01xx` for live data) work almost everywhere, which is
exactly why vendor tools accept any adapter for reading and name specific ones for
maintenance functions. If a documented function works on an OBDLink and fails on a clone,
the function is multi-frame — that is a protocol fact you get for free.

A quick capability probe:

```text
ATZ            → banner (claimed, not proven)
ATSP6          → OK
ATCAF0         → OK          clone firmware sometimes refuses
ATFCSM1        → OK          if this fails, multi-frame TX will fail
```

## Using one for capture

The reason this page exists. To recover a vendor tool's protocol:

1. Android: *Developer options → Enable Bluetooth HCI snoop log*.
2. Run the vendor app through the function of interest, once, cleanly.
3. Pull `btsnoop_hci.log` (`adb pull /sdcard/btsnoop_hci.log`, path varies by OEM).
4. Open in Wireshark, filter `btrfcomm` (Classic) or `btatt` (BLE), *Follow Stream*.
5. Read the AT setup and the hex payloads directly out of the ASCII.

`scripts/obd_discover.py` speaks this same command set over `/dev/rfcomm0` or a BLE
serial bridge, read-only, for mapping which ECUs and DIDs a vehicle answers.

## Tools Used

- [x] Public protocol documentation (ELM327 AT command set, STN extensions)
- [x] Cross-referenced open-source BLE OBD clients for GATT UUID families
- [ ] Per-model GATT enumeration with nRF Connect (contributions welcome — add a row to
      the family table)

## References

- [Car Scanner — choosing an OBD-II adapter (link types and iOS/Android constraints)](https://www.carscanner.info/choosing-obdii-adapter/)
- [obd-ble-serial — FFF0/FFF1/FFF2 family, OBDLink CX](https://github.com/vdvornichenko/obd-ble-serial)
- [nissan-leaf-obd-ble — 18F0/2AF0/2AF1 family, LELink2 / Vgate iCar Pro 2S](https://github.com/pbutterworth/nissan-leaf-obd-ble)
- [OBDLink product line (STN chipsets)](https://www.obdlink.com/products/obdlink-ex/)
- [Raspberry Pi forums — RFCOMM/SPP binding for ELM327 dongles](https://forums.raspberrypi.com/viewtopic.php?t=191517)

## Contributors

- Link-layer survey and capture methodology
