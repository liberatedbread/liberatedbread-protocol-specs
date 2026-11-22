# Coway Airmega Wi-Fi Air Purifiers (Owner-Run Local Server)

> **Status**: Spec Available (unverified)
> **Protocol**: WiFi (JSON over MQTT/TLS, fan-initiated; Bluetooth or hotspot setup)
> **Manufacturer**: Coway Co., Ltd.
> **Manufacturer Status**: Active — the cloud (IoCare+) runs, but the Icon S is discontinued and the cloud route has broken repeatedly

## Overview

Coway's Wi-Fi Airmega purifiers are cloud clients. When the vendor app sets a
fan up, it sends the fan its Wi-Fi credentials **and three server
addresses**: a plain-HTTP URL for the CA certificate the fan should trust, an
HTTPS "certificate server" to enrol at, and a one-time enrolment token. The fan
downloads the CA, enrols, downloads a client certificate and private key, and
learns from the enrolment reply which MQTT broker to use (normally AWS IoT on
port 8883). All control and state then ride JSON messages over
mutually-authenticated MQTT/TLS.

Because those addresses travel inside the setup message, an owner can send the
setup message themselves with their own server's addresses. No DNS override,
no interception and no forged certificate is needed. The owner's server takes
all three cloud roles and the fan never contacts Coway again.
[scottjg/coway-local](https://github.com/scottjg/coway-local) (MIT) is the
working implementation. It is a Home Assistant custom integration that runs
the three listeners, plus a static Web Bluetooth setup page and a shell script
for hotspot-setup units.

**Direction matters.** After setup the fan listens on nothing. It is the HTTP
and MQTT client, so anything that wants to control it has to be its broker.

**Security note.** The fan fetches the CA certificate it trusts over **plain
HTTP**, from whatever URL it was given at setup, and nothing authenticates that
download. That is the owner's redirect mechanism: the URL points at the owner's
own CA, and the fan then trusts only the owner's server. It is also why setup
belongs on a network you control. Keep the three server ports on the trusted
LAN and never forward them from the internet. The spec records this as a
note rather than a `security_advisory`, because an advisory would hide the
very controls this local route provides ([Tom's Hardware's report](https://www.tomshardware.com/tech-industry/cyber-security/dev-hacks-coway-air-purifier-to-cut-it-off-from-the-cloud-now-runs-locally-in-home-assistant-fan-downloads-the-certificate-over-plain-http-letting-a-home-server-stand-in-for-coways)).

## Hardware

| Property | AP-1022K | AP-1720G 02FWK | AP-1720G 02F9R |
|----------|----------|----------------|----------------|
| Retail name | Airmega Icon S (discontinued) | Airmega 250S | Airmega 250S |
| Setup channel | Bluetooth | Bluetooth | Open Wi-Fi hotspot, raw TCP |
| Setup-mode entry | Hold **Mode** (or the fan-speed button) | As AP-1022K | Hold **Filter Reset** + **Wi-Fi** 3 s |
| Firmware seen | MCU `V1.0.0.1`, Wi-Fi `000011` | not recorded | not recorded |
| Reports on | BEvent | BEvent | MEvent |
| Evidence | Protocol source unit | Setup, sensors | Setup, sensors, speed |
| Category | `climate` | | |
| Companion app | Coway IoCare+ (formerly IoCare) | | |

The attribute codes are the AP-1022K's. The 250S's own modes (rapid mode) and
light settings are not mapped. The 02F9R's Wi-Fi modules carry the I&C
Technology prefix `84:72:07`, which is the module vendor's prefix, not a model
identifier.

## Initial Setup

| Property | Value |
|----------|-------|
| Setup required | Yes. The owner's server runs first, then the fan is sent its settings. |
| Method | `ble_provisioning` (primary). The 02F9R hotspot route is typed `none`, because its setup channel is raw TCP. |
| Advertised in setup mode | Manufacturer data under company `0x0639` (byte 1 = `0x40`) or `0xFFFF`. The scan response carries services `ffc0`/`ffc1`/`ffc3`. |
| Passphrase protection | `device_encrypted`: AES-256-CBC, but the key's first 20 bytes travel in the clear one message earlier |
| Server address | Must be fixed. A change of address or port means setting every fan up again. |
| Confidence | medium (coway-local's author ran it; this project has not) |

**What the owner runs.** Three TCP listeners share one fixed LAN address, all
under a CA the owner generates. The ports are coway-local's defaults, and all
three are configurable, because the fan is told them.

| Role | Default | Notes |
|------|---------|-------|
| CA download | HTTP 8080 `GET /ca.pem` | Plain HTTP is the firmware's choice |
| Enrolment + credential download | HTTPS 9443 | `POST certSvrUrl`, then `GET certUrl` / `privateUrl` |
| Broker | MQTT/TLS 9883 | Client certificate required; client ID = serial |

The server certificate needs **both** an IP SAN and a DNS SAN holding the same
IP literal, because the firmware compares an IP host against DNS names. TLS 1.2
with `AES128-SHA256` is required. The enrolment reply must be **compact JSON**:
the 02F9R ignores a reply that contains spaces and keeps re-posting every ~11 s.

**Bluetooth exchange** (GATT service `0000ffc0-0000-1000-8000-00805f9b34fb`).
Read the identity on `ffa0`, a protobuf whose field 2 is the Wi-Fi MAC. Read
the Wi-Fi scan on `ffa1`: `*ICT*SCANRESULT:` followed by 48-byte entries. Then
write to `ffa2`:

```
P001 = "P001" + protobuf{1: 1, 2: base64(K)}           K = 20 bytes
P002 = "P002" + base64(IV + AES-256-CBC(K + MAC12, IV, PKCS#7(settings protobuf)))
```

`MAC12` is the fan's MAC as 12 uppercase ASCII hex digits. The settings
protobuf carries `cmd` 2, `ssid`, `pwd`, `bssid`, `type` 1, `macAddr`,
`caUrl`, `certSvrUrl`, `certToken` and `serial`. Every value on the GATT link
is split into fragments with a 4-byte header: the fragment count, then the
1-based index, each a u16 little-endian. Status arrives on `ffa2` as
`protobuf{1: cmd, 2: ok, 3: code}`. Code 72 means the key was accepted, and
10 / 20 / 40 / 50 / 61 mark the steps up to "broker connected". 52 means the
fan is still retrying the broker.

The hotspot units take the same P001 and P002 messages, without fragment
headers, on TCP 5040 of the fan's fixed hotspot address (the spec's
`gateway_ip`). They take the scan command `AT*ICT*SCAN` on TCP 5001.

**Identity.** The fan uses the `serial` sent in P002 as its MQTT client ID and
as `prodId` in every message. coway-local sends `LOCAL0` followed by the
12-hex-digit MAC, for example `LOCAL000005E00532A` (a documentation-range MAC).

**Factory reset**: none documented (`applicable: unknown`). Removing a fan in
coway-local revokes it on the server but does not reset the fan. New P001/P002
messages replace the old settings.

**Rebinding to a new network**: put the fan in setup mode and send P001/P002
again. The old network need not exist, and a server move is handled the same
way.

## Pairing

| Property | Value |
|----------|-------|
| Pairing required | Yes, as enrolment (no Bluetooth bond) |
| Security mode | `app_layer`: a one-time token at enrolment, then mutual TLS |
| Bonding | `none` |
| One broker at a time | Yes, fixed at setup |
| Confidence | medium |

The fan presents the P002 `certToken` at enrolment and receives a client
certificate. The broker then admits only that certificate, with the fan's
serial as client ID. coway-local makes each token single-use, binds it to one
MAC, and lets it expire after 15 minutes.

## Protocol Summary

Topics, written from the server's side. Every topic has the form
`<prefix>/002AIR007/<serial>`, where `002AIR007` is the `svcCode` from the
enrolment reply.

| Topic | Direction | Carries |
|-------|-----------|---------|
| `IoCare/MControl/…` | server → fan, QoS 1 | Commands and status requests |
| `$aws/rules/AIR/IoCare/BEvent/…` | fan → server | Replies and reports (AP-1022K, 02FWK) |
| `IoCare/MEvent/…` | fan → server | The same messages, from the 02F9R |
| `IoCare/MITG/…`, `IoCare/MITGLWT/…` | fan → server | Unknown content, and the will topic |
| `IoCare/MFota/…`, `IoCare/MCert/…`, `$aws/things/<serial>/shadow/update/delta` | server → fan | Subscribed by the fan, never used locally |

Messages are compact JSON. The `requestId` is 13 digits of epoch milliseconds
followed by `-22`, and the reply echoes it:

```json
{"header":{"requestId":"1767225600002-22","prodId":"LOCAL000005E00532A","API_NO":"A1011"},"attributes":{"A1011.0003":2}}
```

A reply's API number is the request's with the last digit one lower: A1011 →
A1010, A1013 (status request, `{}`) → A1012, and A1051 → A1050. Attribute keys
are single JSON keys that contain a dot.

| Attribute | Meaning |
|-----------|---------|
| `…0001` | Power: 0 off, 1 on |
| `…0002` | Mode: 1 smart, 2 sleep. 0 is read back after a manual speed is set. |
| `…0003` | Manual speed 1–3 |
| `…0007` | Lighting: wire values 1–3 are levels 1–3, and 0 is level 4 |
| `…0008` | Off timer in minutes: 0, 60, 240 or 480 |
| `…000A` | Smart-mode sensitivity: 1 sensitive, 2 moderate, 3 insensitive |
| `A1051/A1050.0001` | Pre-filter cycle: 112 / 168 / 224 = 2 / 3 / 4 weeks |
| `A1020.0001` | PM2.5 in µg/m³ |
| `A1020.0007` | Ambient light in lx (scaling not calibrated) |
| `A1020.0011` / `.0012` | Pre-filter / MAX2 filter **usage** in %. Remaining = 100 − value. |

**Firmware update**: unknown. The fan subscribes to an `MFota` topic, but
nothing about the update protocol, its image or its signing is known. The
spec's `features` entry marks every part of it `unknown`.

`scripts/test_coway_air_purifier_local_spec.py` rebuilds every example in the
spec from its stated rules, using only the standard library (AES included):
P001, the fragments, the settings protobuf, P002 and its decryption, the
identity and scan replies, the status codes, the enrolment exchange, the MQTT
commands and the telemetry decode. All of its values are invented.

See `device-specs/devices/coway-air-purifier-local.yaml` for the full
machine-readable spec.

## References

- [scottjg/coway-local](https://github.com/scottjg/coway-local) (MIT)
- [Scott J. Goldman: Reverse Engineering My Coway Air Purifier to Ditch the Cloud](https://scottjg.com/posts/2026-11-11-reverse-engineering-my-coway-air-purifier-to-ditch-the-cloud/)
- [Tom's Hardware: Dev hacks Coway air purifier to cut it off from the cloud](https://www.tomshardware.com/tech-industry/cyber-security/dev-hacks-coway-air-purifier-to-cut-it-off-from-the-cloud-now-runs-locally-in-home-assistant-fan-downloads-the-certificate-over-plain-http-letting-a-home-server-stand-in-for-coways)
- [Coway Airmega Icon / Icon S (AP-1022K) user manual (PDF)](https://s3.ap-northeast-2.amazonaws.com/coway-app/coway/MANUAL/AP-1022K.pdf)
