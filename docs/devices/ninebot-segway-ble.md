# Ninebot / Segway E-Scooter (BLE)

> **Status**: Spec Available (unverified) — active; newer firmware adds session crypto
> **Protocol**: BLE
> **Manufacturer**: Ninebot-Segway
> **Manufacturer Status**: Active

## Overview

Ninebot/Segway ES and MAX (G30) scooters use the same Nordic-UART serial-over-BLE bridge and register model as the Xiaomi M365 (see that spec); only the outer frame differs. Newer G30 firmware is reported to add AES session encryption.

The Ninebot Z electric unicycle is a different protocol. Its
[WheelLog EUC spec and guide](euc-wheellog-ble.md#ninebot-z-a-distinct-wheellog-variant)
shares this family's Nordic-UART trio and its clear-length, `L + 9` and
little-endian-checksum outer framing. The Z differs in its repeating-XOR
transform, role addresses and telemetry payloads rather than in those outer
length rules. Do not send scooter register commands to a Z wheel.

## Discovery and write safety

Nordic UART is **not an advertisement identity**. It is shared by the Ninebot Z,
InMotion V2 and unrelated serial peripherals, so this spec deliberately has no
NUS scan matcher and no advertised-name guess.

A person must manually select the exact scooter before any GATT write. After
that manual selection, connect and subscribe, then send only a read-only
register request. Confirm the scooter's expected ESC/BMS role addresses and
register reply layout before any setting write. Stop if the response has the
Ninebot Z role addresses or repeating-XOR payload transform. A bare NUS
fingerprint or `5A A5` header never authorizes use of this scooter spec.

## Protocol Summary

Reported post-connect transport: Nordic UART service
`6e400001-b5a3-f393-e0a9-e50e24dcca9e`; write to
`6e400002-b5a3-f393-e0a9-e50e24dcca9e`, notify on
`6e400003-b5a3-f393-e0a9-e50e24dcca9e`. These UUIDs do not identify the model.

Frame header `5A A5` (versus Xiaomi `55 AA`), clear length, addresses, command,
payload and a two-byte little-endian checksum. The complete frame uses `L + 9`
bytes and the register model is shared with the M365.

See `device-specs/devices/ninebot-segway-ble.yaml` for the full machine-readable spec.

## References

- <https://github.com/Informatic/py9b>
- <https://github.com/CamiAlfa/M365-BLE-PROTOCOL>
