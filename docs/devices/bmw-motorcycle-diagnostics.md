# BMW Motorcycle Diagnostics (MotoScan)

> **Status**: In Progress (addressing and data model recovered; reset payloads still in native code)
> **Protocol**: OBD-II connector — BMW D-CAN (ISO 15765-4 with `0x6F1` addressing), KWP2000, UDS
> **Manufacturer**: BMW Motorrad
> **Manufacturer Status**: Active (protocol closed; owner-facing functions are dealer- or paid-tool-gated)

## Overview

The same problem as the [Triumph Tiger 900](triumph-tiger-900.md): a service interval an
owner cannot reset from the bike. The tool that does it is MotoScan
(`de.wgsoft.motoscan`, WGSoft.de), and the findings below come from decompiling it.

There is a neat structural tell here. **MotoScan's vendor also sells the UniCarScan
UCSI-2100 adapter**, whose headline feature is accepting messages up to 255 bytes where a
stock ELM327 stops at 8. That is not a general-purpose selling point — it is what BMW's
coding and adaptation writes need. The adapter told us something about the protocol before
the app was opened.

!!! note "Verification level"
    Derived from the shipped app, not yet reproduced on a bike — `verification: reported`.
    The APK was fetched with `apkeep` and its signature checked before analysis: it is
    signed by `O = WGSoft.de, CN = Wladimir Gurskij`, i.e. the genuine vendor build rather
    than a repack. MotoScan is a free download; the full feature set is an in-app purchase,
    so no cracked build is needed or was used.

!!! warning "Read-only research only"
    Stationary bike, engine off. ECU coding can brick modules and is out of scope. See
    [Clean-room rules](../CLEANROOM_RULES.md).

## Addressing — BMW's `0x6F1` scheme

BMW does not use per-ECU CAN IDs the way Triumph does. The tester transmits on a **single
ID, `0x6F1`**, and the target ECU address is carried as the first payload byte via CAN
extended addressing. Each ECU answers on `0x600 + its address`.

MotoScan's init sequence, parameterised by the target address (`<aa>`):

```text
ATSPB                  select the ELM327 user-defined protocol
ATPBC101               protocol B options C1 01
ATSH6F1                transmit header 0x6F1 (BMW tester address)
ATFCSH6F1              flow-control header 0x6F1
ATFCSD<aa>300008       flow-control data: target, BS=0x00, STmin=0x08
ATFCSM1                use our flow control
ATCEA<aa>              CAN extended addressing — target ECU address
ATCM7FF                mask 0x7FF
ATCF6<aa>              filter to 0x6<aa>, this ECU's reply ID
ATST90                 timeout
ATBI                   bypass the standard init
STCSEGT1 / STCFCPC     STN-only segmentation + flow-control tuning
```

Three consequences worth stating plainly:

- **`ATCEA` is mandatory.** Extended addressing is not something clone firmware reliably
  implements, and without it every BMW ECU is unreachable. This — not multi-frame alone —
  is why MotoScan's adapter list is short.
- The scheme is *uniform*: every module is reached the same way, with only `<aa>` changing.
  That makes enumerating modules straightforward compared to Triumph's four bespoke stacks.
- `STCSEGT1`/`STCFCPC` are STN-only, so an STN adapter takes a faster path, while the
  UCSI-2100 achieves the same end through its long-message mode.

## Service interval model

MotoScan exposes four reset scopes (`Cu$m` in the decompile):

| Value | Meaning |
|-------|---------|
| `SI_ALL` | Reset every service counter |
| `SI_DATE` | Reset the date-based interval only |
| `SI_MILEAGE` | Reset the distance-based interval only |
| `SI_DATE_CAR` | Date variant used for the car-style cluster |

That distance/date split is the same one the Triumph work uncovered, which is now looking
like an industry pattern rather than a Triumph quirk.

The service data itself is named in the embedded diagnostic database:

