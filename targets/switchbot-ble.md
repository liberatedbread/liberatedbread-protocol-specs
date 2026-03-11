# Target: SwitchBot BLE Smart Actuator/Sensor

## Target metadata
- target_id: switchbot-ble
- app package_id(s): com.theswitchbot.switchbot
- device class: BLE smart actuator/sensor (multiple device types)
- transport(s): BLE
- local-only viability: high — purely BLE, no cloud required; python-switchbot-ble library exists

## Known facts (public + observed)
- SwitchBot product family: Bot (button presser), Curtain (motor), Meter (temp/humidity), Contact Sensor
- Price: $15-40 depending on device
- All communicate via BLE locally
- Python API exists: python-switchbot-ble
- Home Assistant BLE integration available
- Bot physically presses buttons — unique mechanical actuator approach
- Curtain uses motor to open/close curtains on a rail
- Meter broadcasts temperature and humidity via BLE advertisements
- Contact Sensor detects door open/close state

## Device discovery signals
- BLE:
  - advertised name patterns: "WoHand" (Bot), "WoCurtain" (Curtain), "WoSensorTH" (Meter), "WoContact" (Contact)
  - service UUIDs: custom SwitchBot service UUID (from python-switchbot-ble)
  - address behavior: public

## Threat model + guardrails
- Scope: only owned devices, no safety-critical use cases.
- Bot presses physical buttons — ensure target button is non-critical.
- Curtain motor — low force, no pinch hazard documented.

## First experiments (do these first)
1) Run ./scripts/detect_devices.sh; attach log paths.
2) Fetch APK (apkeep) for com.theswitchbot.switchbot.
3) Static: grep for BLE service/characteristic UUIDs, command encoding.
4) Dynamic: record one "connect + press button" (Bot) or "read temp" (Meter) HCI snoop.

## Protocol hypotheses (to validate)
- Pairing/bonding steps: some devices may require password-based pairing
- Session state machine: connect → authenticate (if needed) → send command / read data → disconnect
- Commands: Bot (press, switch mode on/off), Curtain (open/close/position %), Meter (read temp/humidity)
- Payload encoding: binary commands via BLE write characteristic
- Timing constraints: Bot press duration configurable

## Control surface inventory (what the replacement app must support)
- Onboarding/pairing UX: BLE scan for WoHand/WoCurtain/WoSensorTH names
- Core controls (MVP): Bot press, Curtain open/close, Meter read
- Power / brightness / modes / uploads: Bot switch mode (hold vs press), Curtain position percentage
- Error handling and recovery: reconnect on BLE disconnect
- Settings persistence: device stores mode settings internally

## Evidence checklist
- APK hashes + version code: TBD
- HCI snoop log: TBD

## Spec output (clean-room)
Write a derived spec in:
- docs/specs/switchbot-ble.md
- include message formats, UUIDs, examples, and tests.

## References (URLs only)
- https://github.com/OpenWonderLabs/SwitchBotAPI-BLE
- https://github.com/Danielhiversen/pySwitchbot
