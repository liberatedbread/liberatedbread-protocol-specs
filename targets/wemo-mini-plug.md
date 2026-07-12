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
- VERIFIED: pywemo Python library provides local control (source: pywemo/pywemo, NOT pavoni/pywemo)
- HomeKit-enabled models retain local control via HomeKit
- Non-HomeKit models at risk without local RE
- VERIFIED: Discovery is SSDP/UPnP, NOT mDNS. There is no `_wemo._tcp` service
  (that earlier guess was wrong and has been dropped). M-SEARCH goes to the
  SSDP multicast group `239.255.255.250:1900`.
- VERIFIED: UPnP deviceType `urn:Belkin:device:controllee:1` (Mini plug);
  SSDP search-target URN `urn:Belkin:service:basicevent:1` (source: pywemo)
- Also relevant: Wemo WiFi Smart Dimmer, Smart Light Switch, Insight Switch
- Existing RE: pywemo/pywemo, iancmcc/ouimeaux
- Structured spec: `device-specs/devices/wemo-mini-plug.yaml`

## Device discovery signals
- Wi-Fi (SSDP / UPnP — this is the discovery path; there is NO mDNS):
  - SSDP M-SEARCH: multicast group `239.255.255.250:1900`, MAN `"ssdp:discover"`,
    MX `1`, ST `urn:Belkin:service:basicevent:1`
    (alternates that also match: `ssdp:all`, `urn:Belkin:device:controllee:1`)
  - SSDP reply: `LOCATION` header → `http://<ip>:<port>/setup.xml`;
    `USN` → `uuid:Socket-1_0-<serial>::urn:Belkin:service:basicevent:1`
  - setup.xml port behavior: port is NOT stable — it drifts across 49152-49159.
    Probe 49153 first, then 49152, 49154, 49151, 49155-49159
    (pywemo `PROBE_PORTS`); re-probe after the device reconnects / changes IP.
  - setup-AP SSID: factory-reset device broadcasts SSID prefix `WeMo.Setup.`
    (app provisions home WiFi via SOAP: GetApList / ConnectHomeNetwork)
  - mDNS service types: N/A — Wemo does not use mDNS/Bonjour
  - UPnP deviceType (from setup.xml): `urn:Belkin:device:controllee:1` (plug);
    others in the family — `:insight:1`, `:dimmer:1`, `:lightswitch:1`, `:bridge:1`

## Threat model + guardrails
- Scope: only owned devices, no safety-critical use cases.
- Smart plug controls power — avoid safety-critical loads.

## First experiments (do these first)
1) Run ./scripts/detect_devices.sh; attach log paths.
2) Fetch APK (apkeep) for com.belkin.wemoandroid.
3) Static: grep for UPnP/SOAP endpoints and command formats.
4) Dynamic: capture one "discover + toggle on/off" PCAP on local network.

## Protocol hypotheses (to validate)
- Pairing/bonding steps: WiFi provisioning via `WeMo.Setup.` AP (VERIFIED — pywemo api/wifi_setup.py)
- Session state machine: UPnP SSDP discovery -> GET /setup.xml -> SOAP action calls (VERIFIED)
- Commands (VERIFIED SOAP actions, SOAP 1.1 POST): basicevent →
  `SetBinaryState` (BinaryState=1/0) and `GetBinaryState` on
  `/upnp/control/basicevent1`; insight → `GetInsightParams` on
  `/upnp/control/insight1` (Insight models only). Each requires a
  `SOAPACTION: "<serviceType>#<Action>"` header. Async state via UPnP
  SUBSCRIBE to `/upnp/event/basicevent1`.
- Payload encoding: XML/SOAP over HTTP (VERIFIED from pywemo architecture)
- Timing constraints: SSDP multicast for discovery; MX 1 second response window

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
- https://github.com/pywemo/pywemo
- https://github.com/pywemo/pywemo/blob/main/pywemo/ssdp.py
- https://github.com/pywemo/pywemo/tree/main/pywemo/ouimeaux_device
- https://github.com/pywemo/pywemo/tree/main/pywemo/ouimeaux_device/api/xsd
- https://github.com/pywemo/pywemo/blob/main/pywemo/ouimeaux_device/api/wifi_setup.py
- https://www.home-assistant.io/integrations/wemo/
- https://github.com/home-assistant/core/tree/dev/homeassistant/components/wemo
- https://github.com/iancmcc/ouimeaux
