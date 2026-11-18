# Wyze Lock Bolt v1 (WLCKB1)

> **Status**: Identify-only spec; untested on hardware
> **Protocol**: BLE GATT, encrypted application protocol
> **Manufacturer**: Wyze Labs (Lockin/Yunding platform)
> **Manufacturer Status**: Active

## Overview

This page covers **only the original BLE-only Wyze Lock Bolt v1**, retail model
**WLCKB1**, app model **XFPL106**, factory family **YD_BT1**. Wyze Lock Bolt v2
adds Wi-Fi and is out of scope. The older Wyze Lock, companion keypad, gateways
and other Yunding products are not covered.

After an owner-authorized cloud export, a replacement client can read encrypted
state/battery and use the legacy local challenge-response without further cloud
contact. Initial provisioning and fresh credential export still require the
Wyze account service. There is no offline way established here to mint those
credentials.

The catalog entry is deliberately `identify_only` with **no generic lock
entity**. NUS is transport, not identity. Select WLCKB1 manually, validate its
read-only encrypted status, and use a dedicated session handler. Any lock or
unlock is an advanced, attended operation — never an automatic action or replay.

## Hardware

| Property | Value |
|----------|-------|
| Retail model | WLCKB1 (v1 only) |
| App/factory identifiers | XFPL106 / YD_BT1 |
| Radio | Bluetooth LE 5.0; no Wi-Fi on v1 |
| Power | 4×AA, 6 V nominal |
| Input | Fingerprint and keypad; separate companion keypad not covered |
| FCC ID | 2AUIUWLCKB1 (printed in the v1 quick-start guide) |
| Companion app | Wyze `com.hualai` |

## Initial Setup and credential boundary

| Property | Value |
|----------|-------|
| Setup required | Yes — application-layer provisioning |
| Method | `cloud_account` once, then cached local BLE credentials |
| Internet needed | Initial pairing and fresh export; not subsequent local sessions |
| Pairing indication | Three beeps and white keypad flashing after releasing P |
| Confidence | Medium — official setup and public protocol implementations, not run here |

1. Install the v1 lock and enable Bluetooth and Internet access on the phone.
2. Select the **v1** Lock Bolt in the Wyze app.
3. Press and hold the round **P** button beneath the batteries. Release after
   three beeps and a white flashing keypad, then complete app setup.
4. Through an owner-authorized export, store these four values privately:
   - cloud **device UUID** — its last 16 ASCII characters are the status key;
   - 32-character **BLE token** — its last 16 ASCII characters are the legacy
     operate key;
   - numeric **BLE key id** — sent as uint16 big-endian;
   - provisioned lock **BLE address**.

These are account-bound per-lock secrets or secret-associated locators. Do not
put them in tickets, examples, shell history, diagnostics or shared captures.
The public export helper needs the owner's login and developer API credentials;
its endpoints and real output are intentionally not reproduced here. A MAC
address alone does not provision a client.

### Factory reset

Official v1 reset is **Settings → Delete Device** in the Wyze app while within
Bluetooth range. A short beep series confirms it. Set up as a new device and
export fresh values afterward.

Removing and reinserting one battery is a **power cycle**, not the app factory
reset. Do not remove a battery during pairing: Wyze warns that pairing-button
plus battery removal can erase all users and settings. This reset procedure is
source-backed but was not run by this project.

### Rebinding

There is no Wi-Fi network to rejoin. Close the other central and reconnect with
the cached values. A new independent client needs an owner export; do not factory
reset merely to resolve a busy connection. Actual central/bond limits and
long-term offline credential acceptance remain unverified.

## Discovery and read-only verification

There is deliberately no executable advertisement matcher:

- the normal app resolves a provisioned lock by its account-associated address;
- NUS (`6e400001-b5a3-f393-e0a9-e50e24dcca9e`) is shared with unrelated devices;
- company ID `0xFFFF` is not a Wyze assignment;
- no dependable advertised model name was established.

Manually choose WLCKB1 and use the owner-supplied address. Subscribe to UART and
state notifications, read the standard Device Information service, and decrypt a
status block. Do not write until the block's zero padding and `loock` marker
validate. Stop on another model or an ID2-only dialect.

## Protocol Summary

### GATT channels

| UUID | Role |
|------|------|
| `6e400001-b5a3-f393-e0a9-e50e24dcca9e` | NUS service; shared transport, never identity |
| `6e400002-b5a3-f393-e0a9-e50e24dcca9e` | UART command write, without response |
| `6e400003-b5a3-f393-e0a9-e50e24dcca9e` | UART response notification |
| `00002220-0000-6b63-6f6c-2e6b636f6f6c` | Encrypted lock state read/notify |
| `00002222-0000-6b63-6f6c-2e6b636f6f6c` | Encrypted door state; raw value mapping unresolved |
| `0000180f-0000-1000-8000-00805f9b34fb` | Battery service |
| `00002a19-0000-1000-8000-00805f9b34fb` | Battery level — **encrypted, not a plain SIG byte** |
| `0000180a-0000-1000-8000-00805f9b34fb` | Standard Device Information service |

The parent service of the custom lock/door characteristics is not asserted;
address them by UUID rather than inventing one.

### Encrypted state, door and battery blocks

Each value is exactly one AES-128-ECB block, with no padding. The key is the
ASCII bytes of `device_uuid[-16:]`, **not** the BLE token.

| Plaintext offset | Size | Meaning |
|------------------|------|---------|
| 0 | 1 | Lock/door raw value or battery percent |
| 1 | 4 | Unix timestamp, uint32 **big-endian seconds** |
| 5 | 6 | Required zero padding |
| 11 | 5 | Required ASCII `loock` marker |

