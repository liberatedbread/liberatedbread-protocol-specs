# HomeWizard P1 Meter (HWE-P1)

> **Status**: Spec Available; official API, untested here
> **Protocol**: Wi-Fi — local HTTP v1 and HTTPS v2
> **Manufacturer**: HomeWizard
> **Manufacturer Status**: Active

## Overview

The HomeWizard P1 Meter reads a compatible smart meter's P1 port and exposes
the latest electricity and attached utility-meter values on the LAN. It has two
official local APIs:

| API | Discovery and transport | Authorization | Main routes |
|-----|-------------------------|---------------|-------------|
| v1 | `_hwenergy._tcp.local.`, HTTP **80** | Enable Local API in the official app; no token | `/api`, `/api/v1/data`, `/api/v1/telegram`, `/api/v1/system` |
| v2 (API **2.3.0+**) | `_homewizard._tcp.local.`, HTTPS **443** | Physical-button bearer-token pairing | `/api`, `/api/measurement`, `/api/telegram`, `/api/system`, setup-only `POST /api/user` |

Prefer v2 when the unit's negotiated metadata supports it. **Do not choose an
API by trying paths until one answers.** Select from `product_type=HWE-P1`, the
mDNS service and semantic `api_version`; `firmware_version` is unrelated. Never
request v1 over HTTPS, and never treat a timeout, 404, 401, 503 or TLS failure
as permission to switch paths.

Every measurement point is optional. Missing means unavailable, **not zero**.
The API returns the latest reading, not a historical series. Cloud/app history
and Energy+ are separate and are not needed for local measurements.

## Hardware and apps

| Property | Value |
|----------|-------|
| API product type | `HWE-P1` |
| v2 certificate product type | `p1dongle` (not `HWE-P1` or necessarily `p1meter`) |
| Android app | HomeWizard Energy, `nl.homewizard.android.energy` |
| iOS app | HomeWizard Energy, App Store ID `1492427207` |
| Setup confidence | medium (official docs; no hardware run here) |
| Local history | None; latest measurement only |

Use the official Energy app, not the older `nl.homewizard.android` hub app.
Check smart-meter compatibility and power requirements for the exact meter. No
physical installation was performed for this guide. No suitable first-party PDF
manual was found, so no manual link is asserted.

## Initial setup

Initial Wi-Fi setup uses the official app for both API versions. Whether an
account is strictly required was not established; do not claim account-free
onboarding. v1 additionally requires **Settings → Meters → this P1 Meter →
Local API**. v2 does not need that toggle, but does need a local token.

### v1: enable and read

1. Provision Wi-Fi in the official Energy app and enable Local API.
2. Browse `_hwenergy._tcp.local.` on port 80. TXT includes `api_enabled`,
   `path=/api/v1`, `serial`, `product_name` and `product_type`. Require
   `product_type=HWE-P1`; for active reads require `api_enabled=1`.
3. Confirm `GET /api` reports `product_type=HWE-P1` and `api_version=v1`.
4. Use only HTTP/80 v1 routes. No bearer token is used, so the trusted LAN is
   the access boundary.

### v2: CA and 30-second physical-button token

1. Browse `_homewizard._tcp.local.` on port 443. Require `product_type=HWE-P1`
   and API **2.3.0 or newer**. TXT `id` is the expected certificate identity:
   `appliance/p1dongle/<serial>`.
