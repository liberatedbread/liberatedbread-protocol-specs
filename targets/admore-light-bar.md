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

## App architecture (from Flutter Dart snapshot reverse engineering)

### Reconstructed Dart source tree
```
package:admore_light_bar/
├── main.dart
├── internal/
│   ├── extensions.dart
│   └── version2/
│       ├── auth/ (auth_api.dart, concrete_auth_api.dart, auth_api_repository.dart)
│       └── local_cache/ (devices_api.dart, local_device.dart, local_device_repository.dart, local_devices_storage.dart)
├── remote/
│   ├── auth_config.dart         ← Firebase auth configuration
│   ├── cloud_storage.dart       ← Firebase Storage (firmware DFU zips, diagnostics upload)
│   ├── lightbar.dart            ← PRIMARY PROTOCOL: sendLightOutput(), sendBarTest(), _queryLightbar(), _connectUart()
│   ├── signals.dart             ← Turn signal state model (SignalModel, _SignalColor)
│   └── uart.dart                ← BLE UART abstraction layer
├── utils/
│   ├── ble_extra.dart           ← BLE helper utilities
│   └── snackbar.dart
├── views/version2/
│   ├── bindings/ (armband, config, device, home, scan, settings)  ← GetX dependency injection
│   ├── controllers/
│   │   ├── armband_controller.dart   ← Armband provisioning (Left/Right), _connectUart(), sendDSSCommit()
│   │   ├── config_controller.dart    ← lb_config.xml parsing (_parseContinuous, _parseDiscrete, _parseToggle)
│   │   ├── developer_controller.dart ← Developer/diagnostic mode
│   │   ├── device_controller.dart    ← Device connection management
│   │   ├── dfu_controller.dart       ← Nordic DFU firmware update flow
│   │   ├── home_controller.dart
│   │   ├── scan_controller.dart      ← BLE scanning (startScan, stopScan, autoConnect)
│   │   ├── settings_controller.dart
│   │   └── your_info_controller.dart
│   ├── model/
│   │   ├── ble_uart.dart         ← BleUart / BleUartDevice model (openUart, UART state)
│   │   ├── config_error.dart
│   │   └── version_model.dart    ← Version info model
│   └── screens/ (armband, bluetooth_off, config, developer, device, dfu, home_v2, scan, settings, your_info, email_verify, change_email, change_password)
└── widgets/ (lb_conf_widgets.dart, scan_result_tile.dart)

package:messaging_common/
├── build_dart/
│   ├── lightbar.pb.dart          ← Protobuf message classes (generated from .proto)
│   └── lightbar.pbenum.dart      ← Protobuf enum definitions
└── kmessaging.dart               ← KMsg routing system (CmdSinkSocket, CmdSourceSocket, EvtSinkSocket, EvtSourceSocket)
```

### Key dependencies
- **BLE**: `flutter_blue_plus` (not flutter_reactive_ble)
- **State mgmt**: GetX (`package:get`)
- **Serialization**: `package:protobuf` (Dart protobuf runtime)
- **DFU**: `package:nordic_dfu` (`dev.steenbakker.nordic_dfu`)
- **Backend**: Firebase Auth, Firebase Storage, Firestore
- **UI framework**: Cupertino-style (iOS-like) with `settings_ui`

## Protocol architecture (confirmed from APK static analysis)

### Transport layer
- BLE Nordic UART Service (NUS) — data sent as byte stream over UART emulation
- RX characteristic (app writes to device): `6E400002-B5A3-F393-E0A9-E50E24DCCA9E`
- TX characteristic (device notifies app): `6E400003-B5A3-F393-E0A9-E50E24DCCA9E`

### Message layer
- **Protocol Buffers** (protobuf) — messages serialized using `package:protobuf`
- Protobuf schema defined in `package:messaging_common/build_dart/lightbar.pb.dart` and `lightbar.pbenum.dart`
- Internal message bus uses **KMsg** (`package:messaging_common/kmessaging.dart`) with source/destination routing

### KMsg routing system

#### Socket types
The KMsg system uses a publish/subscribe socket pattern:
- `CmdSinkSocket` / `CmdSourceSocket` — command request/response sockets
- `EvtSinkSocket` / `EvtSourceSocket` — event subscription sockets
- `_DestinationSocket` / `_SourceSocket` — internal routing primitives
- Reply mechanism: `kmsgCmdSourcePublishReply()` with timeout

