# June Intelligent Oven — Project July (second generation)

> **Status**: Identify only for generic clients; bespoke protocol reference, untested here
> **Protocol**: Local HTTPS/HTTP REST + signed WebSocket + MJPEG
> **Manufacturer**: June Life; replacement firmware by Project July
> **Manufacturer Status**: June cloud shut down 2026-09-22

## Overview

Project July replaces the software path on a **second-generation June Oven**
(NVIDIA Tegra K1/APX) with the on-oven `june-local` server. The native firmware
provides local companion pairing, preheat and cook control, timers, live status,
presets when installed, and a viewer-gated camera for bespoke clients. Normal
operation does not need June's cloud.

This repository's generic integration is **identify_only**: signed cook controls
are an explicit backlog because the schema cannot safely bind credential-
carrying signed frames, ACK/order correlation and actual-plan sequencing. No
placeholder command or entity bindings are offered. The protocol below remains
an implementation contract for bespoke clients; read-only status and camera
documentation do not imply generic heat-control support.

This page applies only to an oven converted with **installer 0.9.1**. Gen 1 is
still being evaluated by Project July. Gen 3 (JCH03/meerkat, MediaTek) is
blocked and has no compatible installer. For an unconverted oven, see the
separate [stock June Oven guide](june-oven.md); July does not reveal a hidden
local API on stock firmware.

!!! danger "Installer and heat safety"
    Use **0.9.1 only**, never withdrawn 0.9.0. Back up first. The installer
    opens the oven (seven screws), uses micro-USB and SW2/APX recovery, and can
    expose mains-powered internals after reconnection. This project performed
    none of those physical steps.

    **Do not use the stable wireless-update channel on a pre-0.9.1 install.**
    The 2026-11-01 metadata snapshot still named the broken 0.9.0 Chef package.
    Re-check current release metadata before updating. If 0.9.0 was installed,
    restore a verified backup or reinstall 0.9.1; do not factory-reset to fix
    its boot loop.

    Remote preheat starts a heating element. Start only while the oven is
    attended and unobstructed, initially at low temperature, and verify Stop
    against the actual reported plan before creating an automation. Never bypass
    door, food-presence, cleaning or remote-preheat protections.

## Hardware and compatibility

| Property | Value |
|----------|-------|
| Supported hardware | Second-generation June Oven, NVIDIA Tegra K1/APX |
| Required installer | Project July **0.9.1**, build `20261025-1411-b827be42` |
| Not covered | Gen 1 (evaluation), Gen 3 MediaTek/JCH03 (blocked), stock firmware |
| Local listeners | HTTPS 443, HTTP 80; WSS/WS on the same ports |
| Discovery | Shared `_http._tcp.local.` instance `June Local`, normally `june.local`; `june2.local` / `june3.local` for more ovens |
| Cloud requirement | None for local control/camera; project downloads and user-started updates use the internet |

Port 8080 belongs to a development/reference server, not the oven's default.
The DHCP name `June-Oven` identifies only a migration candidate. Neither that
name nor generic `_http._tcp.local.` proves July is running.

## Initial setup

An already converted oven needs CA trust and local pairing. Conversion is a
separate physical route.

### Existing July 0.9.1 installation

| Property | Value |
|----------|-------|
| Setup required | Yes: protocol check, independent CA trust, then exact pairing sequence |
| Method | `button_pairing` after network join |
| Passphrase protection | `not_applicable` for Wi-Fi entry; bearer material and an Ed25519 seed protect local control |
| Confidence | medium (public source and offline tests; not run here) |

1. Browse `_http._tcp.local.` for `June Local`, enter `june.local`, or use the
   oven's IP. On multicast-filtered networks use a local DNS record or IP.
2. **Require** `GET /local/status` to return JSON containing
   `"server":"june-local"` before selecting the protocol. This is only a
   fingerprint: unauthenticated HTTP status and `ca.crt` do not authenticate the
   host or establish a trusted server.
