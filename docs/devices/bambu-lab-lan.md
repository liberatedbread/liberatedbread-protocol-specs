# Bambu Lab 3D Printer (LAN mode)

> **Status**: Spec Available (unverified) — active; cloud-first vendor, LAN is the rescue
> **Protocol**: WiFi
> **Manufacturer**: Bambu Lab
> **Manufacturer Status**: Active

## Overview

Bambu Lab printers (X1/P1/A1) can be driven over the LAN with no cloud, but the 2024–2025 firmware 'authorization' change gated LAN/third-party access — so the community-documented LAN mode is the rescue path. All local transports use the printer's LAN Access Code.

## Protocol Summary

The safe default discovery is passive: listen on UDP 2021 for `NOTIFY` with `NT: urn:bambulab-com:device:3dprinter:1`, then map `USN` to the printer serial and `DevName.bambu.com` to the display name. The `Host` header's 1990 is not the socket port. The documented active `M-SEARCH` and its `ST` response remain in `protocol_details` as experimental/unsupported, not an executable discovery method: mobile's `UdpBroadcastProbe` has no `response_match` implementation, so a consumer must enforce both NT and ST itself or leave the printer unidentified rather than accept any USN datagram.

MQTT over TLS 8883 uses app-perspective directions: the client publishes to device/{serial}/request and subscribes to device/{serial}/report (pause/resume/stop/pushall). FTPS 990 carries files, and the camera uses RTSPS 322 (X1/H2) or raw TCP+TLS 6000 (A1/P1). User bblp + LAN Access Code.

See `device-specs/devices/bambu-lab-lan.yaml` for the full machine-readable spec.

## References

- <https://github.com/Doridian/OpenBambuAPI/blob/main/mqtt.md>
- <https://github.com/Doridian/OpenBambuAPI/blob/main/video.md>
- <https://github.com/Doridian/OpenBambuAPI/blob/main/ftp.md>
