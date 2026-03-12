# CHEF iQ Sense — Protocol Specification

!!! warning "Static Analysis Only"
    This specification was derived from static APK analysis of `com.chefman.chefiq.prod` v5.0.0.
    All UUIDs and protocol details require device validation. Confidence levels are noted per section.

## Overview

The CHEF iQ product family (Smart Thermometer / iQ Sense, Smart Cooker, Smart Hub, Mini Oven)
uses Bluetooth Low Energy for local device communication and AWS IoT Core (MQTT) for cloud
features. The Android app is built with React Native / Expo and uses `react-native-ble-manager`
for BLE operations and AWS Amplify for cloud connectivity.

### Architecture

```
┌─────────────┐    BLE     ┌──────────────────┐    WiFi    ┌──────────────────┐
│   Probes    │◄──────────►│   Hub / Device   │◄──────────►│   AWS IoT Core   │
│ (battery)   │            │ (mains-powered)  │            │  iot.chefiq.com  │
└─────────────┘            └──────────────────┘            └────────┬─────────┘
                                    ▲                               │
                                    │ BLE                           │ MQTT
                                    ▼                               ▼
                           ┌──────────────────┐            ┌──────────────────┐
                           │   Mobile App     │◄──────────►│  api.chefiq.com  │
                           │  (React Native)  │   HTTPS    │  graph.chefiq.com│
                           └──────────────────┘            └──────────────────┘
```

## BLE Protocol

### Service UUID Families

Five custom BLE service families were identified. Each family uses a common base UUID
(bytes 5-16) with varying bytes 1-4 for service and characteristic UUIDs.

**Confidence: HIGH** — UUIDs extracted directly from Hermes bytecode string table.

#### Family 1: `9C6F____-0420-41C1-BD98-7A015C45DC5A` (iQ Sense / Thermometer)

This family has the most characteristics, consistent with being the primary thermometer service.

| UUID | Name (hypothesized) | Properties (hypothesized) |
|------|---------------------|--------------------------|
| `9C6F00FC-0420-41C1-BD98-7A015C45DC5A` | **Primary Service** | — |
| `9C6FF050-0420-41C1-BD98-7A015C45DC5A` | Probe Data 0 | read, notify |
| `9C6FF051-0420-41C1-BD98-7A015C45DC5A` | Probe Data 1 | read, notify |
| `9C6FF052-0420-41C1-BD98-7A015C45DC5A` | Probe Data 2 | read, notify |
| `9C6FF054-0420-41C1-BD98-7A015C45DC5A` | Probe Data 4 | read, notify |
| `9C6FF055-0420-41C1-BD98-7A015C45DC5A` | Probe Data 5 | read, notify |
| `9C6FFF81-0420-41C1-BD98-7A015C45DC5A` | Unknown F81 | unknown |
| `9C6FFF82-0420-41C1-BD98-7A015C45DC5A` | Unknown F82 | unknown |
| `9C6FFF84-0420-41C1-BD98-7A015C45DC5A` | Firmware Info | read |
| `9C6FFF85-0420-41C1-BD98-7A015C45DC5A` | Device Config | read, write |
| `9C6FFFB0-0420-41C1-BD98-7A015C45DC5A` | WiFi Provisioning | write |
| `9C6FFFC0-0420-41C1-BD98-7A015C45DC5A` | Control 0 | write |
| `9C6FFFC1-0420-41C1-BD98-7A015C45DC5A` | Control 1 | write |
| `9C6FFFF0-0420-41C1-BD98-7A015C45DC5A` | Command TX | write, write_without_response |
| `9C6FFFF1-0420-41C1-BD98-7A015C45DC5A` | Command RX | read, notify |

**Notes:**

- The `F05x` range likely carries temperature data from individual probe sensors
- The `FFFx` range appears to be a command/response channel
- The `FFBx` range may be WiFi provisioning (BLUETOOTH_REGISTER_AND_CONNECT_TO_WIFI)
- The `FFC0/C1` pair may be control channels

#### Family 2: `048A____-CD06-4D57-A048-CCD5CB9F8F43` (Smart Cooker)

