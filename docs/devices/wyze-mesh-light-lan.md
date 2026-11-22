# Wyze Bulb Color / Light Strip (encrypted LAN)

> **Status**: Spec available (untested, reported); identify-only in this project
> **Protocol**: WiFi, encrypted JSON over HTTP port 88
> **Manufacturer**: Wyze Labs
> **Manufacturer Status**: Active

## Overview

This bounded spec covers only:

| Product | Cloud `product_model` | Cloud `product_type` |
|---|---|---|
| Wyze Bulb Color | `WLPA19C` | `MeshLight` |
| Wyze Light Strip (original) | `HL_LSL` | `LightStrip` |

It does **not** cover Bulb Color v2, BR30, white bulbs, Light Strip Pro (`HL_LSLP`), plugs, cameras, or a different model/type combination.

Cloud inventory must also establish that the exact reported firmware supports the encrypted port-88 API. The minimum compatible firmware is not established, so this spec does not invent a version range: unknown firmware stops at identification. A client needs the cloud MAC, `enr`, firmware and last-known IP, and must confirm the current IP against the router's lease for that MAC. Port 88 is not an identity or discovery signal.

The local endpoint supports ordinary attended light writes. This project remains `identify_only` because it has no handler for the custom encryption; a generic HTTP client must not post plaintext or pretend to have a state-reading integration.

## Initial Setup

This is one route with three required stages, not alternative setup choices:

1. **Vendor account and BLE onboarding.** In the Wyze app, enable Bluetooth/location access, select the exact product, and join it to a 2.4 GHz Wi-Fi network. If setup mode is needed, use only the matching reset below.
2. **Cloud inventory and gates.** Authenticate with the owner's Wyze account and developer API Key/ID. Require the exact model/type tuple, established firmware compatibility, a 16-byte ASCII `enr`, and the MAC. Confirm the current IP by MAC at the router.
3. **Direct LAN writes.** Build the encrypted request below. Continue authorized Wyze cloud polling for actual state.

There is no account-free provisioning, `enr` enumeration, or LAN discovery route.

## Protocol Summary

Send compact JSON to:

```text
POST http://<device-ip>:88/device_request
Content-Type: application/json
```

The plaintext `characteristics` document has keys in this order, with no whitespace:

```json
{"mac":"00005E000001","index":"1","ts":"1700000000123","plist":[{"pid":"P3","pvalue":"1"}]}
```

The MAC and timestamp above are invented test-vector values. In a live request, use the cloud MAC as 12 uppercase hexadecimal digits without separators, literal string `index: "1"`, and current Unix-epoch **milliseconds** as a decimal string. Every `pvalue` is a string.

| Property | Value |
|---|---|
| `P3` power | `"0"` off, `"1"` on |
| `P1501` brightness | Decimal string, 0–100% |
| `P1502` white temperature | Decimal string, 1800–6500 K |
| `P1507` RGB color | Six hex digits `RRGGBB`, without `#` |
| `P1508` mode | `"1"` color, `"2"` white |

When explicitly choosing color, send `P1507` followed by `P1508: "1"` in the same `plist`. When choosing white temperature, send `P1502` followed by `P1508: "2"`.

### Encryption and outer request

1. Encode the inner JSON as ASCII with no whitespace.
2. Append `0x05` exactly `16 - (length mod 16)` times. This always adds 1–16 bytes, including a full 16-byte block when aligned. It is **not PKCS#7**: every added byte is `05`, not the padding length.
3. Encrypt with AES-128-CBC. Use the 16 raw ASCII `enr` bytes directly as both key and IV; do not hash or hex-decode them.
4. Encode with standard base64 (`+`, `/`, `=`; not base64url).
5. Put the ciphertext in compact outer JSON with keys `request`, `isSendQueue`, `characteristics`. `request` is `set_status`; `isSendQueue` is numeric `0`.
6. In the outer JSON text, write every base64 slash as `\/`. JSON parsing turns that escape back into `/`; do not emit two backslashes or URL-encode the value.

The YAML spec contains an independent OpenSSL-generated ciphertext and outer-request vector, padding-boundary vectors, and vectors for every declared property. They use only an invented `enr` and documentation MAC.

### Acknowledgement is not state

**HTTP 200 only acknowledges the request.** No local response-body or state-read schema is established. Do not infer power, brightness, temperature, color, or mode from that response, and do not bind a fictitious local state entity. Authorized Wyze cloud polling is still required for actual state. A timeout, refused connection, non-200 response, or stale cloud state is not success.

## Pairing and credentials

There is no local pairing PIN or persistent BLE client bond. Possession of the per-device `enr`, obtained from authorized cloud inventory, is the app-layer gate for LAN writes. It is reusable symmetric obfuscation, not per-client forward secrecy.

Removing a device from the Wyze account does not prove that a copied `enr` stops working locally. For a compromised value, reset and re-onboard, then refetch inventory and verify whether it rotated before treating the old value as revoked.

## Factory reset and rejoin

Use the exact model procedure:

- **Bulb Color (`WLPA19C`):** using its wall switch, turn the bulb off and on **three times**, within six seconds and with less than two seconds between toggles. Wait for slow pulsing.
- **Original Light Strip (`HL_LSL`):** with power on, hold the button on the side of the controller for **at least seven seconds**, until the strip pulses.

After reset, onboard again in the vendor app, repeat the model/type/firmware gate, and refetch MAC, `enr`, and IP. The vendor guides document reset plus setup for network changes; no direct-LAN or account-free rejoin is claimed.

## References

- [SecKatie/wyzeapy](https://github.com/SecKatie/wyzeapy/tree/907056956508d230149e63d67c21a1253e788058) — local request and encryption implementation
- [SecKatie/ha-wyzeapi](https://github.com/SecKatie/ha-wyzeapi/tree/1a553da0d327d2714f1d0bf6a5c1e359ebd160f9) — light property and mode handling
- [Wyze local API encoding discussion](https://forums.wyze.com/t/wyze-local-api-encoding-changes/206479)
- [Bulb Color setup](https://support.wyze.com/hc/en-us/articles/360056417672-Wyze-Bulb-Color-Setup-Guide) and [reset](https://support.wyze.com/hc/en-us/articles/360056503852-How-to-factory-reset-your-Wyze-Bulb-Color)
- [Light Strip setup](https://support.wyze.com/hc/en-us/articles/4403317155483-Wyze-Light-Strip-and-Pro-Setup-Guide) and [reset/connectivity](https://support.wyze.com/hc/en-us/articles/4405395483163-Wyze-Light-Strip-Connectivity-Troubleshooting)

See `device-specs/devices/wyze-mesh-light-lan.yaml` for the implementable field definitions and vectors.
