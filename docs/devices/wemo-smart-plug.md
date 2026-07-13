# Belkin Wemo Smart Plug

> **Status**: In Progress — spec created from pywemo + APK widget mock analysis; PCAP validation pending
> **Protocol**: WiFi (SSDP/UPnP + SOAP 1.1 over HTTP)
> **Manufacturer**: Belkin
> **Manufacturer Status**: Shutdown (Wemo cloud ends 2026-01-31; local control survives shutdown)

## Overview

The Belkin Wemo Smart Plug family — Mini (F7C063), Smart Plug V2 (WSP080), and
original Smart Plug — are WiFi-connected smart plugs that communicate via UPnP
over the local network. They use SSDP multicast for discovery and SOAP 1.1 over
HTTP for control. No cloud dependency is required for basic on/off and state
reading, which makes them a prime rescue target after Belkin's announced Wemo
cloud shutdown (January 2026).

This is the first UPnP/SOAP device type in the OpenGreenIoT project, and the
first to span a large ecosystem — over 16 distinct Wemo device types share the
same protocol (plugs, switches, dimmers, energy monitors, sensors, bridges, and
even kitchen/environmental appliances). See `targets/wemo-devices.md` for the
full device-type family catalog.

Multiple open-source implementations exist as reference: pywemo (Python), Home
Assistant's Wemo integration, and the ouimeaux library. The APK for the official
Wemo Android app has been downloaded and decoded, providing detailed mock data
for all 16+ device types.

## Hardware

| Property | Value |
|----------|-------|
| Models | F7C063 (Mini), WSP080 (Smart Plug V2), original Smart Plug |
| Radio | WiFi 802.11 b/g/n (2.4 GHz) |
| Chipset | TBD (likely Ralink/Mediatek — extract from FCC filing) |
| FCC ID | TBD |
| Ports | NEMA 5-15R (120V/15A) |
| Dimensions | ~4" × 2" × 1.5" (varies by model) |
| MSRP | $15–25 |
| Setup | `WeMo.Setup.` WiFi AP for provisioning |

## WiFi Discovery

| Property | Value |
|----------|-------|
| Protocol | SSDP (UPnP) — NOT mDNS |
| Multicast Group | `239.255.255.250:1900` |
| M-SEARCH ST URN | `urn:Belkin:service:basicevent:1` |
| Alternate ST URNs | `ssdp:all`, `urn:Belkin:device:controllee:1`, `urn:Belkin:device:socket:1` |
| LOCATION | `http://<ip>:<port>/setup.xml` |
| UPnP DeviceType (Mini) | `urn:Belkin:device:controllee:1` |
| UPnP DeviceType (V2) | `urn:Belkin:device:socket:1` |
| HTTP Port | 49152–49159 (not fixed; probe 49153 first) |
| Reconnect Behavior | Port may change after reconnect; re-probe required |

### Related Devices (same protocol family)

See `targets/wemo-devices.md` for the full 16+ device type catalog. Key
expansion targets:

| Device | deviceType URN | Phase |
|--------|---------------|-------|
| Wemo Insight Switch (F7C029) | `urn:Belkin:device:insight:1` | Phase 2 |
| Wemo Light Switch (1st/2nd/3-way) | `urn:Belkin:device:Lightswitch:1` | Phase 3 |
| Wemo Dimmer (F7C059) | `urn:Belkin:device:dimmer:1` | Phase 3 |
| Wemo Bridge | `urn:Belkin:device:bridge:1` | Phase 3 |
| Wemo Maker | `urn:Belkin:device:Maker:1` | Phase 4 |
| Wemo Motion | `urn:Belkin:device:motion:1` | Phase 4 |
| Wemo Outdoor Plug | `urn:Belkin:device:outdoor:1` | Phase 4 |

## Protocol Summary

### Discovery Flow

1. **SSDP M-SEARCH**: Client sends HTTPMU multicast to `239.255.255.250:1900`
   with `MAN: "ssdp:discover"` and `ST: urn:Belkin:service:basicevent:1`
2. **SSDP Response**: Wemo device responds with unicast UDP containing
   `LOCATION: http://<ip>:<port>/setup.xml` and
   `USN: uuid:Socket-1_0-<serial>::urn:Belkin:service:basicevent:1`
3. **Device Description**: Client HTTP GETs the LOCATION URL to fetch
   `/setup.xml` — a UPnP device description XML containing:
   - `deviceType`, `friendlyName`, `UDN`, `serialNumber`, `macAddress`,
     `modelName`, `modelNumber`, `manufacturer`
   - `<serviceList>` with controlURL and eventSubURL for each service
4. **Port instability**: If 49153 doesn't respond, probe 49152, 49154, 49151,
   then 49155–49159 sequentially (pywemo `PROBE_PORTS` order)
5. **Ready**: Device is ready for SOAP control calls

### SOAP Control

All control uses SOAP 1.1 over HTTP POST. Two headers are critical:

```
Content-Type: text/xml; charset="utf-8"
SOAPACTION: "<serviceType>#<Action>"
```

#### SOAP Services

