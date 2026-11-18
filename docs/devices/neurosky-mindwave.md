# NeuroSky MindWave Mobile (original)

> **Status**: Spec Available (untested)
> **Protocol**: Bluetooth Classic RFCOMM/SPP
> **Manufacturer**: NeuroSky, Inc.
> **Manufacturer Status**: Active

## Overview

The original **MindWave Mobile**, FCC ID **XG9MW3**, streams ThinkGear data
directly to a paired phone or computer. No vendor cloud or account is needed.
This guide covers only that Classic model. **MindWave Mobile 2 BLE, its
characteristics and 20-byte command wrapper are not covered**, and the older
XG9MW1/XG9MW2 USB-dongle generation is separate.

The machine-readable spec is `device-specs/devices/neurosky-mindwave.yaml`.
Everything is source-derived and untested here; no EEG was collected.

## Hardware

| Property | Value |
|----------|-------|
| Model | Original MindWave Mobile (XG9MW3) |
| Radio | Bluetooth Classic with Serial Port Profile |
| Control profile | `00001101-0000-1000-8000-00805f9b34fb` |
| Inquiry name | Exactly `MindWave Mobile` |
| Power | One AAA battery |
| Companion evidence | Official 2011 guide and independent RFCOMM clients |

Resolve the RFCOMM channel with SDP. One independent Linux client used channel
1, but that is not a guarantee for every production unit.

## Initial Setup

| Property | Value |
|----------|-------|
| Setup required | Yes: standard OS Bluetooth pairing |
| Method | `bt_classic_pairing` |
| PIN | Product-wide legacy `0000`, only if the host asks |
| Passphrase protection | `not_applicable` (no Wi-Fi) |
| Confidence | Medium from the official guide; not replayed here |

1. Insert the battery and slide the switch to ON.
2. Hold it past ON for **three seconds**, releasing before six seconds. The
   blue LED flashes for about two minutes.
3. Select `MindWave Mobile` in the host Bluetooth settings and enter `0000`
   if prompted. The LED becomes solid blue on connection.
4. Open a secure RFCOMM socket by the SPP UUID and parse the stream passively.
   Read a valid packet before considering any configuration.

**Pairing memory and reset:** the headset remembers up to three hosts. Holding
past ON clears all of them. The guide's reference section says six seconds; a
quick-start passage says ten. The spec uses the longer instruction and records
the discrepancy. This clears pairings, not a claimed health-history store.
Power-cycling restores default ThinkGear output settings after unsupported
commands.

**Rebinding:** a bonded host reconnects directly. A new host can be added in
pairing mode; clear all pairings only if adoption fails.

## Pairing and host support

| Property | Value |
|----------|-------|
| Pairing required | Yes |
| Security mode | `legacy_pin` |
| Bonding | Required; up to three hosts |
| One bond at a time | No |
| Unpair | Clear all pairing memory; no per-host erase is documented |

An independent CoreBluetooth client on iOS/iPadOS **cannot open this SPP
socket**, because CoreBluetooth has no RFCOMM API. The old guide mentions iOS
pairing but does not establish an MFi/iAP2 protocol an independent client can
use. macOS is different: IOBluetooth provides Classic RFCOMM.

## Protocol Summary

ThinkGear is an asynchronous binary stream, not request/reply GATT:

```
AA AA | PLENGTH | PAYLOAD[PLENGTH] | CHECKSUM
```

- `PLENGTH` is 0–169 bytes; a complete packet is `PLENGTH + 4` bytes.
- `CHECKSUM = (~sum(PAYLOAD)) & 0xff`.
- Keep a buffer across arbitrary RFCOMM reads. Reject oversized lengths and bad
  checksums before emitting values, then scan forward for the next `AA AA`.
- Each DataRow has zero or more `55` extension bytes, a code, and either an
  implicit one-byte value (codes below `80`) or a length byte and multi-byte
  value (`80` and above). Unknown rows are skipped by that rule.

| Code | Meaning | Encoding |
|------|---------|----------|
| `02` | Poor-signal quality | One byte; 0 good, 200 no skin contact |
| `04` / `05` | Attention / Meditation eSense | One byte each; 1–100, 0 unavailable |
| `16` | Blink strength | One byte; not required from current hardware |
| `80` | Raw EEG sample | Signed 16-bit **big-endian** ADC counts |
| `83` | ASIC EEG powers | Eight unsigned **24-bit big-endian** values, 24 bytes total |

The band order is delta, theta, low-alpha, high-alpha, low-beta, high-beta,
low-gamma, mid-gamma. Raw ADC and band-power values have no invented physical
unit. eSense is a vendor wellness metric, not a clinical measurement.

No write command is declared. Mobile 2's raw-enable/notch commands and BLE
wrapper must not be sent to the original; ThinkGear command support is
firmware-specific and wrong commands can require a power cycle.

## References

- [Official ThinkGear Serial Stream Guide](https://developer.neurosky.com/docs/doku.php?id=thinkgear_communications_protocol)
- [Original XG9MW3 user guide (PDF)](https://fccid.co/api/files/s1/xg9mw3_usersmanual_1546394_1c11233670.pdf)
- [Independent RFCOMM client](https://github.com/robintibor/python-mindwave-mobile)
