# Belkin Wemo Mini Smart Plug

> **Status**: Research
> **Protocol**: WiFi (UPnP/SOAP, local LAN)
> **Manufacturer**: Belkin
> **Manufacturer Status**: Shutdown (Wemo cloud + app account features end 2026-01-31 — local UPnP control survives)

## Overview

The Belkin Wemo Mini Smart Plug is the OpenGreenIoT project's **first WiFi device
spec**. Unlike the cloud-dependent Frigidaire ACs, a Wemo plug is fully
controllable on the local LAN with **no cloud**: discovery is UPnP/SSDP and
control is SOAP 1.1 over HTTP. That is exactly why it is a good rescue target —
Belkin has announced the Wemo cloud shutdown (app and account features end
January 31, 2026), but on/off and state continue to work locally afterward.

The same protocol covers the wider Wemo family (Insight Switch, Light Switch,
Dimmer, Bridge), which differ by UPnP `deviceType` and service list. The mature
[pywemo](https://github.com/pywemo/pywemo) library and the
[Home Assistant Wemo integration](https://www.home-assistant.io/integrations/wemo/)
both implement this protocol.

Structured spec: [`device-specs/devices/wemo-mini-plug.yaml`](https://github.com/PigsCanFlyLabs/opengreeniot-protocol-docs/blob/main/device-specs/devices/wemo-mini-plug.yaml).

## Hardware

| Property | Value |
|----------|-------|
| Models | Wemo Mini Smart Plug (F7C063), Wemo WiFi Smart Plug V2 (WSP080) |
| Radio | WiFi 802.11 b/g/n (2.4 GHz) |
| Transport | UPnP / SOAP over HTTP on the local LAN |
| Power metering | No (Insight-class devices only) |
| Chipset | TBD |
| FCC ID | TBD |

## Protocol Summary

### Architecture

```
┌──────────────┐   SSDP M-SEARCH (UDP 239.255.255.250:1900)   ┌──────────────┐
│  Controller  │─────────────────────────────────────────────►│  Wemo Plug   │
│  (HA/pywemo) │◄────── LOCATION: http://<ip>:<port>/setup.xml─│  (WiFi SoC)  │
│              │                                               │              │
│              │──── GET /setup.xml (device description) ─────►│              │
│              │──── SOAP POST /upnp/control/basicevent1 ─────►│  relay       │
│              │◄─── UPnP eventing (SUBSCRIBE /upnp/event/…) ──│              │
└──────────────┘                                               └──────────────┘
```

### Discovery (SSDP / UPnP — **not** mDNS)

Wemo does **not** advertise over mDNS/Bonjour. Discovery is SSDP:

- **M-SEARCH** (HTTP-over-UDP) to multicast group `239.255.255.250:1900`
  - `MAN: "ssdp:discover"`, `MX: 1`
  - `ST: urn:Belkin:service:basicevent:1`
    (alternates that also match: `ssdp:all`, `urn:Belkin:device:controllee:1`)
- **Reply** carries `LOCATION: http://<ip>:<port>/setup.xml` and
  `USN: uuid:Socket-1_0-<serial>::urn:Belkin:service:basicevent:1`

!!! warning "Port is not stable"
    The Wemo HTTP port drifts across **49152-49159** and can change after the
    device reconnects. Probe `49153` first, then `49152, 49154, 49151,
    49155-49159` (pywemo `PROBE_PORTS`), and re-probe after a reconnect.

`GET /setup.xml` returns the UPnP device description: `deviceType`
(`urn:Belkin:device:controllee:1` for the plug; `:insight:1`, `:dimmer:1`,
`:lightswitch:1`, `:bridge:1` for other models), `friendlyName`, `UDN`,
`serialNumber`, `macAddress`, `modelName`/`modelNumber`, and the `serviceList`.

### Control (SOAP 1.1 over HTTP)

Every control call is a SOAP `POST` with two required headers:

- `Content-Type: text/xml; charset="utf-8"`
- `SOAPACTION: "<serviceType>#<Action>"`

| Service | Path | Action (SOAPACTION) | Purpose |
|---------|------|---------------------|---------|
| basicevent | `/upnp/control/basicevent1` | `urn:Belkin:service:basicevent:1#SetBinaryState` | Set relay: `BinaryState` = 1 (on) / 0 (off) |
| basicevent | `/upnp/control/basicevent1` | `urn:Belkin:service:basicevent:1#GetBinaryState` | Read current relay state |
| insight | `/upnp/control/insight1` | `urn:Belkin:service:insight:1#GetInsightParams` | Power/energy telemetry (Insight models only) |

`SetBinaryState` and `GetBinaryState` share the **same path** and are told apart
**only by the SOAPACTION header**. Asynchronous state changes are delivered via
UPnP eventing — `SUBSCRIBE` to each service's `eventSubURL`
(e.g. `/upnp/event/basicevent1`).

### Setup / Provisioning

A factory-reset device broadcasts a WiFi AP with SSID prefix `WeMo.Setup.`. The
app joins that AP and provisions home WiFi through the same SOAP surface
(`GetApList`, `ConnectHomeNetwork` — see pywemo `api/wifi_setup.py`).

### Hybrid Cloud (reference only)

Static analysis of `com.belkin.wemoandroid` shows remote/account features use
`api.xwemo.com:8443` / `appapis.xwemo.com:8443`, Firebase
(`productionwemoandroidpn.firebaseio.com`) for push, and AWS IoT. These are the
services affected by the shutdown; a local-only client does not need them.

## Home Assistant Entities

| Entity | Platform | Device Class | Notes |
|--------|----------|-------------|-------|
| Smart Plug | `switch` | `outlet` | On/off via SetBinaryState; state via GetBinaryState |
| Power | `sensor` | `power` | **Insight models only** — GetInsightParams `instantpower`; not on the Mini |

## Schema Gaps (flagged for maintainers)

The structured spec validates against `device-specs/schema.json`, but the WiFi/UPnP
model exposed three gaps. **The schema was intentionally not modified**; these are
documented in the YAML's `notes` and header comment for a human to resolve:

1. **No SSDP fields in `identification`** — nowhere to record the multicast target
   `239.255.255.250:1900`, the M-SEARCH ST URN `urn:Belkin:service:basicevent:1`,
   or the UPnP `deviceType`. `mdns_service_type` is left null because Wemo is
   SSDP-only. All SSDP facts live in `notes` + the `/setup.xml` endpoint.
2. **`default_port` is a single integer** — but the port drifts 49152-49159. We
   record `49153` and document the probe list in `notes`. A `port_probe_list`
   array would fit better.
3. **`http_endpoints` has no `headers` field** — the mandatory `SOAPACTION` header
   and service-type XML namespace live in each endpoint's `description`, and
   Set/GetBinaryState share one path disambiguated only by SOAPACTION.

## Tools Used

- [x] pywemo reference implementation (protocol source of truth)
- [x] jadx — static analysis of `com.belkin.wemoandroid` (cloud endpoints)
- [ ] Wireshark — capture a live discover + toggle exchange
- [ ] mitmproxy — inspect the hybrid-cloud account flow

## References

- [pywemo/pywemo](https://github.com/pywemo/pywemo) — Python local-control library
- [pywemo ssdp.py](https://github.com/pywemo/pywemo/blob/main/pywemo/ssdp.py) — discovery + port probing
- [pywemo ouimeaux_device](https://github.com/pywemo/pywemo/tree/main/pywemo/ouimeaux_device) — device/service classes
- [pywemo api/xsd](https://github.com/pywemo/pywemo/tree/main/pywemo/ouimeaux_device/api/xsd) — service/device URN constants
- [pywemo api/wifi_setup.py](https://github.com/pywemo/pywemo/blob/main/pywemo/ouimeaux_device/api/wifi_setup.py) — provisioning
- [Home Assistant Wemo integration](https://www.home-assistant.io/integrations/wemo/)
- [home-assistant/core wemo component](https://github.com/home-assistant/core/tree/dev/homeassistant/components/wemo)
- [iancmcc/ouimeaux](https://github.com/iancmcc/ouimeaux) — earlier reverse-engineering library

## Contributors

- OpenGreenIoT community — initial WiFi target spec (first WiFi device documented)