| Service | Service URN | Control URL | Actions | Notes |
|---------|------------|-------------|---------|-------|
| **basicevent** | `urn:Belkin:service:basicevent:1` | `/upnp/control/basicevent1` | SetBinaryState, GetBinaryState | On/off control — universal |
| **insight** | `urn:Belkin:service:insight:1` | `/upnp/control/insight1` | GetInsightParams, SetPowerThreshold, GetPowerThreshold | Insight models only |
| **metainfo** | `urn:Belkin:service:metainfo:1` | `/upnp/control/metainfo1` | GetMetaInfo | Device metadata |
| **timesync** | `urn:Belkin:service:timesync:1` | `/upnp/control/timesync1` | TimeSync | Set device clock |
| **deviceinf** | `urn:Belkin:service:deviceinf:1` | `/upnp/control/deviceinf1` | GetDeviceInformation | Model/serial/MAC |
| **WiFi setup** | `urn:Belkin:service:WiFiSetup:1` | `/upnp/control/wifi1` | GetApList, ConnectHomeNetwork | Provisioning only |

#### Async Events (UPnP Eventing)

The device pushes state changes by accepting UPnP SUBSCRIBE requests on each
service's `eventSubURL`:

| Service | Event URL | Events |
|---------|-----------|--------|
| basicevent | `/upnp/event/basicevent1` | BinaryState change |
| insight | `/upnp/event/insight1` | Power/energy updates |

### Commands

#### ON — SetBinaryState(1)

**SOAPACTION**: `"urn:Belkin:service:basicevent:1#SetBinaryState"`

**SOAP Body**:
```xml
<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"
            s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
  <s:Body>
    <u:SetBinaryState xmlns:u="urn:Belkin:service:basicevent:1">
      <BinaryState>1</BinaryState>
    </u:SetBinaryState>
  </s:Body>
</s:Envelope>
```

**Response**: `<BinaryState>1</BinaryState>` (or `Error` on failure)

#### OFF — SetBinaryState(0)

Same as ON but `<BinaryState>0</BinaryState>`.

#### STATE — GetBinaryState

**SOAPACTION**: `"urn:Belkin:service:basicevent:1#GetBinaryState"`

**Response**: `<BinaryState>0</BinaryState>` or `<BinaryState>1</BinaryState>`

#### INSIGHT — GetInsightParams (Insight models only)

**SOAPACTION**: `"urn:Belkin:service:insight:1#GetInsightParams"`

**Response**: Colon-delimited string with power/energy data:

```
<InsightParams>1|1234567890|3600|7200|86400|60|120.5|500000|2500|15000|...</InsightParams>
```

Fields (from pywemo): `state` | `lastchange` | `onfor_seconds` | `ontoday_seconds`
| `ontotal_seconds` | `timeperiod` | `averagepower` | `instantpower_mW` |
`energytoday` | `energytotal` | `powerthreshold`

### Error Handling

- **SOAP Fault**: Standard SOAP fault envelope on invalid actions
- **HTTP Error**: Standard HTTP error codes (404, 500)
- **BinaryState Error**: Device may respond with `Error` string instead of 0/1
- **Timeout**: Port may have changed — re-probe the full port range

### WiFi Provisioning (Reference)

1. Factory-reset device broadcasts SSID `WeMo.Setup.XXXX`
2. App connects to this AP
3. App sends `GetApList` to discover available home WiFi networks
4. User selects network and provides password
5. App sends `ConnectHomeNetwork` with SSID and password
6. Device reboots and connects to home WiFi

Note: Provisioning is NOT in scope for the local-control MVP. The device is
assumed to already be on the home LAN.

## Tools Used

- [x] apkeep — APK download (v0.18.0, source: APKPure)
- [x] apktool — APK decoding (smali, assets, widget mocks)
- [x] `scripts/wemo_discover.py` — SSDP M-SEARCH discovery tool
- [x] `scripts/wemo_control.py` — SOAP command builder (dry-run mode)
- [x] pywemo — Reference implementation (github.com/pywemo/pywemo)
- [ ] Wireshark — PCAP capture of discovery + control cycle
- [ ] `scripts/run_static_target.sh` — SSDP pattern grepping

## References

- [pywemo: Python Wemo library](https://github.com/pywemo/pywemo)
- [pywemo SSDP module](https://github.com/pywemo/pywemo/blob/main/pywemo/ssdp.py)
- [pywemo device implementations](https://github.com/pywemo/pywemo/tree/main/pywemo/ouimeaux_device)
- [pywemo XSD schemas](https://github.com/pywemo/pywemo/tree/main/pywemo/ouimeaux_device/api/xsd)
- [pywemo WiFi setup](https://github.com/pywemo/pywemo/blob/main/pywemo/ouimeaux_device/api/wifi_setup.py)
- [Home Assistant Wemo integration](https://www.home-assistant.io/integrations/wemo/)
- [Home Assistant Wemo source](https://github.com/home-assistant/core/tree/dev/homeassistant/components/wemo)
- [ouimeaux: alternative Python Wemo library](https://github.com/iancmcc/ouimeaux)

## Contributors

- OpenGreenIoT community — APK static analysis, device spec, discovery/control tooling
