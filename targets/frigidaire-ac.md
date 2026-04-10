# Frigidaire Connected Air Conditioners

## Target metadata
- target_id: frigidaire-window-ac, frigidaire-portable-ac, frigidaire-wall-ac
- app package_id(s): com.electrolux.oneapp.frigidaire (needs verification — may also appear as com.frigidaire.android or via SmartHQ/Electrolux ecosystem apps)
- device class: window air conditioner, portable air conditioner, wall-mounted air conditioner
- transport(s): Wi-Fi (802.11 b/g/n 2.4 GHz)
- local-only viability: medium — cloud-connected via Electrolux platform; local API may exist but is unconfirmed; DNS redirect or local broker could enable offline control if MQTT is used

## Known facts (public + observed)
- Frigidaire is an Electrolux brand; connected appliances use the Electrolux/Frigidaire app platform
- WiFi-connected window ACs include FHWW series (FHWW082WCE, FHWW102WCE, FHWW152WCE) and Gallery GHWQ series (GHWQ083WC1)
- WiFi-connected portable ACs include FHPC series (FHPC082AC1) and FHPH series (FHPH132AB1)
- App provides: power on/off, mode selection (cool/eco/fan only), temperature setpoint (60-90°F), fan speed (auto/low/medium/high), timer, sleep mode, filter status
- Gallery models add Clean Air (ionizer) feature
- Portable models add Dehumidify mode and drain-full indicator
- Devices connect to home WiFi during setup (2.4 GHz only) and communicate via Electrolux cloud servers

## Device discovery signals
- BLE:
  - Not expected for ongoing control; BLE may be used for initial WiFi provisioning (unconfirmed)
  - advertised name patterns: unknown
  - service UUIDs: unknown
- Wi-Fi:
  - SSID patterns: unknown (may broadcast AP for provisioning)
  - default gateway IPs: unknown
  - mDNS service types: unknown (check for _http._tcp or custom Electrolux service)
  - UPnP URNs / LOCATION: unknown

## Threat model + guardrails
- Scope: only owned devices, no safety-critical use cases
- Temperature commands must be bounded to safe ranges (60-90°F / 16-32°C)
- Do not attempt to bypass any safety interlocks (compressor delay timers, overtemp shutoff)
- Non-goals: firmware modification, cloud account compromise, multi-tenant access

## First experiments (do these first)
1) Network capture: set up mitmproxy/Wireshark on WiFi network during app usage; capture HTTPS/MQTT traffic between app and cloud
2) Fetch APK: `apkeep -a com.electrolux.oneapp.frigidaire` (verify package ID on Play Store first)
3) Static analysis: decompile APK with jadx; grep for API endpoints, MQTT broker addresses, authentication patterns
4) DNS analysis: identify cloud endpoints (likely *.electrolux.com or similar); check for local API fallback
5) If BLE provisioning exists: capture HCI snoop log during device setup flow

## Protocol hypotheses (to validate)
- Cloud transport: likely MQTT over TLS to Electrolux/AWS IoT broker, or HTTPS REST API
- Authentication: OAuth2 or API key via Electrolux account; device likely uses certificate or token-based auth
- Command encoding: likely JSON payloads (MQTT or REST); could be protobuf
- Local API: may not exist — many Electrolux devices are cloud-only; check for local HTTP server on device IP
- Provisioning: app likely uses BLE or SoftAP to send WiFi credentials to device during setup

## Control surface inventory (what the replacement app must support)

### Onboarding/pairing UX
- WiFi provisioning (send SSID + password to device)
- Device registration / naming

### Core controls (MVP)
- Power on/off
- Mode: Cool, Eco (Energy Saver), Fan Only
- Temperature setpoint: 60-90°F (16-32°C), 1°F increments
- Fan speed: Auto, Low, Medium, High
- Current room temperature (read-only)

### Extended controls
- Timer: on/off, 0.5-24 hours
- Sleep mode: on/off
- Display: on/off (brightness dimming)
- Filter alert status (read-only binary sensor)
- Filter reset command

### Model-specific controls
- **Gallery models**: Clean Air / Ionizer toggle
- **Portable models**: Dehumidify mode, drain-full indicator (binary sensor)

### Error handling and recovery
- WiFi reconnection after network interruption
- Compressor delay timer awareness (cannot restart compressor immediately after power cycle)
- Filter maintenance reminders

### Settings persistence
- Schedule programming (if supported by protocol)
- Temperature unit preference (°F / °C)

## Evidence checklist
- [ ] APK hash + version code
- [ ] APK decompilation output (jadx)
- [ ] Network capture (mitmproxy / PCAP) during app-to-cloud communication
- [ ] MQTT broker address + topic structure (if applicable)
- [ ] REST API endpoints (if applicable)
- [ ] HCI snoop log during provisioning (if BLE used)
- [ ] Screenshots of app UI for each control (do not commit proprietary assets)

## Spec output (clean-room)
Write derived specs in:
- `device-specs/devices/frigidaire-window-ac.yaml`
- `device-specs/devices/frigidaire-portable-ac.yaml`
- `docs/devices/frigidaire-ac.md`

Include message formats, topic/endpoint structures, payload examples, and entity mappings.

## References (URLs only)
- https://www.frigidaire.com/owner-center/connect/
- https://play.google.com/store/apps/details?id=com.electrolux.oneapp.frigidaire
