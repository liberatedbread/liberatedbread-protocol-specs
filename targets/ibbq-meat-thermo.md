# Target: iBBQ / Inkbird BLE Meat Thermometer

## Target metadata
- target_id: ibbq-meat-thermo
- app package_id(s): com.inkbird.ibbtgo
- device class: BLE BBQ/meat thermometer (multi-probe, 2-6 probes)
- transport(s): BLE
- local-only viability: high — purely BLE, no cloud

## Known facts (public + observed)
- iBBQ/Inkbird multi-probe BBQ meat thermometer
- Price: $15-25
- Sold under many brands: Inkbird, Tenergy Solis, generic iBBQ
- Protocol documented in gist form: credential messages, settings data, alarm silencing, temperature notifications
- BLE notify for temperature readings
- Existing RE: github.com/gleeds/cloudbbq, gist.github.com/uucidl (iBBQ protocol gist)

## Device discovery signals
- BLE:
  - advertised name patterns: "iBBQ", "Inkbird", "solis"
  - service UUIDs: TBD from RE gists
  - address behavior: TBD

## Threat model + guardrails
- Scope: only owned devices, no safety-critical use cases.
- Temperature sensor — no actuation risk.

## First experiments (do these first)
1) Run ./scripts/detect_devices.sh; attach log paths.
2) Fetch APK (apkeep) for com.inkbird.ibbtgo.
3) Static: grep for GATT service/characteristic UUIDs.
4) Dynamic: record one "connect + read temperatures" HCI snoop.

## Protocol hypotheses (to validate)
- Pairing/bonding steps: credential exchange required after connection
- Session state machine: connect → send credentials → enable real-time → receive notifications
- Commands: pair/credential, enable real-time mode, set alarm thresholds, silence alarm
- Payload encoding: temperature as 16-bit integers in notifications, divide by 10 for °C
- Timing constraints: notifications at regular interval (~1-2 seconds)

## Control surface inventory (what the replacement app must support)
- Onboarding/pairing UX: BLE scan for iBBQ name
- Core controls (MVP): read temperature per probe, set alarms
- Power / brightness / modes / uploads: alarm thresholds, temperature units
- Error handling and recovery: handle probe disconnect, reconnect BLE
- Settings persistence: alarm thresholds

## Evidence checklist
- APK hashes + version code: TBD
- HCI snoop log: TBD

## Spec output (clean-room)
Write a derived spec in:
- docs/specs/ibbq-meat-thermo.md

## References (URLs only)
- https://github.com/gleeds/cloudbbq
- https://gist.github.com/uucidl/b9c60b6d36d8080d085a8e3310621d64
