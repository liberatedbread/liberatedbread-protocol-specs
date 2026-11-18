# FIXD OBD adapter transport identities — IDENTIFICATION-ONLY RESEARCH

**Status:** reported, unverified, and deliberately not a device specification or
client implementation. No adapter, vehicle, VIN, diagnostic session or packet
capture was used. This note has **no setup or pairing flow, reset procedure,
executable GATT service declaration, adapter commands, capabilities, or
diagnostic requests**.

Do not resolve these profiles to `obd2-bluetooth-adapter.yaml` or any other
executable OBD profile. The generic family's ATI setup, ATZ/ATD reset, FFF2
configuration commands, capability tiers and ELM327 requests are not evidence of
FIXD compatibility.

## Evidence

Static analysis of FIXD OBD2 Scanner `com.fixdapp.two` version 26.22
(versionCode 2026102222), reviewed on 2026-11-10. The app maps the hardware
profiles below to transport identities. Profile identifiers and display names
are app metadata, **not observed BLE local names or Bluetooth Classic inquiry
names**. FFF0 is shared with unrelated devices and is not scan-time identity.

## Reported BLE identities

These six profiles map to the following UUID roles:

- Service: `0000fff0-0000-1000-8000-00805f9b34fb`
- Characteristic labeled read by the app:
  `0000fff1-0000-1000-8000-00805f9b34fb`
- Characteristic labeled write by the app:
  `0000fff2-0000-1000-8000-00805f9b34fb`

| App hardware profile | Display name | Reported transport identity |
|---|---|---|
| `FIXD2` | FIXD2 | BLE FFF0/FFF1/FFF2 |
| `SETOSMART` | FIXD | BLE FFF0/FFF1/FFF2 |
| `VIECAR` | FIXD | BLE FFF0/FFF1/FFF2 |
| `VIECAR_V2` | FIXD | BLE FFF0/FFF1/FFF2 |
| `APPRAISAL_PRO` | Appraisal PRO | BLE FFF0/FFF1/FFF2 |
| `VIECAR_AUTHENTICATED` | Auto Assist | BLE FFF0/FFF1/FFF2 |

The read/write labels do not establish GATT properties. In particular, FFF1
might be polled, notified or both; initialization and FFF2 behavior are unknown.

## Reported legacy identity

`OLD_KICKSTARTER`, displayed as `OBDII`, has no BLE triple in the app profile.
The app separately uses standard Serial Port Profile UUID
`00001101-0000-1000-8000-00805f9b34fb` for this legacy profile. This is not
evidence that other FIXD sensors support SPP. Pairing, socket security and the
payload session remain unknown.

## Unresolved and prohibited inferences

- Advertised names, full GATT properties and a model discriminator are unknown.
- Initialization, notification subscription, flow control and multi-frame
  response reassembly are unknown.
- ELM327 command/session compatibility is unknown. No ATI, ATZ, ATD, ATSP,
  Mode 01, Mode 03, ISO-TP, VIN, trouble-code or ECU operation is sanctioned by
  this note.
- Offline behavior of account- or subscription-backed app features is unknown.

Next evidence step: on an owner-authorized adapter, record only the advertised
name and complete GATT table, then passively observe FFF1/FFF2 during normal
read-only vendor-app monitoring. Do not inject adapter initialization or a PID.
Preserve only redacted traffic with invented identifiers before using it here.
