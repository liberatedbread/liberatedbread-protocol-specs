# Pebble Smartwatch

> **Status**: Abandoned — Pebble closed 2016; firmware open-sourced 2025, revived by Rebble
> **Protocol**: BLE
> **Manufacturer**: Pebble Technology (defunct 2016; revived via Rebble + Core Devices)
> **Manufacturer Status**: Abandoned

## Overview

The original crowdfunded smartwatch line. Pebble shut down in 2016, but in 2025 the firmware was open-sourced 100%, Rebble runs the appstore, and Core Devices ships new compatible hardware. Full local control.

## Protocol Summary

Every Pebble Protocol frame is:

| Offset | Length | Description |
|--------|--------|-------------|
| 0–1 | 2 | Body length, **u16 big-endian**, excluding this four-byte header |
| 2–3 | 2 | Endpoint, **u16 big-endian** |
| 4 | `body_length` | Endpoint-specific body |

Fields inside bodies are big-endian by default unless their message definition
overrides that. Direct Bluetooth serial uses **115200 baud**. A port-9000
WebSocket developer connection and QEMU are alternative libpebble2 transports.
Only one connection is supported at a time.

### PPoGATT transports

These UUIDs use the Pebble base `xxxxxxxx-328e-0fbb-c642-1aa6699bdada`, not
the Bluetooth SIG base.

| Transport | Service and characteristics | Direction |
|-----------|-----------------------------|-----------|
| Forward, phone-hosted | Service `10000000-…`; data `10000001-…`; meta `10000002-…` | Watch reads meta and writes data to phone; phone notifies watch. Watch sends the first ResetRequest. |
| Pebble-2 watch-hosted V1 | Service `30000003-…`; notify `30000004-…`; meta `30000005-…`; write `30000006-…` | Phone reads meta, receives watch notifications, and writes the separate data-write characteristic. |
| Reversed watch-hosted V2 | Service `40000000-…`; notify `40000001-…`; write `40000003-…` | Phone subscribes then sends the first ResetRequest to `40000003`; watch replies on `40000001`. No meta characteristic exists. |

PPoGATT packets prepend a one-byte header containing sequence number in bits
3–7 and packet type in bits 0–2 (data 0, ack 1, ResetRequest 2, ResetComplete
3). The payload carries the Pebble Protocol stream above. Generation-specific
battery/GATT support and firmware-update transport/signing remain unresolved;
do not assume one watch generation's endpoints apply to every model.

See `device-specs/devices/pebble-smartwatch.yaml` for the full machine-readable spec.

## References

- <https://libpebble2.readthedocs.io/en/latest/protocol/>
- <https://rebble.io/>
- <https://ericmigi.com/blog/pebble-watch-software-is-now-100percent-open-source/>
