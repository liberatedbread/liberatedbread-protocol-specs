# Pix Backpack / Pix Mini — target spec starter

## Target metadata
- target_id: pix-backpack
- app package_id: style.pix.app — **v1.40** (versionCode 3040) analyzed; minSdk 21,
  targetSdk 29. Delisted from Google Play; recovered from a third-party APK mirror
  (XAPK: base + arm64 config split).
- app type: **React Native** — all protocol logic lives in the JavaScript bundle;
  the native side is stock RN boilerplate and BLE rides the stock
  react-native-ble-manager library (no custom native code, no vendor SDK, no
  crypto besides MD5 for firmware integrity).
- vendor: Pix Inc. (pix.style) — **appears defunct**; app delisted, stage
  environment hostnames shipped in a release build. Abandoned-hardware rescue.
- device class: wearable 16×20 RGB LED matrix backpack (Kickstarter 2018); smaller
  kids' variant **Pix Mini** (2019). USB-power-bank powered — no internal battery.
- transport(s): Bluetooth (BLE). Wi-Fi exists on-device but is used ONLY for
  device-side firmware download during OTA — phone↔device control is BLE only
  (no Wi-Fi/UDP/TCP transport libraries in the app).
- local-only viability: **HIGH** — scan/connect/upload/brightness/text/widgets/games
  are pure local BLE; the cloud was marketplace + firmware hosting only.

## Product variants
The app selects the product at BUILD time; the analyzed build is "original"
(Pix Backpack). UUID bases:

| Variant | Service-UUID base `0000XXXX-…` | Status |
|---|---|---|
| Pix Backpack (legacy fw) | `e984-11e7-b78e-ffd6fcc3450f` | mapped |
| Pix Backpack (V1 fw) | `e984-11e7-b78e-ffd6fcc34510` | mapped |
| Pix Mini | `9552-4325-8021-a85f8136a5c4` | UUID recorded; never exercised in this build — geometry/layout unconfirmed |

Legacy vs V1 is chosen at connect time from the DISCOVERED services: legacy 0100
present → legacy base, else V1. Characteristic layout is identical between bases.

## Known facts (from app analysis)
- Advertised name rule: lowercase, split on spaces — first word `pix`, last word
  exactly 12 hex digits (the MAC, doubles as device id): `pix <12-hex-MAC>`.
- GATT: service `0100`; chars `0101` RPC write (declared response char is the SAME
  `0101`, never subscribed — no ACKs, fire-and-forget), `0103` width, `0104`
  height, `0105` max frames, `0106` brightness (`floor(255*level)`), `0107`/`0108`/
  `0109` OTA enable/config/state, `0110` demo. DIS `180A`: `2A26`/`2A27` read at
  connect. Optional MTU 517 request (Android); default 20-byte write chunks.
- RPC frame: `[callId u8 (wraps 255→0), opcode u8, payload…]` — no length, no
  checksum, no crypto.
- Opcodes: 0 SET_FRAME, 1 SET_PALETTE, 2 SET_FRAME_COUNT (0 = erase),
  3 SET_FRAMES_DURATIONS (u16LE ms, default 80), 4 SET_ANIMATION_DIRECTION
  (0 normal / 1 alternate / 2 normal-stop / 3 alternate-stop),
  5 SAVE_TO_PERSISTENT_MEMORY (autostart on boot), 6 PRINT_MEMORY (debug),
  7 SET_CONFIG (render mode + config, 512-byte chunks), 8 SET_INPUT
  (widget/game input; 1 START / 2 STOP / 3 RESET / 4 LAP), 9 RESTART.
- Render modes (first SET_CONFIG byte): 0 NONE, 1 ANIMATION, 2 SCROLLING,
  3 OTA_PROGRESS, 6 CLOCK, 7 BIKE, 8 COUNTDOWN, 9 STOPWATCH, 16 PIX_BLOCKS,
  17 PIXEL_BREAKER, 18 CRAWLER. Widgets need fw ≥ 2.2.5.
- Pixels: palette-indexed — RGB888 palette uploaded first (≤160 colors/480 B per
  SET_PALETTE call, second call at index 160), then 1 byte/pixel palette index,
  row-major, width×height bytes per frame (320 B @ 16×20).
