## Machine-Readable Discovery

Every device spec in `device-specs/devices/` now includes a `device.discovery`
section that a consumer app can parse to implement automatic discovery without
per-device hardcoding. See the `discovery` property in
[device-specs/schema.json](../device-specs/schema.json) for the full JSON
Schema definition. See the discovery reference at
[docs/devices/discovery.yaml](../docs/devices/discovery.yaml) for a
annotated example of each discovery method.

The flows documented below are the SSDP, mDNS, and Cloud variants that
correspond to the machine-readable `device.discovery.methods[].type` values.

# WiFi Device Discovery

WiFi devices in this repository do not all use the same discovery model. The
right first step depends on whether the device exposes a local protocol, an
mDNS service, or only a cloud account API.

## SSDP / UPnP: Wemo

Wemo devices should be discovered with SSDP first. Users should not have to
enter static IP addresses.

Send an M-SEARCH UDP multicast packet to `239.255.255.250:1900`:

```http
M-SEARCH * HTTP/1.1
HOST: 239.255.255.250:1900
MAN: "ssdp:discover"
MX: 1
ST: urn:Belkin:service:basicevent:1
```

Useful Wemo search targets:

| Search target | Use |
|---|---|
| `urn:Belkin:service:basicevent:1` | Broad Wemo local-control discovery |
| `urn:Belkin:device:controllee:1` | Mini plug / controllee-class devices |
| `urn:Belkin:device:socket:1` | Socket / WiFi smart plug devices |
| `urn:Belkin:device:insight:1` | Insight smart plug |
| `ssdp:all` | Fallback when device-specific ST values miss |

Each response includes a `LOCATION` header, normally:

```text
LOCATION: http://<ip>:<port>/setup.xml
```

Fetch that URL and parse `/setup.xml`. The important fields are:

| Field | Purpose |
|---|---|
| `deviceType` | Variant match, for example `urn:Belkin:device:insight:1` |
| `UDN` | Primary stable identity and ordering key |
| `serialNumber` | Secondary stable identity |
| `macAddress` | Tertiary stable identity |
| `friendlyName` | Display name only |
| `serviceList` | SOAP `controlURL` and `eventSubURL` values |

Wemo HTTP ports are not stable. If SSDP is stale or a known device stops
answering, rediscover with SSDP or probe the pywemo port order:

```text
49153, 49152, 49154, 49151, 49155, 49156, 49157, 49158, 49159
```

Example:

```bash
python scripts/wemo_discover.py --timeout 5
```

Expected output shape:

```text
IP               Port   Name                     Device Type                            Serial
----------------------------------------------------------------------------------------------
192.168.1.42     49153  Kitchen Plug             socket                                 2216...
        Service: basicevent           CTRL=/upnp/control/basicevent1     EVENT=/upnp/event/basicevent1
        Service: metainfo             CTRL=/upnp/control/metainfo1       EVENT=/upnp/event/metainfo1
```

## mDNS / DNS-SD: Vector

Vector robots advertise a local mDNS service:

```text
_ankivector._tcp.local.
```

Use Zeroconf/Bonjour to browse that service type. The service record gives the
robot hostname, IP address, port, and TXT metadata such as serial fields when
advertised.

Example:

```bash
python scripts/vector_discover.py --timeout 5
```

Expected output shape:

```text
Found 1 Vector robot(s):

  Name:       Vector-A1B2
  Hostname:   Vector-A1B2.local.
  Address:    192.168.1.43
  Port:       443
  Serial:     00e00000
```

Discovery only locates the robot. Control still requires TLS certificate
pinning and a GUID bearer token from Vector onboarding.

## Cloud API: Frigidaire / Electrolux

Frigidaire connected air conditioners are documented as WiFi cloud devices.
They are not BLE devices, and no local SSDP, mDNS, or static-IP LAN API has
been verified.

Discovery is account-based:

1. Pair the AC in the Frigidaire/Electrolux app.
2. Authenticate to the Electrolux cloud/OCP account.
3. Enumerate appliances assigned to that account.
4. Send commands through the confirmed cloud API or broker.

This means local network scans are not expected to find a usable control
endpoint. If the cloud service disappears, replacement control will likely
require a cloud API reimplementation, DNS redirection plus protocol capture, or
firmware-level work.

## Identification Matrix

| Device family | Discovery | Primary type identifier | Stable ordering/naming |
|---|---|---|---|
| Wemo Mini Plug | SSDP/UPnP | `urn:Belkin:device:controllee:1` or `socket:1` | `UDN`, then serial, then MAC; display `friendlyName` |
| Wemo WiFi Plug | SSDP/UPnP | `urn:Belkin:device:socket:1` | `UDN`, then serial, then MAC; display `friendlyName` |
| Wemo Insight | SSDP/UPnP | `urn:Belkin:device:insight:1` | `UDN`, then serial, then MAC; display `friendlyName` |
| Wemo Light Switch | SSDP/UPnP | `urn:Belkin:device:Lightswitch:1` | UDN prefix separates Gen1/Gen2/3-way |
| Wemo Dimmer v1/v2 | SSDP/UPnP | `urn:Belkin:device:dimmer:1` | UDN prefix/model metadata separates v1 and v2 |
| Wemo Maker | SSDP/UPnP | `urn:Belkin:device:Maker:1` | `UDN`, then serial, then MAC |
| Wemo Outdoor Plug | SSDP/UPnP | `urn:Belkin:device:outdoor:1` | `UDN`, then serial, then MAC |
| Wemo Motion | SSDP/UPnP | `urn:Belkin:device:motion:1` or `sensor:1` | `UDN`, then serial, then MAC |
| Wemo Bridge | SSDP/UPnP | `urn:Belkin:device:bridge:1` | Bridge `UDN`; child bulbs use bridge end-device IDs |
| Wemo appliances | SSDP/UPnP | `coffeemaker:1`, `crockpot:1`, `heater:1`, `purifier:1`, `humidifier:1` | `UDN`, then serial, then MAC |
| Vector Robot | mDNS/DNS-SD | `_ankivector._tcp.local.` | Service name, hostname, TXT serial |
| Frigidaire AC | Cloud API | Electrolux account appliance ID | Cloud appliance ID and app display name |

For Wemo, ports are never the identity. Ports are connection details discovered
from SSDP `LOCATION` or from the fallback probe list.
