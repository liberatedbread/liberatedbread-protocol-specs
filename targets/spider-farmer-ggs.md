# Target: Spider Farmer GGS BLE Grow Light Controller

## Target metadata
- target_id: spider-farmer-ggs
- app package_id(s): spider.farmer (approximate; confirm from Play Store)
- device class: BLE grow light controller
- transport(s): BLE
- local-only viability: high — BLE protocol fully RE'd, ESP32 MQTT bridge available

## Known facts (public + observed)
- Spider Farmer GGS grow light controller
- Price: $30-50
- Marketed as requiring cloud but actually uses simple local BLE protocol
- Fully reverse-engineered with ESP32 MQTT bridge for cloud-free operation
- Demonstrates that "cloud-required" claims are often false
- Relevant to OpenGreenIoT mission (literal plant growing hardware)
- Existing RE: github.com/cr0ssn0tice/Spider-Farmer-GGS-Controller-MQTT

## Device discovery signals
- BLE:
  - advertised name patterns: "GGS", "Spider Farmer"
  - service UUIDs: TBD from RE project
  - address behavior: TBD

## Threat model + guardrails
- Scope: only owned devices, no safety-critical use cases.
- Controls grow lights — moderate power draw, but no critical safety risk.

## First experiments (do these first)
1) Run ./scripts/detect_devices.sh; attach log paths.
2) Fetch APK (apkeep) for Spider Farmer app.
3) Static: grep for BLE UUIDs and command formats.
4) Dynamic: record one "connect + set light level" HCI snoop.

## Protocol hypotheses (to validate)
- Pairing/bonding steps: TBD from RE project
- Session state machine: connect → send command → disconnect (or maintain)
- Commands: set brightness/dimming level, on/off, schedule timers
- Payload encoding: simple BLE write commands
- Timing constraints: TBD

## Control surface inventory (what the replacement app must support)
- Onboarding/pairing UX: BLE scan for GGS name
- Core controls (MVP): on/off, brightness/dimming level
- Power / brightness / modes / uploads: scheduling, timer modes
- Error handling and recovery: reconnect on disconnect
- Settings persistence: device may store schedules internally

## Evidence checklist
- APK hashes + version code: TBD
- HCI snoop log: TBD

## Spec output (clean-room)
Write a derived spec in:
- docs/specs/spider-farmer-ggs.md

## References (URLs only)
- https://github.com/cr0ssn0tice/Spider-Farmer-GGS-Controller-MQTT
