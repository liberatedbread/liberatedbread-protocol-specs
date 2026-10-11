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
| [Drobo NAS Status Daemon](../devices/drobo-nasd-status.md) | #15 | Read-only. Header layout checked on one 5N2. |

Two corrections to the survey's rows, found while writing them: the Blind
Engine app's delisting could not be confirmed either way, and StorCentric filed
Chapter 11 in June 2022 (sales ended 27 January 2023, Chapter 7 in April 2023),
not 2023.

### New candidates

Not in the repo or the survey as of this date.

**Orphaned or dying, with a local path**

| Device | Status | Risk | Local path | Public work | Catch |
|---|---|---|---|---|---|
| **Bose Sleepbuds II** | Bose stopped offering the Sleep app on 2025-07-21 ([Bose support](https://support.bose.co.uk/article/sleepbuds-ii-sleep-app-availability)). | A | Phone-direct BLE, one connection per bud: an audio service (`fdc34961-888e-4a93-abf1-b3490d8b231b`) and a settings service (`0xfe21`). | [SleepBuds2Revival](https://github.com/chillee151/SleepBuds2Revival) | No licence on the repo: derive facts only. Tested on one firmware. Keep sound upload and DFU out of scope. |
| **Äike T e-scooter** | Vendor bankrupt ([nns.ee, 2026-01-06](https://blog.nns.ee/2026/01/06/aike-ble/); [The Register](https://www.theregister.com/security/2026/01/16/bankrupt-scooter-startups-single-key-controlled-everything/4963667)). | A | Phone-direct BLE with a SHA-1 challenge-response. | nns.ee write-up | **Handle with care**: the key is identical across the fleet, so a spec is also "unlock any Äike". Owner-held scooters only. |
| **Lexie and Eargo OTC hearing aids** | LXE Hearing is winding down US operations; Lexie's app and cloud were due off 2026-10-08, Eargo's 2026-10-22 ([HearingTracker](https://www.hearingtracker.com/news/lxe-announces-discontinuation-of-eargo-and-lexie-what-users-know)). Whether the 10-08 removal happened is *unverified*. | A | App v9 is said to keep local Bluetooth control. | None found | **Research target**, and a medical device. The most time-sensitive item here: captures are only possible while v9 apps still work. |
| **Ampler e-bikes** (Curt, Stout, Axel) | Ampler Bikes OÜ filed for bankruptcy around 2026-05-15 ([ERR News](https://news.err.ee/1610024830/estonian-electric-bicycle-maker-ampler-bikes-files-for-bankruptcy)). | A | The app pairs over BLE; protocol unknown. | None found | **Research target.** Check first whether an existing drive spec already covers its electronics. |

**New or popular, with a local path**

| Device | Status | Risk | Local path | Public work | Catch |
|---|---|---|---|---|---|
| **Besen BS20 EV charger** | Home Assistant core integration in 2026.9; CVE-2026-9394, -9395 and -9398 (cleartext credentials, BLE/UDP replay). | C | BLE GATT ("ACP#"), 6-digit PIN that often stays at its default; UDP on Wi-Fi. | HA `besen` integration | Cap current at the wiring maximum; tell owners to change the PIN. |
| **Yarbo yard robot** | Active; May 2026 security flaws; an official "Open Platform" promised for early 2027. | C | Unauthenticated MQTT broker on the base station, TCP 1883. | [home-assistant-yarbo](https://github.com/markus-lassfolk/home-assistant-yarbo) (MIT) | Blades and auger: attended use only. The vendor may close the broker. |
| **ISEO Argo BLE locks** | HA core integration in 2026.9. | C | Phone-direct BLE with an EC key exchange; the client enrols with the physical master card. | [iseo-argo-ble](https://github.com/FezVrasta/iseo-argo-ble) | Enrolment must be explicit and owner-only. |
| **Elegoo Centauri Carbon** | Active, very popular printer. | C | SDCP WebSocket on TCP 3030, UDP discovery on 3000, MJPEG on 3031. | [OpenCentauri](https://github.com/OpenCentauri/OpenCentauri) (MIT) | Primary docs not yet read (*unverified*). Heaters: attended use. |
| **Nubert nuControl X-2 / nuPro X** | Active. | C | Phone-direct BLE, one connection. | [nubert-ble-homeassistant](https://github.com/DatNoHand/nubert-ble-homeassistant) (MIT) | Small; the author used AI-assisted RE, so re-check opcodes. |
| **Marstek Venus C / D / E batteries** | Active. | C | Vendor "Open API" on UDP 30000, off by default. | [ha-marstek-local-api](https://github.com/jaapp/ha-marstek-local-api/) | Possibly vendor-documented (link, don't spec). Power setpoints need limits. |
| **Mahle X20 / X35 (ebikemotion) drives** | Active. | C | Phone-direct BLE, read-mostly. | [ha-mysmartbike_ble](https://github.com/ReneNulschDE/ha-mysmartbike_ble) (MIT) | Leave out any assist or speed-limit writes. |
| **Hot Spring spas (Connected Spa Kit 2)** | HA core integration in 2026.9. | C | Local polling of the home network adapter. | HA `hotspring` integration | Wire format undocumented; read the integration. |
| **Even Realities G1 / G2 glasses** | Active. | C | Phone-direct BLE. | Gadgetbridge; [even-g2-protocol](https://github.com/i-soxi/even-g2-protocol) | AGPL and unlicensed sources: derive facts only. |
| **Harbor Sleep baby monitor** | HA integration in 2026.8. | C | Mutual-TLS on the LAN with a client certificate exported from the app. | HA integration | Research target; never commit a captured certificate. |
| **Unitree Go2 robot dog** | Active. | C | Local WebRTC; per-device AES key on recent firmware. | [unitree_webrtc_connect](https://github.com/legion1581/unitree_webrtc_connect) | Handle with care (locomotion). |
| **TRMNL e-ink display** | Active; the vendor supports bring-your-own-server. | C | Device polls a self-hosted HTTP server. | [TRMNL developers](https://trmnl.com/developers) | Vendor-documented: link, don't spec. |
| **LEGO SMART Play brick** | Launched 2026-03-01. | C | Encrypted BLE between bricks. | Teardowns only | Research target. |

### Status changes to items already listed

- **Neato Botvac**: heise reported the cloud phase-out in the week of 2025-10-06 ([heise](https://heise.de/-10748987)), earlier than the survey's late-December date. A Vorwerk exchange programme from 2026-04-24 is *unverified*.
- **Melnor RainCloud**: Home Assistant 2026.10 removed the integration because the cloud no longer responds ([release notes](https://www.home-assistant.io/blog/2026/10/07/release-202610/)), confirming the survey's April 2026 date.
- **SolarEdge**: the same release dropped SolarEdge Local and added a core SolarEdge Modbus integration, which backs the survey's "Modbus TCP is the durable path". The entry should be re-scoped to Modbus.
- **Tesla Powerwall**: a 2026-09-17 community report says local interfaces were disabled on the customer Wi-Fi after a Powerwall 2 to 3 swap ([HA community](https://community.home-assistant.io/t/recent-tesla-powerall-3-firmwares-remove-local-api-support/1025423)); firmware version not given.
- **Sleep Number**: the sale to Sleep Country Canada closed 2026-07-31 ([Davis Polk](https://www.davispolk.com/experience/sleep-number-chapter-11-filing-dip-financing-and-stalking-horse-apa)); the new owner's plans for the SleepIQ cloud are unknown.
- **Owlet Smart Sock 2**: Owlet's own page now confirms the 2025-04-08 cutoff ([Owlet support](https://support.owletcare.com/hc/en-us/articles/34468745952141-Smart-Sock-2-Support-Ended-USA)).
- **Wallbox**: the restructuring plan became final in July 2026 after a new equity raise, easing the going-concern risk the survey cites.
- **Sense monitor** (`research-notes/sense-monitor.yaml`): Sense stopped selling the consumer monitor on 2025-12-31 (secondary source); risk moves to B. Still cloud-only.
- **TiVo**: free SkipMode reportedly ends 2026-11-02 in favour of a paid add-on (*unverified*); the network remote is unaffected.
- **Enphase Envoy**: a June 2026 community thread reports `/api/v1/production` stalling on firmware D8.3.5528 (*unverified*, page did not load). The spec was observed on D8.3.5427; check on the next verification session.
- **Accell group** (Haibike, Ghost, Raleigh, Lapierre, Winora) was declared bankrupt on 2026-08-11. Their bikes use Bosch, Yamaha or Shimano drives, so the drive specs are the relevant coverage.

### No local path

Samsung's Korea-only SmartThings Tracker (service ends 2026-10-31), the
Limitless pendant (Meta acquisition; no public protocol work), Meta Ray-Ban's
paywalled Conversation Focus, Permobil wheelchairs (cloud API deprecated),
Hookii Neomow mowers (vulnerabilities only, no supported path), Spectrum Home
Security and Rad Power Bikes. Senec home batteries are a lead worth a targeted
look: EnBW is winding down new sales, and a community LAN API on Senec.Home V3
is *unverified*.
