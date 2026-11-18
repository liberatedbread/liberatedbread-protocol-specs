# ANT Smart BMS (legacy and 2021+ BLE)

> **Status**: Spec Available (source-derived, untested)
> **Protocol**: BLE GATT, two incompatible frame generations
> **Manufacturer**: Shenzhen ANT (Zhuofeng)
> **Manufacturer Status**: Active

## Overview

ANT Smart BMS boards can report pack voltage/current, state of charge,
capacity, per-cell voltages, temperatures and FET/balancer state directly over
BLE. This is a **read-only telemetry** profile. No FET, protection, balancing,
calibration, factory-default, DTU, vehicle or firmware write is included.

Two protocols must not be merged by their shared FFE0 service:

- **Legacy 2019/2020**: Smart 7S-32S, BMS-12 and BMS-24, exact 140-byte
  `AA 55 AA FF` response, big-endian fields and additive checksum.
- **2021+**: `7E A1` frames, one-byte length, little-endian Modbus CRC and
  scalar offsets that move with cell/temperature counts.

The documented 2021+ boards are ANT-BLE16ZMUB, ANT-BLE24BHUB, ANT-BLE04DMUB
and ANT@BLE22AAUB, including their listed hardware/software aliases. Other
`ANT?BLE24*` and `ANT?BLE3*` names are candidates requiring response
validation. Wired-only cross-check models are not BLE-qualified.

## Initial Setup

| Property | Value |
|----------|-------|
| Setup required | No on open units; some 2021+ units need the owner's application secret |
| Method | `ble_direct`, generation-specific status read |
| Discovery | ANT name prefix only; FFE0 is post-connect GATT/fallback, not a discovery requirement |
| Pairing/bonding | None; optional application authentication is separate |
| Confidence | High for default FFE1 paths; medium for fallback channels |

Choose the generation **before sending a status request**. Exact known 2021+
names take precedence: `ANT-BLE16ZMUB` and `ANT-BLE04DMUB` otherwise resemble
legacy `[01]` names, while `ANT@BLE22AAUB` resembles the legacy `ANT-BLE22*`
pattern. After those exact exclusions, apply the generic 2021+ matcher, then
the legacy matcher. Unknown prefixes are not automatically decoded.

Subscribe to FFE1 and send one matching status request. If a 2021+ unit
requires application authentication, use function `0x23` at address `0x6a01`
with the **owner's own secret**. There is no recovered/default secret in this
spec, and public example values are not credentials to try on hardware.

**Factory reset**: unknown and deliberately not offered. The legacy register
map includes factory-default/reboot controls, but their effect on cell count,
capacity, calibration, protection thresholds and secrets is not established.
A BMS reset is not an onboarding step.

**Rebinding**: no OS bond or network membership exists. Close the old client,
rediscover and rerun the generation/channel check; no reset is needed.

## Protocol Summary

### Default BLE Service

| UUID | Name | Description |
|------|------|-------------|
| `0000ffe0-0000-1000-8000-00805f9b34fb` | Default ANT service | Shared container, not proof of generation |
| `0000ffe1-0000-1000-8000-00805f9b34fb` | Request/notification | Write and notify on the default path |

If FFE1 is absent or yields no valid reply, the V2 app documents two fallback
pairs: write `0000fff3-0000-1000-8000-00805f9b34fb` / notify
`0000fff4-0000-1000-8000-00805f9b34fb`, and write
`0000fff5-0000-1000-8000-00805f9b34fb` / notify
`0000fff6-0000-1000-8000-00805f9b34fb`.

Discover each characteristic's **actual parent service**, subscribe, then send
only the bounded read-only probe
`7e a1 01 00 00 f5 58 62 aa 55`. Accept a valid `0x11` or `0x12` reply with
correct trailer and CRC. Try one candidate at a time with a bounded timeout;
never blindly write every pair. Fallback support on named retail boards is
still unverified.

### Legacy: exact 140-byte status

Request `db db 00 00 00 00` (six bytes). Response starts `AA 55 AA FF` and is
exactly 140 bytes. The last two bytes are `sum(bytes 4..137) mod 65536`, stored
big-endian.

