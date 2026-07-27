# Device Specs

Machine-readable specifications for BLE IoT devices. Both the OpenGreenIoT mobile app
and Home Assistant integration consume these specs.

## Format

Device specs are YAML files describing a device's BLE GATT services, characteristics,
and the commands needed to control them.

```yaml
# device-specs/examples/example-bulb.yaml
device:
  name: "Example Smart Bulb"
  manufacturer: "Acme Corp"
  manufacturer_status: "abandoned"
  protocol: "ble"
  identification:
    # How to identify this device during BLE scanning
    local_name_prefix: "ACME_"
    service_uuids:
      - "0000fff0-0000-1000-8000-00805f9b34fb"

services:
  - uuid: "0000fff0-0000-1000-8000-00805f9b34fb"
    name: "Control Service"
    characteristics:
      - uuid: "0000fff1-0000-1000-8000-00805f9b34fb"
        name: "Command"
        properties: ["write"]
        commands:
          power_on:
            description: "Turn the bulb on"
            value: [0x01, 0x01]
          power_off:
            description: "Turn the bulb off"
            value: [0x01, 0x00]
          set_brightness:
            description: "Set brightness level"
            template: [0x02, "{brightness}"]
            parameters:
              brightness:
                type: "uint8"
                min: 0
                max: 100

      - uuid: "0000fff2-0000-1000-8000-00805f9b34fb"
        name: "Status"
        properties: ["read", "notify"]
        format:
          - offset: 0
            length: 1
            name: "power_state"
            type: "bool"
          - offset: 1
            length: 1
            name: "brightness"
            type: "uint8"

entities:
  # How this device maps to Home Assistant entities
  - platform: "light"
    name: "Bulb"
    features: ["brightness"]
    state_characteristic: "0000fff2-0000-1000-8000-00805f9b34fb"
    state_mapping:
      is_on: "power_state"
      brightness: "brightness"
    commands:
      turn_on: "power_on"
      turn_off: "power_off"
      set_brightness: "set_brightness"
```

## Required vs Optional Fields

### `device` (required)

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Human-readable device name |
| `manufacturer` | Yes | Original manufacturer name |
| `manufacturer_status` | Yes | One of: `abandoned`, `shutdown`, `unsupported`, `active` |
| `protocol` | Yes | Primary protocol: `ble`, `wifi`, `zigbee`, `zwave`, `obd2` |
| `notes` | No | Free-text notes about the device |
| `identification` | No | How to auto-discover during scanning |

### `identification` (optional)

| Field | Required | Description |
|-------|----------|-------------|
| `local_name_prefix` | No | BLE advertisement local name prefix |
| `service_uuids` | No | BLE service UUIDs (full 128-bit format) |

### `services` (required, array)

| Field | Required | Description |
|-------|----------|-------------|
| `uuid` | Yes | BLE service UUID (full 128-bit format) |
| `name` | Yes | Human-readable name |
| `characteristics` | Yes | Array of characteristic definitions |

### `characteristics` (required within services, array)

| Field | Required | Description |
|-------|----------|-------------|
| `uuid` | Yes | Characteristic UUID (full 128-bit format) |
| `name` | Yes | Human-readable name |
| `properties` | Yes | Array of: `read`, `write`, `write_without_response`, `notify`, `indicate` |
| `commands` | No | Named commands for writable characteristics |
| `format` | No | Binary format for readable/notifiable characteristics |

### `entities` (optional, array)

Maps device capabilities to Home Assistant entity types. See the example spec for details.

## OBD-II devices (`obd`)

A spec satisfies the schema by carrying `services` (BLE), `http_endpoints` or
`mqtt_topics` (Wi-Fi), **or** `obd` — for devices reached through a vehicle
diagnostic connector rather than a radio. Set `device.protocol: "obd2"` and
describe the diagnostic surface:

