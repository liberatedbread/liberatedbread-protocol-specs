# Target: Cat Printer (GB01/GB02/GT01)

## Target metadata
- target_id: cat-printer
- app package_id(s): com.iprint.paper (and various)
- device class: mini thermal printer
- transport(s): BLE
- local-only viability: high — purely BLE, no cloud

## Known facts (public + observed)
- Cat-shaped mini thermal receipt/sticker printer
- Price: $15-20
- Multiple hardware variants: GB01, GB02, GT01 with documented differences
- BLE protocol fully reverse-engineered
- Cross-platform Python tool available
- Popular novelty item widely available on AliExpress/Amazon
- Existing RE: github.com/NaitLee/Cat-Printer, werwolv.net/blog/cat_printer

## Device discovery signals
- BLE:
  - advertised name patterns: "GB01", "GB02", "GT01", "MX*"
  - service UUIDs: TBD from RE projects
  - address behavior: public

## Threat model + guardrails
- Scope: only owned devices, no safety-critical use cases.
- Thermal printer only — no safety risk.

## First experiments (do these first)
1) Run ./scripts/detect_devices.sh; attach log paths.
2) Fetch APK (apkeep) for com.iprint.paper.
3) Static: grep for BLE service/characteristic UUIDs, print command format.
4) Dynamic: record one "connect + print image" HCI snoop.

## Protocol hypotheses (to validate)
- Pairing/bonding steps: no bonding required
- Session state machine: connect → configure → send image data → disconnect
- Commands: print image (rasterized bitmap), feed paper, set energy (darkness)
- Payload encoding: 1-bit bitmap rasterized row-by-row, command framing varies by model
- Timing constraints: may need flow control between rows

## Control surface inventory (what the replacement app must support)
- Onboarding/pairing UX: BLE scan for GB01/GB02/GT01 names
- Core controls (MVP): print image, feed paper
- Power / brightness / modes / uploads: print darkness/energy setting
- Error handling and recovery: paper-out detection, reconnect
- Settings persistence: N/A

## Evidence checklist
- APK hashes + version code: TBD
- HCI snoop log: TBD

## Spec output (clean-room)
Write a derived spec in:
- docs/specs/cat-printer.md

## References (URLs only)
- https://github.com/NaitLee/Cat-Printer
- https://werwolv.net/blog/cat_printer
