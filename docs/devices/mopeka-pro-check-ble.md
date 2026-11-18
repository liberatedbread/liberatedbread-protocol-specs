# Mopeka Pro Check Tank Sensor

> **Status**: Spec Available (unverified) — active; community-decoded broadcast
> **Protocol**: BLE
> **Manufacturer**: Mopeka Products LLC
> **Manufacturer Status**: Active

## Overview

Mopeka Pro Check ultrasonic tank sensors report a tank's fill level from ultrasonic time-of-flight to the liquid surface. The BLE broadcast is decoded passively (as ESPHome does) — no cloud, no pairing.

## Protocol Summary

Passive broadcast, configured by MAC (press the sync button to surface it); do not activate an automatic scan. The shared Nordic 0x0059 header is not Mopeka identity and 0x0059 alone must never select this spec. Battery is `V=(raw&0x7F)/32`, percent `clamp((V-2.2)/0.65*100,0,100)` truncated; temperature is `(raw&0x7F)-40` °C. Level is 14-bit LE across bytes 3–4, quality is byte 4 bits 7–6 (3 HIGH, 2 MEDIUM, 1 LOW, 0 ZERO), and compensated distance is `uint32(raw_level*(0.573045-0.002822*raw_t-0.00000535*raw_t^2))` mm. Bytes 5–9 remain undecoded. Tank level derives from distance via tank-shape calibration.

See `device-specs/devices/mopeka-pro-check-ble.yaml` for the full machine-readable spec.

## References

- <https://esphome.io/components/sensor/mopeka_pro_check.html>
