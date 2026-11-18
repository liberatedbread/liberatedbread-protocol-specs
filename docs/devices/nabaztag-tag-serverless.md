# Nabaztag/tag with ServerlessNabaztag

> **Status**: Spec Available, untested
> **Protocol**: Wi-Fi, device-local HTTP
> **Integration**: Supported through the declared HTTP command/entity bindings
> **Manufacturer**: Violet / Mindscape hardware; ServerlessNabaztag replacement firmware
> **Manufacturer Status**: Original platform shut down

## Overview

ServerlessNabaztag replacement firmware gives a Nabaztag/tag its own HTTP API.
This guide does not describe the stock rabbit's v1 polling or v2 XMPP protocol,
and it does not cover Karotz. Nothing here has been replayed against hardware.

The spec
[`nabaztag-tag-serverless.yaml`](https://github.com/liberatedbread/liberatedbread-protocol-specs/blob/main/device-specs/devices/nabaztag-tag-serverless.yaml)
contains all 33 paths and 34 operations from OpenAPI 1.1.0. Exact parameter
constraints, form encodings, and responses live under
`protocol_details.openapi.operations`; executable controls use only declared
command parameters and endpoint request/response fields. The replacement project and its
[OpenAPI document](https://github.com/andreax79/ServerlessNabaztag/blob/63e654955aadffeff82786d03d345cd6e910d230/vl/api/openapi.yaml)
are authoritative.

## Initial setup

1. Unplug the rabbit. Hold its head button while restoring power, and release
   when all lights are blue.
2. Join the `Nabaztag<XX>` setup Wi-Fi network and open `http://192.168.0.1`.
3. Under General Info, set **Violet Platform** to
   `andreax79.github.io/ServerlessNabaztag`, without `http://`. The firmware
   appends `/vl` itself.
4. Alternatively, copy the repository's `vl` directory to a trusted plain-HTTP
   server in a directory named `vl` and enter that server's address without a
   scheme.
5. Select Update settings and wait for the rabbit to reboot. Find its DHCP
   address at the router and open `http://<rabbit-address>/`.

The setup page is plain HTTP, so any Wi-Fi passphrase or settings entered there
have no TLS protection. No mDNS or SSDP discovery mechanism is documented for a
provisioned rabbit.

**Rebinding to another network:** repeat the head-button setup sequence and
change the settings. The published flow does not require a factory reset.

**Factory reset:** unknown. The head-button sequence enters setup mode; the
sources do not prove that it erases Wi-Fi settings, scripts, or client state.

## Pairing and access control

OpenAPI declares no security scheme, but the README also mentions optional
simple password protection for web and Telnet without defining its HTTP
exchange. Therefore this spec does **not** claim either that every installation
is open or that a particular header, cookie, or pairing token works. Check the
owner's configuration and do not invent credentials. Telnet on port 22 and its
login settings are outside the HTTP OpenAPI surface.

## Rabbit-local API versus `/vl`

This distinction is load-bearing:

- The **rabbit** serves the root routes below on `http://<rabbit-address>/`.
- The **platform host** serves replacement firmware and resources below `/vl`.
- The rabbit fetches resources from that platform host. It is not the same
  server, and `/vl` is not a prefix for `/status`, `/left`, or other local API
  routes.
- The README also exposes `/openapi.json` on the rabbit and a hosted Swagger UI.
  Those are documentation routes, not additional operations in the OpenAPI
  `paths` object.

Paths and single-letter parameters are case-sensitive. Percent-encode query and
form values once. A color such as `#ff0000` is `%23ff0000` inside an
`application/x-www-form-urlencoded` body, not raw `#ff0000` and not JSON.

## Actions, ears, LEDs, and sound

| Method | Route | Inputs and result |
|---|---|---|
| GET | `/taichi` | Tai Chi choreography; 204 |
| GET | `/left` | Required `p=0..16`, `d=0` forward or `1` backward; 204 |
| GET | `/right` | Same ranges as left ear; 204 |
| GET | `/surprise` | Ear movement and sound; 204 |
| GET | `/stop` | Stop current movement and sound; 204 |
| GET | `/sleep` | Sleep; 204 |
| GET | `/wakeup` | Wake; 204 |
| GET | `/communication` | Play Communication sound; 204 |
| GET | `/ack` | Play Ack sound; 204 |
| GET | `/abort` | Play Abort sound; 204 |
| GET | `/ministop` | Play Ministop sound; 204 |
| GET | `/play` | Required `u`, a plain-HTTP MP3 URL; 204 |
| GET | `/say` | Required `t` text; 204 |

`/stop` stops current movement and sound. `/abort` names a sound effect. Do not
treat either as a universal emergency stop for external tools or AI-invoked
actions.

### LED and service values

| Method | Route | Values |
|---|---|---|
| GET | `/nose` | Required `v`: 0, 1, 2, 3, or 4 |
| POST | `/leds` | Form fields `n`, `l`, `c`, `r`, `b`: `#rrggbb` or `-1` to disable override |
| GET | `/clear` | Clear informational service LEDs |
| GET | `/weather` | Required `v`: 0 through 5 |
| GET | `/stock` | Required `v`: 0 through 6 |
| GET | `/traffic` | Required `v`: 0 through 6 |
| GET | `/pollution` | Required `v`: 0 through 10 |
| GET | `/service4` | Required integer `v`; no published range |
| GET | `/service5` | Required integer `v`; no published range |
| GET | `/mail` | Required `v`: 0 through 3 |

The LED fields are nose, left, center, right, and base respectively. All form
fields are optional, although the request body itself is required. Example:

```text
n=-1&l=%23ff0000&c=%2300ff00&r=-1&b=-1
```

OpenAPI does not assign human labels to the numeric service codes. Preserve the
numbers rather than inventing names. Ear positions are device positions, not
angles, and no ear-position read-back field is published.

## Status and settings

| Method | Route | Purpose |
|---|---|---|
| GET | `/status` | 200 JSON object with current status |
| GET | `/animations` | 200 JSON object of animations grouped by service |
| GET | `/tasks` | 200 JSON object with task state |
| GET | `/setup` | Optional location/language/timezone/sleep settings |
| GET | `/update-time` | Refresh time from configured NTP; 204 |
| GET | `/update-weather` | Refresh weather from configured provider; 204 |

`/setup` accepts optional `j` latitude, `k` longitude, `l` language (`uk`, `it`,
`fr`, `es`, `de`), `c` timezone city code, `d` DST (0/1), `w` wake hour (0-23),
`b` sleep hour (0-23), and `t` Tai Chi frequency (0, 40, 80, or 255).

The three JSON GET responses and `/forth` declare only `type: object`; their
property names are not published. Do not invent status entities from guessed
fields. The README says no AI API credential is exposed through `/status`.

## Advanced operations

- **GET `/reboot`** restarts the rabbit and interrupts activity and network
  availability. It is not a factory reset and requires deliberate owner intent.
- **POST `/forth`** executes arbitrary form-encoded Forth in field `c` and
  returns 200 JSON. Forth can move hardware, alter settings, and reach functions
  outside the safe route catalogue. Review the code and require explicit owner
  intent; do not expose it as an ordinary button.

## Optional AI routes

`GET /ask?t=...` starts an asynchronous AI turn; `t` is limited to 4,000
characters. `GET` and `POST /setup-ai` update non-secret preferences. Both forms
accept the same fields: `e`, `b`, `w` (0/1), `s` (0-255), `r` (2-20), `t`
(15-255), `u` (up to 95), `m` (47), `v` (23), `l` (7), `p` (2047), `o` (95), and
`n` (23), with the character patterns in the spec. POST form encoding is
preferred for the long personality prompt.

The assistant and experimental wake word are disabled by default. A stateful
Node.js + FFmpeg relay on the trusted LAN is required, along with its external
OpenAI connection. The rabbit uses plain HTTP to that relay; the relay uses
TLS/WSS upstream.

**`OPENAI_API_KEY` and `TTS_SIGNING_SECRET` stay only in the relay's protected
environment.** They are never accepted by `/setup-ai`, stored in rabbit flash,
exposed through `/status`, or sent over the rabbit's plain-HTTP hop. Do not add
an API-key parameter to either AI route.

## External dependencies are separate features

| Dependency | Routes | What is not inherently local |
|---|---|---|
| Resource fetch | `/play` | Rabbit fetches a caller-supplied plain-HTTP MP3 URL; use a LAN source for local playback |
| Weather/air quality | `/update-weather`, `/setup` | Rabbit uses open-meteo per README; direct `/weather` and `/pollution` LED writes remain separate |
| NTP | `/update-time`, time-related behavior | Configured time server; its default host is not specified in the reviewed sources |
| AI | `/ask`, `/setup-ai` | LAN relay plus external AI service |
| Firmware/resources | Installation and resource refresh | Rabbit fetches from configured `/vl` platform host, which can be self-hosted |

Basic local actions do not require the old Violet/Mindscape cloud, but these
optional features should not be advertised as offline guarantees.

## Verification

`scripts/test_nabaztag_serverless_spec.py` independently transcribes OpenAPI
1.1.0 and compares every route, method, parameter schema, form encoding, and
response. It also checks percent encoding, range/pattern examples, advanced
markers, setup/rejoin, dependency separation, and the absence of relay-key
fields. No hardware calls are made.

Remaining unknowns include the optional web/Telnet auth exchange, JSON response
properties, numeric code labels, factory-reset scope, NTP defaults, `/say`'s
speech backend, and live compatibility of every operation.

## References

- [ServerlessNabaztag project and setup README](https://github.com/andreax79/ServerlessNabaztag)
- [OpenAPI 1.1.0](https://github.com/andreax79/ServerlessNabaztag/blob/63e654955aadffeff82786d03d345cd6e910d230/vl/api/openapi.yaml)
- [Swagger UI](https://andreax79.github.io/ServerlessNabaztag/vl/api/)
