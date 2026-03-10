# Target: Xiaomi Mi Scale BLE Body Composition Scale

## Target metadata
- target_id: xiaomi-mi-scale
- app package_id(s): com.xiaomi.mifit, com.mi.health
- device class: BLE body composition scale
- transport(s): BLE
- local-only viability: high — BLE protocol RE'd via openScale project

## Known facts (public + observed)
- Xiaomi Mi Scale (v1 and v2)
- Price: $20-30
- First byte is control byte with stabilized/weight-removed flags and unit field
- Weight transmitted as little-endian integer, divide by 100 (lbs/jin) or 200 (kg)
- V2 adds impedance measurement for body composition
- Existing RE: github.com/oliexdev/openScale

## Device discovery signals
- BLE:
  - advertised name patterns: "MIBCS", "MI_SCALE", "XMTZC"
  - service UUIDs: 0x181B (Body Composition), 0x181D (Weight Scale)
  - address behavior: public

## Threat model + guardrails
- Scope: only owned devices, no safety-critical use cases.
- Weight measurement — health data, handle with privacy awareness.

## First experiments (do these first)
1) Run ./scripts/detect_devices.sh; attach log paths.
2) Fetch APK (apkeep) for com.xiaomi.mifit.
3) Static: grep for weight scale GATT service UUIDs.
4) Dynamic: capture BLE weight measurement notification.

## Protocol hypotheses (to validate)
- Pairing/bonding steps: minimal or none for basic weight reading
- Session state machine: connect → subscribe to weight notifications → step on scale → receive measurement → disconnect
- Commands: N/A (read-only)
- Payload encoding: control byte (flags) + weight as LE int16; v2 adds impedance
- Timing constraints: measurement notifications sent when weight stabilizes

## Control surface inventory (what the replacement app must support)
- Onboarding/pairing UX: BLE scan for MI_SCALE name
- Core controls (MVP): read weight, read unit (kg/lbs)
- Power / brightness / modes / uploads: body composition (v2)
- Error handling and recovery: handle unstable readings
- Settings persistence: weight unit preference

## Evidence checklist
- APK hashes + version code: TBD
- HCI snoop log: TBD

## Spec output (clean-room)
Write a derived spec in:
- docs/specs/xiaomi-mi-scale.md

## References (URLs only)
- https://github.com/oliexdev/openScale
- https://github.com/oliexdev/openScale/wiki/Xiaomi-Bluetooth-Mi-Scale
