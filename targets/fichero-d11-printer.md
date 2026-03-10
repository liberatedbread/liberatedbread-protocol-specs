# Target: Fichero / AiYin D11 Thermal Label Printer

## Target metadata
- target_id: fichero-d11-printer
- app package_id(s): com.lj.fichero
- device class: thermal label printer
- transport(s): BLE
- local-only viability: high — purely BLE, no cloud

## Known facts (public + observed)
- Fichero/AiYin D11 thermal label printer
- Price: $15-20
- Sold at discount stores under many brand names
- All use the same LuckPrinter SDK internally
- Protocol reverse-engineered from decompiled APK
- Python CLI and Web GUI available
- APK requests 26 permissions (suspicious for a label printer)
- Existing RE: github.com/0xMH/fichero-printer

## Device discovery signals
- BLE:
  - advertised name patterns: "D11", "D110", "AiYin"
  - service UUIDs: TBD from APK decompilation
  - address behavior: TBD

## Threat model + guardrails
- Scope: only owned devices, no safety-critical use cases.
- Label printer only — no safety risk.

## First experiments (do these first)
1) Run ./scripts/detect_devices.sh; attach log paths.
2) Fetch APK (apkeep) for com.lj.fichero.
3) Static: identify LuckPrinter SDK BLE protocol layer.
4) Dynamic: record one "connect + print label" HCI snoop.

## Protocol hypotheses (to validate)
- Pairing/bonding steps: TBD
- Session state machine: connect → configure label size → send image → disconnect
- Commands: set label size, print image, feed
- Payload encoding: LuckPrinter SDK framing, rasterized bitmap
- Timing constraints: TBD

## Control surface inventory (what the replacement app must support)
- Onboarding/pairing UX: BLE scan for D11/D110 name
- Core controls (MVP): print label image, set label size
- Power / brightness / modes / uploads: print darkness
- Error handling and recovery: reconnect on disconnect
- Settings persistence: N/A

## Evidence checklist
- APK hashes + version code: TBD
- HCI snoop log: TBD

## Spec output (clean-room)
Write a derived spec in:
- docs/specs/fichero-d11-printer.md

## References (URLs only)
- https://github.com/0xMH/fichero-printer
