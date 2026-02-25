# Common WiFi Patterns

## Local HTTP API

Many WiFi IoT devices run a local HTTP server.

### Discovery
- **mDNS/Bonjour**: `_http._tcp` or custom service type
- **SSDP/UPnP**: Less common in newer devices
- **Fixed IP / AP mode**: Configure via access point

### API Patterns

Most local APIs use REST-ish JSON:

```http
GET /api/status
POST /api/control {"command": "set_brightness", "value": 50}
```

## Cloud API Relay

When the cloud server dies, control dies too. General replacement strategy:
1. Capture cloud communication
2. Set up local server mimicking cloud API
3. Redirect device via DNS override or firmware mod
