# Target: Belkin Wemo Mini Smart Plug

## Target metadata
- target_id: wemo-mini-plug
- app package_id(s): com.belkin.wemoandroid
- device class: WiFi smart plug
- transport(s): Wi-Fi LAN
- local-only viability: high — pywemo/ouimeaux Python libraries exist for local LAN control

## Known facts (public + observed)
- Belkin Wemo Mini Smart Plug (F7C063) and Wemo Smart Plug V2 (WSP080)
- Price: $15-25
- Cloud shutdown announced for January 31, 2026 — devices being abandoned
- HomeKit-enabled models retain local control via HomeKit
- Non-HomeKit models become cloud-dependent bricks without RE
- Uses UPnP/SOAP protocol on local network
- Existing RE: pywemo, ouimeaux Python libraries
- Also relevant: Wemo WiFi Smart Dimmer, Wemo Smart Light Switch, Wemo Insight Switch

## Device discovery signals
- Wi-Fi:
  - SSID patterns: "WeMo.Setup.XXX" (during setup)
  - default gateway IPs: N/A (joins home network)
  - mDNS service types: _wemo._tcp
  - UPnP URNs / LOCATION: urn:Belkin:device:controllee:1

## Threat model + guardrails
- Scope: only owned devices, no safety-critical use cases.
- Smart plug controls power to connected device — avoid safety-critical loads.

## First experiments (do these first)
1) Run ./scripts/detect_devices.sh; attach log paths.
2) Fetch APK (apkeep) for com.belkin.wemoandroid.
3) Static: grep for UPnP/SOAP endpoints and command formats.
4) Dynamic: capture one "discover + toggle on/off" PCAP on local network.

## Protocol hypotheses (to validate)
- Pairing/bonding steps: WiFi provisioning via WeMo.Setup AP, then joins home network
- Session state machine: UPnP discovery → SOAP action calls
- Commands: on/off toggle, get state, get power consumption (Insight model)
- Payload encoding: XML/SOAP over HTTP
- Timing constraints: UPnP SSDP multicast for discovery

## Control surface inventory (what the replacement app must support)
- Onboarding/pairing UX: WiFi AP provisioning flow
- Core controls (MVP): on/off, get current state
- Power / brightness / modes / uploads: energy monitoring (Insight), dimmer level (Dimmer)
- Error handling and recovery: device rediscovery after IP change
- Settings persistence: device retains state across power cycles

## Evidence checklist
- APK hashes + version code: TBD
- PCAP logs: TBD

## Spec output (clean-room)
Write a derived spec in:
- docs/specs/wemo-mini-plug.md

## References (URLs only)
- https://github.com/pavoni/pywemo
- https://github.com/iancmcc/ouimeaux
