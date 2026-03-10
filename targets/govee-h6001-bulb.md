# Target: Govee H6001 BLE Smart Bulb

## Target metadata
- target_id: govee-h6001-bulb
- app package_id(s): com.govee.home
- device class: BLE smart bulb
- transport(s): BLE
- local-only viability: high — BLE protocol fully reverse-engineered for local control

## Known facts (public + observed)
- Govee H6001 BLE LED smart bulb
- Price: ~$13
- Govee intentionally disables local API, forcing cloud dependency
- BLE protocol fully reverse-engineered
- Packets start with 0xAA, 0x33, or 0xA3
- Padded to 20 bytes with XOR checksum
- Existing RE: github.com/chvolkmann/govee_btled, blog.coding.kiwi/reverse-engineering-govee-smart-lights/

## Device discovery signals
- BLE:
  - advertised name patterns: "ihoment_H6001_XXXX"
  - service UUIDs: TBD from APK analysis
  - address behavior: public

## Threat model + guardrails
- Scope: only owned devices, no safety-critical use cases.
- Light bulb only — no safety risk beyond light output.

## First experiments (do these first)
1) Run ./scripts/detect_devices.sh; attach log paths.
2) Fetch APK (apkeep) for com.govee.home.
3) Static: grep for UUIDs/endpoints + identify BLE write characteristic.
4) Dynamic: record one "connect + set color" HCI snoop.

## Protocol hypotheses (to validate)
- Pairing/bonding steps: no bonding, open BLE write
- Session state machine: connect → write → disconnect
- Commands: on/off (0x33 prefix), color set (0xA3 prefix), brightness
- Payload encoding: 20-byte packets with XOR checksum in final byte
- Timing constraints: unknown

## Control surface inventory (what the replacement app must support)
- Onboarding/pairing UX: BLE scan for ihoment_H6001 name
- Core controls (MVP): on/off, color (RGB), brightness
- Power / brightness / modes / uploads: color temperature, scene modes
- Error handling and recovery: reconnect on disconnect
- Settings persistence: device retains last state on power cycle

## Evidence checklist
- APK hashes + version code: TBD
- HCI snoop log: TBD

## Spec output (clean-room)
Write a derived spec in:
- docs/specs/govee-h6001-bulb.md

## References (URLs only)
- https://github.com/chvolkmann/govee_btled
- https://github.com/egold555/Govee-Reverse-Engineering
- https://blog.coding.kiwi/reverse-engineering-govee-smart-lights/
- https://www.xda-developers.com/reverse-engineered-govee-smart-lights-smart-home/
