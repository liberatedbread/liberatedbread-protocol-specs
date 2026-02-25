# Common BLE Patterns

## Standard GATT Services

| UUID | Service | Purpose |
|------|---------|---------|
| `0x1800` | Generic Access | Device name, appearance |
| `0x180A` | Device Information | Manufacturer, model, firmware |
| `0x180F` | Battery Service | Battery level |

## Common Custom Service Patterns

### Single-Service Command Interface

Many IoT devices use one write characteristic and one notify characteristic.

### Command Structure

Common packet format:
```
[Header] [Command ID] [Payload Length] [Payload...] [Checksum]
```

Common checksums: XOR of all bytes, sum mod 256, CRC-8.

## Authentication Patterns

- **No auth**: Just connect and write (common in cheap devices)
- **Simple PIN**: Write PIN to auth characteristic first
- **Challenge-response**: Read challenge, compute response with shared key
