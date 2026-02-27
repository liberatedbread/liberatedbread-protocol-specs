# CHEF iQ Sense devices — target spec starter

## Target metadata
- target_id: chef-iq-sense
- app package_id(s): com.chefman.chefiq.prod
- device class: smart thermometer / cooking appliances
- transport(s): Wi-Fi + Bluetooth (per app listing)
- local-only viability: medium/unknown (verify offline BLE-only operation)

## Known facts (public)
- App listing describes a "SMART THERMOMETER" with "unlimited range connectivity over Wi‑Fi and Bluetooth".
- App includes community/recipes and integrations; these may imply cloud traffic.

## Device discovery signals (hypotheses)
- BLE: hub/base station likely advertises; probes may be separate radios.
- Wi-Fi: base station may join home Wi-Fi; may use local LAN + cloud.

## First experiments
1) Run ./scripts/detect_devices.sh with the hub/base powered.
2) Offline tests (highly informative):
   - Phone in airplane mode (Bluetooth on), can you still read sensors?
   - Router unplugged, can you still read sensors?
3) Capture:
   - BLE HCI snoop for connect + read temps.
   - Wi-Fi PCAP (tcpdump) while doing onboarding to see whether traffic is LAN-local or cloud-only.
4) Static APK scan:
   - search for mDNS/SSDP usage
   - search for MQTT/WebSockets/GRPC
   - identify certificate pinning early

## Replacement app MVP
- connect + show temps reliably
- configurable alerts
- no account requirement for core thermometer functionality (if feasible)

## References
- https://play.google.com/store/apps/details?id=com.chefman.chefiq.prod
