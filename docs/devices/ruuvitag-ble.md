# RuuviTag

> **Status**: Spec Available (unverified) — active; open published format
> **Protocol**: BLE
> **Manufacturer**: Ruuvi Innovations Ltd
> **Manufacturer Status**: Active

## Overview

The RuuviTag is an open BLE environmental sensor. Ruuvi publishes its advertisement formats and firmware — passive listen, no pairing, no cloud.

## Protocol Summary

Manufacturer data, company id 0x0499. Data Format 5 (RAWv2), 24 bytes MSB-first: temperature ×0.005 °C @1, humidity ×0.0025 % @3, pressure raw + 50000 Pa @5, acceleration, battery/TX power, sequence and MAC. Battery raw 0x7FF, TX raw 0x1F and all-ones MAC are unavailable. Legacy DF3 (14 bytes) uses sign-magnitude temperature `(-1 if byte2 & 0x80 else +1) * ((byte2 & 0x7F) + byte3/100)`, not int16; official vector `03 29 1a 1e ce 1e fc 18 f9 42 02 ca 0b 53` decodes to 26.30 °C.

See `device-specs/devices/ruuvitag-ble.yaml` for the full machine-readable spec.

## References

- <https://docs.ruuvi.com/communication/bluetooth-advertisements/data-format-5-rawv2>
- <https://docs.ruuvi.com/communication/bluetooth-advertisements/data-format-3-rawv1>
