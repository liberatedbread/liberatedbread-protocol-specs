# Target: ETEKCITY ESN00 BLE Smart Kitchen/Nutrition Scale

## Target metadata
- target_id: etekcity-smart-scale
- app package_id(s): com.vesync.vesync
- device class: BLE kitchen/nutrition scale
- transport(s): BLE
- local-only viability: high — BLE protocol partially explored, local control feasible

## Known facts (public + observed)
- ETEKCITY ESN00 Smart Nutrition Scale
- Price: $20-30
- BLE protocol partially explored via Android HCI snoop + Wireshark
- APK decompilation reveals serialization details
- No complete protocol documentation exists — greenfield spec opportunity
- Existing RE: partial, DEV Community writeup (dev.to/hertzg/hacking-ble-kitchen-scale-55io)

## Device discovery signals
- BLE:
  - advertised name patterns: "Etekcity", "ESN00"
  - service UUIDs: TBD from APK analysis
  - address behavior: TBD

## Threat model + guardrails
- Scope: only owned devices, no safety-critical use cases.
- Kitchen scale — no safety risk.

## First experiments (do these first)
1) Run ./scripts/detect_devices.sh; attach log paths.
2) Fetch APK (apkeep) for com.vesync.vesync.
3) Static: decompile APK, identify BLE serialization and GATT UUIDs.
4) Dynamic: record one "connect + weigh item" HCI snoop.

## Protocol hypotheses (to validate)
- Pairing/bonding steps: TBD from APK analysis
- Session state machine: connect → subscribe → place item → receive weight → disconnect
- Commands: tare, unit change, possibly nutritional data lookup
- Payload encoding: TBD — binary serialization found in APK
- Timing constraints: weight notifications likely continuous while item on scale

## Control surface inventory (what the replacement app must support)
- Onboarding/pairing UX: BLE scan for Etekcity name
- Core controls (MVP): read weight, tare, change units
- Power / brightness / modes / uploads: nutritional tracking (if supported)
- Error handling and recovery: reconnect on disconnect
- Settings persistence: unit preference

## Evidence checklist
- APK hashes + version code: TBD
- HCI snoop log: TBD

## Spec output (clean-room)
Write a derived spec in:
- docs/specs/etekcity-smart-scale.md

## References (URLs only)
- https://dev.to/hertzg/hacking-ble-kitchen-scale-55io
