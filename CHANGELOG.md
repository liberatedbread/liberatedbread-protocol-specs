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
- Triumph Tiger 900 device doc, target spec and device spec, including the recovered
  service interval reset message (`33 <km/100>` / `34 <miles/100>` on CAN 0x701 to the
  instrument cluster) and the surrounding diagnostic surface — four separate stacks,
  UDS DIDs, DTC read/clear, ABS bleed, TPMS/immobiliser and instrument settings —
  derived from static analysis of the freeware TigerTool V3.51 and independently
  confirmed by decompiling TuneECU 23
- `obd` block and `obd2` protocol value in `device-specs/schema.json`, with a
  per-fact `verification` level so untested hypotheses cannot be mistaken for facts
- OBD-II device classification: `obd.role` (vehicle / adapter / module),
  `obd.adapter_profile` capability tiers (basic-clone, standards-elm327,
  advanced-stn, native-can), and per-request `command_class` (basic vs advanced)
  with a `requires` capability list, so a consumer can tell before connecting
  whether a given adapter can run a given command
- BMW motorcycle diagnostics device doc and spec — BMW's 0x6F1 D-CAN addressing with
  CAN extended addressing, the service interval data model (distance/date/valve-clearance),
  cluster-owned service data, module list, and the service reset itself — UDS
  WriteDataByIdentifier on BMW's 0xE1xx DIDs (`2E E1 2B/2C/2D`) with matching reads —
  recovered from the shipped MotoScan app
- BMW motorcycle / MotoScan target starter (`de.wgsoft.motoscan`) — the same
  service-interval-reset problem as the Triumph work, with an analysis plan and the
  observation that the app vendor also makes the UCSI-2100 adapter whose 255-byte
  message support exists because BMW's protocols need it
- Named OBD-II adapter coverage: UniCarScan UCSI-2100, OBDLink MX and OBDLink MX+,
  with per-model capability profiles, plus an `alt_can_bus` capability (Ford MS-CAN /
  GM SW-CAN) and a tool-requirement matrix covering FORScan, TuneECU, TigerTool,
  MotoScan, BimmerCode, OBD Fusion and Torque Pro
- `scripts/obd_discover.py` — read-only ECU and DID reconnaissance over an
  ELM327-class adapter, plus working vehicle modes: `--triumph-sia` /
  `--triumph-reset` for the Triumph cluster and `--bmw-scan` / `--bmw-module` for
  BMW's 0x6F1 addressing. The BMW scan supplies the module addresses the decompile
  did not; the Triumph reset reads state before and after and refuses to run
  without `--yes-write`
- Vendor ECU-description file references in the schema: `obd.description_files` at
  vehicle and per-ECU level for BMW/EDIABAS SGBD `.prg` and `.grp` files (plus ODX,
  PDX, CDD, A2L and DBC), and per-request `job` / `results` linkage so a recovered
  frame ties back to its authoritative definition. Files are referenced and
  checksummed, never redistributed
- Triumph odometer reply decoded from TigerTool's parser: `0D 01` answers
  `704 8D 01 <b1> <b2> <b3>`, a 24-bit big-endian value in kilometres, with
  `5E 01` -> `704 DE` flagging a TFT dash and selecting which mile divisor
  (1.60934 vs 1.6099895) the tool applies
- Fardriver ND-series motor controller device doc, target spec and device spec —
  BLE sine-wave/FOC controllers of the ND72xxx family (QS Motor hub kits,
  e-motorcycle builds and app-connected classic-scooter EV conversions). Free-running
  16-byte `0xAA` status notifications reassembled into a 512-byte memory image with
  CRC16 (poly `0x8005`, init `0x7F3C`), and a documented parameter/system write path
  carried behind an `advanced` opcode flag. Framing, CRC and field offsets are
  `reported` from public community RE; the per-unit BLE-bridge UUIDs are `hypothesis`
  and the Retrospective Project:E vendor attribution inferred — nothing confirmed from
  a physical unit. No auto-identification block is declared, deliberately: the sole
  advertised signal (`0xFFE0`) is the generic HM-10 BLE-UART service and unsafe to
  match on
