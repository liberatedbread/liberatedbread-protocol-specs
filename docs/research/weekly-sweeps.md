# Weekly Device Sweeps

Every week the catalogue gets a short sweep: a few devices from the backlog
become validated specs, and the news since the last sweep is searched for
devices that are newly dying (cloud shutdowns, bankruptcies, withdrawn apps,
new paywalls, firmware that removes local access) or newly popular, where local
control is reasonably achievable. The backlog is
[Missing Devices](missing-devices.md); this page is the dated log on top of it.

Like the survey, each entry is a snapshot. Grep `device-specs/devices/`,
`research-notes/` and `targets/` before starting on anything listed here.
Claims marked *unverified* rest on a search snippet or a page that would not
load, and need checking before they go into a spec.

## 2026-10-11

### Added this week

Four of the survey's [Do these next](missing-devices.md#do-these-next) picks:

| Spec | Survey item | Notes |
|---|---|---|
| [AM43 / A-OK Blind Motor](../devices/am43-blind-motor.md) | #2 | Every frame checked against the XOR rule; six match literal frames in am43-ctrl; `scripts/test_am43_spec.py`. No BLE command to *set* travel limits is public. |
| [Instant Pot Smart Bluetooth](../devices/instant-pot-smart-bluetooth.md) | #1 | Follows OpenPot's code where its README disagrees; every disagreement is in `remaining_unknowns`. `scripts/test_instant_pot_spec.py`. |
| [TiVo Network Remote](../devices/tivo-network-remote.md) | #17 | TCP 31339 remote only; Mind RPC is out of scope. TiVo's own PDF is offline, so facts come from openHAB and McBrine's client. |
| [Drobo NAS Status Daemon](../devices/drobo-nasd-status.md) | #15 | Read-only. The 16-byte header layout rests on one owner's reading of a single 5N2. |

One caveat on the survey's rows, found while writing them: the AM43 row says
the Blind Engine app is off Google Play, which could not be confirmed either
way. The Drobo row's "liquidated in 2023" is the Chapter 7 conversion of April
2023; the fuller timeline is Chapter 11 in June 2022 and the end of sales and
support on 27 January 2023.

### New candidates

Not in the repo or the survey as of this date.

**Orphaned or dying, with a local path**

