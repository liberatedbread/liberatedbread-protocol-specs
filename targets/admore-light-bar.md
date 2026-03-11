# AdMore Light Bar Pro — target spec

## Target metadata
- target_id: admore-light-bar
- app package_id(s): com.admorelighting.lightbar
- app version analyzed: 2.1.0 (version_code 44)
- app framework: Flutter/Dart with FlutterBluePlus BLE plugin
- device class: motorcycle light bar (brake/tail/turn signal)
- transport(s): BLE (Nordic UART Service)
- local-only viability: high — all settings stored on-device via protobuf-over-UART; Firebase backend used only for firmware distribution and user accounts, not required for device control

## Known facts (public + observed)
- Vendor describes the Light Bar Pro as a programmable, multi-functional motorcycle lighting system providing tail light, brake light, progressive amber turn signals, hazard flasher, and license plate illumination.
- The PRO model (SKU: LED8020-BT / LED8020-BT-SMK) adds Bluetooth connectivity, an accelerometer for deceleration-triggered braking, three extra center amber LEDs, and a white license plate LED.
- Hardware: 81 bi-color (red/amber) Cree LEDs + 3 center amber strobe LEDs + 3 white license plate LEDs in a weatherproof aluminum housing (7.9 x 1.3 x 0.7 in / 20 x 3.2 x 1.8 cm).
- Five-wire installation: brake, taillight, left signal, right signal, ground. 12V compatible. CANBUS compatible.
- The free AdMore Connect app (Android and iOS) controls the light bar via Bluetooth.
- The app also supports firmware updates over Bluetooth using Nordic DFU.
- Older non-Pro models used MicroUSB + desktop configurator software; the Pro model replaced this with BLE + mobile app.
- Manufactured in Calgary, Alberta, Canada by AdMore Lighting Inc.
- MSRP: $219 USD.
- The app also supports "AdMore Armband" accessories (left/right) as additional devices.

## Device discovery signals (confirmed from APK static analysis)
- BLE:
  - advertised name patterns:
    - `"AdMore Light Bar"` — normal operation
    - `"AdMore Light Bar DFU"` — firmware update mode
    - `"AdMore Armband"` / `"AdMore Armband Left"` / `"AdMore Armband Right"` — armband accessories
  - service UUIDs (Nordic UART Service variants):
    - Light Bar: `6E400001-B5A3-F393-E0A9-E50E24DCCA9E` (NUS service)
    - Armband:   `6E400001-B5A3-F393-E0A9-E50E24DCCAAE`
    - Unknown:   `6E400001-B5A3-F393-E0A9-E50E24DCCABE`
    - Unknown:   `6E400001-B5A3-F393-E0A9-E50E24DCCACE`
  - Each NUS service has three characteristics (standard NUS layout):
    - `6E40000x-...CA9E` where x = 1 (service), 2 (RX/write), 3 (TX/notify)
  - CCCD descriptor: `00002902-0000-1000-8000-00805f9b34fb` (standard)
  - address behavior: unknown (confirm via scan)
- Wi-Fi: not applicable
- USB: older models used MicroUSB for configuration (not in scope)

## Threat model + guardrails
- Scope: only owned devices.
- This is a visibility/lighting device, not a vehicle control system. It does not control throttle, braking force, or steering.
- Risk: incorrect light behavior (e.g., brake light stuck off, or strobing erroneously) could confuse other road users. Document safe default values from manufacturer.
- Non-goals: do not modify accelerometer thresholds beyond manufacturer-supported ranges (sensitivity 1–50 per config, corresponding to raw values 4000–80). Do not disable safety-critical brake light activation from the physical brake switch input.
- Firmware updates: document the DFU mechanism but do not distribute or modify firmware images. DFU zip served from Firebase (`admore-light-bar-with-ble.firebaseio.com`).

## Protocol architecture (confirmed from APK static analysis)

### Transport layer
- BLE Nordic UART Service (NUS) — data sent as byte stream over UART emulation
- RX characteristic (app writes to device): `6E400002-B5A3-F393-E0A9-E50E24DCCA9E`
- TX characteristic (device notifies app): `6E400003-B5A3-F393-E0A9-E50E24DCCA9E`

