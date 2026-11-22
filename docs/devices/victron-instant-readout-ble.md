# Victron Instant Readout (BLE)

> **Status**: Spec Available (unverified) — active; Victron published the format
> **Protocol**: BLE
> **Manufacturer**: Victron Energy
> **Manufacturer Status**: Active

## Overview

A read-only BLE telemetry broadcast most modern Victron products emit (MPPT chargers, BMV/SmartShunt monitors, inverters, SmartLithium). Victron itself published the advertisement format — no connection, no cloud.

## Protocol Summary

BLE manufacturer data, company id 0x02E1, record type 0x10, AES-CTR encrypted with a per-device key extracted once from VictronConnect. Records of 17–20 bytes require a second counter block; the documented MSB counter starts at zero. Record types include 0x01 Solar Charger and 0x02 Battery Monitor. Solar and battery-monitor voltage are signed 16-bit. Battery Monitor uses a 2-bit AUX selector at bit 64: 0 starter voltage (signed 0.01 V), 1 midpoint voltage (0.01 V), 2 temperature (0.01 K), 3 no AUX. Current starts at bit 66 (signed 22-bit), consumed Ah at bit 88 (unsigned 20-bit then negated), and SOC at bit 108 (unsigned 10-bit). Alarm `0xffff` is a valid full bitmask and AUX `0xffff` is valid input, not universal NA; apply only documented per-field sentinels before sign extension or negation.

See `device-specs/devices/victron-instant-readout-ble.yaml` for the full machine-readable spec.

## References

- <https://communityarchive.victronenergy.com/questions/93919/victron-bluetooth-ble-protocol-publication.html>
- <https://github.com/keshavdv/victron-ble>
