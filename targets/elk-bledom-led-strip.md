# Target: ELK-BLEDOM Generic BLE LED Strip Controller

## Target metadata
- target_id: elk-bledom-led-strip
- app package_id(s): com.Zhiling.DuoCoStripLight, com.lotuslantern.ledble, com.auraLed
- device class: BLE LED strip controller
- transport(s): BLE
- local-only viability: high — purely BLE, no cloud dependency

## Known facts (public + observed)
- Sold under dozens of brand names: JACKYLED, auraLED, HueLite, MELK, LEDBLE, ELK-BULB, ELK-LAMPL
- Extremely cheap ($2-15 from AliExpress/Amazon)
- Uses simple 9-byte BLE packets
- BLE service UUID: 0xFFF0
- Write characteristic UUID: 0xFFF3
- Read characteristic UUID: 0xFFF4
- Packet format: [0x7E, mode, r/g/b, speed, 0x00, 0xEF]
- Multiple open-source RE projects exist but no unified protocol spec
- One researcher bricked a unit by probing undocumented modes
- Existing RE: github.com/FergusInLondon/ELK-BLEDOM, github.com/dave-code-ruiz/elkbledom, github.com/arduino12/ble_rgb_led_strip_controller

## Device discovery signals
- BLE:
  - advertised name patterns: "ELK-BLEDOM", "MELK", "LEDBLE", "ELK-BULB", "ELK-LAMPL"
  - service UUIDs: 0000FFF0-0000-1000-8000-00805F9B34FB
  - address behavior: public

## Threat model + guardrails
- Scope: only owned devices, no safety-critical use cases.
- LED strip only — no safety risk beyond light output.

## First experiments (do these first)
1) Run ./scripts/detect_devices.sh; attach log paths.
2) Fetch APK (apkeep) OR pull from device (adb).
3) Static: grep for UUIDs/endpoints + identify transport stack.
4) Dynamic: record one "connect + set color" HCI/PCAP.

## Protocol hypotheses (to validate)
- Pairing/bonding steps: no bonding required, open BLE write
- Session state machine: connect → write characteristic → disconnect
- Commands: color set (RGB), brightness, mode/effect selection, on/off
- Payload encoding: fixed 9-byte packets, see existing RE repos
- Timing constraints: unknown; likely none

## Control surface inventory (what the replacement app must support)
- Onboarding/pairing UX: BLE scan for ELK-BLEDOM name
- Core controls (MVP): on/off, color (RGB), brightness
- Power / brightness / modes / uploads: multiple effect modes (strobe, fade, etc.)
- Error handling and recovery: reconnect on disconnect
- Settings persistence: device may not persist state across power cycles

## Evidence checklist
- APK hashes + version code: TBD
- HCI snoop log: TBD
- Screenshots (optional): N/A

## Spec output (clean-room)
Write a derived spec in:
- docs/specs/elk-bledom-led-strip.md
- include message formats, UUIDs, examples, and tests.

## References (URLs only)
- https://github.com/FergusInLondon/ELK-BLEDOM
- https://github.com/dave-code-ruiz/elkbledom
- https://github.com/arduino12/ble_rgb_led_strip_controller
- https://github.com/kquinsland/JACKYLED-BLE-RGB-LED-Strip-controller
