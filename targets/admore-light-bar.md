# AdMore Light Bar Pro — target spec

## Target metadata
- target_id: admore-light-bar
- app package_id(s): com.admorelighting.lightbar
- device class: motorcycle light bar (brake/tail/turn signal)
- transport(s): BLE
- local-only viability: high — all settings appear stored on-device; no cloud account or internet required; BLE-only communication between app and light bar

## Known facts (public + observed)
- Vendor describes the Light Bar Pro as a programmable, multi-functional motorcycle lighting system providing tail light, brake light, progressive amber turn signals, hazard flasher, and license plate illumination.
- The PRO model (SKU: LED8020-BT / LED8020-BT-SMK) adds Bluetooth connectivity, an accelerometer for deceleration-triggered braking, three extra center amber LEDs, and a white license plate LED.
- Hardware: 81 bi-color (red/amber) Cree LEDs + 3 center amber strobe LEDs + 3 white license plate LEDs in a weatherproof aluminum housing (7.9 x 1.3 x 0.7 in / 20 x 3.2 x 1.8 cm).
- Five-wire installation: brake, taillight, left signal, right signal, ground. 12V compatible. CANBUS compatible.
- The free AdMore Connect app (Android and iOS) controls the light bar via Bluetooth.
- The app also supports firmware updates over Bluetooth.
- Older non-Pro models used MicroUSB + desktop configurator software; the Pro model replaced this with BLE + mobile app.
- Manufactured in Calgary, Alberta, Canada by AdMore Lighting Inc.
- MSRP: $219 USD.

## Device discovery signals (hypotheses)
- BLE:
  - advertised name patterns: unknown — hypothesize "AdMore", "LBP", "LED8020", or model-specific prefix (discover via scan)
  - service UUIDs: unknown (discover via GATT enumeration and APK static analysis)
  - address behavior: unknown (likely public for consumer pairing simplicity)
- Wi-Fi: not applicable
- USB: older models used MicroUSB for configuration (not in scope for BLE reverse engineering)

## Threat model + guardrails
- Scope: only owned devices.
- This is a visibility/lighting device, not a vehicle control system. It does not control throttle, braking force, or steering.
- Risk: incorrect light behavior (e.g., brake light stuck off, or strobing erroneously) could confuse other road users. Document safe default values from manufacturer.
- Non-goals: do not modify accelerometer thresholds beyond manufacturer-supported ranges. Do not disable safety-critical brake light activation from the physical brake switch input.
- Firmware updates: document the update mechanism but do not distribute or modify firmware images.

## First experiments (do these first)
1) Run ./scripts/detect_devices.sh with the Light Bar Pro powered on and nearby; record BLE advertising name and any service UUIDs.
2) Fetch APK via `apkeep -a com.admorelighting.lightbar`; record APK hash and version code.
3) Static APK analysis:
   - Search for UUID literals (16-bit `0x????` and 128-bit `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`)
   - Search for strings: "bluetooth", "gatt", "characteristic", "write", "notify", "admore", "lightbar", "brightness", "flash", "accelerometer"
   - Identify BLE library used (Android BluetoothGatt, RxAndroidBle, Nordic, etc.)
   - Look for command byte constants or enum classes
4) Dynamic: enable Android HCI snoop logging, then:
   - Open the AdMore Connect app
   - Connect to the Light Bar Pro
   - Change one setting (e.g., brake brightness)
   - Disconnect
   - Pull btsnoop_hci.log and parse with tools/pcap_parser.py
5) Repeat step 4 for each of the 7 configurable settings to map command IDs.

## Protocol hypotheses (to validate)
- Pairing/bonding: likely no bonding required (consumer BLE devices rarely bond); possibly just-works pairing or no pairing at all
- Session state machine: connect -> discover services -> write commands -> disconnect (no persistent session state)
- Commands: hypothesize a single custom GATT service with a write characteristic for settings commands
  - Each command likely a short byte sequence: [command_id, value] or [header, command_id, length, value, checksum]
  - Possible notify characteristic for acknowledgments or current-state readback
- Payload encoding: likely raw uint8 values for brightness (0-255 or 0-100), flash count (integer), flash speed (integer or enum), accelerometer sensitivity (enum or 0-100)
- Firmware update: possibly a separate characteristic or service (DFU); may use Nordic DFU or a vendor-specific OTA protocol
- Timing constraints: probably none beyond standard BLE connection intervals
- Settings persistence: settings likely stored in on-device flash; survive power cycles

## Control surface inventory (replacement app MVP)
- **Onboarding**: scan for BLE device, connect (no account needed)
- **Core controls (MVP)**:
  - Set brake light brightness
  - Set brake light flash count (number of flashes before solid)
  - Set brake light flash speed
  - Toggle license plate LED (on/off)
  - Set accelerometer sensitivity
  - Set running light brightness
  - Set taillight brightness
- **Read current settings**: read back all 7 settings from device
- **Firmware info**: read firmware version (for display, not for update in MVP)
- **Error handling**: connection loss recovery, out-of-range notification
- **Settings persistence**: settings persist on-device; app just sends new values

## Evidence checklist
- [ ] APK hash + version code for com.admorelighting.lightbar
- [ ] HCI snoop log: connect + single setting change
- [ ] HCI snoop logs: one per configurable setting (7 total)
- [ ] GATT service/characteristic UUID table
- [ ] Command byte map (command_id -> setting)
- [ ] Value range validation for each setting
- [ ] Firmware version readback format

## Spec output (clean-room)
Write a derived spec in:
- docs/devices/admore-light-bar.md (human-readable protocol documentation)
- device-specs/admore-light-bar.yaml (machine-readable device spec)
- Include message formats, UUIDs, command tables, value ranges, and examples.

## References (URLs only)
- https://admorelighting.com/product/admore-light-bar-pro/
- https://play.google.com/store/apps/details?id=com.admorelighting.lightbar
- https://admorelighting.com/admore-connect-app-help/
- https://ridermagazine.com/2024/12/17/admore-light-bar-pro-motorcycle-lighting-system-review/
- https://motorcyclemojo.com/2023/07/admore-light-bar-pro-revisited/
