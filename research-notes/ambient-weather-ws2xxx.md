# Ambient Weather WS-2902x / WS-2000 / WS-5000 — Local Path Research Notes

## What it is
Ambient Weather (US brand, owned by Nielsen-Kellerman since 2019) resells
Fine Offset hardware: WS-2902A/B/C/D all-in-one stations, WS-2000/WS-5000
display consoles, ObserverIP (WS-0900-IP/WS-1400-IP) hub. All push to
ambientweather.net cloud by default.

## Local path — custom-server push (vendor feature)
- Firmware update rolled out ~April 2021 added a **Custom Server** upload
  option: protocol type `Ambient Weather` or `Wunderground`, plus
  user-supplied server IP/hostname, port, path, and interval
  ([HA community thread, 2021-04](https://community.home-assistant.io/t/ambient-weather-available-locally-now-integration-anyone/299180);
  confirmed for WS-2902B via awnet app and WS-2000/WS-5000 on-console menus;
  WXforum WS-5000 thread shows `Gear Setup -> Weather Server -> Customized`).
- Console then HTTP-GETs readings to the LAN host — same wire formats as the
  Ecowitt gateways (these ARE Fine Offset consoles; the Ecowitt/Froggit custom
  server docs apply).
- Configuration via the **awnet app** (held Android package
  `com.dtston.ambienttoolplus` 1.1.29, versionCode 42; iOS) — works over local
  Wi-Fi AP mode; no cloud account needed to set the custom server. AmbientTool /
  WS View Plus apps also configure these consoles (they are FO clones). The old
  `com.ambientweather.awnet` package identifier in this note was not present in
  the held artifact and has been removed rather than treated as a second app.

## BLE onboarding evidence (app-derived, not hardware-verified)
The held awnet APK also contains a BLE provisioning path. Its GATT constants and
call sites establish this map:

| Role | UUID | App behavior |
|---|---|---|
| Service | `0000aaaa-0000-1000-8000-00805f9b34fb` | BLE connection and provisioning |
| TX | `0000bbb0-0000-1000-8000-00805f9b34fb` | Writes Wi-Fi connection requests |
| RX | `0000bbb1-0000-1000-8000-00805f9b34fb` | Subscribes to notifications |

This is a second local onboarding route beside the console's Wi-Fi AP flow, not
evidence that the sensor array uses BLE (its sensor RF remains sub-GHz), and not
a claim that every listed console supports this service. The static decompile has
no completion marker in its log, so these facts are deliberately limited to the
UUIDs and observed call roles.

**Unknown before a client can be implemented:** provisioning packet framing and
response schemas, credential encoding/protection, pairing and bonding, actual
GATT properties, fragmentation/MTU behavior, and model/firmware coverage. No
completed provisioning client or live provisioning success is claimed. An
owner-authorized GATT capture is still needed.

## Receivers for the push (community)
- [dancwilliams/awnet_to_hass](https://github.com/dancwilliams) HA add-on +
  `ambient_station_local` HACS integration (parses the Ambient-protocol GET).
- WeeWX `interceptor` driver (matthewwall/weewx-interceptor) in listen mode.
- Any Ecowitt-protocol parser (FOSHKplugin, ecowitt-controller) since the
  formats match.

## ObserverIP (WS-0900-IP)
Older hub has NO custom server, but serves a local web UI on port 80 with a
`livedata.htm` page — scrapeable HTML table of current readings
(well documented in WeeWX docs/forums). Also interceptable.

## Limitations
- Push-only on the stations: no pull API on WS-2902x/WS-2000/WS-5000 (unlike
  Ecowitt-branded GWxxxx, which add TCP 45000 + HTTP GET). Someone must listen.
- Cloud-only extras: derived fields (dew point, feels-like) are computed
  server-side, not sent in the local push — receivers must compute them.
- WS-2902A (oldest hw rev) may lack the custom-server option; B/C/D confirmed.
- BLE provisioning is only statically mapped as above; it is not an alternative
  data-reading API and its payload format remains unknown.

## Cloud dependency
None once custom server is set. Local onboarding includes the documented console
Wi-Fi AP flow and the app-derived BLE path above. ambientweather.net is optional
for local push. Whether BLE setup can complete with every cloud host blocked has
not been tested.

## Company status (checked 2026-08-07)
Active. ambientweather.net and store live; WS-2902D/WS-5000 still sold.

## APK
The held awnet artifact identifies itself as `com.dtston.ambienttoolplus`
1.1.29 (versionCode 42), with the `awnet` application label. Its acquisition
record and package identity agree. Static analysis supplements, but does not
replace, the community-documented custom-server evidence.

## Rating
**Confirmed** for the custom-server push — vendor feature, multiple community
receivers in production. **Reported** for BLE onboarding — static app evidence
only, with no hardware capture or complete provisioning client.

## Spec-work notes
- Document the Ambient-protocol GET field set (`MAC`, `dateutc`, `tempf`,
  `humidity`, `windspeedmph`, `baromin`, `rainin`, `solarradiation`, `UV`,
  `aqin_*` for indoor AQ, …) vs the Wunderground variant.
- Note derived-field gap (compute dewpoint/feels-like client-side).
- Capture BLE onboarding before declaring provisioning commands or credential
  protection in a validated spec.