Lock payload `0` is unlocked, `1` locked and `0xFF` unknown. Battery accepts
0–100 percent or `0xFF` unknown. Reject a wrong key, bad length, nonzero padding,
missing marker or out-of-range battery instead of publishing plausible garbage.
Door-value semantics beyond the unknown sentinel remain unverified.

### L1 UART frame

| Offset | Size | Meaning |
|--------|------|---------|
| 0 | 1 | Magic `0xAB` |
| 1 | 1 | Flags: client request `0x00`, ACK `0x08`, device data `0x40`, ACK+data `0x48` |
| 2 | 2 | L2 payload length, uint16 **big-endian** |
| 4 | 2 | CRC over **L2 payload only**, uint16 **big-endian** |
| 6 | 2 | Sequence, uint16 **big-endian** |
| 8 | variable | L2 payload |

CRC is **CRC-16/ARC (IBM)**: reflected polynomial `0xA001` (normal `0x8005`),
initial zero, reflected input/output, no final XOR. The standard check value for
ASCII `123456789` is `0xBB3D`.

Reassemble arbitrary notification fragments, scan to `0xAB`, and validate length
and CRC before delivery. Drop a corrupt frame and rescan at the next magic;
never deliver its payload. ACK has flags `0x08`, no payload, CRC zero and the
sequence it acknowledges. Challenge request uses sequence 1; legacy actuation
uses 2. Counter-overflow behavior is not asserted.

### L2 command and TLVs

Every L2 payload starts with `command` and `version_flags`:

- legacy header nibble `0`: `key u8 | length u16be | value`;
- ID2 header nibble `7`: `key u16be | length u16be | value`.

Reject truncated headers/values, duplicate keys and unsupported versions.

The legacy challenge request is command `0x91`, flags `0x00`, field `0x0A`
containing `0x27`:

```text
L2: 91 00 0a 00 01 27
L1: ab 00 00 06 d3 5e 00 01 91 00 0a 00 01 27
```

The lock answers command `0x86` with a 16-byte random challenge in field `0xD2`.
Require its length and ACK/result sequence before continuing.

### Legacy lock/unlock — advanced, attended only

This algorithm is documentary for a dedicated handler, not a generic command:

1. Request a fresh challenge and validate the response.
2. Compute `AES-128-ECB-encrypt(operate_key, challenge)`, where
   `operate_key = ble_token[16:32]` as 16 ASCII bytes.
3. XOR the 16-byte result with the operation marker: byte 0 is `0x01` unlock or
   `0x02` lock; bytes 1–10 are zero; bytes 11–15 are `loock`.
4. Build legacy command `0x04`, flags `0x00`, preserving this field order:
   - `0x05`: BLE key id, uint16 big-endian;
   - `0x04`: the 16-byte XOR response;
   - `0xAD = 00`, `0xF4 = 01`, `0xF7 = 01` (one-byte values).
5. Send once in L1 sequence 2. Handle ACK and command `0x04` result, ACK device
   data, and require a fresh marker-valid state notification.

Some firmware omits command ACK and returns only the result. An absent result or
state notification is **not** permission to replay. Keep someone at the door
with an independent entry method available.

The spec contains newly generated unlock and lock vectors using an invented
token, BLE id `0x1234` and challenge `00..0F`. Its tests independently rebuild
the AES/XOR response, every TLV and the complete L1 frame without contacting a
lock.

### ID2 is unresolved, not a fallback

The app also carries an ID2 path (`version_flags 0x70`, two-byte TLV keys). The
reported construction folds the challenge into an eight-byte AES-CCM nonce and
uses key `0x0111`, but accepted firmware, complete field ordering and CCM
parameters are not capture-confirmed. **Do not construct or send ID2 actuation
from that outline.** Implement the legacy path only after validation; otherwise
stop and obtain a sanitized owner-authorized capture.

## Firmware updates

The app includes a Nordic secure DFU client, but no public v1 Bolt image was
found. A similarly named bundled image belongs to an unrelated camera. No DFU
entry command, bootloader identity, signature/rollback result or interrupted
update behavior is asserted, and the spec exposes no uploader.

## Verification and remaining work

No lock, account, real key, capture or actuation was used. All facts are
`reported`; the spec is `testing: untested`. Independent tests cover ARC,
fragmentation/noise/bad CRC/truncation, legacy and ID2 TLV syntax, malformed
input, AES marker/padding/range checks, timestamp/sentinel decoding, and both
legacy operation vectors.

Still needed: current-firmware legacy-versus-ID2 evidence, safe advertised model
identity, complete ID2 parameters, door-state mapping, credential rotation and
central/bond behavior, and public OTA/recovery evidence.

## References

- [Wyze Lock Bolt Local integration (pinned)](https://github.com/willdatrill2007/Wyze-Lock-Bolt-Local/tree/1f128cbea748c17a17a52e76457314ac366aaf1b) — final CRC, L1/L2, marker and legacy-session cross-check.
- [Wyze Bolt Wi-Fi Bridge ESP32 (pinned)](https://github.com/tpawley2001/Wyze-Bolt-WiFi-Bridge-ESP32/tree/c212299aa104802f9a6c147a39c609d859226a48) — independent battery decode and radio/proxy notes.
- [Official v1 quick-start guide](https://support.wyze.com/hc/article_attachments/22783653833755) — WLCKB1 identity, power, setup and lights; HTTP 200 verified 2026-11-18.
- [Official v1 setup guide](https://support.wyze.com/hc/en-us/articles/7851773368091-Wyze-Lock-Bolt-Setup-Guide) — initial pairing and P-button indication.
- [Official v1 factory-reset guide](https://support.wyze.com/hc/en-us/articles/5335456919963-How-do-I-factory-reset-Wyze-Lock-Bolt) — Delete Device reset and power-cycle warning.
