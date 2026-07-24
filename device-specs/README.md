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
| `protocol` | Yes | Primary protocol: `ble`, `wifi`, `zigbee`, `zwave` |
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
