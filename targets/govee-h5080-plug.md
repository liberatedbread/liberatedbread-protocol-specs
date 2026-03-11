# Target: Govee H5080 BLE Smart Plug

## Target metadata
- target_id: govee-h5080-plug
- app package_id(s): com.govee.home
- device class: BLE smart plug
- transport(s): BLE
- local-only viability: high — BLE-only plug, no WiFi or cloud dependency

## Known facts (public + observed)
- Govee H5080 BLE Smart Plug
- Price: $15-20
- BLE-only — no WiFi radio, purely local control
- Home Assistant integration exists but protocol not formally documented
- Power command uses packet type 0x33
- Same BLE packet framework as other Govee BLE devices (0xAA/0x33 prefixes, XOR checksum)
- Existing RE: github.com/virtuald/govee-ble-plugs, github.com/egold555/Govee-Reverse-Engineering

## Device discovery signals
- BLE:
  - advertised name patterns: "GVH5080_XXXX", "ihoment_H5080_XXXX"
  - service UUIDs: TBD from RE projects (likely same family as H6001)
  - address behavior: public

## Threat model + guardrails
- Scope: only owned devices, no safety-critical use cases.
- Smart plug controls power — avoid safety-critical loads.

## First experiments (do these first)
1) Run ./scripts/detect_devices.sh; attach log paths.
2) Fetch APK (apkeep) for com.govee.home.
3) Static: grep for BLE write characteristic UUIDs, power command format.
4) Dynamic: record one "connect + toggle on/off" HCI snoop.

## Protocol hypotheses (to validate)
- Pairing/bonding steps: no bonding required, open BLE write
- Session state machine: connect → write command → disconnect
- Commands: on (0x33 + on payload), off (0x33 + off payload)
- Payload encoding: 20-byte packets, XOR checksum in final byte (same as Govee bulb family)
- Timing constraints: unknown

## Control surface inventory (what the replacement app must support)
- Onboarding/pairing UX: BLE scan for GVH5080 name pattern
- Core controls (MVP): on/off toggle, get current state
- Power / brightness / modes / uploads: N/A (binary on/off)
- Error handling and recovery: reconnect on disconnect
- Settings persistence: device retains state across power cycles

## Evidence checklist
- APK hashes + version code: TBD
- HCI snoop log: TBD

## Spec output (clean-room)
Write a derived spec in:
- docs/specs/govee-h5080-plug.md

## References (URLs only)
- https://github.com/virtuald/govee-ble-plugs
- https://github.com/egold555/Govee-Reverse-Engineering
