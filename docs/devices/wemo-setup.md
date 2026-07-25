# Wemo Setup, Factory Reset and Rebinding

> **Status**: In Progress — flow documented from public implementations, not yet replayed against hardware
> **Applies to**: every Wemo device family in [the catalog](wemo-devices.md)
> **Prerequisite**: none — the Belkin cloud is not involved at any point

[Discovery and control](wemo-devices.md) assume a Wemo device is already on your
WiFi. This page covers how it got there, and — the case that matters now that
the Wemo cloud is gone — how to move a device to a *different* network without
the vendor app.

The good news: Wemo provisioning is entirely local. The device hosts its own
access point and takes credentials over the same SOAP 1.1 stack it uses for
normal control. Nothing in the flow requires Belkin's servers, which is why
Wemo hardware remains recoverable after the January 2026 shutdown.

!!! warning "Confidence"
    Service and action names are **high** confidence — they appear in the
    device's own `setup.xml` service list and in the public
    [pywemo](https://github.com/pywemo/pywemo) and
    [wemosetup](https://github.com/vadimkantorov/wemosetup) implementations.

    The passphrase encryption derivation and the exact `ApList` field order are
    **medium** confidence: taken from the public wemosetup implementation and
    not yet replayed against hardware in this project. `scripts/wemo_setup.py`
    prints raw device responses so you can check them against this page — if
    they differ, that is a finding worth filing.

## When you need this

| Situation | What to do |
|---|---|
| New or factory-reset device | Full provisioning flow below |
| Moving to a new router, old network still up | [`ReSetup`](#rebinding-to-a-new-network) — no physical reset needed |
| Moving to a new router, old network already gone | Factory reset, then full provisioning |
| Device stuck on an SSID you no longer control | Factory reset, then full provisioning |
| Device works but you want a different name | `basicevent#ChangeFriendlyName` — not a setup operation |

The one piece of timing advice worth acting on: **if you are replacing a
router, re-provision your Wemo devices before the old SSID goes away.**
`ReSetup` needs the device to still be reachable. Once the old network is down,
every device drops to a physical factory reset, which for in-wall switches
means getting at the Restore button behind the faceplate.

## Factory reset

A reset clears the stored WiFi credentials, the friendly name, and any local
rules or timers, then reboots the device into setup mode. The UDN, serial
number and MAC address are hardware identity and survive — so a device keeps
its stable discovery keys across reprovisioning, and anything storing per-device
state will still recognise it afterwards.

### Plug-style devices (Mini, Smart Plug, Insight, Outdoor)

The Restore button must be held **while power is applied**. Pressing it on a
running device does not reset it, which is the usual reason people conclude
their device is dead.

1. Unplug the device from the outlet.
2. Press and hold the Restore button.
3. Plug the device back in, still holding.
4. Keep holding for about 5 seconds after power is applied, then release.
5. Wait up to 90 seconds for the reboot to finish.

### In-wall devices (Light Switch, Dimmer)

Power stays on at the breaker; the button does the work.

1. Leave the switch powered.
2. Press and hold the Restore button on the device body for about 10 seconds,
   until the status LED changes pattern.
3. Wait up to 90 seconds for the reboot.

### Confirming it worked

Do not trust the stopwatch — hold times vary by generation and vendor
documentation is inconsistent. The reliable confirmation is that an **open
`Wemo.*` WiFi network reappears** in a scan:

```bash
# Linux
nmcli device wifi rescan && nmcli -f SSID,SECURITY device wifi list | grep -i wemo

# macOS
/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport -s | grep -i wemo
```

Observed names follow `<Family>.<Class>.<3 chars>`, with the case of the first
token varying across firmware: `WeMo.Switch.A1B`, `Wemo.Mini.4A2`,
`WeMo.Insight.7C4`. Match case-insensitively on `wemo.` rather than on any
single spelling.

## Provisioning flow

Once the setup AP is up, the device is at **`10.22.22.1`**, serving HTTP on the
usual Wemo port range (49152–49153 in setup mode).

```text
  ┌────────────┐   join open AP    ┌──────────────┐
  │  client    │ ────────────────▶ │ Wemo in      │  10.22.22.1:49153
  │            │                   │ setup mode   │
  └────────────┘                   └──────────────┘
        │ 1. GET /setup.xml                  → identity + service control URLs
        │ 2. metainfo#GetMetaInfo            → key material for the passphrase
        │ 3. WiFiSetup#GetApList             → networks the device can see
        │ 4. WiFiSetup#ConnectHomeNetwork    → SSID + encrypted passphrase
        │ 5. WiFiSetup#GetNetworkStatus      → poll until connected
        │ 6. WiFiSetup#CloseSetup            → leave setup mode
        ▼
   rejoin your own network, rediscover by SSDP
```

### 1. Read the device description

```bash
curl -s http://10.22.22.1:49153/setup.xml
```

Take the control URLs from the `serviceList` rather than hardcoding them. Both
`/upnp/control/WiFiSetup1` and `/upnp/control/wifi1` have been reported for
`urn:Belkin:service:WiFiSetup:1` across firmware generations; `setup.xml` is
authoritative for the device in front of you.

### 2. Read the metadata that keys the passphrase encryption

`urn:Belkin:service:metainfo:1#GetMetaInfo` returns a pipe-delimited
`MetaInfo` string. Fields 0 and 1 supply the key material:

```text
keydata = meta[0][0:6] + meta[1] + meta[0][6:12]
salt    = keydata[0:8]      # first 8 bytes
iv      = keydata[0:16]     # first 16 bytes
```

### 3. Ask the device what it can see

`urn:Belkin:service:WiFiSetup:1#GetApList` returns an `ApList` string, one
entry per line, carrying the SSID, channel, auth mode, cipher and signal
strength. Use the device's own values verbatim in the next step — a network the
device can see will still be rejected if the auth string does not match its
vocabulary.

### 4. Encrypt the passphrase and send the credentials

The passphrase is AES-128-CBC encrypted with a key derived from the device
metadata, using OpenSSL's legacy MD5-based `EVP_BytesToKey` derivation, then
encoded in a Wemo-specific way:

1. Encrypt with `aes-128-cbc`, `-md md5`, the salt and IV above, and `keydata`
   as the passphrase.
2. Strip OpenSSL's 16-byte `Salted__` + salt header from the ciphertext.
3. Base64-encode the remainder.
4. Append the hex-encoded length of that base64 string, then the hex-encoded
   length of the original plaintext passphrase.

Then call `ConnectHomeNetwork` with `ssid`, `auth`, `password` (the blob above),
`encrypt` and `channel`.

!!! danger "This is obfuscation, not encryption"
    Every input to the key derivation comes from `GetMetaInfo`, which the
    device serves to anyone on its open setup AP without authentication. The
    scheme stops a passive listener from lifting your passphrase off the air;
    it provides no protection against anyone who bothered to read this page.
    Implement it exactly — the device rejects anything else — and do not treat
    it as a security boundary.

### 5. Poll the result

`GetNetworkStatus` returns `NetworkStatus`; `1` indicates a successful join.
Poll it rather than assuming — without this step you cannot tell a wrong
passphrase from a slow DHCP lease, and the device is about to become
unreachable either way.

### 6. Close setup and rediscover

`CloseSetup` drops the setup AP and moves the device onto your network. Rejoin
your own WiFi and rediscover by SSDP — the device now has a completely
different address, so match on UDN, serial or MAC, never on IP:

```bash
python scripts/wemo_discover.py --timeout 5
```

## Using the tool

`scripts/wemo_setup.py` implements the flow above. It is **dry-run by
default** — every subcommand prints the SOAP it would send and stops there
unless you pass `--execute`.

```bash
# Confirm you are on the setup AP and the device is answering
python scripts/wemo_setup.py info --execute

# See the networks the device can find (prints the raw ApList too)
python scripts/wemo_setup.py list-aps --execute

# Hand over credentials. Values come from the list-aps output.
python scripts/wemo_setup.py connect \
    --ssid "HomeNetwork" --auth WPA2PSK --encrypt AES --channel 6 --execute

# Check the join, then release the device onto your network
python scripts/wemo_setup.py status --execute
python scripts/wemo_setup.py close --execute

# Push a device that is still on the old network back into setup mode
python scripts/wemo_setup.py resetup --device 192.168.1.42:49153 --execute
```

The passphrase is read from the `WEMO_WIFI_PASSWORD` environment variable, or
prompted for without echo. It is never printed, never logged, and never written
to a file — including in dry-run output, where the encrypted blob is shown as a
placeholder.

Encryption is performed by the `openssl` command-line tool, which must be on
your `PATH`. Python's standard library has no AES implementation, and this
repository's tooling deliberately has no third-party runtime dependencies.

## Rebinding to a new network

`urn:Belkin:service:basicevent:1#ReSetup` pushes a provisioned device back into
setup mode over the LAN, without a physical reset. This is the answer to "my
router changed and my Wemo is in the ceiling".

```bash
python scripts/wemo_setup.py resetup --device 192.168.1.42:49153 --execute
```

Two caveats worth stating plainly:

- **It clears the stored credentials immediately.** If the reprovisioning that
  follows fails, the device is sitting in setup mode, not back on the old
  network. Have the new SSID and passphrase to hand before you run it.
- **It only works while the device is reachable.** It is a LAN call. Once the
  old network is gone, so is this option.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| No `Wemo.*` network after a reset | Button was not held *through* power-on (plug devices), or the hold was too short. Watch the LED, not the clock. |
| `ConnectHomeNetwork` accepted, `GetNetworkStatus` never reaches 1 | Wrong passphrase, or the SSID is 5 GHz-only. Every Wemo radio is 2.4 GHz. |
| Join fails on a network the device listed | `auth`/`encrypt`/`channel` do not match the `ApList` entry — send back the device's own strings verbatim. |
| Setup AP visible but HTTP times out | Client fell back to cellular or another interface. Pin the route to the 10.22.22.0/24 subnet. |
| Device joins, then never appears in SSDP | Client AP isolation, or a router that blocks multicast between wireless clients. |
| Device appears, then disappears, on a different port | Normal. Wemo ports move across 49152–49159; rediscover rather than caching the port. |
| Everything works, then breaks after a power cut | Also normal, same cause. Never store the port as identity. |

## References

- [pywemo](https://github.com/pywemo/pywemo) — device classes and SSDP handling
- [pywemo `wifi_setup.py`](https://github.com/pywemo/pywemo/blob/main/pywemo/ouimeaux_device/api/wifi_setup.py) — WiFiSetup service surface
- [wemosetup](https://github.com/vadimkantorov/wemosetup) — the public implementation of the passphrase encryption
- [ouimeaux](https://github.com/iancmcc/ouimeaux) — pywemo's lineage
- [Wemo device catalog and control](wemo-devices.md)
- [Initial Device Setup](../protocols/device-setup.md) — the cross-device patterns
- Machine-readable spec: `device-specs/devices/wemo-devices.yaml` (`device.setup`)
