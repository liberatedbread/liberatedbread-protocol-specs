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
- Provisioning requires `/login` + `/verify` and `X-Auth-Token` on
  `POST /xled/v1/network/status`. The legacy complete body is
  `{"mode":1,"station":{"ssid":"<ssid>","encpassword":"<ciphertext>","dhcp":1}}`;
  from 2.4.30 it is
  `{"mode":1,"station":{"encssid":"<ciphertext>","encpassword":"<ciphertext>","dhcp":1}}`.
  Through 2.4.22 the password alone uses the old 16-byte schedule; the newer
  48-byte schedule appears from 2.4.25 and encrypts both SSID and password.
  The encssid field is documented only from 2.4.30, and 2.4.23–2.4.29 behavior
  remains unresolved. Both schedules are MAC-derived obfuscation, not secret
  key management or a replacement for login.

See `device-specs/devices/twinkly-lights.yaml` for the full machine-readable spec,
including independent synthetic vectors for both RC4 uses and realtime framing.

## References

- <https://github.com/scrool/xled>
- <https://xled-docs.readthedocs.io/>
