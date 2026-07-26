# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- SPOTLED LED panel device doc, device spec and target starter — the OEM matrix-panel family
  (hats, badges, packs, banner signs) behind `com.led.spotled`, now the canonical home for the
  `0xFF20` protocol
- LED sign & panel design app survey (`docs/devices/led-sign-apps.md`) mapping design apps to
  device families, OEM platform clusters, and a triage checklist for unknown signs
- CoolLEDX / CoolLED1248 device doc, device spec and target starter — the unbranded BLE LED sign
  platform behind most AliExpress/Amazon car, bike, backpack and badge signs
- Target starters for iLEDColor (`com.led.iledcolor`), LED space (`com.yj.led`) and
  Divoom Pixoo (`com.divoom.Divoom`)
- OBD-II / vehicle diagnostics support: `docs/protocols/obd2-common.md` covering
  connectors (SAE J1962, ISO 19689), transports, ISO-TP framing, UDS services and
  capture methodology
- OBD-II Bluetooth adapter (ELM327 / STN) device doc and spec — BLE GATT families,
  Bluetooth Classic SPP, and the AT/ST command set
- Triumph Tiger 900 device doc, target spec and device spec, focused on the service
  interval (SIA) reset message; transport confirmed, reset request still uncaptured
- `obd` block and `obd2` protocol value in `device-specs/schema.json`, with a
  per-fact `verification` level so untested hypotheses cannot be mistaken for facts
- `scripts/obd_discover.py` — read-only ECU and DID reconnaissance over an
  ELM327-class adapter
- Initial project structure
- Device documentation template
- Getting started guides
- MkDocs Material theme configuration

### Changed

- LEDs2Rave4 / Lunchbox Dream LED docs now map each product generation to its design app
  (LED CHORD → SPOTLED → iLEDColor) and document the SPOTLED framed BLE protocol on `0xFF20`,
  corroborated against `python-spotled`
