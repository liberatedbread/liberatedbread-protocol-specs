# Twinkly Smart Lights

> **Status**: Spec Available (unverified) — active
> **Protocol**: WiFi
> **Manufacturer**: Ledworks Srl (Twinkly)
> **Manufacturer Status**: Active

## Overview

App-controlled decorative RGB/RGBW string, curtain and matrix lights. Control is a private-but-reverse-engineered local REST API (the promised public API never shipped); xled documents it.

## Protocol Summary

HTTP REST on port 80 with a short-lived token (`/xled/v1/login` + `/verify`, `X-Auth-Token`), plus a UDP 7777 realtime per-pixel channel. Discovery is a UDP 5555 broadcast.

- Turn-on is `POST /xled/v1/led/mode` with `{"mode":"color"}`, which does not
  require an uploaded movie. Static RGB uses `POST /xled/v1/led/color` with
  `red`, `green` and `blue` bytes. Effects use `/led/mode` with
  `{"mode":"effect","effect_id":N}`; query `/led/effects` for availability.
- Realtime v2 has one trailing zero byte after the eight-byte token; v3 has
  two zero bytes before its fragment number. v3 fragments are at most 900
  bytes. RGB order is R,G,B; RGBW order is W,R,G,B.
- Challenge verification repeats the six-byte MAC to 16 bytes, XORs
  `evenmoresecret!!`, RC4-encrypts the raw challenge, and compares the SHA1
  hex digest. This authenticates the device using public identity; it is not
  client access control.
- Provisioning is not plaintext: through 2.4.22 the password alone is
  RC4-encrypted with the old 16-byte schedule; from 2.4.25 both SSID and
  password use the newer 48-byte schedule and Base64. Both are MAC-derived
  obfuscation, not secret key management.

See `device-specs/devices/twinkly-lights.yaml` for the full machine-readable spec,
including independent synthetic vectors for both RC4 uses and realtime framing.

## References

- <https://github.com/scrool/xled>
- <https://xled-docs.readthedocs.io/>