3. Enter only a hostname/IP with an optional scheme and port. HTTPS is the
   default on 443; explicit HTTP uses 80. Reject credentials, non-root paths,
   queries, fragments and malformed ports instead of concatenating them into
   request URLs.
4. Establish CA trust independently:
   - **Connect-by-IP:** obtain the per-home CA from the installer USB, or
     explicitly compare the downloaded CA's SHA-256 fingerprint against
     independently obtained installer material before pinning it. Do not use
     only material from the same unauthenticated endpoint.
   - **Connect-by-name:** pre-pin the known July CA/fingerprint before sending
     credentials. The public CA embedded in the pinned maintained client has
     SHA-256 fingerprint
     `B6:65:DB:2E:74:F4:F8:62:95:14:08:DA:0B:AE:1D:F4:F7:76:AE:77:6F:12:9E:95:73:54:2F:17:A8:AA:A1:B2`.
   `GET /local/ca.crt` is only a convenience copy. Deliberate unauthenticated
   TOFU is a separate lower-security choice with an interception warning, never
   server verification. Keep chain and hostname/IP verification enabled.
5. Register with `POST /2/devices/register`. The body contains fresh random
   32-hex `device_id` and `password`, `device_type=companion`, `device_name`,
   `platform=android`, `version`, and `platform_version`, plus the published
   companion interoperability constants from the pinned open-source client:
   `client_id=dcxqbcv2dY-G12elqDoAhCP8E12V0zC8XWThT-4U` and
   `client_secret=tmoSUwt3OOZCcfMaIadAGD7-x-qPht85HkCgdvuhTKk1yFtfMcfJEyd`.
   These are protocol identifiers, not per-user secrets. Registration has no
   bearer header. The response contains `device_id` and `token.access_token`
   plus refresh material; store them and the new Ed25519/encryption key pairs
   securely.
6. **Before requesting a code**, open
   `wss://<oven>/1/messaging/websocket/companion` with
   `Authorization: Bearer <access_token>` and listen for `10026`/`10027`.
   Use `ws://` only as a separately acknowledged plaintext choice.
7. Send `POST /2/devices/pairing` with the bearer header. The response is
   `{pin:{code,expires,request_id}}`; **`pin.code` is five digits**, and
   `expires` is Unix epoch seconds. Construct the user PIN as
   `five-digit server code + two random decimal digits + one Damm digit`.
   The resulting eight-digit shown PIN, including the Damm digit, initializes
   SRP-6a. The companion acts as the **SRP server**, with the oven as client:
   RFC 5054 8192-bit group, generator 19, SHA-1, identity `user`.
8. Enter the eight-digit shown PIN on the oven's Connect screen. The five-digit
   server code remains the value used in the companion route.
9. Wait for the **first** `10026`, carrying the oven's SRP public `A` in
   `data.key_info.A`. Only then derive `S` and `K = BLAKE2b-256(S)`. Seal
   `companion_info` containing `companion_id`, `companion_name`,
   `public_signing_key`, `public_encryption_key`, `timezone`, and `platform`
   with a fresh 24-byte nonce.
10. Send `POST /2/devices/pairing/{five-digit-server-code}/companion` with the
    bearer header and exactly
    `{key_info:{salt,B,companion_info}}`. Those three fields are nested under
    `key_info`, not top-level fields. A success-only response does not finish
    pairing.
11. Wait for the **second** `10026`, carrying sealed `oven_info` in
    `data.key_info.oven_info`, and open it under `K`. Then send
    `GET /2/devices/{device_id}/associated` with the bearer header and select
    the `devices[]` entry containing the real `oven_id`.
12. Persist `oven_id`, companion ID, bearer material and Ed25519 seed. Only now
    may the pairing mailbox be deleted; deleting it earlier can trigger `10027`.
    Completing pairing does not create generic cook controls in this spec.

### Convert a stock second-gen oven

