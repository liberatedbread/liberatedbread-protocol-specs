# Fitbit Aria Air (FB203)

> **Status**: Spec Available (untested; reported facts only)
> **Protocol**: BLE GATT, AES-128-CCM encrypted weigh-in indications
> **Manufacturer**: Fitbit (Google)
> **Manufacturer Status**: Active. Still sold, and not part of the change that ended Aria / Aria 2 pairing (dated 2026-11-09 by Google's current English notice)
> **Integration**: Identify-only. Reading a weight needs the scale's 16-byte key and a dedicated AES-CCM handler

## Overview

The Aria Air is Fitbit's Bluetooth-only bathroom scale: weight and nothing
else, no Wi-Fi, no body-fat measurement. The Google Health app (the renamed
Fitbit app) works out BMI from the weight.

!!! tip "If your Aria Air works today, the safest thing to do is nothing"
    The scale is not part of the Aria / Aria 2 change, it still syncs with
    the vendor app, and it shows your weight on its own display with no app
    at all. **Both** ways of getting the key that this page describes
    **begin by removing the scale from your account and factory-resetting
    it.** That ends the pairing you have now, and getting one back depends on
    the vendor app completing a fresh setup. Nothing here is a reason to
    unpair or reset a scale that works.

**Which Aria is this?** Turn the scale over and count the batteries. Three
AAA cells: Aria Air, this page. Three AA cells and "Aria 2" printed on the
underside: Aria 2 (FB202). Four AA cells: the original Aria, see
[Fitbit Aria Wi-Fi Smart Scale (FB201)](fitbit-aria-wifi-scale.md). The
reassurance on this page applies to the Aria Air **only**. For a scale that
takes AA cells, pairing and re-pairing have already ended by Google's current
notice: one that is unpaired cannot be paired again, so leave a working one
paired and do not reset it.

Three things to know before anything else:

- **It is not part of the Aria / Aria 2 change.** By Google's English notice
  as read on 2026-11-24, pairing and re-pairing of the Aria (FB201) and Aria 2
  (FB202) ended on 9 November 2026 with app version 5.12. The same notice
  says "Aria Air is not impacted by this change", and the scale was still on
  sale that day. One observation about the source: the notice read 28
  November 2026 when fetched at 05:11 UTC on 2026-11-23, and 9 November 2026
  by 23:07 UTC the same day and in every fetch since; only the day changed.
  The German, French and Japanese editions still said 28 November at 01:02
  UTC on 2026-11-24. This page follows the English text: for an Aria or
  Aria 2, pairing and re-pairing have already ended.
- **It depends on the vendor app all the same.** Setup happens only in the
  app, the app has to be open on a nearby phone during every weigh-in, and the
  key that decrypts the scale's readings is normally known only to the app.
  That dependency is why the scale is in this catalogue. "Not impacted" is a
  statement about one change, on a page that changed within a day; it is not
  a promise about the future.
- **Nothing on this page was run on hardware by this project.** The facts come
  from one public implementation, one independent capture in an openScale
  issue, the vendor manual and help pages, and the FCC record. Two questions
  are open and are marked wherever they matter: the scale factor in
  kilograms, and whether an owner can give the scale a key without the vendor
  app.

The machine-readable spec is
[`fitbit-aria-air.yaml`](https://github.com/liberatedbread/liberatedbread-protocol-specs/blob/main/device-specs/devices/fitbit-aria-air.yaml).
`scripts/test_fitbit_aria_air_spec.py` reproduces its synthetic test vectors
with two independent AES-CCM implementations and pins what the spec is allowed
to claim.

## What an owner can do, cheapest first

The first three change nothing on the scale and leave the pairing alone. The
first two cost nothing at all; the third can cost the weigh-in it connects
during. The last two end the vendor pairing before they give anything back.

| | What | What it gives | What it costs | Evidence |
|---|---|---|---|---|
| 1 | **Leave it paired and keep using it** | Weight on the display; vendor sync for as long as the vendor keeps it working | Nothing | Vendor documentation |
| 2 | **Read the display with a phone camera** ([SmarterScale](https://github.com/drinkcat/SmarterScale), Apache-2.0) | The displayed weight written to Android Health Connect. No Bluetooth link to the scale, no key | Nothing to the scale. One manual step per weigh-in | Its author reports testing it on an Aria Air, and on nothing else |
| 3 | **Connect and read what is in the clear** | Identification, firmware string, whether the scale has a key, a step-on flag. Never the weight | Nothing to the scale or the pairing. But the scale accepts a connection only during a weigh-in and serves one client at a time, so a weigh-in made while a local client is connected may never reach the vendor app | Two parties for the name, service, characteristic, indication and length; one for the rest |
| 4 | **Route 1: capture the key the vendor app writes** | Local reads with the same key the app holds | **The present pairing**, at the first step. Then it depends on the app completing a fresh setup | One party, on hardware `H01` / firmware `A16`; not reproduced end to end |
| 5 | **Route 2: reset and write your own key** | A key you chose, nothing needed from the vendor, if the report holds | **The vendor pairing.** Going back means another reset and a fresh in-app setup | One report, reproduced by nobody |

About the camera app in row 2: it reads the seven-segment digits through the
camera and stores the number locally. By its own README it handles kilograms
only, assumes where the decimal point is, and is installed from the project's
release page, not from an app store. It was written by the person who posted
the January 2025 capture in openScale issue 1105. This project has not run or
reviewed it.

If a paired scale stops syncing, start with the first steps of the vendor's
own [sync troubleshooting](https://support.google.com/googlehealth/answer/14236618):
app open nearby, force quit and reopen the app, restart Bluetooth, restart
the phone. Its later steps reinstall the app and sign in on another phone.
That is the vendor's advice, but where the key is kept is not established
(Q11 in the spec), so this page cannot say what a reinstall does to it: try
the earlier steps first. None of its Aria Air steps removes the scale itself
from the account or resets it. Do neither.

**New phone?** Sign in to the same account on the new phone and weigh in
with the vendor app open there. Changing phone is not a reason to reset the
scale or to remove it from the account; see
[Rebinding](#rebinding-to-a-new-phone-or-network).

## What a third-party client can and cannot do today

| | Status |
|---|---|
| Find the scale and tell it apart from a standard Bluetooth scale | Yes. It advertises the name `Aria Air` |
| Connect and subscribe without pairing | Reported yes. The link is open; the data is encrypted |
| Read a weigh-in **with** the scale's key, display in pounds | Reported yes. One public implementation says decoded values matched its scale's display but does not say which unit that was (pounds is this project's inference); one later, unreplicated comment gives the pounds rule |
| Read a weigh-in with the key, display in kilograms | Decrypts, but the scale factor is disputed. See [the kilogram conflict](#the-kilogram-conflict) |
| Read a weigh-in **without** the key | No. The 19 bytes are ciphertext with an 8-byte authentication tag |
| Get the key from the scale | No. It cannot be read back |
| Get the key without ending the present pairing | **No known way.** Both routes start with a reset |
| Get the key by watching the vendor app set the scale up | Reported yes by one party, from the owner's own Android Bluetooth log, after removing and resetting the scale |
| Give a reset scale a key of your own, no vendor app | **One report, reproduced by nobody, says yes.** Treat as an experiment |
| Read weigh-ins made while nothing was connected | Not known to be stored at all |
| Battery level, weigh-in time, body fat | Not available over Bluetooth |
| Redirect the scale to a server of your own | Does not apply: no Wi-Fi, and the scale never talks to a server |

## Hardware

| Property | Value |
|----------|-------|
| Model Number | FB203 |
| Chipset | Telink `TLSR8261` (marking `F512ET32`) on a Transtek radio module (read from the 2020 FCC internal photos; reported) |
| Radio | Bluetooth LE only, 2402-2480 MHz. A 2020 change lowered the transmit power in software, so expect short range |
| FCC ID | XRAFB203 (ISED 8542A-FB203) |
| Power | 3 AAA cells |
| Capacity / division | 180 kg (397 lb, 28 st 5 lb) / 100 g |
| Display units | Pounds, stones, kilograms. Tap the back button to cycle |
| Category / hierarchy | `scale` + `["measurement", "health", "other"]` (weight only) |
| Aliases | Fitbit Aria Air, Aria Air |
| Distributors | Fitbit (brand), Google LLC (manufacturer of record and seller), Zhongshan Transtek Electronics (factory named in the FCC report) |
| Companion apps | Google Health, the renamed Fitbit app |

**Manuals.** Both vendor copies returned a PDF on 2026-11-24 and cover the
Aria Air only:

- [Aria Air User Manual, version 1.8](https://storage.googleapis.com/support-kms-prod/tstfwA3ivox007uvXqN4xtTKSmowts0Gzuxj)
  (the copy the vendor's manuals page links to)
- [Aria Air User Manual, version 1.1](https://staticcs.fitbit.com/content/assets/help/manuals/manual_aria_air_en_US.pdf)
  (PDF dated 2020-01-03; same restart procedure)
- [Aggregator copy on manua.ls](https://www.manua.ls/fitbit/aria-air/manual), as a fallback
- Vendor help covering all three Aria scales:
  [How do I use my Fitbit scale?](https://support.google.com/googlehealth/answer/14236805)
  (carries the pairing notice),
  [Set up your Fitbit device](https://support.google.com/googlehealth/answer/14236818)
  and
  [How do I erase my Fitbit device?](https://support.google.com/googlehealth/answer/14236515)
  (one line for the Aria Air: it holds no personal data)

The FCC report names a factory that carries the Transtek name, and openScale
puts that name on its Trisa and 1BODY handlers. The Aria Air does **not**
speak that family's protocol: none of those services, characteristics or
challenge exchanges is reported on it, so no existing handler carries over.
Whether the shared name means one company, let alone one plant, is not
established.

**Inside the case: research notes, not instructions.** The vendor manual says
the scale is not serviceable, the top is one piece of glass with no visible
fasteners, and nobody has published a teardown. What the FCC photographs
show: the Telink chip sits on a small Transtek module (`LS8261-512`) whose
underside, the face soldered against the main board, carries pads labelled
`VDD`, `GND`, `SWS`, `RXD` and `TXD`. Nobody has reported connecting to them,
and no public programmer lists this chip as tested. The main board also has a
separate unmarked controller, one empty 8-pad footprint, four three-wire load
cells and further pads labelled `DOWN`, `SET`, `UP` and `UNIT` whose function
nobody has documented: do not bridge them. (One reading of the photograph,
not an established fact, is that `UNIT` is the back-button line; if so,
bridging it could act as holding the button that starts the reset.) This
page gives no wiring or
flashing procedure. Any erase or write to the chip made without a verified
dump of that same unit could not be undone, because no firmware image for
this scale is public.

## Initial Setup

| Property | Value |
|----------|-------|
| Setup required | Yes, for a third-party client: it can read weigh-ins only with the 16-byte key the scale was given at setup. A scale that already works with the vendor app needs nothing |
| Method | `cloud_account` then `ble_direct` (vendor app writes the key, owner captures it); or `ble_provisioning` (write your own key; one unreplicated report). Both are `verified: false` and marked advanced |
| Setup AP / advertised name | `Aria Air` |
| Passphrase protection | not_applicable (no Wi-Fi) |
| Confidence | low. Nothing replayed here, and the vendor-free route rests on one report |

### The key problem, in plain words

Every weigh-in the scale sends is locked with a 16-byte key. The scale gets
that key once, at setup: the client doing the setup reads a status byte, sees
that the scale has no key, and writes 16 bytes to it. From then on the scale
locks every reading with those 16 bytes.

In normal use the client doing the setup is the vendor app, so the vendor app
is the only thing that knows the key. The scale will not tell anyone else: the
key cannot be read back. An owner who wants to read their own scale has to
either **watch the app write the key** or **write a key themselves**, and
either way the scale has to be reset first.

The key is sent in clear over an unencrypted Bluetooth link. That is why the
owner's own phone log contains it. It is also why anyone else recording that
moment has it, and anyone holding it within radio range can read the
weigh-ins until the next reset.

### Before either route: what it costs

!!! danger "Both routes end the pairing you have"
    Route 1 and Route 2 each start with a factory reset, and Route 1 first
    removes the scale from your account. From that moment the vendor app no
    longer shows your weigh-ins. Getting the pairing back means a fresh
    setup in the vendor app, and in-app setup of this scale has a public
    history of failing: a Fitbit Community thread titled "'Something went
    wrong' during Aria Air setup" ran past twenty pages (seen only as
    search-result titles; the thread now redirects). If the setup does not
    complete you are left with **a scale that is unpaired and an app that
    will not re-pair it**. The scale's firmware is not at risk in that
    state, but nothing reads the scale until a setup succeeds.

The one free moment to record a key is a setup that is happening anyway: a
new scale, or one that is already unpaired. Turn the phone's Bluetooth log on
before that setup starts.

### Route 1: let the vendor app set the key and capture it from your phone's log

Who has done it: the author of the one public implementation reports taking
the key from the Bluetooth HCI snoop log of an Android phone, recorded while
the vendor app was setting the scale up (hardware `H01`, firmware `A16`, the
vendor app as it was in October 2026), and publishes a parser for such logs.
A second person saw the 16-byte write itself in April 2025 and guessed,
without confirming, that it was a key being set up. Nobody else has reported
the route end to end, and nobody has reported it against the app released as
version 5.12. Not run by this project.

What you need: an Android phone, and a way to take an Android bug report off
it. The source makes the bug report with the `adb` tool from a computer and
gives the log's place inside the report archive as
`FS/data/misc/bluetooth/logs/btsnoop_hci.log`. This project has not checked
that on any phone, which is one reason for the dry run in step 3.

What you end up with: a local client that holds the same key as the app. The
same key serves both, but the scale serves one client at a time, so each
weigh-in goes to whichever is connected. Nobody has reported what the app
shows after a local client has taken a reading.

1. **Decide first.** Steps 4 and 5 end the pairing you have (see the warning
   above). Doing nothing keeps a working scale working.
2. On the Android phone, turn on Developer options and enable the Bluetooth
   HCI snoop log in its full form. Switch Bluetooth off and on.
3. **Dry run, before anything is removed.** With the log on and the vendor
   app open, do one normal weigh-in. Take the log off the phone as in step 6
   (keep it just as private, but leave the log switched on) and check that
   it holds the scale's traffic: at least one indication with a 19-byte
   value. **Go on only when that works.** If the log cannot be exported, or
   holds no such indication, stop: the pairing is intact and nothing has
   been lost. The dry run shows that the phone records and the log can be
   exported; it does not show that the app will write the key in clear at
   the coming setup, nor that the setup will complete. It is this project's
   addition to the published procedure.
4. Remove the scale from the vendor app. **This ends the present pairing.**
5. Reset the scale ([below](#factory-reset)), then set it up in the app
   again. If the setup completes, the app has written a fresh key. If it
   does not, retry the setup in the app; the scale stays unpaired until one
   succeeds.
6. Take the Bluetooth log off the phone (the source does it inside an
   Android bug report, as above). Keep it private and never upload it: it
   holds the key and everything else the phone did over Bluetooth while it
   was recording, and the bug report holds far more than that. Switch the
   log off again.
7. In the log, find the phone-to-scale write of exactly 16 bytes to
   characteristic `26f33a01-52a8-414b-99a2-1db75c99c032`. Those bytes are the
   key. If there are several, the latest setup is the one in force.
8. Store the key like a password. Close the vendor app, step on the scale and
   check that a weigh-in decrypts.

An owner who already holds a Bluetooth log from a previous setup can skip to
step 7 with no reset at all, provided the scale has not been set up again
since. Whether the app ever sends the key again without a reset (a second
phone, a reinstall) is not known; the vendor's troubleshooting suggests
signing in on another phone and syncing there, which would fit a key the
account holds, but nobody has shown where the key is kept.

### Route 2: reset and write your own key (one unreplicated report)

!!! warning "Experiment, not procedure"
    One comment in openScale issue 1105 (2026-10-26) reports that after a
    factory reset the scale accepts a 16-byte key written by any client, and
    that weigh-ins then decrypt with that key: one unit, twelve weigh-ins
    matching the display, no vendor account. The poster introduces the
    comment as findings an AI assistant produced; it does not state the
    firmware, names no tool and links no repository or capture. The only
    code in it is a four-line fragment that decodes a message, with nothing
    for the key write. Nobody has repeated it, and the research behind this
    page could read the comment only through a summarising tool.

    **It ends the vendor pairing.** The app is left holding a key the scale
    no longer uses, and can be expected to show nothing until the scale is
    reset and set up in the app again. **Record the key before you write it**: it cannot be read
    back, and a scale keyed with a value nobody holds is unreadable until it
    is reset again. If weigh-ins do not decrypt afterwards, reset again.

The steps are in the spec (`device.setup.methods`, second entry), as the GATT
operations the report describes; no tool recipe exists to give. Reset; store
16 random bytes somewhere safe **before** writing them; step on the scale;
connect; read the status and continue only if it reads `00`; write the 16
bytes with response; read the status again and expect `01`; subscribe, weigh,
decrypt and compare with the display. If you try it, please report the result
with the firmware string from Device Information.

### Factory reset

**What it costs:** a reset ends the scale's current setup. The vendor app and
every other client lose the scale until it is set up again, and the only way
to do that which more than one party has observed is the vendor app. Do not
reset as casual troubleshooting, and never because a local client received
nothing (that is a subscription problem, not a key problem).

**How** (vendor manual, both editions; not run by this project). Find the
single button on the underside of the scale. Press it and keep it held:
after 5 seconds `otA` flashes on the display, and after about 5 more the
display changes to `clr`. The manual files this under restarting the scale
and says the scale is then reset. It words the two stages as two 5-second
holds and does not say whether to release in between; if one continuous hold
does not reach `clr`, hold 5 seconds, then hold again for 5 seconds.

**About `otA`:** neither the manual nor any other public source says what
that state is, what the scale does on the air while it shows, or what
releasing the button there leaves behind. So do not start the hold unless you
mean to reset (a short tap of the same button only changes the unit), and
once you are resetting, keep holding until `clr`.

What the reset does, as reported: the scale's status goes back to "no key",
and the next setup gives it a new key. What the scale sends in between is
not reported by anyone, so **assume a reset scale is useless to every client,
the vendor app included, until it is given a key again.** If you are about to
reset anyway, turn the phone's Bluetooth log on first.

The vendor's erase article says the Aria Air holds no personal data. One
unreplicated report says the key survives a battery change.

### Rebinding to a new phone or network

**Changing phone is not a reason to reset.** There is no network to rejoin:
the scale holds no Wi-Fi or account credentials, so a new router or a house
move changes nothing.

- **Vendor app on a new phone.** Sign in to the same account on the new
  phone and weigh in with the app open there, with the old phone away from
  the scale or its Bluetooth off. The vendor's
  [sync troubleshooting](https://support.google.com/googlehealth/answer/14236618)
  describes signing in on another phone or tablet and syncing from that one,
  with no setup step mentioned. **Do not remove the scale from the account
  and do not reset it.** Not tested by this project; how the key reaches the
  new phone is not established (Q11, experiment E7).
- **Local client on a new phone, computer or Bluetooth proxy.** It needs
  only the key, carried over by the owner, and no reset. If you do not hold
  the key, there is no reported way to obtain it without a reset, and a
  reset ends the vendor pairing ([what it costs](#factory-reset)). An owner
  without the key loses nothing by staying with the vendor app.

## Pairing

| Property | Value |
|----------|-------|
| Pairing required | Yes — not a Bluetooth pairing: the gate is the scale's 16-byte key |
| Security mode | `app_layer` |
| Bonding | `none` |
| PIN source | `vendor_app` (a 16-byte key the app writes at setup, never shown to the owner) |
| One central at a time | Yes (reported). While a client is connected the scale is absent from scans |
| One bond at a time | No bond exists. The scale holds one key; every client must hold that same key |
| Confidence | medium (public implementation plus an independent capture; not run here) |

**Entering pairing mode**: nothing to press. The name is always on the air,
but a connection only succeeds while someone is on the platform. Expect
several refused attempts in the first seconds after stepping on, and a
dropped connection within about a second if the scale is asleep.

**Unpairing**: the only reported way to clear the key is the factory reset,
with the cost described above. Whether the scale would accept a new key while
it already has one is unknown.

**Recovery**: close the vendor app on every nearby phone, or switch that
phone's Bluetooth off, and step on again. A scale that has vanished from a
scan is usually connected to something else. A local client should disconnect
as soon as it has the reading, so that it does not keep the vendor app out.

See [Pairing, Bonding and Unpairing](../protocols/pairing.md) for the
vocabulary.

## Protocol Summary

Everything in this section is `reported`: restated from the public
implementation (one unit, firmware `A16`, hardware `H01`) and the independent
capture, not confirmed by this project.

### Identification

Match on the exact advertised name **`Aria Air`**. Do not match on either of
the other two signals:

- The scale advertises the standard Weight Scale service
  `0000181d-0000-1000-8000-00805f9b34fb`, as unrelated standard scales do. A
  client that selects scales by that service alone will claim an Aria Air and
  then get nothing from it.
- It also sends manufacturer data under company identifier `0x018e`, which is
  assigned to Google LLC and is not specific to this product. The record is
  8 bytes after the identifier: one byte reported as `00`, one byte that is
  `1` while someone is on the platform and `0` otherwise, then the scale's own
  6-byte address (byte order not stated). One source describes this record,
  and it places it in the scan response while hedging the claim. If that is
  right, only an **active** scan receives the step-on flag, and a scanner that
  active-scans in short bursts can miss it. Use the flag to decide *when* to
  connect, not *what* the device is.

After connecting, confirm: Device Information model number reads `FB203`; the
vendor characteristic below is present; and the standard Weight Measurement
characteristic `00002a9d-0000-1000-8000-00805f9b34fb` is **absent**.

### BLE Services

| UUID | Name | Description |
|------|------|-------------|
| `0000180a-0000-1000-8000-00805f9b34fb` | Device Information | Manufacturer `Fitbit`, model `FB203`, hardware `H01`, firmware `A16`. The serial number embeds the scale's address: never publish it |
| `0000181d-0000-1000-8000-00805f9b34fb` | Weight Scale (shell) | Holds the vendor characteristic and a Weight Scale Feature that reads zero. No standard measurement characteristic |
| `67b0ab2c-8323-427a-b1c9-70324bb5e228` | Encrypted weigh-in (characteristic) | Indicate. One 19-byte message per reading |
| `26f33a00-52a8-414b-99a2-1db75c99c032` | Provisioning (vendor) | |
| `26f33a01-52a8-414b-99a2-1db75c99c032` | Provision status / key (characteristic) | Read: `00` no key, `01` has a key. Write: the 16-byte key, at setup only |
| `00001530-1212-efde-1523-785feabcd123` | Off limits: firmware update | **Do not write to anything in this service. Recovery: none known.** Present in the one published listing (one unit). The UUID is the one Nordic's legacy DFU uses, on a Telink radio; what runs behind it, and whether it checks anything, is unknown, and no Nordic default is assumed |

### Receiving a weigh-in

1. Wait for the scale to wake (the awake byte in the manufacturer data reads
   `1`). Without that signal, the source's attended reader, a tool a person
   starts while stepping on, retries the connection every 0.4 s for up to
   3 minutes; its unattended integration tries every 15 s instead, and only
   as an option. Do not run the 0.4 s cadence in an always-on client.
2. Connect. No pairing.
3. Read `26f33a01-52a8-414b-99a2-1db75c99c032`. `01` means the scale has a
   key; `00` means it was reset and has none (what it sends then is not
   reported; assume nothing can be decrypted).
4. Enable the stream on `67b0ab2c-8323-427a-b1c9-70324bb5e228` by writing
   `01 00` to its Client Characteristic Configuration descriptor.
5. Messages arrive as **indications**. Confirm each one.
6. Reported timing: the first message follows the subscription by a few
   seconds, and the same reading tends to be sent a second time. The source
   also saw unexplained messages carrying different values. Disconnect once
   the reading is in: the scale serves one client at a time.

!!! warning "The descriptor value is a trap"
    The characteristic declares *indicate* only, so a standards-following
    stack writes `02 00`. The vendor app writes `01 00`, and the scale is
    reported to respond to that value with indications. The source says a
    client writing `02 00` may get no messages at all. BlueZ picks the value
    itself and refuses a direct descriptor write, so whether its own GATT
    client (and Bleak on top of it) can open the stream is not established;
    the public implementation's Linux tool sidesteps the question with a raw
    ATT write. Apple hosts are an unknown of the same kind: by Apple's
    documentation an app cannot write this descriptor and the stack picks
    the value. Yet the vendor offers its app for iPhone, so either `02 00`
    does work or the characteristic declares more than the one public
    listing shows; nobody has looked. Bluetooth proxies: the source lists an
    ESPHome proxy as a supported host and reports that proxies often miss
    the wake flag, but shows no session through one, nor which descriptor
    value reaches the scale that way.

    The trap bites after either setup route. A correct key can still be
    followed by silence, and silence says nothing about the key: a wrong key
    shows up as messages whose tag fails. Never reset a scale because nothing
    arrived.

### Message layout

A message is always 19 bytes, laid out on the wire as:

| Offset | Length | Description |
|--------|--------|-------------|
| 0 | 8 | Nonce. Use exactly as received |
| 8 | 8 | AES-CCM authentication tag |
| 16 | 3 | Ciphertext |

Open it with **AES-128-CCM**: 16-byte key, the 8-byte nonce, 8-byte tag, no
associated data. The tag comes *before* the ciphertext on the wire; most
libraries want the ciphertext first and the tag appended, so reorder before
calling them. A message that is not 19 bytes, or whose tag does not verify,
is not a reading. A tag failure means the key is not the one the scale holds.

The 3 plaintext bytes:

| Offset | Length | Description |
|--------|--------|-------------|
| 0 | 1 | Flags. `1` in every published capture |
| 1 | 2 | Weight count, unsigned 16-bit, little-endian |

For hosts with AES block encryption but no CCM mode, the spec gives the block
layouts that follow from RFC 3610 for these sizes (7-byte length field, first
block flags `0x1e`, counter block flags `0x06`).

### The kilogram conflict

The 16-bit count is not in dispute. What it means is agreed for pounds only.

| Scale display | Reading A: public implementation | Reading B: 2026-10-26 comment |
|---|---|---|
| Pounds | count × 0.01 lb | flags bit 0 set, count × 0.01 lb |
| Kilograms | count × 0.01 kg, flags meaning not established | flags bit 0 clear, count × 0.005 kg |
| Stones | not addressed | not addressed |

Reading A divides by 100 whatever the unit and asks the owner which unit the
display shows. Reading B is the Bluetooth SIG Weight Measurement convention.
They agree for pounds with flags bit 0 set and differ by exactly a factor of
two in kilograms. **Neither source says it captured a scale set to
kilograms**: the implementation does not state which unit its scale
displayed (pounds is this project's inference), and the comment does not say
kilograms was among its weigh-ins. So this page does not pick one. If
reading B is right, a client built on reading A shows double the true weight
to everyone who weighs in kilograms. If the implementation's scale was in
fact set to kilograms, reading B's bit-0 rule is contradicted instead.

Until someone settles it on hardware, a client follows the spec's
`decision_table` (under `protocol_details.weight_decoding`). The owner states
the display unit; the client never infers it from the flags byte.

| Display unit (owner's word) | Flags bit 0 | What the client does |
|---|---|---|
| Pounds | set | Publish count × 0.01 lb. Both readings agree |
| Pounds | clear | Refuse and report the raw bytes. The readings disagree and nobody has reported this case |
| Kilograms | either | Compute count × 0.005 kg and count × 0.01 kg; the owner confirms once which equals the display. If neither does, refuse and report the raw bytes |
| Stones | either | Refuse and report the raw bytes. No source addresses stones |

Three guards come first. A message whose tag fails is dropped. A flags value
other than `0` or `1` is refused and reported. And if flags ever differs from
the value stored when the owner stated or confirmed the unit, the client
stops publishing and asks again: the unit button is the same back button that
resets the scale, so the unit can change under a client.

### Worked example (synthetic)

An invented key, nonce and weight. Not a capture.

```text
key        6c696265726174656462726561642121      ASCII "liberatedbread!!"
message    4d1c972a971c39727bdfb1d475fdff4e45cc28
  nonce       4d1c972a971c3972
  tag         7bdfb1d475fdff4e
  ciphertext  45cc28
plaintext  01 88 3b
  flags       0x01
  count       0x3b88 = 15240   ->  152.40 lb under both readings
```

A second vector in the spec has flags `0x00` and count 13820: 69.10 kg under
reading B, 138.20 kg under reading A. A third repeats the first plaintext
under a different nonce, and no byte of the tag or ciphertext matches.

### What a client must never do

- **Write to the provision characteristic when it reads `01`.** Nobody knows
  whether the scale refuses or silently replaces its key. A replaced key locks
  out the vendor app and every other client until a reset.
- Write a key it has not already stored somewhere safe, or write to a scale
  its user does not own.
- Write anything to the firmware-update service. No recovery is known.
- Lead a user into a factory reset, or into removing the scale from the
  vendor account, without first showing what it costs.
- Suggest a reset because no message arrived.
- Treat a message whose tag fails as a reading.
- Stay connected once the reading is in.
- Connect on its own when it does not hold the key. The scale accepts a
  connection only during a weigh-in and serves one client at a time, so
  that weigh-in may never reach the vendor app, and the owner gets nothing
  for it. Connect only when the owner asks, and disconnect as soon as the
  reads are done.
- Log, publish or commit a key, the scale's address or its serial number.

## Verification and unknowns

| Fact | Standing |
|---|---|
| Name, service, vendor characteristic, indication, 19-byte length | Two independent parties, 21 months apart |
| Value handle `0x0019`, address prefix `A4:C1:38` | The January 2025 capture only: one party, one unit. The prefix agrees with the Telink chip marking in the FCC photograph, which is not a second observation of the prefix |
| Device Information strings, manufacturer data and step-on flag, advertising while asleep, the full GATT listing | One party, one unit |
| 8-byte nonce split | One implementation; its claim about mirrored nonce bytes holds in nine samples a different person posted earlier |
| AES-128-CCM parameters, plaintext layout | One implementation and one later comment, both leaning on the vendor app's parser; their independence is not established. The vendor's store page lists AES-128 under data encryption |
| Weights match the display | One unit each, two reporters |
| Key captured from an Android Bluetooth log | One party, hardware `H01` / firmware `A16`; the 16-byte write itself seen by a second person |
| Scale factor in kilograms | **Conflict, unresolved** |
| Own-key provisioning | **One report**: relayed from an AI assistant's analysis, one unit, firmware not stated, reproduced by nobody |
| Anything on firmware other than `A16` | Unknown |
| Run on hardware by this project | Nothing |

### Experiments an owner can run

Each closes a named open question in the spec
(`protocol_details.owner_experiments` has the steps). All are on your own
scale. E7, E11 and E12 need the vendor app. **E1 and E10 reset the scale,
which ends the vendor pairing**; the only way to set a reset scale up again
that more than one party has observed is the vendor app. None of these is a
reason to unpair or reset a scale that works. Never write to the
firmware-update service, and remove the address, serial number and key before
sharing.

| | Experiment | What it settles | Cost |
|---|---|---|---|
| E1 | Own-key provisioning: reset; subscribe and weigh once while the status still reads `00`; write a stored random key; weigh; then try a second write at status `01`; then pull the batteries. Record the firmware string | Whether the scale has a vendor-free future, and on which firmware; what a keyless scale sends; whether a provisioned scale can be re-keyed over the air; whether the key survives a battery change | **A factory reset, which ends the vendor pairing.** The app loses the scale until it is reset and set up there again |
| E2 | Unit sweep with a known key: first one fixed load in the unit the scale is already set to, then the same load in the other two units | The kilogram conflict and the flags byte, starting with the unit behind the one flags value ever published | None to the scale. The weigh-ins used may not reach the vendor app. Tap the unit button briefly: holding it starts the reset |
| E3 | Descriptor value and host matrix: `01 00`, `02 00`, the stack's own subscribe on Linux and on an Apple host, a proxy; list the characteristic's declared properties | What works on Linux, on Apple hosts and on proxies | None to the scale. The weigh-ins used may not reach the vendor app |
| E4 | Weigh with nothing connected, then wake the scale and connect; log every message of one slow step-on | Stored readings; the extra messages | None to the scale. The weigh-ins used may not reach the vendor app |
| E5 | Capture advertisement and scan response, awake and asleep | Exact bytes, interval, address byte order, where the step-on flag travels | None: scanning only, no connection |
| E6 | Full read-only GATT listing, including under the firmware-update service | What that service holds; other firmware revisions | None to the scale: read only, no button held, nothing written. The weigh-in used may not reach the vendor app |
| E7 | Leave the working phone untouched. Sign in on a **second** phone with its Bluetooth log on, weigh once, look for a key write in that log | Whether a new phone gets the key from the account or has it written again, and so whether a key could ever be learned without a reset | None to the pairing if the scale is never removed from the account. Needs the vendor app and a second phone |
| E8 | Collect a few hundred messages | Whether nonces repeat | Time; the weigh-ins collected may not reach the vendor app |
| E9 | Note the address prefix on units of different years; optionally photograph the radio chip's marking if it shows through the battery bay. **Do not open the scale for this** | Whether the radio changed | None: the case stays closed |
| E10 | Scan the scale through a complete reset hold, timing `otA` and `clr`. Never release at `otA`; write nothing | What the scale does on the air in the `otA` stage; the reset timing | **A factory reset.** Only as the reset that starts E1 or a Route 1 capture |
| E11 | Only when a setup is happening anyway (new scale, or one already unpaired): log that one in-app setup on the current vendor app | Whether app version 5.12 still writes the key in clear, and whether setup completes | None beyond that setup. Needs the vendor app. Never unpair a working scale to run it |
| E12 | With a known key: take one reading locally, disconnect, then look in the vendor app; weigh again with the app open | What the app shows for a weigh-in a local client received | None. Needs the vendor app and a key |

E1 and E2 matter most. E1 decides whether an owner would ever be stuck; E2
fixes a factor-of-two error that a published integration may already have.

### What is not a route

Each of these was looked for and is recorded so that nobody repeats the
search.

- **Nothing to redirect.** The scale has no Wi-Fi and never talks to a
  server; the phone does. The DNS-redirect approach used for the original
  Aria has nothing to act on.
- **No shared protocol with the Transtek-named scale family.** The factory
  name matches the one openScale puts on its Trisa and 1BODY handlers, but
  that family's services and challenge exchange are not on this scale.
- **A matcher on the standard weight service alone** claims this scale and
  gets nothing: the standard measurement characteristic is absent.
- **No weight in the advertisement.** The one description of it has a step-on
  flag and no reading.
- **No off-the-shelf Telink over-the-air update.** The stock Telink update
  service is not present in the one published GATT listing; nobody has
  checked while the display shows `otA`.
- **No firmware side-load.** The update service that is listed is
  undocumented, no image is public and no recovery is known. This page
  publishes no route through it.
- **No separate flash chip to read** on the photographed unit, and no custom
  firmware for this scale or any Transtek or Telink bathroom scale was found.
- **No key without a reset.** Nobody reports the vendor app sending the key
  again to a scale that is already set up (experiment E7 would settle it).

Open hardware questions (how the case opens, whether the chip's debug port
answers, whether the reading crosses the board unencrypted between the
scale's controller and the radio module) are listed in the spec under
`protocol_details.hardware_research` with what each would risk. They are not
owner experiments.

### When nothing else is left

The scale has four conventional three-wire load cells wired as one bridge
(FCC photograph). Fitting a load-cell amplifier and a controller of your own
in place of the original board is a generic technique that nobody has
documented on this model. It ends the Fitbit function, it needs recalibration
against known weights because the factory calibration stays with the original
board, and it needs the glass-topped case opened, for which no instructions
exist. It can be undone only if the original board is kept undamaged and
every wire's pad is recorded before it is unsoldered. Anything fitted in its
place must be battery-powered or safely isolated from the mains: a person
stands on it. This is a last resort for a scale that nothing can read any
more, not something to do to one that works.

## Tools Used

- No hardware, vendor app, account or capture was used by this project.
- `scripts/test_fitbit_aria_air_spec.py`: synthetic vectors, AES-CCM from the
  `cryptography` package and from bare AES blocks.

## References

- [ha-fitbit-aria-air protocol notes, pinned](https://github.com/BigWebstas/ha-fitbit-aria-air/blob/d43708a1eb6acee368bde5a06b34208c9ece88f8/docs/PROTOCOL.md)
  and [the implementation](https://github.com/BigWebstas/ha-fitbit-aria-air/tree/d43708a1eb6acee368bde5a06b34208c9ece88f8).
  No licence file. What was taken from it is facts (identifiers, layouts,
  parameters, timings, observed behaviour), written up in this project's own
  words; none of its code is used. Its documented way of getting the key
  starts by removing and resetting the scale.
- [openScale issue 1105](https://github.com/oliexdev/openScale/issues/1105):
  the January 2025 capture and the 2026-10-26 comment. openScale has no Aria
  Air handler.
- [SmarterScale](https://github.com/drinkcat/SmarterScale): the camera-reading
  Android app, Apache-2.0.
- [FCC ID XRAFB203](https://fccid.io/XRAFB203): test reports, label, external
  and internal photos.
- [RFC 3610](https://www.rfc-editor.org/rfc/rfc3610): the CCM mode.
- [Firmware Update (DFU / OTA)](../protocols/firmware-update.md): why a DFU
  service UUID is not proof of a particular bootloader.
