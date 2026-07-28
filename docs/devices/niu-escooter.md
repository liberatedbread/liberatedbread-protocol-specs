# NIU Electric Scooter

> **Status**: Research
> **Protocol**: Cloud HTTP API (documented) + BLE (undocumented)
> **Manufacturer**: Niu Technologies
> **Manufacturer Status**: Active, **cloud-dependent**

## Overview

NIU scooters report telemetry — battery state, position, odometer, ride history — through
NIU's cloud. The companion app (`com.niu.manager`) authenticates against NIU's account
service, receives an OAuth2 token, and reads everything back from NIU's servers. The
scooter also has a BLE link the app uses when it is next to the bike.

This one is on the registry for the reason the project exists: **if NIU turns the service
off, the app stops working, and every documented data path goes with it.** Per the
project's scope rules, cloud-only devices are documented and deprioritised — so this page
records the cloud dependency accurately, and names the local path as the gap worth closing.

!!! warning "The documented API is the dependency, not the escape from it"
    Everything below runs through NIU's servers. It is genuinely useful today — it is what
    the Home Assistant integrations use — but it is not local control, and it does not
    survive the service being retired. **The BLE link is the local-first target and it is
    not publicly documented.** Closing that gap is the actual work here.

## Hardware

| Property | Value |
|----------|-------|
| Models | N/M/U/G series (varies by market) |
| App | `com.niu.manager` (Android) |
| Radios | Cellular (scooter → NIU cloud), BLE (scooter ↔ phone) |
| Battery | Removable; single- and dual-battery variants differ in API shape |

## Cloud API

### Hosts

| Constant | Value |
|----------|-------|
| Account service | `https://account-fk.niu.com` |
| API service | `https://app-api-fk.niu.com` |

The `-fk` hosts are the ones current integrations use; older captures show
`app-api.niu.com`. Hosts appear to be region-dependent — confirm against your own account
rather than assuming.

### Authentication

| Item | Value |
|------|-------|
| Path | `POST /v3/api/oauth2/token` (on the account host) |
| Scheme | OAuth2 → bearer token |
| Credentials | The owner's own NIU app account |
| Scope | Most data calls also need the scooter's serial number (`sn`) |

### Endpoints

| Path | Returns |
|------|---------|
| `/v5/scooter/list` | Scooters on the account, with serial numbers |
| `/v5/scooter/motor_data/index_info` | Main telemetry — state of charge, position, odometer |
| `/v3/motor_data/battery_info` | Battery detail (dual-battery models report per-pack) |
| `/motoinfo/overallTally` | Lifetime totals |
| `/v5/track/list/v2` | Ride/track history |

Note the mixed versioning: telemetry and listing moved to `v5` while battery detail is
still `v3`. Both are live — this is the API's actual shape, not a transcription slip.

### Verification

`reported`. Hosts and paths are taken from a maintained Home Assistant integration and
corroborated by independent captures, but none have been exercised by us. The original
API capture work explicitly covers **dual-battery scooters only**; single-battery models
may differ in response shape.

!!! note "Credentials and tokens"
    A token is tied to the owner's account and grants access to their scooter — including
    its live location. Capture tokens only from your own account, never commit one, and
    treat a captured token like a password. Nothing in this repo should carry a real token
    or serial number.

## BLE — the gap

The app talks to the scooter directly over BLE when in range, and this is the path that
would still work with the cloud gone. It is not publicly documented: no service or
characteristic UUIDs, no framing, no pairing flow.

Prior work exists on adjacent scooters — Ninebot/Segway's BLE protocol has been reverse
engineered independently — but nothing transfers without a capture. This is the highest
value experiment on this page:

1. Scan a powered scooter with nRF Connect; record advertised name, address, service and
   characteristic UUIDs.
2. Enable Android HCI snoop logging and capture the app performing one connect plus one
   simple action.
3. Establish whether the BLE link is a full control channel or only a proximity/unlock
   handshake with everything else deferred to the cloud. That answer decides whether local
   control is achievable at all.

## No device spec YAML yet

The schema's `http_endpoints` is for **local** HTTP on Wi-Fi devices. Writing NIU's cloud
endpoints into it would tell every consumer that this is a locally-controllable device when
the opposite is true — the whole point of the entry is that control is remote. A spec
becomes honest once the BLE link is characterised, at which point it is an ordinary
`services` block.

## Tools Used

- [ ] nRF Connect — BLE scan and GATT enumeration
- [ ] Android HCI snoop log (`btsnoop_hci.log`) — app connect + one action
- [ ] mitmproxy — cloud API inspection, against your own account only

## References

- [Bonnee/niu-app-api — cloud API reverse engineering (dual-battery)](https://github.com/Bonnee/niu-app-api)
- [marcelwestrahome/home-assistant-niu-component — maintained HA integration](https://github.com/marcelwestrahome/home-assistant-niu-component)
- [cascha42/niu-info — shell client against the same API](https://github.com/cascha42/niu-info)
- [ub4raf/Ninebot-PROTOCOL — adjacent scooter BLE protocol, for comparison](https://github.com/ub4raf/Ninebot-PROTOCOL)
- [NIU app on Google Play (`com.niu.manager`)](https://play.google.com/store/apps/details?id=com.niu.manager)

## Contributors

- Initial research — hosts and endpoint paths transcribed from public integrations; not
  exercised against a live account, and no BLE capture taken.