### Message layer
- **Protocol Buffers** (protobuf) — messages serialized using `package:protobuf`
- Protobuf schema defined in `package:messaging_common/build_dart/lightbar.pb.dart` and `lightbar.pbenum.dart`
- Internal message bus uses **KMsg** (`package:messaging_common/kmessaging.dart`) with source/destination routing

### Message routing
- Sources (SRC): `SRC_CMD_APP`, `SRC_CMD_HOST_APP`, `SRC_CMD_HOST_DIAG`, `SRC_CMD_UART_DIAG`, `SRC_CMD_KMSG`, `SRC_CMD_BKND_APP`, `SRC_CMD_BKND_DIAG`, `SRC_CMD_APP_ARML`, `SRC_CMD_APP_ARMR`
- Destinations (DST): `DST_CMD_APP`, `DST_CMD_BLE_ENGINE`, `DST_CMD_KMSG`, `DST_CMD_APP_DIAG`, `DST_CMD_APP_ARML`, `DST_CMD_APP_ARMR`, `DST_CMD_APP_DIAG_ARML`, `DST_CMD_APP_DIAG_ARMR`
- Events: `SRC_EVT_*` / `DST_EVT_*` for async notifications

### Protobuf command types (from libapp.so symbol analysis)

The app uses these protobuf message types for communication:

| Protobuf Type | Purpose |
|---|---|
| `t_cmdAppQuery` / `t_cmdAppQuery_Reply` | Query device state (request/response) |
| `t_cmdAppNop` | No-op / keepalive |
| `t_cmdAppWriteString` | Write string data (`APP_WRITE_STRING`) |
| `t_cmdAppInjectEvent` | Inject event (`APP_INJECT_EVENT`) |
| `t_cmdAppSetDstEvt` / `t_cmdAppSetDstEvtDiag` | Set event routing destinations |
| `t_cmdDssSetData` | Set a device setting (setting ID + value) |
| `t_cmdDssGetData` / `t_cmdDssGetData_Reply` | Get a device setting (request/response) |
| `t_cmdDssOperation` | System operations (commit, factory reset, reload, etc.) |
| `t_cmdLosSetLight` | Direct light output control (used by `sendLightOutput()`, `sendBarTest()`) |
| `t_evtAppEvent` | Generic app event (device → app) |
| `t_evtDiagMmsDecelData` | Diagnostic deceleration data (device → app) |

The DSS (Data Storage Subsystem) is the main mechanism for reading/writing settings:
- **`DSS_SET_DATA`**: Write a setting — takes a setting ID string (e.g., `LOS_TAIL_LIGHT_BRIGHTNESS`) and integer value
- **`DSS_GET_DATA`**: Read a setting — takes a setting ID, reply contains current value
- **`DSS_OPERATION`**: System-level operations — `DATA_COMMIT`, `DATA_FACTORY_DEFAULT`, `DATA_RELOAD`, `DATA_MAINTAIN`, `DATA_ABANDON_RESTORE`

### App commands (sent via protobuf over NUS)

#### Settings commands (LOS = Light Output Setting)
| Command ID | Label | Values |
|---|---|---|
| `LOS_TAIL_LIGHT_BRIGHTNESS` | Tail Light Brightness | OFF=0, 1=200, 2=400, 3=1000, 4=1500, 5=2000 |
| `LOS_BRAKE_LIGHT_BRIGHTNESS` | Brake Light Brightness | 6=5000, 7=5500, 8=6000, 9=6500, 10=7000 |
| `LOS_BRAKE_FLASH_COUNT` | Brake Flash Count | OFF=0, 2, 4, 6, 8, 10 |
| `LOS_BRAKE_FLASH_TIME_MS` | Brake Flash Speed | 1=50ms, 2=40ms, 3=30ms, 4=20ms, 5=10ms |
| `LOS_BRAKE_STROBE_DURATION_MS` | Amber Strobe (Brake) | OFF=0, 5s=5000, 10s=10000, 15s=15000, 20s=20000, ON=-1 |
| `LOS_PLATE_LIGHT_BRIGHTNESS` | Plate Light | ON=8000, OFF=0 |
| `LOS_TURN_LIGHT_SEQUENTIAL_STEP_MS` | Sequential Turn Signal | ON=30, OFF=0 |
| `LOS_TURN_LIGHT_BRIGHTNESS` | Turn Light Brightness | (not in lb_config.xml; internal/runtime use only) |
| `LOS_SET_LIGHT` | Set Light (direct control) | (used by `sendLightOutput()` and `sendBarTest()` for direct LED control) |
| `LOS_DEALER_DEMO_MODE` | Demo Mode | ON=1, OFF=0 (version ^1+) |

