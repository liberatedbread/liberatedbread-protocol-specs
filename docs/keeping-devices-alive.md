# Keeping Devices Alive After the Vendor Cloud Dies

This guide is the practical companion to the protocol specs: for each device
family documented here, what is the realistic path to keep it working from a
local controller (Home Assistant, ESPHome, or a plain MQTT broker) once the
vendor's app and backend are gone — or today, while they still limp along.

Everything below is derived from the specs in this repository. Where a claim
rests on something we have not verified ourselves it is marked **unverified**.
Follow the per-device doc links for the actual protocol details; this page
deliberately does not duplicate them.

**Effort scale:** `None` = works locally today with an off-the-shelf
integration, `Low` = one-time setup, `Medium` = some DIY (custom component,
flashing, broker config), `High` = real engineering (emulate a cloud service),
`Blocked` = no known local path for the affected function.

## Quick reference

| Device / family | Transport | Keep-alive path | Effort | Details |
|---|---|---|---|---|
| Roku | Wi-Fi (HTTP ECP :8060, SSDP) | Local by design; HA `roku` integration | None | [doc](devices/roku-ecp.md) |
| Philips Hue Bridge | Wi-Fi (local REST/CLIP API) | Local API key via link-button press; HA `hue` | None | [doc](devices/hue-bridge.md) |
| WLED controllers | Wi-Fi (JSON API, WebSocket, MQTT) | Open firmware, no cloud at all; HA `wled` | None | [doc](devices/wled-controller.md) |
| LIFX Z | Wi-Fi (LAN UDP) | Local LAN protocol; HA `lifx` | None | [doc](devices/lifx-z.md) |
| TP-Link Kasa | Wi-Fi (UDP :9999 / KLAP) | Local protocol; HA `tplink` integration | None | [doc](devices/tplink-kasa.md) |
| Dyson purifiers/fans | Wi-Fi (local MQTT :1883) | Device *is* the broker; creds from sticker; custom `ha-dyson` | Low | [doc](devices/dyson-air-purifier.md) |
| iRobot Roomba (Wi-Fi) | Wi-Fi (local MQTT-over-TLS) | Password retrievable locally (dorita980); HA `roomba` | Low | [doc](devices/irobot-roomba.md) |
| Rabbit Air | Wi-Fi (local UDP protocol) | Local-only control; HA `rabbitair` | None | [doc](devices/rabbit-air-purifier.md) |
| Snapmaker U1 | Wi-Fi (Moonraker HTTP :80) | Unauthenticated local Klipper/Moonraker API | None | [doc](devices/snapmaker-u1.md) |
| TVs (Android TV, LG, Sony, Panasonic, Samsung, Vizio, Philips) | Wi-Fi (varies) | Per-brand local APIs; HA `androidtv_remote`, `webostv`, `braviatv`, `panasonic_viera`, `samsungtv`, `vizio` | None–Low | see §1 |
| Belkin Wemo | Wi-Fi (UPnP/SOAP) | Local SOAP control; HA `wemo` | None | [doc](devices/wemo-devices.md) |
| Lutron Caseta Smart Bridge 2 | Wi-Fi (LIP telnet :23) | Local LIP after local pairing; HA `lutron_caseta` | Low | [doc](devices/lutron-caseta-smart-bridge.md) |
| UniFi / MikroTik / UniFi Protect | Wi-Fi/LAN | Infrastructure gear, local by design; HA `unifi`, `unifiprotect`, `mikrotik` | None | [UniFi device](devices/ubiquiti-unifi-device.md), [MikroTik](devices/mikrotik-routeros.md), [Protect](devices/unifi-protect-camera.md) |
| Enphase Envoy | Wi-Fi (local REST/HTTPS) | Local API, but fw 7+ needs a cloud-minted JWT (~1 yr token); HA `enphase_envoy` | Medium | [doc](devices/enphase-envoy.md), §5 |
| Rachio | Wi-Fi (HomeKit HAP) | HomeKit pairing is local; vendor app path is cloud | Low | [doc](devices/rachio-controller.md) |
| PurpleAir | Wi-Fi (local JSON API) | On-device JSON API documented; no account needed | None | [doc](devices/purpleair-sensor.md) |
| devolo Home Control | Z-Wave | Re-pair sensors to any local Z-Wave controller (Z-Wave JS) | Medium | [doc](devices/devolo-home-control.md) |
| Nuki Smart Lock | BLE GATT (+ optional Wi-Fi bridge) | Local BLE keypair; HA `nuki` integration | Low | spec only (`nuki-smart-lock`) |
| Magic Display (LED) | BLE (+ cloud for OTA/ads/logs) | Fully local over BLE already; cloud loss is invisible | None | [doc](devices/magic-display.md), §2 |
| KingSmith WalkingPad | BLE (WiLink/FTMS); MIOT on Wi-Fi/CN models | Local BLE control; KS Fit cloud only syncs account/history/OTA | None–Low | [doc](devices/kingsmith-walkingpad.md), §2 |
| UREVO Walking Pad | BLE (+ UREVO cloud for account/OTA) | Local BLE control; cloud only metadata/OTA | None–Low | [doc](devices/urevo-walking-pad.md), §2 |
| Chef iQ Sense | BLE + Wi-Fi→AWS IoT MQTT | Probes broadcast readable BLE advertisements (HA `ble_monitor` decodes them) | Low | [doc](devices/chef-iq-sense.md), §2 |
| Frigidaire ACs | Wi-Fi→Electrolux OCP only | **No LAN API found**; local only via DNS/TLS emulation of OCP (nobody has built it) | High | [audit](devices/frigidaire-local-api-audit.md), §2 |
| Anki Vector | Wi-Fi (local gRPC/TLS) | wire-pod local voice/token server; WireOS on unlocked bots | Medium | [doc](devices/vector-robot.md), §2/§3 |
| Bafang BBS02/BBSHD | UART | bbs-fw open replacement firmware | Medium | [doc](devices/bafang-bbs02.md), §3 |
| Tongsheng TSDZ2 | UART | OpenSource-EBike-firmware (OSF) + wireless board | Medium–High | [doc](devices/tsdz2-tongsheng.md), §3 |
| Xiaomi LYWSD03MMC | BLE | pvvx/ATC_MiThermometer flash (browser, no soldering) or ZigbeeTLc | Low | spec only, §3 |
| Chamberlain/LiftMaster Sec+ | Wired (UART wall-panel bus) | ratgdo / Konnected blaQ board (ESPHome), fully local | Low | [ratgdo](devices/ratgdo.md), [Sec+](devices/chamberlain-garage-opener-secplus.md), §3 |
| Bluetooth LED name badge | BLE | fossasia/badgemagic-firmware on CH582M badges | Medium | [doc](devices/bluetooth-led-name-badge.md), §3 |
| Broadcast BLE sensors (Govee, Inkbird, ThermoPro, SwitchBot, SensorPush, Xiaomi, Aranet4, Airthings) | BLE adverts | Passive listen-only; HA Bluetooth / `ble_monitor` / ESPHome proxy / Theengs | None–Low | §4 |
| Kwikset Kevo | BLE (+ dead cloud) | Local BLE lock/unlock survives; eKeys/time-sync are cloud-mediated and partly lost | Low + Blocked parts | [doc](devices/kwikset-kevo.md), §5 |
| SmartThings Hub v2 | Ethernet (Edge drivers local) | Drivers run locally, but claiming a hub needs the cloud | Blocked (claim) | [doc](devices/smartthings-hub-v2.md), §5 |
| Withings Body Smart WBS13 / Body Comp WBS12 / Body WBS06 | BLE (WBS13/WBS12); incoming Classic RFCOMM (WBS06) | Existing-association-key local reads are now specced; initial kl export and model-specific pairing remain prerequisites | Medium; untested here | [BLE scales](devices/withings-body-smart-comp-ble.md), [WBS06 Classic](devices/withings-body-wbs06-classic.md), §5 |
| Fitbit Aria Wi-Fi Smart Scale (FB201, four AA cells) | Wi-Fi (plain-HTTP upload client) | Still syncing and you want to keep that: do nothing. Otherwise DNS-redirect `www.fitbit.com` (never block it) to a LAN server, with nothing done at the scale. Setup mode is a one-way door | Medium; untested here | [doc](devices/fitbit-aria-wifi-scale.md), §2 |
| Fitbit Aria 2 (FB202, three AA cells) | Wi-Fi to the vendor cloud; Bluetooth for setup only | No local route known. Do not unpair or factory-reset: pairing has ended, so neither can be undone | Blocked | [research note](https://github.com/liberatedbread/liberatedbread-protocol-specs/blob/main/research-notes/fitbit-aria-2.md), §2, §5 |
| Fitbit Aria Air (FB203, three AAA cells) | BLE (AES-128-CCM, key-gated) | Not part of the Aria cutoff: leave it paired. Local reads need the scale's key, and both reported ways to get it begin with a factory reset that ends the pairing | High; untested here | [doc](devices/fitbit-aria-air.md), §2, §4 |

---

## 1. Local API / direct control — works today

These devices expose a real local control plane. Integrate them now and the
vendor cloud becomes irrelevant; the worst that happens when it dies is losing
firmware-update notifications.

**Network gear first.** Everything in this section is found by mDNS/SSDP on
the LAN, so give each device a DHCP reservation in your router *before* the
cloud disappears — an integration pointed at a stable IP keeps working even if
mDNS discovery changes in a later firmware.

- **Roku** — the External Control Protocol is plain HTTP on port 8060 with
  SSDP discovery, no auth. Home Assistant's core `roku` integration covers it.
  See [devices/roku-ecp.md](devices/roku-ecp.md).
- **Philips Hue Bridge** — the local CLIP API issues a key when you press the
  link button; no cloud account is involved at any step. HA `hue` integration.
  See [devices/hue-bridge.md](devices/hue-bridge.md).
- **WLED** — already the escape hatch: it *is* open firmware. JSON API,
  WebSocket push, MQTT, and realtime streaming protocols all work LAN-only.
  HA auto-discovers it via the `wled` integration. See
  [devices/wled-controller.md](devices/wled-controller.md).
- **LIFX Z** — local UDP LAN protocol; HA `lifx` integration. Cloud features
  (scenes synced to account) are the only casualty. See
  [devices/lifx-z.md](devices/lifx-z.md).
- **TP-Link Kasa** — local UDP 9999 (legacy XOR protocol) and the newer KLAP
  handshake are both documented; the HA core `tplink` integration (python-kasa)
  drives them locally — verified current as of 2026-08. See
  [devices/tplink-kasa.md](devices/tplink-kasa.md).
- **Dyson purifiers/fans** — the machine runs its own MQTT broker on port
  1883 (mDNS `_dyson_mqtt._tcp`); username is the serial, password is derived
  from the sticker Wi-Fi password. Record both **now** while the sticker is
  legible. The maintained path is the custom
  [`ha-dyson`](https://github.com/libdyson-wg/ha-dyson) integration
  (Dyson Local/Dyson Cloud lineage). See
  [devices/dyson-air-purifier.md](devices/dyson-air-purifier.md).
- **iRobot Roomba (Wi-Fi models)** — local MQTT-over-TLS; the per-device
  password can be pulled from the robot itself with no iRobot account
  (dorita980's password-disclosure probe). One local client at a time. HA
  `roomba`. See [devices/irobot-roomba.md](devices/irobot-roomba.md).
- **Rabbit Air** — fully local UDP protocol (HA core `rabbitair`,
  local_polling); the cloud only adds account features and OTA. See
  [devices/rabbit-air-purifier.md](devices/rabbit-air-purifier.md).
- **Snapmaker U1** — Klipper-based; Moonraker REST/WebSocket on plain HTTP
  port 80 with no authentication (verified live against a real U1). Any
  Klipper client (Mainsail/Fluidd-style) works. See
  [devices/snapmaker-u1.md](devices/snapmaker-u1.md).
- **TVs** — every documented TV platform has a local protocol: Android
  TV/Google TV (HA `androidtv_remote`, plus ADB), LG webOS (`webostv`), Sony
  Bravia (`braviatv`), Panasonic Viera (`panasonic_viera`), Samsung Tizen
  (`samsungtv`), Vizio SmartCast (`vizio`), Philips JointSPACE, Hisense VIDAA.
  See the individual pages under Devices → WiFi Devices.
- **Belkin Wemo** — local UPnP/SOAP; HA `wemo`. Setup/reset quirks are in
  [devices/wemo-setup.md](devices/wemo-setup.md).
- **Lutron Caseta Smart Bridge 2** — local LIP over telnet; pairing files are
  generated locally. HA `lutron_caseta`. See
  [devices/lutron-caseta-smart-bridge.md](devices/lutron-caseta-smart-bridge.md).
- **UniFi, UniFi Protect, MikroTik** — infrastructure gear that is local by
  design; the specs here cover discovery/identification.
- **PurpleAir** — the sensor serves its own JSON API on the LAN, no account.
  (Note: the HA `purpleair` integration is cloud-based; use the local REST
  path from the spec instead.) See
  [devices/purpleair-sensor.md](devices/purpleair-sensor.md).
- **Rachio** — the controller advertises HomeKit HAP over mDNS; HomeKit
  pairing is a local exchange, so Apple Home / `homekit_controller` keeps
  working without Rachio's cloud. Only discovery is documented in the spec —
  pairing an accessory we haven't tested is marked unverified there.
- **Nuki Smart Lock** — BLE GATT with a locally established keypair; the
  optional Wi-Fi bridge is only for remote access. HA `nuki`. Spec:
  `device-specs/devices/nuki-smart-lock.yaml` (no docs page yet).
- **Enphase Envoy** — local REST API, but see §5: firmware 7+ gates it behind
  a JWT minted from Enphase's cloud. HA `enphase_envoy` handles the token
  flow. See [devices/enphase-envoy.md](devices/enphase-envoy.md).
- **devolo Home Control** — plain Z-Wave devices; exclude them from the
  devolo hub and include them into any local Z-Wave controller (Z-Wave JS with
  a USB stick) before the devolo cloud/app goes away. See
  [devices/devolo-home-control.md](devices/devolo-home-control.md).

## 2. Cloud-redirection / interception — the device wants a server, give it one

For Wi-Fi devices that phone home, the general play is: run split-horizon DNS
(Pi-hole, AdGuard Home, or your router) so the vendor hostname resolves to a
local emulator, and terminate TLS there. How feasible that is depends entirely
on certificate pinning and hardcoded IPs — noted per device. **None of the
emulators below exist yet unless stated; treat them as documented attack
surface, not finished solutions.**

- **Magic Display (e-toys.cn)** — good news: you don't need to do anything.
  Control is 100% local BLE; the cloud backend
  (`http://api.e-toys.cn/api/`) only feeds the app's OTA-version check, ads
  and telemetry, and the OTA images are bundled in the app itself. A DNS
  sinkhole for `api.e-toys.cn` is optional hygiene. See
  [devices/magic-display.md](devices/magic-display.md).
- **KingSmith WalkingPad** — control plane is local BLE (WiLink/FTMS frames);
  the KS Fit cloud (`eu.api.ks.fit/V0.1/index.php`, plus CN and staging
  variants) only handles account, workout-history sync and OTA notification —
  all losable. For the Wi-Fi/CN variant there is a better trick than
  emulation: it is a registered Xiaomi MIOT device (`ksmb.walkingpad.v1`),
  controllable through python-miio or the HACS **Xiaomi Miot Auto**
  integration (`al-one/hass-xiaomi-miot`, verified current 2026-08). Working
  local BLE controllers: ph4r05/ph4-walkingpad, mcdax/walkingpad-controller.
  See [devices/kingsmith-walkingpad.md](devices/kingsmith-walkingpad.md).
- **UREVO Walking Pad** — same shape: local BLE control plane; the cloud
  (`service.urevosports.com`, `urevo.urevosports.com`, H5 pages on
  `h5.urevosports.com`) holds account/workout/OTA metadata. Caveat for
  would-be interceptors: the app also carries two **hardcoded plain-HTTP IP
  endpoints** — DNS redirection will not catch those; you would need
  IP-level redirection on the router. See
  [devices/urevo-walking-pad.md](devices/urevo-walking-pad.md).
- **Chef iQ Sense** — the practical keep-alive path is not the cloud channel
  at all: the probes continuously broadcast BLE advertisements that are fully
  decoded (temperature/status byte layout verified against a live CQ60) and
  already supported by HA's `ble_monitor` custom component. The cloud leg is
  AWS IoT MQTT (topics under `ciq-v2/...`, Cognito auth, OTA URL push); a
  local broker could in principle interpose, but that means defeating AWS IoT
  TLS — unverified and likely blocked by certificate validation. Treat BLE as
  the path. See [devices/chef-iq-sense.md](devices/chef-iq-sense.md).
- **Frigidaire connected ACs (Electrolux OCP)** — the honest bad news. A
  systematic audit of three app generations found **no steady-state LAN
  control API**; everything goes through OCP
  (`https://api.ocp.electrolux.one`, regional `api.us.` / `api.eu.` bases,
  websocket `wss://ws.us.ocp.electrolux.one` / `ws.eu.`). Community HA
  integrations ([ha-electrolux](https://github.com/TTLucian/ha-electrolux),
  active as of 2026-08) use the official developer API and therefore die with
  the cloud. Keeping these alive post-cloud means writing an OCP emulator and
  DNS-redirecting the fleet — High effort, unverified, nobody has done it.
  The local provisioning code in old APKs (Delta NIU TCP/TLS setup channel)
  is a lead, not a solution. See
  [devices/frigidaire-local-api-audit.md](devices/frigidaire-local-api-audit.md).
- **Anki Vector** — the most successful interception story in the collection.
  The robot speaks gRPC/TLS on the LAN; the only cloud steps were voice-intent
  processing and onboarding token issuance, and **wire-pod**
  (`kercre123/wire-pod`) replaces both locally (built on the vendor's own
  open-sourced cloud code). Official OTA hosts already fail DNS as of
  2026-07-31 while subscriptions are still billed — exactly the zombie-cloud
  scenario this guide exists for. Production robots need a one-time
  recovery-mode detour with DDL's free "ep" OTA before wire-pod will accept
  them; unlocked (OSKR/dev) robots can skip to WireOS (§3). See
  [devices/vector-robot.md](devices/vector-robot.md).

### Fitbit Aria scales

Three different products share the name, and only one of them belongs in
this section. The first two paragraphs apply whichever you own.

**What Google ended, and when.** By Google's current English help pages
([using a scale](https://support.google.com/googlehealth/answer/14236805),
[setting one up](https://support.google.com/googlehealth/answer/14236818)),
pairing and re-pairing of the Aria and the Aria 2 ended on **2026-11-09**,
with app version 5.12: "If you choose to unpair your scale after this date,
you will not be able to pair it again." That date has passed, so for those
two models treat unpairing and resetting as permanent. Two lines on those
pages are unchanged:
scales paired before the date that remain paired "will continue to sync",
with no end date named, and "Aria Air is not impacted by this change". One
observation about the source, which is not a second deadline: the English
notice read "November 28, 2026" when first fetched at 05:11 UTC on
2026-11-23 and "November 9, 2026" from at least 23:07 UTC that day, and the
German, French and Japanese editions still said 28 November at 00:57 UTC on
2026-11-24. Do not plan around the later date.

**Which Aria do you have?** Turn the scale over and count the batteries.

| Batteries | Model | Radio | Where it stands |
|---|---|---|---|
| Four AA | Aria (FB201), the original | Wi-Fi only | A local route is reported: a server of your own. [Device page](devices/fitbit-aria-wifi-scale.md) |
| Three AA, and "Aria 2" printed on the back | Aria 2 (FB202) | Wi-Fi; Bluetooth for setup only | No local route known. [Research note](https://github.com/liberatedbread/liberatedbread-protocol-specs/blob/main/research-notes/fitbit-aria-2.md) |
| Three AAA | Aria Air (FB203) | Bluetooth only | Not part of the change. [Device page](devices/fitbit-aria-air.md) |

Nothing below transfers from one model to another.

**Original Aria (four AA).** This is the one that belongs here, and it
differs from the preamble of this section in two ways. The scale uploads
over **plain HTTP**: there is no TLS to terminate, no certificate and no
pinning, and it does not check who answers `www.fitbit.com`. And servers for
it **do exist**: several public ones, listed on the
[device page](devices/fitbit-aria-wifi-scale.md#existing-public-servers)
with what each reports. None was written or run by this project, so
everything here is *reported* by other people and **unverified** by us. The
advice, in the order the page gives it:

1. **It still syncs to your Fitbit / Google account and you want to keep
   that: do nothing.** Do not unpair it, do not remove yourself from it, do
   not re-run setup, and do not press or step on it while it shows
   `TAP TO CHANGE`. **Do not add the redirect** of step 2 on the network the
   scale uses: the scale talks to one server only, so with the redirect in
   place nothing reaches Fitbit. Keep your Wi-Fi name and passphrase, and
   export your history now. If you also want a local copy of new readings, a
   pass-through relay is the only evidenced way, and a relay changes the
   scale's firmware exposure: read the page's relay section before building
   one.
2. **It is on your Wi-Fi and you want it local, or it has stopped syncing:
   a DNS redirect and a LAN server.** Run a server on the home network and
   make your DNS answer the one name `www.fitbit.com` with that server's
   address. Redirect the name, never block it; do it for the scale alone
   where your network allows, on the resolver the scale receives by DHCP.
   Nothing is done at the scale: no setup mode, no battery pull. What it
   costs: from the next weigh-in the scale talks to your server only,
   readings your server accepts never reach Fitbit, and its first accepted
   reply replaces the scale's users, display unit and clock. The server must
   never signal a firmware update. Keep the redirect for good; the reason is
   in [Blocking Vendor Updates and the Cloud](blocking-vendor-updates.md#fitbit-aria-redirect-dont-block).
3. **The router changed: bring the old network back first.** Give the new
   router, or a small dedicated access point, the same network name,
   passphrase and security mode as the old one, with 802.11b still allowed
   on 2.4 GHz. This is an untested inference. It costs nothing, and nothing
   is lost if it fails.
4. **Only as the last resort: setup mode.** This is for a scale with no
   usable network at all. One request to the scale's own open setup network
   hands it new Wi-Fi details, and it is a **one-way door**: assume the scale
   forgets its stored network the moment its display reads `SETUP ACTIVE`;
   the request replaces the token Fitbit gave it; and Fitbit will not pair
   the scale again, so a scale that still synced to your account stops for
   good. It is reported working on firmware 35, said by one author to work on
   37, unproven on 39, and has one unexplained failure report on 38. Have the
   redirect and the server answering before you start.

**Aria 2 (three AA): no local route is known.** Bluetooth is its setup
channel only. By Google's description its weigh-ins travel over Wi-Fi to
Google, so a phone should not expect to read a weight from it, and it has no
setup network or web page of its own. Nobody has published how it talks, so
the catalogue has a [research note](https://github.com/liberatedbread/liberatedbread-protocol-specs/blob/main/research-notes/fitbit-aria-2.md)
(`research-notes/fitbit-aria-2.md`) and no spec. In the note's order:

- **Do not unpair it.** In the app the button is "Disconnect device". By
  Google's notice a scale unpaired now cannot be paired again.
- **Do not factory-reset it.** The reset clears the scale's users and Wi-Fi
  networks, and the scale then asks to be set up, which is the step that has
  ended: a reset cannot be undone by any documented means. Google's own
  advice for a scale that logs you as a guest still ends in a factory reset,
  and its sync advice for other Fitbit devices says to remove "other Fitbit
  devices" from the account. Stop after the battery step, and leave the
  Aria 2 out of that advice. When you change batteries, keep your fingers off
  the small button above the battery slots: holding it while the batteries
  go in is the reset.
- **Safe to try.** At a router change, give the new router the same network
  name, security mode and passphrase before anything else, and keep the old
  router until the scale shows its check mark. That is ordinary Wi-Fi
  behaviour, untested on this model. Treat the in-app Wi-Fi change as already
  gone unless you have seen it offered, and even then use it only if the
  network has to change anyway: nobody has published a run of it since app
  5.12, and a change that is refused or interrupted may leave the scale
  without a network for good. Export your history while the scale
  still syncs (Google Takeout, the Google Health API, Health Connect); all
  three read Google's copy, and none is a local route. Even a stranded scale
  still weighs: the manual says setup is not needed to weigh yourself.
- **Already unpaired or reset?** Trying setup again costs no pairing, because
  none is left. One thing may be at stake: a scale that was unpaired but
  never reset may still hold its people and its network, and whether a failed
  setup clears them is not documented. Do not expect it to work, and never
  unpair a working scale to find out.
- **Do not try the original Aria's redirect on it.** Nobody has shown that it
  speaks that protocol, or which names it looks up.
- **How to help.** Three things leave the pairing alone. Look, without
  tapping through, at whether the app still offers "Wi-Fi Network" or "Pair
  Scale to Different Network" for the scale, and note the app version and
  the date. Run a passive Bluetooth scan (scan only: skip the optional
  connect on a scale you depend on). Log the router's DNS and capture one
  normal weigh-in. Either of the last two alone would turn the note into an
  identify-only spec. The note's experiments say how, what to scrub before
  sharing, and which steps are for a spare scale only.

**Aria Air (three AAA): not part of the change. Leave a working pairing
alone.** Google's notice says "Aria Air is not impacted by this change";
that is a statement about one change, not a promise about the future. The
scale is Bluetooth-only, so there is no server to redirect and nothing in the
original Aria's steps applies. In the page's order:

- **If it works, do nothing.** It still syncs with the vendor app, and it
  shows your weight on its own display with no app at all. A new phone means
  signing in to the same account there. It is not a reason to reset the scale
  or to remove it from the account.
- **If it stops syncing,** start with the first steps of the vendor's sync
  troubleshooting: app open nearby, restart the app, Bluetooth and the phone.
  Never reset the scale because a local client received nothing.
- **What the spec gives you:** how to recognise the scale, its GATT layout,
  the 19-byte encrypted message with its AES-128-CCM parameters, and
  synthetic vectors to test a decoder against. **What it does not give you:**
  the 16-byte key. The key is normally known only to the vendor app, and both
  reported ways to get one **begin by factory-resetting the scale**. The
  first, capturing the vendor app's setup write from your own phone's
  Bluetooth log (reported by one party), also removes the scale from your
  account before the reset. The second, writing a key of your own after the
  reset, is one report reproduced by nobody. Either way the pairing you have
  ends. Getting one back depends on the vendor app completing a fresh setup,
  and if it does not you hold an unpaired scale and an app that will not
  re-pair it. The kilogram scale factor is an unresolved conflict, and the
  scale's firmware-update service must never be written to: no recovery is
  known.
- **A free alternative** is on the device page: an Android app that reads
  the display through the phone camera, with no Bluetooth link to the scale
  and no key. This project has not run or reviewed it.

See [devices/fitbit-aria-wifi-scale.md](devices/fitbit-aria-wifi-scale.md),
[devices/fitbit-aria-air.md](devices/fitbit-aria-air.md) and the
[Aria 2 research note](https://github.com/liberatedbread/liberatedbread-protocol-specs/blob/main/research-notes/fitbit-aria-2.md).

## 3. Replacement firmware / hardware — replace the brain

When the device itself is fine but its firmware is the problem, reflash it.
After flashing, these devices move into category 1 or 4 permanently.

- **Xiaomi LYWSD03MMC thermometers** — the cheapest win in home automation.
  Flash [pvvx/ATC_MiThermometer](https://github.com/pvvx/ATC_MiThermometer)
  from a Chrome browser over BLE (TelinkMiFlasher, no soldering); the sensor
  then broadcasts unencrypted ATC/BTHome advertisements any BLE monitor can
  read. The same hardware converts to **Zigbee** via pvvx/ZigbeeTLc (Z03MMC).
  ⚠ Units sold since 2025-03 (PCB marks B1.5/B1.6) can be flashed but are
  not recommended: they draw more power and use weaker display and sensor
  parts. New B1.6 units on stock firmware 2.1.1_0159 also need Mi Home
  registration before their first OTA. Check the PCB mark before buying.
  Spec: `device-specs/devices/xiaomi-lywsd03mmc.yaml`.
- **Chamberlain/LiftMaster garage openers (Security+)** — the vendor cloud
  (myQ) is actively hostile: Home Assistant removed its MyQ integration in
  2023 after Chamberlain blocked third-party access. The community answer is
  a replacement controller board wired to the wall-panel bus:
  **[ratgdo](https://paulwieland.github.io/ratgdo/)** (DIY, ESPHome/MQTT,
  fully local) or the commercial **Konnected GDO blaQ**. Works with Security+
  1.0/2.0; note that openers sold from 2025 with a white learn button use
  Security+ 3.0, which neither board supports yet. See
  [devices/ratgdo.md](devices/ratgdo.md) and
  [devices/chamberlain-garage-opener-secplus.md](devices/chamberlain-garage-opener-secplus.md).
- **Bafang BBS02/BBSHD e-bike controllers** — flash
  [bbs-fw](https://github.com/danielnilsson9/bbs-fw) for open, tunable
  firmware on the stock controller. See
  [devices/bafang-bbs02.md](devices/bafang-bbs02.md).
- **Tongsheng TSDZ2 e-bike motors** — the OpenSource-EBike-firmware project
  replaces the stock firmware (and, with the TSDZ2_wireless nRF52840 board,
  the display stack too). Higher effort: motor-controller flashing, follow the
  project wiki. See [devices/tsdz2-tongsheng.md](devices/tsdz2-tongsheng.md).
- **Anki Vector (unlocked robots)** — [WireOS](https://github.com/os-vector/wire-os)
  is a full open firmware replacement for OSKR/dev units and the only
  supported path now that the official OTA servers are dead. Production robots
  stay on stock firmware + wire-pod (§2). See
  [devices/vector-robot.md](devices/vector-robot.md).
- **Bluetooth LED name badges** — CH582M-based badges can run
  [fossasia/badgemagic-firmware](https://github.com/fossasia/badgemagic-firmware);
  the stock badge is already fully local BLE (no pairing, no cloud), driven by
  FOSSASIA's Badge Magic app or the spec here. See
  [devices/bluetooth-led-name-badge.md](devices/bluetooth-led-name-badge.md).
- **WLED** — belongs here too: for cheap ESP-based LED controllers with a
  dying app, flashing WLED *is* the keep-alive move. See §1.

## 4. BLE-only devices — already cloud-free

Most of the BLE devices in this collection never needed a cloud: no account,
no pairing infrastructure, just advertisements and GATT. They survive every
vendor bankruptcy by construction. What you need is a receiver close to them:

- **Home Assistant Bluetooth integration** with one or more **ESPHome
  Bluetooth Proxies** (`bluetooth_proxy`) — cheap ESP32 nodes that extend BLE
  range to the whole house. Many broadcast sensors (Govee, Inkbird, SwitchBot,
  Xiaomi, ThermoPro, Aranet4, oral-b) are auto-discovered by core
  integrations.
- **`ble_monitor`** (`custom-components/ble_monitor`, HACS) — passive
  listen-only decoding for a long list of broadcasters; added Chef iQ CQ60
  support in 12.8.0, covers Govee/Xiaomi/Inkbird/ThermoPro families.
- **Theengs Gateway / OpenMQTTGateway** — BLE-to-MQTT bridges; right choice
  when your controller is not Home Assistant or when you want everything on a
  plain MQTT broker. Verified active as of 2025–2026.
- **The Liberated Bread mobile app**
  ([liberatedbread-mobile](https://github.com/liberatedbread/liberatedbread-mobile))
  — renders the specs in this repo directly for interactive BLE devices (LED
  signs, name badges, heated gear, mugs, walking pads): the open replacement
  for the vendor app itself.

Devices in this category include: Govee H5075/H5080/H6001, Inkbird IBS-TH and
BBQ thermometers, ThermoPro TP357 and TempSpike, SensorPush HT1/HTP.xw,
SwitchBot BLE, Xiaomi MiFlora and Mi Scale, Aranet4 (enable the "Smart Home
integrations" toggle once to make it broadcast), Airthings Wave, oral-b
toothbrushes, Omron BLE blood-pressure monitors, Ember Mug, iTag trackers, and
the whole LED sign/panel family (iDotMatrix, SPOTLED, CoolLEDX, Shining
mask/glasses, Divoom Pixoo, ELK-BLEDOM strips, SmartDawn, xkchrome, and the
motorcycle/bicycle LEDs). For the interactive ones, the per-device pages under
Devices → BLE Devices document pairing and reset.

One BLE-only device does not belong on that list: the **Fitbit Aria Air**.
Its link is local, but every reading is encrypted under a key that normally
only the vendor app holds, and both reported ways to obtain that key begin
with a factory reset that ends the vendor pairing. If yours works, leave it
paired. See [Fitbit Aria scales](#fitbit-aria-scales) in §2 and
[devices/fitbit-aria-air.md](devices/fitbit-aria-air.md).

Honest caveat: BLE is short-range. "Cloud-free" still means you need a proxy,
gateway, or phone within radio reach — plan ESPHome proxies for fixed sensors.

## 5. Dead ends and cloud-keyed devices — the honest list

Some families have no complete local path today. Documenting that is as
valuable as documenting a success — it tells you what to fix or what to avoid
buying again.

- **Kwikset Kevo** — a real post-mortem: ASSA ABLOY shut down the Kevo app
  and portal on **2025-11-14**. Local BLE lock/unlock, tap-to-enroll of new
  phones, history pull and even firmware-update transport all keep working
  (the full BLE protocol is in the spec). What is *lost*: remote access, eKey
  management, and **time sync** — the lock's clock certificate is computed
  server-side (`serverTimingInformationCertificate`) and is not reproducible
  locally, so scheduled/time-bounded eKeys are untested. Lesson: record
  everything while the cloud is alive. See
  [devices/kwikset-kevo.md](devices/kwikset-kevo.md).
- **Enphase Envoy (firmware 7+)** — local API in name only: the JWT the local
  endpoints demand is minted by Enphase's Enlighten cloud (~1-year validity).
  If Enlighten dies, tokens stop renewing and the gated endpoints degrade to
  the few unauthenticated ones. The installer/provisioning endpoints are not
  publicly documented at all. See
  [devices/enphase-envoy.md](devices/enphase-envoy.md).
- **SmartThings Hub v2** — Edge drivers genuinely run locally on the hub
  (that's what the `_smartthings-hedge._tcp` service is), but **claiming an
  unclaimed hub and distributing drivers both require the cloud**, and there
  is no documented alternative. Samsung already bricked the hub v1 fleet on
  2021-06-30, so this risk has precedent. If you depend on it: pair critical
  Zigbee/Z-Wave devices to a local stick as insurance. The Samsung
  *appliances* on the same account are a different story: the
  [LocalThings](https://github.com/mbillow/localthings) Home Assistant
  integration (HACS) drives them over the LAN with no Samsung account, so
  move those first. See
  [devices/smartthings-hub-v2.md](devices/smartthings-hub-v2.md).
- **Withings, scope correction** — local readout is no longer accurate to
  describe as universally blocked. [Body Smart WBS13 and Body Comp WBS12](devices/withings-body-smart-comp-ble.md)
  have a reported read-only BLE WPP path, and [Body/Nokia Body WBS06](devices/withings-body-wbs06-classic.md)
  has a separate incoming Classic RFCOMM path with weight/time/battery only.
  All require an existing 32-character association key and model-specific
  pairing, and all remain untested by this project. Fresh association/roster
  provisioning, other Withings models, destructive/settings writes and
  replacement-firmware services remain outside these paths.
- **Fitbit Aria 2** — no local route is known, and by Google's current
  English help pages pairing and re-pairing ended on 2026-11-09. Bluetooth is
  its setup channel only and nothing about how it talks is public, so there
  is a [research note](https://github.com/liberatedbread/liberatedbread-protocol-specs/blob/main/research-notes/fitbit-aria-2.md)
  and no spec. **Do not unpair it and do not factory-reset it:** by Google's
  notice an unpaired scale cannot be paired again, so neither can be undone
  by any documented means. What is safe to try, and how an owner can help
  change this entry, is under [Fitbit Aria scales](#fitbit-aria-scales) in
  §2.
- **Frigidaire / Electrolux OCP devices** — listed in §2, but until an OCP
  emulator exists they effectively belong here too.

## General practices

1. **Do it before the funeral.** Extract credentials, tokens, BLID/passwords,
   API keys and sticker secrets now, while apps and clouds still answer.
2. **Freeze the addressing.** DHCP reservations (or static IPs) for every
   local-API device; integrations keyed to IPs outlive mDNS changes.
3. **Quarantine, don't amputate.** Devices that work locally can be denied
   WAN access at the router — but block *internet*, not the LAN, and keep DNS
   redirection rules documented for the devices in §2. The per-device DNS
   blocklists generated from the specs, and which names must *not* be blocked
   (a clock, most often; for the original Fitbit Aria, the one name you
   redirect to your own server instead), are in
   [Blocking Vendor Updates and the Cloud](blocking-vendor-updates.md).
4. **Archive the app.** Keep an offline copy of the vendor APK/IPA and its
   version number; it is often the only place OTA images and setup flows live
   (the Magic Display OTA images survived precisely because they were bundled
   in the app).
5. **Prefer local-first hardware next time.** Everything in §1 and §4 stayed
   useful because somebody documented it — contributing a spec is how the next
   device gets saved. See [How to Contribute](contributing/index.md).