```yaml
device:
  name: "Example Motorcycle"
  manufacturer: "Acme Motors"
  manufacturer_status: "active"
  protocol: "obd2"

obd:
  role: "vehicle"                # vehicle | adapter | module
  connector:
    standard: "sae-j1962"        # or iso-19689 (6-pin Euro 5 motorcycle), proprietary
    location: "under the pillion seat"
  transport:
    standard: "iso15765-4"       # CAN with ISO-TP segmentation
    bitrate: 500000
    addressing: "11bit"
    request_id: "0x7E0"
    response_id: "0x7E8"
    verification: "confirmed"
  requests:
    - name: "read_vin_did"
      command_class: "advanced"  # basic = legislated OBD-II; advanced = UDS/manufacturer
      requires: ["custom_headers", "multiframe_rx"]
      service: "22"
      request: "22 F1 90"
      expected_response: "62 F1 90 ??"
      writes: false
      verification: "confirmed"
```

### Device categories

`obd.role` says what the device is on the diagnostic link — `vehicle` (the thing being
diagnosed), `adapter` (the dongle bridging a host to the connector), or `module` (a single
ECU documented on its own).

An `adapter` also carries an `adapter_profile` classifying what it can actually do:

| Class | Hardware | Adds |
|-------|----------|------|
| `basic-clone` | Cloned "ELM327 v2.1" firmware | `single_frame` only |
| `standards-elm327` | Genuine ELM327 v1.4/1.5 | `multiframe_rx`, `custom_headers` |
| `advanced-stn` | STN chipset (OBDLink LX/MX+/CX) | `multiframe_tx`, `flow_control`, `raw_frames` |
| `native-can` | SocketCAN, PCAN, Kvaser | `monitor_all`, `non_standard_bitrate` |

`alt_can_bus` (Ford MS-CAN / GM SW-CAN) is orthogonal to the tiers — only the OBDLink
MX / MX+ / EX carry it, and tools such as FORScan need it for body and chassis modules.

### Referencing vendor description files

Manufacturers describe each ECU in a machine-readable file — a BMW/EDIABAS SGBD (`.prg`)
selected by a group file (`.grp`), or an ODX/PDX container, CDD, A2L or CAN database. Those
files are the authoritative definition of a module's jobs, results, addressing and scaling,
so a spec can point at them instead of relying only on hand-recovered offsets:

```yaml
obd:
  description_files:                 # vehicle level — usually the .grp entry points
    - type: "sgbd-grp"
      name: "D_MOTOR.grp"
      provides: ["jobs", "results"]
      source: "EDIABAS/INPA/ISTA installation (ECU directory)"
      verification: "hypothesis"
  ecus:
    - name: "KOMBI (instrument cluster)"
      description_files:
        - type: "sgbd-prg"
          name: "KOMBI.prg"
          provides: ["jobs", "results", "ecu_address", "scaling"]
  requests:
    - name: "read_odometer"
      request: "22 E1 19"
      job: "STATUS_LESEN"           # the job this frame implements
      results: ["STAT_SERVICE_KMSTAND_DATA"]
```

`job` and `results` tie a recovered frame back to its definition, which is how a consumer
resolves units and scaling without hardcoding byte offsets.

**Reference these files; never commit them.** They are vendor copyright. `source` records
where a licensed copy comes from — an EDIABAS/INPA/ISTA installation, a vendor tool bundle
— not a redistribution link. `sha256` pins the exact file a fact came from so a consumer
can tell whether it is looking at the same one.

### Basic vs advanced commands

Each request carries `command_class` and a `requires` list of capability tokens:

- `basic` — legislated OBD-II (SAE J1979 modes), single-frame, no session or security
  prerequisite. Works on essentially any adapter.
- `advanced` — UDS or a manufacturer dialect: non-default session, security access,
  custom headers, multi-frame, or any write. Needs a capable adapter.

`command_class` defaults to `advanced`, so an unclassified request is never assumed to be
the safe kind. Matching a request's `requires` against an adapter's
`adapter_profile.capabilities` answers "can this dongle run this command?" before
connecting, instead of failing halfway through a write.

Two further conventions differ from the BLE blocks, on purpose:

- **Byte sequences are hex strings** (`"22 F1 90"`), not integer arrays, matching how
  automotive traces are conventionally written. `??` marks an unknown byte position.
- **Every fact carries a `verification`** — `confirmed` (observed in our own capture or
  read back from the device), `reported` (stated by vendor/community documentation but
  not reproduced here), or `hypothesis` (inferred, untested). This lets a spec record
  ranked candidate messages without them being mistaken for facts. Anything not
  `confirmed`, and anything with `writes: true`, must not be executed against a vehicle
  without review.

