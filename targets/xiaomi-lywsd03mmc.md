# Target: Xiaomi Mijia LYWSD03MMC BLE Thermometer/Hygrometer

## Target metadata
- target_id: xiaomi-lywsd03mmc
- app package_id(s): com.xiaomi.smarthome
- device class: BLE thermometer/hygrometer
- transport(s): BLE
- local-only viability: high — custom firmware enables direct BLE advertisement of data; OTA flashable from browser

## Known facts (public + observed)
- Xiaomi Mijia LYWSD03MMC temperature and humidity sensor
- Price: $4-6 (one of the cheapest BLE sensors available)
- Uses Telink TLSR8251 SoC
- Custom firmware (ATC_MiThermometer by pvvx) available, OTA flashable from a web browser
- Can be converted to Zigbee device via z03mmc firmware
- E-ink display shows temperature and humidity
- CR2032 battery, lasts 6-12 months
- Existing RE: github.com/pvvx/ATC_MiThermometer, github.com/devbis/z03mmc

## Device discovery signals
- BLE:
  - advertised name patterns: "LYWSD03MMC", "ATC_XXXXXX" (custom firmware)
  - service UUIDs: standard + Xiaomi MiBeacon (UUID 0xFE95)
  - address behavior: public (custom firmware), random (stock firmware)

## Threat model + guardrails
- Scope: only owned devices, no safety-critical use cases.
- Passive sensor — no actuation risk.
- Custom firmware flashing is reversible.

## First experiments (do these first)
1) Run ./scripts/detect_devices.sh; attach log paths.
2) Fetch APK (apkeep) for com.xiaomi.smarthome.
3) Static: grep for MiBeacon protocol UUIDs (0xFE95).
4) Dynamic: capture BLE advertisements with stock and custom firmware.

## Protocol hypotheses (to validate)
- Pairing/bonding steps: stock firmware may require Xiaomi cloud pairing; custom firmware: none
- Session state machine: passive advertisement broadcast (no connection needed for custom firmware)
- Commands: N/A (read-only sensor)
- Payload encoding: stock: MiBeacon encrypted advertisement; custom: plain advertisement with temp/humidity/battery
- Timing constraints: advertisement interval configurable (2-10 seconds)

## Control surface inventory (what the replacement app must support)
- Onboarding/pairing UX: BLE scan for LYWSD03MMC name
- Core controls (MVP): read temperature, read humidity, read battery
- Power / brightness / modes / uploads: N/A
- Error handling and recovery: handle missed advertisements
- Settings persistence: N/A

## Evidence checklist
- APK hashes + version code: TBD
- HCI snoop log: TBD

## Spec output (clean-room)
Write a derived spec in:
- docs/specs/xiaomi-lywsd03mmc.md

## References (URLs only)
- https://github.com/pvvx/ATC_MiThermometer
- https://github.com/devbis/z03mmc
- https://home-is-where-you-hang-your-hack.github.io/ble_monitor/MiBeacon_protocol
