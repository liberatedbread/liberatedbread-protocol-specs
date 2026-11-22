# Wyze Cam (via docker-wyze-bridge)

> **Status**: Spec available (untested, reported); identify-only in this project
> **Protocol**: WiFi, TUTK upstream with local RTSP/HLS from a community bridge
> **Manufacturer**: Wyze Labs
> **Manufacturer Status**: Active

## Overview

Stock Wyze cameras have no first-party general-purpose local API. The narrow exception is the separate official RTSP firmware branch for three exact model/firmware combinations, documented in [Wyze legacy RTSP](wyze-legacy-rtsp.md); it does not make ordinary stock firmware an RTSP API.

The community [docker-wyze-bridge](https://github.com/mrlt8/docker-wyze-bridge) logs in to the owner's Wyze account, obtains camera information and TUTK values, and serves media from the machine running the bridge. A Wyze account and developer API Key/ID are required. Permanent cloud isolation is not supported.

The bridge prefers a LAN connection but can fall back to P2P or relay. Its session codes are **0 = P2P**, **1 = relay**, and **2 = LAN**. `NET_MODE=LAN` rejects non-LAN sessions. Even in relay mode, the RTSP/HLS URLs below remain endpoints on the local bridge host; “local endpoint” does not prove that the upstream media stayed on the LAN.

## Supported cameras

This is an allowlist from the bridge's supported-camera table, not a list of Wyze products to try experimentally.

| Product | Model code |
|---|---|
| Cam v1 (HD only) | `WYZEC1` |
| Cam v2 | `WYZEC1-JZ` |
| Cam v3 | `WYZE_CAKP2JFUS` |
| Cam v3 Pro (2K) | `HL_CAM3P` |
| Cam v4 (2K) | `HL_CAM4` |
| Cam Pan v1 | `WYZECP1_JEF` |
| Cam Pan v2 | `HL_PAN2` |
| Cam Pan v3 | `HL_PAN3` |
| Cam Pan Pro (2K) | `HL_PANP` |
| Cam Outdoor v1 | `WVOD1` |
| Cam Outdoor v2 | `HL_WCO2` |
| Cam Doorbell v1 | `WYZEDB3` |
| Cam Doorbell v2 (2K) | `HL_DB2` |
| Cam Floodlight v1 | `WYZE_CAKP2JFUS` with `HL_CFL` accessory identity |
| Cam Floodlight v2 (2K) | `HL_CFL2` |

`WYZE_CAKP2JFUS` is shared by the standalone Cam v3 and Floodlight v1. `HL_CFL` is only the Floodlight v1 accessory identity that distinguishes it from the standalone camera, not another cloud camera model or a standalone variant. Product and accessory identity therefore matters, especially for reset.

Do **not** infer support for `HL_PAN4`, Gwell or Meari devices, Battery Cam Pro (`AN_RSCW`), Floodlight Pro (`LD_CFP`), Doorbell Pro (`GW_BE1`), or Doorbell Pro 2 (`AN_RDB1`). Warning-marked and different-SDK products in upstream's table are not included.

## Initial Setup

1. Confirm the exact product and model code above and onboard the camera in the Wyze app.
2. Create a Wyze developer API Key and API ID. Configure the bridge with those and the account email/password.
3. Leave the default LAN preference, or set `NET_MODE=LAN` to reject P2P and relay. Neither choice makes the camera permanently cloud-independent.
4. Manually configure the **bridge/NVR hostname or address**. There is no `_http._tcp`-on-8554 discovery method and no automatic camera discovery on the LAN; cloud account enumeration supplies the camera list.

`{address}` in every stream URL means the bridge/NVR host, never the camera. The bridge's Web UI is `http://{address}:5000/`.

### Camera slugs

With upstream's default settings, trim the nickname, replace spaces with hyphens, remove special/non-ASCII characters other than `_`, `-`, and `+`, and lowercase the result. For example, `Front Porch Cam` becomes `front-porch-cam`. `URI_SEPARATOR` and `URI_MAC` overrides are outside this spec.

### Local endpoints

| Transport | URL |
|---|---|
| RTSP | `rtsp://{address}:8554/{camera_name}` |
| HLS | `http://{address}:8888/{camera_name}/stream.m3u8` |

The HLS path above is the actual MediaMTX playlist path, not the bridge Web UI. No generic WebRTC template is offered: the pinned bridge's `NO_WEBRTC` set excludes six otherwise allowed models—`WYZEC1`, `HL_PANP`, `WVOD1`, `HL_WCO2`, `WYZEDB3`, and `HL_DB2`—and the stream schema cannot variant-scope an entry. Those exclusions are known; only additional WebRTC/ICE and host/network behavior remains unverified.

## Pairing and authentication

There is no camera PIN or Bluetooth-style pairing. The Wyze cloud supplies per-camera TUTK values to the bridge after account/developer-API authentication. Camera account binding and consumer-to-bridge authentication are separate gates.

`WB_AUTH` is **enabled by default**:

- Media streams use username `wb` and the bridge's unique `WB_API` key as the password. The key is shown at the bottom of the Web UI unless explicitly configured.
- The Web UI defaults to username `wbadmin`; `WB_PASSWORD` overrides its derived password.
- The REST API accepts `WB_API` in an `api` header or query parameter.
- `STREAM_AUTH` uses `user:password[:client-ip[,client-ip...]][@path[,path...]]`, with multiple entries separated by `|`. Empty IP or path restrictions mean any IP or all paths. These grants can coexist with `WB_AUTH=true` and its `WB_API` credential.

An empty `STREAM_AUTH` username matches **any username**; an empty username and password creates an anonymous grant. Credentialed and anonymous examples are:

| Value | Meaning |
|---|---|
| `cam-user:example-only-password` | Credentialed access from any IP to all paths; the password is an invented example. |
| `::192.168.0.10` | Anonymous access from `192.168.0.10` to all paths. |
| `::192.168.0.15,192.168.0.20@just-one-cam` | Anonymous access from either listed IP to only `just-one-cam`. |
| `:@public-cam` | Anonymous access from any IP to only `public-cam`. |

`WB_AUTH=false` with no `STREAM_AUTH` is the **whole-stream default-anonymous configuration**, not the only anonymous form. It configures anonymous reads for every stream and is an insecure, deliberate choice for a trusted isolated LAN, not a safe configuration for port forwarding or an untrusted network.

To revoke a bridge, revoke its Wyze developer API key and clear cached bridge credentials. Rotate `WB_API` or `STREAM_AUTH` secrets to revoke local stream consumers; cloud revocation alone does not change those local credentials.

## Factory reset

Reset coverage is deliberately limited to standalone **Cam v1, Cam v2, Cam v3, and Pan v1**. It does not extend to the other bridge products or to Floodlight v1 merely because that product shares the v3 model code.

Remove the microSD card first. With the camera powered:

- **Cam v1:** hold the bottom Setup button for **20 seconds**.
- **Cam v2, standalone Cam v3, and Pan v1:** hold it for **10 seconds**.

Wait at least 30 seconds, allowing up to five minutes. Cam v1/v2/Pan v1 change from solid yellow to blinking yellow; standalone Cam v3 turns red. These procedures are vendor-documented but unverified by this project. Per-model quick-start guides and the factory-reset article are linked from the YAML spec.

For an ordinary router change, use the model's Wyze app setup/reconnect flow first rather than factory-resetting by default. Reconnect the bridge afterward and update the client's manually configured bridge address if that host changed too.

## Protocol Summary

The machine-readable spec carries the exact model allowlist, manual bridge-host identity, TUTK session codes, slug algorithm, stream templates, all authentication modes, and product-scoped reset procedures. It is `untested` and `identify_only`: this project has not streamed a camera and does not currently ship a video player.

See `device-specs/devices/wyze-bridge-camera.yaml` for implementation detail.

## References

- [docker-wyze-bridge supported cameras](https://github.com/mrlt8/docker-wyze-bridge/blob/bf893749b748f142199c9bce14fac44f8a661d6e/README.md#supported-cameras)
- [Bridge authentication](https://github.com/mrlt8/docker-wyze-bridge/wiki/Authentication)
- [Network connection modes](https://github.com/mrlt8/docker-wyze-bridge/wiki/Network-Connection-Modes)
- [Wyze factory-reset article](https://support.wyze.com/hc/en-us/articles/360031484511-How-to-factory-reset-your-Wyze-Cam-v1-v2-v3-or-Pan-v1)
