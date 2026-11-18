# HomeWizard Wi-Fi Energy Socket (HWE-SKT / HWE-SKT-21)

> **Status**: Spec Available; official v1 API, untested here
> **Protocol**: Wi-Fi — local HTTP/80 v1, GET-only
> **Manufacturer**: HomeWizard
> **Manufacturer Status**: Active

## Overview

The HomeWizard Energy Socket combines a mains relay with electrical metering.
This guide covers its official **v1** local API on HWE-SKT and HWE-SKT-21:
identity, latest measurements, actual relay/lock/LED state and cloud state.

The pinned official compatibility table marks Socket v2 planned/in development.
**Do not discover `_homewizard`, infer v2 from a newer app, or try v2 paths.**
The certificate product type `energysocket` is not evidence of v2 support. Both
hardware variants use `product_type=HWE-SKT`; HWE-SKT-21 adds three measurement
fields rather than a new API identity.

This is deliberately a **GET-only first implementation**. No relay, switch
lock, brightness, cloud, reboot or firmware write is declared or tested.

!!! warning "Mains loads and cloud consequences"
    Vendor ratings are **3680 W / 16 A maximum** and **2760 W / 12 A
    continuous**, with overload and overheat protection. Those protections do
    not make unattended automation inherently safe or replace appliance-specific
    load limits and safety interlocks.

    Disabling cloud through the system write also disconnects the official app
    and stops future firmware updates. It is a deliberate owner operation, not
    a routine privacy toggle, and is outside this implementation. Pairing mode
    or factory reset can restore cloud.

## Hardware and apps

| Property | Value |
|----------|-------|
| API product type | `HWE-SKT` for both variants |
| Extra SKT-21 fields | `active_reactive_power_var`, `active_apparent_power_va`, `active_power_factor` |
| Radio | 2.4 GHz Wi-Fi 802.11 b/g/n |
| Android app | HomeWizard Energy, `nl.homewizard.android.energy` |
| iOS app | HomeWizard Energy, App Store ID `1492427207` |
| API confidence | medium (official docs; no hardware run here) |

Use the official Energy app, not the older `nl.homewizard.android` hub app. No
suitable first-party PDF manual was found, so no manual link is asserted.

## Initial setup

| Property | Value |
|----------|-------|
| Setup required | Yes: official app Wi-Fi + Local API toggle |
| Discovery | `_hwenergy._tcp.local.`, HTTP port 80 |
| Client pairing | None for v1 reads; the trusted LAN is the gate |
| Passphrase protection | Unknown during app provisioning; no API token is issued |
| Confidence | medium; not replayed here |

1. Connect the socket within its rated load and provision Wi-Fi with the
   official Energy app on the same LAN as the client. Whether an account is
   strictly required was not established; do not claim account-free setup.
2. In the app open **Settings → Meters → this Energy Socket → Local API** and
   enable it.
3. Browse `_hwenergy._tcp.local.`. TXT includes `api_enabled`, `path=/api/v1`,
   `serial`, `product_name` and `product_type`. Require `product_type=HWE-SKT`
   and, for active reads, `api_enabled=1`.
4. Confirm `GET /api` over HTTP/80 returns `product_type=HWE-SKT` and
   `api_version=v1`. Do not use `firmware_version` to infer v2.
5. Read `/api/v1/data`, `/api/v1/state` and `/api/v1/system` with GET only.
   Serials and SSIDs are private installation metadata; redact them in logs.

**Factory reset**: no exact physical procedure was established. Vendor docs say
factory reset restores cloud, but Wi-Fi and local-state survival are unknown.
Do not invent a button hold or use pairing mode as a reset substitute.

**Rebinding to a new network**: use the official app's Wi-Fi/pairing flow; no
factory-reset-only route is documented. Pairing mode re-enables cloud. Match
the returning socket by serial, require v1 identity again, and re-enable Local
API only if `api_enabled=0`. Do not probe `_homewizard` or v2 endpoints.

## Pairing and credentials

| Property | Value |
|----------|-------|
| Pairing required | No for v1 API reads |
| Security mode / bonding | `none` / `none` |
| PIN/token | None |
| One client at a time | No |
| Unpair | No per-client bond; disable Local API in the app to withdraw v1 LAN access |
| Confidence | medium (official documentation) |

Wi-Fi/app pairing mode belongs to provisioning and restores cloud. It is not the
P1 v2 token flow and does not establish Socket v2 support.

