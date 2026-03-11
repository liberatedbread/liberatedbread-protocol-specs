# Target: BLE Pulse Oximeter (BerryMed / SP001)

## Target metadata
- target_id: ble-pulse-oximeter
- app package_id(s): com.viatom.oxyfit (and various generic oximeter apps)
- device class: BLE pulse oximeter
- transport(s): BLE
- local-only viability: high — purely BLE, no cloud required

## Known facts (public + observed)
- BerryMed / SP001 / generic BLE fingertip pulse oximeters
- Price: $15-30
- Measures SpO2 (blood oxygen saturation) and pulse rate
- Uses BLE GATT with proprietary framing (not standard BLE health profiles)
- BCI protocol documented for some models
- Many Amazon/AliExpress units share similar BLE chipsets and protocols
- Partially RE'd: github.com/jcomas/PulseOximeterSP001

## Device discovery signals
- BLE:
  - advertised name patterns: "BerryMed", "SP001", "OxySmart", "Pulse Oximeter"
  - service UUIDs: custom service (not standard 0x1822 Pulse Oximeter profile in most cheap units)
  - address behavior: public

## Threat model + guardrails
- Scope: only owned devices, no safety-critical use cases.
- Medical device caveat: readings are indicative only, not for clinical diagnosis.
- Do not rely on RE'd protocol for medical decisions.

## First experiments (do these first)
1) Run ./scripts/detect_devices.sh; attach log paths.
2) Fetch APK (apkeep) for com.viatom.oxyfit or similar companion app.
3) Static: grep for GATT service/characteristic UUIDs, data parsing format.
4) Dynamic: record one "connect + read SpO2/pulse" HCI snoop.

## Protocol hypotheses (to validate)
- Pairing/bonding steps: none expected (most cheap oximeters don't bond)
- Session state machine: connect → subscribe to notifications → receive continuous readings → disconnect
- Commands: N/A (read-only — device streams data when finger inserted)
- Payload encoding: proprietary binary frames with SpO2 (%), pulse rate (bpm), plethysmograph waveform
- Timing constraints: notifications at ~50-100 Hz for waveform, ~1 Hz for SpO2/pulse values

## Control surface inventory (what the replacement app must support)
- Onboarding/pairing UX: BLE scan for oximeter name patterns
- Core controls (MVP): read SpO2 percentage, read pulse rate
- Power / brightness / modes / uploads: plethysmograph waveform display (optional)
- Error handling and recovery: detect finger removal (invalid readings), reconnect
- Settings persistence: N/A

## Evidence checklist
- APK hashes + version code: TBD
- HCI snoop log: TBD

## Spec output (clean-room)
Write a derived spec in:
- docs/specs/ble-pulse-oximeter.md

## References (URLs only)
- https://github.com/jcomas/PulseOximeterSP001
