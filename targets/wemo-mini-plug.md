# Target: Belkin Wemo Mini Smart Plug

## Target metadata
- target_id: wemo-mini-plug
- app package_id(s): com.belkin.wemoandroid
- device class: WiFi smart plug
- transport(s): Wi-Fi LAN
- local-only viability: high — UPnP/SOAP protocol on local LAN; pywemo library exists

## Known facts (verified from RE sources)
- Belkin Wemo Mini Smart Plug (F7C063) and Wemo Smart Plug V2 (WSP080)
- Price: $15-25
- VERIFIED: Cloud shutdown announced for January 31, 2026 (news reports)
- VERIFIED: Uses UPnP/SOAP protocol on local network
- VERIFIED: SSDP multicast discovery on local LAN
- VERIFIED: pywemo Python library provides local control (source: home-assistant-libs/pywemo, NOT pavoni/pywemo)
- HomeKit-enabled models retain local control via HomeKit
- Non-HomeKit models at risk without local RE
- TBD — needs verification: mDNS service type "_wemo._tcp" (speculative, may use UPnP SSDP only)
- TBD — needs verification: UPnP URN "urn:Belkin:device:controllee:1" (plausible but unconfirmed)
- Also relevant: Wemo WiFi Smart Dimmer, Smart Light Switch, Insight Switch
- Existing RE: home-assistant-libs/pywemo, iancmcc/ouimeaux

## Device discovery signals
- Wi-Fi:
  - SSID patterns: "WeMo.Setup.XXX" (during setup) — TBD, needs verification
  - default gateway IPs: N/A (joins home network)
  - mDNS service types: TBD — _wemo._tcp is speculative
  - UPnP URNs / LOCATION: TBD — needs verification from pywemo source

## Threat model + guardrails
- Scope: only owned devices, no safety-critical use cases.
- Smart plug controls power — avoid safety-critical loads.

## First experiments (do these first)
1) Run ./scripts/detect_devices.sh; attach log paths.
2) Fetch APK (apkeep) for com.belkin.wemoandroid.
3) Static: grep for UPnP/SOAP endpoints and command formats.
4) Dynamic: capture one "discover + toggle on/off" PCAP on local network.

## Protocol hypotheses (to validate)
- Pairing/bonding steps: WiFi provisioning via WeMo.Setup AP (TBD — needs verification)
- Session state machine: UPnP SSDP discovery -> SOAP action calls (VERIFIED)
- Commands: on/off toggle, get state, energy monitoring (Insight) — TBD exact SOAP actions
- Payload encoding: XML/SOAP over HTTP (VERIFIED from pywemo architecture)
- Timing constraints: SSDP multicast for discovery

## Control surface inventory (what the replacement app must support)
- Onboarding/pairing UX: WiFi AP provisioning flow
- Core controls (MVP): on/off, get current state
- Power / brightness / modes / uploads: energy monitoring (Insight), dimmer (Dimmer)
- Error handling and recovery: device rediscovery after IP change
- Settings persistence: device retains state across power cycles

## Evidence checklist
- APK hashes + version code: TBD
- PCAP logs: TBD

## Spec output (clean-room)
Write a derived spec in:
- docs/specs/wemo-mini-plug.md

## References (URLs only)
- https://github.com/home-assistant-libs/pywemo
- https://github.com/iancmcc/ouimeaux