| Device | Status | Risk | Local path | Public work | Catch |
|---|---|---|---|---|---|
| **Bose Sleepbuds II** | Bose stopped offering the Sleep app on 2025-07-21 ([Bose support](https://support.bose.co.uk/article/sleepbuds-ii-sleep-app-availability)). | A | Phone-direct BLE, one connection per bud: an audio service (`fdc34961-888e-4a93-abf1-b3490d8b231b`) and a settings service (`0xfe21`). | [SleepBuds2Revival](https://github.com/chillee151/SleepBuds2Revival) | No licence on the repo: derive facts only. Tested on one firmware. Keep sound upload and DFU out of scope. |
| **Äike T e-scooter** | Vendor bankrupt ([nns.ee, 2026-01-06](https://blog.nns.ee/2026/01/06/aike-ble/); [The Register](https://www.theregister.com/security/2026/01/16/bankrupt-scooter-startups-single-key-controlled-everything/4963667)). | A | Phone-direct BLE with a SHA-1 challenge-response. | nns.ee write-up | **Handle with care**: the key is identical across the fleet, so a spec is also "unlock any Äike". Owner-held scooters only. |
| **Lexie and Eargo OTC hearing aids** | LXE Hearing is winding down US operations; Lexie's app and cloud were due off 2026-10-08, Eargo's 2026-10-22 ([HearingTracker](https://www.hearingtracker.com/news/lxe-announces-discontinuation-of-eargo-and-lexie-what-users-know)). Whether the 10-08 removal happened is *unverified* (the Play listing still resolved on 2026-10-11). | A | App v9 is said to keep working with its local on-device controls; whether that is a phone-direct Bluetooth link is not stated. | None found | **Research target**, and a medical device. The most time-sensitive item here: captures are only possible while v9 apps still work. |
| **Ampler e-bikes** (Curt, Stout, Axel) | Ampler Bikes OÜ filed for bankruptcy around 2026-05-15 ([ERR News](https://news.err.ee/1610024830/estonian-electric-bicycle-maker-ampler-bikes-files-for-bankruptcy)). | A | The app pairs over BLE; protocol unknown. | None found | **Research target.** Check first whether an existing drive spec already covers its electronics. |

**New or popular, with a local path**

| Device | Status | Risk | Local path | Public work | Catch |
|---|---|---|---|---|---|
| **Besen BS20 EV charger** | Home Assistant core integration in 2026.9; CVE-2026-9394 (weak PIN requirements on the BLE handler), -9395 (credentials exposed over BLE and UDP) and -9398 (capture-replay authentication bypass), all on firmware up to 20260426. | C | BLE GATT ("ACP#"), 6-digit PIN that is often left at 123456. The UDP path on Wi-Fi rests on the CVE text only; the HA integration is BLE-only. | HA `besen` integration | Cap current at the wiring maximum; tell owners to change the PIN. |
| **Yarbo yard robot** | Active; May 2026 security flaws; an official "Open Platform" promised for early 2027. | C | Unauthenticated MQTT broker on the base station, TCP 1883. | [home-assistant-yarbo](https://github.com/markus-lassfolk/home-assistant-yarbo) (MIT) | Blades and auger: attended use only. The vendor may close the broker. |
| **ISEO Argo BLE locks** | HA core integration in 2026.9. | C | Phone-direct BLE with an EC key exchange; the client enrols with the physical master card. | [iseo-argo-ble](https://github.com/FezVrasta/iseo-argo-ble) | Enrolment must be explicit and owner-only. |
| **Elegoo Centauri Carbon** | Active, very popular printer. | C | SDCP WebSocket (and HTTP upload) on TCP 3030, UDP discovery on 3000; the MJPEG stream's port (3031 in the docs' example) comes from the printer's reply. Centauri Carbon only: the CC2 reportedly uses MQTT 1883 and MJPEG on 8080 (*unverified*). | [OpenCentauri](https://github.com/OpenCentauri/OpenCentauri) (MIT) | Heaters: attended use. |
| **Nubert nuControl X-2 / nuPro X** | Active. | C | Phone-direct BLE, one connection. | [nubert-ble-homeassistant](https://github.com/DatNoHand/nubert-ble-homeassistant) (MIT) | Small; the author used AI-assisted RE, so re-check opcodes. |
| **Marstek Venus C / D / E batteries** | Active. | C | Vendor "Open API" on UDP 30000, enabled per device with a community tool (Venus Monitor). | [ha-marstek-local-api](https://github.com/jaapp/ha-marstek-local-api/) | Whether the vendor publishes the API is not established; if it does, link rather than spec. Power setpoints need limits. |
| **Mahle X35 / X35+ / X20 (ebikemotion) drives** | Active. | C | Phone-direct BLE, read-mostly (one write: a switch that powers the bike down). Tested on two bikes only. | [ha-mysmartbike_ble](https://github.com/ReneNulschDE/ha-mysmartbike_ble) (MIT) | Leave out any assist or speed-limit writes. |
| **Hot Spring spas (Connected Spa Kit 2)** | HA core integration in 2026.9. | C | Local polling of the home network adapter. | HA `hotspring` integration | Wire format undocumented; read the integration. |
| **Even Realities G1 / G2 glasses** | Active. | C | Phone-direct BLE. | Gadgetbridge (G1); [even-g2-protocol](https://github.com/i-soxi/even-g2-protocol) (G2 only) | AGPL and unlicensed sources: derive facts only. |
| **Harbor Sleep baby monitor** | HA integration in 2026.8. | C | Mutual-TLS on the LAN with a client certificate exported from the app. | HA integration | Research target; never commit a captured certificate. |
| **Unitree Go2 robot dog** | Active. | C | Local WebRTC; per-device AES key on recent firmware. | [unitree_webrtc_connect](https://github.com/legion1581/unitree_webrtc_connect) | Handle with care (locomotion). |
| **TRMNL e-ink display** | Active; the vendor supports bring-your-own-server. | C | Device polls a self-hosted HTTP server. | [TRMNL developers](https://trmnl.com/developers) | Vendor-documented: link, don't spec. |
| **LEGO SMART Play brick** | Launched 2026-03-01. | C | Encrypted BLE between bricks. | Teardowns only | Research target. |

### Status changes to items already listed

- **Neato Botvac**: heise reported the cloud phase-out in the week of 2025-10-06 ([heise](https://heise.de/-10748987)), earlier than the survey's late-December date. Vorwerk's exchange programme (a Kobold VR7 for EU owners who bought since May 2023 and used the cloud features) is on Neato's own support site.
- **Melnor RainCloud**: Home Assistant 2026.10 removed the integration because the cloud no longer responds ([release notes](https://www.home-assistant.io/blog/2026/10/07/release-202610/)), confirming the survey's April 2026 date.
- **SolarEdge**: the same release dropped SolarEdge Local and added a core SolarEdge Modbus integration, which backs the survey's "Modbus TCP is the durable path". The entry should be re-scoped to Modbus.
- **Tesla Powerwall**: a 2026-09-17 community report says local interfaces were disabled on the customer Wi-Fi after a Powerwall 2 to 3 swap ([HA community](https://community.home-assistant.io/t/recent-tesla-powerall-3-firmwares-remove-local-api-support/1025423)); firmware version not given.
- **Sleep Number**: the sale to SNBR Inc., an affiliate of Sleep Country Canada, was approved 2026-07-20 and closed 2026-07-31 ([Davis Polk](https://www.davispolk.com/experience/sleep-number-sale-sleep-country-canada)); the new owner's plans for the SleepIQ cloud are unknown.
- **Owlet Smart Sock 2**: Owlet's own page now confirms the 2025-04-08 cutoff ([Owlet support](https://support.owletcare.com/hc/en-us/articles/34468745952141-Smart-Sock-2-Support-Ended-USA)).
- **Wallbox**: the restructuring plan became final in July 2026 after a new equity raise, easing the going-concern risk the survey cites.
- **Sense monitor** (`research-notes/sense-monitor.yaml`): Sense's own help centre says consumer monitor sales ended 2025-12-31 or when stock ran out. Still cloud-only, so the note's verdict does not change.
- **TiVo**: one-button and automatic SkipMode end 2026-11-02 in favour of a paid add-on with a 30-day trial (trade press, September 2026); the network remote is unaffected.
- **Enphase Envoy**: a June 2026 Enphase community thread reports `/api/v1/production` and `/api/v1/consumption` stalling on firmware D8.3.5528 (an Envoy-S Metered, upgraded 2026-06-14; the page itself renders only as an error shell, so the detail is from the search snippet). The spec was observed on D8.3.5427; check on the next verification session.
- **Accell group** (Haibike, Ghost, Raleigh, Lapierre, Winora) was declared bankrupt on 2026-08-11. Their bikes use Bosch, Yamaha or Shimano drives, so the drive specs are the relevant coverage.

### No local path

Samsung's Korea-only SmartThings Tracker (service ends 2026-10-31), the
Limitless pendant (Meta acquisition; no public protocol work), Meta Ray-Ban's
paywalled Conversation Focus, Permobil wheelchairs (cloud API deprecated),
Hookii Neomow mowers (vulnerabilities only, no supported path), Spectrum Home
Security and Rad Power Bikes. Senec home batteries are a lead worth a targeted
look: EnBW is winding down new sales, and a community LAN API on Senec.Home V3
is *unverified*.

## 2026-10-11 (second pass)

A same-day second sweep, run after the first pass merged. It takes more of
the survey's [Do these next](missing-devices.md#do-these-next) picks, turns
three of last pass's candidates into specs, graduates one research note, and
opens eight `targets/` stubs for finds that have public work but no protocol
write-up yet.

### Added this week

Five more of the survey's [Do these next](missing-devices.md#do-these-next)
picks, one of last pass's new candidates, and one research note graduated.
Every spec is `testing: untested`; byte-level facts from client code are
`reported`.

| Spec | Survey item | Notes |
|---|---|---|
| [Enel X Way JuiceBox](../devices/enel-x-juicebox.md) | #3 | Plaintext JuiceNet UDP (v09u Gen 2, v07 Gen 1): 25-field status grammar, CMD reply with its 16-bit hash and base-35 check digits, telnet console on TCP 2000, three re-point routes (DNS override, router DNAT, telnet) each staged behind the SoftAP join. Both current commands `advanced` behind a `safety_advisory`: the charger clamps to its rating, not the wiring. The encrypted v09e/v08 firmware (June/Nov 2024) is recognised, not decoded. `scripts/test_enel_x_juicebox_spec.py`. |
| [Sengled Wi-Fi Smart Bulbs](../devices/sengled-wifi-bulb.md) | #5 | Unauthenticated UDP 9080 JSON control (power, brightness, RGB, colour temperature 1-100, discovery broadcast); the setup-AP exchange at the bulb's fixed SoftAP address under RC4 with a fixed public key (`device_encrypted`); the stand-in-cloud replies and the `wifielement/<MAC>/…` MQTT vocabulary for a user-owned broker. Zigbee and BLE-mesh Sengled bulbs excluded. The brief's "WF863" model could not be verified; the Tasmota route is tied to ESP8266EX modules instead. Open: Kelvin endpoints of the 1-100 scale. `scripts/test_sengled_wifi_bulb_spec.py`. |
| [Yummly Smart Thermometer](../devices/yummly-smart-thermometer.md) | #7 | XW2 (T1 dock + P1 probe): TLV service, one-byte challenge ping, probe frames with a reversed MAC, bit-rotation packing (20-bit core in 0.1 °F, 12-bit body in whole °F, 4-bit battery gauge) with 15 worked vectors, computed from the algorithm and labelled `hypothesis`. XW3 (T3 + P3) from the app only, marked untested in `variants`. Food-safety `safety_advisory`. App shutdown 2024-12-18 (RE repo), site and apps 2024-12-20. `scripts/test_yummly_smart_thermometer_spec.py`. |
| [Kano Coding Wand](../devices/kano-coding-wand.md) | #16 | Kano's own `@kano/devices-sdk` (MIT, npm, 2018) survives and names every UUID, so `openness: documented_api`; it settles the quaternion order (int16 LE, w x y z, ×1000) where two community clients disagree. Button, battery, vibration, RGB565 LED, keep-alive, orientation reset, magnetometer calibration, raw temperature, Nordic Secure DFU with both entry writes `advanced`. Administration 2023-06-06 (Gazette). Gesture recognition out of scope. `scripts/test_kano_coding_wand_spec.py`. |
| [Hot Wheels id Race Portal](../devices/hot-wheels-id-race-portal.md) | #18 | Read-only: `HWiD` name, three services under one base UUID, indications for car UID, serial, NDEF car-ID token (21 bytes, base64url) and a float32 pass value whose physical unit is unconfirmed and stays raw. Mattel discontinued the id system 2023-12-31 (vendor FAQ). The authentication service is recorded as wire facts only. Laps are a client-side derivation. `scripts/test_hot_wheels_id_race_portal_spec.py`. |
| [Bose Sleepbuds II](../devices/bose-sleepbuds-ii.md) | last pass's candidate | One peripheral per bud: 12-byte Audio Data frame (play, stop, volume, timer), stored-sound list, clock sync, Settings flags and phone-free toggle, battery, Control Point opcodes (play-in-future, alarms, firmware queries). Sound upload and firmware activation under `out_of_scope` only. Link-layer security `unknown` at low confidence; the name matcher is low-confidence because no source recorded the factory name. Facts only from the unlicensed community client. |
| [QardioArm (A100)](../devices/qardio-arm.md) | graduated from `research-notes/qardio-arm.md` | SIG Blood Pressure service with a full SFLOAT, flags and status decode; vendor control bytes for start and cancel; Just-Works bond with the four ATT error codes that mean re-bond; pinhole bond reset as `factory_reset` and unpair. Medical `safety_advisory`. The original note's dates were loose: the app vanished about 2024-09-21 and returned, servers were intermittent from 2025-03-12 and down for good 2025-04-29. The research note stays as the dated trail. `scripts/test_qardio_arm_spec.py`. |

Three schema gaps surfaced while writing them. One was closed in the same
PR after review: `advanced` was not a declared key on network `commands`,
so the JuiceBox current-limit flag validated only because command objects
are open; the schema now carries the same `advanced` / `advanced_reason`
contract there as on BLE commands and HTTP endpoints. Two remain, noted in
the specs' `remaining_unknowns`: `format.type` has no float (Hot Wheels
speed, Yummly XW3), and the BLE command vocabulary cannot express RGB565
packing (Kano `set_color` is unbound). Candidates for
[spec-evolution](../contributing/spec-evolution.md).

### Tracked for later (new `targets/` stubs)

Each has public code or a dated shutdown but not enough published protocol
to spec from; the stub records what is known and the first experiment.

| Target | Why | Public work | The gap |
|---|---|---|---|
| `fc-smarthome-lock` | Fingerchip / Fingercrystal fingerprint locks (FC SmartHome, Yi-Lock, eApartment, K3 apps). Risk C. | [fc-smart-home-assistant](https://github.com/JuanmanDev/fc-smart-home-assistant) (MIT, 2026-09): 0xfc/0xfe framing, AES-128-ECB per-device key, locks dial TCP 4067 when woken. | How an owner gets the per-device key without the vendor cloud; GATT UUIDs unpublished. A lock: unlock stays `advanced`. |
| `mycoolman-mcmr-fridge` | myCOOLMAN MCMR compressor fridges (MCMR43 confirmed). Risk C. | [mycoolman-ha](https://github.com/HeapsGoodTom/mycoolman-ha) (MIT, 2026-07). | UUIDs and frame layout live only in code; voltage scaling unverified; check the Alpicool family first. |
| `fermob-linkio-lamps` | Fermob Hoopik / MOOON! lamps on the Linkio BLE stack. Risk C. | [ha-fermob](https://github.com/edouardrosset/ha-fermob) (MIT, 2026-05). | The handshake is undocumented; other Linkio brands may share the spec. |
| `roca-inwash-toilet` | Roca In-Wash shower toilets. Risk C. | [roca-inwash-ha](https://github.com/IsaacVI/roca-inwash-ha) (MIT, 2026-08): service `fabaee02-…`, AES challenge keyed by a vendor constant XOR the MAC. | The vendor constant is a secret and stays out of the repo; models and firmware coverage. |
| `delonghi-pinguino-ble-remote` | De'Longhi Pinguino ACs whose remote is a BLE HID peripheral. Risk C. | [pinguino-ha-remote](https://github.com/bdherouville/pinguino-ha-remote) (MIT, 2026-06): an nRF52840 emulates the remote through the AC's SMP pairing gate. | Inverted shape: the AC is the central. The schema has no block for a peripheral *we emulate*; propose one before a spec. |
| `senec-home-v3` | SENEC.Home V2.1 / V3 batteries; EnBW is winding down SENEC sales. Risk B. | pysenec, pysenechome, ioBroker.senec, evcc: unauthenticated JSON POST to `/lala.cgi`, `fl_` hex IEEE-754 values. | Read-only by rule; some firmware dropped daily statistics or answers 405; V4 / Home 4 have no local API at all. |
| `lexie-eargo-hearing-aids` | LXE Hearing wind-down: Lexie app and cloud off 2026-10-08, Eargo 2026-10-22 ([BBB record](https://www.bbb.org/losangelessiliconvalley/quote/request-eargo-inc-415118), [HearingTracker](https://www.hearingtracker.com/news/lxe-announces-discontinuation-of-eargo-and-lexie-what-users-know)). Risk A. | None. | **Most time-critical item in the repo**: captures need a phone that still has the v9 app installed, signed in and synced. A follow-up pass the next day established that the cloud sits in front of the Lexie app's sign-in, not the BLE link, and that Eargo 5-8 aids have no radio at all (control is ultrasonic audio from the phone; BLE reaches only the charger). Medical device; settings within the fitting range only. |
| `ampler-ebike` | Ampler Bikes OÜ bankrupt ~2026-05-15. Risk A. | None. | Own drive electronics, so no existing drive spec applies; collect the APK while it is listed. |

### New candidates

Not in the repo or the survey before this pass.

| Device | Status | Risk | Local path | Public work | Catch |
|---|---|---|---|---|---|
| **Petlibro feeders** | A cloud outage from 2026-08-11 left feeders offline for days; the CEO said schedules run on-device ([Futurism, 2026-08-17](https://futurism.com/future-society/internet-connected-pet-feeders-go-down-cats-hungry)). | C | None known: Wi-Fi models are cloud-driven; whether the BLE on some models carries control is *unverified*. | None found | A capture target only if BLE control exists. |
| **my-PV AC•THOR / AC ELWA 2** | HA core integration in 2026.10. | C | Local HTTP JSON on the LAN, vendor-documented. | my-PV API docs; HA `mypv` | Vendor-documented: link, don't spec. |
| **KACO inverters** | HA core integration in 2026.10 (Modbus TCP). | C | Modbus TCP, vendor-documented register map. | HA `kaco_modbus` | Link, don't spec. |
| **Bitvis Power Hub; Theben Conexa 3.0** | HA core integrations in 2026.10 reading smart-meter HAN ports. | C | Local; the gateway protocols are the vendors'. | HA integrations | Check whether either is documented before anything else. |
| **Vitesy Shelfy** | HA core integration in 2026.10. | C | *Unverified* whether local or cloud. | HA `vitesy` | Read the integration first. |

### Status changes to items already listed

- **Samsung SmartThings**: free API access ends in October 2026; continued use of the cloud API needs a US$4.99/month Personal Plan, and Home Assistant says its integration is affected ([HA docs](https://www.home-assistant.io/integrations/smartthings), [Android Headlines](https://www.androidheadlines.com/2026/06/samsung-smartthings-api-monthly-fees-home-assistant.html)). The `smartthings-hub-v2` spec documents the hub's local surface, which is unaffected; the paywall is one more reason to finish it.
- **June Oven**: the shutdown happened as scheduled on 2026-09-22; Weber declined to open-source the stack ([Digg / The Verge](https://digg.com/tech/9q35hmwm)). The spec's "pair before the cutoff" route is now closed for anyone who did not.
- **Neato Botvac**: the cloud went off on 2025-10-06 ([heise](https://heise.de/-11206228)); Vorwerk's voluntary European exchange programme (a Kobold VR7 for Neatos bought since May 2023 and actively used) is confirmed, announced 2026-04-24 ([Neato support](https://support.neatorobotics.com/support/solutions/articles/204000080637-vorwerk-launches-voluntary-exchange-program-for-neato-customers-in-europe)). Last pass marked it *unverified*.
- **Lexie / Eargo**: the BBB record and HearingTracker's later article agree on 2026-10-08 (Lexie) and 2026-10-22 (Eargo), and extend support to 2026-10-22. Now a `targets/` stub (above).
- **Qardio**: graduated from `research-notes/qardio-arm.md` to a spec (above); technodabbler's 2026-05-19 post-mortem adds the Dutch entity's bankruptcy at its own request.
- **VanMoof**: still no primary source on whether the official key server runs; a third-party app (Mooflet, policy dated 2026-02-12) and Cowboy's Bikey still export the S3/X3 key after one login, so the survey's #4 remains feasible.
- **Fossil Hybrid HR**: no server-shutdown notice found; still time-sensitive, no change.

### No local path

Google Fit's APIs end in late 2026 (a platform, not a device). Fox Sports' smart-TV app closed 2026-05-07. Nothing else new.

## 2026-10-18

The first scheduled sweep. Both 2026-10-11 passes had merged, so the backlog
was re-read against main before picking.

### Added this week

Three more of the survey's [Do these next](missing-devices.md#do-these-next)
picks, all LAN hubs, one of them a graduated research note. Every spec is
`testing: untested`; wire facts from client code are `reported`.

| Spec | Survey item | Notes |
|---|---|---|
| [IKEA TRÅDFRI Gateway (E1526)](../devices/ikea-tradfri-gateway.md) | #19 | CoAP over DTLS-PSK on UDP 5684: mDNS `_coap._udp`, PSK enrolment with the label security code (`/15011/9063`), and the resource and key numbers for lights, outlets, blinds, groups and scenes, plus observe. Reboot and factory reset are `advanced`. Follows pytradfri and node-tradfri-client, which agree. Open: the DTLS cipher suite, the PSK idle-expiry rule and the blind stop value (the two clients send different values). `scripts/test_ikea_tradfri_gateway_spec.py`. |
| [Hörmann BiSecur Gateway](../devices/hormann-bisecur-gateway.md) | #6 | UDP 4001 discovery, then hex-ASCII frames on TCP 4000 with a packet checksum and a transport checksum. The rule reproduces all 30 frames in halacs/BiSecur's tests, and every example in the spec was rebuilt from it with a placeholder MAC and an invented token. Scope is login, door list, position and status, and the impulse. The impulse is `advanced` and carries a `safety_advisory`. SEC Consult's 2020 finding (clear-text logins, takeover of a session from the LAN) is the `security_advisory`. User, port and Wi-Fi management are left out. `scripts/test_hormann_bisecur_gateway_spec.py`. |
| [Insteon Hub (2245-222 / 2242-222)](../devices/insteon-hub.md) | #22, graduated from `research-notes/insteon-hub.*` | Hub v2: HTTP on 25105 with the label's Basic auth, the send / buffer-read / buffer-clear endpoints and the 200-character ring buffer's read rules. Hub v1: raw modem frames on TCP 9761. Standard and extended frames, with the extended-message checksum, cmd1 values, link-database walk and linking. IM reset is `advanced`. The Talos 2018 advisories on firmware 1012 are the `security_advisory`. Insteon Technologies still sells the 2245-222 (2026-10-18). The research note stays as the dated trail. `scripts/test_insteon_hub_spec.py`. |

Corrections to the survey's rows, found while writing them:

- **TRÅDFRI.** IKEA did not stop updating the gateway in July 2024. Its FAQ
  says no new products or features after April 2024, because the gateway hit
  its memory limit, and promises support at least until June 2026. Gateway
  firmware kept coming after that: 1.21.44 (2025-07-01), 1.21.51 (2026-02-10)
  and 1.21.57 (2026-05-04), which IKEA's update feed still offered on
  2026-10-18. July 2024 matches only bulb-firmware releases.
- **BiSecur.** No Hörmann source dates the end of support. "End of 2023 /
  beginning of 2024" comes from halacs's README and nothing is cited behind
  it. A dealer says the gateway has not been sold since December 2020, and
  users saw an in-app change-over notice in October 2023.

Schema gaps that came up: `udp_broadcast.response_format` has no XML value
(BiSecur's discovery reply). No command envelope fits a hex-ASCII frame with
two checksums (BiSecur) or raw binary over TCP (Insteon v1). And no
`instances` shape fits a collection that returns a bare array of ids
(TRÅDFRI). Each spec notes its gap in `remaining_unknowns`.

### New candidates — orphaned or dying, with a local path

| Device | Status | Risk | Local path | Public work | Catch |
|---|---|---|---|---|---|
| **Withings Body+ scale** (and likely other Withings scales) | New paywall. Accounts created on or after 2026-10-13 need Withings+ (US$99.50/yr) for automatic sync to Apple Health, Health Connect and any third-party app, the developer API included. Older accounts are unaffected ([MacRumors, 2026-10-15](https://macrumors.com/2026/10/15/withings-plus-apple-health-syncing); Android Authority would not load). | B | Phone-direct over **Bluetooth Classic**, not BLE: the scale pushes each weigh-in with a per-user ID after an association step. One owner has it reporting to an original ESP32, with the scale's Wi-Fi removed ([didac.dev, 2026-09-03](https://didac.dev/blog/i-made-my-withings-scale-sync-to-home-assistant-without-the-cloud)). | The write-up only. Code "not uploaded yet" and no licence. Protocol details not published. | **Research target.** Classic BT is a shape the schema may not cover well. One unit, two profiles, AI-assisted reverse engineering. The survey's Withings row covers only the Steel HR watch, through Gadgetbridge. |

Nothing else qualifies. Sony's mocopi link app (leaves the stores 2026-10-28)
and Casio's GSW SYSTEM app (support ends 2026-10-31) are under *No local
path*.

### New candidates — new or popular, with a local path

| Device | Status | Risk | Local path | Public work | Catch |
|---|---|---|---|---|---|
| **Keto-Mojo GK+ glucose and ketone meter** | New HACS integration announced 2026-10-17 ([HA community](https://community.home-assistant.io/t/new-integration-keto-mojo-gk-glucose-ketone-meter-over-bluetooth/1029313)). Vendor active. | C | Phone-direct BLE on a vendor service `0003cdd0-0000-1000-8000-00805f9b0131` (not the SIG Glucose 0x1808). Commands go to `cdd2` and replies come on `cdd1`: unit, serial and all stored records as 9-byte records (time, value, meal flag, meal type). Control-solution results are flagged. One connection at a time. No pairing step is described. | [ha-keto-mojo](https://github.com/gjg4000-debug/ha-keto-mojo) (MIT; README says it was worked out independently and contains no vendor code) | Read-only and small, so a clean first spec. It is a medical device, so add a `safety_advisory`. Tested on one meter in mg/dL only. Frame bytes are only in the code. |
| **Easee wall chargers** (Charge Max tested; others claimed) | Community BLE integration first posted 2026-09-13, still active on 2026-10-07 ([HA community](https://community.home-assistant.io/t/easee-ev-charger-ble-integration/1024958)). The company is stable: new majority owner May 2026 and back in profit. | C | Phone-direct BLE with a PIN handshake. The PIN is on the label, not the app password. Errors are named `JPakeError`, which suggests J-PAKE (*unverified*). State, Config and Debug channels. Writes cover current limits, phase mode (1/auto/3), cable lock, LED, reboot and local RFID keys. One BLE connection; the charger must be advertising ("always on", or a 5 s button press). | [ha-easee-ble](https://github.com/parrel/ha-easee-ble) and [easee-ble](https://github.com/parrel/easee-ble) (both MIT) | No protocol doc; everything is in code. Current and phase writes need `advanced` plus a wiring-limit `safety_advisory`. Settings sync both ways with the cloud. Very large European installed base. |
| **Bluetooth SIG Mesh lights and plugs** (generic; tested on a Tuya tunable-white bulb) | New HACS integration posted 2026-10-15 ([HA community](https://community.home-assistant.io/t/aoi-bluetooth-sig-mesh-local-control-of-bluetooth-mesh-lights-and-plugs-no-hub-or-cloud/1029038)). | C | Standard SIG Mesh through a GATT proxy node: provisioning (no-OOB only), Generic OnOff, Light Lightness and Light CTL. | [ha-aoi-sig-mesh](https://github.com/pratikthorat/ha-aoi-sig-mesh) (MIT, forked from tuya-ble-mesh, MIT) | The Bluetooth SIG publishes the protocol: a profile-style spec (like `bthome-v2` / `matter-device`) that links to it, not a reverse-engineering effort. Covers the many no-name Tuya "BLE mesh" devices. Telink proprietary mesh (survey #13, AwoX) is a separate protocol. Network keys must be placeholdered. |

Considered and left out: `hlmblue` / `helium-air-ble` (a BLE air conditioner
whose brand the README does not name; GPL-3.0, 0 stars, control blocked on a
per-unit passkey). Thin until the brand is known.

### Status changes to items already listed

- **Orbit B-hyve** (survey row): a new, broader MIT integration was announced on 2026-10-10 ([HA community](https://community.home-assistant.io/t/local-only-orbit-b-hyve-integration-for-home-assistant-over-bluetooth-le/1028201); [orbit-bhyve-ble](https://github.com/ljmerza/orbit-bhyve-ble), 125 commits). It actuates HT25, HT25G2 and HT25A (Gen2, verified 2026-09-14), HT31 and HT32A, and decodes HT34A; some families use protobuf. AES-128-ECB keystream with a `sum(plaintext)+magic+len` trailer. The per-mesh key is fetched from the cloud once, at setup. This makes the survey's "one 12-star repo" caveat out of date and makes B-hyve a stronger spec pick.
- **Lexie / Eargo**: Eargo's app removal and cloud deactivation on **2026-10-22** still stands ([BBB](https://www.bbb.org/losangelessiliconvalley/quote/request-eargo-inc-415118)), four days from now. No source confirms that the Lexie removal on 2026-10-08 happened (*unverified*). Nothing new on the protocol.
- **Tesla Powerwall**: pypowerwall (MIT) now says that from firmware **25.10.0** Tesla no longer supports routed access to the TEDAPI endpoint at the gateway's fixed address, so a client must join the gateway's own Wi-Fi AP ([pypowerwall](https://github.com/jasonacox/pypowerwall)). The README gives no date for this. It matches the 2026-09-17 Powerwall 3 report and is not new this week.
- **Senec**: this adds detail to the existing target, not news from this week. New-customer business stopped 2026-07-14, E4/P4 orders closed end of August 2026, and installs must be done by 2026-12-31. Service and warranties continue. The article says nothing about the app or cloud ([pv magazine, 2026-07-14](https://www.pv-magazine.de/2026/07/14/enbw-findet-keinen-investor-neukundengeschaeft-von-senec-wird-eingestellt/)).
- **Samsung SmartThings**: no source yet confirms that billing actually started in October. The latest coverage is from June.
- **TiVo SkipMode**: no change. It still ends 2026-11-02, and the price of Premium Auto Commercial Skip is unpublished ([Cord Cutters News](https://cordcuttersnews.com/tivo-plans-to-end-free-automatic-commercial-skipping-in-november-tests-paid-premium-replacement-service/)).
- **No news found this week** on Enphase firmware, Sleep Number / SleepIQ, Petlibro, the VanMoof key server or the Fossil Hybrid key server.

### No local path

Sony mocopi link app: it leaves the stores 2026-10-28, but the sensors still
work with the main mocopi app and PCs move to Sensor Data Receiver
([Sony](https://xyn.sony.net/en/news/20251028)). Casio G-SQUAD PRO GSW-H1000:
support for the GSW SYSTEM app ends 2026-10-31. It is a Wear OS watch
([Casio](https://world.casio.com/support/info/2026/0406/)). Execulink Smart
Home (Canada): the app and self-monitoring end 2026-12-30, and the operator
says the devices keep working locally (operator platform, *unverified*
detail). Zeabur: a cloud host, not a device.
