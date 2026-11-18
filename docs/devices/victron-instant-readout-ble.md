# Victron Instant Readout (BLE)

> **Status**: Spec Available (unverified) — active; Victron published the format
> **Protocol**: BLE
> **Manufacturer**: Victron Energy
> **Manufacturer Status**: Active

## Overview

A read-only BLE telemetry broadcast most modern Victron products emit (MPPT chargers, BMV/SmartShunt monitors, inverters, SmartLithium). Victron itself published the advertisement format — no connection, no cloud.

## Protocol Summary

BLE manufacturer data, company id 0x02E1, record type 0x10, AES-CTR encrypted with a per-device key extracted once from VictronConnect. Records of 17–20 bytes require a second counter block; the documented MSB counter starts at zero. Record types include 0x01 Solar Charger and 0x02 Battery Monitor. Decrypted bodies are LSB-first bitstreams: check exact all-ones sentinels before sign extension or negation. Battery-monitor voltage is signed 16-bit, current signed 22-bit, consumed Ah unsigned 20-bit then negated, and SOC unsigned 10-bit.

See `device-specs/devices/victron-instant-readout-ble.yaml` for the full machine-readable spec.

## References

- <https://communityarchive.victronenergy.com/questions/93919/victron-bluetooth-ble-protocol-publication.html>
- <https://github.com/keshavdv/victron-ble>
