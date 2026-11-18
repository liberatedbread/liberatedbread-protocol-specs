# SESAME (CANDY HOUSE) BLE Locks

> **Status**: Spec Available (unverified) — active; vendor publishes the protocol
> **Protocol**: BLE
> **Manufacturer**: CANDY HOUSE
> **Manufacturer Status**: Active

## Overview

SESAME locks by CANDY HOUSE are developer-friendly: the vendor publishes the full SesameOS3 BLE protocol and open SDKs, and the vendor app runs on the same SDK. Full local lock/unlock/history works with no cloud once the per-device secret is held.

## Protocol Summary

Service 0xFD81; write commands **without response** to 16860002-…, notify on 16860003-…. 20-byte segments. Lock/unlock application requests are `[52 00]` / `[53 00]` when using an empty history tag: the second byte is the tag length, so the bare item code is incomplete. History request `[04 01]` peeks at the oldest record without deleting it; deletion is a separate explicit operation with the returned record ID. Mechanical-status target `0x8000` means unavailable, and battery raw units are 2 mV. Crypto: SECP256R1 ECDH at registration → device_secret; AES-CMAC session token; AES-CCM payloads with a ±3 s time check.

See `device-specs/devices/sesame-candyhouse-ble.yaml` for the full machine-readable spec.

## References

- <https://github.com/CANDY-HOUSE/API_document/blob/master/docs/en/SesameOS3/bluetooth.md>
- <https://github.com/homy-newfs8/libsesame3bt-core>
- <https://docs.candyhouse.co/>
