# TP-Link Tapo and KLAP-era Kasa plugs

> **Status**: Spec available, untested; identify-only in the generic app
> **Protocol**: Wi-Fi LAN — UDP TDP discovery and encrypted HTTP
> **Manufacturer**: TP-Link (active)

## Overview

This guide covers Tapo plugs and Kasa-era plugs whose discovery reply selects
**KLAP** or the older **securePassthrough/AES** transport. Legacy Kasa plugs
speaking JSON over TCP 9999 use the [existing Kasa guide](tplink-kasa.md).
Cameras, bulb-specific controls, hubs and TPAP-only firmware are out of scope.

The machine-readable source of truth is
`device-specs/devices/tplink-tapo-klap.yaml`. The generic integration is
`identify_only`: no dedicated TDP/KLAP/passthrough consumer currently exists.
A generic HTTP client must not send the documentary plaintext command bodies.

## Discovery and transport selection

Send the same TDP v2 discovery request to **UDP 20002 and 20004 in parallel**.
The 16-byte header is big-endian. Broadcast uses flags `0x11`; a unicast probe
uses `0x21`. Before calculating CRC32, put `5a 6b 7c 8d` in the CRC field, then
replace that placeholder with the big-endian CRC of the complete packet.

A dedicated TDP codec must first require the version/opcode/serial and exact
payload length, then restore the placeholder and verify CRC, and only then decode
the JSON payload. The generic UDP binary reader cannot skip the header or resolve
`binary:result.*` paths, so the spec deliberately declares **no discovery identity
mapping**. Header-first decoding and transport selection require the custom handler.

The JSON reply identifies the device and advertises its management transport:

- `KLAP` selects the two-handshake encrypted HTTP protocol below;
- `AES` selects RSA-wrapped securePassthrough;
- a `tpap` object belongs to the separate reported TPAP appendix.

Do not try TPAP after a KLAP failure, and do not infer a device class from an
open port or TP-Link address prefix.

## KLAP v1 and v2

KLAP posts raw bytes to `/app/handshake1`, `/app/handshake2`, and
`/app/request?seq=<n>`. Keep the `TP_SESSIONID` cookie from handshake 1 for all
later calls.

1. Send a fresh **16-byte local seed**. The response must be exactly 48 bytes:
   a 16-byte remote seed and a 32-byte device proof.
2. Verify the device proof, then send the client proof in handshake 2.
3. Derive the AES key, signature key and IV prefix from the two seeds and the
   authentication hash. The labels are `lsk`, `ldk`, and `iv`.
4. Increment the sequence, put its unsigned big-endian uint32 representation in
   the URL, IV suffix and signature. AES-128-CBC with PKCS#7 protects the JSON.
   The wire body is `SHA256(sig || seq || ciphertext) || ciphertext`.

The credential and proof difference is important:

| Version | Authentication hash | Device proof | Client proof |
|---|---|---|---|
| v1 | `MD5(MD5(user) || MD5(password))` | `SHA256(local || auth)` | `SHA256(remote || auth)` |
| v2 | `SHA256(SHA1(user) || SHA1(password))` | `SHA256(local || remote || auth)` | `SHA256(remote || local || auth)` |

All inner digests are raw bytes, not hexadecimal text. Both versions use
SHA-256 for the seed proofs and request signatures.

On **HTTP 403**, invalidate the session and perform both handshakes again with a
new local seed. Retry an idempotent read once. For a relay write, first
reconcile `device_on`; a timeout is not proof that the write did not happen.
Serialize requests because out-of-order sequence tolerance is unknown.

## Older securePassthrough

Older firmware posts JSON to `/app`:

1. Generate an **RSA-1024** key pair and send the public key in `handshake`.
2. RSA-PKCS#1-v1.5-decrypt `result.key`. The 32-byte plaintext is a 16-byte AES
   key followed by a 16-byte IV.
3. Encrypt `login_device` using AES-128-CBC/PKCS#7 and Base64, then retain the
   returned token.
4. Post `securePassthrough` to `/app?token=<token>`, with the inner JSON in
   `params.request` as Base64 AES-CBC ciphertext. Decrypt `result.response`
   with the same session key and IV.

Select the login shape from `mgt_encrypt_schm.lv`: only `lv == 2` uses
`password2` with SHA-1 hexadecimal password material; every other advertised
value uses the older Base64 `password` field. Do not switch versions merely to
retry a failed login.