1. Read the current [Project July setup guide](https://project-july.org/setup/)
   and obtain **0.9.1**. Its published ISO hash is upstream metadata unless you
   independently measure the download.
2. Make a full-eMMC backup and verify both the image and its adjacent `.sha256`.
   Keep that known-good backup independent of the update process.
3. With power disconnected, open the case as the official guide directs. Connect
   micro-USB directly to the installer computer, hold **SW2**, and apply power
   for about ten seconds until the installer reports APX/RCM.
4. Choose **Connect by IP** (recommended) or **Connect by name**, then install
   0.9.1. Reset persistence is a separate explicit choice.
5. Reboot, require the `/local/status` fingerprint, inspect identity/component/
   certificate/update diagnostics, then complete the CA and pairing flow above.

**Factory reset** is not routine troubleshooting. A standard reset can remove
July and return to stock, restoring the dead-cloud problem. It clears paired
companions, logs and media. The persistence option can retain local components,
and 0.8+ identity restoration recreates the oven account row, but clients may
still need to pair again. A reset also restores the installer-baked Chef build,
not the latest wireless-updated one. Never use reset to escape the 0.9.0 boot
loop.

**Rebinding to a new network**: change Wi-Fi from the touchscreen without a
factory reset, then repeat discovery and the status gate. A Connect-by-IP
certificate covers the old IP, so an address change can require new certificate
material or reinstall; use the configured hostname where possible. Companion
pairing is per oven, not per router.

## Pairing and credentials

| Property | Value |
|----------|-------|
| Pairing required | Yes, locally after July installation |
| Security mode | `app_layer` (SRP-6a plus signed frames) |
| Bonding | Persistent per-companion trust |
| PIN source | Five-digit server code + two random digits + Damm digit = eight-digit shown PIN, entered on oven |
| One client at a time | No |
| One bond at a time | No; phones and Home Assistant pair independently |
| Confidence | medium; not replayed here |

Remove one companion from the oven's Connect screen without resetting the
others. Deleting only the app's entry does not revoke the oven-side key.

The bearer material and Ed25519 seed authorize cook commands. Keep them, real
`oven_id`/`device_id` values and the per-install update token out of logs and
fixtures. The CA certificate is public trust material, not a private key.
Plain HTTP still has SRP and frame signatures, but network observers can read
camera and telemetry traffic. Prefer verified HTTPS, especially for video and
updates.

## Local protocol

### Discovery and endpoint security

Use one normalized `scheme://host[:port]` origin for REST, WebSocket and media.
`wss` corresponds to HTTPS and `ws` to explicit plaintext HTTP. Do not silently
fall back to plaintext on a CA or hostname failure.

A `10011` image URL can name June's old cloud host because the oven still uses
the original frame format. Re-home only its `/media/` path and query onto the
configured oven origin. Reject non-media paths and `..` segments; never follow
the embedded host.

### Routes

| Method | Route | Purpose |
|--------|-------|---------|
| GET | `/local` | Real June Local admin/status page. Use `https://{address}/local` after independent CA trust is established; `http://{address}/local` is an explicit unauthenticated plaintext diagnostics fallback, not server verification |
| GET | `/local/status` | Required `server=june-local` protocol fingerprint, not server authentication, plus diagnostics |
| GET | `/local/ca.crt` | Unauthenticated public CA copy over HTTP 80; independently obtained trust material is still required |
| GET | `/local/cook` | Compact JSON; `/local/cook.json` is explicit JSON, `/local/cook.html` or HTML `Accept` is a live page |
| GET | `/1/messaging/device/{oven_id}/status` | Full cloud/July status aliases with `Authorization: Bearer {access_token}` and the associated `credential:oven_id` |
| POST | `/2/devices/register` | Local companion registration, then authenticated companion WSS |
| POST | `/2/devices/pairing` | Create session and return FIVE-digit server code, not the eight-digit shown PIN |
| POST | `/2/devices/pairing/{code}/companion` | Submit nested `key_info` {salt, B, sealed companion_info} after first 10026 public A |
| GET | `/2/devices/{device_id}/associated` | Resolve the real `oven_id` |
| WSS/WS | `/1/messaging/websocket/companion` | Original signed command and telemetry channel |
| GET | `/media/stream.mjpg` | Viewer-gated MJPEG live view |
| GET | `/media/prod/images/latest.jpg` | Still-image fallback |
| POST | `/internal/camera/on?seconds=120`, `/internal/camera/off` | Bounded still-polling viewer gate |

### Full-status aliases

Parse full status with this precedence:

1. `ha_connection_state`: `online` / `offline`.
2. `connection_state`: `connected` / `disconnected`.
3. Boolean `online`.

Prefer `device_state_data` and `cook_plan_data`, falling back to `device_state`
and `cook_plan` only when the preferred value is unusable. Any of those values
can itself be wrapped once in `{ "data": ... }`. Read `food.plan.id` and the
step selected by `step_state.step_index`, not blindly step zero. A completed
cook's cached plan is history, not a live cook.

`/local/cook` instead supplies `success`, `state` (default `idle`), `mode`,
`current_c`, `target_c`, `remaining_seconds`, `door_open`, `probe_c`,
`oven_connected`, `updated_at`, and optional `last_cook`. Temperatures are
**degrees Celsius** and remaining time is **seconds**. Missing optional values
are unknown, not zero. On idle, previous mode/target/ETA/plan/end time appear
only under `last_cook`; never render them as active fields.

### Signed frames are byte-sensitive

The compact frame key order is exactly `v, message_code, order, time,
signature, device_name, device_id, data, target`. The signature is standard
base64 of `BLAKE2b(pubkey, digest_size=8) || Ed25519_sign(canonical_json)` with
`signature` empty during signing: 72 bytes decoded. Use the unchanged
[synthetic June conformance vectors](https://github.com/mvanhorn/printing-press-library)
for SRP, Damm, secretbox and signature checks.

July's relay parses for routing but forwards the **original frame bytes**. Do
not re-marshal JSON in a signed relay path; key order and bytes are part of
signature verification. The oven, not the relay, decides authorization. A bad
signature is silently dropped, so no response is not an explicit refusal.

Signed temperatures are integer milli-°C (`350 F = 176667`) and durations are
milliseconds. Message order is strictly increasing: mask current Unix
milliseconds with `0x7fffffff`, then increment above the previous order when
needed so equal timestamps and the 31-bit wrap cannot repeat an order.

## Cook modes and plan safety

The general climate target is **100–500 °F in 5 °F steps**, narrowed by the
following mode rules. The phone's narrower ranges are shown separately.

| Mode | Temperature / plan | Restart after explicit 11005 refusal? |
|------|--------------------|---------------------------------------|
| `bake` | Phone 170–450 °F, default 350 | Only under the plan rules below |
| `roast` | Phone 250–450 °F, default 400 | Only under the plan rules below |
| `airfry` | Phone 300–450 °F, default 400 | Only under the plan rules below |
| `proof` | 80–110 °F, default 85; needs installed preset content | Only under the plan rules below |
| `dehydrate` | 100–160 °F, default 135 | Only under the plan rules below |
| `broil` | Fixed 500 °F | Never |
| `toast` | Fixed 500 °F; `plan_index` 0–8 = levels 1–9, default 4; plan owns timing | Never |
| `reheat` | Fixed 350 °F; phone timer default 60 min, max 600 | Never |
| `warm` | Fixed 170 °F | Never |
| `pizzaiolo` | Fixed 500 °F | Never |
| `grill` | `plan_index` 0 High/450 °F, 1 Medium/400 °F, 2 Low/275 °F | Never |

Use **`airfry`**, not `air-fry`; normalize the older stored alias. Preset and
guided-cook availability depends on installer content. In particular, Proof is
not supplied by the public payload alone.

For `11004` Stop, `11005` temperature and `11006` timer, always send the
**actual current `food.plan.id`**. Zero is valid only when the oven actually
reported plan zero.

1. Attempt `11005` in place first.
2. A start acknowledgement can precede the new plan report. After `11002`, wait
   for `10014` or suitable `10013` telemetry naming the new plan before Stop,
   timer or temperature commands. Ignore late telemetry from the replaced plan;
   if no new plan arrives, fail locally without sending a plan-targeted command.
3. Only an **explicit `10020` refusal** of `11005` may trigger a restart, and
   only for a phone-startable, restart-eligible mode whose actual plan ID is 0.
   Never cancel/restart a fixed-plan mode, grill, an unknown mode, or a
   touchscreen-originated program (including Proof on plan 114). A timeout,
   disconnect or missing acknowledgement is **not refusal** and never authorizes
   a restart.
4. After an eligible refusal, cancel that actual plan, wait 400 ms, restart the
   same mode at the requested temperature, and wait for the new plan before any
   further plan-targeted command.
5. Preserve `success`, `not-allowed`, `door-open`, `not-ready` and `cleaning`
   distinctly. A definite start refusal restores the old plan; a start timeout
   leaves its outcome unknown.

`10012` with `notification_id=NOTIFICATION_PREHEAT_COMPLETE` marks preheat
completion. Deduplicate it by `session_id` against the plan transition to
`preheat_and_hold`, emitting once per cook session. A plan first seen already
holding after a client restart does not create a new event. Frames can repeat
or arrive out of order: after a later-looking `10016`, an older `10015` must not
move the step or preheat state backward.

## Camera viewer gate

Prefer `/media/stream.mjpg`. An active stream keeps the camera/light gate open
and lets it lapse about 15 seconds after disconnect; duplicate JPEGs are
suppressed at the stock roughly-1-fps cadence. For still polling, call
`/internal/camera/on?seconds=120`, renew about every 100 seconds only while the
viewer is visible, and call `/internal/camera/off` on close.

The stock capture service retains camera ownership. The local bridge connects
only when needed so toast doneness and door-open recognition continue to work;
do not open a competing raw camera device. Cook-time frames normally come from
the oven's own capture path.

## Updates and reset caveats

Wireless updates are user-started outbound HTTPS and cover **Chef app/content
only**, not kernel, boot image, bootloader, system image or full firmware.
Manifest bytes are Ed25519-signed; size, hash and ZIP are checked; monotonic
sequence blocks downgrade/replay; failed apply rolls back. The per-install
update token authorizes one oven but is not the release signing key.

Check/stage controls require verified HTTPS so the token cannot cross the LAN
in plaintext. This spec deliberately exposes no update command: current stable
metadata must be reviewed first, and the historical pre-0.9.1 channel mismatch
is not assumed fixed.

## Tools and evidence

- [x] Offline review of pinned Project July installer/server, Home Assistant
      and mobile source, documentation and sanitized fixtures
- [x] Independent standard-library protocol transcriptions and synthetic tests
- [ ] Physical install, recovery, pairing, heat command, camera or update

Pinned evidence: installer `4672d1ef1b963a062fc1d21fea9776961abd0d0c`, Home
Assistant `be3007bfd9008c216769850cd500dfc3199439dc`, mobile
`85c12e92c5123173b332ebb2e2204c807cf69d82`.

## References

- [Project July installer and release notes](https://github.com/prj-july/installer)
- [Official setup guide](https://project-july.org/setup/)
- [Maintained Home Assistant integration](https://github.com/prj-july/ha-june-oven)
- [Project July mobile app](https://github.com/prj-july/project-july-app)
- [Original synthetic June conformance vectors](https://github.com/mvanhorn/printing-press-library)
- [Stock June Oven guide](june-oven.md)

## Remaining unknowns

Physical installer/recovery behavior, Gen 1 support, any Gen 3 path, exact
preset content per installer, CA behavior on every client and the current
stable-update manifest remain unverified here. No hardware testing is claimed.