#### Route IDs (36 total)

**Command Sources (SRC_CMD)**: `APP`, `HOST_APP`, `HOST_DIAG`, `UART_DIAG`, `KMSG`, `BKND_APP`, `BKND_DIAG`, `APP_ARML`, `APP_ARMR`
**Command Destinations (DST_CMD)**: `APP`, `BLE_ENGINE`, `KMSG`, `APP_DIAG`, `APP_ARML`, `APP_ARMR`, `APP_DIAG_ARML`, `APP_DIAG_ARMR`
**Event Sources (SRC_EVT)**: `APP`, `APP_ARML`, `APP_ARMR`, `APP_DIAG`, `APP_DIAG_ARML`, `APP_DIAG_ARMR`, `BLE_ENGINE`, `KMSG`
**Event Destinations (DST_EVT)**: `APP`, `APP_ARML`, `APP_ARMR`, `BKND_APP`, `BKND_DIAG`, `BLE_ENGINE_APP`, `HOST_APP`, `HOST_DIAG`, `KMSG`
**Special**: `SRC_UNASSIGNED`

#### KMSG system events (14)
| Event | Description |
|---|---|
| `KMSG_BLE_CONNECT` | BLE connection established |
| `KMSG_BLE_CONNECT_READY` | BLE connection ready for commands |
| `KMSG_BLE_DISCONNECT` | BLE disconnected |
| `KMSG_BLE_ADVERTISING_START` | Device advertising started |
| `KMSG_BLE_ADVERTISING_STOP` | Device advertising stopped |
| `KMSG_BLE_SCANNING_START` | BLE scan started |
| `KMSG_BLE_SCANNING_STOP` | BLE scan stopped |
| `KMSG_BLE_ARMBAND_L_CONNECT` | Left armband connected |
| `KMSG_BLE_ARMBAND_L_DISCONNECT` | Left armband disconnected |
| `KMSG_BLE_ARMBAND_R_CONNECT` | Right armband connected |
| `KMSG_BLE_ARMBAND_R_DISCONNECT` | Right armband disconnected |
| `KMSG_BLE_SIGNALS_CONNECT` | Signals accessory connected |
| `KMSG_BLE_SIGNALS_DISCONNECT` | Signals accessory disconnected |

### Device state machine (19 states)
```
INITIAL → STARTUP → SEARCHING → CONNECT → SETUP_DONE → IDENTIFY → SERIAL → QUERY_STATE → SETTINGS
                       ↓                                                                      ↓
                  SEARCH_FAIL                                                               SAVING
                       ↓                                                                      ↓
                  RECONNECTING → RECONNECT_FAIL                                          PROCESSING
                                                                                              ↓
                                                                               VERIFYING → TRANSFERRING → TRANSFER_FAIL
                                                                                              ↓
                                                                                        DISCONNECT → EXIT_SLEEP
```

### Connection flow (from debug strings)
1. **Scan**: `startScan()` → filter by name `"AdMore Light Bar"` or `"AdMore Armband"`
2. **Connect**: `autoConnect` → `discoverServices()` → find NUS service UUID
3. **UART open**: `_connectUart()` → `openUart()` on `BleUartDevice` → subscribe to TX notifications (`setNotifyValue`)
4. **Query**: `_queryLightbar()` → `getLightbarData()` → parse protobuf response
5. **Ready**: `KMSG_BLE_CONNECT_READY` → device ready for commands
6. **Reconnect**: on disconnect → `RECONNECTING` → retry with exponential backoff

### Protobuf message types (14 from libapp.so)

| Protobuf Type | Direction | Purpose |
|---|---|---|
| `t_cmdAppQuery` | app→dev | Query device state |
| `t_cmdAppQuery_Reply` | dev→app | Device state response |
| `t_cmdAppNop` | app→dev | No-op / keepalive |
| `t_cmdAppWriteString` | app→dev | Write string data (`APP_WRITE_STRING`) |
| `t_cmdAppInjectEvent` | app→dev | Inject event (`APP_INJECT_EVENT`) |
| `t_cmdAppSetDstEvt` | app→dev | Set event routing destination |
| `t_cmdAppSetDstEvtDiag` | app→dev | Set diagnostic event routing destination |
| `t_cmdDssSetData` | app→dev | Write a device setting (setting ID + value) |
| `t_cmdDssGetData` | app→dev | Read a device setting |
| `t_cmdDssGetData_Reply` | dev→app | Read setting response |
| `t_cmdDssOperation` | app→dev | System operations (commit, factory reset, reload, etc.) |
| `t_cmdLosSetLight` | app→dev | Direct LED output control |
| `t_evtAppEvent` | dev→app | Generic state event notification |
| `t_evtDiagMmsDecelData` | dev→app | Diagnostic deceleration sensor data |