The RSA public key is SubjectPublicKeyInfo DER encoded as unwrapped Base64 inside
the two PEM markers. Serialize the handshake as compact UTF-8 JSON with no added
whitespace and set `Content-Length` to the exact body byte count; it is required,
and some devices answer 500 without it. The synthetic RSA-1024 vector in the spec
reproduces the reference implementation's **314-byte** body. Do not use chunked
transfer encoding. Send `Content-Type` and `Accept` as `application/json`,
`requestByApp: true`, and the `/app` Referer.

Retain `TP_SESSIONID` after the handshake, falling back to `SESSIONID` when that
is what the device supplied; normalize it into `TP_SESSIONID` on login and every
secure request. Read `TIMEOUT` in seconds and refresh at
`monotonic_now + TIMEOUT - 1200` (a 20-minute skew buffer), defaulting to 86400
seconds only when absent. Never return `TIMEOUT` as the session cookie.

AES session recovery is **independent of KLAP's 403 handshake**. Require HTTP
200 for RSA handshake, login and passthrough; non-200 is a transport failure, not
an automatic AES refresh classification. The pinned implementation tests HTTP 400
as a failure without default-credential retry, so this spec does not invent
401/403 mappings.

Only these application codes trigger one bounded RSA handshake **and**
`login_device` with the accepted account credential: **9999** session timeout,
**1111** login failed, **1100** handshake failed, **1003** unknown credentials,
**-1501** login error, **-1005** AES decode failure, **-40412** HomeKit login
failure, and session-specific **-40401** session expiry / **-40413** invalid
nonce. Invalidate token/cookie/cipher first, then retry an idempotent read once
and stop on any failure. Every other application error performs no RSA
handshake/login and is surfaced unchanged; outer transport-retry codes 1002,
1112 and -1001 are not RSA reauthentication either.

For a relay write, first read `device_on`: skip if it already has the desired
value, issue at most one write if it differs, and do not write when state cannot
be read.

The spec publishes the exact encodings and synthetic RSA/AES vectors; it contains
no real account key or credential.

## Controls and energy boundary

Use `component_nego` to discover capabilities and `get_device_info` to read
identity and `device_on`. Relay writes use `set_device_info` with a boolean
`device_on`. They are **advanced, attended operations**: mains equipment can
start, move, heat, or lose power without its own safe shutdown. Read back the
actual relay state.

Energy monitoring is **advertised only**. Method names such as
`get_energy_usage` and `get_current_power` are recorded, but this version does
not claim their per-model response fields or V/A/W/kWh scaling and exposes no
meter entity.

## Setup, reset, and replacing a router

Initial setup uses the Tapo app and a TP-Link ID. A reset plug may advertise
`Tapo_Plug_XXXX`, with `192.168.0.1` as the setup-side address. Day-to-day local
control then needs no cloud request, but it does need the account credential
accepted by the device. This is not universal cloud-free onboarding or a way to
recover an unknown credential.

The official P110 guide distinguishes two holds on its Power button:

- **5 seconds**: reset Wi-Fi while preserving other settings. Use this for a
  router replacement.
- **10 seconds**: restore factory defaults and re-enable setup mode. Rebind the
  plug and expect local authorization to change.

Blinking orange and blue indicates readiness for setup. Exact behavior on other
models must come from that model's own manual rather than this P110 procedure.

## Reported TPAP appendix

Newer firmware can advertise TPAP over **HTTPS 4433**, with SPAKE2+ login and
`/stok=<stok>/ds` application framing. In the reviewed plug/IoT app, TPAP uses a
passcode exchange; SPAKE2+ does **not** inherently mean a cloud-issued NOC is
required. That statement is not a promise for every family or future firmware.

`extra_crypt`, passcode composition, DAC handling and CCM additional authenticated
data remain unresolved. The appendix is deliberately non-executable and does
not delay or weaken the complete KLAP implementation notes.

## Verification

`scripts/test_tapo_klap_spec.py` independently reconstructs the fixed-seed v1/v2
proofs and encrypted sessions, header-first TDP broadcast/unicast CRC packets,
314-byte RSA handshake, RSA key wrap and AES passthrough envelope using only the
standard library and the OpenSSL command-line AES primitive. It separately checks
KLAP 403 rehandshake and AES handshake+login recovery, exact recovery-code and
non-200 gating, cookie normalization and TIMEOUT expiry, bounded failure and
relay-state reconciliation. No hardware operation is claimed.

## References

- [python-kasa](https://github.com/python-kasa/python-kasa), the recommended
  maintained client and protocol cross-check.
- [Tapo P110(US) user guide](https://static.tp-link.com/upload/manual/2024/202402/20240226/Tapo%20P110(US)1.0&1.6_UG_V1.pdf),
  the source for setup, reset and safety details.
