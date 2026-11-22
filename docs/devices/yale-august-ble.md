# Yale Access / August BLE Locks

> **Status**: Spec Available (unverified) — active; local control needs a cloud-held offline key
> **Protocol**: BLE
> **Manufacturer**: August / Yale (ASSA ABLOY)
> **Manufacturer Status**: Active

## Overview

August / Yale Access smart locks. No official local API, but direct BLE lock/unlock works once a client holds the lock's OFFLINE KEY + slot — which must be synced from an August/Yale cloud account. After that, day-to-day unlock is fully local. yalexs-ble (Home Assistant) is the reference implementation.

## Protocol Summary

Service 0xFE24. Normal lock/status operations use write bd4ac611-… and responses on bd4ac612-…; the secure pair bd4ac613/614-… is for setup and shutdown. Normal application requests are 18-byte `0xEE` frames with the opcode at byte 1 (0x0A unlock, 0x0B lock, 0x02 status) and a negated-sum8 checksum. The two-part handshake combines two random 8-byte halves into a 16-byte session key. Setup uses AES-ECB, initially with the offline key and key slot. Later operations use that session key with independent, persistent client-to-lock and lock-to-client CBC chains: each starts with a zero IV only at session-key installation, continues across consecutive frames, and resets on reconnect. Secure-handshake frames use the documented three-term little-endian 32-bit checksum, not a bytewise sum. GETLOG (0x2D) consumes the oldest activity record; the subtype-0x09 unread-count poll does not. Manufacturer data can use Yale 0x01D1 or ASSA ABLOY 0x012E.

The YAML's `protocol_details` contains both application frames and deterministic full-ciphertext examples. Characteristic commands and entity bindings are deliberately absent because the generic schema/mobile consumer has no stateful CBC transform; writing those application bytes directly would be incorrect.

See `device-specs/devices/yale-august-ble.yaml` for the full machine-readable spec.

## References

- <https://github.com/Yale-Libs/yalexs-ble>
- <https://www.home-assistant.io/integrations/august/>
