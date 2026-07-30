# Candidate Devices & Hardware Sourcing

**Survey date: 2026-07-30.** Candidates were checked against the 69 specs in
`device-specs/devices/` and the 51 target stubs in `targets/`; nothing on this
page duplicates existing coverage.

This page answers two questions at once:

1. **What should we document next?** Devices whose vendor cloud is dead or dying,
   where enough public protocol work already exists to write a clean-room spec.
2. **What does the verification hardware cost?** Every candidate carries a real
   listing price, so a spec can be confirmed against hardware instead of
   staying a paper exercise.

!!! warning "Prices are snapshots, not quotes"
    All prices are eBay US listings observed on **2026-07-30**, sorted by
    lowest total price (item + shipping). They move constantly, and the
    cheapest listing is often "parts only" — the notes say which. Re-check
    before buying. Amazon was not surveyed programmatically (it returns 503 to
    automated fetches); Amazon prices for the new-hardware items in Tier 3 and
    Tier 6 are generally within a few dollars of the eBay figures.

!!! note "Clean-room discipline still applies"
    A public reverse-engineering write-up is a *reference*, not a license to
    copy. Follow [Clean-room Rules](../CLEANROOM_RULES.md): cite the source,
    re-derive the protocol, and never lift code or vendor assets into a spec.

---

## Tier 1 — Orphaned by the vendor (highest mission fit)

These are the devices the project exists for: hardware that still works but
whose cloud has been switched off.

### 1. Spotify Car Thing

