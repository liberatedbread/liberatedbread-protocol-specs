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
| `manufacturer_status` | Yes | One of: `abandoned`, `shutdown`, `unsupported` |
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

## Schema Validation

All specs are validated against `schema.json` in CI. To validate locally:

```bash
pip install pyyaml jsonschema
python -c "
import json, yaml, jsonschema
schema = json.load(open('device-specs/schema.json'))
spec = yaml.safe_load(open('device-specs/examples/example-bulb.yaml'))
jsonschema.validate(spec, schema)
print('Valid!')
"
```

## Structure

```
device-specs/
├── README.md          # This file
├── schema.json        # JSON Schema for validation
├── examples/          # Example specs for reference
│   └── example-bulb.yaml
└── devices/           # Actual device specs (added as devices are RE'd)
```

## Contributing

1. Reverse engineer the device's BLE protocol (see `docs/re-guide/`)
2. Create a YAML spec following the format above
3. Validate against `schema.json`
4. Place it in `device-specs/devices/`
5. Submit a PR

Even partial specs are welcome -- someone else can fill in the gaps.
