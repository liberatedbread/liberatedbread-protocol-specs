# Target: Govee H5075 BLE Thermometer/Hygrometer

## Target metadata
- target_id: govee-h5075-thermo
- app package_id(s): com.govee.home
- device class: BLE thermometer/hygrometer
- transport(s): BLE (advertisement broadcast)
- local-only viability: high — broadcasts temp/humidity via BLE advertisements every 2 seconds

## Known facts (public + observed)
- Govee H5075/H5074 temperature and humidity sensor
- Price: $10-15
- Broadcasts data via BLE advertisements using custom manufacturer data
- UUID identifier: "INTELLI_ROCKS_HW"
- Govee intentionally disables local API on many products, forcing cloud dependency
- Multiple RE projects exist but no unified spec
- Existing RE: github.com/wcbonner/GoveeBTTempLogger, github.com/Thrilleratplay/GoveeWatcher

## Device discovery signals
- BLE:
  - advertised name patterns: "GVH5075_XXXX", "GVH5074_XXXX", "Govee_H5075_XXXX"
  - service UUIDs: manufacturer-specific data in advertisement
  - address behavior: public

## Threat model + guardrails
- Scope: only owned devices, no safety-critical use cases.
- Passive sensor — no actuation risk.

## First experiments (do these first)
1) Run ./scripts/detect_devices.sh; attach log paths.
2) Fetch APK (apkeep) for com.govee.home.
3) Static: grep for UUIDs/endpoints + identify advertisement data format.
4) Dynamic: capture BLE advertisements with btmon or nRF Connect.

## Protocol hypotheses (to validate)
- Pairing/bonding steps: none — passive advertisement broadcast
- Session state machine: no connection needed, read advertisements
- Commands: N/A (read-only sensor)
- Payload encoding: manufacturer data in BLE advertisement, temp/humidity encoded in specific byte positions
- Timing constraints: advertisement interval ~2 seconds

## Control surface inventory (what the replacement app must support)
- Onboarding/pairing UX: BLE scan for GVH5075 name pattern
- Core controls (MVP): read temperature, read humidity
- Power / brightness / modes / uploads: N/A
- Error handling and recovery: handle missed advertisements
- Settings persistence: N/A

## Evidence checklist
- APK hashes + version code: TBD
- HCI snoop log: TBD

## Spec output (clean-room)
Write a derived spec in:
- docs/specs/govee-h5075-thermo.md

## References (URLs only)
- https://github.com/wcbonner/GoveeBTTempLogger
- https://github.com/Thrilleratplay/GoveeWatcher
- https://github.com/Bluetooth-Devices/govee-ble
- https://github.com/egold555/Govee-Reverse-Engineering
