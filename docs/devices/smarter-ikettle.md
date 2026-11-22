# Smarter iKettle 2.0 / Smarter Coffee

> **Status**: Shutdown — smart features removed from the app in mid-2025
> **Protocol**: WiFi
> **Manufacturer**: Smarter Applications Ltd
> **Manufacturer Status**: Shutdown

## Overview

Wi-Fi kettles/coffee makers whose app features were removed in 2025, leaving "very expensive ordinary kettles". The LAN protocol needs no cloud, so it is the rescue path.

## Protocol Summary

Binary protocol on port 2081 (UDP or TCP), no auth, `<id> <args> 0x7e` framing. Commands (hex wire byte, decimal in brackets): 0x15 (21) boil, 0x16 (22) stop, 0x64 (100) device-info / discovery probe, 0x6d (109) firmware-update mode; responses 0x03 (3) ack, 0x14 (20) status (temperature + water level), 0x65 (101) device info.

The seven-byte status frame is `[14][flag][temperature][water_hi][water_lo][unknown][7e]`. Water is an unsigned big-endian u16 raw sensor value; a calibrated level subtracts the unit's off-base baseline. The earlier 7-off/8-on observation is unit-specific, not a Boolean or safety threshold. Temperature `0x7f` means off-base/unavailable, not 127 °C. The three-byte ACK is `[03][result][7e]`, with results 0 success, 1 busy, 4 failed and `0x69` invalid.

See `device-specs/devices/smarter-ikettle.yaml` for the full machine-readable spec.

## References

- <https://github.com/ian-kent/ikettle2/blob/master/protocol/README.md>
- <https://github.com/jkellerer/iBrew>