### Protobuf enums (7)
| Enum | Likely purpose |
|---|---|
| `e_CMD` | Top-level command type discriminator |
| `e_APP_QUERY` | Query type variants |
| `e_APP_EVT` | App event type variants |
| `e_CONFIG` | Configuration operation type |
| `e_DSS_OPERATION` | DSS operation type (commit, reset, reload) |
| `e_LIGHT_OUTPUT` | Light output mode/type |
| `e_SKT` | Socket/routing type |

### DSS (Data Storage Subsystem)
The DSS is the main mechanism for reading/writing settings:
- **`DSS_SET_DATA`**: Write a setting — takes a setting ID string (e.g., `LOS_TAIL_LIGHT_BRIGHTNESS`) and integer value
- **`DSS_GET_DATA`**: Read a setting — takes a setting ID, reply contains current value
- **`DSS_OPERATION`**: System-level operations — `DATA_COMMIT`, `DATA_FACTORY_DEFAULT`, `DATA_RELOAD`, `DATA_MAINTAIN`, `DATA_ABANDON_RESTORE`

### App method call graph (remote/lightbar.dart)
```
_connectUart() → BleUartDevice.openUart() → NUS service discovery + TX notify subscribe
_queryLightbar() → getLightbarData() → protobuf parse response
sendLightOutput() → t_cmdLosSetLight protobuf → NUS RX writeCharacteristic
sendBarTest() → t_cmdLosSetLight protobuf → NUS RX writeCharacteristic
sendArmbandLeft() → armband NUS variant (DCCAAE)
sendArmbandRight() → armband NUS variant (DCCAAE)
sendArmbandDefault() → armband default config
sendArmbandUndefined() → armband reset to unprovisioned
setLight / setDecel / setLeftTurn / setRightTurn → helper methods for direct control
```

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
The device reports version info with these field names (from `version_model.dart`):
| Field | Description |
|---|---|
| `productFirmware` | Current firmware version |
| `productFirmwareBeta` | Beta firmware version (if any) |
| `productBootloader` | Bootloader version |
| `productSystem` | System/OS version |
| `productDatabase` | Settings database version |
| `productModel` | Hardware model identifier |
| `productId` | Unique device identifier |

### Firmware update (DFU)
- Uses Nordic DFU library (`package:nordic_dfu`)
- Flutter plugin: `dev.steenbakker.nordic_dfu`
- DFU zip files served from Firebase Storage:
  - Project: `admore-light-bar-with-ble`
  - Storage bucket: `admore-light-bar-with-ble.appspot.com`
  - Database URL: `https://admore-light-bar-with-ble.firebaseio.com`
  - Firmware path: `lightbar-firmware/`
  - Debug firmware: `/debug/dfu_lightbar_latest.zip`
- Latest version check: `getLatestLightbarVersion()` in `cloud_storage.dart`
- Device enters DFU mode via `ENTER_DFU` command, advertises as `"AdMore Light Bar DFU"`
- DFU states: `INITIAL` → `PROCESSING` → `VERIFYING` → `TRANSFERRING` → success or `TRANSFER_FAIL`

### Config parsing (config_controller.dart)
The `lb_config.xml` Flutter asset defines all settings with three types:
- **Discrete**: `_parseDiscrete()` — finite set of labeled value options
- **Toggle**: `_parseToggle()` — binary on/off with explicit on/off values
- **Continuous**: `_parseContinuous()` — range with `continuousDivisor` and `continuousUpdates` (not used in current config)

