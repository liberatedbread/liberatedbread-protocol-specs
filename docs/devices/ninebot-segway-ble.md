# Ninebot / Segway E-Scooter (BLE)

> **Status**: Spec Available (unverified) — active; newer firmware adds session crypto
> **Protocol**: BLE
> **Manufacturer**: Ninebot-Segway
> **Manufacturer Status**: Active

## Overview

Ninebot/Segway ES and MAX (G30) scooters use the same Nordic-UART serial-over-BLE bridge and register model as the Xiaomi M365 (see that spec); only the outer frame differs. Newer G30 firmware is reported to add AES session encryption.

The Ninebot Z electric unicycle is a different protocol. Its
[WheelLog EUC spec and guide](euc-wheellog-ble.md#ninebot-z-a-distinct-wheellog-variant)
document its own length rules, repeating-XOR session obfuscation, controller/BMS
addresses and read-only telemetry. The shared `5A A5` header alone does not
distinguish a Z wheel from this scooter family; confirm the protocol after
connecting and do not send scooter register writes to a Z wheel.

## Protocol Summary

Nordic UART service `6e400001-b5a3-f393-e0a9-e50e24dcca9e`; write to
`6e400002-b5a3-f393-e0a9-e50e24dcca9e`, notify on
`6e400003-b5a3-f393-e0a9-e50e24dcca9e`. Frame header `5A A5` (versus Xiaomi
`55 AA`), length, addresses, command, payload and a two-byte little-endian
checksum. The register model is shared with the M365.

See `device-specs/devices/ninebot-segway-ble.yaml` for the full machine-readable spec.

## References

- <https://github.com/Informatic/py9b>
- <https://github.com/CamiAlfa/M365-BLE-PROTOCOL>
