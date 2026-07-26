# BMW motorcycle diagnostics (MotoScan) target spec

## Target metadata
- target_id: bmw-motorcycle-motoscan
- app package_id(s): de.wgsoft.motoscan (MotoScan for BMW Motorcycles, WGSoft.de)
- device class: motorcycle ECU / cluster diagnostics
- transport(s): OBD-II connector; BMW KWP2000, KWP2000*, D-CAN and UDS
- local-only viability: high -- the diagnostic bus is local and the adapter command set is
  ELM327-compatible. The gate is a paid app plus closed BMW application-layer messages.

## Why this target
The Triumph work (see `targets/triumph-tiger-900.md`) showed that a motorcycle service
interval reset is a short proprietary frame to the instrument cluster, recoverable from the
tools that already speak it. BMW is the same shape of problem with a different vendor, and
MotoScan is the tool that covers it.

There is a useful structural detail here: **MotoScan and the UniCarScan UCSI-2100 adapter
come from the same vendor, WGSoft.de.** The adapter's headline feature is accepting
messages up to 255 bytes where a stock ELM327 stops at 8 — that is not a general-purpose
selling point, it is what BMW's protocols need. The adapter tells you something about the
protocol before the app is even opened.

## Known facts (public)
- Package `de.wgsoft.motoscan`, Android 6.0+, vendor WGSoft.de (motoscan.de).
- Covers BMW C-, F-, G-, K- and R-series motorcycles.
- Functions: live data, fault-code read and clear, ECU coding, **service interval reset**,
  adaptations and actuator tests.
- Supported adapters: OBDLink LX/MX, UniCarScan UCSI-2000/2100, and ELM327 "with
  restrictions" -- the same tiering seen across every vendor tool in this repo.
- Protocols, from the UCSI-2100's own specification: BMW KWP2000, KWP2000*, D-CAN, UDS,
  alongside the legislated ISO9141-2, KWP2000 slow/fast init and CAN 11/29-bit at 250 and
  500 kbit/s.
- Distribution is Google Play only -- unlike TuneECU, the vendor publishes no direct APK.
  A Lite build exists for testing before purchase.

## Acquisition status
Not yet obtained. The vendor site links only to Play, and third-party APK mirrors
(apkpure, apkcombo, apkmirror, aptoide) are unreachable from this environment. Legitimate
routes:
- `adb shell pm path de.wgsoft.motoscan` then `adb pull` from a device that owns it --
  this is what `scripts/pull_apks_adb.sh` does, and it is the preferred route for a paid app.
- `apkeep -a de.wgsoft.motoscan` from a machine with normal browser-grade network access.

## First experiments (do these first)
1) Obtain the APK by one of the routes above; record SHA-256 and version code.
2) Decompile (jadx). The TuneECU pass showed the payoff is highest in two places:
   - per-stack ELM327 init arrays, which fall out as plain string constants and map the
     whole bus topology at once (`ATSH`, `ATCRA`, `ATTP`, `ATCP`, `ATIIA`, `ATPB`)
   - the command builders, where the interesting scaling lives (Triumph's reset turned out
     to be `distance / 100` in a single line)
3) Grep for the service reset specifically: BMW service data is conventionally in the
   instrument cluster or a central body ECU, so expect a non-`0x7E0` address.
4) Compare the recovered CAN IDs against the Triumph map. The interesting question is
   whether "service data lives in the cluster behind a proprietary raw-frame protocol" is
   a Triumph quirk or a motorcycle-industry pattern.

## Protocol hypotheses (to validate)
- BMW's D-CAN is ISO 15765-4 with BMW addressing; KWP2000* is a BMW variant of KWP2000
  over K-line. Both are named by the adapter vendor, so both are in play depending on
  model year.
- Long-message support (255 bytes) implies coding/adaptation writes that exceed a single
  ISO-TP frame, i.e. real multi-frame transmit rather than the two-byte frames Triumph's
  cluster uses.
- ECU coding implies SecurityAccess (`27`) somewhere in the stack.
- Service interval reset is likely a routine or a value write to whichever module owns the
  odometer, on a manufacturer-specific address.

## Threat model + guardrails
- Scope: only a bike the researcher owns, stationary, engine off.
- Vehicles are safety-critical. Read-only work. No ABS, immobiliser or engine-map writes.
- ECU coding can brick modules and is explicitly out of scope for this repo.
- Non-goals: odometer alteration, immobiliser defeat, emissions-control tampering.

## Control surface inventory (what a replacement would need)
- Adapter connect and protocol selection across KWP2000 / D-CAN / UDS
- Read fault codes and live data
- Read service interval and odometer state
- Reset the service interval, with read-back confirmation

## Evidence checklist
- MotoScan APK hash + version code: pending
- Decompiled init sequences and CAN IDs: pending
- Service reset command bytes: pending
- Hardware confirmation with read-back: pending

## Spec output (clean-room)
Write a derived spec in:
- docs/devices/bmw-motorcycle-diagnostics.md
- device-specs/devices/bmw-motorcycle-diagnostics.yaml

## References (URLs only)
- https://www.motoscan.de/
- https://play.google.com/store/apps/details?id=de.wgsoft.motoscan
- https://www.wgsoft.de/unicarscan-ucsi-2100
