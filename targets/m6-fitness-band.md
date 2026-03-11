# Target: M6 Smart Fitness Band

## Target metadata
- target_id: m6-fitness-band
- app package_id(s): com.m6.fitness (approximate — generic fitness apps like H Band, FitPro, etc.)
- device class: BLE fitness tracker / smartband
- transport(s): BLE
- local-only viability: high — purely BLE, no cloud required for basic operation

## Known facts (public + observed)
- M6 Smart Fitness Band (cheap Mi Band 6 clone)
- Price: ~$6 (AliExpress)
- Uses Telink TLSR8232 SoC
- OLED display, vibration motor, heart rate sensor (optical PPG)
- Hardware fully torn down by rbaron.net with custom firmware written
- BLE protocol between phone app and device not fully documented — greenfield spec opportunity
- SWD debug interface accessible for firmware dumping/flashing
- Existing RE: rbaron.net/blog/2021/07/06/Reverse-engineering-the-M6-smart-fitness-band.html

## Device discovery signals
- BLE:
  - advertised name patterns: "M6", "M6 Band", "FitBand" (varies by firmware/rebrand)
  - service UUIDs: TBD from companion app analysis
  - address behavior: TBD

## Threat model + guardrails
- Scope: only owned devices, no safety-critical use cases.
- Fitness tracker — heart rate data is indicative only, not medical grade.

## First experiments (do these first)
1) Run ./scripts/detect_devices.sh; attach log paths.
2) Fetch APK (apkeep) for common companion apps (H Band, FitPro, etc.).
3) Static: decompile APK, identify BLE GATT services, characteristic UUIDs, command encoding.
4) Dynamic: record one "connect + sync data" HCI snoop.

## Protocol hypotheses (to validate)
- Pairing/bonding steps: likely requires bonding for persistent connection
- Session state machine: connect → bond → sync time → read data → disconnect
- Commands: set time, set alarms, read step count, read heart rate, trigger heart rate measurement
- Payload encoding: binary, likely proprietary framing (common in cheap fitness bands)
- Timing constraints: heart rate measurement takes several seconds

## Control surface inventory (what the replacement app must support)
- Onboarding/pairing UX: BLE scan for M6 name, bond
- Core controls (MVP): read step count, read heart rate, set time
- Power / brightness / modes / uploads: set alarms, notifications, sedentary reminders
- Error handling and recovery: reconnect on disconnect, handle sync failures
- Settings persistence: device stores step/HR data internally

## Evidence checklist
- APK hashes + version code: TBD
- HCI snoop log: TBD

## Spec output (clean-room)
Write a derived spec in:
- docs/specs/m6-fitness-band.md

## References (URLs only)
- https://rbaron.net/blog/2021/07/06/Reverse-engineering-the-M6-smart-fitness-band.html