## HTTP endpoints

| Method | Path | Returns |
|--------|------|---------|
| GET | `/api` | `product_name`, `product_type`, `serial`, `firmware_version`, `api_version=v1` |
| GET | `/api/v1/data` | Latest optional measurement JSON |
| GET | `/api/v1/state` | Actual `power_on`, `switch_lock`, `brightness` |
| GET | `/api/v1/system` | Actual `cloud_enabled` |

No PUT is included. In particular, `/api/v1/state` supports writes upstream but
this spec reads it only. Raw `/api/v1/telegram` is P1-only and not a Socket
endpoint.

### Measurement fields

All points are optional when unavailable. Energy totals are **kWh**, not Wh.

| Field | Unit | Meaning |
|-------|------|---------|
| `wifi_ssid` | — | Joined Wi-Fi network; private metadata |
| `wifi_strength` | % | v1 Wi-Fi strength percentage |
| `total_power_import_kwh` | kWh | Aggregate imported energy |
| `total_power_import_t1_kwh` | kWh | Duplicate of aggregate for backwards compatibility |
| `total_power_export_kwh` | kWh | Aggregate exported energy |
| `total_power_export_t1_kwh` | kWh | Duplicate of aggregate for backwards compatibility |
| `active_power_w` | W | Aggregate active power |
| `active_power_l1_w` | W | Duplicate of aggregate for backwards compatibility |
| `active_voltage_v` | V | Socket voltage; **not** P1's `active_voltage_l1_v` |
| `active_current_a` | A | Socket current; **not** P1's `active_current_l1_a` |
| `active_frequency_hz` | Hz | Line frequency |
| `active_reactive_power_var` | var | **HWE-SKT-21 only** reactive power |
| `active_apparent_power_va` | VA | **HWE-SKT-21 only** apparent power |
| `active_power_factor` | dimensionless | **HWE-SKT-21 only** numeric factor, not a percentage |

Never add tariff-1 totals or `active_power_l1_w` to their aggregates; they are
duplicate views of the same values. Do not multiply power factor by 100 without
an explicit UI convention. If SKT-21's three extra fields are temporarily
unavailable, do not invent a new product type to explain it.

### State fields

`GET /api/v1/state` returns:

- `power_on`: actual relay state, `true` when on;
- `switch_lock`: when `true`, prevents turning the socket off;
- `brightness`: LED ring brightness from **0 (0%) to 255 (100%)**, not v2's
  0–100 `status_led_brightness_pct`.

These are read-only values in this implementation. There are intentionally no
`turn_on`, `turn_off`, lock or brightness commands bound to the entities.

### System field

`GET /api/v1/system` returns `cloud_enabled`. This spec never sends the system
PUT. Disabling cloud stops both official app communication and future firmware
updates; pairing mode or factory reset can restore it.

## Polling and freshness

Follow the vendor guidance not to retrieve data more often than every **500
ms**. The endpoint returns the latest measurement, not historical series. Use
monotonic staleness handling and do not treat repeated counters as new samples.
Cloud/app history and Energy+ are separate and not required for local readings.

## Tools and evidence

- [x] Official API documentation and official Python client/fixture review
- [x] Independent standard-library fixture, field, unit and GET-only tests
- [ ] Live discovery or physical Socket reads
- [ ] Every relay/lock/brightness/cloud/firmware write (out of scope)

Pinned evidence: `homewizard/api-documentation`
`571384adec2183c16a79392a227d0e5ee92b4ee9` and
`homewizard/python-homewizard-energy`
`60be21a42da6700f3939bdbf3ed4e3d87a0bc2d8`.

## References

- [Device/API compatibility](https://api-documentation.homewizard.com/docs/introduction#devices)
- [Getting started](https://api-documentation.homewizard.com/docs/getting-started)
- [Discovery](https://api-documentation.homewizard.com/docs/discovery)
- [v1 measurement](https://api-documentation.homewizard.com/docs/v1/measurement)
- [v1 Socket state](https://api-documentation.homewizard.com/docs/v1/state)
- [v1 system](https://api-documentation.homewizard.com/docs/v1/system)
- [Energy Socket product page](https://www.homewizard.com/energy-socket/?default=true)

## Remaining unknowns

Physical HWE-SKT/HWE-SKT-21 behavior, optional-field presence, initial app
account requirements, reset/rejoin state survival and all writes remain
unverified. Socket v2 is outside scope and must not be inferred from planned
documentation or app releases.