Pack voltage is uint16 BE at offset 4 in 0.1 V. Cell voltages are uint16 BE
millivolts starting at 6, limited by the count at 123 (maximum 32). Current is
signed int32 BE at 70: **decode as `raw * -0.1 A`**, so positive means charging
and negative discharging in the normalized convention. SOC is uint8 at 74;
capacity and charge fields are unsigned 32-bit microamp-hours; runtime is
seconds at 87. Four reviewed temperature readings are signed int16 BE whole
°C starting at 91, followed by FET/balancer state and other fields.

Buffer fragments and split coalesced data at exactly 140 bytes. Reject wrong
headers, short/overlong candidates and bad checksums.

### 2021+: `7E A1` frames

```text
7e a1 | function | address LE16 | data length u8 | data | CRC LE16 | aa 55
```

Replies use request function + `0x10`. CRC-16/Modbus (reflected `0xa001`,
initial `0xffff`) covers from `A1` through the last data byte and is stored
little-endian before `AA 55`.

The **one-byte** length is deliberate. A secondary prose table showing separate
length-high/low bytes conflicts with both the executable encoder and the V2
app's ten-byte probe; do not implement that prose variant. A normal status
request is `7e a1 01 00 00 be 18 55 aa 55`.

Read requests and replies differ: a read request's nonzero length is the
**requested reply size** and it carries no request data. Authentication instead
uses length as actual secret length followed by secret bytes. A reply's total
length is `data_length + 10`. Device-info function `0x12` alone has a known
incorrect-length exception; status never gets that exception. The real
48-byte fixture declares 42: CRC `57 96` is checked at offsets 38–39 over the
declared span, bytes 40–41 are `ff 0b` rather than a trailer, and the actual
`AA 55` appears only at offsets 46–47. Validate the declared CRC, require the
final trailer, and preserve the six intervening bytes. A stream reader must
not slice at 42 before finding the final trailer; fragmented and coalesced
fixtures exercise this exact path.

For status, `temp_count` is at 8 (clamp 6), `cell_count` at 9 (clamp 32), and
cells begin at 34 as little-endian millivolts. Temperatures follow the cells:
`temp_count` probes plus MOSFET and balancer temperatures, signed int16 LE
whole °C. Compute:

```text
S = 2 * (min(cell_count, 32) + min(temp_count, 6))
```

Then pack voltage is uint16 LE at `38 + S` in 0.01 V; current is signed int16
LE at `40 + S` in **+0.1 A** (positive charging); SOC/SOH are at `42 + S` and
`44 + S`; FET/balancer state follows; power is signed int32 LE at `62 + S`;
cell-voltage delta is at `82 + S` in 0.001 V. Never reuse scalar offsets across
different cell/temperature counts.

The focused standard-library test checks both CRC algorithms, split/coalesced
and malformed frames, legacy sign/checksum, and multiple dynamic layouts
without making a hardware call.

## Evidence and limits

The official four-page legacy protocol, two official apps, and three pinned
public implementations back the spec. No battery, BMS, cloud account or owner
secret was accessed. Fallback channels, the length-prose conflict on live
hardware, device-info quirk breadth, unusual counts and optional
authentication behavior remain open. Readings are not a battery safety
interlock.

- [ANT legacy protocol PDF (pinned)](https://github.com/syssi/esphome-ant-bms/blob/f93196ecd7917ad138300bdee0390732ec61eabb/docs/ANT_communication_protocol_EN.1.pdf)
- [ANT official download center](https://download.antbms.com/)
- [patman15/aiobmsble](https://github.com/patman15/aiobmsble/tree/eb3fe1488eceeb25eadffbf2d40b24c9facd371b)
- [syssi/esphome-ant-bms](https://github.com/syssi/esphome-ant-bms/tree/f93196ecd7917ad138300bdee0390732ec61eabb)
- [fl4p/batmon-ha](https://github.com/fl4p/batmon-ha/tree/af401fa12414e16fcdf02ac71019c60587abfb8c)
