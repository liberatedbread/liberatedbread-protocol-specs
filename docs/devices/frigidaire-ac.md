# Frigidaire Connected Air Conditioners

> **Status**: Research
> **Protocol**: WiFi (cloud-connected)
> **Manufacturer**: Frigidaire (Electrolux)
> **Manufacturer Status**: Unsupported (cloud-dependent — if Electrolux shuts down servers, app control is lost)

## Overview

Frigidaire sells WiFi-connected air conditioners across three product families: window units,
portable units, and wall-mounted/PTAC units. All are controlled through the Frigidaire app
(Electrolux platform) and communicate via the Electrolux cloud. This makes them vulnerable
to bricking if Electrolux discontinues the cloud service.

This is the first HVAC/climate device category in the OpenGreenIoT project. The protocol
has not yet been reverse engineered — device specs are hypothesized from publicly available
app feature descriptions and need validation through APK analysis and network captures.

## Hardware

### Window AC (FHWW / GHWQ Series)

| Property | Value |
|----------|-------|
| Models | FHWW082WCE (8K BTU), FHWW102WCE (10K BTU), FHWW152WCE (15K BTU) |
| Gallery Models | GHWQ083WC1 (8K BTU, adds ionizer) |
| Radio | WiFi 802.11 b/g/n (2.4 GHz) |
| Chipset | TBD |
| FCC ID | TBD |

### Portable AC (FHPC / FHPH Series)

| Property | Value |
|----------|-------|
| Models | FHPC082AC1 (8K BTU), FHPH132AB1 (13K BTU) |
| Radio | WiFi 802.11 b/g/n (2.4 GHz) |
| Chipset | TBD |
| FCC ID | TBD |

### Wall-Mounted / PTAC

| Property | Value |
|----------|-------|
| Models | TBD — specific connected model numbers need verification |
| Radio | WiFi 802.11 b/g/n (2.4 GHz, expected) |
| Chipset | TBD |
| FCC ID | TBD |

## Protocol Summary

!!! warning "Hypothesized Protocol"
    The protocol details below are hypothesized from public app features and common
    Electrolux platform patterns. Nothing has been validated through APK analysis or
    network captures yet.

### Architecture (Hypothesized)

```
┌──────────────┐    WiFi    ┌──────────────────┐    MQTT/HTTPS    ┌──────────────────┐
│  AC Unit     │◄──────────►│  Home Router     │◄───────────────►│  Electrolux Cloud│
│  (WiFi SoC)  │            │                  │                 │  (AWS/Azure?)    │
└──────────────┘            └──────────────────┘                 └────────┬─────────┘
                                                                         │
                                                                         │ MQTT/HTTPS
                                                                         ▼
                                                                ┌──────────────────┐
                                                                │  Frigidaire App  │
                                                                │  (Mobile)        │
                                                                └──────────────────┘
```

### Transport

- **Primary**: WiFi to Electrolux cloud (MQTT over TLS or HTTPS REST — unconfirmed)
- **Local API**: Unknown — needs investigation (some Electrolux devices may have local HTTP fallback)
- **Provisioning**: Likely SoftAP or BLE to transfer WiFi credentials during setup

### Authentication

- Electrolux user account (OAuth2 expected)
- Device-to-cloud authentication (certificate or token-based, TBD)

## Commands

### Power

| Command | Description |
|---------|-------------|
| `set_power_on` | Turn AC on |
| `set_power_off` | Turn AC off |

### Mode

| Command | Value | Description |
|---------|-------|-------------|
| `set_mode` | `cool` | Cooling mode |
| `set_mode` | `eco` | Energy saver / eco mode |
| `set_mode` | `fan_only` | Fan only (no compressor) |
| `set_mode` | `dehumidify` | Dehumidify mode (portable only) |

### Temperature

| Command | Range | Description |
|---------|-------|-------------|
| `set_temperature` | 60-90°F (16-32°C) | Set target temperature |

### Fan Speed

| Command | Value | Description |
|---------|-------|-------------|
| `set_fan_speed` | `auto` | Automatic fan speed |
| `set_fan_speed` | `low` | Low speed |
| `set_fan_speed` | `medium` | Medium speed |
| `set_fan_speed` | `high` | High speed |

### Other Controls

| Command | Description |
|---------|-------------|
| `set_timer` | Set on/off timer (0.5-24 hours) |
| `set_sleep_on/off` | Enable/disable sleep mode |
| `set_display_on/off` | Toggle display |
| `set_clean_air_on/off` | Toggle ionizer (Gallery models only) |
| `reset_filter` | Reset filter alert after cleaning |

## Home Assistant Entities

| Entity | Platform | Device Class | Notes |
|--------|----------|-------------|-------|
| Air Conditioner | `climate` | — | Main control: power, mode, temp, fan |
| Room Temperature | `sensor` | `temperature` | Current room temperature |
| Filter Alert | `binary_sensor` | `problem` | Needs cleaning indicator |
| Sleep Mode | `switch` | — | Sleep mode toggle |
| Display | `switch` | — | Display on/off |
| Clean Air | `switch` | — | Ionizer (Gallery window models only) |
| Drain Full | `binary_sensor` | `problem` | Tank full (portable models only) |

## Tools Used

- [ ] mitmproxy — HTTPS/MQTT traffic capture between app and cloud
- [ ] Wireshark — network packet analysis
- [ ] jadx — APK decompilation and static analysis
- [ ] apkeep — APK retrieval from Play Store
- [ ] nmap — local network scan for device services
- [ ] Frida — runtime app instrumentation (if needed for certificate pinning bypass)

## Next Steps

1. **Verify app package ID**: Confirm `com.electrolux.oneapp.frigidaire` on Google Play
2. **Fetch and decompile APK**: Use apkeep + jadx for static analysis
3. **Identify cloud endpoints**: Grep for MQTT broker addresses, REST API base URLs, authentication flows
4. **Network capture**: Set up mitmproxy to capture app-to-cloud traffic during control operations
5. **Check for local API**: Scan device IP for open ports / HTTP endpoints
6. **Validate hypothesized protocol**: Compare actual traffic against the hypothesized MQTT/HTTP structure

## References

- Frigidaire Connected Products: https://www.frigidaire.com/owner-center/connect/
- Frigidaire App on Google Play: https://play.google.com/store/apps/details?id=com.electrolux.oneapp.frigidaire

## Contributors

- OpenGreenIoT community — initial target spec and hypothesized protocol documentation