- Bafang BBS02 mid-drive device doc, target spec and device spec — the 36–48 V
  conversion kit sharing a controller and config protocol with the BBS01/BBSHD.
  A 1200-baud UART request/response configuration bus on the display harness, reached
  by USB programming cable or over BLE through an aftermarket bridge display
  (EggRider V2, `com.eggbikes.EggRider`, whose own BLE UUIDs are undocumented). The
  read/write opcode set, the basic/pedal/throttle parameter blocks and the
  direction-dependent checksum asymmetry are catalogued, with the four writes flagged
  `advanced`. The protocol is already public — transcribed from MIT-licensed community
  work (OpenBafangTool, two bafang-python forks) — so `reported` throughout, not
  confirmed against a physical unit; the ambiguous write length byte is left unasserted
- Tongsheng TSDZ2 mid-drive device doc, target spec and device spec — a torque-sensing
  DIY mid-drive on a plain 9600-baud TTL serial link (not the BBS02's 1200), documented
  as a continuous bidirectional stream rather than request/response: the motor pushes
  9-byte `0x43` status frames 8×/s and the display pushes 7-byte `0x59` control frames
  15×/s, with an 8-bit sum checksum both ways. The control packet is the write path,
  so `display_control` is marked `writes: true` and `advanced`. `reported` from
  community work (hurzhurz/tsdz2) and OSF forks, nothing captured from a physical unit;
  widely-installed open-source firmware changes the protocol, so a mismatching capture
  most likely means OSF
- Bosch Performance Line CX (Gen4) e-bike system device doc, target spec and device
  spec — the most closed mainstream e-bike system (Kiox display, eBike Flow app), where
  fault detail, component pairing and firmware updates sit behind Bosch dealer tooling.
  Documented as a starting kit, not a protocol: how to get onto the 500 kbit/s CAN bus
  (D-Sub 9 / CiA DS-102 breakout, SocketCAN/can-utils tooling) plus a single
  `hypothesis` frame (`061#00` start/stop) as the entire public message catalogue.
  Link parameters and wiring are `reported` and reproducible; nothing observed on our
  own bus. Community CAN RE (bosch-nerds/ebike) is early-stage, and there is no radio
  to scan — reaching the bus needs a CAN interface and physical harness access
- NIU electric scooter device doc, target spec and device spec — recorded as a cloud
  dependency rather than a control surface: the scooter reports over cellular to NIU's
  servers and the app (`com.niu.manager`) reads everything back via OAuth2
  (`account-fk.niu.com`, `app-api-fk.niu.com`), so `cloud.required: true` and every
  documented function 404s if the service is retired. The scooter's own BLE link — the
  genuine local-first target — is undocumented (no UUIDs, framing or pairing flow), and
  the only shipped local route is an aftermarket Bluetooth controller that replaces the
  motor controller and frees drive parameters only, leaving telemetry, GPS and alarm
  cloud-tethered. `reported` from maintained third-party integrations, none exercised
  by us and dual-battery captures only; no real token or serial is committed, since a
  token exposes the owner's live location
- Motorcycle ground-effect LED controllers — ProGLOW/TTCBLE and Seeblue/LEDGlow device
  specs on a combined `docs/devices/motorcycle-ground-effect-lighting.md` page, with a
  shared target spec — white-label BLE underglow modules recovered from static APK
  analysis. ProGLOW (`com.ttcble.proglow`): unencoded GATT writes on service `0x1000` /
  characteristic `0x1001`, packets led by a `0x3C` header with no checksum in the
  command builder. Seeblue (`com.seeblue.ledglow_moto` v1.9.1, `com.seeblue.ledglowv2`
  v1.4.1): a `[0x95, len, index, protocol_id, payload, checksum]` envelope on service
  `0xffe5` (TX `0xffe9`, RX `0xffe4`) with an 8-bit two's-complement checksum. Derived
  from static analysis only — not yet hardware-verified
- Initial device setup (provisioning) coverage:
  - `device.setup` block in `device-specs/schema.json` — onboarding methods,
    factory reset procedures, rebinding, and credential handling
  - `device.setup` populated for every device spec, including the OBD-II
    vehicles and adapter, where `factory_reset.applicable: false` records
    that a vehicle has no reset rather than inventing one
  - `docs/protocols/device-setup.md` — cross-device onboarding patterns for
    WiFi (SoftAP) and BLE devices
  - `docs/devices/wemo-setup.md` — Wemo factory reset, provisioning over the
    device's setup AP, and rebinding to a new network via `ReSetup`
- `scripts/test_wemo_scaffolding.py` — pins the Wemo scaffolding to the spec it
  verifies, so a script that has drifted cannot pass for a verified document.
  Skips cleanly when the scripts are removed
- `scripts/test_wemo_spec.py` — proves the Wemo spec is implementable from the
  spec alone for all three client jobs (discover, control, provision):
  transcribes the published protocol using only the standard library and
  `openssl`, and asserts the transcription reproduces the spec's own examples
  and test vectors
- `docs/api/spec-format.md` — how to read a device spec, with the `setup` block
  covered field by field
- `scripts/test_device_specs.py` — cross-spec consistency checks for conventions
  the schema cannot express (explicit `verified`, reset procedures with steps,
  `rejoin` answering the router-replacement question, and so on)
- Schema documents the well-known `setup` extension blocks — `payload_formats`,
  `timing`, `troubleshooting`, and a much richer `credential_encryption`
  including `algorithm_steps`, `variants` and `test_vectors`
- `wemo-devices.yaml` is now implementable on its own: SOAP wire format,
  `MetaInfo`/`ApList` payload layouts, the encryption algorithm step by step
  with reproducible test vectors, timing constants and a troubleshooting table
- `requirements-dev.txt` and `pyproject.toml` — ruff and pytest configuration
- CI `lint-and-test` job running `ruff check` and `pytest`
- Initial project structure
- Device documentation template
- Getting started guides
- MkDocs Material theme configuration

### Changed

- Reframed the OBD-II guardrails for repair-café use: maintenance writes (service
  interval resets, TPMS sensor IDs, clearing recorded faults) are in scope and are the
  point, with a function-risk tier table and bench sequences for the Triumph and BMW
  service resets
- Coding, flashing, immobiliser and key work are documented and flagged
  `advanced: true` in the schema rather than excluded — reviving an old bike needs
  them. Only odometer falsification and work on a moving vehicle stay out
- LEDs2Rave4 / Lunchbox Dream LED docs now map each product generation to its design app
  (LED CHORD → SPOTLED → iLEDColor) and document the SPOTLED framed BLE protocol on `0xFF20`,
  corroborated against `python-spotled`
- The Wemo protocol now lives in `device-specs/devices/wemo-devices.yaml`
  rather than in scripts: the SSDP datagram and response handling, the rule
  separating Wemo from other UPnP responders, the description parse rules
  including Belkin's vendor extensions, the SOAP wire format, and
  `payload_formats` for `BinaryState`, `InsightParams` and `MetaInfo`.
  `scripts/wemo_discover.py`, `wemo_control.py` and `wemo_setup.py` are
  retained only as verification scaffolding until the spec has been checked
  against hardware, and are marked as such (#16).

### Fixed

- `InsightParams` was documented without the `wifipower` field, which shifts
  every power reading one column left — now published field by field with an
  example
- `test_build_index.py`: hardcoded device list had rotted into a failing test
- `mkdocs.yml`: ten device pages existed but were missing from the nav
- `docs/devices/wifi-discovery.md`: content appeared above the page title
- `docs/devices/vector-robot.md`: corrected the repository URL and a heading level
- `docs/devices/discovery.yaml`: split into separate YAML documents; the four
  examples shared one top-level key and collided
- Device specs: removed `local_name_prefix: ""` values, which match every
  BLE device when used as a scan filter
- `targets/wemo-devices.md` claimed WiFi provisioning was app-only and out of
  scope, gave the setup AP prefix as `WeMo.Setup.`, and called `InsightParams`
  colon-delimited — all three contradicted by this branch's own findings
- `VERIFICATION_REFERENCE.md` now says on its face that it is not reproducible,
  since its APK column probes the gitignored workspace directory (#18)
- Wemo SOAP requests put action arguments in the service namespace
  (`<u:BinaryState>`); UPnP arguments are unqualified, and the request body now
  matches the wire format pywemo and ouimeaux send
- Wemo setup: the passphrase length suffix was not zero-padded, so any length
  below 16 produced a blob the device rejects; MetaInfo field order was
  documented backwards (field 0 is the MAC, field 1 the serial); only one of
  the three encryption variants was implemented; `ReSetup` was called without
  its required `Reset` scope argument; and `ApList` parsing did not skip the
  header line or read the auth/cipher pair from the last column
