# GAPS.md

Last updated: 2026-11-23

This file is a record of the ORIGINAL 27-target research wave and what
became of it. It is not a live list of everything the catalogue is missing
-- the catalogue has roughly five times as many specs as that wave produced,
and per-spec gaps live in each spec's own `evidence` and
`remaining_unknowns` blocks, where the person who found them was standing.

The dated sections further down are the exception: each records the leads a
later sweep turned up and did not finish, so the next person starts from the
checked facts instead of the search. The newest is
[November 23: devices going away](#november-23-devices-going-away-worth-investigating).

## Remaining Gaps: 1

| Target | Status |
|--------|--------|
| **ifreqtech-speaker-mic** | No companion APK exists — BT Classic hardware bridge (HFP + likely SPP). Requires HCI snoop on physical device. RE blocked until hardware in hand. |

## Resolved: 27 of 27 original targets

| Target | Resolution |
|--------|-----------|
| switchbot-ble | YAML written |
| govee-h5075, h5080, h6001 | 3 YAMLs written |
| gerbing-thermogauge | 10 UUIDs from IL disassembly, YAML written |
| elk-bledom | YAML written |
| ibbq-meat-thermo | YAML written |
| itag-ble-tracker | YAML written |
| xiaomi-miflora | YAML written |
| xiaomi-lywsd03mmc | YAML written |
| xiaomi-mi-scale | YAML written |
| niimbot-d110 | YAML written |
| cat-printer | YAML written |
| fichero-d11 | YAML written |
| shining-glasses, shining-mask | 2 YAMLs written |
| spider-farmer-ggs | YAML written |
| hotwired-heated-gear | Full frame format (AA/CC), YAML written |
| etekcity-smart-scale | YAML written |
| iledcolor-led-panel | YAML written |
| ble-pulse-oximeter | YAML written |
| divoom-pixoo | 666-line spec, 17 pixel encodings, YAML written |
| bmw-motorcycle-motoscan | → obd2-bluetooth-adapter.yaml (OBD-II/CAN) |
| motorcycle-ground-effect-lighting | → split: proglow ✅, seeblue ✅, opt7=elk-bledom ✅, xkglow ✅ |
| roku-local-remote | → roku-ecp.yaml (protocol fully documented) |
| led-space | → led-space.yaml (third app on the LOY SPACE / popled.cn platform; Wi-Fi AP/UDP 9090 path documented from com.yj.led static analysis) |

## Resolved: m6-fitness-band (was "Uncertain")

RESOLVED 2026-07-31: the Veryfit 2.0 (`com.veryfit.multi`) app-to-device match was
positively REFUTED by the M6's own stock firmware dump (rbaron/m6-reveng) — no 0AF0
UUID exists anywhere in the 512 kB flash. The M6 is an LT716-platform device speaking
the FitPro protocol (NUS + 0xCD-framed commands + Telink OTA, advertised name "M6",
companion app `xfkj.fitpro`). `m6-fitness-band.yaml` was re-targeted accordingly and
keeps the Veryfit analysis only as a clearly-labeled mis-attribution note. See
`research/m6-fitness-band/CONFIRMATION.md` §C.

## Mobile handlers' schema asks (image-upload wave)

Recorded from the `SPEC-GAP` comments the mobile app's handlers carry in
`rust/src/protocol/`. Each marks a place where a handler had to hard-code a
value, tell two cases apart by command name, or parse a payload out of prose,
because the spec or schema gave it no field to read. These are spec/schema
asks, not protocol unknowns: the bytes are established downstream and work;
what is missing is a machine-readable home for them so a generic consumer
gets what this app had to special-case. Twelve asks across five handlers:

All twelve were closed on 2026-09-17 by declaring the facts (the specs and
schema now carry them; the handlers can resolve by key):

| Handler | Schema ask | Now declared as |
|---------|-----------|-----------------|
| cdbwsoft_ecb | `link_flag` vocabulary is undeclared — the handler carries the values inline. | `data_transfer_start.parameters.link_flag` `allowed: [0, 1]` with labels (magic-display). |
| cdbwsoft_ecb | WRITE2 and WRITE3 are distinguishable only by command name; wants a declared `channel_tag` to switch on. | `role: bulk` on WRITE2, `role: stream` on WRITE3, `role: command` on WRITE1 — a new optional characteristic key. |
| cat_printer | Command set is in prose only — there is no `commands:` block to bind. | `commands:` on 0xAE01 (cat-printer) and on 0xAE01/0xAE03 (cat-printer-mxw01), CRC via `auto: crc8`. |
| cat_printer | Energy byte order is unstated. | `set_energy.parameters.energy.endianness: little` (NaitLee; rbaron's big-endian noted in remaining_unknowns). |
| cat_printer | Payload values are unstated. | A3 → 0x00, BE → 0x01, A9 → 0x00, A4 → 50, precomputed in each command's `value`. |
| fichero_d11 | Command set is in prose, not a `commands:` block. | `commands:` on 0xFF02, aliased onto 0x2AF1. |
| fichero_d11 | Density vocabulary is not a field. | `features[image_upload].print_density` and `set_density.parameters.density` (`allowed`/`labels`). |
| fichero_d11 | Paper-type vocabulary is not a field. | `features[image_upload].paper_type` and `set_paper_type.parameters.paper_type`. |
| idotmatrix | The 4096-byte chunk payload is described in prose only. | `framing.max_chunk_size: 4096` on 0xFA02, and `upload_image_chunk`/`upload_gif_chunk` templates. |
| idotmatrix | Static-image header values (time/delay + speed) are unstated. | `display_seconds` and `material_type` parameters with defaults (0/12 image, 5/13 GIF). |
| ledbadge_bitmap | Slot-mode enumeration is not in the YAML. | `write_badge_data.parameters.mode` `allowed: [0..8]` with labels. |
| ledbadge_bitmap | The 8192-byte flash ceiling is not declared. | `features[image_upload].max_payload_bytes: 8192`. |

Still open from the same wave: a payload-length `auto` role (the cat
printer's variable-length 0xBF RLE row), nibble-packed parameters (the
badge's speed nibble shares a byte with `mode`), and a raw-byte-stream
transport arm for top-level `commands` (Brother's raster opcodes stay
`payload_hex` prose).

## November 17 LAN consumer handlers

The protocol documents are no longer missing, but four generic-consumer
integration gaps remain explicit. `tplink-tapo-klap` needs TDP plus cookie-bound
KLAP/RSA session handling, `meross-wifi-appliances` needs signed/Encrypt.Suite
handling, and `sonoff-ewelink-lan` needs stock TXT/AES/per-UIID dispatch.
`somfy-tahoma-developer-mode` needs bearer auth-scheme, vendor-CA, advanced
network-action, DELETE and named-cover-state handlers. All four are
`identify_only`, not fake plaintext-HTTP integrations. Per-protocol open
questions and hardware verification gaps remain in the specs rather than being
flattened into this file.

## November 23: devices going away, worth investigating

Recorded 2026-11-23 from the sweep that followed Google's Fitbit Aria cutoff
(no pairing or re-pairing of Aria and Aria 2; see the note on the date below).
Three searches
ran in parallel (smart scales; news of shutdowns between September 2026 and
mid-2027; Wi-Fi devices that call home and can be served from the LAN), and a
second, skeptical pass then re-loaded a primary source for every row. Where
that pass could not load a source the row says **unverified**. Nothing here
was run on hardware by this project. The dated log is
[docs/research/weekly-sweeps.md](docs/research/weekly-sweeps.md); this
section is the work list.

Three limits on the search itself, so nobody mistakes a gap for a negative:
the Internet Archive and Reddit were unreachable from the research sandbox,
web search was rate-limited part-way through the news sweep, and GitHub issue
threads were read through a summarising tool rather than verbatim.

**Orphaned is not the bar.** A device whose vendor is still running is often
the better target: the app still pairs, the cloud still answers, and a capture
taken now is one nobody can take after the switch-off. The Aria 2 is the
lesson: nothing about its wire protocol was ever written down, and by the
time anyone looked the vendor said pairing had already ended, so the pairing
exchange may never be observable again. So "the vendor is still active" is
never a reason to park a row here; it is the reason for
[Capture while the service still runs](#capture-while-the-service-still-runs).

**The cutoff date moved while this was being written.** Google's help page
for the scales read "Starting November 28, 2026, with the release of app
version 5.12" when fetched at 05:11 UTC on 2026-11-23, and "Starting
November 9, 2026" when fetched again at 23:40 UTC the same day; nothing else
in the sentence changed. Read it as: pairing and re-pairing of the Aria and
Aria 2 have already ended, and every "before the 28th" plan is void. Paired
scales "will continue to sync" by the same page, which names no end date.

### Fitbit Aria family: what is still open

The original Aria (FB201) and the Aria Air (FB203) have specs and the Aria 2
(FB202) has a research note; each carries its own unknowns. These are the
ones worth an owner's hour, cheapest first:

| Device | Open question | Experiment that settles it |
|--------|---------------|----------------------------|
| Aria (FB201) | Does a freshly set-up scale complete register, validate and its first empty upload against a purely local server on every firmware? Reported on 35 and 37, setup request accepted on 39, one unexplained failure on 38. Twenty public 2016 captures (firmware 37) show that sequence against the vendor; no log of it against a local server has been published. | Run the local setup with a logging server; keep the full request and reply bytes for all three calls, scrubbed. Setup mode is a one-way door (see below): only on a scale that is already unpaired or must change network. |
| Aria (FB201) | Does a battery re-insert on firmware 38 and 39 keep the stored Wi-Fi key, and does reaching `SETUP ACTIVE` erase the stored network at once? One log cannot tell a wiped key from a weak signal. This decides how dangerous a battery change is. | On a spare or already-unpaired scale: pull a battery, do not press, and see whether it rejoins. |
| Aria (FB201) | What does the scale do when `/scale/validate` answers 404 or `F`? Two 2026 servers have no such route. | Answer each way once and note the display and the next request. |
| Aria (FB201) | Zero users, or three to eight users, in a reply from a local server: accepted, and what does the display show? Evidence stops at two. | Reply with 0, 3 and 8 user records in turn. |
| Aria (FB201) | Where the 16-byte `auth_code` comes from, and whether it changes when setup is re-run with a new token. | Compare the upload header before and after a second setup. |
| Aria (FB201) | Record order in a multi-record upload (two write-ups disagree), impedance unit, and whether guest readings carry impedance. | Weigh several times offline, then log one upload. |
| Aria (FB201) | How long will Google's scale-facing endpoints keep answering for already-paired scales? Google names no end date. | Passive: watch whether a paired scale still shows the check mark. |
| Aria 2 (FB202) | Everything on the wire: advertised name and services, upload hostname, TLS and certificate handling. Nothing is public. | Read-only BLE scan; router DNS log and flow capture of one weigh-in. None of it touches the pairing. |
| Aria 2 (FB202) | Does the in-app Wi-Fi change still work on app 5.12 and later, and does it need anything from Google's servers? | Android HCI snoop log while changing the network on a still-paired scale. Do it now: the control may already be gone. |
| Aria 2 (FB202) | Is the pairing block enforced in the app, on the server, or both? | Try pairing a scale that is already unpaired with an app build older than 5.12. A failed attempt costs nothing; never unpair a working scale to test it. |
| Aria 2 (FB202) | Does it reuse Fitbit's tracker-era Bluetooth service? The academic work on trackers never mentions a scale. | Read-only BLE scan for the tracker service `adabfb00-6e7d-4601-bda2-bffaa68956ba`. |
| Aria 2 (FB202) | Does a paired scale rejoin a new router that reuses the old network name and passphrase? Expected, untested. | Clone the network on a spare access point. |
| Aria Air (FB203) | Can a client write its own key after a reset, with no vendor app? One unreplicated report. | Reset a scale that is not needed day to day, write a key, weigh. |
| Aria Air (FB203) | Scaling in kg mode: 0.01 or 0.005 per unit? The one public integration and the one report disagree. | Weigh a known mass in lb, st and kg and compare plaintext bytes. |

### Fitbit Aria family: every other local route, checked

A second research pass asked what else an owner can do: connect directly,
use a debug port, side-load firmware, or fall back to hardware. Each route
was then re-checked by a skeptic against its primary source, with the brick
risk re-rated. "Nobody" means no public report of anyone doing it on this
model. Routes marked **do not** are recorded so nobody rediscovers them the
hard way.

**Original Aria (FB201).** It has no Bluetooth at all, and on the home
network it is a client only: awake for seconds, with no listening port ever
observed.

| Route | Evidence | Needs | Risk and what it costs |
|-------|----------|-------|------------------------|
| DNS override plus a LAN server | Demonstrated on firmware 35, 37 and 39 by five or more independent deployments. | A resolver you control for the one name and a small always-on server. | None. **Needs no setup mode**, so it is the only route that leaves the stored network and token alone and stays reversible. The reply sets the display unit and user table. Hand the special resolver to the scale only (a per-device DHCP option) rather than to the whole house. |
| The same, relaying to the vendor | Demonstrated (a 2024 write-up and a 2024 container). | As above, plus the vendor's current address. | None. Logs locally while a still-paired scale keeps syncing. Other household members' guest readings ride in the same request. |
| Destination NAT of port 80, or a dedicated access point or travel router that does its own DNS | Inferred from the plain-HTTP design; pieces demonstrated separately, the bundle by nobody. | A gateway you control. A dedicated access point can also keep the 802.11b rates new routers drop. | None. Covers the "I cannot change DNS on this network" case, which is nearly the only case firmware would otherwise be wanted for. |
| New router with the old network name and passphrase | Inferred (a firmware 39 log shows a scan by stored name); nobody has published doing it. | Same name, security mode and passphrase; 802.11b rates on. | None, and nothing is lost if it fails. Try this before setup mode. |
| An ESP32 that is access point, DNS and server in one | Author-reported on firmware 37, one user, no session log. | Build it yourself; then the setup request below. | None to the scale, but it sets pounds unless the source is edited, recognises everyone as one user, and needs setup mode. |
| Direct connection in setup mode: one HTTP request to the scale's own open access point | Demonstrated on 35 and 37; request accepted on 39; one unexplained failure on 38. Nobody reports doing it from a phone. | A laptop joined to the `Aria XXXXXX` network. | **One-way door.** Reaching setup mode on a configured scale takes a deliberate press that discards the stored network, and the request replaces the token. The vendor link cannot be recreated. Have the DNS override and server answering first. The passphrase crosses an open network in clear. |
| Serial console on the internal UART1 header | Demonstrated on firmware 39 by two people: 115200 8N1; prints weight, impedance, body fat and the user table at each weigh-in. | Case open; wires soldered to unpopulated holes; the logic level is published nowhere, so measure first. | Diagnostics only: **no command sets Wi-Fi or the server**, so it cannot redirect the scale. The partial help list also names writes to identity, factory and calibration data that nobody has documented running. The glass is a body-contact electrode on a battery-isolated product: anything wired to the board must be battery powered or isolated while someone stands on it. |
| Listen-only logger on the console's transmit line | Nobody has built it; the log content is shown on firmware 39 only. | Case open, two wires, a parser for one firmware's format. | None if it only listens. Fully local readings even if every network route fails. |
| Firmware update triggered by the server's reply | The channel is real: plain HTTP, fetched from whatever answers for the name. A header-only probe on 2026-11-23 found the vendor's image endpoint still answering for versions 35, 38 and 39 (33 gone). | Nothing an owner should supply. | **Do not.** Nobody has ever sent the update flag to a real scale from a local server. A bad image on a sealed scale has no demonstrated way back. This is why a local server must always answer "no update". |
| Side-loading a modified image over that channel | Nobody. A 2015 security team tried, reported the update process well protected, and published no follow-up. No public parser, no located integrity field, no located hostname string. | Reverse engineering that has not been done. | **Not available.** And mostly unnecessary: the redirect routes above already do what a patched image would. |
| The Wi-Fi module's boot-ROM download mode, or JTAG | Chip capability from the module's datasheet; the board carries a labelled switch and pads. Never used on an Aria. | Case open; a valid image, which does not exist in a form that flow can program; no read-back is documented. | **Do not** on a scale you want: the documented flow begins with a full erase and there is no public image to restore. |
| Replace the electronics with a load-cell amplifier | Generic technique; nobody on an Aria. Wire colours unpublished. | Case open, soldering, calibration weights. | Last resort for a dead board. Loses the display, user recognition and body fat. |
| Nothing: use it as a plain scale | Vendor-documented. | Nothing. | It weighs and shows `NO SYNC`. No history. |

Two facts the same pass added to the protocol record: the scale's DHCP host
name is `GainSpan` plus six hex digits (one unit, firmware 37, 2016
captures), a usable hint for finding it on a LAN; and in those captures the
vendor's own reply ended in tail words 0, 0, 0, where every working local
server sends 0, 3, 0. Both forms have been accepted by scales; which the
firmware actually checks is open.

**Aria 2 (FB202).** Bluetooth is its provisioning channel only: by the
vendor's own description weigh-ins travel over Wi-Fi to the cloud, so a
phone connecting to a paired scale should not expect to read a weight. It
has no setup access point and no web page.

| Route | Evidence | Needs | Risk and what it costs |
|-------|----------|-------|------------------------|
| New router with the old network name and passphrase | Ordinary Wi-Fi behaviour; untested on this model. | A matching network. | None. The first thing to try at a router change. |
| Capture the in-app Wi-Fi change | Method inferred; the control is vendor-documented, and whether it still works is unknown. | Android HCI snoop log, router DNS and flow log. | None; read-only. The single dataset that says whether anyone can ever re-provision this scale without Google. |
| Re-provision over Bluetooth with your own client | Nobody; no public GATT table. | The unknown exchange, and possibly a secret only the vendor's servers issue. | Unknown, and a botched write can no longer be repaired by re-pairing. Research direction only. |
| DNS override plus a LAN server | Works on the original Aria; explicitly untested here, and the two FB201 projects say this model is unsupported. | Hostname, TLS behaviour and the whole upload protocol: all unknown. | None for a passive look. Blocked on the protocol, not on risk. |
| Debug pads | The FCC internal photograph shows an ST ARM microcontroller, a separate Macronix flash chip and an unlabelled test-pad cluster. The radio chip is unidentified. Nobody has connected to anything. | Case open, fine wiring, a debug probe. | Unknown. Production microcontrollers of this family usually have read-out protection; **do not force it off**: that mass-erases, and no image exists to restore. A clip-on read of the flash chip is non-destructive; what it holds is unknown. |
| Firmware over Bluetooth, as academics did on Fitbit trackers | Shown only on trackers, only in their unencrypted mode. A 2017 device would need a per-device key no owner can obtain. | That key, the image format, a tool chain. None public. | **Not available.** |
| Firmware over Wi-Fi | Nobody; no update address for this model is documented anywhere. | Nothing exists to try. | **Not available.** |
| Replace or piggyback the load cells | Four conventional cells are visible in the FCC photograph; the retrofit is generic and undemonstrated here. | Case open, soldering, calibration. | Cutting in is one-way and ends the Fitbit function. Tapping the cells without cutting keeps the board alive but is bench work nobody has shown. |

**Aria Air (FB203).** Bluetooth only: there is no server to redirect. The
safest move for an owner whose scale works is to leave the pairing alone.

| Route | Evidence | Needs | Risk and what it costs |
|-------|----------|-------|------------------------|
| Capture the key the vendor app writes at setup | Demonstrated by one party (hardware H01, firmware A16, October 2026), with a published parser. Not reproduced. | Android HCI snoop log of an in-app setup. | The published procedure **starts by removing the scale from the account and resetting it**, then depends on the vendor app completing a fresh setup, which has a public history of failing. Failure state: unpaired, with an app that will not re-pair. |
| Write your own key after a reset | One report (October 2026, one unit, firmware not stated), relayed from an AI assistant's analysis by its poster. Not reproduced. | A reset, then one GATT write. | Ends the vendor pairing. Whether a second write is accepted once a key is set is untested, which is both a possible shortcut and a possible hazard. |
| Read without the key | Identification demonstrated by two parties; a step-on flag by one. | Any BLE scanner. | None. Never yields the weight. |
| Read the display with a phone camera | Demonstrated by one party: an Apache-2.0 Android app whose author tested it only on this scale; kilograms only. | A phone, and a manual step per weigh-in. | None. No pairing involved. |
| Firmware over the air | The scale exposes an update service under Nordic's legacy DFU identifier on a Telink chip; nothing about it is public. The stock Telink update service that the custom-firmware tools need is absent from the one published listing. | Nothing an owner should supply. | **Do not write to that service.** Recovery: none known. |
| The chip's single-wire debug port | Pads labelled for it are visible in the FCC photograph, on the face of the module that is soldered against the main board. No public programmer lists this chip as tested. | Lifting the module or identifying an edge pin nobody has mapped. | Unknown. Not a route today. |
| The link between the weighing controller and the radio module | Inferred from the two-chip layout; nobody has probed it. | Case open (a one-piece glass top, no published way in). | If the weight crosses that link before encryption, a listen-only tap would read it without the key. Open question, not a route. |
| Reuse the four load cells | Generic technique; nobody on this model. | Case open, soldering, calibration. Unsolder rather than cut, and record the wiring. | Ends the Fitbit function; starts uncalibrated. |

### Ready for a spec

Each of these has a vendor that is gone or leaving and public protocol work
that a skeptic judged complete enough to implement from.

| Device | What happened | Local route and evidence | Notes for the author |
|--------|---------------|--------------------------|----------------------|
| **QardioBase / QardioBase 2** (B100, B200) | Qardio's cloud has been off since 2025-04-29 and both app listings are gone (dates as sourced in `qardio-arm.yaml`; not re-loaded on 2026-11-23). The scale still weighs. | Phone-direct BLE: a vendor service with state, command, result and user-profile characteristics; profiles and results are JSON. [openScale's handler](https://github.com/oliexdev/openScale/blob/master/android_app/app/src/main/java/com/health/openscale/core/bluetooth/scales/QardioBaseHandler.kt) (GPL-3.0), observed on a QardioBase 2. | Single source. It was derived from the vendor app and quotes that app's obfuscated identifiers and one person's readings: copy neither. B100 evidence is thinner; bonding requirement open. `research-notes/qardio-arm.md` still says no community work exists for the scale and needs correcting. |
| **Runtastic Libra** | adidas withdrew the app and disabled login and sync, announced 2020-09-21 ([The Register](https://www.theregister.com/2020/09/22/adidas_libra_scale/)). | Listed by openScale as the Beurer BF700/800 dialect already in `openscale-body-scales.yaml` ([protocol page](https://github.com/oliexdev/openScale/wiki/Beurer-Sanitas)). | An extension of the existing spec, not a new file: the Libra's names, the `0xf7` start byte, the init, set-time and disconnect frames, and the withdrawn-app status. No Libra-specific hardware report was found; the one cited observation is a Beurer BF800. |
| **Withings Body+** (WBS05) | Accounts created on or after 2026-10-13 need a Withings+ subscription for automatic sync to Apple Health, Health Connect and third parties ([MacRumors, 2026-10-15](https://macrumors.com/2026/10/15/withings-plus-apple-health-syncing)). | BLE read of all stored measurements after a challenge-response with the account's association secret. [openwithings](https://github.com/totruok/openwithings) (MIT) documents framing, commands and record layouts from hardware. | One unit, one firmware (1651). Not cloud-free: the secret comes from Withings' legacy API, and after a battery change body composition needs a user list from Withings. The scale must be in Bluetooth mode. The reference tool deletes records after reading; a spec here stays read-only, like its two Withings siblings. The sweep log's "code unpublished" entry is now stale. |
| **Eufy smart scales** (P2, P2 Pro, C1, P1, A1, C20, P3) | eufy's own post of 2026-03-27 says the whole scale line was discontinued on its US store in March 2026 ([eufy](https://us.eufy.com/blogs/home/eufy-smart-scale-discontinued)). The app still syncs; this is a retail exit, not a shutdown. | Phone-direct BLE in three shapes: a handshake then 16-byte frames (P2 family), 11-byte frames (C1, P1, A1), weight in advertisements (C20, P3). [eufylife-ble-client](https://github.com/bdr99/eufylife-ble-client) (MIT, stated only in its packaging metadata) and a Home Assistant core integration. | Best-evidenced row here, lowest urgency. The P2 key derives from the Bluetooth address, which Apple platforms hide; P2 weight is also in advertisements, so the handshake is not needed for weight. Sources disagree on which bytes carry P2 impedance. Wi-Fi side has no public work. |
| **Flipr AnalysR 3 / Start Max** pool analysers | Maker liquidated by judgment of 2025-09-25 (published 2025-10-12); owners report the cloud and app failing from 2025-10-21; Home Assistant removed its cloud integration in [2026.11](https://www.home-assistant.io/blog/2026/11/04/release-202611/). | BLE read of a 13-byte frame (temperature, pH, ORP, battery) with a write that triggers an analysis: `Adrien40/ha-flipr-local` (GPL-3.0). The first search pass missed this and called the local route unknown. | Single implementation, layout in code only, and its author says frames differ between hardware versions: fall back to a research note if that cannot be pinned down. Sigfox-only probes, the Hub and ControlR are not covered. Raw sensor millivolts need the calibration story before any entity claims a pH. |
| **Bose SoundTouch, the cloud half** | Bose ended cloud support on 2026-05-06 ([Bose](https://www.bose.com/soundtouch-end-of-life)): presets, in-app services and stereo pairing on the SoundTouch 10 stopped. `bose-soundtouch.yaml` covers only the speaker's own local API. | A LAN server replaces the endpoints the speaker calls; the speaker is re-pointed at a plain-HTTP address over its service console on TCP 17000. Servers: [ueberboese-api](https://github.com/julius-d/ueberboese-api) (MIT, with an OpenAPI description), [soundcork](https://github.com/deborahgu/soundcork) (MIT), and at least two more. | Six corrections from the skeptic pass: a DNS-only override fails (the speaker rejects the TLS handshake); the order of the console commands matters and one project's quick start has it backwards; a factory-reset speaker also needs a local pairing call; the console is firmware-gated (reported on SoundTouch 10/20/300 and Wave III/IV, not on the SA-5, unverified on the 30 and 520); some firmware may refuse non-Bose addresses; the root-shell alternative is an unauthenticated root shell and needs a security advisory. Rebuild every example from invented ids. |
| **AcuRite Internet Bridge / smartHUB** | End of service 2019-02-28 ([AcuRite, 2018-02-24](https://www.acurite.com/blogs/default-blog/extending-end-of-service-and-support-for-acurite-smarthub)). | DNS override of two upload hostnames to a plain-HTTP listener; the reply format differs by bridge firmware (126 and 224), corroborated by [weewx-interceptor](https://github.com/matthewwall/weewx-interceptor) (GPL-3.0) and [Acuparse](https://github.com/acuparse/acuparse) (AGPL-3.0). | `research-notes/acurite-access-atlas.*` rates this `rejected_dud` because DNS interception was once judged out of scope. That reason is stale (JuiceBox, and now the Aria, are specced on exactly this route) and the note has factual errors: rewrite and re-rate it. The reply's firmware-version field must match the bridge or it tries to fetch firmware. |

### A research note first

Real leads where something blocks a spec today. The blocker is the point of
each row.

| Device | What happened | What is known | What blocks a spec |
|--------|---------------|---------------|--------------------|
| **iHealth HS5 / HS5S Wi-Fi scales, AM3 / AM3S, BP3** | iHealth's help centre says the Legacy app is being phased out and these products "may no longer be able to pair or function" (article dated 2026-08-17; no end date). The Android listing was last updated 2023-08-10; the iOS listing appears delisted. | Bluetooth for Wi-Fi setup, then Wi-Fi; the vendor SDK's documentation hints that the same-network session is UDP. | No public wire format at all. Closest twin to the Aria and the most time-sensitive row here: captures need a unit that is still provisioned. Extend `research-notes/ihealth-classic-bt.*`. |
| **iHealth HS3 and HS2S** | Same frozen app. | openScale has a receive-only HS3 parser (Bluetooth Classic) and a detailed HS2S handler (GPL-3.0). | The HS3 parser carries no transport, pairing or pound-mode detail; the HS2S handler is marked untested on hardware by its own authors, embeds fixed per-model keys (do not copy) and deletes records after reading. The existing note says no community work exists; that is now wrong for the HS3. |
| **Withings Wireless Scale (WS-30), Smart Body Analyzer (WS-50), Smart Kid Scale** | Listed as end-of-support in Withings' [policy dated 2026-04-23](https://media.withings.com/web/legal/legal-pdf/end-of-support-policy/eu-en-end-of-support-policy-20260423.pdf); they still work with the app and cloud, with no guarantee. The policy promises no notice before a cloud shutdown. | [YourOwnWeigh](https://github.com/tomanthony/YourOwnWeigh) (MIT) documents the four upload endpoints and the session hash, and serves them itself. | It needs patched firmware flashed over Bluetooth, which the existing Withings specs deliberately exclude. A DNS override alone does not work on any covered model (stock firmware speaks TLS); whether stock WS-30/WS-50 validate the certificate is unpublished and is the one experiment that matters. |
| **Koogeek S1** | Vendor status **unverified**: no dated notice found, the vendor site does not connect, and "the cloud no longer exists" is an undated developer remark. | BLE frames documented in the [ble-scale-sync adapter](https://github.com/KristianP26/ble-scale-sync/blob/main/src/scales/koogeek-s1.ts) (GPL-3.0): init acknowledgement, then weight and impedance. | One hardware reporter, and the adapter itself says connecting is unreliable on BlueZ, ESP32 and macOS. Find one dated source for the vendor's state first. |
| **vTuner-dependent AV receivers** (Yamaha, Denon, Marantz, Onkyo, Pioneer and others) | A paywall, not a shutdown: vTuner charges a yearly fee on its brand portals, and Yamaha lists 61 models that cannot move to its replacement directory. | DNS override of the brand hostnames to a plain-HTTP server that answers a token handshake and returns XML station lists. Two independent servers: [YCast](https://github.com/milaq/YCast) (GPL-3.0) and YTuner (MIT, 87 user-tested models). | The protocol exists only as code; nobody has written it down. Strongest candidate to promote next, because writing that prose is the whole job. Receivers append their MAC to requests: redact. |
| **Oregon Scientific LW301 / LW302** | Upload server gone since 2018, on community sources only. | DNS override of one hostname; key/value packets per sensor type, in weewx-interceptor. | About half the payload fields are unknown and what the hub needs in the reply is not stated. Its existing note carries the same stale `rejected_dud` rating as AcuRite's. |
| **Koubachi Wi-Fi plant sensor** | Service ended 2019-10-23. | The vendor published the protocol on its way out ([api-docs](https://github.com/koubachi-sensor/api-docs), no licence file) and a community server exists ([koubachi-pyserver](https://github.com/koalatux/koubachi-pyserver), MIT). Plain HTTP; the server address is an owner setting on the sensor's own setup page. | Every payload is encrypted under a per-device factory key whose only documented source was a vendor mailbox, on a domain whose web hosts no longer answer. No key-extraction method is known. Without the key there is no route. |
| **Hello Sense** | Shutdown announced 2017-06-12 (secondary source). | Firmware and server source are public (no licence: facts only). | A documented negative: the device checks the server against a certificate authority stored in its own flash and signs uploads with a per-device key, so a DNS override cannot work. One lead: the firmware source appears to contain a debug-serial routine that prints the device key (read from code, not demonstrated). |
| **Little Printer and BERG Cloud Bridge** | Closure announced 2014-09-09. A community server instance is live. | WebSocket JSON between Bridge and server, in the two `sirius` repositories. | Neither repository has a licence, and re-pointing a stock Bridge now means opening it and using a serial console. The repositories' READMEs contain what look like live credentials: do not copy them. |
| **Karotz** | Vendor servers stopped 2015-02-18 (secondary source). A community service was active the week of this sweep. | A replacement OS with web, Telnet and FTP enabled by default; a community CGI API on the rabbit. | No reference for the API's calls was found, and the replacement OS is a modified vendor image. `nabaztag-tag-serverless.yaml` explicitly excludes Karotz. |
| **Airzone zoning and Aidoo controllers** | Remote control went behind a EUR 48 per year plan in October 2026 (price and view-only remote confirmed on Airzone's own page; the exact day and country list rest on secondary sources). Local control stays free. | Airzone publishes its LAN API (ports 3000 and 3443, with an OpenAPI file): link, do not spec. Separately, [Open Airzone Gateway](https://raw.githubusercontent.com/letherman255/Open-Airzone-Gateway/main/docs/protocol.md) (MIT) documents the RS-485 bus of AZ6 centrals. | The bus map rests on one installation, days old, and its author latched a refrigerant-leak alarm while testing: any write needs `advanced` and a safety advisory. The Aidoo Wi-Fi has no local route at all. |
| **Hunter HunterSMART ceiling fans** | From 2027-01-01 Hunter ends the cloud link to Google Home and Alexa (Hunter's post of 2026-11-05); its own app and the remote keep working. | The local routes are HomeKit and, after Hunter's update, Matter. Both are public protocols. | Nothing proprietary to document: a short advisory linking the public protocols. The fans' own Wi-Fi platform was not researched. |
| **Bluetooth SIG Weight Scale profile, generic** | No vendor is leaving. | The public Weight Scale and Body Composition services, read by openScale for two named scales (A&D UC-352BLE, Samsung GP-BELAD001BP0). | Worth one generic reference spec. Polar Balance compatibility is a 2016 statement of intent with no demonstrated third-party read; do not list it. |
| **Omron body-composition monitors** | Vendor active; the claimed app migration has no loadable source. | openScale reads stored records after a key unlock (GPL-3.0). | Probably a per-model record layout for `omron-connect.yaml` rather than a new protocol; the record-layout code was not located. |

### Capture while the service still runs

Devices whose vendor service is up today. For each, the thing worth having is
a capture or an export that stops being obtainable when the service does.
Ordered by how short the window looks. Scrub every capture before it leaves
the owner's machine: MAC, serial, tokens, network name, account ids.

| Device | Window | What to get now | What it settles |
|--------|--------|-----------------|-----------------|
| **Fitbit Aria 2** (FB202) | Possibly already shut: Google now dates the end of pairing to 2026-11-09, and whether the in-app Wi-Fi change survives is unknown. | An Android Bluetooth HCI snoop log of a Wi-Fi network change on a still-paired scale; a read-only BLE scan; the router's DNS log and a flow capture of one weigh-in. Do not unpair or reset to get any of it. | Whether third-party Wi-Fi provisioning is possible at all, the upload hostname, and whether TLS interception is even worth trying. Turns the research note into an identify-only spec. |
| **Fitbit Aria** (FB201), still paired | Unknown: Google promises no end date for the scale-facing endpoints. | A passive LAN capture of the scale talking to the real server. It is plain HTTP, so a mirror port or the router's capture is enough; nothing needs redirecting. Keep the full reply bytes. | Things no local server can answer: the real server's tail words today (2016 captures show 0, 0, 0; one write-up says the middle one is 3), what three to eight user records look like, name padding, the daily check-in cadence, and the update branch if one is ever offered. |
| **Fitbit Aria Air** (FB203) | Open-ended, but tied to one vendor app. | An HCI snoop log of a second phone or a reinstall connecting to an already-paired scale, plus one weigh-in. If you ever set the scale up afresh for any other reason, log that too. | Whether the app ever re-sends the 16-byte key, or fetches it from the account, which decides whether an owner can obtain their key without a reset. Do not reset a working scale just to capture it. |
| **iHealth HS5 / HS5S, AM3 / AM3S, BP3** | Short and undated: the Legacy app "is being phased out". | With the legacy app still installed: an HCI snoop log of Wi-Fi setup, a capture of a same-network weigh-in (the SDK documentation hints at UDP) and of an offline upload. | The whole wire format; today nothing is public. |
| **Withings Wireless Scale (WS-30), Smart Body Analyzer (WS-50), Smart Kid Scale, and the other end-of-support products** | Withings promises no notice before a cloud shutdown. | Whether stock firmware validates the server certificate (a self-signed interception test), and one full upload exchange against the live service. | Whether a DNS override can ever work without flashing patched firmware. This is the one unpublished fact that decides the route. |
| **Withings Body+** (WBS05) and siblings | As long as Withings' legacy API keeps issuing the association secret. | Export the association secret and the user list for your own scale now. | Without the secret the documented BLE read cannot authenticate; with it the scale is readable locally for good. |
| **Garmin Index** (original) | Unknown: last firmware 2021-11-29, changing the upload server "for continued support". | DNS log, TLS behaviour and a flow capture of a weigh-in; an ANT+ and BLE scan during setup. | Everything: there is no public work on any of its three radios. |
| **Eufy P2 / P2 Pro / P3, Wi-Fi side** | Open-ended; the line is off eufy's US store. | DNS log and TLS behaviour of the Wi-Fi upload; a BLE capture that pins down which bytes carry impedance. | The Wi-Fi route has no public work; the impedance bytes are disputed between sources. |
| **vTuner-dependent receivers** | Paywalled, with no end date announced. | A plain-HTTP capture of a receiver's directory session against the real service, one per brand. | A prose protocol to check the two community servers against, instead of deriving it from their code alone. |
| **La Crosse GW1000U** | Vendor service appears alive. | The registration exchange with the vendor (both community write-ups say to register there first), captured. | The key and ping-interval reply that a stand-in server would have to produce. |
| **Hunter HunterSMART fans** | The Google Home and Alexa link ends 2027-01-01. | A LAN scan and DNS log of a fan before and after Hunter's Matter update. | Whether the fans have any LAN surface of their own besides HomeKit and Matter; nothing is known. |
| **Airzone Cloud Webserver** | Open-ended; the paywall is already in force. | A port scan of the webserver for the vendor's documented LAN API. | A disputed fact: Airzone says "Webserver" units have the local API, one owner found the port closed on a Cloud Webserver. |
| **Growatt ShineWiFi / ShineLAN** | Cloud live. | Nothing urgent: the datalogger's server address is an owner setting, and `grott` already documents the records. | Listed so it is not mistaken for a dead end. The public code has no licence (facts only), and register writes reach a grid-tied inverter: read-only until someone owns the safety story. |
| **Toniebox (first generation)** | Vendor active. | Nothing urgent: TeddyCloud's own project documents the endpoints. | The route needs the box opened and its flash rewritten (the box checks the server against a certificate authority in flash), so there is no capture-only shortcut. |

### Parked, with the reason

Parked means there is no known route **and** nothing left to capture, or
nothing proprietary to document. A live vendor is not a parking reason; see
the table above.

- **Under Armour / HTC UA Scale**: dead since 2020-03-31, no public protocol work, and no service left to capture against. An owner's BLE scan is the only first step.
- **Roost Wi-Fi leak detector**: switched off in mid-2026 on about thirty days' notice; device-initiated TLS to a dead host, certificate handling unknown, no public work.
- **Wahoo Balance**: neither the vendor status page nor the only protocol source would load, so there is nothing checked to write down yet.
- **Testo Saveris 2**: one secondary source for the cloud migration; commercial gear, no local route known.
- **Brilliant panels**: a paywall (from 2026-12-03) on a cloud-to-cloud link; the affected devices keep their own routes, and there is no device protocol in it to capture.
- **reMarkable, Mycroft, Chumby**: an open stack or a route its own project already documents in full, or a replacement firmware image rather than a protocol.

### Things this sweep found wrong in the tree

- `research-notes/qardio-arm.md` says openScale has no QardioBase support. It does now.
- `research-notes/ihealth-classic-bt.md` says no community work exists for the HS3 weight stream. openScale has a parser.
- `research-notes/oregon-scientific-anywhere-weather.*` and `research-notes/acurite-access-atlas.*` are rated `rejected_dud` on the grounds that DNS interception is out of scope. The catalogue has since specced that route more than once.
- The 2026-10 sweep-log entries for Withings Body+ say the community code is unpublished. It is published, under MIT.
- The schema has no field for requests a device sends to a server the owner runs. Specs that need it (Eye-Fi, PicoBrew, and now the Aria) put the server's routes under `protocol_details` with a direction string, where no consumer can read them by key. The open sweep PR logs the same gap for Coway. It belongs in [docs/contributing/spec-evolution.md](docs/contributing/spec-evolution.md).

## Validation: 331/331 passing (330 device specs + 1 example)

Pinned by `test_gaps_md_states_the_real_spec_count` in
`scripts/test_device_specs.py`: this line said 92/92 for a fortnight after
the catalogue passed 130, which is the failure mode of every hand-written
count. It fails the suite now rather than quietly misleading a reader.
