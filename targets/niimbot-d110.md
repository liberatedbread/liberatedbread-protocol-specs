# Target: NIIMBOT D110/B21 Thermal Label Printer

## Target metadata
- target_id: niimbot-d110
- app package_id(s): com.niim.label
- device class: thermal label printer
- transport(s): BLE
- local-only viability: TBD — BLE protocol reportedly RE'd via NiimBlue, but could not verify

## Known facts (verified from RE sources)
- NIIMBOT D110/B21 thermal label printer
- Price: $15-30
- Popular cheap label printer with closed ecosystem
- Web Bluetooth client "NiimBlue" reportedly exists — TBD: could not access repo to verify (MultiMote/niimern returned 404)
- TBD — needs verification: All BLE protocol details unconfirmed
- TBD — needs verification: Advertised name patterns ("D110", "B21", "NIIMBOT" are speculative)
- TBD — needs verification: Service/characteristic UUIDs
- NOTE: This target has the weakest verification of all entries — needs hands-on RE or verified repo access

## Device discovery signals
- BLE:
  - advertised name patterns: TBD — "D110", "B21", "NIIMBOT" are speculative
  - service UUIDs: TBD
  - address behavior: TBD

## Threat model + guardrails
- Scope: only owned devices, no safety-critical use cases.
- Label printer only — no safety risk.

## First experiments (do these first)
1) Run ./scripts/detect_devices.sh; attach log paths.
2) Fetch APK (apkeep) for com.niim.label.
3) Static: grep for BLE UUIDs, print protocol framing.
4) Dynamic: record one "connect + print label" HCI snoop.

## Protocol hypotheses (to validate)
- Pairing/bonding steps: TBD
- Session state machine: TBD
- Commands: TBD
- Payload encoding: TBD
- Timing constraints: TBD

## Control surface inventory (what the replacement app must support)
- Onboarding/pairing UX: TBD
- Core controls (MVP): print label, set label size
- Power / brightness / modes / uploads: print density
- Error handling and recovery: reconnect
- Settings persistence: N/A

## Evidence checklist
- APK hashes + version code: TBD
- HCI snoop log: TBD

## Spec output (clean-room)
Write a derived spec in:
- docs/specs/niimbot-d110.md

## References (URLs only)
- https://github.com/MultiMote/niimern (NOTE: returned 404 during verification — URL may be incorrect)