#### Accelerometer / motion commands (MMS = Motion Management System)
| Command ID | Label | Values |
|---|---|---|
| `MMS_DECEL_TOGGLE` | Accelerometer Sensor | ON=1, OFF=0 (native preference, controls visibility of sub-settings) |
| `MMS_DECEL_THRESHOLD` | Deceleration Sensitivity | OFF=0, 1=4000, 2=3920, ..., 50=80 (step=-80, 50 levels) |
| `MMS_DECEL_OFF_DELAY_MS` | Deceleration Light Delay | 1s=1000, 1.5s=1500, 2s=2000, 2.5s=2500, 3s=3000 |
| `MMS_DECEL_COUNT` | Deceleration Duration | 5–40 (integer, higher=longer detection required) |
| `MMS_ENABLE_BRAKE_WHITE_STROBE` | Amber Strobe on Deceleration | ON=1, OFF=0 |
| `MMS_ENABLE_TIPOVER` | Tip Over Flash | ON=1, OFF=0 |
| `MMS_QUERY_INFO` | Query Device Info | (read-only query) |
| `MMS_DECEL_ON` / `MMS_DECEL_OFF` | Decel Events | (internal state) |
| `MMS_MOTION_ON` / `MMS_MOTION_OFF` / `MMS_MOTION_STOP` | Motion Events | (internal state) |
| `MMS_TILT_DOWN` / `MMS_TILT_UPD` | Tilt Events | (internal state) |

#### Input / wiring commands (LIS = Light Input Setting)
| Command ID | Label | Values |
|---|---|---|
| `LIS_ENABLE_BRAKE_INVERT` | Input Brake Invert | ON=1, OFF=0 (version ^1+) |
| `LIS_ENABLE_TWO_WIRE` | Two Lamp Mode | ON=1, OFF=0 (version ^1+) |
| `LIS_BRAKE_ON` / `LIS_BRAKE_OFF` | Brake Input Events | (state signals) |
| `LIS_LEFT_ON` / `LIS_LEFT_OFF` | Left Turn Events | (state signals) |
| `LIS_RIGHT_ON` / `LIS_RIGHT_OFF` | Right Turn Events | (state signals) |
| `LIS_PWM_ON` / `LIS_PWM_OFF` | PWM Events | (state signals) |

#### Override / special mode commands
| Command ID | Description |
|---|---|
| `OVERRIDE_HAZARD` | Hazard flasher mode |
| `OVERRIDE_PROCESSION` | Procession mode (amber wig-wag) |
| `OVERRIDE_DEMO` | Demo mode override |
| `OVERRIDE_TILTOVER` | Tilt-over override |

#### System commands
| Command ID | Description |
|---|---|
| `DATA_FACTORY_DEFAULT` | Reset to factory defaults |
| `DATA_COMMIT` | Commit/save settings |
| `DATA_RELOAD` | Reload settings from storage |
| `DATA_MAINTAIN` | Maintenance mode |
| `DATA_ABANDON_RESTORE` | Abandon restore operation |
| `SOFT_RESET` | Soft reset device |
| `ENTER_DFU` | Enter firmware update mode |
| `ENTER_SLEEP` | Enter sleep mode |
| `RESET_LIGHTS` | Reset all lights |

#### Test commands
| Command ID | Description |
|---|---|
| `TEST_BRAKE_LIGHT_LEFT` | Test left brake light |
| `TEST_BRAKE_LIGHT_RIGHT` | Test right brake light |
| `TEST_BRAKE_LIGHT_CENTER` | Test center brake light |
| `TEST_BRAKE_WHITE` | Test white brake light |
| `TEST_LEFT_TURN` | Test left turn signal |
| `TEST_RIGHT_TURN` | Test right turn signal |
| `TEST_PLATE_LIGHT` | Test plate light |
| `TEST_BLUE_LIGHT` | Test blue light |
| `TEST_RESET_LIGHTS` | Reset test lights |