| Identifier | Holds |
|------------|-------|
| `STAT_SERVICE_KMSTAND_DATA` | Odometer reading at last service |
| `STAT_SERVICE_DATUM_DATA` | Service date (composite) |
| `STAT_SERVICE_JAHR_WERT` / `_MONAT_WERT` / `_TAG_WERT` | Service year / month / day |
| `STAT_VENTILSPIELSERVICE_RESTWEG_WERT` | Distance remaining to the valve-clearance service |
| `STAT_VENTILSPIELSERVICE_ANZAHL_RESET_WERT` | How many times the valve service has been reset |
| `STR_VENTILSPIELSERVICE_RESET` | The valve-service reset itself |

BMW tracks a **separate valve-clearance service** with its own remaining-distance counter
and reset count — a second interval on top of the usual oil service, and the reset counter
means the bike remembers how often it has been zeroed.

## Modules

The embedded database uses BMW's SGBD naming (`STAT_*` results, `ECU_ID*` identity).
Motorcycle modules seen include:

| Short name | Module |
|------------|--------|
| `KOMBI` | Instrument cluster — owns the service and odometer data |
| `ZFE` | Central body electronics |
| `BMS` | Engine management |
| `ABS` | Brake modulator |
| `RDC` | Tyre pressure monitoring |
| `DWA` | Alarm system |
| `ILAF` | Adaptive headlight |

Also present: oil level and oil temperature sensing (`STAT_OELNIVEAU`,
`STAT_OELSTANDSANZEIGE`, `STAT_TEMPERATUR_OEL_WERT`, ADC voltages for the level and temp
senders), and reset counters for several subsystems.

## Adapter classification — from the vendor's own code

MotoScan carries an adapter enum that is, in effect, third-party validation of the
[capability tiers](obd2-bluetooth-adapter.md#capability-tier) this repo uses:

```text
ELM327_CLONE   ELM327_ORIGINAL   ELM327_UNKNOWN
OBDLINK_LX     OBDLINK_MX        OBDLINK_MX_PLUS     OBDLINK_MX_WIFI
UCSI_2000      (UI text: "UCSI-2000/2100", "UniCarScan")
```

The app distinguishes a **clone** from an **original** ELM327 at runtime and treats them
differently. A tool shipping clone detection is the strongest possible statement that the
tier distinction is real and load-bearing.

## What is still unknown

The reset **payloads** are not in the Java. MotoScan's diagnostic engine lives in
`libmotoscan-helper.so` (~7 MB per ABI), which embeds a BMW SGBD-style job and result
database along with localised parameter descriptions. The Java layer dispatches job names;
the native layer turns them into UDS/KWP frames.

Remaining work, in order of value:

1. **Recover the job → frame mapping** from `libmotoscan-helper.so`. The names are already
   readable; what is needed is the table that binds `STR_VENTILSPIELSERVICE_RESET` to a
   service byte and identifier.
2. **Enumerate module addresses** — the `<aa>` values MotoScan probes.
3. **Confirm on hardware** with read-back of `STAT_SERVICE_KMSTAND_DATA`.
4. **Compare with Triumph.** Both vendors put service data in the cluster and split it
   distance/date; whether the resemblance goes deeper is worth knowing.

## Tools Used

- [x] `apkeep` fetch of `de.wgsoft.motoscan` + signature verification (genuine WGSoft build)
- [x] DEX string-pool extraction and jadx decompile (8708 classes)
- [x] Native-library string survey (`libmotoscan-helper.so`)
- [ ] Native job-table analysis for the reset payloads
- [ ] Hardware confirmation with read-back

## References

- [MotoScan (WGSoft.de)](https://www.motoscan.de/)
- [MotoScan on Google Play (`de.wgsoft.motoscan`)](https://play.google.com/store/apps/details?id=de.wgsoft.motoscan)
- [UniCarScan UCSI-2100 — 255-byte messages, BMW protocols](https://www.wgsoft.de/unicarscan-ucsi-2100)

## Contributors

- APK acquisition, signature verification, decompile and native-string survey
