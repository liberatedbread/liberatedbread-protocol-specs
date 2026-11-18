# b-parasite Soil Sensor

> **Status**: Spec Available (unverified) — active; open by design (BTHome v2)
> **Protocol**: BLE
> **Manufacturer**: rbaron (open-source project)
> **Manufacturer Status**: Active

## Overview

b-parasite is an open-source (nRF52) BLE soil-moisture sensor that also reports air temp/humidity, light and battery. Its default firmware broadcasts in BTHome v2 — decode per the BTHome v2 reference. Passive, no pairing, no cloud.

## Protocol Summary

Default: BTHome v2 in service data UUID 0xFCD2, keyed by MAC. Default firmware emits battery 0x01 (u8 %), temperature 0x02 (s16 LE, 0.01 °C), illuminance 0x05 (u24 LE, 0.01 lux), voltage 0x0C (u16 LE, 0.001 V), one-byte humidity 0x2E and one-byte moisture 0x2F (both 1 %). The 0x03/0x14 BTHome alternatives are not this firmware's defaults. A legacy custom advertisement is decoded separately by the ESPHome b_parasite component.

See `device-specs/devices/b-parasite-ble.yaml` for the full machine-readable spec.

## References

- <https://github.com/rbaron/b-parasite>
- <https://esphome.io/components/sensor/b_parasite.html>
