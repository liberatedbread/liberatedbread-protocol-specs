# Remootio 2 / 3 — WebSocket API v3

> **Status**: Spec Available — documented local API, untested on hardware
> **Protocol**: Wi-Fi, WebSocket on port 8080; separate BLE boundary
> **Manufacturer**: Remootio / Assemblabs Ltd. (active)

## Overview

Remootio's official local WebSocket API v3 supports authenticated status and
control without EasyConnect or another Internet path. It applies to device
software 2.24 and later. The machine-readable spec is
[`remootio-garage-door.yaml`](https://github.com/liberatedbread/liberatedbread-protocol-specs/blob/main/device-specs/devices/remootio-garage-door.yaml).

**Safety**: `TRIGGER`, `OPEN` and `CLOSE` can move a real gate or garage door.
Keep the opening clear and watched. The contact sensor is state reporting, not
a safety interlock. Only read-only `QUERY` is encoded by this project's tests;
no actuation was performed.

Remootio 1, Pro compatibility, wireless-sensor pairing, secondary relay and OTA
are outside this profile. BLE owner setup is real, but its complete encrypted
enrolment and commands are not established and are not replaced with LAN frames.

## Initial Setup

| Property | Value |
|----------|-------|
| Setup required | Yes, owner/master-key setup in the vendor app |
| Method | `ble_provisioning`, then enable WebSocket API (medium confidence) |
| Wi-Fi passphrase protection | Unknown — BLE provisioning was not captured |
| Client credentials | API Secret Key + API Auth Key, then per-session key |
| Discovery | `_remootio._tcp.local.`, port 8080 |

Power the controller and use phone-direct BLE vendor setup to join Wi-Fi. The
Remootio 3 manual describes a five-second blink after setup and continuous LED
after Wi-Fi setup. As the master-key owner, enable the WebSocket API with or
without logging. The app displays two 64-hex-character keys and the local IP.
Store them in a secret store, never in a spec or capture.

The mDNS instance name is the controller serial and the hostname is
`remootio_<serial>.local`. A DHCP reservation is useful but not required. One
API connection is allowed at a time.

**Factory reset**: the manual identifies a physical reset button, but the
reviewed material did not establish its hold time or exact cleared-state list.
No candidate hold is published. Disabling the API is not a factory reset.

**Rebinding**: use BLE owner setup to join the new Wi-Fi network, rediscover the
service and authenticate a new session. Whether API keys survive re-provisioning
is unverified, so preserve them first and be prepared to read them again.

## Pairing and authorization

No OS-level bond is asserted for the LAN path. Authorization is application
layer: enabling the API requires the master key and every new socket starts
unauthenticated. Disabling the API withdraws LAN access; key-rotation behavior
is unknown. Close the other API client if the sole connection is occupied.

## Protocol Summary

| Role | Value |
|------|-------|
| Socket | `ws://<device-ip>:8080` |
| Version probe | `{"type":"HELLO"}` → `SERVER_HELLO` with `apiVersion: 3` |
| Authentication start | `{"type":"AUTH"}` |
| Keepalive | Application `PING`/`PONG` every 60–90 seconds |
| Timeouts | 30 seconds to authenticate; 120 seconds idle |
| Encrypted frame | `ENCRYPTED` with `data.iv`, `data.payload` and `mac` |

`HELLO`, `PING` and `AUTH` are the only top-level commands declared. `QUERY` and
actuation are **not** plain WebSocket JSON commands. They require the encrypted
envelope below.

### Session and cryptography

1. Send `AUTH`. Verify the challenge HMAC with the API Auth Key, then decrypt it
   using the hex-decoded 32-byte API Secret Key.
2. The challenge carries a base64 session key and `initialActionId`. Later AES
   uses the session key; the API Auth Key remains the HMAC key for every frame.
3. Finish authentication with read-only `QUERY`, using
   `id = (lastActionId + 1) % 0x7fffffff`. The same formula applies to every
   later action; `0x7ffffffe` therefore wraps to zero.
4. A wrong id, MAC, padding or credential fails the session. Reconnect and
   authenticate afresh instead of replaying an action whose result was lost.

For each sensitive inner JSON document:

- serialize compactly and apply PKCS7 to a 16-byte boundary;
- generate a fresh random 16-byte IV and encrypt with AES-256-CBC;
- base64-encode IV and ciphertext separately;
- construct exactly `{"iv":"<iv64>","payload":"<payload64>"}`, with no spaces
  and `iv` before `payload`;
- HMAC-SHA256 those exact bytes with API Auth Key and base64-encode the MAC;
- on receive, validate shape/base64 lengths and compare MAC in constant time
  **before** decrypting and validating PKCS7/JSON.

The spec carries a complete synthetic `QUERY` vector made from sequential
invented keys and a fixed IV. It contains no official example credentials or
real session material.

### Status and advanced actions

`QUERY` returns `open`, `closed` or `no sensor`, a success flag, matching id,
`relayTriggered: false` and `t100ms` uptime in 100-millisecond units. Authenticated
`StateChange` events use the same state values and an independent event counter.

`TRIGGER`, `OPEN` and `CLOSE` are recorded only in `protocol_details` as advanced
actions. They must run through the encrypted session, display the physical-
movement warning and check `success`, `relayTriggered`, state and `errorCode`.
`ERR_NO_SENSOR` and `ERR_RELAY_BUSY` are not transport failures. Secondary relay,
latch duration, restart and key-management operations are omitted.

### BLE boundary

Service `9fb4ffe0-1cc1-4023-a656-5f055d30d35a` and characteristic
`9fb4ffe1-1cc1-4023-a656-5f055d30d35a` carry the separate encrypted BLE channel.
Reported constants include 20-byte chunks and a 512-byte requested MTU, but the
message markers and enrolment are unresolved. No BLE commands are declared.

## Validation and omissions

`scripts/test_remootio_garage_door_spec.py` reproduces the synthetic vector with
standard-library HMAC/JSON handling and the OpenSSL AES equivalent named in the
spec. It also tests tampered MACs, malformed base64/IV/padding, action-ID wrap
and fragmented JSON input. Nothing opens a socket or actuates a relay.

Open work includes an owner-controlled redacted BLE session, reset effects, key
rotation/preservation, Pro/Remootio 1 compatibility and sensor/OTA protocols.

## References

- [Official WebSocket API v3 specification (pinned)](https://github.com/remootio/remootio-api-documentation/blob/d5f3cdd1f51711571065f363081db4295ec76f58/websocket_api_v3_specification.md)
- [Independent Python LAN client (pinned)](https://github.com/ivgg-me/aioremootio/tree/7bf2b4856fe7494d52b2d048e06725504cb366f4)
- [Remootio 3 installation and user manual](https://www.remootio.com/blogs/tutorials/remootio-3-installation-manual), verified on 2026-11-17.
