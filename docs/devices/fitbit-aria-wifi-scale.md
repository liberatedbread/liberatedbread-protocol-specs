# Fitbit Aria Wi-Fi Smart Scale (FB201)

> **Status**: Spec Available, untested
> **Protocol**: Wi-Fi. The scale is a plain-HTTP *client* of a server you run
> **Integration**: Identify-only. A phone app cannot be the scale's server
> **Manufacturer**: Fitbit (Google)
> **Manufacturer Status**: Abandoned. Vendor pairing has ended (2026-11-09 by Google's current English help pages)

## Overview

This page covers the **original** Aria, model FB201 (sold as FB201B black and
FB201W white): the one that takes **four AA batteries** and has Wi-Fi only.
Aria 2 (three AA, "Aria 2" printed on the back) and Aria Air (three AAA,
Bluetooth only) are different products and none of this applies to them.

**Vendor pairing has ended.** Read on 2026-11-24 at 01:01 UTC, Google's
English help page says: "Starting November 9, 2026, with the release of app
version 5.12, you can no longer pair or re-pair Aria and Aria 2 scales"
([Google Health help](https://support.google.com/googlehealth/answer/14236805)).
That date is already past. Three things Google still says, unchanged:

- "If you choose to unpair your scale after this date, you will not be able to
  pair it again." So unpairing is now permanent.
- "Any scales that were paired prior to this date, and remain paired, will
  continue to sync." No end date is named, and it is not a promise.
- "Aria Air is not impacted by this change."

The date on that page was edited while this entry was being written. The same
sentence said "Starting November 28, 2026" when read on 2026-11-23 between
05:11 and 06:57 UTC, and "November 9" from 23:07 UTC that day; nothing else in
the sentence changed and the edit was not announced. On 2026-11-24 the German,
French and Japanese editions still said 28 November, and a
[press report](https://gadgetsandwearables.com/2026/11/20/fitbit-aria-support-cutoff-early/)
of 2026-11-20 quotes the 28th. **Do not plan around the later date.** For this
model the door was already shut in practice: on 2026-11-23 and 2026-11-24 the
web page the manual sends you to for setup redirected to a notice titled "Aria
is no longer supported", last modified on 2026-11-09. Security updates for
this scale ended in 2020.

**What can be done.** The scale never needed Fitbit's app to talk. After a
weigh-in it joins Wi-Fi and POSTs its readings over plain HTTP to the name
`www.fitbit.com`. It does not check who answers. So an owner can run a small
server on the home network, **redirect** that one name to it in DNS, and the
scale keeps working: weight, body fat, users, clock and display unit. Nothing
has to be done to the scale itself for that.

The machine-readable version, complete enough to build the server from, is
[`fitbit-aria-wifi-scale.yaml`](https://github.com/liberatedbread/liberatedbread-protocol-specs/blob/main/device-specs/devices/fitbit-aria-wifi-scale.yaml).
This project ships no server; the spec is the product.

!!! warning "Nothing here was run on this project's hardware"

    Every fact below comes from other people's published captures, write-ups
    and open-source servers. Their authors report it working on firmware 35, 37
    and 39. This project has not repeated any of it, so treat it as *reported*
    and *untested*, and read "What is and is not established" before you act.

!!! danger "One step cannot be undone"

    Putting the scale into **setup mode** and sending it new Wi-Fi details is a
    **one-way door**. Assume the scale forgets its stored network the moment
    its display reads `SETUP ACTIVE`. The request then replaces the token
    Fitbit gave it. Fitbit will not pair this scale again, so a scale that
    still synced to your account stops for good. A scale that is already on
    your Wi-Fi never needs setup mode.

### Which situation are you in?

1. **The scale still syncs to your Fitbit / Google account and you want to
   keep that.** Do nothing to the scale. Do not unpair it, do not remove
   yourself from it, do not re-run setup, and do not press or step on it while
   it shows `TAP TO CHANGE`. **Do not add the redirect** described below on
   the network the scale uses: the scale talks to one server only, so with the
   redirect in place nothing reaches Fitbit. Keep your Wi-Fi name and
   passphrase. Export your history now
   ([Google's export instructions](https://support.google.com/googlehealth/answer/14236615)):
   Fitbit's own notice says the scale's data can no longer be viewed in the
   app, while its help page says synced data is not affected. If you want a
   local copy of new readings as well, the only evidenced way is a
   [pass-through relay](#keeping-vendor-sync-do-nothing-or-a-pass-through-relay).
2. **The scale is on your Wi-Fi and you want it local** (or it has stopped
   syncing). Start a server and add the DNS redirect. Nothing is done to the
   scale; the next weigh-in arrives at your server. This is the primary and
   best-evidenced route.
3. **The scale lost its network because you changed the router.** Before
   anything else, try giving the new router (or a small dedicated access
   point) the old network name, passphrase and security mode. This is an
   untested inference; it costs nothing and loses nothing.
4. **The scale has no usable network at all** (second-hand, never set up, old
   network gone for good). The direct setup below is the only way. It is the
   one-way door: reported working on firmware 35, said by one author to work
   on 37, unproven on 39, and with one unexplained failure report on
   firmware 38.

### What is and is not established

| Claim | Who says so |
|---|---|
| The scale uploads to whatever answers `www.fitbit.com` over plain HTTP on port 80 | A 2014 capture, a public 2016 capture set and several independent owners; firmware 35, 37, 39 |
| A local reply sets the display unit and the clock | Reported on firmware 35 and 39 |
| The scale recognises one or two users sent by a local server | Reported on firmware 35; 37 and 39 by one contributor |
| One request to the scale's setup network makes it join your Wi-Fi | Shown on firmware 35. One line in a README for 37. On 39 the request returned 200 but nobody has published the scale joining. **No success report on 38, one failure report** |
| After setup the scale calls register, validate, then an empty upload | Seen against Fitbit's server on firmware 35 and 37. Against a local server nobody has published a log |
| A check mark on the display with a server that writes its own replies | Not explicitly reported by anyone |
| A battery change keeps the stored Wi-Fi | Fitbit's troubleshooting assumes it. A 2015 write-up says a fix then being prepared should wipe the key when the batteries are removed. One firmware 39 log shows the network *name* and the users still there, and does not show whether the key survived. **Not established** |
| Entering setup mode discards the stored network | Stated for firmware 35; a 2015 write-up says a fix Fitbit was preparing should do so. Not tested on 37 to 39. **Assume yes** |
| A recreated network (same name and passphrase) is rejoined | Inferred. Nobody has reported trying; the manual says a changed router needs a reconnect |
| Zero users, or more than two users, from a local server | Thin or untested |
| Already-paired scales keep syncing to Fitbit | Google's help page says so and names no end date; the notice on Fitbit's own site says it no longer connects to these scales |
| Firmware update from a local server | Never done. **Must never be attempted** |

## Hardware

| Property | Value |
|----------|-------|
| Model Number | FB201 (retail FB201B, FB201W; regulatory name FB201A) |
| Chipset | GainSpan GS1011MEE Wi-Fi module, which also runs the scale's own program |
| Radio | Wi-Fi 802.11b only, 2.4 GHz, channels 1 to 11. No Bluetooth |
| FCC ID | XRAFB201A (with the trailing A) |
| Category / hierarchy | `scale` + `["measurement", "health", "body_composition"]` |
| Aliases | Fitbit Aria, Aria Wi-Fi Smart Scale, "Aria 1", original Aria |
| Power | Four AA cells |
| MAC address | Printed on the underside label. Begins `00:1D:C9` or `20:F8:5E`; neither block is Fitbit's |
| Name in a router's client list | `GainSpan` + six lower-case hex characters (the end of the MAC), e.g. `GainSpan005301`. Seen on one firmware 37 unit; probably the Wi-Fi module maker's default, so a hint, not proof |

**Networks it can join:** 2.4 GHz with 802.11b rates still enabled (a mixed
b/g/n network that still allows them); WEP, WPA or WPA2 with a passphrase of at
most 31 characters; DHCP. The vendor advises a network name and passphrase made of letters and
digits only. **Networks it cannot join:** 5 GHz, 2.4 GHz with 802.11b turned
off, enterprise (802.1X) networks, networks that need a static address.
**Not established:** WPA3 (the radio predates it) and channels 12 and 13.

## Initial Setup

See [Initial Device Setup](../protocols/device-setup.md) for the general
patterns. The spec's `device.setup` block carries the same routes in the same
order, with an actor on every step.

| Property | Value |
|----------|-------|
| Setup required | **No** for a scale already on your Wi-Fi. Yes for a scale with no usable network |
| Method | 1. `none`: DNS redirect plus a LAN server, nothing done at the scale. 2. `none`: bring the old network back (untested). 3. `softap_http`: one GET to the scale's own setup network, a one-way door. The vendor's `cloud_account` flow is dead |
| Setup AP / advertised name | Open network `Aria ` + six hex characters (the end of the MAC), e.g. `Aria 005301` |
| Passphrase protection | plaintext, over an open network |
| Confidence | medium (public sources and working open implementations; not replayed here) |

**Factory reset**: none is established for this model, and what the vendor's
"erase" does is not established either. That instruction is to take the
batteries out for 10 seconds. A third-party log on firmware 39 shows the
stored users and the stored network *name* still there after a power loss.
The same log prints an empty passphrase field and then four failed attempts to
join at weak signal, so it does not show that the Wi-Fi key survived.
Fitbit's own troubleshooting assumes a battery pull keeps the network; a 2015
write-up says a fix Fitbit was then preparing should wipe the key when the
batteries are removed. So whether the key survives is not established on any
firmware. Do not try a reset as troubleshooting, do not pull a battery on a
working scale without a reason, do not treat a battery pull as a wipe before
selling the scale, and keep hands and feet off the scale after any battery
change until the display goes dark.

**Rebinding to a new network**: there is no in-place way. New Wi-Fi details
are accepted only in setup mode, and setup mode is the one-way door. So first
try to avoid it: give the new router the same network name, passphrase and
security mode as the old one, with 802.11b still allowed on 2.4 GHz. That is
an inference from how the scale stores its network, not a tested procedure,
and the manual says a changed router needs a reconnect; if it fails nothing
has been lost. Only then use the direct setup. If the scale is to stay local,
the new network's DNS needs the same redirect.

### Route 1: the server and the DNS redirect (scale already on Wi-Fi)

For situation 2. Nothing is done to the scale: no setup mode, no battery pull.
The scale's stored network and token are left alone. What does change is on
your side of the wire: from the next weigh-in the scale talks to your server
only. Readings your server accepts never reach Fitbit, and your server's first
accepted reply replaces the scale's stored user list, display unit and clock.

**Who should not do this:** anyone in situation 1. See
[Keeping vendor sync](#keeping-vendor-sync-do-nothing-or-a-pass-through-relay).

**Build and test the server first, without touching DNS.** Address it
directly:

```text
curl -H "Host: www.fitbit.com" http://192.168.1.50/scale/validate   -> T
```

**Redirect one name, do not block it.** Tell your network's DNS to answer
`www.fitbit.com` with the LAN address of your server. Examples use
`192.168.1.50`. Not `fitbit.com`, not `*.fitbit.com`: that one name.

- **Router "local DNS record" / "static host" / "DNS override"**: add
  `www.fitbit.com` → `192.168.1.50`. Then test it (below). One owner reports
  that a UniFi gateway's built-in record did not override a name that has a
  real public answer; another reports a UniFi redirect working.
- **Pi-hole**: add a Local DNS record `www.fitbit.com` → `192.168.1.50`. The
  scale must receive the Pi-hole as its DNS server by DHCP.
- **dnsmasq**: `host-record=www.fitbit.com,192.168.1.50` answers exactly that
  name. Owners also report `address=/www.fitbit.com/192.168.1.50`, which
  answers the name and everything under it.

The scale uses the DNS server its DHCP lease names, so the redirect must live
on that resolver.

**Scope it.** Every phone and browser on the network looks up the same name.
A network-wide record sends them to your server, where they fail, and one
owner who pointed a whole household's DNS at a shared machine reports
intermittent failures for every device. If the same house has an Aria 2, it
may depend on the same name; nobody knows. Better is to give the redirect to
the scale alone, with a per-device DNS server handed out by DHCP. A separate
guest or IoT network does the same job **only if the scale is already on
it**: moving a joined scale to another network needs setup mode, the one-way
door. With dnsmasq as the DHCP server the per-device form is, for example:

```text
dhcp-host=00:00:5e:00:53:01,set:aria
dhcp-option=tag:aria,option:dns-server,192.168.1.51
```

Here `192.168.1.51` is a **resolver** that carries the `www.fitbit.com` →
`192.168.1.50` record and forwards every other name. It can be the same
machine as the server, but whatever address you hand out as DNS server must
actually run a resolver, or the scale gets no answers and shows `NO SYNC`.
Replace the placeholder MAC with the one on the scale's label. This is
ordinary dnsmasq configuration, inferred to work because the scale uses the
resolver its lease names; no source reports this exact form with the scale.

**Test it from a second device**, not from the DNS box itself, which can pass
falsely, and with curl, **not a browser** (a browser that has visited
fitbit.com switches to HTTPS and fails against a port-80 server):

```text
nslookup www.fitbit.com          -> 192.168.1.50
curl http://www.fitbit.com/scale/validate   -> T
```

Your server answers `T`. Fitbit's own server answered `F` to that same bare
request on 2026-11-23 and 2026-11-24, so `F` means the redirect is not in
effect.

**Then just weigh yourself.** Roughly 20 seconds later a `POST /scale/upload`
should reach your server. The scale looks the name up at the start of each
session, so a changed DNS answer is expected to apply at the next weigh-in.
**Do not pull a battery** to hurry it: nothing shows that is needed, and on a
working scale it opens the `TAP TO CHANGE` prompt. `NO SYNC` on the display
means the upload failed or your reply was rejected; the scale keeps the
reading and sends it again next time, so a wrong first attempt loses nothing.

**Keep the redirect for good.** If the public name ever changes hands, whoever
answers it receives your uploads and can tell the scale to fetch firmware.
This is the same point
[Blocking Updates & the Cloud](../blocking-vendor-updates.md) makes about
lapsed vendor names; the published blocklists deliberately leave
`www.fitbit.com` out for this scale.

**If you cannot change DNS**, three variants exist, none published for this
scale as a working bundle: rewrite the scale's port-80 traffic at a gateway
you control (destination NAT); put the scale on its own small network, a
dedicated access point or travel router with its own resolver; or build the
[ESP32 project](https://github.com/tao-j/helvetic/tree/master/esp32) that is
access point, DNS and server at once. They are rated under
[Other local routes](#other-local-routes). The last two move the scale to a
new network, which means setup mode unless the old network's name and
passphrase are reused.

### Keeping vendor sync: do nothing, or a pass-through relay

For situation 1. The safe choice is to do nothing.

If you also want a local copy of each reading while Fitbit still answers, the
evidenced way is a **pass-through relay**: the same redirect, pointing at a
small program that logs each upload and then passes it on to Fitbit's real
server, handing Fitbit's reply back to the scale. A
[December 2024 write-up](https://www.waynepiekarski.net/blog/2024/12/fitbit-mitm.htm)
and a 2024 container, [aria2mqtt](https://github.com/bigbadbob2003/aria2mqtt)
(MIT), do this; an older relay,
[aria-spoof](https://github.com/ads04r/aria-spoof), ran on firmware 39 from
2018. It needs no setup mode and leaves the scale's network and token alone.
Know its limits:

- The relay must reach Fitbit by **IP address**, because the name now points
  at the relay. Look the address up *before* adding the redirect. It has
  changed over the years.
- It works only while Fitbit answers, and Fitbit can stop at any time. **Make
  the switch to local replies a decision, not an automatic fallback.** A reply
  your relay writes itself is accepted as delivered, so that reading never
  reaches Fitbit, and it replaces the scale's users, unit and clock with
  yours. While you want vendor sync, answer a Fitbit error or timeout with an
  error status: the scale is reported to keep a reading that was not accepted
  and send it again. In a long outage the backlog grows, and what happens
  when it fills is unknown.
- Fitbit's reply reaches the scale: users, unit and clock stay Fitbit's.
- **A relay changes the firmware exposure.** The published relays hand
  Fitbit's reply back as it came, any update signal included. With the
  redirect in place, the scale's request for the image then arrives at your
  relay, not at Fitbit, and nobody has published what a scale does when that
  fetch fails or is answered by an error page. So, as this project's own
  untested rule: check the tail of every Fitbit reply (three words, each 0 or
  3, and no extra bytes) before handing it on. Do not hand on anything else:
  log it and answer the scale with an error, so it shows `NO SYNC` and keeps
  the reading. Never answer or forward a request under `/scale/firmware/`.
  What to do next is then your decision. Taking the redirect out puts the
  scale back in direct contact with Fitbit, which can send the signal itself
  (no recovery from a failed update has been shown); switching to local
  replies ends vendor sync.
- Everyone's readings in the upload, guests included, still go to Fitbit.

This page does not specify a relay byte for byte.

### Before setup mode: bring the old network back (untested)

For situation 3. Configure a 2.4 GHz network with **exactly** the old network
name, the old passphrase and the old security mode, with 802.11b rates enabled
and band steering off. A small dedicated access point does as well as the main
router. Then weigh yourself. Do not pull a battery and do not press anything.

A check mark, or an upload at your server, means the scale rejoined and
nothing about it has changed. `NO SYNC` means it did not join, or joined and
found no server; a device named `GainSpan` plus six characters in the router's
client list tells the two apart. Nobody has reported trying this, and the
manual says a changed router needs a reconnect. If it fails, nothing has been
lost.

### Last resort for Wi-Fi: direct setup (the one-way door)

For situation 4 only. **Have the redirect and the server answering first**,
and test them from a second device. Use a computer that is *not* the machine
running the server, the resolver or a hotspot: the scale calls the server
within a second of joining. Every published report used a computer; nobody
reports doing this from a phone.

1. **You:** server running, redirect tested. If the scale is already on this
   network, stop here and weigh in.
2. **You:** take **one** battery out, wait 10 seconds, put it back. Do not
   press or step on the scale. The display shows `HI :)`, then `V` and a
   number (the firmware, e.g. `V39`), then `SETUP ACTIVE` if no network is
   stored. If it shows `WIFI IS <your old network>` and `TAP TO CHANGE`
   instead, a network is still stored. To back out, leave the scale alone
   until the display goes dark.
3. **You. Point of no return.** Only if it shows `TAP TO CHANGE`, and only if
   you mean to re-provision: press briefly and firmly, for under a second, on
   the **two lower corners, farthest from the display**. It should change to
   `SETUP ACTIVE`. From that moment assume the stored network is gone, even if
   you send nothing, and that a scale which still synced to Fitbit has stopped
   for good. If it goes blank or shows `STEP ON` or a weight, you missed the
   moment; pull a battery and try again. The prompt comes about three seconds
   after the firmware number.
4. **You:** on the second computer, join the open Wi-Fi network `Aria XXXXXX`.
   The scale is `192.168.240.1` on it.
5. **Your computer:** send one request, with the name and passphrase of the
   network the scale should join and any short token:

    ```text
    curl -v --raw --max-time 15 --cookie "token=localsetup01" "http://192.168.240.1/scale/setup?ssid=HomeNet24&custom_password=examplepass123"
    ```

    Look for a status line with **200**. On firmware 39 the rest of the reply
    is malformed, so curl may then report an error or time out. That is
    expected; the 200 is what counts. `ssid` and `custom_password` are URL
    parameters; the token travels as the cookie `token` and can be any short
    string. Use at most 31 characters: a longer token is reported to be cut to
    31 when the scale echoes it (a third party's reading of the firmware,
    relayed through an issue thread this project could not read verbatim; not
    tested). How the scale decodes spaces and symbols in the
    URL is not documented, which is one more reason to use letters and digits.
    Send this one request and nothing else: nothing shows what the scale's
    web server does with other paths or with a POST.
6. **The scale:** drops its `Aria XXXXXX` network and joins yours. `WIFI ERR`
   or `NO SYNC` now means it could not join or found no server. Nobody has
   published a log of this join on firmware 39, and on 38 nobody reports it
   succeeding.
7. **The scale:** calls `GET /scale/register`, then `GET /scale/validate`,
   then a first `POST /scale/upload` with no readings in it, on
   `www.fitbit.com`, which is now your server. All three should show in its
   log within about a second. The vendor describes a check mark or smiley on
   the display at this point.
8. **You:** step on. An upload should arrive.

The passphrase you send in step 5 crosses an **open** Wi-Fi network in clear
text. Do it at a time and place where that is acceptable, and keep setup mode
short.

**If it fails:** wrong passphrase or one over 31 characters; a router that no
longer accepts 802.11b; MAC filtering, a firewall or an extender; the redirect
missing from the resolver the scale actually uses; a server on a port other
than 80 or one that redirects to HTTPS; the same machine acting as server and
as the sender of the setup request.

**If `SETUP ACTIVE` appeared by accident** on a working scale (someone pressed
or stepped on it during `TAP TO CHANGE`), what follows is an **untested
suggestion**: nobody has reported what recovers from it, or whether setup mode
ends by itself. Send nothing. Take one battery out for 10 seconds, put it back, and do
not touch the scale. If `WIFI IS <name>` appears, the name is still stored;
that does not show the key is, so weigh in to find out whether the scale can
still join. If `SETUP ACTIVE` appears again, the network is gone and the
direct setup is the only way back.

### What the display shows

| Display | Meaning |
|---|---|
| `HI :)` then `V39` | Power-up; `V` and the firmware number |
| `SETUP ACTIVE` | Setup network is up, waiting for the request. Assume the old network is already forgotten |
| `WIFI IS <name>` / `TAP TO CHANGE` | A network is stored. Leave the scale alone to keep it. A press on the two lower corners, or a step onto the scale, enters setup mode |
| `STEP ON`, `SENSING`, `STEP OFF`, `THINKING` | Weigh-in phases |
| Initials, or `GUEST` | Recognised user, or nobody matched (weight only) |
| Progress bar, then check mark | Uploading, then accepted |
| `WIFI ERR` / `NO SYNC` during setup | Could not join the network or reach a server |
| `NO SYNC`, or Wi-Fi symbol with an X, after a weigh-in | Upload failed or reply rejected; reading kept and re-sent |
| `ERR` after `THINKING` | Measurement failure, not a network problem |

## Pairing

See [Pairing, Bonding and Unpairing](../protocols/pairing.md).

| Property | Value |
|----------|-------|
| Pairing required | No |
| Security mode | `none` |
| Bonding | `none` |
| PIN source | not applicable |
| One central at a time | not applicable (no Bluetooth) |
| One bond at a time | not applicable |
| Confidence | medium (working open implementations; not run here) |

Nothing pairs. The scale trusts whatever answers `www.fitbit.com` on the
network it joined, and accepts any reply whose layout and checksum are right.
It does not authenticate the server; your server needs no key or certificate.
The network is the only gate.

**Entering pairing mode**: there is none. Setup mode only hands the scale
Wi-Fi credentials, and it is a one-way door.

**Unpairing**: "unpair" and "remove yourself from the scale" are things you
did in a Fitbit account. Do not: by Google's current statement the scale
cannot be paired again, so it cannot be undone.

**Recovery**: if the display shows `NO SYNC`, fix the server or the redirect;
the readings are kept on the scale and sent again.

## Protocol Summary

The scale is the client. These are routes on **your server**, not on the
scale; do not point anything at the scale's address.

### What your server must answer

| Method | Path | When | Reply |
|--------|------|------|-------|
| GET | `/scale/register?serialNumber=…&token=…&ssid=…` | Right after the scale joins Wi-Fi at the end of setup | `200`, empty body, `Content-Length: 0` |
| GET | `/scale/validate?serialNumber=…&token=…` | 0.2 to 0.4 s later, on the same connection (firmware 37) | `200`, body `T`; `Content-Length: 1` recommended |
| POST | `/scale/upload` | About 20 s after a weigh-in; with zero records straight after validate, on a new connection | `200`, `Content-Length`, the binary reply below |

`serialNumber` is the MAC as 12 upper-case hex digits, not the 16-digit serial
on the label. Listen on TCP 80, plain HTTP/1.1, and accept any `Host` header
(the scale sends `Host: www.fitbit.com`, and on register and validate no other
header at all). The upload body is binary even though the scale labels it as a
form; read the raw bytes. Every multi-byte number in both directions is
little-endian. Be able to answer validate on the connection that carried
register. Answer a malformed upload with `400` and no binary reply.

### Upload request: `48 + 32 × records` bytes

| Offset | Length | Field | Type | Unit / meaning |
|---:|---:|---|---|---|
| 0 | 4 | protocol version | u32 | always 3 |
| 4 | 4 | battery | u32 | percent |
| 8 | 6 | MAC | bytes | printed order |
| 14 | 16 | auth code | bytes | opaque per-scale value; origin unknown |
| 30 | 4 | firmware version | u32 | 35, 37, 39 reported |
| 34 | 4 | unknown | u32 | 33 on firmware 35 and 37 |
| 38 | 4 | scale clock | u32 | Unix seconds |
| 42 | 4 | record count | u32 | 0 to 17 seen |

Then one 32-byte record per reading, the first at offset 46:

| Offset in record | Length | Field | Type | Unit / meaning |
|---:|---:|---|---|---|
| 0 | 4 | constant | u32 | always 2; meaning unknown |
| 4 | 4 | impedance | u32 | raw; unit not confirmed |
| 8 | 4 | weight | u32 | grams |
| 12 | 4 | time of reading | u32 | Unix seconds, by the scale's clock |
| 16 | 4 | user id | u32 | 0 = guest |
| 20 | 4 | body fat | u32 | thousandths of a percent (22500 = 22.5 %); 0 for guests |
| 24 | 4 | "covariance" | float32 | meaning unknown |
| 28 | 4 | second body-fat figure | u32 | meaning unknown; use the first |

Then two bytes: CRC, low byte first, over everything before it.

Reject a body shorter than 48 bytes, one whose length is not 48 plus a
multiple of 32, a version other than 3, or a record count that does not match
the length. Do not rely on record order; sort by time. The scale re-sends what
it thinks was not delivered, so de-duplicate on MAC, record time and weight.

**Clock.** The scale's clock is whatever your last reply set; after a battery
change it restarts at a fixed time (the firmware's build date, February 2016,
on firmware 39). Store `true time = server now − (scale clock − time of
reading)`, not the raw time. A reading whose time is *later* than the scale
clock cannot be placed that way; keep its raw time and mark it.

### Reply: `27 + 77 × users` bytes

| Offset | Length | Field | Type | Value |
|---:|---:|---|---|---|
| 0 | 4 | server time | u32 | Unix seconds; the scale sets its clock from it |
| 4 | 1 | display unit | u8 | 0 pounds, 1 stone, 2 kilograms |
| 5 | 1 | status | u8 | send `0x32` |
| 6 | 1 | unknown | u8 | always `0x01` |
| 7 | 4 | user count | u32 | 1 and 2 reported; vendor limit 8 |

Then one 77-byte user record per user, the first at offset 11. The record is
packed: height starts straight after the one-byte sex field.

| Offset in record | Length | Field | Type | Value |
|---:|---:|---|---|---|
| 0 | 4 | user id | u32 | any stable non-zero number |
| 4 | 16 | reserved | bytes | sixteen zero bytes |
| 20 | 20 | name | ASCII | upper case, cut to 20 bytes, padded with spaces; the display uses the first three characters |
| 40 | 4 | weight window, low | u32 | grams |
| 44 | 4 | weight window, high | u32 | grams |
| 48 | 4 | age | u32 | years |
| 52 | 1 | sex | u8 | send `0x00` female or `0x02` male; see below |
| 53 | 4 | height | u32 | millimetres |
| 57 | 4 | unknown | u32 | always 0 |
| 61 | 4 | previous body fat | u32 | thousandths of a percent; send 0 |
| 65 | 4 | previous "covariance" | float32 | send 0 |
| 69 | 4 | previous weight | u32 | grams; send 0 |
| 73 | 4 | time of previous weight | u32 | Unix seconds; send 0 |

Then the 12-byte tail, the CRC and a length:

| Offset (after users) | Length | Field | Type | Value |
|---:|---:|---|---|---|
| 0 | 4 | tail word 0 | u32 | send 0. **Never 1** |
| 4 | 4 | tail word 1 | u32 | send 3. **Never 1** |
| 8 | 4 | tail word 2 | u32 | send 0. **Never 1** |
| 12 | 2 | CRC | u16 | over everything before it, low byte first |
| 14 | 2 | length | u16 | `25 + 77 × users` (`0x66` for one user, `0xb3` for two) |

**The tail: two readings, one rule.** One of the first two tail words is the
firmware-update status, and which one is not settled. helvetic, its test
server and the ESP32 port send 0, 3, 0 and are reported accepted (firmware 35
by helvetic's author; 37 by the port's author; 37 and 39 by one helvetic
contributor). aria-bridge, the one local server whose own author reports
firmware 39, sends 3, 3, 0. Fitbit's own server sent 0, 0, 0: in 20 of 20
replies of a public 2016 capture set (firmware 37), and in a 2014 capture
described as twelve zero bytes; that tail has not been reported from a local
server. helvetic's notes put the status in the first word, its code in the
second. For a server none of that matters: **send 0, 3, 0; never put 1 in any
of the three words; never send a value other than 0 or 3; never add bytes
after the tail.**

**The sex byte: two readings.** Local servers send `0x00` or `0x02` and are
reported working. Fitbit's replies carried `0x34` (a 2014 capture, labelled
"unset" by its author) and `0x36` (20 of 20 replies in 2016). Either the byte
is a list of codes with `0x34` meaning unset, which cannot explain `0x36`; or
bit 1 is the sex and Fitbit also set other bits whose meaning is unknown
(`0x36` is `0x34` with that bit set). Nobody knows which, and nobody has
compared the scale's body-fat figure between them. Send `0x00` or `0x02`;
accept anything when reading a saved Fitbit reply.

**Who is who.** The scale, not your server, decides whose reading it is: a
weight inside a user's window is that user's, anything else is `GUEST` (user
id 0, weight only, no body fat). Fitbit used the last weight minus and plus
4000 g. Keep windows from overlapping.

**A new user has no window, and no rule says what to send.** Nobody knows
what Fitbit sent for a brand-new account. The public servers differ: helvetic
sends a window of 0 to 0 until the user has a stored measurement (what a scale
does with that is not reported); its test server and the PHP server take a
window or a starting weight from the operator; the ESP32 project centres the
window on whatever was just weighed; aria-bridge sends no users at all. With
no window that contains the person, every reading arrives as a guest, and a
server that only learns weights from recognised readings never gets out of
that state. So your server needs a first weight per user from somewhere else:
a starting weight you type in, or a guest reading you assign to the user.

### CRC

CRC-16/XMODEM: polynomial `0x1021`, initial value `0x0000`, no reflection, no
final XOR. The check value for the ASCII text `123456789` is `0x31c3`, which
goes on the wire as `c3 31`. The usual mistake is initial value `0xffff`; a
scale answers `NO SYNC` to that.

### Must, and must never

Your server **must**: answer the three routes above; send `Content-Length` on
the upload reply; answer every well-formed upload with `200`, including one
with zero records (the one exception, for a relay, is under
[Keeping vendor sync](#keeping-vendor-sync-do-nothing-or-a-pass-through-relay));
send the tail words 0, 3, 0 and nothing after the length.

Your server **must never**:

- **Signal a firmware update.** Never put 1 in any tail word, never send a
  tail word other than 0 or 3, and never add bytes to the reply. Never serve
  anything under `/scale/firmware/`. Why is under
  [Firmware: a danger, not a route](#firmware-a-danger-not-a-route).
- **Redirect to HTTPS**, or answer with any 3xx status. The scale is reported
  to ignore redirects and cannot speak TLS. A web server that "helpfully"
  upgrades port 80 breaks it.
- Use chunked encoding on the upload reply, or leave out `Content-Length`.
- Forward uploads to Fitbit unless you chose a relay: everyone who steps on
  the scale, guests included, is in the same request.

### A vector to test against

Synthetic values only (documentation-range MAC `00:00:5e:00:53:01`, invented
auth code, round timestamps); never sent to a scale. A two-record upload,
112 bytes: battery 87 %, firmware 39, scale clock 1800000060; user 1 at
80000 g with 22.5 % body fat at 1800000000; a guest at 61200 g at 1799990000.

```text
030000005700000000005e005301a0a1a2a3a4a5a6a7a8a9aaabacadaeaf27000000210000003cd2496b02000000
02000000f40100008038010000d2496b01000000e45700000000003f3c5a0000
02000000e001000010ef0000f0aa496b00000000000000000000000000000000
771c
```

A reply to it, 104 bytes: time 1800000065, kilograms, one user `ABC` with a
window of 76000 to 84000 g, age 40, male, 1750 mm, tail 0, 3, 0.

```text
41d2496b02320101000000
01000000000000000000000000000000000000004142432020202020202020202020202020202020
e0280100204801002800000002d60600000000000000000000000000000000000000000000
000000000300000000000000
56fe6600
```

`scripts/test_fitbit_aria_wifi_scale_spec.py` rebuilds these and four more
from the spec's own offset tables, byte for byte, with the standard library
only. One of the four has the shape of a Fitbit reply (sex byte `0x36`, real
previous values, tail 0, 0, 0) so that a parser or relay can be tested against
it; it is not something to send. No hardware is involved.

### Firmware: a danger, not a route

There is no firmware route for this scale, and this section is here so that
nobody goes looking for one.

- The update signal is part of the reply to an upload. Whoever answers
  `www.fitbit.com` for the scale can send it.
- On that signal the scale fetches an image over **plain HTTP, with no TLS**,
  from whatever answers `www.fitbit.com` on its network, under
  `/scale/firmware/`. A local server must never answer that path.
- Fitbit's image endpoint was still answering on 2026-11-23: header-only
  requests (no image was fetched) returned 200 for versions 35, 38 and 39 and
  404 for version 33. So a scale told to update could still be handed a real
  image by Fitbit, and anything at all by whoever answers the name.
- **Nobody has built or flashed a modified image** for this scale. The one
  public attempt, in 2015, was abandoned: its authors wrote that the update
  process was well protected and that they ran out of time.
- Nobody has sent the update signal to a real scale from a local server,
  nobody has shown a downgrade, and nobody has shown a way to recover a scale
  from a bad image. Treat a failed update as permanent.
- A pass-through relay changes this exposure, because the scale's image
  request then arrives at the relay: see
  [Keeping vendor sync](#keeping-vendor-sync-do-nothing-or-a-pass-through-relay).

So: never send the signal, never serve the path, never test either on a
scale, and never let a relay hand an update signal on.

### Existing public servers

None was run by this project, and they do not all agree with each other.

| Project | Licence | What it reports | Know before you use it |
|---|---|---|---|
| [helvetic](https://github.com/micolous/helvetic) | AGPL-3.0 | Firmware 35 (author); 37 and 39, one and two users (contributor) | Last commit 2018. Its notes print a wrong reply layout; its code is right. A new user gets a window of 0 to 0 |
| [helvetic ESP32 port](https://github.com/tao-j/helvetic/tree/master/esp32) | AGPL-3.0 (fork) | Firmware 37, in one README line with no log: an ESP32 is the access point, DNS and server | An unreviewed fork. Sets the display to pounds; one user; needs a hand-made library patch |
| [aria-bridge](https://github.com/ty-machine/aria-bridge) | MIT | FB201B, firmware 39, 2026; includes a setup script that copes with the malformed reply | No validate route; zero users; its reply tail differs from the layout above; it does not show the scale joining after setup |
| [fitbit-aria-php-server](https://github.com/m322345/fitbit-aria-php-server) | GPL-3.0 | 2026; multiple users with starting weights; checks the request CRC | No hardware statement; no validate route; no local setup step |
| [aria-spoof](https://github.com/ads04r/aria-spoof) | Unlicense | Firmware 39, 2018 | A relay to Fitbit, not a replacement |
| [aria2mqtt](https://github.com/bigbadbob2003/aria2mqtt) | MIT | 2024; firmware not stated | A relay to Fitbit that also publishes to MQTT. Not for the Aria 2, despite the name |

## Other local routes

Every route anyone has proposed, with how well it is evidenced. "Pairing
impact" keeps two things apart: what the scale stores (network, token, users)
and the link between scale and Fitbit account, which cannot be recreated any
more. Ratings follow a second, sceptical read of every source; where it was
more cautious than the first, the cautious rating is printed.

| Route | Evidence | Needs | Brick risk | Pairing impact |
|---|---|---|---|---|
| **DNS redirect + LAN server** (primary) | Shown by third parties on firmware 35 and 39; reported on 37 | A resolver you control; a server on port 80 | None | No setup mode: network and token untouched. Your reply replaces unit and users |
| **Pass-through relay** (to keep vendor sync) | Shown: a 2024 write-up (firmware not stated) and a 2024 container | The redirect, a small relay, Fitbit's current address | None while no update signal is handed on; **unknown** if one is (see [the relay's limits](#keeping-vendor-sync-do-nothing-or-a-pass-through-relay)) | None: network and token untouched; users, unit and clock stay Fitbit's |
| **Same network name and passphrase** on new hardware | Inferred; nobody has tried it in public | An access point with the old name, passphrase, security mode and 802.11b | None | None if it works; nothing lost if not |
| **Direct setup request** | Shown on firmware 35; one README line for 37; 200 but no join shown on 39; no success on 38 | A battery re-insert and a deliberate press; a second computer; redirect and server ready | None | **One-way.** New token; stored network reset; vendor link lost for good |
| Redirect variant: **per-device DHCP resolver** | Inferred; cheap to test | A DHCP server with per-client options | None | None |
| Redirect variant: **destination NAT** at a gateway | Inferred; nobody has published it for this scale | A gateway that can rewrite port-80 traffic | None | None |
| Redirect variant: **dedicated access point or travel router** | Inferred: pieces demonstrated, bundle not published | An access point with 802.11b and its own resolver | None | As direct setup, unless the old network is recreated |
| Redirect variant: **all-in-one ESP32** | Author-reported on firmware 37, one line, no log | Building the project, with a hand-made library patch | None | As direct setup, unless the old network is recreated. Sets pounds; one user |
| **Plain scale** | Vendor-documented | Nothing | None | None. Weight only; body fat only while a stored window still fits |
| **Internal serial console** | Shown on firmware 39 by two people | Opening the case; wires into bare header holes; an adapter at a level nobody has published | **Unknown** | None if only reading; each cold boot opens `TAP TO CHANGE` |
| **Listen-only logger** on the console | Inferred. Nobody has built it | Opening the case; battery or isolated power; a series resistor on the input; the line's level measured first; never left attached unpowered | None (inferred) | None |
| **Load-cell retrofit** | Inferred; done on other scales, never on an Aria | Opening the case, soldering, calibration | Recoverable (inferred) | Abandons the product |

About the last three, which are research notes, not owner procedures:

- **Diagnostics only: the serial console.** It prints the firmware version,
  a self-test, the stored users and network name and each weigh-in. It cannot
  redirect the scale: no known command sets the Wi-Fi details, the server name
  or the DNS server. The signal level and the voltage on its supply pad are
  published nowhere, and the Wi-Fi module's limit is 4.0 V, so an adapter with
  a powered supply wire, or 5 V logic, can destroy it. Its list also names
  commands that write or erase identity, factory and calibration data; none
  has been shown running in public, so do not run them.
- **Never stand on the scale while it is wired to mains-powered equipment.**
  The glass passes a small signal through bare feet and the scale is isolated
  only because it runs on batteries. A cable to a laptop on its charger
  removes that. Battery power or galvanic isolation only.
- **The retrofit is a last resort** for a dead board or a parts donor. It
  gives a plain scale in the Aria's body: no display, no users, no body fat.

What is **not** a route, one line each:

- **No Bluetooth.** The FB201 has none; that is the Aria 2 and Aria Air.
- **Connecting to the scale on your network:** never tested. No inbound
  service has ever been observed, and nobody has published a scan.
- **The setup network** is a provisioning hook only, not a data or debug
  channel.
- **The scale's own setup page alone in a browser:** served, but nobody has
  shown it completing a setup without Fitbit's site.
- **A phone app for setup:** none exists.
- **Console commands that change state:** listed, never shown running.
- **The Wi-Fi module's wired download mode:** documented by the module's
  maker, never used on an Aria; that flow starts with a full erase and no Aria
  image exists to put back, so any erase is permanent.
- **JTAG:** on the chip on paper; never used on an Aria, and any erase is
  permanent.
- **Tapping the internal bus:** nobody has, and nothing about it is published.
- **Modified firmware:** see
  [Firmware: a danger, not a route](#firmware-a-danger-not-a-route).

## Security and safety

- **Setup mode is an open Wi-Fi network** and your passphrase crosses it in
  clear text. A 2015 write-up also found a page on that network that handed
  back the stored passphrase; whether newer firmware still does is not known.
  Anyone who can pull a battery and press two corners can put the scale in
  setup mode.
- **Uploads are plain HTTP with no authentication.** Whatever answers
  `www.fitbit.com` for the scale gets the readings and controls its clock,
  users and update signal. Keep the server on a network you trust and never
  expose it to the internet.
- **No security updates since 2020.** The newest firmware anyone has seen was
  built in February 2016. A DNS weakness Fitbit patched in 2016 is visible in
  the 2016 captures of a scale still on firmware 37. A network name and
  passphrase of its own limits what the scale can expose, but **do not move a
  working scale to another network for this**: that needs setup mode, the
  one-way door. To isolate a working scale, leave its present network name
  and passphrase exactly as they are and move your other devices to a new
  one, or do it when the scale has to go through setup anyway.
- **Before the scale leaves the house.** No way to clear the stored
  passphrase or users is established, and a battery pull is not a wipe. The
  remedy is on your side: change the passphrase of the network it knew. That
  also cuts off every other device that knows it, and an Aria that stays
  would then need setup mode. Removing the scale from your Fitbit account
  cannot be undone.
- **Bioimpedance.** The body-fat measurement sends a small electrical signal
  through bare feet. The manual says: do not use with a pacemaker or any other
  internal medical device; do not use when pregnant; not intended for children
  under 10. That applies whoever's server the scale talks to. The body-fat
  figure is computed inside the scale from the age, sex and height your server
  supplies; it is not a medical measurement.
- **Other people's data.** Guests are uploaded too, as user 0, weight only.

## Help close the unknowns

Every open question is listed in the spec's `remaining_unknowns`, each with
the cheapest experiment that would settle it. The ones that matter most to
other owners:

1. Does a battery re-insert on firmware **38 or 39** keep the Wi-Fi key? On a
   scale that already talks to a local server, next to its router: pull a
   battery, do not press, weigh, look for an upload. **The risk:** if the key
   does not survive, the scale is off Wi-Fi, and the only way back is the
   direct setup, which is unproven on these versions. Do it when the batteries
   need changing anyway, or on a scale you can afford to lose from Wi-Fi, and
   never on a scale whose vendor sync matters. And, **only on a spare
   scale**: does reaching `SETUP ACTIVE` erase the stored network at once?
2. Does a freshly set-up scale on firmware **35, 38 or 39** complete register,
   validate and a first upload against a local server? Spare scale only.
3. Will the scale rejoin a different access point that has the same network
   name and passphrase?
4. What does the scale do with a user whose window is 0 to 0?
5. Is the tail 0, 0, 0 accepted from a local server? (Never try 1.)
6. If you run a relay: what do Fitbit's replies look like today, and on what
   date do they stop?

Anything that needs setup mode is a one-way door: use a spare scale, or one
whose stored network and vendor sync no longer matter.

**What to capture:** every request and reply with a timestamp (request line,
headers, body as hex), which connection each arrived on, the firmware number
shown at power-up, and what the display said after each exchange.

**Scrub before you share:** the MAC (bytes 8 to 13 of the upload, the
`serialNumber` parameter, the six characters of the `Aria XXXXXX` name and of
the `GainSpan` host name); the auth code (bytes 14 to 29); the token; your
network name and passphrase; user ids, names and profile values. Use
`00:00:5e:00:53:01` for the MAC, recompute the CRC after editing bytes, and
say that you did.

**Do not share the scale's own setup page or script files**, or a firmware
image: they are the vendor's code and this project cannot accept them. Report
what the page and its scripts do in your own words: paths, parameter names,
header names, sizes.

**Never** test the firmware-update form on a scale, do not send test traffic
to Fitbit with a real serial, and do not weigh on a scale that is wired to
mains-powered equipment.

## Tools Used

- [ ] No hardware, account or firmware image was used by this project, and it made no capture of its own
- [x] Public write-ups and open-source servers, read as text (facts only; several are AGPL/GPL)
- [x] A public 2016 capture set, read with this project's own parser; cited, never committed
- [x] FCC filing XRAFB201A and the vendor manual, read on 2026-11-23
- [x] Parameterless and header-only web requests to the vendor's public endpoints on 2026-11-23 and 2026-11-24

## References

Manuals, all checked on 2026-11-24:

- [Aria Product Manual Rev C (PDF, vendor-hosted)](https://staticcs.fitbit.com/content/assets/help/manuals/manual_aria_en_US.pdf)
  for FB201B and FB201W. Its setup chapter relies on the dead web page.
- [The same manual at the Internet Archive](https://web.archive.org/web/20260427164741/https://staticcs.fitbit.com/content/assets/help/manuals/manual_aria_en_US.pdf),
  for the day the vendor copy goes. The Archive's index listed this snapshot
  on 2026-11-24; the file itself was not opened, because the Archive is
  blocked from this project's build environment.
- [14-page manual on manua.ls](https://www.manua.ls/fitbit/aria/manual) and the
  [older 19-page edition on manualsdir](https://www.manualsdir.com/manuals/601834/fitbit-aria.html),
  both for the original Aria.
- Google Health help:
  [using the scale](https://support.google.com/googlehealth/answer/14236805)
  (the notice that pairing has ended, display messages; **do not follow its
  reconnect steps for this model**: they begin with the corner press, the
  one-way door, and end at the dead web page),
  [setup requirements](https://support.google.com/googlehealth/answer/14236818),
  [erase](https://support.google.com/googlehealth/answer/14236515),
  [export your data](https://support.google.com/googlehealth/answer/14236615).

Protocol sources:

- [helvetic protocol notes](https://github.com/micolous/helvetic/blob/master/protocol.md)
  (request side; do not use its reply structures)
- Pen Test Partners, 2015:
  [setup mode](https://www.pentestpartners.com/security-blog/are-your-smart-weighing-scales-lying-to-you-quite-possibly-part-1/),
  [upload protocol](https://www.pentestpartners.com/security-blog/are-your-smart-weighing-scales-lying-to-you-quite-possibly-part-2/),
  [passphrase disclosure and the abandoned firmware attempt](https://www.pentestpartners.com/security-blog/extracting-your-wpa-psk-from-bathroom-scales/)
- The public 2016 capture set: described in the
  [IoT Sentinel paper](https://arxiv.org/abs/1611.04880) (dataset "available
  on request for research use") and mirrored in a
  [public repository](https://github.com/andypitcher/IoT_Sentinel). Twenty
  setups of one original Aria on firmware 37 against Fitbit's server. The
  files hold a real MAC, tokens and an account id: read them for facts, do not
  pass them on, and never copy an identifier out of them. None is in this
  repository.
- [Hackerspace Bamberg, 2012](https://www.hackerspace-bamberg.de/projekte/fitbit-aria-wi-fi-smart-scale/)
  (the older protocol version 2; historical)
- [Wayne Piekarski, 2024](https://www.waynepiekarski.net/blog/2024/12/fitbit-mitm.htm)
  (pass-through relay behind a DNS redirect)
- [Teardown and serial logs](https://pooloferrors.com/project/2015/01/10/fitbit-teardown.html)
  (read the console warnings above before copying its wiring)
- [FCC ID XRAFB201A](https://fccid.io/XRAFB201A)
- [The Register, 2016](https://www.theregister.com/2016/04/29/fitbit_aria_scales_security_flaw/)
  (the DNS fix)

Related pages here: [Keeping Devices Alive](../keeping-devices-alive.md),
[Blocking Updates & the Cloud](../blocking-vendor-updates.md),
[Firmware Update](../protocols/firmware-update.md).

## Contributors

- Research consolidated 2026-11-23 and revised 2026-11-24 from the public
  sources above; no hardware verification yet. If you run any of the
  experiments, your scrubbed logs are the contribution this page needs most.
