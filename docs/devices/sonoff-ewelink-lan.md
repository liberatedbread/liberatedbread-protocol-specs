# Sonoff / eWeLink LAN relays

> **Status**: Spec available, untested; identify-only in the generic app
> **Protocol**: Wi-Fi LAN — mDNS/DNS-SD and HTTP `/zeroconf/*`
> **Manufacturer**: ITEAD / Sonoff (active)

## Overview

Two protocols share the same service type and URL prefix but are **not the same
wire format**:

- **Stock eWeLink LAN** uses account/device metadata and AES-128-CBC when TXT
  `encrypt` is true.
- **Official DIY mode** is keyless plaintext with a smaller object envelope, and
  applies only to **Basic R3, RFR3, and Mini** on ITEAD-documented firmware.

Do not send a stock envelope to DIY mode. Do not treat plaintext stock `data` as
DIY or remove encryption from a stock device. The full split and synthetic test
vectors are in `device-specs/devices/sonoff-ewelink-lan.yaml`.

Generic integration is `identify_only` until a dedicated stock envelope/per-UIID
handler exists. DIY commands are separate and require an explicit
`type=diy_plug`, `apivers=1` dispatch decision.

## Discovery

Browse **`_ewelink._tcp.local.`**. Instance names are
`eWeLink_<deviceid>`; the `eWelink_` capitalization also occurs. The device ID is
the suffix after the first eight instance characters.

Use the resolved IPv4 address and **SRV port**. Port **8081 is only a fallback
when SRV supplies no port**, never an override for a different advertised port.

Read `id`, `type`, `apivers`, `seq`, `encrypt`, `iv`, and `data1` through
`data4`. Join the present data fields in numeric order before decoding; each part
holds at most 249 bytes. `seq` orders state updates. For bridges, TXT `id` can
identify a child and differ from the instance device ID.

## Stock request envelope and AES

Stock requests go to `http://<ipv4>:<srv-port>/zeroconf/<cmd>` with this shape:

```json
{
  "sequence": "1700000000000",
  "deviceid": "10000000d0",
  "selfApikey": "<account-apikey>",
  "iv": "<base64-of-16-raw-iv-bytes>",
  "encrypt": true,
  "data": "<base64-aes-ciphertext>"
}
```

`sequence` is a 13-character epoch-millisecond string. `data` is always a
**string**. With TXT `encrypt=false` or absent, it contains
`JSON.stringify(params)` rather than a nested JSON object; the other stock fields
still remain. The stock app sends an IV in both modes.

For encrypted stock:

- `key = MD5(UTF-8 devicekey)` as the **raw 16-byte digest**, not hex ASCII;
- AES-128-CBC uses PKCS#7 padding;
- decode `iv` from Base64 before using its 16 bytes;
- Base64-decode `data` before decryption, and encode requests in the reverse order.

There is no MAC or replay authentication. Successful CBC decryption, valid
padding, or a valid JSON parse proves **decodability, not authenticity or
integrity**. A fresh random 16-byte IV works; the app's own IV happens to be
16 decimal digits. Require `error=0` and correlate `sequence`/`seq` where
returned. Serialize HTTP requests because the small server is effectively
single-threaded. Some units return `text/html` to `getState`, meaning online but
no JSON state, not proof of DIY.

After normal PKCS#7 validation/removal, tolerate only the exact reported trailing
`0x02` bytes left by a firmware padding bug. Do not strip arbitrary bytes, and do
not call the resulting decode authenticated.

## Commands

| Path | Inner params | Notes |
|---|---|---|
| `/zeroconf/switch` | `{"switch":"on"}` | Single stock relay, `off` to de-energize |
| `/zeroconf/switches` | `{"switches":[{"switch":"on","outlet":0}]}` | Multi-channel stock, zero-based outlet |
| `/zeroconf/startup` | `{"startup":"stay"}` | Power-recovery state, also `on`/`off` |
| `/zeroconf/pulse` | `{"pulse":"on","pulseWidth":500}` | Inching; width in milliseconds |
| `/zeroconf/getState` | `{}` | Not universal |

Relay, startup, and pulse writes are advanced attended operations. Startup
`on`/`stay` can energize a load after a future power cut. DIY documents pulse
widths from 500 through 36,000,000 ms in multiples of 500; stock UIID limits can
be narrower and must be checked.

## Official DIY is a separate envelope

On the three documented models, DIY requests contain only:

```json
{"deviceid":"10000000d0","data":{"switch":"on"}}
```

There is no `sequence`, `selfApikey`, `iv`, or `encrypt` field and no devicekey.
Discovery reports `type=diy_plug`, `apivers=1`. Firmware 3.3.0 or later is the
published baseline; version 3.5.0 enables DIY from the device AP web page.
Requests should be at least 200 ms apart.

DIY also documents `startup`, `pulse`, `info`, `signal_strength`, `wifi`, and the
advanced `ota_unlock` → `ota_flash` sequence. OTA pulls an HTTP image from a
Range-capable server with an expected SHA-256. A checksum proves integrity, not
model compatibility or recoverability; older firmware can require a vendor
unlock service.

## Credentials and setup

Stock setup normally uses eWeLink account binding, and the account device list
supplies `deviceid` and `devicekey`. On bounded stock setup flows, joining the
`ITEAD-…` AP and reading **`http://10.10.7.1/device`** can expose `deviceid`
and `apikey` (the devicekey) before normal setup. Use it only when that response
actually exposes both fields. It is not universal recovery for configured or
unsupported devices.

`POST /ap` provisions `ssid`, `password`, `serverName`, and `port`. This and DIY
`/zeroconf/wifi` send Wi-Fi credentials over plaintext HTTP. Stock AES has no
integrity protection, so setup and control belong on a trusted LAN.

## Reset and changing routers

The conservative **stock** rejoin posture is `in_place_supported: false` and
`requires_factory_reset: true`: use the exact model's setup flow rather than
inventing an in-place write. The BASICR2/RFR2 manual specifically requires a
**five-second pairing-button hold** until the Wi-Fi LED cycles **two short
flashes and one long flash**. Release to enter quick pairing and provision the
new network. That reset remains scoped to BASICR2/RFR2; other stock models use
their own instructions rather than inheriting the hold.

Official **DIY is the separate exception**: on a verified `type=diy_plug`, POST
`/zeroconf/wifi` with the new SSID/password without a factory reset. Recheck the
instance device ID and SRV port afterward. Whether a stock devicekey changes
during re-pairing is unresolved; retrieve it again via a legitimate account or
bounded setup source if necessary.

## Verification

`scripts/test_sonoff_ewelink_lan_spec.py` reconstructs the raw-MD5 AES key,
Base64 IV and ciphertext, stock request example, TXT reassembly, SRV-port
selection, and stock-versus-DIY bodies and rejoin behavior. It checks pulse units,
advanced relay/OTA gates, bounded reset/credential claims, unauthenticated-CBC
wording and exact-only trailing `0x02` cleanup without contacting a relay.

## References

- [ITEAD DIY mode protocol](https://github.com/itead/Sonoff_Devices_DIY_Tools),
  official Basic R3/RFR3/Mini documentation.
- [AlexxIT SonoffLAN](https://github.com/AlexxIT/SonoffLAN), stock and DIY client
  cross-check.
- [BASICR2/RFR2 manual](https://fccid.co/api/files/s1/2apn5basicr2_usersmanual_4642809_0c68b950d2.pdf),
  source for the model-scoped reset procedure.