2. Download the public
   [HomeWizard CA](https://api-documentation.homewizard.com/homewizard-ca-cert.pem).
   Validate the device chain against it and pass the TXT `id` through the HTTP
   library's `server_hostname` facility. Do not disable chain or hostname
   verification. The reviewed CA is self-signed HomeWizard Appliance Access CA,
   valid 2021-12-18 through 2031-12-16, SHA-256 fingerprint
   `4E:C2:77:E6:20:33:FA:E8:BC:37:3E:3F:2A:97:66:76:D3:F6:65:68:38:73:F1:EA:8E:3B:DF:78:AC:68:00:03`.
   No live leaf/TLS session was verified here.
3. With `Content-Type: application/json` and `X-Api-Version: 2`, send
   `POST /api/user` with a unique name such as `local/example-client`.
   The name must match:

   ```text
   ^local\/[a-zA-Z0-9\-_/\\# ]{1,40}$
   ```

4. Expect HTTP 403 `{"error":"user:creation-not-enabled"}` before authorization.
   Press the **P1 button once**. The 1–3 second hold documented for kWh Meter
   does not apply here.
5. Repeat the same POST within **30 seconds**. Success returns the name and a
   token matching `^[A-F0-9]{32}$`. Reusing a name can invalidate its previous
   token; do not loop token creation at an unknown device.
6. Store the token in platform key storage. Verify `GET /api` with
   `Authorization: Bearer <token>` and `X-Api-Version: 2`. A 401
   `user:unauthorized` means repair/re-pair, not try the v1 path.

The physical token flow is local and needs no cloud account. It does not remove
the initial app-provisioning requirement.

**Factory reset**: the exact physical procedure was not established. Vendor
documentation says factory reset restores cloud communication; Wi-Fi and local
v2-user/token survival are unknown. Do not invent a button hold or substitute
pairing mode for reset. Pairing mode also re-enables cloud.

**Rebinding to a new network**: use the official app's Wi-Fi/pairing flow;
factory reset is not documented as required. Rediscover by serial/certificate
ID and select the API from negotiated metadata again. Token survival across the
move is unverified, so reauthorize only if the existing token is rejected.

## Pairing and credentials

| Property | Value |
|----------|-------|
| v1 client pairing | None after the app toggle; open on the trusted LAN |
| v2 client pairing | Named local user plus one P1 button press, 30-second window |
| Security mode | `app_layer` bearer token over verified HTTPS |
| Bonding | Persistent named v2 user/token |
| One client at a time | No |
| One bond at a time | No; use unique names because reuse can replace a token |
| Unpair | Vendor documents authenticated `DELETE /api/user`; excluded from this first implementation |

The token grants full local data access and is not a cloud credential. Tokens
whose names begin `local/` or `cloud/` describe how the user was created; both
are for local device communication. Keep tokens, serials, meter identifiers,
SSIDs and token-user names out of logs and fixtures. The CA certificate is
public, not a private key.

## HTTP API

All v2 data requests below require `Authorization: Bearer <token>` and
`X-Api-Version: 2`. The major header selects version 2 while later minor
versions may add fields; retain unknown fields.

| Method | Path | API | Returns |
|--------|------|-----|---------|
| GET | `/api` | v1 and v2, on their respective transports | Product name/type, serial, firmware and API identity |
| GET | `/api/v1/data` | v1 | Latest optional P1 measurement |
| GET | `/api/v1/telegram` | v1 | Latest valid raw DSMR telegram, `text/plain` |
| GET | `/api/v1/system` | v1 | `cloud_enabled`; GET-only here |
| GET | `/api/measurement` | v2 | Latest optional P1 measurement |
| GET | `/api/telegram` | v2 | Raw DSMR; 503 `telegram:no-telegram-received` means unavailable |
| GET | `/api/system` | v2 | Wi-Fi/system telemetry; GET-only here |
| POST | `/api/user` | v2 | Setup-only physical-button token creation |

Raw telegrams have their checksum validated when present and otherwise pass
through. Use a real DSMR parser if structured data is needed and redact meter
identifiers in retained telegrams.

### v1 measurement fields

All are optional. Energy counters are **kWh**, not Wh. Import and export remain
separate counters.

| Quantity | Exact v1 fields and units |
|----------|---------------------------|
| Identity/network | `unique_id`, `smr_version`, `meter_model`, `wifi_ssid`, `wifi_strength` (%) |
| Tariff | `active_tariff` |
| Import totals | `total_power_import_kwh`, `total_power_import_t1_kwh` … `_t4_kwh` (kWh) |
| Export totals | `total_power_export_kwh`, `total_power_export_t1_kwh` … `_t4_kwh` (kWh) |
| Active power | `active_power_w`, `active_power_l1_w` … `_l3_w` (W); negative indicates export and aggregate is not absolute phase sum |
| Voltage/current | `active_voltage_l1_v` … `_l3_v` (V), `active_current_l1_a` … `_l3_a` (A) |
| Frequency | `active_frequency_hz` (Hz) |
| Diagnostics | `voltage_sag_l1_count` … `_l3_count`, `voltage_swell_l1_count` … `_l3_count`, `any_power_fail_count`, `long_power_fail_count` |
| Demand | `active_power_average_w` (W), **`montly_power_peak_w`** (W), **`montly_power_peak_timestamp`** |
| Legacy gas | `total_gas_m3` (m³), `gas_timestamp`, `unique_gas_id` and example spelling `gas_unique_id` |
| External meters | `external[]` with `unique_id`, `type`, `timestamp`, `value`, `unit` |

The `montly` misspelling is part of the v1 wire format; do not correct it in a
parser. v1 numeric timestamps use `YYMMDDhhmmss` with no timezone. External
`type` can be `gas_meter`, `heat_meter`, `warm_water_meter`, `water_meter` or
`inlet_heat_meter`; tolerate future types and preserve each entry's own `unit`
(such as `m3` or `GJ`) instead of forcing m³. Prefer `external` over the legacy
gas-only fields, which are marked for future removal.

### v2 measurement fields and aliases

| Quantity | Exact v2 fields and units |
|----------|---------------------------|
| Identity/time | `unique_id`, `protocol_version`, `meter_model`, `timestamp`, `tariff` |
| Import totals | `energy_import_kwh`, `energy_import_t1_kwh` … `_t4_kwh` (kWh) |
| Export totals | `energy_export_kwh`, `energy_export_t1_kwh` … `_t4_kwh` (kWh) |
| Power | `power_w`, `power_l1_w` … `_l3_w` (W) |
| Voltage/current | `voltage_v`, `voltage_l1_v` … `_l3_v` (V); `current_a`, `current_l1_a` … `_l3_a` (A) |
| Frequency | `frequency_hz` (Hz) |
| Diagnostics | Same sag/swell/failure count names as v1 |
| Demand | `average_power_15m_w` (W), `monthly_power_peak_w` (W), `monthly_power_peak_timestamp` |
| External meters | Typed `external[]` records as above |

v2 timestamps are ISO 8601 strings such as `2024-06-28T14:12:34`, again with no
timezone; never silently label them UTC. `current_a` is the sum of **absolute**
per-phase currents, while signed per-phase currents indicate export. It is not
interchangeable with a signed sum.

Common v1 → v2 renames include `smr_version` → `protocol_version`,
`active_tariff` → `tariff`, `total_power_*` → `energy_*`, `active_power_*` →
`power_*`, `active_voltage_*` → `voltage_*`, `active_current_*` → `current_*`,
`active_frequency_hz` → `frequency_hz`, `active_power_average_w` →
`average_power_15m_w`, and `montly_power_peak_*` → `monthly_power_peak_*`.
Select the mapping from the negotiated API version. The official Python
normalizer's dependence on optional `wifi_ssid` is not a safe version test.

### System fields

v1 `GET /api/v1/system` returns only `cloud_enabled` for this implementation.
v2 `GET /api/system` can return `wifi_ssid`, `wifi_rssi_db` (dBm), `uptime_s`
(seconds), `cloud_enabled`, `status_led_brightness_pct` (0–100%) and optional
`api_v1_enabled`. These are distinct from v1's `wifi_strength` percentage and
the Energy Socket's 0–255 brightness.

System/cloud/LED/v1-enable writes, user list/delete, identify, reboot, battery
and firmware operations are excluded. Disabling cloud is not a casual privacy
toggle: it also disconnects the official app and stops future firmware updates.
Pairing mode or factory reset can restore cloud.

## Freshness and polling

Do not poll more frequently than every **500 ms**; one second is a sensible
base for DSMR 5. Use monotonic staleness handling—an unchanged counter or old
timestamp is not a new sample.

- DSMR 5: power about every second, gas every five minutes.
- Older DSMR: power about every 10 seconds, gas every 60 minutes.

## Tools and evidence

- [x] Official API documentation and official Python client/fixture review
- [x] Independent standard-library alias, negotiation, regex and fixture tests
- [ ] Live discovery, token pairing, certificate session or physical meter read

Pinned evidence: `homewizard/api-documentation`
`571384adec2183c16a79392a227d0e5ee92b4ee9` and
`homewizard/python-homewizard-energy`
`60be21a42da6700f3939bdbf3ed4e3d87a0bc2d8`.

## References

- [Device/API compatibility](https://api-documentation.homewizard.com/docs/introduction#devices)
- [Getting started](https://api-documentation.homewizard.com/docs/getting-started)
- [Discovery](https://api-documentation.homewizard.com/docs/discovery)
- [Version negotiation](https://api-documentation.homewizard.com/docs/versioning)
- [v1 measurement](https://api-documentation.homewizard.com/docs/v1/measurement)
- [v2 measurement](https://api-documentation.homewizard.com/docs/v2/measurement)
- [v2 authorization and CA validation](https://api-documentation.homewizard.com/docs/v2/authorization)
- [P1 Meter product page](https://www.homewizard.com/shop/wi-fi-p1-meter/)

## Remaining unknowns

Physical compatibility, optional-field behavior on every firmware, actual
pairing/revocation, live certificate chains, exact reset/token survival and
initial app account requirements remain unverified. Timestamp timezone is not
supplied by the device and must not be guessed as UTC.