Setting subtypes:
- **NativeSetting**: `isnative=true`, `nativechangetype=PREFERENCE_CHANGE` — stored as app preference, not sent to device directly. Example: `MMS_DECEL_TOGGLE` controls UI visibility of sub-settings.
- **Dependent settings**: `<dependent to="MMS_DECEL_TOGGLE" />` — hidden when parent is OFF. Example: `MMS_DECEL_THRESHOLD`, `MMS_DECEL_OFF_DELAY_MS`, `MMS_DECEL_COUNT`
- **Version-gated settings**: `<version value="^1" />` — only shown for firmware version ≥1. Example: `LIS_ENABLE_BRAKE_INVERT`, `LIS_ENABLE_TWO_WIRE`, `LOS_DEALER_DEMO_MODE`

### Armband protocol
- Armbands are turn signal accessories (left/right arms)
- Provisioning flow: scan `"AdMore Armband"` → connect → mark as Left or Right → device renames to `"AdMore Armband Left"` or `"AdMore Armband Right"` → disconnect → USB reset → reconnect to verify
- Armband NUS service: `6E400001-B5A3-F393-E0A9-E50E24DCCAAE`
- Armband-specific methods: `sendArmbandLeft()`, `sendArmbandRight()`, `sendArmbandDefault()`, `sendArmbandUndefined()`
- Armband routing: `SRC_CMD_APP_ARML` / `SRC_CMD_APP_ARMR` → `DST_CMD_APP_ARML` / `DST_CMD_APP_ARMR`
- Armband types: `ArmbandType` enum with `LEFT`, `RIGHT`, `UNDEFINED`
- Armband setting: `ARMBAND_SIDE` (provisioning command)
- Firebase: `addArmbandToFirebase()`, `updateProductArmband()`

### Diagnostics
- Diagnostic event routing: `APP_SET_DST_EVT_DIAG` command
- Deceleration diagnostic data: `t_evtDiagMmsDecelData` protobuf message
- Diagnostic upload paths: `diagnostics/accel/`, `accel_diag/`
- Upload to Firebase Storage: `Upload Diagnostics` feature in developer screen
- Diagnostic sources: `SRC_CMD_UART_DIAG`, `SRC_CMD_HOST_DIAG`, `SRC_CMD_BKND_DIAG`

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
- **Error handling**: connection loss → `RECONNECTING` state with retry; autoConnect support; GATT error handling via flutter_blue_plus

## Evidence checklist
- [x] APK hash + version code: SHA256 `1efb084dff01d0d68caf23883adf023806c0f8d2604494fbc5c51b37239d5141` (XAPK), version 2.1.0 (code 44)
- [x] BLE service/characteristic UUID table (4 NUS variants, confirmed from libapp.so strings)
- [x] Complete setting ID → value mapping (18 settings from lb_config.xml, all values enumerated)
- [x] Command ID list — all setting IDs, system commands, test commands, override commands (confirmed from libapp.so)
- [x] DFU mechanism (Nordic DFU, dev.steenbakker.nordic_dfu, confirmed from libapp.so)
- [x] App architecture — full Dart source tree reconstructed from package: paths in libapp.so
- [x] Protobuf message types — 14 types identified (t_cmd*, t_evt*)
- [x] Protobuf enum types — 7 enums identified (e_CMD, e_APP_EVT, e_APP_QUERY, e_CONFIG, e_DSS_OPERATION, e_LIGHT_OUTPUT, e_SKT)
- [x] KMsg routing — 36 route IDs, 14 system events, socket architecture (CmdSink/Source, EvtSink/Source)
- [x] Device state machine — 19 states from INITIAL through SETTINGS/DFU
- [x] Connection flow — scan → connect → discover → UART open → query → ready
- [x] Version fields — 7 product fields (firmware, firmwareBeta, bootloader, system, database, model, id)
- [x] Armband protocol — provisioning flow, NUS UUID, routing IDs, type enum
- [x] Config parsing — 3 setting types (discrete, toggle, continuous), native settings, dependencies, version gating
- [x] Firebase backend — project ID, storage bucket, firmware paths, diagnostic upload paths
- [ ] Protobuf field numbers — exact wire format requires HCI capture or blutter analysis (blutter not available on this system)
- [ ] HCI snoop log: connect + single setting change (requires physical device)

## Remaining work (requires physical device or blutter)
1. HCI snoop capture of a connect + query + setting change session
2. Parse protobuf wire format from captured UART data to reconstruct field numbers
3. blutter analysis of libapp.so to extract Dart class field offsets and protobuf tag constants
4. Validate all setting value ranges match device behavior
5. Test factory reset and DFU flows
6. Confirm armband provisioning protocol via HCI capture

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