| UUID | Name (hypothesized) | Properties (hypothesized) |
|------|---------------------|--------------------------|
| `048A00FF-CD06-4D57-A048-CCD5CB9F8F43` | **Primary Service** | — |
| `048AF000-CD06-4D57-A048-CCD5CB9F8F43` | Cooker Data 0 | read, notify |
| `048AF001-CD06-4D57-A048-CCD5CB9F8F43` | Cooker Data 1 | read, notify |
| `048AF010-CD06-4D57-A048-CCD5CB9F8F43` | Cooker Control 0 | write |
| `048AF011-CD06-4D57-A048-CCD5CB9F8F43` | Cooker Control 1 | write |
| `048AF014-CD06-4D57-A048-CCD5CB9F8F43` | Cooker Config | read, write |
| `048AF020-CD06-4D57-A048-CCD5CB9F8F43` | Cooker Status 0 | read, notify |
| `048AF021-CD06-4D57-A048-CCD5CB9F8F43` | Cooker Status 1 | read, notify |
| `048AF022-CD06-4D57-A048-CCD5CB9F8F43` | Cooker Status 2 | read, notify |
| `048AFFF0-CD06-4D57-A048-CCD5CB9F8F43` | Command TX | write |
| `048AFFF1-CD06-4D57-A048-CCD5CB9F8F43` | Command RX | read, notify |

#### Family 3: `6AC4____-5BC3-4E99-ACB8-F85D442B9AE4` (Smart Hub)

| UUID | Name (hypothesized) | Properties (hypothesized) |
|------|---------------------|--------------------------|
| `6AC400FB-5BC3-4E99-ACB8-F85D442B9AE4` | **Primary Service** | — |
| `6AC4FF80-5BC3-4E99-ACB8-F85D442B9AE4` | Hub Data | read, notify |
| `6AC4FF83-5BC3-4E99-ACB8-F85D442B9AE4` | Hub Config | read, write |
| `6AC4FFB1-5BC3-4E99-ACB8-F85D442B9AE4` | Hub Provisioning 1 | write |
| `6AC4FFB2-5BC3-4E99-ACB8-F85D442B9AE4` | Hub Provisioning 2 | write |

#### Family 4: `8A71____-BABE-B7AE-074F-86D0C0B50089` (Probe Peripheral)

| UUID | Name (hypothesized) | Properties (hypothesized) |
|------|---------------------|--------------------------|
| `8A7100FE-BABE-B7AE-074F-86D0C0B50089` | **Primary Service** | — |
| `8A71FFA0-BABE-B7AE-074F-86D0C0B50089` | Probe Data 0 | read, notify |
| `8A71FFA2-BABE-B7AE-074F-86D0C0B50089` | Probe Data 2 | read, notify |
| `8A71FFA3-BABE-B7AE-074F-86D0C0B50089` | Probe Data 3 | read, notify |
| `8A71FFA4-BABE-B7AE-074F-86D0C0B50089` | Probe Config | read, write |
| `8A71FFA5-BABE-B7AE-074F-86D0C0B50089` | Probe Status | read, notify |

#### Family 5: `F640____-6F49-4B5B-9BF8-76B3775D4D01` (Mini Oven)

| UUID | Name (hypothesized) | Properties (hypothesized) |
|------|---------------------|--------------------------|
| `F64000FD-6F49-4B5B-9BF8-76B3775D4D01` | **Primary Service** | — |
| `F640FFF0-6F49-4B5B-9BF8-76B3775D4D01` | Command TX | write |
| `F640FFF1-6F49-4B5B-9BF8-76B3775D4D01` | Command RX | read, notify |

### BLE Communication Pattern

**Confidence: MEDIUM** — inferred from react-native-ble-manager usage and constant names.

1. **Scan** with service UUID filter for the target device family
2. **Connect** to discovered peripheral
3. **Discover services** and characteristics
4. **Subscribe** to notification characteristics (CCCD 0x2902 write)
5. **Read/Write** characteristics for data exchange

The app uses a notification-based data flow:

- Temperature data arrives as BLE notifications on the `F05x` characteristics
- Commands are written to the `FFF0` characteristic
- Responses arrive as notifications on the `FFF1` characteristic

### WiFi Provisioning over BLE

**Confidence: MEDIUM** — inferred from constant names.

The app provisions WiFi credentials to the device over BLE:

1. Connect to device via BLE
2. Write WiFi SSID and password to provisioning characteristics (`FFB0`-`FFB2`)
3. Device connects to WiFi network
4. Device registers with AWS IoT Core
5. App receives confirmation via BLE notification

Key constants:
- `BLUETOOTH_REGISTER_AND_CONNECT_TO_WIFI_SUCCESS`
- `BLUETOOTH_START_WIFI_NETWORK_TIMER`
- `WIFI_CONNECT_IOT_CONNECTION`

