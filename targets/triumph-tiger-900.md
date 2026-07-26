# Triumph Tiger 900 target spec

## Target metadata
- target_id: triumph-tiger-900
- app package_id(s): com.tuneecu_lite (free "diagnosis and test" build), com.tuneecu
  (paid full app, Alain Fontaine). TigerTool and DealerTool are Windows-only.
- device class: motorcycle ECU / instrument cluster diagnostics
- transport(s): OBD-II connector, ISO 15765-4 (CAN); Bluetooth SPP between phone app and OBD adapter
- local-only viability: high -- the diagnostic bus is entirely local; the gate is a closed
  application-layer message plus tool licensing, not a cloud dependency

## Known facts (public + observed)
- Tiger 900 (2020-2023) uses a SAE J1962 16-pin diagnostic connector under the pillion
  seat; Gen 2 (MY2024+) moved to the 6-pin ISO 19689 Euro 5 connector (red).
- TigerTool documents its ECU families as ISO 9141-2 + ISO 15765-4 for Mk1 Tiger 800-era
  ECUs, and "primarily ISO15765-4 (aka CAN bus)" for later ECUs. Tiger 900 is the latter.
- Third-party tools reach the ECU through an ordinary ELM327-class adapter, but the
  service interval reset specifically requires an OBDLink LX/MX (STN chipset) on many
  Triumph models while DTC reads work on anything.
- The service reminder has two parts: a distance component reset over diagnostics, and a
  calendar date component reset from the bike's own instrument menu on newer models.
- Odometer and service values are stored in the instrument cluster in kilometres.
- Interval granularity is 100 units; Tiger 900 maximum is 6000 miles / 10000 km.
- The wrench reappears 500 miles / 800 km before the service-due distance.
- A failed reset can lock out further diagnostic functions until the tool reconnects.
- TuneECU requires the bike's clock/date to be set before running the reset.
- TigerTool does not connect to Gen 2 (MY2024+) bikes -- Triumph relocated ECU data.
- TuneECU ships two Android builds: `com.tuneecu` (paid) and `com.tuneecu_lite` (free,
  "diagnosis and test of the ECU", no remapping). The Lite build is the clean
  static-analysis lead: it is distributed free, and diagnosis/test is exactly the code
  path that carries the Triumph dialect.
- TuneECU Lite's own listing states clone ELM327 v2.1 adapters do not work and a genuine
  v1.4/1.5 is required -- independent corroboration that the vendor traffic depends on
  correct adapter behaviour rather than on anything exotic in the bike.
- The Windows TuneECU (freeware, ISO 9141-era Triumph ECUs) is discontinued and no longer
  distributed by the author; support is Android-only.
- TuneECU's published documentation is UI-level only. The official Android description PDF
  is a scanned image with no text layer, and the online guide covers adapters and model
  support without any message-level detail. The bytes are in the app, not the manual.

## Device discovery signals
- OBD / CAN:
  - connector: SAE J1962 (2020-2023) / ISO 19689 6-pin (MY2024+), under the pillion seat
  - bus: ISO 15765-4, expected 11-bit at 500 kbit/s (to be confirmed by capture)
  - expected physical addressing: 0x7E0 request / 0x7E8 response (unconfirmed for Triumph)
  - functional broadcast: 0x7DF (emissions modes only)
- Bluetooth (tool side, not the bike):
  - OBDLink LX/MX adapter, RFCOMM/SPP, ASCII ELM327 command set

## Threat model + guardrails
- Scope: only a bike the researcher owns, stationary, on a stand, engine off, ignition on.
- Vehicles are safety-critical. No writes to ABS, immobiliser, TPMS or engine-map memory.
- Non-goals: ECU flashing, remapping, immobiliser defeat, odometer alteration.
- Goal: document the service interval reset message so an owner who has done their own
  service can clear their own reminder without a dealer visit or a paid tool.