- Upload sequence (the app's upload orchestrator): clear screen → erase
  (frame count 0) → palette → frames → durations → direction → count(n) →
  save-to-flash if "play on boot".
- OTA: device-side Wi-Fi HTTP download. App writes a 215-byte blob to `0108`
  (ssid pad32, pass pad64, flags 0, host pad32, port u16LE = **80**, path pad64,
  size u32LE, md5 raw 16 B) between writes of 0 and 1 to `0107`; device joins the
  named 2.4 GHz network and plain-HTTP GETs the image, MD5-verified. Metadata was
  `GET {api}/firmware?fields=latest`, binary at `{device-gateway}/firmware/{version}`.
  Needs hardwareVersion ≥ 3.1.
- Cloud endpoints in this (release!) build are the STAGE environment:
  `app.stage.pix.style/api/pix/1.0.0`, `device-gateway.stage.pix.style/...` —
  production siblings (`app.pix.style`, `device-gateway.pix.style`) presumably
  existed. Also: silent anonymous-account creation for the marketplace (optional
  Google sign-in), a Tilda-hosted news feed, Firebase, Branch.io, Facebook SDK,
  Sentry. None of it is on the control path.

## Device discovery signals
- BLE name regex: `^[pP][iI][xX]( .+)? [0-9a-fA-F]{12}$`
- Service UUIDs (scan filter): `00000100-e984-11e7-b78e-ffd6fcc3450f`,
  `00000100-e984-11e7-b78e-ffd6fcc34510` (mini: `00000100-9552-4325-8021-a85f8136a5c4`)
- Geometry is device-reported (0103/0104/0105) — read it, don't assume 16×20
  (matters for the Mini).

## Threat model + guardrails
- Owned devices only. The backpack connects without bonding and accepts uploads
  from anyone in range — a wearer-privacy consideration (anyone nearby can draw on
  your back), not an attack surface to tool against.
- OTA is the sensitive path: the Wi-Fi passphrase crosses an unencrypted, unbonded
  BLE link in cleartext, and the firmware fetch is plain HTTP on port 80. Use a
  throwaway hotspot; never hand it a real network's credentials in public.

## Remaining experiments
1) **Live capture (highest priority)**: connect → read geometry → upload a small
   animation → brightness sweep. Confirms the whole write path against hardware.
2) Subscribe to `0101` notifications and issue commands — does firmware stream RPC
   responses the app never listens for?
3) Read `0105` (max frames) and probe the real palette cap (256 assumed).
4) Extract the config byte layouts for CLOCK/BIKE/COUNTDOWN/STOPWATCH and the three
   games from the bundle (present, not yet pulled).
5) Probe SET_FRAME's offset field (partial-frame writes?) and demo char `0110`.
6) OTA rehearsal against a rescue server (HTTP :80 + matching size/MD5) with a
   sacrificial image — image format unknown (ESP32-class bin suspected); confirm
   chip family via FCC ID or image header.
7) Pix Mini: scan one, confirm the mini base UUID, read geometry, check whether the
   characteristic layout matches.

## Control surface inventory (replacement app MVP)
- scan (`pix <hex>` / 0100 filter) + connect + base-UUID selection
- read geometry/firmware/hardware at connect
- brightness slider (0–255)
- still-image and animation upload: palette → frames → durations → direction →
  count → optional save-to-flash; local gallery that survives reinstall
- scrolling text (mode 2: 8×20 sprites as frames + config blob)
- clear screen (mode NONE), restart
- stretch: clock/stopwatch/countdown widgets, OTA against a self-hosted rescue
  server

## References
- Machine-readable spec: `device-specs/devices/pix-backpack.yaml` (this repo)
- User page: `docs/devices/pix-backpack.md` (this repo)
- Hackster, "PIX: Interactive Animated LED Backpack": https://www.hackster.io/news/pix-interactive-animated-led-backpack-d29f09a138c2
- Pix Mini press release (2019): http://www.prweb.com/releases/pix_mini_the_first_smart_backpack_for_kids_more_than_doubles_goal_to_raise_37_000_and_counting_on_kickstarter/prweb16375233.htm
- pix.style via the Wayback Machine: https://web.archive.org/web/2019*/pix.style
- Delisted Play listing: https://play.google.com/store/apps/details?id=style.pix.app