## Cloud Protocol

### Authentication

**Confidence: HIGH** — AWS Cognito pool ID extracted from BuildConfig.

- AWS Cognito Identity Pool: `us-east-1:f95270e2-a024-41dc-bf5e-2d5df159f259`
- Google Sign-In supported (web client ID present)
- Auth flow: email/password + social login via AWS Amplify Auth

### REST API

**Confidence: HIGH** — endpoints from BuildConfig.

| Endpoint | Purpose |
|----------|---------|
| `https://api.chefiq.com/` | Main REST API |
| `https://graph.chefiq.com/graphql` | GraphQL API for recipes, cooking data |
| `https://media.chefiq.com` | Media/image CDN |
| `https://{service}-api.chefiq.com/v1` | Microservice endpoints |
| `iot.chefiq.com` | AWS IoT Core MQTT broker |

### MQTT / AWS IoT

**Confidence: MEDIUM** — AWS IoT endpoint confirmed; topic patterns inferred from constants.

The app uses AWS Amplify PubSub for real-time device communication:

- Device state updates via MQTT topics (WIFI_HANDLE_PUBSUB_UPDATE)
- Cloud-to-device commands (DEVICE_SEND_TO_DEVICE)
- Device registration and subscription (DEVICE_REGISTER_AND_SUBSCRIBE)

Hypothesized topic pattern: `$aws/things/{device_id}/shadow/...`

## Appliance State Machine

**Confidence: HIGH** — state names extracted from string constants.

```
                    ┌──────────────┐
                    │     IDLE     │
                    │  (WARNING)   │
                    └──────┬───────┘
                           │ start cook
                    ┌──────▼───────┐
           ┌────────┤  DELAY_START │
           │        └──────┬───────┘
           │               │ timer expires
           │        ┌──────▼───────┐
           │        │   PREHEAT    │
           │        │  DONE_DELAY  │
           │        └──────┬───────┘
           │               │ target reached
           │        ┌──────▼───────┐
  abort/   │        │   COOKING    │◄───── resume
  error    │        │  (ATTENDED)  │
           │        └──────┬───────┘
           │               │ timer/temp done
           │        ┌──────▼───────┐
           │        │  KEEP_WARM   │
           │        └──────┬───────┘
           │               │ done
           │        ┌──────▼───────┐
           └───────►│  DONE_COOK   │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │    ERROR     │
                    │   (PAUSE)    │
                    └──────────────┘
```

### Termination conditions
- Probe overheat / sensor error / probe disconnected
- Appliance overheat / heater failure
- Door open (oven)
- Communication NACK / local NACK

## Temperature Data

**Confidence: LOW** — format not yet confirmed from binary analysis.

- The app supports Fahrenheit and Celsius (DEFAULT_TEMPERATURE_UNIT_SETTING)
- Multiple probes supported (probe index 0-5 based on characteristic UUIDs)
- Probe status values: OK, sensor error, overheat, not inserted properly,
  disconnected, warning, regulatory certification info
- Ambient temperature alerts supported

## Probe Hardware Variants

**Confidence: MEDIUM** — version strings found in bytecode.

| Variant | Notes |
|---------|-------|
| Probe2v3 | v3 hardware, 2nd generation |
| Probe3v3 | v3 hardware, 3rd generation |
| Probe4v8 | v8 hardware, 4th generation |

Multi-probe support: Hub models support 1-4 probes (CQ60-1 through CQ60-4).

## Validation TODO

These items require a physical device to confirm:

- [ ] Confirm BLE advertised name prefix/pattern
- [ ] Verify service UUID to device type mapping
- [ ] Capture actual temperature data format (byte layout, endianness, scale factor)
- [ ] Confirm characteristic properties (read/write/notify)
- [ ] Map command opcodes for the FFF0/FFF1 command channel
- [ ] Verify WiFi provisioning byte sequence
- [ ] Capture MQTT topic names and message payloads
- [ ] Determine probe identification method in multi-probe setups

## Replacement App MVP Acceptance Criteria

A minimal replacement app for the iQ Sense thermometer should:

1. Scan and connect to the device via BLE (service UUID filter)
2. Read real-time temperature from all connected probes
3. Display temperature in user-selected units (F/C)
4. Set target temperature alerts with notifications
5. Show probe connection status
6. Work without cloud account (BLE-only mode)
7. Support background BLE notifications (foreground service)