Vehicles are safety-critical, so specs here document read paths and owner-facing
maintenance functions only. See [`docs/protocols/obd2-common.md`](../docs/protocols/obd2-common.md)
for the transport background and
[`docs/devices/triumph-tiger-900.md`](../docs/devices/triumph-tiger-900.md) for a worked
example.

`device.protocol: "obd2"` is not yet consumed by the mobile Rust `Protocol` enum, so
these specs are documentation and tooling targets today rather than mobile-app targets.

## Extended / optional fields

The schema is intentionally **permissive** (no `additionalProperties: false`),
so specs may carry bespoke, device-specific metadata alongside the standard
fields. In addition to the required fields above, `schema.json` formally
defines several **optional** blocks for richer protocols — including
characteristic-level `encryption` and `framing`, top-and-service-level
`initialization` handshakes, `device.variants`, command-level `encoding` /
`payload`, per-command `parameters.color_order`, top-level `features` and
`protocol_handler`. See `schema.json` (the source of truth) for the exact
shapes and enums. Some optional fields are declarative and require dedicated
consumer-side code; those carry a `NOTE` in the schema `description`.

## Schema Validation

All specs under `device-specs/` are validated against `schema.json` on every
push and pull request by the `validate-specs` job in
[`.github/workflows/ci.yml`](../.github/workflows/ci.yml). The same job also
regenerates `device-specs/index.json` and fails if it is out of date. The
`build` job additionally runs `python scripts/build_index.py --check`,
re-validating every published spec against the schema before the docs (and JSON
API) are built.

To validate locally:

```bash
pip install -r requirements.txt        # installs jsonschema + pyyaml
python scripts/validate_specs.py        # PASS/FAIL per file; exits non-zero on any failure
```

`scripts/validate_specs.py` discovers every `device-specs/**/*.yaml` (top-level,
`examples/`, and `devices/`), validates each against the draft 2020-12 schema,
and prints a `PASS`/`FAIL` line per file with the failing JSON path on error.

## Machine-consumable spec index (`device-specs/index.json`)

`device-specs/index.json` is a generated manifest that lets consumers enumerate
specs automatically instead of hardcoding a file list. It is a JSON array,
sorted by path, of `{ name, path, protocol, manufacturer, manufacturer_status,
protocol_handler (if set), schema_version }`. Regenerate it with:

```bash
python scripts/generate_index.py        # idempotent: no diff on re-run
```

Do not edit `index.json` by hand — it is produced from the specs and checked in
CI.

## Machine-consumable manifest (JSON API)

The single source of truth for consumers is the versioned JSON API generated by
[`scripts/build_index.py`](../scripts/build_index.py). It discovers every spec
under `device-specs/devices/`, validates each against `schema.json`, and emits:

- `site/api/v1/manifest.json` — a registry index with per-device `id`, `name`,
  `manufacturer`, `protocol`, `status`, `updated_at`, `url`, and `sha256`
  checksum.
- `site/api/v1/devices/<id>.json` — each spec normalized to JSON.

```bash
python scripts/build_index.py           # generate site/api/v1/**
python scripts/build_index.py --check   # validate every spec without writing (CI gate)
```

The API is also regenerated into the published site automatically by the
`scripts/mkdocs_hooks.py` post-build hook, so `mkdocs build` always ships a
fresh manifest. See [`docs/api/index.md`](../docs/api/index.md) for the consumer
guide. Only specs under `device-specs/devices/` are published;
`examples/example-bulb.yaml` is a reference example and is intentionally not
included in the manifest.

## Structure

```
device-specs/
├── README.md          # This file
├── schema.json        # JSON Schema for validation
├── index.json         # Generated spec index (scripts/generate_index.py)
├── examples/          # Example specs for reference (not published in the API)
│   └── example-bulb.yaml
└── devices/           # Published device specs (surfaced in the JSON API)
```

## Contributing

1. Reverse engineer the device's BLE protocol (see `docs/re-guide/`)
2. Create a YAML spec following the format above
3. Validate against `schema.json`
4. Place it in `device-specs/devices/`
5. Submit a PR

Even partial specs are welcome -- someone else can fill in the gaps.
