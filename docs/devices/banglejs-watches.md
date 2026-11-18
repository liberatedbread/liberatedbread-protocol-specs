# Espruino Bangle.js 1 and 2

> **Status**: Spec Available (untested)
> **Protocol**: BLE Nordic UART Service (NUS)
> **Manufacturer**: Espruino / Pur3 Ltd
> **Manufacturer Status**: Active (Bangle.js 1 no longer sold)

## Overview

Bangle.js watches are programmable, not tied to a proprietary account. They
share a UART/JSON interface with Gadgetbridge and a Web Bluetooth App Loader.
This entry covers **Bangle.js 1 and 2 only**; Bangle.js 3 metadata is not enough
evidence to claim it.

The machine-readable spec is `device-specs/devices/banglejs-watches.yaml`.
No watch was driven from it, and no optional relay, code upload or firmware
update was exercised.

## Hardware

| Property | Bangle.js 1 | Bangle.js 2 |
|----------|-------------|-------------|
| SoC | nRF52832 | nRF52840 |
| Controls | Three buttons + two touch zones | Full touchscreen + one button |
| Radio | BLE | BLE |
| Recovery | BTN1+BTN2(+BTN3 for Recovery) | Side button |
| FCC ID | 2AILG-F18 | 2AKUO-10 |

## Initial Setup

| Property | Value |
|----------|-------|
| Setup required | No for raw NUS; install Android Integration for full Gadgetbridge |
| Method | `ble_direct` |
| Advertised identity | `Bangle.js ` prefix plus suffix; NUS in scan response |
| Pairing | Optional bond, not an account credential |
| Confidence | Medium from official open documentation; not replayed here |

Enable BLE and **Make Connectable**, disconnect any other client, then actively
scan. For Gadgetbridge install **Android Integration** and its Messages
dependency; the older Gadgetbridge widget is unmaintained. Leave Programmable,
Internet access, intents and file/code writes off unless deliberately needed.

**Rebinding:** disconnect the old phone/browser and connect the new one. On
firmware 2v30+, Recovery's **Delete BT Pairing** (Soft, then Hard if pairing
flash is corrupt) clears only bonds. Forget the host OS entry as needed.

**Factory reset (2v19+):** continue holding through the initial DFU text and
`====` progress into Recovery, then choose **Factory Reset**. Releasing at the
first six-second mark only reboots. On Bangle.js 1 hold all three buttons, then
release BTN1/BTN2 while keeping BTN3 held; on Bangle.js 2 keep holding its one
button. Factory Reset wipes data/settings. Older firmware can use App Loader
**Install default apps**, which also erases and reinstalls defaults. Clean Boot
only suppresses installed code for one boot.

## Protocol Summary

| Direction | Characteristic and framing |
|-----------|----------------------------|
| Host to watch | `6e400002-b5a3-f393-e0a9-e50e24dcca9e`: byte `10`, then `GB(<JSON object>)\n` |
| Watch to host | `6e400003-b5a3-f393-e0a9-e50e24dcca9e`: one JSON object per line, no `10`/GB wrapper |
| Service | `6e400001-b5a3-f393-e0a9-e50e24dcca9e` |

NUS may appear only in a scan response and is shared with other devices, so it
is not identity by itself. Android Integration sends `status` (battery) and
`ver` (firmware/hardware) after connection. Use `ver.hw` to confirm the model.
Twenty bytes is a safe default UART chunk; high MTU is optional. Reassemble
fragments/coalesced messages by their wrappers/newlines, not by notification.
Ignore non-JSON console text and preserve unknown `t` types for a newer handler.

Common phone messages include `notify`/`notify-`, `alarm`, `find`, `vibrate`,
`weather`, `musicstate`/`musicinfo`, `call`, `act`/`actfetch`, recorder-log
requests, `calendar`/`calendar-`, `gps`/`gps_power` and `nav`. Watch messages
include `status`, `ver`, `findPhone`, `music`, `call`, notification actions,
`act`, recorder-log chunks, `force_calendar_sync` and `gps_power`. Exact fields
and units are tabulated in the spec and the official guide.

### Optional advanced surfaces

These are **not required for local sync** and are disabled by default:

- **Arbitrary JavaScript and app/file/code upload:** executes code and can
  overwrite apps, files or startup behavior. Requires Programmable/reviewed code.
- **HTTP relay:** watch JSON `{t:"http",...}` asks Bangle.js Gadgetbridge for an
  HTTPS request and receives a response. Requires explicit Internet permission;
  `insecure` defaults false and plain HTTP is unsupported.
- **Phone file writes:** `{t:"file", n, c, m}` writes/appends phone-side files;
  approve destination/content first.
- **Android intents:** can launch activities/services and interact with other
  apps; requires explicit Allow Intents.

Firmware update is board-specific and advanced. Bangle.js 2 recommends its App
Loader Firmware Update app; Kickstarter 2v10 bootloaders need updating first.
The spec does not invent a byte-level updater or claim a Nordic stack.

## References

- [Bangle.js 1 official board/recovery guide](https://www.espruino.com/Bangle.js)
- [Bangle.js 2 official board/recovery guide](https://www.espruino.com/Bangle.js2)
- [Official Gadgetbridge protocol and setup](https://www.espruino.com/Gadgetbridge)
- [Espruino NUS guide](https://www.espruino.com/BLE+UART)
- [Bangle.js App Loader](https://banglejs.com/apps)
