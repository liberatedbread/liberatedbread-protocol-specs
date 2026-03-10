# Target: Sengled WiFi Smart Bulb

## Target metadata
- target_id: sengled-wifi-bulb
- app package_id(s): com.sengled.app2
- device class: WiFi smart bulb
- transport(s): Wi-Fi LAN
- local-only viability: low without RE — cloud-dependent WiFi bulbs; Zigbee models work locally

## Known facts (public + observed)
- Sengled WiFi Smart Bulb A19, BR30, Smart LED Strip
- Price: $8-15 per bulb
- Company in financial crisis since January 2025 (employees unpaid)
- Alexa skill shut down August 2025
- WiFi models are cloud-locked — no local control without RE
- Zigbee models work locally with Home Assistant/Zigbee controllers
- Cloud shutdown imminent given company financial status

## Device discovery signals
- Wi-Fi:
  - SSID patterns: TBD (provisioning mode)
  - default gateway IPs: N/A (joins home network)
  - mDNS service types: TBD
  - UPnP URNs / LOCATION: TBD

## Threat model + guardrails
- Scope: only owned devices, no safety-critical use cases.
- Light bulb only — no safety risk.

## First experiments (do these first)
1) Run ./scripts/detect_devices.sh; attach log paths.
2) Fetch APK (apkeep) for com.sengled.app2.
3) Static: grep for API endpoints, local discovery protocol, command format.
4) Dynamic: PCAP of one "toggle on/off" command on local network.

## Protocol hypotheses (to validate)
- Pairing/bonding steps: WiFi provisioning via app
- Session state machine: TBD from APK analysis
- Commands: on/off, brightness, color temperature, color (RGB on supported models)
- Payload encoding: likely JSON/HTTP or proprietary binary
- Timing constraints: TBD

## Control surface inventory (what the replacement app must support)
- Onboarding/pairing UX: WiFi provisioning
- Core controls (MVP): on/off, brightness
- Power / brightness / modes / uploads: color temperature, RGB color
- Error handling and recovery: reconnect after WiFi drop
- Settings persistence: device retains last state

## Evidence checklist
- APK hashes + version code: TBD
- PCAP logs: TBD

## Spec output (clean-room)
Write a derived spec in:
- docs/specs/sengled-wifi-bulb.md

## References (URLs only)
- https://www.sengled.com