#### App / system query commands
| Command ID | Description |
|---|---|
| `APP_QUERY` | Query device state |
| `APP_VERSIONS` | Query app versions |
| `APP_NOP` | No-op / keepalive |
| `HW_VERSIONS` | Query hardware versions |
| `SYS_VERSIONS` | Query system/firmware versions |

### Version reporting
The device reports multiple version strings:
- Firmware Version
- Bootloader Version
- System Version
- Database Version

### Firmware update (DFU)
- Uses Nordic DFU library (`package:nordic_dfu`)
- Flutter plugin: `dev.steenbakker.nordic_dfu`
- DFU zip files served from Firebase Storage (`admore-light-bar-with-ble.firebaseio.com`, path: `lightbar-firmware/`)
- Device enters DFU mode via `ENTER_DFU` command, advertises as `"AdMore Light Bar DFU"`
- Supports both legacy and secure DFU modes

## Control surface inventory (replacement app MVP)
- **Onboarding**: scan for BLE devices with name `"AdMore Light Bar"`, connect via NUS service UUID `6E400001-B5A3-F393-E0A9-E50E24DCCA9E`
- **Core controls (MVP)** — 18 configurable settings from `lb_config.xml`:
  - Tail light brightness (6 levels: OFF, 200, 400, 1000, 1500, 2000)
  - Brake light brightness (5 levels: 5000–7000)
  - Brake flash count (6 levels: OFF, 2, 4, 6, 8, 10)
  - Brake flash speed (5 levels: 50ms–10ms)
  - Amber strobe duration (6 levels: OFF, 5s–20s, always-on)
  - Amber strobe on deceleration (toggle)
  - Tip-over flash (toggle)
  - Sequential turn signal (toggle: 30ms step or 0)
  - Plate light (toggle: 8000 or 0)
  - Accelerometer sensor (toggle, gates sub-settings)
  - Deceleration sensitivity (51 levels: OFF + 1–50, raw 4000–80)
  - Deceleration light delay (5 levels: 1s–3s)
  - Deceleration duration (36 levels: 5–40)
  - Input brake invert (toggle, version ^1+)
  - Two lamp mode (toggle, version ^1+)
  - Demo mode (toggle, version ^1+)
- **Special modes**: hazard flasher, procession mode (amber wig-wag)
- **Read current settings**: query via `APP_QUERY` / `MMS_QUERY_INFO`
- **Version info**: `APP_VERSIONS`, `HW_VERSIONS`, `SYS_VERSIONS`
- **Factory reset**: `DATA_FACTORY_DEFAULT` with confirm/revert flow
- **Error handling**: connection loss recovery, out-of-range notification, GATT error mapping via `y7/a.java`

## Evidence checklist
- [x] APK hash + version code: SHA256 `1efb084dff01d0d68caf23883adf023806c0f8d2604494fbc5c51b37239d5141` (XAPK), version 2.1.0 (code 44)
- [x] BLE service/characteristic UUID table (NUS-based, confirmed from libapp.so strings)
- [x] Complete setting ID → value mapping (confirmed from lb_config.xml)
- [x] Command ID list (confirmed from libapp.so strings)
- [x] DFU mechanism (Nordic DFU, confirmed from jadx decompile)
- [ ] HCI snoop log: connect + single setting change (requires physical device)
- [ ] Protobuf message schema reconstruction (requires deeper Dart snapshot analysis)
- [ ] Exact protobuf field numbers for each command (requires HCI capture or Dart snapshot disassembly)

## Remaining work (requires physical device)
1. HCI snoop capture of a connect + query + setting change session
2. Parse protobuf wire format from captured UART data to reconstruct field numbers
3. Confirm exact protobuf message structure (lightbar.pb.dart schema)
4. Validate all setting value ranges match device behavior
5. Test factory reset and DFU flows

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
