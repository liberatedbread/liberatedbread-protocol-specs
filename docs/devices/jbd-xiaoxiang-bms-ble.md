# JBD / Xiaoxiang Smart BMS (BLE)

> **Status**: Spec Available (unverified) — active; ships in countless LiFePO4 packs
> **Protocol**: BLE
> **Manufacturer**: Shenzhen Jiabaida (JBD) — many LiFePO4 pack rebrands (Overkill Solar, LIONTRON, ECO-WORTHY, ...)
> **Manufacturer Status**: Active

## Overview

JBD (Xiaoxiang) battery-management systems inside many rebranded LiFePO4 packs (Overkill Solar, LIONTRON, ECO-WORTHY). Local BLE/UART, no cloud.

## Protocol Summary

GATT service 0xFF00 (notify 0xFF01, write 0xFF02) is shared with Bluetti, so manually select the candidate and prove identity with a read-only 0x03 exchange before writes. Requests checksum register + length + data (excluding `DD`, `A5`, checksum and `77`); responses checksum register + status + length + data. Reassemble notifications to `4 + length + 3` bytes before terminator/CRC validation. Request vectors are `DD A5 03 00 FF FD 77`, `DD A5 04 00 FF FC 77`, and `DD A5 05 00 FF FB 77`.

Read 0x03 basic info (voltage, current, SOC, FET status, temps), 0x04 cell voltages. Current is signed, negative = discharge. Operation-status bit 7 selects 100 mA/100 mAh on firmware implementing that flag; otherwise current and both capacities use 10 mA/10 mAh. Writes toggle FETs/balancer in factory mode.

See `device-specs/devices/jbd-xiaoxiang-bms-ble.yaml` for the full machine-readable spec.

## References

- <https://gitlab.com/bms-tools/bms-tools/-/blob/master/JBD_REGISTER_MAP.md>
- <https://github.com/syssi/esphome-jbd-bms>
- <https://github.com/kolins-cz/Smart-BMS-Bluetooth-ESP32>
