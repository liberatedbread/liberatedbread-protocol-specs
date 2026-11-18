# Somfy TaHoma Developer Mode

> **Status**: Spec available, untested; executable bearer-HTTPS surface
> **Protocol**: Wi-Fi/Ethernet LAN — mDNS and HTTPS 8443
> **Manufacturer**: Somfy (active)

## Overview

Somfy publishes an official local API for compatible TaHoma gateways. After the
owner enables Developer Mode and generates a token, a client can read the
installation, receive events and execute local commands without ongoing cloud
access.

The **first-generation square TaHoma/Somfy box and Connectivity Kit are
excluded**. Offline activation and activation of an unsupported/unactivated box
are not claimed. The source of truth is
`device-specs/devices/somfy-tahoma-developer-mode.yaml`, pinned to the official
README/OpenAPI at `3eae7a51`.

Unlike the encrypted/session protocols added alongside it, this API uses normal
HTTPS requests and a bearer header, so the generic HTTP surface is executable.
Shade `open`/`close` commands are advanced attended writes; `stop` and execution
cancellation are deliberately not advanced.

## Activation and credentials

1. Install the supported gateway in **TaHoma by Somfy** using Ethernet or a
   secured 2.4 GHz Wi-Fi network.
2. In the installation's box parameters, tap the gateway PIN seven times to
   enable Developer Mode.
3. Generate a token and copy it immediately. Tokens are visible only at creation;
   multiple tokens may be generated.
4. Store the token as a secret. `gateway_pin` is identity, not the token.

Whether activation works completely offline is unproven. The OpenAPI has no token
revocation endpoint, and app-side token deletion was not established. Do not
invent a reset as a token-recovery mechanism.

## Discovery, PIN matching, and TLS

Browse **`_kizboxdev._tcp.local.`**, not `_kizbox._tcp`. TXT records contain:

- `gateway_pin`, in `1234-5678-9012` form;
- `api_version`;
- `fw_version`.

The TXT `gateway_pin` is authoritative. Construct:

```text
https://gateway-<pin>.local:8443/enduser-mobile-web/1/enduserAPI
```

Require the resolved hostname to agree with that PIN. A hostname/TXT mismatch is
an error, not a reason to guess identity from the instance name.

Somfy publishes the **Overkiz Root CA** at
<https://ca.overkiz.com/overkiz-root-ca-2048.crt>. Add or pin that root for the
gateway context and perform normal certificate and hostname verification. Do not
disable verification, use `--insecure`, or substitute the app-bundled Device CA
without separate evidence. The inspected root fingerprint is recorded in the
spec.

## Requests

`GET /apiVersion` is the **only unauthenticated endpoint**:

```http
GET /enduser-mobile-web/1/enduserAPI/apiVersion
```

It returns `{"protocolVersion":"2022.1.3-1"}` in the official example. Every
other endpoint requires:

```http
Authorization: Bearer <owner-token>
```

The implemented request catalogue is:

| Method | Path below `enduserAPI` | Purpose |
|---|---|---|
| GET | `/setup` | Complete installation at startup/resync |
| GET | `/setup/gateways` | Gateway/connectivity description |
| GET | `/setup/devices` | Device URLs, labels, controllables and states |
| GET | `/setup/devices/{deviceURL}/states` | One device's named State array |
| POST | `/events/register` | Create listener, return `id` |
| POST | `/events/{listenerId}/fetch` | Fetch pending events |
| POST | `/events/{listenerId}/unregister` | Orderly listener cleanup |
| POST | `/exec/apply` | Apply non-persistent action group, return `execId` |
| GET | `/exec/current` | List current local executions |
| GET | `/exec/current/{executionId}` | Query one local execution |
| DELETE | `/exec/current/setup/{executionId}` | Cancel one local execution |
| DELETE | `/exec/current/setup` | Cancel all local setup-level executions |

URL-encode a `deviceURL` exactly once when placing it in a path. State is an array
of named typed records; find entries by `name`, not position. For the declared
cover, `core:OpenClosedState` carries the string `open` or `closed`. Other state
values can be numeric or boolean and must not be coerced blindly.

## Listener lifecycle

At startup, fetch `/setup` once and register a listener. Fetch events **at most
once per second**, but often enough to keep the listener alive. A listener is
destroyed after **10 minutes of inactivity** and when the gateway reboots.

Unregister on orderly shutdown. On an invalid-listener `400`, register a fresh
listener and rebuild state from `/setup`; do not continue silently with a dead
ID. Event-driven updates avoid overloading the gateway with repeated setup polls.

## Executions and cover safety

An action group contains one or more device commands:

```json
{
  "label": "Attended cover open",
  "actions": [
    {
      "deviceURL": "io://2001-0000-0000/1000001",
      "commands": [{"name": "open", "parameters": []}]
    }
  ]
}
```

The returned `execId` acknowledges an execution, not physical completion. Query
current executions and follow device/execution events. Use the matching cancel
endpoint or a `stop` command to halt movement.

Opening and closing require an attended user, confirmed device URL/direction and
a clear travel path. Stop and cancellation remain directly available. The spec
does not infer position, tilt, or arbitrary commands for every Somfy product;
instantiate only from the installation's actual controllable and state support.

## Reset and changing networks

No official Developer Mode source establishes a physical factory-reset sequence
or which tokens, network settings and paired products survive it. The seven-tap
developer gesture and motor pairing/reset are not gateway factory resets.

Use the official app to change networks. Rediscover and require the same TXT PIN
before reusing a token; a different PIN is a different gateway, not a routine
address change.

## Verification

`scripts/test_somfy_tahoma_developer_mode_spec.py` starts a local standard-library
HTTP stub and makes real `urllib` requests for version, devices, listener
register/fetch/unregister, action apply, execution query and cancellation. It
checks bearer presence/absence, request/response JSON, listener timing/recovery,
PIN mismatch rejection, Overkiz trust settings and advanced movement boundaries.
No external network or real token/gateway is used.

## References

- [Official Developer Mode project at 3eae7a51](https://github.com/Somfy-Developer/Somfy-TaHoma-Developer-Mode/tree/3eae7a51ba55eee28649319942239aab7b139eb7).
- [Official local OpenAPI](https://github.com/Somfy-Developer/Somfy-TaHoma-Developer-Mode/blob/3eae7a51ba55eee28649319942239aab7b139eb7/docs/openapi.yaml).
- [TaHoma Switch installation guide](https://asset.somfy.com/Document/105bf554-3ac5-4646-8288-4151f5a43c5c_TaHoma_switch_installation_guide_EN.pdf).
