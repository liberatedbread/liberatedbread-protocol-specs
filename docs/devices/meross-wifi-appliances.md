# Meross Wi-Fi plugs, switches, and MSG100 garage opener

> **Status**: Spec available, untested; identify-only in the generic app
> **Protocol**: Wi-Fi LAN — UDP discovery, signed/encrypted HTTP JSON
> **Manufacturer**: Meross (active)

## Overview

The same Meross envelope covers plugs/switches using `ToggleX` and the MSG100
using `GarageDoor.State`. It runs on `POST /config` on the LAN and on the
device's setup AP at **10.10.10.1**. This version does not cover bulbs,
thermostats, hubs, BLE-only sensors, roller shutters, or Matter.

The authoritative details and synthetic vectors are in
`device-specs/devices/meross-wifi-appliances.yaml`. Generic integration is
`identify_only` until a dedicated signed-envelope/Encrypt.Suite handler exists.

!!! warning "Garage doors and mains loads"
    `GarageDoor.State` can move a door without line of sight. Its contact sensor
    is not a safety interlock. Closing requires an attended user, a clear and
    watched opening, and working opener safety systems. ToggleX writes are also
    advanced, attended operations because they energize or remove mains power.

## Discovery

Bind the client to **UDP 9989**, then send this JSON to
`255.255.255.255:9988` once per second for five sends:

```json
{"id":"<md5(userid)>","devName":"*"}
```

Listen for five seconds. A reply carries `uuid`, `ip`, `port`, `mac`, `devName`,
`deviceType`, and hardware/firmware fields. Match UUID and MAC to the intended
account/device before sending any command. The vector in the spec uses invented
userid `123456`, whose MD5 is `e10adc3949ba59abbe56e057f20f883e`.

## Signed message envelope

Plaintext requests are JSON objects with `header` and `payload`. Important header
fields are:

- `messageId`: 32 lowercase hex characters;
- `timestamp`: integer epoch seconds;
- `sign`: `MD5(messageId || account_key || timestamp)`;
- `method`: `GET` or `SET` (`GETACK`, `SETACK`, `PUSH`, `ERROR` in replies);
- `namespace`: the full `Appliance.*` name;
- `payloadVersion`: `1`;
- `from`: the full local `/config` URL;
- `uuid`: the target device UUID.

Correlate before decrypting or applying state. A normal reply must carry the
**exact outstanding `messageId`**, the expected full `namespace`, and `GETACK`
for a GET or `SETACK` for a SET. Only then verify its signature and bound UUID,
and only after those checks consume its payload. A stale reply with a valid
signature still fails.

Handle `ERROR` separately: correlate its ID/namespace, verify signature/UUID,
then surface `payload.error.code` instead of treating it as an ACK or normal
payload. Handle `PUSH` separately as an unsolicited state notification, never as
completion of an in-flight command. If the exact ID is missing or no matching
request is outstanding, reject the reply and serialize the next request with a
fresh ID rather than matching by arrival order. HTTP success alone is not command
success, and MD5 signing does not supply modern replay protection.

## Encrypt.Suite

When `Appliance.System.Ability` advertises `Appliance.Encrypt.Suite`, negotiate
it in cleartext. For a bound device, this version supports the reported
`ecdhe256` / `mrskey` suite:

- key material is `uuid[3:22] || key[1:9] || mac || key[10:28]`;
- the AES-256 key is the 32 ASCII characters of that material's MD5 hex digest;
- AES-CBC uses sixteen ASCII `0` characters as IV;
- append zero bytes to a 16-byte multiple, even when the input is aligned;
- send the raw Base64 ciphertext as the HTTP body, with no MAC.

`System.All`, `System.Firmware`, `System.Ability`, `Encrypt.Suite`, and
`Encrypt.ECDHE` stay cleartext. Do not encrypt those namespaces. The setup-side
ECDHE reply is unresolved, so this bound-device derivation is not a setup bypass.

## Commands

`Appliance.Control.ToggleX` uses:

```json
{"togglex":{"channel":0,"onoff":1}}
```

`onoff=0` turns channel zero off. Read `Appliance.System.All` afterward rather
than assuming success.

MSG100 state uses `GET Appliance.GarageDoor.State` with
`{"state":{"channel":0}}`. An attended write includes the bound UUID:

```json
{"state":{"channel":0,"open":1,"uuid":"<device-uuid>"}}
```

Use `open=0` to request close. The acknowledgement is not proof of physical
completion; monitor the actual contact state and the door itself. Never use this
surface for unattended closing.

## Credentials and provisioning

There are two legitimate but different paths:

1. **Stock account setup.** Add the device in the Meross app and retain the
   account user ID/key. Established LAN requests need no cloud round trip.
2. **Owner-selected Config.Key on supported legacy setup AP firmware.** Choose a
   new user ID/key and a compatible owner-controlled MQTT broker, then provision
   `Appliance.Config.Key` before Wi-Fi. That selected key subsequently signs LAN
   messages and feeds Encrypt.Suite derivation.

The second path does **not** recover an existing stock key, authorize an unknown
device, or work universally on hardware that requires setup-side ECDHE. It is a
deliberate rebind that requires updating every client. `Config.Key` also does not
set the Wi-Fi SSID; `Config.Wifi`/`Config.WifiX` is a separate step.

## Reset and changing networks

No single physical factory-reset procedure or state-survival rule is asserted
across MSS switches and MSG100. Use the exact model's linked guide. Setup/pairing
mode is not automatically a full reset, and a short relay press is not a reset.

For a router change, enter the model's setup flow and provision Wi-Fi again.
Retain verified stock account material, or deliberately choose replacement
`Config.Key` material only on a supported legacy AP. Rediscover by UUID/MAC and
update clients if the shared key changed.

## Verification

`scripts/test_meross_wifi_appliances_spec.py` reconstructs the MD5 signature,
AES-256-CBC/zero-padding vector, UDP probe and identity binding, Config.Key
payload, ToggleX messages, and garage open/close writes. It also checks the
cleartext exemptions, advanced safety gates, stock-versus-owner-selected
credential boundary, and stale-ID/wrong-namespace/wrong-ACK/signature/UUID,
ERROR and PUSH handling using no network or real key.

## References

- [meross_lan](https://github.com/krahabb/meross_lan) and
  [MerossIot](https://github.com/albertogeniola/MerossIot), maintained client
  implementations.
- [Custom-Meross-Pairer at 29cb6c6](https://github.com/albertogeniola/Custom-Meross-Pairer/tree/29cb6c64c07875c48ba1de1a32e7f4b30b543a01),
  bounded legacy AP provisioning evidence.
- [MSS110 user guide](https://d386u2e9lj99mt.cloudfront.net/public/staticfile/1688528473196/8122798.pdf)
  and [MSG100 user guide](https://d386u2e9lj99mt.cloudfront.net/public/staticfile/1688608956001/6946162.pdf).