| | |
|---|---|
| Transport | USB (serial/ADB), Bluetooth |
| Status | **Bricked by vendor** — killed 2024-12-09; Spotify issued refunds |
| Public RE | [err4o4/spotify-car-thing-reverse-engineering](https://github.com/err4o4/spotify-car-thing-reverse-engineering), [iFixit custom-firmware guide](https://www.ifixit.com/Guide/How+to+Install+Custom+Firmware+onto+Car+Thing/178814), Nocturne replacement firmware (2026) |
| Cheap unit | **$40** used (no cable, auction) — $68 open-box, typical range $54–$75 |

The bootloader is unlocked-able and the community already has feature-parity
firmware. What is missing is a written protocol/interface spec: the USB
control surface, the display bus, and the dial/button event encoding. Good
first Tier-1 target because the device is inert without documentation.

### 2. Neato Botvac Connected (D3/D4/D5/D6/D7)

| | |
|---|---|
| Transport | Wi-Fi (cloud, now dead) + internal UART serial console |
| Status | **Cloud shut down 2025** by Vorwerk; app control and scheduling gone |
| Public RE | [pybotvac](https://pypi.org/project/pybotvac/) (Nucleo cloud API, RE by Lars Brillert), [RobertSundling/neato-botvac](https://github.com/RobertSundling/neato-botvac/discussions/12), `neato-connected` ESP32-on-UART approach |
| Cheap unit | **$99.99** used complete D5. Parts/spares $3–$15 |

The interesting half is the **local serial command set** on the robot's RX/TX
pads — that is what survives the cloud shutdown, and it is only documented as
scattered forum posts. Vorwerk explicitly refused to release the cloud API,
so this is the canonical "documentation is the only rescue" case. Most
expensive Tier-1 buy; worth one unit.

### 3. Logitech Harmony Hub

| | |
|---|---|
| Transport | Wi-Fi LAN — local WebSocket API + (restored) XMPP |
| Status | **Product line discontinued**; local API was removed in firmware 4.15.206, then restored in 4.15.250 as officially-unsupported |
| Public RE | [JordanMartin/harmonyhub-api](https://github.com/JordanMartin/harmonyhub-api), [maddox/harmony-api](https://github.com/maddox/harmony-api/issues/106) |
| Cheap unit | **$9.99** used hub-only — $10–$18 is the normal band |

Cheapest Tier-1 hardware by a wide margin, and the precedent matters: a vendor
removed a local API and public pressure got it back. A spec pins that down so
the next firmware change cannot quietly take it away again. Slots naturally
into the existing **WiFi Devices** cluster alongside `roku-ecp` and
`hue-bridge`.

### 4. Bose SoundTouch

| | |
|---|---|
| Transport | Wi-Fi LAN — local HTTP/XML API, plus Bluetooth/AirPlay |
| Status | **Cloud ended 2026-05-06** (extended from 2026-02-18). Bose shipped a final offline-capable app *and published the API* |
| Public reference | [Bose SoundTouch end-of-life page](https://www.bose.com/soundtouch-end-of-life), [SoundTouchPlus HA component](https://github.com/thlucas1/homeassistantcomponent_soundtouchplus/discussions/37) |
| Cheap unit | **$29.97–$50** parts-only SoundTouch 10; **~$60–$70** for a tested working unit |

Note this one needs *documentation*, not reverse engineering — Bose released
the specs. That makes it the fastest spec on this page to write and the
easiest to verify, and it is a useful contrast case in the docs: the vendor
did the right thing on the way out.

### 5. Insteon Hub 2245-222

| | |
|---|---|
| Transport | Wi-Fi/Ethernet LAN HTTP API; Insteon powerline + 915 MHz dual-mesh |
| Status | **Cloud died abruptly in 2022** when SmartLabs folded (later revived by a user group) |
| Public reference | Insteon's own published developer guides; `pyinsteon`, `insteon-terminal` |
| Cheap unit | **$14.88–$22** used hub; $9.99 parts-only |

Two protocol layers worth separate specs: the hub's local HTTP interface and
the underlying Insteon message format over the PLM serial link. The dual-band
powerline mesh is a transport the repo has no coverage of at all.

### 6. Nest Learning Thermostat, 1st & 2nd generation

| | |
|---|---|
| Transport | Wi-Fi (Weave/TLS, port 9243) |
| Status | **Support ended October 2025** after 14 years |
| Public RE | Fragmentary. No complete public local protocol map located |
| Cheap unit | **~$22.95** tested working; $15.90 unit-only, $10 parts-only |

Listed for reach, not for readiness — a very large installed base went dark at
once. Be honest about the state: the local Weave interface is authenticated
and not publicly mapped, so this is a **research target**, not a spec that can
be drafted from existing sources. Buy one only if someone intends to do the
capture work.

---

## Tier 2 — Cheap BLE sensors that extend families we already cover

Low cost, low risk, and each one broadens an existing spec cluster rather than
starting a new one.

| Device | Why | Public RE | Cheap unit |
|---|---|---|---|
| **Govee H5074 / H5179** | Extends the existing `govee-h5075-thermo.yaml` to the rest of the family | [Theengs decoder H5074](https://decoder.theengs.io/devices/H5074.html), [H5179](https://decoder.theengs.io/devices/H5179.html) | **$15 + $5 ship**; $17.81–$22 typical |
| **RuuviTag** | Vendor **publishes** its RAWv2 advertisement format — a reference-quality passive-advertisement spec | [Theengs RuuviTag RAWv2](https://decoder.theengs.io/devices/RuuviTag_RAWv2.html) | **$27.95** open box; $29.95 new; Pro $64 |
| **BLE TPMS sensors** | Fits the OBD-II / vehicle cluster; passive advertisement decode, no pairing | Theengs decoder TPMS support | **$19.98 for 4** (≈$5/sensor), new |
| **Qingping CGG1 / CGDK2** | Xiaomi-adjacent; sends both MiBeacon **and** an undocumented Qingping format — the Qingping format is the gap | [Theengs / ble_monitor by brand](https://home-is-where-you-hang-your-hack.github.io/ble_monitor/by_brand) | No eBay listings found 2026-07-30; source from AliExpress (~$10–15) |

The Qingping second format is the most interesting item in this tier: it is a
documented *absence* — decoders support MiBeacon from these sensors and
explicitly do not support the Qingping frames.

---

## Tier 3 — Battery, solar and energy (a transport family the repo lacks)

The repo has `enphase-envoy` and nothing else in this space, yet this is the
best-documented and cheapest-to-buy category surveyed.

### JK-BMS / JBD (Xiaoxiang) / Daly BMS — BLE + UART

| | |
|---|---|
| Public RE | [syssi/esphome-jk-bms](https://github.com/syssi/esphome-jk-bms), [syssi/esphome-jbd-bms](https://github.com/syssi/esphome-jbd-bms), [fl4p/batmon-ha](https://github.com/fl4p/batmon-ha), [patman15/BMS_BLE-HA](https://github.com/patman15/BMS_BLE-HA) |
| Cheap unit | **JK BMS from $6.35** (4S entry) new; **JBD BLE module $12.35–$13** new; **Daly BLE/UART module ~$21** new |

Cheapest new hardware on this entire page, three vendors share one problem
space, and the protocols are already mapped in maintained implementations.
Highest specs-per-dollar of anything surveyed. Each vendor deserves its own
spec; a shared "BMS BLE patterns" protocol page would mirror the existing
`obd2-common.md`.

### Victron Instant Readout — BLE advertisement

| | |
|---|---|
| Public RE | [keshavdv/victron-ble](https://github.com/keshavdv/victron-ble), [felixwatts/victron_ble](https://github.com/felixwatts/victron_ble), [Olen/VictronConnect](https://github.com/Olen/VictronConnect) |
| Cheap unit | **$38.88–$39.10** new Smart Battery Sense |

Victron publishes its extra-manufacturer-data layout, and the community
decoders fill the rest. Encrypted advertisements with a per-device key — a
pattern nothing in the repo currently documents.

### Renogy BT-1 / BT-2 — BLE-to-Modbus bridge

| | |
|---|---|
| Public RE | `cyrils/renogy-bt`; also covered by [BMS_BLE-HA](https://github.com/patman15/BMS_BLE-HA) |
| Cheap unit | **$19.95** new; $19.99 open box |

A BLE wrapper around Modbus registers — worth documenting as a transport
pattern, since the same trick shows up across solar and inverter gear.

---

## Tier 4 — Locks and actuators

| Device | Transport | Public RE | Cheap unit |
|---|---|---|---|
| **TTLock locks** | BLE | [Fusseldieb/ttlock-reverse-engineering](https://github.com/Fusseldieb/ttlock-reverse-engineering) — packet framing documented down to CRC8/MAXIM and the `0d 0a` tail; [ttlock-sdk-js](https://github.com/Fusseldieb/ttlock-reverse-engineering), [ha-ttlock-ble](https://github.com/roquerodrigo/ha-ttlock-ble) | Lock bodies from **$28.50** (cabinet/NFC); full door locks $34+; G2 gateway $18 |
| **Tuya BLE (Fingerbot etc.)** | BLE | `redphx/python-tuya-ble`, [ShonP40/Tuya-BLE](https://github.com/ShonP40/Tuya-BLE), [BillyNate/esphome-tuya-ble](https://github.com/BillyNate/esphome-tuya-ble) | **Fingerbot from $8.99** new |

TTLock is the strongest lock candidate: the framing is already published, the
lock name encodes the MAC in reverse byte order (a nice discovery signal for
the spec's `discovery` block), and it complements the existing `nuki-smart-lock`
and `switchbot-ble` specs.

Tuya BLE is a **platform**, not a device — one spec covering the DP
(datapoint) framing and session key exchange would unlock hundreds of cheap
devices at once. Best leverage-per-spec on the page. Note the honest catch:
the local key normally comes from a one-time cloud enrolment, and that
dependency belongs in the spec.

---

## Tier 5 — Mobility (extends the existing e-bike/scooter cluster)

| Device | Transport | Public RE | Cheap unit |
|---|---|---|---|
| **Xiaomi M365 / Ninebot** | BLE serial with register map | [CamiAlfa/M365-BLE-PROTOCOL](https://github.com/CamiAlfa/M365-BLE-PROTOCOL) (protocol notes + register spreadsheet), [m365py](https://github.com/AntonHakansson/m365py), [macbury/m365](https://github.com/macbury/m365) | **BLE dashboard board $18.78–$22.99** new — no need to buy a whole scooter to bench-test |
| **Votol EM series controllers** | CAN bus + BLE programming dongle | [bananu7/votol](https://github.com/bananu7/votol), [Ming2k8-Coder/VotolAIO](https://github.com/Ming2k8-Coder/VotolAIO), Endless Sphere protocol threads | **$25–$28.72** new (LanDe EM25–EM150S / EM150-2 class) |

The M365 dashboard-board trick is the useful find here: the BLE module is sold
separately for under $23, so the protocol can be exercised on a bench supply.
Votol pairs directly with the existing `fardriver-controller.yaml` and would
give the repo a second CAN-based controller alongside the OBD-II references.

---

## Tier 6 — Wi-Fi and BLE commodity gear

| Device | Transport | Public RE | Cheap unit |
|---|---|---|---|
| **Zengge / Magic Home / LEDnetWF** | Wi-Fi binary + BLE | [flux_led](https://github.com/lightinglibs/flux_led) (Wi-Fi, protocol RE'd from captures), [8none1/zengge_lednetwf](https://github.com/8none1/zengge_lednetwf) (BLE), [vikstrous/zengge-lightcontrol](https://github.com/vikstrous/zengge-lightcontrol), [HA led_ble](https://www.home-assistant.io/integrations/led_ble/) | **$1.99–$5** new controller |
| **TP-Link Kasa** | Wi-Fi LAN, TCP/9999 XOR-obfuscated JSON | `python-kasa` | **$6.74** used HS103; ~$1.50/plug in used multipacks |
| **Electronic shelf labels (Solum ZBS243)** | 802.15.4 + BLE | [OpenEPaperLink](https://github.com/OpenEPaperLink/OpenEPaperLink) — SoC reverse engineered by dmitry.gr, unencrypted Zigbee-like packets | **~$4.90/tag** (Solum Newton Lite 20-pack, $97.99); 2.2" single $62.50 |

Zengge is the highest-volume LED family the repo does *not* cover, and it is
the cheapest hardware surveyed — dual-stack (Wi-Fi *and* BLE) with firmware
revisions that shift the framing, which is exactly the kind of variation a
written spec is good at capturing. It sits right next to the existing
`elk-bledom-led-strip` and `coolledx-led-sign` specs.

On the ESL listings: the **Solum** lots are the OpenEPaperLink-compatible
ones. The much cheaper **Altierre** lots (50 tags for $80.75, ≈$1.62/tag) are
a *different*, unmapped proprietary system — cheap, but they are a research
target, not a quick spec.

---

## Tier 7 — Kitchen BLE (cheap, but the vendors are still alive)

Documentable and inexpensive; lower mission fit because nothing here is
abandoned. Extends `inkbird-bbq-thermometer`, `ibbq-meat-thermo`,
`thermopro-tempspike-bbq` and `chef-iq-sense`.

| Device | Public RE | Cheap unit | Vendor status |
|---|---|---|---|
| **Weber / iDevices iGrill 2, mini, v3** | [1mckenna/esp32_iGrill](https://github.com/1mckenna/esp32_iGrill), [fransakeson/ESP32_iGrill](https://github.com/fransakeson/ESP32_iGrill), [pilot1981/weber-igrill-integration-HA](https://github.com/pilot1981/weber-igrill-integration-HA) | **$17.99** used iGrill 2 | App still updated (v4.9.1, Jan 2025) — **not** abandoned |
| **MEATER / MEATER+** | [nathanfaber/meaterble](https://github.com/nathanfaber/meaterble) | **$19.99** open-box MEATER+ | Active |
| **Fellow Stagg EKG+ / EKG Pro** | [tlyakhov/fellow-stagg-ekg-plus](https://github.com/tlyakhov/fellow-stagg-ekg-plus), [calvinmclean/stagg-ekg-plus](https://github.com/calvinmclean/stagg-ekg-plus), `breiflabb/ekg-pro-ble-lib` | **$44** EKG Pro (parts-only); working units higher | Active |
| **Anova Precision Cooker (BT)** | [Aldaviva/SousVide](https://github.com/Aldaviva/SousVide), [pyanova](https://github.com/c3V6a2Vy/pyanova); Anova also publishes BLE docs for Nano/Mini | Not surveyed | Anova **cancelled** its Sept-2025 EOL and committed to indefinite support, but added an app subscription |

The Stagg is the most technically interesting: BLE serial-port service
`0x1820` / characteristic `0x2A80`, `0xEFDD` frame separator, and a magic
init sequence the kettle requires before it will talk — a clean worked example
for the BLE patterns page.

---

## Considered and deprioritised

Recording these so the same ground is not re-covered.

| Device | Why not now |
|---|---|
| **Sena / Cardo intercoms** | DFU images are signed and flash extraction needs hardware modification; no usable public protocol map. High effort, low odds. |
| **Chamberlain / LiftMaster Security+ 2.0** | [ratgdo](https://paulwieland.github.io/ratgdo/) already solves it properly with a wired board, and the rolling-code serial protocol is obfuscated. Document only if we can add something ratgdo has not. |
| **Logitech POP buttons** | Bricked in 2025 with two weeks' notice, but the hardware is a thin bridge-dependent button — little protocol surface to liberate. |
| **Broadlink RM4** | `python-broadlink` covers it and eBay results were all accessories; no clean price signal. Low priority. |
| **Wink / Lowe's Iris hubs** | Iris hubs stopped working in 2019 and no local protocol documentation surfaced in this survey. Would need ground-up research. |

---

## Consolidated buy list

Ordered by cost. Every price is the cheapest listing observed on 2026-07-30;
"parts" flags a listing sold as non-functional.

| Device | Cheapest observed | Condition | Tier |
|---|---|---|---|
| Zengge / Magic Home LED controller | $1.99 | New | 6 |
| JK-BMS (4S entry) | $6.35 | New | 3 |
| TP-Link Kasa HS103 | $6.74 | Used | 6 |
| Tuya Fingerbot | $8.99 | New | 4 |
| Logitech Harmony Hub | $9.99 | Used | 1 |
| JBD / Xiaoxiang BLE module | $12.35 | New | 3 |
| Insteon Hub 2245-222 | $14.88 | Used | 1 |
| Govee H5074-class thermo-hygrometer | $15.00 + ship | New | 2 |
| Weber iGrill 2 | $17.99 | Used | 7 |
| Xiaomi M365 BLE dashboard board | $18.78 | New | 5 |
| MEATER+ | $19.99 | Open box | 7 |
| Renogy BT-1 | $19.95 | New | 3 |
| BLE TPMS, set of 4 | $19.98 | New | 2 |
| Daly BMS BLE/UART module | ~$21 | New | 3 |
| Nest Learning Thermostat gen 2 | $22.95 | Used, tested | 1 |
| Votol EM controller | $25.00 | New | 5 |
| RuuviTag | $27.95 | Open box | 2 |
| TTLock cabinet/NFC lock | $28.50 | New | 4 |
| Bose SoundTouch 10 | $29.97 (parts) / ~$60 working | Mixed | 1 |
| Victron Smart Battery Sense | $38.88 | New | 3 |
| Spotify Car Thing | $40.00 | Used | 1 |
| Fellow Stagg EKG Pro | $44.00 | Parts | 7 |
| Solum ESL tags (20-pack) | $97.99 (~$4.90/tag) | New | 6 |
| Neato Botvac D5 | $99.99 | Used, complete | 1 |

**A Tier-1-plus-Tier-3 starter basket** — Harmony Hub, Insteon Hub, Car Thing,
JK-BMS, JBD module, Renogy BT-1, Victron Smart Battery Sense — comes to
roughly **$160** and covers five protocol families the repo has no spec for.

---

## Suggested order of work

1. **Bose SoundTouch** — published API, cheap hardware, fastest spec to land.
2. **Logitech Harmony Hub** — $10 hardware, two documented local APIs.
3. **BMS family (JK / JBD / Daly)** — cheapest hardware, best-documented
   protocols, opens the energy category.
4. **Tuya BLE platform spec** — one spec, hundreds of devices.
5. **Zengge / Magic Home** — largest uncovered LED family, $2 hardware.
6. **Spotify Car Thing** — highest-profile orphan; needs the most new writing.
7. **Neato local serial** — highest value per unit rescued, most hands-on work.

## Sources

Vendor status and shutdown timelines:

- [7 smart home brands that bricked their own products](https://www.howtogeek.com/smart-home-brands-that-bricked-products/)
- [Bose: SoundTouch cloud service ended](https://www.bose.com/soundtouch-end-of-life) ·
  [Hackster: Bose opens the API](https://www.hackster.io/news/bose-throws-end-of-life-soundtouch-owners-a-lifeline-plans-an-offline-app-update-and-opens-the-api-e6b4a59bd94c)
- [Neato: announcement, 6 Oct 2025](https://support.neatorobotics.com/support/solutions/articles/204000073686-announcement-6th-oct-2025) ·
  [Vorwerk explains the Neato cloud shutdown](https://www.wespeakiot.com/vorwerk-explains-neato-cloud-shutdown-why-your-smart-vacuum-just-got-dumb/)
- [TechCrunch: Spotify Car Thing refunds](https://techcrunch.com/2024/05/30/spotify-begins-offering-car-thing-refunds-as-it-faces-lawsuit-over-bricking-the-streaming-device)
- [Anova: ongoing product support](https://anovaculinary.com/blogs/blog/good-news-about-ongoing-product-support)
- [HA blog: Logitech Harmony removes local API](https://www.home-assistant.io/blog/2018/12/17/logitech-harmony-removes-local-api/)
- [Forrester: Insteon and the internet of bricks](https://www.forrester.com/blogs/insteon-and-the-internet-of-bricks)

Protocol references are linked inline in each candidate's row.
