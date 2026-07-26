# Triumph Tiger 900

> **Status**: Research
> **Protocol**: OBD-II connector, ISO 15765-4 (CAN) + UDS
> **Manufacturer**: Triumph Motorcycles Ltd.
> **Manufacturer Status**: Active (protocol closed; owner-facing functions are dealer- or paid-tool-gated)

## Overview

The Tiger 900 displays a spanner/wrench "service due" reminder on its TFT dash. Resetting
it after an owner-performed service requires either a dealer visit or a third-party tool
(TuneECU, TigerTool, DealerTool, HealTech Maintenance Mate) plus a specific Bluetooth OBD
adapter. There is no button combination on the bike that clears the distance-based part
of the reminder.

The transport underneath is ordinary and open — ISO 15765-4 CAN on a standard diagnostic
connector. The reset itself is a manufacturer-specific request on top of it, and that
request is what this page is trying to pin down. See
[Common OBD-II patterns](../protocols/obd2-common.md) for the general layer cake.

**The exact reset request bytes are not yet known.** Everything below is split into what
is confirmed from public documentation, and what is hypothesis with a plan to test it.

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

### Confirmed

| Fact | Source |
|------|--------|
| Diagnostic access is over the OBD connector, ISO 15765-4 CAN | TigerTool `-tryecu2` documentation |
| Third-party tools reach the ECU through a plain ELM327-class adapter | TigerTool instructions |
| Service distance and odometer are held in the instrument cluster in km | TigerTool instructions |
| The calendar date is *not* reset by TigerTool; instrument menu only | TigerTool instructions |
| Interval granularity 100 units; max 6000 mi / 10000 km for Tiger 900 | TigerTool instructions |
| A failed reset can lock out further diagnostic functions until reconnect | TigerTool instructions |

### Unknown — the open question

**What is the exact request that resets the service interval?**

Candidate hypotheses, ranked, all **unverified**:

| # | Hypothesis | Request shape | Why plausible | How to falsify |
|---|-----------|---------------|---------------|----------------|
| H1 | UDS RoutineControl | `31 01 <RID hi> <RID lo> [interval]` | "Reset" functions are conventionally routines; explains the post-reset lockout if the routine ends the session | Capture shows `31`/`71` exchange |
| H2 | UDS WriteDataByIdentifier | `2E <DID hi> <DID lo> <km u16>` | Tool UI is "pick a number, validate" — that is a value write, and the 100-unit granularity suggests a scaled integer | Capture shows `2E`/`6E` exchange |
| H3 | H2 plus a second write for the date | `2E <DID> <date>` | TuneECU insists the clock is set before the reset | Two writes in one session |
| H4 | KWP2000 `3B` writeDataByLocalIdentifier | `3B <LID> <data>` | Triumph's older ISO 9141 ECUs predate UDS; the CAN ECUs may have kept the dialect | Capture shows `3B`/`7B` |

Common to all four, also unverified:

- Preceded by `10 03` (extended diagnostic session). The lockout-on-failure behaviour is
  hard to explain otherwise.
- Possibly preceded by SecurityAccess `27 01` / `27 02`. Owners report region-locked ECUs
  on some liquid-cooled Triumphs, which implies a seed/key exists somewhere in the stack.
- `3E 00` TesterPresent keepalive during the exchange.
- Addressed physically to a single ECU (`0x7E0` → `0x7E8` if Triumph uses the OBD-II
  defaults), **not** functionally to `0x7DF`. Since the value lives in the cluster, the
  engine ECU may be gatewaying the write, or the cluster may have its own diagnostic
  address — determining which is part of the work.

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

### Where the answer actually is

TuneECU is the most likely place to recover the message, and its published documentation
is not it: the online guide is an adapter/model compatibility matrix, and the official
Android description PDF is a scanned image with no text layer. Neither carries anything
below the UI level.

The app itself is a different matter, and there is a clean route into it:

| Build | Package | Cost | Function |
|-------|---------|------|----------|
| TuneECU | `com.tuneecu` | Paid | Remapping **plus** diagnosis, tests and adjustments (where Reset Service Interval lives) |
| TuneECU Lite | `com.tuneecu_lite` | Free | "Diagnosis and test of the ECU" — no remapping |

The Lite build is distributed free, and diagnosis/test is exactly the code path that
carries the Triumph dialect, so it is the clean-room static-analysis lead:
`apkeep -a com.tuneecu_lite`, then `scripts/run_static_target.sh triumph-tiger-900`, then
grep for ELM327 setup strings (`ATSP`, `ATSH`, `ATCRA`, `ATFC`) and UDS service bytes
(`31 01`, `2E`, `22`, `10 03`, `27 01`, `3B`) near the adjustments-screen strings. The
paid build should only be analysed from a copy the researcher owns.

One corroborating detail from the Lite listing: it requires a genuine ELM327 v1.4/1.5 and
states that clone v2.1 adapters do not work. That is the same adapter-sensitivity seen in
the full app's service-reset requirement, and it points at frame handling and timing
rather than anything exotic on the bike.

The Windows TuneECU — freeware, and the one that covered the ISO 9141-era Triumph ECUs —
is discontinued and no longer distributed by its author, so it is not a route in.

## Next Steps

1. **Static analysis of TuneECU Lite.** Free build, so fetching it needs no purchase;
   `scripts/run_static_target.sh triumph-tiger-900` plus the greps above. If the request
   is constructed from string constants it will fall out here.
2. **btsnoop capture (cheapest live confirmation, no CAN hardware).** Android *Developer options → Enable
   Bluetooth HCI snoop log*, run one vendor-tool service reset against an owned bike, pull
   `btsnoop_hci.log`, open in Wireshark, follow the RFCOMM stream. The ELM327 protocol is
   ASCII, so the `ATSH`/`ATFC` setup **and** the hex request appear in clear text. This
   answers H1–H4 outright in a single capture.
3. **Passive CAN log.** T-tap CAN-H/CAN-L at the connector, `candump -L`, filter to the
   physical request/response pair, run the reset, diff.
4. **Read-only DID sweep.** `22 <DID>` across the manufacturer range with the bike
   stationary; record every DID answering `62`. Look for a km odometer, a service-due
   distance that is a multiple of 100, and a packed date. `scripts/obd_discover.py` does
   this — read-only, no writes.
5. **Confirm the addressing.** Establish whether the service data is read from the engine
   ECU's address or from a separate cluster address, and whether the cluster is reachable
   directly from the diagnostic connector.
6. **Model-year split.** Repeat 1–5 on a MY2024+ Gen 2 bike; do not assume the 2020–2023
   findings carry over, since TigerTool's failure there indicates relocated data.

## Tools Used

- [x] Public tool documentation review (TigerTool V3.0 instructions, TuneECU guide)
- [ ] APK static analysis of TuneECU Lite (`com.tuneecu_lite`)
- [ ] btsnoop HCI capture of a vendor tool performing the reset
- [ ] Passive CAN capture at the diagnostic connector
- [ ] Read-only UDS DID sweep (`scripts/obd_discover.py`)

## References

- [TigerTool V3.0 instructions (bmdiag.co.uk)](https://www.bmdiag.co.uk/user/tiger%20tool/TigerTool%20V3.0%20Instructions.pdf)
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
