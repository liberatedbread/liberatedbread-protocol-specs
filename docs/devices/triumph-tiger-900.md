# Triumph Tiger 900

> **Status**: In Progress (protocol recovered from tool analysis; hardware confirmation pending)
> **Protocol**: OBD-II connector — UDS/CAN, proprietary CAN, and KWP2000/K-line
> **Manufacturer**: Triumph Motorcycles Ltd.
> **Manufacturer Status**: Active (protocol closed; owner-facing functions are dealer- or paid-tool-gated)

## Overview

The Tiger 900 displays a spanner/wrench "service due" reminder on its TFT dash. Resetting
it after an owner-performed service requires either a dealer visit or a third-party tool
(TuneECU, TigerTool, DealerTool, HealTech Maintenance Mate) plus a specific Bluetooth OBD
adapter. There is no button combination on the bike that clears the distance-based part
of the reminder.

The transport underneath is ordinary and open — CAN on a standard diagnostic connector.
The reset itself is a manufacturer-specific request on top of it. See
[Common OBD-II patterns](../protocols/obd2-common.md) for the general layer cake.

**The reset message is `21 <km/100>` (or `22 <miles/100>`) sent on CAN ID `0x701` to the
instrument cluster** — not a UDS request to the engine ECU at all. See
[Protocol Summary](#protocol-summary) for that and the rest of the recovered surface.

!!! warning "Read-only research only"
    Stationary bike, on a stand, engine off, ignition on. No writes to ABS, immobiliser
    or engine-map memory. See [Clean-room rules](../CLEANROOM_RULES.md).

## Hardware

| Property | Value |
|----------|-------|
| Models | Tiger 900 GT / GT Pro / Rally / Rally Pro (2020–2023), Gen 2 Tiger 900/850 (MY2024+) |
| ECU | Keihin (per TuneECU's Triumph model list) |
| Diagnostic connector, 2020–2023 | SAE J1962 16-pin, black, under the pillion seat |
| Diagnostic connector, MY2024+ | ISO 19689 6-pin, red, JST MWT series |
| Bus | ISO 15765-4 (CAN); Mk1 Tiger 800-era ECUs also used ISO 9141-2 |
| Nodes on the bus | Engine ECU, instrument cluster, ABS modulator, immobiliser (also carries TPMS) |

TigerTool exposes its ECU-family assumptions as command-line switches, which is the
clearest public statement of the transport split:

- `-tryecu1` — "protocols used by similar ECUs to those typically fitted to the Mk1 Tiger
  800. These ECUs use a combination of ISO9141-2 & ISO15765-4 (aka CAN bus) protocols."
- `-tryecu2` — "protocols used by later ECUs that primarily use ISO15765-4 (aka CAN bus)."

The Tiger 900 sits in the `-tryecu2` family: **CAN, and the standard OBD-II variant of it
is 11-bit at 500 kbit/s.**

### Connector change at MY2024

Triumph moved the Gen 2 bikes to the 6-pin ISO 19689 Euro 5 socket. Consequences observed
by owners:

- 6-pin-to-J1962 adapter leads exist and are cheap, so the *physical* change is trivial.
- The *logical* change was not: TigerTool does not connect to Gen 2 bikes because Triumph
  relocated ECU data, and HealTech's Maintenance Mate did not initially support MY2024.
- Treat 2020–2023 and MY2024+ as two separate targets until proven identical.

## The service reminder (SIA)

"SIA" is Triumph's Service Interval Announcement. It has **two independent components**,
and conflating them is the most common source of "I reset it and the wrench is still on"
reports:

| Component | Stored where | Reset by |
|-----------|--------------|----------|
| Service-due **distance** | Instrument cluster (all odometer values held in km) | Diagnostic request over the OBD connector |
| Service-due **date** (calendar-equipped models) | Instrument cluster | The bike's own instrument menu — *not* reset by TigerTool |

Confirmed behavioural facts from tool documentation:

- The interval is settable only in multiples of 100 (miles or km).
- Maximum interval on Tiger 800/900/Sport is 6000 miles / 10000 km (Explorer/1200 is
  10000 miles / 16000 km). The tool clamps this per model, implying the ECU either
  accepts a raw distance or rejects out-of-range values.
- After a reset a new countdown begins from the **current odometer reading**.
- The wrench reappears 500 miles / 800 km before the service-due distance.
- Odometer values live in the instruments in kilometres; mile displays are converted, and
  rounding differences of ~1 mile between tool and dash are expected.
- TuneECU's procedure requires the **bike's clock and date to be set correctly first**,
  then offers km/miles selection and an interval value, then "Validate" — consistent with
  the reset writing a date as well as a distance on calendar-equipped models.
- A failed reset can leave the ECU unresponsive to further diagnostic functions until the
  tool reconnects. That is the signature of a **diagnostic session** that ends (or is
  torn down by an ECU reset) as part of the routine.

### Adapter requirements — a protocol clue

The vendor tools name specific adapters for the reset, while accepting anything for DTC
reading:

| Adapter | DTC read | Service reset |
|---------|----------|---------------|
| OBDLink LX / MX+ (STN chipset) | Yes | Yes |
| UniCarScan UCSI-2100, Vgate vLinker MC+ | Yes | Model-dependent |
| Generic ELM327 clone | Usually | Frequently fails |

Reading DTCs is a single-frame OBD-II mode `03`. If that works and the reset does not, the
reset is almost certainly **multi-frame ISO-TP and/or requires custom request headers** —
exactly the area where clone ELM327 firmware is unreliable. This is a strong hint about
the *shape* of the message even without having captured it.

## Protocol Summary

**The service interval reset message is now known.** It was recovered by static analysis
of TigerTool V3.51 (`TigerTool.exe`, SHA-256 `3c7270ef…`), which its author distributes
free of charge — a Delphi Win32 binary whose ELM327 command strings and CAN payloads are
plain string constants, cross-checked against the surrounding x86.

!!! note "Verification level"
    Everything below is **derived from a third-party tool binary, not yet reproduced on a
    bike.** It is recorded as `verification: reported` in the spec. Confirming it against
    hardware — and reading the values back — is the remaining work.

TigerTool covers Tiger 800, 900, Sport, Explorer/1200 and Trophy, so this surface is
almost certainly not Tiger-900-specific. It does **not** cover Gen 2 (MY2024+) bikes,
where Triumph relocated the data.

### There is no single bus — there are four

The most important structural finding, and the reason a plain OBD-II tool sees nothing
useful: Triumph's owner-facing functions are spread across four different stacks, and
only one of them is UDS.

| Stack | ELM327 setup | Addressing | What lives there |
|-------|--------------|------------|------------------|
| **Engine ECU (UDS/CAN)** | `AT TP 7`, `AT CP 18`, `AT SH DA D5 F1`, `AT CAF0`, `AT CFC1` | 29-bit `18 DA D5 F1` (tester `F1` → ECU `D5`); replies `18 DA F1 D5`. Functional: `18 DB 33 F1` | ECU identity, DTC read/clear, throttle balance |
| **Instrument cluster (proprietary/CAN)** | `AT TP6`, `AT SH701`, `AT CRA704`, `AT CAF0`, `AT CFC0` | 11-bit, request `0x701` → response `0x704` | **Service interval + date**, odometer, instrument menu/units |
| **Immobiliser / TPMS (proprietary/CAN)** | `AT TP6`, `AT SH604`, `AT CRA602`, `AT CAF0`, `AT CFC0` | 11-bit, request `0x604` → response `0x602`; live data broadcast on `0x600` | Immobiliser DTCs, TPMS sensor IDs and live data |
| **Engine + ABS ECU (K-line)** | `AT TP3`, `AT SH 68 6A F1`, ABS adds `AT IIA43` | KWP2000 header `68 6A F1` (target `6A`, source `F1`), ISO init address `0x43` | ECU ping, security access, ABS DTCs and brake bleed |

The cluster and immobiliser stacks run with **auto-formatting off (`ATCAF0`) and flow
control off (`ATCFC0`)** — they are *not* ISO-TP. Frames are raw and short, first byte is
an opcode. That is precisely why a generic OBD-II tool cannot touch them, and why adapter
quality matters so much: the tool is hand-rolling frames.

### The service interval reset

Cluster stack, CAN `0x701` → `0x704`:

```text
AT WS                      reset adapter
AT TP6                     ISO 15765-4, 11-bit, 500 kbit/s
AT E0 / AT H1 / AT L0      echo off, HEADERS ON, linefeeds off
AT CFC0                    flow control off
AT CAF0                    auto-formatting off — raw frames
AT SH701                   transmit on 0x701
AT CRA704                  receive only 0x704
AT ST7F                    long timeout (~508 ms) for the reset
21 <n>                     RESET SERVICE INTERVAL, distance in KILOMETRES
   or
22 <n>                     RESET SERVICE INTERVAL, distance in MILES
```

**`<n>` is the service interval divided by 100, as a single byte.** That one detail
explains the constraint every tool's UI enforces: intervals are settable only in multiples
of 100 because the wire format cannot express anything else. The documented ceilings fit a
single byte exactly — 10000 km → `21 64`, 6000 miles → `22 3C`.

The success reply is a frame on `0x704` beginning `B4` or `B3`; TigerTool matches the
first six characters of the header-prefixed reply (`704 B4` / `704 B3`). A reply beginning
`704 00` is the no-data/error case.

The date reset is a separate command on the same stack: `5C <x> <hi> <lo>`, where the
16-bit date word is incremented and split across two bytes, answered by `704 DC`.

| Function | Request | Success reply |
|----------|---------|---------------|
| Reset service interval (km) | `21 <km/100>` | `704 B4` / `704 B3` |
| Reset service interval (miles) | `22 <miles/100>` | `704 B4` / `704 B3` |
| Reset service date | `5C <x> <hi> <lo>` | `704 DC` |

### Reading the current service and odometer values

Sent in sequence on the same `0x701`/`0x704` stack after connecting:

| Request | Reply seen | Meaning |
|---------|-----------|---------|
| `0D 01` | `704 8D 01 …` | First SIA/odometer record (data parsed from byte 6 onward) |
| `47 01` | — | Second record |
| `5E 01` | — | Third record |
| `6E 76` | — | Fourth record |
| `6E 74` | — | Fifth record |

Field-level decoding of these replies is the obvious next piece of work; the tool displays
odometer, distance-to-service and service date from them.

### Instrument menu and units

Same stack. Each is opcode + one value byte, and each has its own acknowledgement:

| Request | Sets | Success reply |
|---------|------|---------------|
| `30 <v>` | Odometer units (miles/km) | `704 B0` |
| `31 <v>` | TPMS menu item enable/disable | `704 B1` |
| `32 <v>` | ABS menu item enable/disable | `704 B2` |
| `33 <v>` (inferred from the reply table) | A further unit setting | `704 B3` |

### Engine ECU — UDS over 29-bit CAN

Identity block, read on connect. All are standard `22` ReadDataByIdentifier requests with
an ISO-TP single-frame PCI:

| Request | DID | TigerTool label |
|---------|-----|-----------------|
| `03 22 F1 A0` | `F1A0` | Tune number |
| `03 22 F1 A7` | `F1A7` | Tune number (second variant) |
| `03 22 F1 AE` | `F1AE` | Tune count |
| `03 22 F1 A2` | `F1A2` | Cal / build number |
| `03 22 F1 99` | `F199` | Tune date |
| `03 22 F1 8C` | `F18C` | ECU serial |
| `03 22 F1 90` | `F190` | VIN |
| `02 09 04` (functional, `18 DB 33 F1`) | mode 09 PID 04 | Calibration ID |

A second ECU answers on `18 DA F1 D6` (address `0xD6`) and is probed when checking for a
new tune.

| Function | Request | Reply |
|----------|---------|-------|
| DTC count | `03 19 01 08` | `59 01 …` |
| DTC list | `03 19 02 08` | `59 02 …` |
| Clear DTCs / MIL | `04 14 FF FF FF` | `44`, or `03 7F 14 78` (pending) then `44` |
| Throttle balance MAP | `03 22 00 03 / 00 17 / 00 31 / 00 33` and `01 03 / 01 17 / 01 31 / 01 33` | `62 00 33 …` etc. |

Throttle balance is gated by **SecurityAccess on the K-line stack**: `27 03` → `67 03`
(seed), `27 04` → `67 04` (key). The app labels failures "SA Invalid" and "K1 Invalid",
confirming a real seed/key exchange exists — though notably **not** in front of the
service reset.

### ABS module — KWP2000 over K-line

Reached with `AT IIA43` (ISO init address `0x43`) and header `68 6A F1`:

| Function | Request | Reply |
|----------|---------|-------|
| ABS ECU identity | `A0` | (ID string) |
| Read ABS DTCs | `13 40 FF` | `53 …` |
| Clear ABS DTCs | `14 00 00` | `54 00 00` |
| Start bleed | `A1 01 FF` | `E1 01 FF` (ack) |
| Bleed status poll | `A1 B0 FF` | `E1 B0 00` idle / `E1 B0 01` running |
| Stop bleed | `A1 01 00` | `E1 01 00` |

`3F` is used throughout the K-line stack as the ECU ping/keepalive.

### Immobiliser and TPMS — proprietary CAN

Request `0x604` → reply `0x602`, live broadcast on `0x600` (`AT CRA600` + `AT MA`):

| Function | Request | Reply |
|----------|---------|-------|
| Identify immobiliser | `00` | `602 0B` (type) |
| Immobiliser access | `02 18 E2 31 02` | — |
| Read immobiliser DTCs | `40` | `602 40 00` |
| Erase immobiliser/TPMS DTCs | `41 FF FF FF FF` | `602 41 00` |
| TPMS enable state | `0A` | `602 0A` |
| TPMS enable / disable | `03 00` / `03 10`, `04 00` / `04 10` | `602 03 00` / `602 04 00` |
| Write TPMS sensor ID | `09 00 00 <id bytes> 01 19` | `602 09` |

### Why cheap adapters fail — now with the actual reason

The earlier inference was multi-frame ISO-TP. The binary shows something more specific:
TigerTool turns **auto-formatting off** and hand-builds raw frames, uses **non-standard
CAN IDs** (`0x701`, `0x604`, not `0x7E0`), switches between **11-bit and 29-bit** headers
mid-session, and drops to **K-line with a custom ISO init address** for ABS. Clone
firmware that only implements the legislated OBD-II happy path fails at the first
`AT CAF0` or `AT CRA`, long before any payload is sent.

### Community-reported broadcast CAN IDs (different bus traffic, for orientation)

Reverse-engineering threads on the Triumph 675 forums list ECU→cluster broadcast IDs.
These are **not** diagnostic requests and are **not confirmed for the Tiger 900** — they
are noted only so a capture is not misread as diagnostic traffic:

| CAN ID | Reported content |
|--------|------------------|
| `0x518` / `0x519` | Engine RPM |
| `0x540` | Gear position, neutral indicator |
| `0x550` | Coolant bar graph, warning light |
| `0x570` | Coolant temperature |

### TuneECU — the cross-model cross-check

TigerTool answered the question, but it covers only Tiger 800/900/Sport/Explorer/Trophy
and nothing from MY2024. TuneECU covers a far wider range, so it is the natural place to
check whether the cluster opcodes above are shared across Triumph's line-up or specific to
this family.

Its published documentation will not tell you: the online guide is an adapter/model
compatibility matrix, and the official Android description PDF is a scanned image with no
text layer. The app is a different matter, and there is a clean route in:

| Build | Package | Cost | Function |
|-------|---------|------|----------|
| TuneECU | `com.tuneecu` | Paid | Remapping **plus** diagnosis, tests and adjustments (where Reset Service Interval lives) |
| TuneECU Lite | `com.tuneecu_lite` | Free | "Diagnosis and test of the ECU" — no remapping |

The Lite build is distributed free and diagnosis/test is the code path carrying the
Triumph dialect, so it is the clean static-analysis lead: `apkeep -a com.tuneecu_lite`,
then `scripts/run_static_target.sh triumph-tiger-900`, then grep for the ELM327 setup
strings (`ATSP`, `ATSH`, `ATCRA`, `ATFC`, `ATCAF`) and for the cluster opcodes recovered
here (`21`, `22`, `5C`, `0D 01`, `30`/`31`/`32`). The paid build should only be analysed
from a copy the researcher owns.

One corroborating detail from the Lite listing: it requires a genuine ELM327 v1.4/1.5 and
states that clone v2.1 adapters do not work — the same adapter sensitivity the TigerTool
analysis now explains (raw frames, non-standard IDs, mid-session protocol switching).

The Windows TuneECU — freeware, and the one that covered the ISO 9141-era Triumph ECUs —
is discontinued and no longer distributed by its author, so it is not a route in.

## Next Steps

The message is known; proving it and decoding the rest is what remains.

1. **Confirm on hardware.** Cluster stack setup, then `21 <km/100>`, and check for a reply
   beginning `704 B4`. Read back through the instrument menu, and via the `0D 01` / `47 01`
   / `5E 01` / `6E 76` / `6E 74` query sequence, that the service-due distance changed.
2. **Decode the SIA query replies.** The five query opcodes return the odometer,
   distance-to-service and service date. Field offsets and scaling are not yet mapped —
   this is the highest-value remaining piece, since it turns a write-only reset into a
   readable state.
3. **Pin down the date reset.** `5C <x> <hi> <lo>` — the two data bytes are a 16-bit date
   word plus one, but the epoch and the `<x>` byte are unresolved.
4. **Identify the `33 <v>` setting** implied by the unexplained `704 B3` acknowledgement.
5. **Map the immobiliser/TPMS opcode space** beyond the handful TigerTool uses.
6. **Model-year split.** All of the above is for 2020–2023. TigerTool does not connect to
   Gen 2 (MY2024+) bikes, so that variant needs its own capture — most likely a btsnoop
   log of a tool that does work there (DealerTool is reported to).
7. **Cross-check against TuneECU**, which covers models TigerTool does not, to see whether
   the cluster opcodes are shared across the range.

## Tools Used

- [x] Public tool documentation review (TigerTool V3.0 instructions, TuneECU guide)
- [x] Static analysis of TigerTool V3.51 — Delphi literal-table extraction plus x86
      disassembly (capstone) of the request builders and response matchers
- [ ] Hardware confirmation of the reset on a bike, with read-back
- [ ] Field decoding of the SIA query replies
- [ ] APK static analysis of TuneECU Lite (`com.tuneecu_lite`) for cross-model coverage
- [ ] btsnoop HCI capture for the MY2024+ Gen 2 variant

## References

- [TigerTool V3.0 instructions (bmdiag.co.uk)](https://www.bmdiag.co.uk/user/tiger%20tool/TigerTool%20V3.0%20Instructions.pdf)
- [TigerTool V3.51 download — free for non-commercial use](https://www.bmdiag.co.uk/bmdiag-obd-interface-for-triumph-tiger-tool)
- [TuneECU basic guide — supported adapters and models](https://tuneecu.fr/docs/_en/Basic_guide.html)
- [TuneECU — Android-only, Windows freeware discontinued](https://tuneecu.net/)
- [TuneECU Lite (free diagnosis and test build, `com.tuneecu_lite`)](https://apkcombo.com/tuneecu-lite/com.tuneecu_lite/)
- [Gen 2 Tiger 900 uses the 6-pin Euro 5 (ISO 19689) connector](https://www.tiger800.co.uk/index.php?topic=32836.0)
- [TigerTool and the service wrench on Tiger 800/900](https://www.tiger800.co.uk/index.php?topic=27014.0)
- [ISO 19689:2016 — motorcycle diagnostic connector](https://www.iso.org/standard/66030.html)
- [HealTech Maintenance Mate](https://www.healtech-electronics.com/products/mm/)
- [Reverse-engineering the Triumph ECU-to-cluster CAN bus (Triumph675.net)](https://www.triumph675.net/threads/ecu-to-dash-can-bus-message-ids.242889/)

## Contributors

- Public-documentation survey and hypothesis framing
