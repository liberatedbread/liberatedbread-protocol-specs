# Target: Xiaomi Mi Flora / Flower Care Plant Sensor

## Target metadata
- target_id: xiaomi-miflora
- app package_id(s): com.huahuacaocao.flowercare
- device class: plant/soil sensor (moisture, temperature, light, soil fertility)
- transport(s): BLE
- local-only viability: high — purely BLE, coin cell powered, ~1 year battery life

## Known facts (public + observed)
- Xiaomi Mi Flora / Flower Care plant sensor
- Price: $12-17
- Measures: soil moisture, temperature, light intensity, soil fertility (conductivity)
- Coin cell (CR2032) powered, lasts ~1 year
- Protocol known: write 0xA01F to handle 0x33 to switch to real-time mode, then read from handle 0x35
- Firmware version readable from handle 0x38
- Widely available on AliExpress/Amazon
- Existing RE: github.com/basnijholt/miflora, github.com/sidddy/flora, github.com/vrachieru/xiaomi-flower-care-api

## Device discovery signals
- BLE:
  - advertised name patterns: "Flower care", "Flower mate"
  - service UUIDs: TBD — standard GATT with custom service
  - address behavior: public

## Threat model + guardrails
- Scope: only owned devices, no safety-critical use cases.
- Passive sensor — no actuation risk.

## First experiments (do these first)
1) Run ./scripts/detect_devices.sh; attach log paths.
2) Fetch APK (apkeep) for com.huahuacaocao.flowercare.
3) Static: grep for GATT handles/UUIDs + data format.
4) Dynamic: capture BLE read of sensor data with btmon.

## Protocol hypotheses (to validate)
- Pairing/bonding steps: none for reading; may need bonding for firmware update
- Session state machine: connect → write mode switch → read data → disconnect
- Commands: enable real-time mode (write 0xA01F to handle 0x33), read sensor data (handle 0x35), read firmware/battery (handle 0x38)
- Payload encoding: binary, little-endian integers for temp (°C × 10), moisture (%), light (lux), fertility (µS/cm)
- Timing constraints: real-time mode may timeout

## Control surface inventory (what the replacement app must support)
- Onboarding/pairing UX: BLE scan for "Flower care" name
- Core controls (MVP): read all 4 sensor values, read battery level
- Power / brightness / modes / uploads: N/A
- Error handling and recovery: handle connection timeouts, retry reads
- Settings persistence: N/A (read-only sensor)

## Evidence checklist
- APK hashes + version code: TBD
- HCI snoop log: TBD

## Spec output (clean-room)
Write a derived spec in:
- docs/specs/xiaomi-miflora.md

## References (URLs only)
- https://github.com/basnijholt/miflora
- https://github.com/sidddy/flora
- https://github.com/vrachieru/xiaomi-flower-care-api