## First experiments (do these first)
0) APK static analysis of `com.tuneecu_lite` (free build, so `apkeep -a com.tuneecu_lite`
   or `scripts/pull_apks_adb.sh` are both legitimate). Run
   `scripts/run_static_target.sh triumph-tiger-900` and grep the decompile for:
   - ELM327 setup strings: `ATSP`, `ATSH`, `ATCRA`, `ATFC`, `ATCAF`
   - service bytes and their positive responses: `31 01`/`71`, `2E`/`6E`, `22`/`62`,
     `10 03`/`50`, `27 01`/`67`, `3B`/`7B`
   - resource strings around the adjustments UI: "Reset", "Service", "Interval", "SIA",
     "Validate", plus the km/miles selector
   - byte-array literals near those strings, and any per-model table keyed on ECU id
   Analyse `com.tuneecu` (paid) only from a copy the researcher owns.
1) btsnoop HCI capture of a vendor Android tool performing one service reset against an
   owned bike; the ELM327 protocol is ASCII so the request appears in clear text in the
   RFCOMM stream. This confirms whatever the decompile suggests.
2) Passive CAN log at the diagnostic connector (`candump -L can0`) across the same
   operation; diff idle traffic against reset traffic.
3) Read-only UDS DID sweep with `scripts/obd_discover.py` to map which identifiers hold
   the odometer, the service-due distance and the service date.
4) Determine whether the service data is owned by the engine ECU or the instrument
   cluster, and whether the cluster has its own diagnostic address.

## Protocol hypotheses (to validate)
- Session: `10 03` extended diagnostic session before the reset; `3E 00` keepalive.
- Security: possible SecurityAccess `27 01`/`27 02` seed/key -- region-locked ECUs are
  reported on some liquid-cooled Triumphs.
- Reset message, ranked:
  - H1 RoutineControl `31 01 <RID> [interval]` -> `71 01 <RID>`
  - H2 WriteDataByIdentifier `2E <DID> <km u16>` -> `6E <DID>`
  - H3 H2 plus a second write carrying the service date
  - H4 KWP2000 `3B <LID> <data>` dialect carried over from the ISO 9141 ECUs
- Payload encoding: distance almost certainly kilometres as a scaled integer (100-unit
  granularity, 10000 km ceiling fits a uint16 comfortably).
- Timing constraints: multi-frame ISO-TP with flow control -- the adapter requirement is
  the evidence.
- Model-year split: 2020-2023 and MY2024+ must be validated separately.

## Control surface inventory (what the replacement app must support)
- Adapter connect + protocol selection (ISO 15765-4, 11-bit, 500 kbit/s)
- Read odometer, current service interval, service-due distance and date
- Set service interval (100-unit granularity, clamped to the model maximum)
- Execute the reset and confirm by read-back
- Read and clear DTCs (already possible with generic tools)
- Clear error reporting when the ECU refuses (map UDS NRCs to plain language)

## Evidence checklist
- TuneECU Lite APK hash + version code: pending
- Decompile grep results for ELM327 setup strings and UDS service bytes: pending
- btsnoop HCI log of a vendor tool reset: pending
- CAN capture (candump / SavvyCAN) of the same operation: pending
- DID sweep output: pending
- Read-back proof that the dash value changed: pending

## Spec output (clean-room)
Write a derived spec in:
- docs/devices/triumph-tiger-900.md
- device-specs/devices/triumph-tiger-900.yaml

## References (URLs only)
- https://www.bmdiag.co.uk/user/tiger%20tool/TigerTool%20V3.0%20Instructions.pdf
- https://tuneecu.fr/docs/_en/Basic_guide.html
- https://www.tiger800.co.uk/index.php?topic=32836.0
- https://www.tiger800.co.uk/index.php?topic=27014.0
- https://www.iso.org/standard/66030.html
- https://www.healtech-electronics.com/products/mm/
- https://www.triumph675.net/threads/ecu-to-dash-can-bus-message-ids.242889/
