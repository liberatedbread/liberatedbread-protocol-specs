# Target: iTag BLE Bluetooth Tracker

## Target metadata
- target_id: itag-ble-tracker
- app package_id(s): com.nut.blehunter (and various iTag apps)
- device class: BLE key finder / anti-loss tracker
- transport(s): BLE
- local-only viability: high — simple BLE device, no cloud

## Known facts (public + observed)
- iTag BLE key finder / anti-loss tracker
- Price: $1-2 (one of the cheapest BLE devices available)
- CR2032 battery
- Has LED and buzzer
- Immediate Alert service: value 2 triggers 30 beeps + LED blinks
- Button press notifies on UUID 0xFFE1-0000-1000-8000-00805F9B34FB
- Supported by Gadgetbridge
- Known issue: some models drain batteries in hours if not bonded
- Existing RE: github.com/Freeyourgadget/Gadgetbridge, thejeshgn.com/2017/06/20/reverse-engineering-itag-bluetooth-low-energy-button/

## Device discovery signals
- BLE:
  - advertised name patterns: "iTAG", "iTag"
  - service UUIDs: 0x1802 (Immediate Alert), 0xFFE0 (button notify)
  - address behavior: public

## Threat model + guardrails
- Scope: only owned devices, no safety-critical use cases.
- Simple buzzer/LED — no safety risk.

## First experiments (do these first)
1) Run ./scripts/detect_devices.sh; attach log paths.
2) Fetch APK (apkeep) for common iTag companion apps.
3) Static: identify GATT services (Immediate Alert 0x1802, custom 0xFFE0).
4) Dynamic: trigger buzzer via Immediate Alert write, capture button press notification.

## Protocol hypotheses (to validate)
- Pairing/bonding steps: bonding recommended (prevents battery drain on some models)
- Session state machine: connect → bond → subscribe notifications → use
- Commands: alert level write to 0x1802 (0=off, 1=mild, 2=high), button press notification on 0xFFE1
- Payload encoding: single byte for alert level; single byte for button state
- Timing constraints: connection must be maintained for button notifications

## Control surface inventory (what the replacement app must support)
- Onboarding/pairing UX: BLE scan for "iTAG" name, bond
- Core controls (MVP): trigger buzzer, receive button press
- Power / brightness / modes / uploads: N/A
- Error handling and recovery: reconnect on disconnect, handle battery drain issue
- Settings persistence: bonding state

## Evidence checklist
- APK hashes + version code: TBD
- HCI snoop log: TBD

## Spec output (clean-room)
Write a derived spec in:
- docs/specs/itag-ble-tracker.md

## References (URLs only)
- https://github.com/Freeyourgadget/Gadgetbridge/wiki/iTag
- https://thejeshgn.com/2017/06/20/reverse-engineering-itag-bluetooth-low-energy-button/
- https://github.com/Edzelf/Itag
- https://github.com/s4ysolutions/itag
