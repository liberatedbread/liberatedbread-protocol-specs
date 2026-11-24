# Fitbit Aria 2 (FB202) — Research Notes

Consolidated 2026-11-23 from Google's help pages, the vendor manual, the FCC
filing, and a search of public projects, forums and papers. Revised
2026-11-24 with a second research round on local routes, each of which was
then checked against its source by a separate, sceptical pass. **No physical
scale, capture, vendor app or firmware image was used by this project.** Every
fact below was read off a public document or reported by someone else; nothing
was reproduced on hardware. The cutoff notice was read again on 2026-11-24
(00:22, 01:54 and 03:10 UTC), because Google changed the date in it during
2026-11-23; see [The cutoff](#the-cutoff).

**This is a research note and not a spec, on purpose.** Nothing about how the
Aria 2 talks, over Bluetooth or over Wi-Fi, has been published by anyone. The
catalogue therefore records what is known, what is not, and exactly how an
owner holding a scale can find out. The structured sketch is
`research-notes/fitbit-aria-2.yaml`.

**The short answer: no way to use this scale without Google is known.**
Bluetooth is its setup channel only. By Google's own description its weigh-ins
travel over Wi-Fi to Google's servers (vendor), so a phone or computer that
connects to a paired Aria 2 over Bluetooth should not expect to read a weight
from it (inferred from that description; nobody has listed the scale's
Bluetooth services). The scale has no setup access point and no web page of
its own; those belonged to the original Aria (vendor, by absence). Every route
anyone has proposed is rated under [Local routes, rated](#local-routes-rated).
None of them has been run on an Aria 2 by anyone.

It is a different product from its two siblings, and nothing here transfers in
either direction:

- the original **Aria (FB201)**, four AA cells, Wi-Fi only: see
  `docs/devices/fitbit-aria-wifi-scale.md`;
- the **Aria Air (FB203)**, three AAA cells, Bluetooth only: see
  `docs/devices/fitbit-aria-air.md`.

How each statement is labelled:

| Label | Meaning |
|---|---|
| **vendor** | Stated in a Fitbit / Google manual or help page, read 2026-11-23 (the cutoff notice and the pages quoted beside it again on 2026-11-24, 00:22 and 01:54 UTC; the three notice pages once more at 03:10 UTC). Not demonstrated by anyone independent. |
| **FCC** | Measured by the test lab, or stated in a document, in the public FCC filing. |
| **photo-read** | Read off the FCC internal photograph by this project's research, at the photograph's resolution. Not checked against a unit. It shows that a part is on the board. It never shows that a route through that part works. |
| **academic** | Published, peer-reviewed work on Fitbit *trackers*. None of it mentions a scale. |
| **reported** | Said by a third party who had the device. Not checked. |
| **unverified** | Known only from a search-engine snippet; the page itself could not be read. Do not rely on it. |
| **inferred** | This note's own reasoning from the facts beside it. |
| **not found** | Looked for and not found; the method is in [How the search was done](#how-the-search-was-done). |

## If you own one, read this first

Google's English help pages now say pairing of this scale ended on
**2026-11-09**. Until 2026-11-23 the same notice said 2026-11-28, and other
language editions still do (see [The cutoff](#the-cutoff)). Treat pairing as
over: there is no window left to plan around. Each point below gives its
basis; where a suggestion has not been tested by anyone, it says so.

**Do not unpair it.** Do not remove the scale from your account in the app.
Google's notice says a scale unpaired after the date cannot be paired again
(vendor), and by its English text that date has passed. In the app the button
is "Disconnect device": Connections, the scale, System (vendor). On iPhone and
iPad, removing yourself as a user of the scale is the documented first step of
removing it (vendor), so do not do that either. No owner report of an Aria 2
being refused, or accepted, was found (see [The cutoff](#the-cutoff)); treat
the door as closed.

**Do not factory-reset it.** The reset is: batteries out, hold the small button
above the battery slots, put the batteries back while still holding, keep
holding for at least 10 seconds (vendor). The manual says it clears "all user
data from the scale including stored weights and Wi-Fi networks", and the scale
then asks to be set up (vendor). Setting up is the step Google says has ended,
so **a factory reset cannot be undone by any documented means** (inferred from
those two vendor statements).

**Google's own troubleshooting still tells you to do it.** On the same help
page that carries the cutoff notice, the advice for an Aria 2 that logs you as
a guest, or whose weigh-ins do not appear, is: batteries out for 30 seconds,
weigh again, and if that fails "factory reset the scale and go through the
setup process again" (vendor, two places on
<https://support.google.com/googlehealth/answer/14236805>). **Stop after the
battery step.** The second half of that advice now strands the scale.

**Google's sync troubleshooting for other devices can take the scale with
it.** The page for a tracker, watch or Aria Air that will not sync says to
remove "other Fitbit devices" from your account, and to "Disconnect device"
and then "Add device" to clear connection errors (vendor, four places on
<https://support.google.com/googlehealth/answer/14236618>: the tracker step
names "trackers or watches", the Pixel Watch and Aria Air steps say "other
Fitbit devices" without limit). The Aria 2 error table sends owners to that
page when the scale is not syncing (vendor). **Leave the Aria 2 out of all of
it:** once disconnected it cannot be added back (inferred from the notice).

**Changing batteries: keep your fingers off the button.** The reset is that
button held while the batteries go in. Taking the batteries out and putting
them back is Google's first troubleshooting step for a paired scale, so that
is the step to use (vendor, for the step; Google says "at least 10 seconds" or
"10 seconds" in three places and "30 seconds" in the guest advice, and states
no maximum). A *brief* press of the same button with the batteries in is
described as a restart, but only in the instructions for a setup that is stuck
(vendor); nobody has published what a restart keeps.
There is no reason to touch the button on a working scale. Replace the
batteries when the low-battery icon appears rather than letting them run flat:
one commenter says they had to pair "that Fitbit scale" again whenever its
batteries ran low (reported; the model was not named, so this may not be the
Aria 2 at all).

**Do not remove people from the scale** unless you are sure. Whether a person
can be added back after the cutoff is not stated anywhere.

**Avoid changing your Wi-Fi.** Google says the scale must be reconnected
whenever the network name, provider, password or router changes, and the only
documented way to reconnect an Aria 2 is the phone app, over Bluetooth:
Connections, then Aria 2, then "Wi-Fi Network" or "Pair Scale to Different
Network" (vendor). Google has not said whether that menu survives the cutoff,
and its notice does not define "re-pair". But its own wording puts the network
change inside setup and pairing: both manual editions say to reconnect "using
the setup method above", the set-up article speaks of setting up the Aria 2
"again after you make changes to your network", and one of the two menu labels
is "Pair Scale to Different Network" (vendor for the wording; that the block
therefore covers the Wi-Fi change is inferred). **Treat the in-app Wi-Fi
change as already gone unless experiment 1 shows otherwise.** One press
article asserts that after a router change the scale cannot be reconnected;
that is the journalist's reading, not a Google statement.

**If the router has to go: make the new network look like the old one. Try
this first.** Give the new router the *same network name, the same security
mode and the same passphrase*. A Wi-Fi client normally joins any access point
that presents the network it already knows, so the scale should not notice.
**This is untested on an Aria 2: nobody has published a result.** It uses
neither the app nor the scale's setup, so a failed try should be undoable by
switching the old router back on (inferred: Google's own troubleshooting
assumes the scale survives a router restart, but nobody has reported what an
Aria 2 does after repeated failed joins, and one commenter's unnamed Fitbit
scale had to be paired again after dropping off Wi-Fi on low batteries). Keep
the old router until the scale shows its check mark on the new one.
Stay inside what the scale is documented to support: 2.4 GHz, 802.11b/g/n,
WEP / WPA / WPA2 personal, automatic (DHCP) addressing, network name and
password each at most 32 characters, no sign-in page (vendor). WPA3-only and
enterprise (802.1X) networks are not on the vendor's list (inferred from the
list).

**A phone cannot be expected to read your weight from it.** Bluetooth on the
Aria 2 is for setup and for changing the network. Google says the Aria 2 uses
Wi-Fi to connect directly to the router, and lists only trackers, watches and
the Aria Air as syncing over Bluetooth (vendor). Apps that read Bluetooth
scales, including any that handle the Aria Air, should not be expected to work
with it: no source shows this scale offering a weight over Bluetooth
(inferred; nobody has listed its Bluetooth services, and experiment 4 would
show it if the inference were wrong).

**A new phone should not matter.** The scale uploads over Wi-Fi to the account,
not through the phone (vendor, for the Wi-Fi part). That a phone change needs
no re-pairing is inferred from it; Google does not say so. When you move
phones, sign in on the new one and leave the scale alone: do not "remove" it in
the old phone's app first, because that is unpairing.

**It still weighs with no network and no account.** The manual: body fat, BMI
and lean mass need a scale that has been set up with an account, and "You do
not need to complete this setup to weigh yourself" (vendor). So even a reset or
stranded Aria 2 is a working weight-only bathroom scale. What is lost is body
fat percentage, BMI, recognising who stepped on, and the history. A paired
scale whose Wi-Fi is down still weighs and then shows an error (vendor);
whether it still shows body fat for a recognised person while offline is not
stated.

**If yours is already unpaired or reset.** It still weighs, weight only.
Trying to set it up again costs no pairing, because there is none left to
lose: try the current app, and, if you still have a phone or tablet whose app
is older than version 5.12, try that too (experiment 7). One thing may be at
stake: a scale that was unpaired but never reset may still hold its people
and its network, and whether a failed setup clears them is not documented.
**Do not expect either attempt to work.** Google has not said whether the
block is in the app or on its servers; if it is on the servers, an older app
is refused as well, and press reports say old enough builds no longer run at
all (route 3). **Never unpair or reset a working scale to test this.**

**Get your history out now.** Google says previously synced data is not
affected (vendor), but it gives no end date for syncing and makes no promise.
One forum user wrote on 2026-07-03 that their "fitbit scales" (model not
named) had stopped syncing a couple of weeks earlier (reported; read directly
on 2026-11-24; cause unknown). The thread is about Home Assistant's cloud
integration, and five days later the same user wrote that a newer Google
Health component "supports scales" and "seems to work". So the report may be
about weigh-ins no longer reaching Home Assistant and not about the scale no
longer reaching Google; the post does not say which, and both readings are
kept. Separately, the public page of one personal connector, last updated
2026-08-23, describes it as reading Aria 2 weight and body-fat measurements
through the Google Health API (reported; a description of the tool, not a
dated sync observation).

Export routes that exist on 2026-11-23:

| Route | State | Label |
|---|---|---|
| Google Takeout with "Google Health" selected | Google's documented export for Google-account users (<https://support.google.com/googlehealth/answer/14236615>) | vendor |
| Google Health API, `weight` and `body-fat` data types | Live; lists the Aria 2 as a compatible device (<https://developers.google.com/health/data-types>). All scopes are restricted (<https://developers.google.com/health/about>); an unverified app is limited to 100 users (<https://developers.google.com/health/app-verification>) | vendor |
| Health Connect on an Android phone | Google's help lists Weight and Body fat percentage among the data types the Google Health app can write to Health Connect (<https://support.google.com/googlehealth/answer/14506680>). That scale weigh-ins in particular are written, and can be forwarded from there by another app, is said by one forum post of 2026-09-28, which addresses an Aria 2 owner by name; its author wrote the forwarding app it recommends | vendor for the data types; reported for scale weigh-ins (one post, by the author of the app it recommends; read directly on 2026-11-24) |
| Legacy Fitbit Web API | Switched off 2026-11-02; requests answer HTTP 410. Every older "Aria to somewhere" sync tool built on it is dead | vendor; the consequence is inferred |
| fitbit.com "Data Export" | Documented only for accounts that still sign in with a Fitbit login; those logins ended 2026-05-19 | vendor; "effectively closed" is inferred |

All of these read the cloud copy. None is a local route, and none helps a
scale that has lost its pairing or its Wi-Fi.

**Do not try the original Aria's tricks on it.** The local servers that exist
are for the FB201's plain-HTTP upload. Nobody has shown the Aria 2 speaks that
protocol, and nobody knows which names it resolves. If the same house also has
an original Aria and you redirect `www.fitbit.com` for it, scope that DNS
override to the old scale's address only: whether the Aria 2 depends on the
same name is unknown, and a network-wide override could cut it off.

**Do not open a scale you depend on.** Everything that involves the board is
bench work for a spare (see [Local routes, rated](#local-routes-rated)).

**Vendor safety text, unchanged:** do not use the scale if you are pregnant or
have a pacemaker or other implanted medical device; it measures body
composition by passing a small current (vendor).

## Verdict

| | |
|---|---|
| Rating | **Unknown.** The directory's usual ratings do not fit: not `confirmed` (no local path is known) and not `rejected` (nobody has shown the scale is closed; nobody has looked). |
| Verdict | **Research note only. Parked: no local path known.** |
| Local use without Google | **None known.** Eleven proposals are rated below; three of them are not routes at all. One is ordinary Wi-Fi behaviour and worth trying first at a router change. One is a log of the app's own Wi-Fi change: the log is read-only, the change is not, and a change refused part-way may leave the scale without a network for good. It is for an owner who must change network anyway or for a spare, and it may already be impossible. The rest are untested, blocked on the unknown protocol, bench work on a spare, or not available. None has been run on an Aria 2. |
| Why not a spec | A spec in this catalogue is found by a matcher. The public record holds no machine-observable identifier for the Aria 2: no Bluetooth name or service, no MAC prefix, no DHCP or DNS name. `discovery.none` is reserved for devices that cannot be discovered, not for ones nobody has scanned, and a guessed matcher fails silently. |
| What changes it | One owner session. Any single observed identifier promotes this to an identify-only spec; see [Experiments](#experiments-an-owner-can-run). |
| Testing | Untested. Nothing here was run on this project's hardware. |

## Local routes, rated

A second research round listed every route anyone could propose, and a
separate pass then opened each cited source and re-rated it. Where the two
disagreed, the stricter rating is the one given here. Being listed does not
make something a route: numbers 4, 8 and 9 are here only so that nobody
mistakes them for one. Read the table with three rules in mind:

- **Nothing here has been run on an Aria 2 by anyone.** "Works on the original
  Aria" and "shown on a Fitbit tracker" are statements about other products.
- **A part seen in a photograph is not a route.** The FCC photograph shows
  that a chip or a pad is on the board. It does not show that anything can be
  read or changed through it.
- **Re-pairing has ended.** A step that makes the scale forget its network or
  its account can no longer be repaired the normal way, so "it would only need
  setting up again" now means "it is lost".

| # | Proposed route | Evidence | Run on an Aria 2? | Risk to the scale | Effect on the pairing | Standing |
|---|---|---|---|---|---|---|
| 1 | New router with the old network name, security mode and passphrase | Ordinary Wi-Fi behaviour (inferred) | No | None | Leaves it alone | **Try first** at a router change. Untested on this model |
| 2 | Log the app's own Wi-Fi change | The control is vendor-documented; the method is inferred; whether the control still works is unknown | No | Unknown as a whole. The log: none, it is read-only. The change it records: unknown, untested since app 5.12 | The log does not touch it. The change it records: unknown | **Only if you must change network anyway, or on a spare; then at once**, if the app still offers the control. It may already be gone. A refused or interrupted change may leave the scale without a network for good |
| 3 | Pair with an app build older than 5.12 | None. Where the block is enforced is not stated; probably on the servers. Press reports say old builds are being shut out | No | None | **Only for a scale that is already unpaired.** A failed attempt costs no pairing, because none is left; a scale that was unpaired but never reset may still hold its people and its network, and whether a failed setup clears them is not documented | Cheapest thing to try for a stranded scale. May well not work; an old enough build may refuse to run |
| 4 | Send new Wi-Fi details over Bluetooth from your own client | None: no published services, no capture; plausible only by analogy with trackers | No | Unknown | A lost network or account link could not be repaired by re-pairing | **Research direction, not a route** |
| 5 | DNS override plus a LAN server, the original Aria's route | Works on the original Aria; untested here; the two FB201 projects that mention this model call it unsupported and untested | No | None for a passive look | Leaves it alone | Untested, and blocked on the unknown protocol |
| 6 | Debug pads on the board | Two groups of bare pads and an ST ARM microcontroller are photo-read; nobody has connected to anything | No | Unknown, with an unrecoverable branch | Reading: none. Erasing or patching: destroys it | Bench work on a spare. **Never force read-out protection off** |
| 7 | Clip-on read of the flash chip | The chip is photo-read; a read is undemonstrated; contents unknown | No | Reading: none. Writing: recoverable only from a dump taken first | Reading: none | Bench work on a spare, read only |
| 8 | Firmware over Bluetooth, as on Fitbit trackers | Shown only on trackers, and only where the tracker ran unencrypted or its key had been extracted; never on any scale | No | Unknown | Would replace the firmware | **Not available** |
| 9 | Firmware over Wi-Fi | None: no update address for this model is documented anywhere | No | Unknown | Would replace the firmware | **Not available** |
| 10 | Replace the electronics with your own load-cell amplifier | Four load cells are photo-read; the technique is generic and not shown on this chassis | No | Unrecoverable: the Fitbit board is abandoned | Ends it for good | **One-way last resort.** Whatever is added runs from batteries, never from the mains |
| 11 | Tap the load cells without cutting them | None | No | Unknown | Should leave it alone; unproven | Undemonstrated bench work, on batteries only |

"Risk to the scale" is the chance of leaving it unable to work as it does
today: none, unknown, recoverable, or unrecoverable.

### Routes an owner can use or try

**1. The same network on a new router.** Described under "If the router has to
go" above, and tested by experiment 5. It is the first thing to try when a
router or provider changes, because it involves neither the app nor the
scale's button. Nothing in Google's text ties syncing to anything but the
scale joining the network it has stored (inferred).

**2. Logging the app's own Wi-Fi change.** This is the one dataset that would
say whether anyone can ever move this scale to a new network without Google:
it shows whether the phone talks to Google's servers during the change or
only to the scale. It is experiment 2.

- The log is read-only. It records what the phone and the scale already say
  to each other and sends nothing of its own.
- What it records is the app's Wi-Fi change with the *same* network typed in
  again. That is Google's documented procedure, but nobody has published a
  run of it since app 5.12, and what the app asks the owner to do to the scale
  during it is not documented.
- **Stated plainly:** if the app starts the change and is then refused or
  interrupted, nobody knows what the scale is left holding. If it has dropped
  its stored network, the only documented way to put one back is this same
  control, and Google says re-pairing has ended. That is why the route as a
  whole is rated unknown, although the log adds no risk of its own.
- **If the app asks you to remove the scale, reset it, press or hold its
  button, or set it up as new, stop and back out.** Nobody has published what
  even a brief press of the button keeps.
- So: do it immediately if you are going to have to change the network
  anyway, or on a scale you can afford to lose. On a working scale with no
  change coming, the choice is the owner's, with that sentence in view.
- The control may already be gone (experiment 1 is the one-minute look that
  says).

**3. An app build older than 5.12, only on a scale that is already
unpaired.** Google's notice ties the block to "the release of app version
5.12" and does not say where it is enforced. If the block is in the app, an
older build might still pair; if it is on the servers, it will not, and the
pass that checked this route judged the servers more likely. A failed attempt
on a scale that is already unpaired or reset costs no pairing, because none
is left. One thing may be at stake: a scale that was unpaired but never reset
may still hold its people and its network, and whether a failed setup clears
them is not documented. **Never unpair or reset a working scale to test
this.** Three cautions:

- This project did not obtain or examine any app build. An app package from
  an unofficial download site is software of unknown origin that you then
  sign in to with your Google account; this note links none. A phone or tablet
  whose app has simply not been updated is the clean way to try.
- On 2026-05-19 the Fitbit app became the Google Health app, and after that
  date a Fitbit account can no longer be used to sign in (vendor,
  <https://support.google.com/googlehealth/answer/17068213> and
  <https://support.google.com/googlehealth/answer/14237024>). A build from
  before that date is the Fitbit-branded app with the sign-in Google has
  ended, so it may not sign in at all (inferred).
- Old builds are reported to be shut out already (reported: press, one
  outlet, two articles; not checked by this project). An article published
  2026-06-25 says a Google notice gave 2026-07-15 as the day app versions
  older than 5.0 stop working. An article of 2026-10-11 says owners still on
  the old app were being met by update prompts that would not let them carry
  on, though a few could still dismiss the prompt, and that app version
  5.08, in September, dropped sign-in with a Fitbit account. So an older
  build may refuse to run, or insist on updating, before it ever reaches
  setup (inferred from those reports).
  (<https://gadgetsandwearables.com/2026/06/25/google-is-about-to-kill-the-old-fitbit-app-workaround/>,
  <https://gadgetsandwearables.com/2026/10/11/fitbit-holdouts-forced-google-health-update/>)

Do not expect this route to work.

### Research directions, not routes

**4. Re-provisioning over Bluetooth with your own client.** Nobody has
published this scale's Bluetooth services or a capture of the exchange. That
it might be possible rests only on how Fitbit trackers behaved (see
[Fitbit tracker research](#fitbit-tracker-research-and-whether-it-applies)),
and it may need something only Google's servers issue. **Warning: a write
that goes wrong, or even one that works and makes the scale drop its stored
network or its account link, cannot be repaired by re-pairing, because
re-pairing has ended. The loss would be permanent by any normal means.** This
note gives no bytes to send, and nobody should send any to a scale they depend
on. Experiment 2 is the step that would turn this from a guess into a
question with an answer; its log is read-only, the app's change that it
records is not, and it carries its own warning.

**5. The original Aria's DNS route.** On the FB201, redirecting the upload
hostname to a server on the LAN works. Nobody has shown the Aria 2 speaking
that protocol: the one issue on the subject says it "probably uses a different
API", and one of the FB201 servers says it is "*not* tested with an Aria 2"
(reported). The route is blocked on facts nobody has: the hostname, whether
the upload is plain HTTP or TLS, whether the scale checks certificates, and
the upload and reply formats. Without them no working server can be built, so
there is nothing to try yet. A passive look at the traffic (experiment 3)
carries no risk and is where this starts. **A stand-in server must never tell
the scale that a firmware update is available**: a wrong or cut-off image
could leave the scale unable to start, and no image exists to restore it.

### Case open: bench work on a spare, never on a scale you depend on

Opening the scale means removing the battery-bay label, two Torx T10 screws
under it, and prying the plastic base off the glass (reported, iFixit). That
alone puts a working scale at risk. Two rules for everything in this group:

- **Nobody stands on the scale while anything is attached to it.** The Aria 2
  measures body fat by passing a small current through the feet (vendor), so
  its circuit is in contact with the person on it. That holds for a hand
  pressed on the glass as much as for feet (inferred). A debug probe, serial
  adapter, flash programmer or computer powered from the mains must never be
  part of that circuit: a fault in mains-powered equipment would then have a
  path through the person. Work with the scale open on a table. Anything added
  to a scale that will be stood on again runs from batteries.
- **Report facts, never contents.** A dump of either memory is a firmware
  extraction and may hold your Wi-Fi password and account material. No image
  or code from it may be sent to or committed in this project; part numbers,
  pad functions and derived facts are what is wanted.

**6. The debug pads.** The board carries bare round test pads with no legible
labels, in two groups by the latest reading of the photograph (earlier
readings recorded one cluster), and its host chip is an ST-made ARM
microcontroller (all photo-read; see
[Hardware](#hardware-from-the-fcc-photographs)). Groups like these usually
carry a chip's debug or serial lines for factory programming (inferred
from general practice, not read off this board). Which group serves which
chip, and which pad is which, is unknown, and nobody has connected to any of
them.

- ST's ARM microcontroller families have a read-out protection setting: off;
  on, where a debugger can attach but cannot read the program memory, and
  where turning protection back off erases the whole chip; and permanent,
  where debug access is disabled for good. Production devices usually ship
  with it on. (General to the chip family, from the maker's documentation;
  not re-read for this note, and the exact part on this board is unknown.)
  Which level this chip has is unknown, and it decides whether this is a
  route at all.
- Reading the chip's identity code is harmless. **If the first read of the
  program memory is refused, stop. Never use the command that turns read-out
  protection off: it erases the chip, no Aria 2 firmware image exists anywhere
  to put back, and the scale is then dead for good.**
- The same chips have a built-in loader, entered by holding a boot-select pin
  at power-up, that reads and writes program memory over a serial line. It is
  cheaper to reach than the debug port but sits behind the same protection:
  with protection on it will not read, and removing protection through it
  erases the chip just the same. Whether that pin is brought out here is
  unknown.
- A serial console may or may not exist. The original Aria had one; nothing
  shows this board does. The tracker firmware studied by academics contained
  an unauthenticated factory console able to change a tracker's serial number
  and encryption key (academic), so typing into a console here could change
  the scale's identity or state. **Listen only:** connect ground and the
  adapter's receive line, never its transmit line, and measure the board's
  logic voltage first, because it is not published. Probing unlabelled pads
  with the batteries in risks shorting neighbours. Even if a console exists,
  a way to point the scale at another server through it is a guess.

**7. A clip-on read of the flash chip.** An eight-lead chip with the Macronix
logo sits on the board (photo-read); that maker's eight-lead parts are serial
flash memory, so it is taken to be external flash (inferred). It is a separate
chip from the microcontroller's own program memory, so the microcontroller's
read-out protection does not cover it (general). A test clip and a serial
flash reader can read such a chip in place with the batteries out, which
changes nothing on the board; nobody has reported doing it on an Aria 2, and
whether an in-circuit read works on this board is untested. **What the chip
holds is unknown**: display assets, logs, settings, stored networks and a
firmware image are all possible and none is shown. Writing to it is for a
sacrificial unit and only after two reads that match: a bad write with no
good dump, or a board that checks the chip and then refuses to start, can be
unrecoverable, and desoldering adds the risk of lifting pads.

### Not available

**8. Firmware over Bluetooth.** Academic work flashed modified firmware onto
Fitbit *trackers* over Bluetooth in two cases only: trackers running
unencrypted, which the paper describes as an option on models from before
2015; and two early models whose key could be read out of the device through
a weakness Fitbit patched in October 2017 (academic). A 2017 product would be
expected to always encrypt (inferred), which means an image has to be
prepared with a per-device key that is held inside the device and that no
owner can obtain. The image format and the tools for this scale are not
public either. Nobody has shown any Fitbit scale accepting firmware
over Bluetooth, and nobody knows whether this one takes updates that way at
all. It is a known tracker weakness that nobody has shown applies to this
scale. **Do not attempt it on a scale you want**: nothing says a failed
attempt could be recovered.

**9. Firmware over Wi-Fi.** The scale updates itself (vendor), and the help
text ties updates to the Wi-Fi connection (see
[Which radio does what](#which-radio-does-what)). But no update address for
the Aria 2 is documented anywhere, no image has been published, nobody has
observed an update in transit, and how an update is authenticated is unknown.
There is nothing to try. The original Aria has a documented update address,
but it belongs to a different design and nothing ties it to this model.
**Never offer or signal an update to the scale from a server of your own**,
for the reason given under route 5.

### Last resort

**10. Replacing the electronics.** The four load cells are joined to the board
by coloured leads on solder pads along both long edges (photo-read). Cutting
those leads and wiring the cells to a hobby load-cell amplifier and a small
microcontroller is a generic, widely used pattern; nobody has published doing
it on this chassis, and which lead is which is not published. **It is
one-way.** The Fitbit board is abandoned, the pairing and the account link go
with it, and so do body fat, user recognition and the display, which hangs
off the Fitbit board by a flat-flex cable and has no published interface. What
remains is a weighing platform that depends on nobody, after calibration with
known weights. For a scale that already cannot be set up, that may be the
honest end state.

The two rules under
[Case open](#case-open-bench-work-on-a-spare-never-on-a-scale-you-depend-on)
apply here too, and this is the one route that ends with someone standing on
a rewired scale. **Whatever you add runs from batteries, never from a mains
adapter or a computer's USB port, for as long as anyone stands on it.** A
bathroom scale is stood on barefoot, and a fault in mains-powered equipment
wired into it could reach the person on it (general electrical safety, not
specific to this scale). While it is on the bench and connected to a computer
for calibration, load it with weights, not with a person.

**11. Tapping the cells without cutting.** A second amplifier can sometimes be
connected across load-cell wiring that stays attached to its original board,
which would leave the Fitbit electronics alive. Whether that works here
depends on how the board drives the cells, which is unknown; it may read
nothing useful or disturb the scale's own readings. Nobody has demonstrated
it on this scale. It is bench work for a spare, under the two rules above.
The amplifier and whatever reads it both run from batteries, with no lead to
anything plugged into the mains, and nobody stands or presses on the scale
while they are attached (experiment 13).

### Ruled out

| Idea | Why not |
|---|---|
| Joining a setup access point or opening a web page on the scale | The Aria 2 has neither. All setup and network changes go through the app over Bluetooth (vendor, by absence). That was the original Aria's method |
| Pointing the scale, as it is, at a server written for the original Aria | Not shown to speak that protocol (route 5) |
| Using the Aria Air's Bluetooth recipe | A different product: Bluetooth-only data path, different hardware, a different FCC filing, no Wi-Fi. Nothing links its services to this scale |
| The original Aria's Wi-Fi-module download mode and labelled switches | Different hardware. The FB201's Wi-Fi module is not on this board; the host chip here is an ST ARM microcontroller (photo-read) |
| Checking whether a firmware address for this model still answers | None is published, so there is nothing to check. This project did not guess addresses |
| Google Takeout, the Google Health API, Health Connect | They work for a paired scale, but they read Google's copy. They are not local |

## Identity and regulatory record

| Fact | Label | Source |
|---|---|---|
| Model **FB202**; sold as "Fitbit Aria 2", described as a "Wireless Smart Scale" / "Wi-Fi Smart Scale". | vendor | Aria 2 manual; launch post |
| FCC ID **XRAFB202**. ISED Canada **8542A-FB202**. The label is inside the battery bay. | FCC (label exhibit); vendor | <https://fccid.io/XRAFB202>; manual |
| FCC grant dated 2017-08-28, application dated 2017-08-14, equipment class DTS (digital transmission system). | FCC | <https://fccid.io/XRAFB202> |
| Two grant lines: 2402 to 2480 MHz at 0.0049 W, and 2412 to 2462 MHz at 0.081 W, both conducted. | FCC | same |
| Grant note: an 802.11 b/g/n single-stream (1x1) radio with 20 MHz channels. | FCC | same |
| Cover letter: the device "supports 802.11bgn and Bluetooth Low Energy". Its header misprints the FCC ID with a leading Z. | FCC | cover-letter exhibit |
| **Confidential in the filing:** the block diagram, the schematics and the operational description are held under long-term confidentiality and listed as metadata only. The filing therefore names no chip and describes no protocol. | FCC | exhibit list on <https://fccid.io/XRAFB202> |
| Released after a short-term hold that ended 2018-02-09: user manual, internal and external photographs, test-setup photographs. | FCC | same |
| EU declaration of conformity (dated 2020-10-20) cites radio standard EN 300 328 V2.1.1 and names no chipset. | vendor | <https://www.fitbit.com/pdfs/doc/CE_DoC_FB202_Aria2_Updated_102020.pdf> |
| Announced 2017-08-28 at US$129.95, on sale "Fall 2017". The vendor called it an FDA-regulated medical device. | vendor | launch post |
| No FDA 510(k) record for the Aria 2 turned up. | not found | web search 2026-11-23 |
| How to tell the three scales apart: four AA = Aria; **three AA and "Aria 2" printed on the back = Aria 2**; three AAA = Aria Air. | vendor | <https://support.google.com/googlehealth/answer/14236805> |
| Three AA alkaline cells (4.5 V nominal), about a year of battery life; weighing range 10 to 400 lb (4.5 to 181.4 kg); 31.2 x 31.2 x 3.19 cm, 2.13 kg; IP53; operates at 5 to 40 °C; up to 8 linked accounts. | vendor | manual |
| MAC address prefix (OUI). | **not published anywhere found** | — |

On the OUI: the IEEE registry lists address blocks assigned to Fitbit, but no
source ties any block to the FB202, and the two prefixes seen on original
Arias are registered to GainSpan (maker of its Wi-Fi module) and to Delta
Electronics (no source says why), not to Fitbit. Do not take a prefix from the
registry; only one observed on a scale counts.

### Radios, as measured

From the FCC test report (National Technical Systems, Silicon Valley, report
R105487 Rev 1, dated 2017-08-02 and reissued 2017-08-04; sample received
2017-06-12), all FCC:

| | Wi-Fi | Bluetooth |
|---|---|---|
| Kind | 802.11b, g and n (HT20) | **Low Energy only**: the report states that Bluetooth operation is limited to Low Energy |
| Band | 2412 to 2462 MHz | 2402 to 2480 MHz |
| Modulation | DSSS/CCK (b), OFDM (g, n) | GFSK |
| Conducted power | 19.1 dBm (b), 18.8 dBm (g), 18.7 dBm (n20) | 6.9 dBm |
| 6 dB bandwidth | — | 687 kHz |

- One Wi-Fi output with transmit/receive diversity; two internal antennas,
  peak gain 2.36 dBi and 2.21 dBi.
- Wi-Fi and Bluetooth never transmit at the same time.
- Battery powered only, no charger. The test report's interface-port table,
  which records the cabling used during testing, lists "None" (FCC). That the
  case has no wired data port on the outside is inferred from that entry.
- The SAR report's sample was hardware revision "DVT2.1" running software
  "10.2"; that this was a pre-production build is inferred from the revision
  name and the test dates. Bluetooth used antenna chain 0 only; Wi-Fi used
  chains 0 and 1.

## Which radio does what

**Bluetooth is for setup and for changing the Wi-Fi network. Wi-Fi is the only
data path.**

- Google's sync page separates the family in one sentence: trackers, watches
  and the Aria Air sync over Bluetooth Low Energy with a phone, while the Aria
  and Aria 2 "use Wi-Fi to connect directly to your router" (vendor,
  <https://support.google.com/googlehealth/answer/14237221>).
- The scale syncs by itself after every weigh-in; a progress bar and then a
  check mark on the display mean the measurement reached the account (vendor,
  <https://support.google.com/googlehealth/answer/14236618>).
- The 2017 launch post describes setup "via your smartphone's Bluetooth
  connection", after which stats sync automatically (vendor).
- Changing the network is done from the app with the scale nearby (vendor).
  That it travels over Bluetooth is inferred: the scale has no other way to
  hear the phone once its Wi-Fi network is gone.
- Nothing from the vendor says a weigh-in ever travels over Bluetooth. A forum
  moderator is quoted in a search snippet saying Bluetooth is used for adding
  the scale and changing Wi-Fi settings (unverified).
- So a phone connecting to a paired scale over Bluetooth should not expect a
  weight (inferred). Nobody has listed the scale's Bluetooth services, so this
  rests on the vendor's description and not on an observation.

What the sync visibly carries, all inferred from vendor descriptions of
behaviour:

- **Up:** weight, impedance-derived body fat, which user or "guest", battery
  level (the app's battery reading "is accurate as of the last sync").
- **Down, applied "the next time you weigh in and the scale syncs":** lean or
  regular mode per person, whether body fat and BMI are shown, weight units,
  the list of people with their icons. So the exchange is two-way, and any
  stand-in for the vendor's server would have to supply user profiles before
  the scale could work out body fat or recognise anyone.

Firmware updates, source by source:

| Source | What it says | Label |
|---|---|---|
| Aria 2 manual, 2019 edition, safety list | "Your scale will receive automatic firmware updates", and to let them finish before use. It names no channel | vendor |
| Set-up help page, <https://support.google.com/googlehealth/answer/14236818> | A phone hotspot is discouraged because it "may slow down the sync process and prevent an update" | vendor |
| Scale help page, Aria 2 icon table, <https://support.google.com/googlehealth/answer/14236805> | One icon means the scale "successfully connected to your Wi-Fi network or the scale completed an update"; another means the connection or the update failed; a third means it "is currently updating" | vendor |
| "About Fitbit Aria 2", <https://support.google.com/googlehealth/answer/14236401> | Nothing. The page does not contain the word "firmware" or mention an update. An earlier draft of this research cited it for the Wi-Fi claim; that citation was wrong | vendor, by absence |

That updates arrive over Wi-Fi is therefore **inferred** from the first three
rows together. No vendor page says so in as many words, and the word
"firmware" appears on none of the five Google help pages fetched on
2026-11-24 (14236805, 14236818, 14236515, 14236401, 14236618). Nobody has
published an update address, an image, or an observation of an update.

## The cutoff

### What Google says

The same notice appears on three Google Health help pages:
<https://support.google.com/googlehealth/answer/14236805> (using a scale),
<https://support.google.com/googlehealth/answer/14236818> (setting up a device)
and <https://support.google.com/googlehealth/answer/14236515> (erasing a
device). In Google's words, in the English edition as fetched 2026-11-24 at
00:22 UTC and again at 01:54 and 03:10 UTC:

> "Starting November 9, 2026, with the release of app version 5.12, you can no
> longer pair or re-pair Aria and Aria 2 scales. If you choose to unpair your
> scale after this date, you will not be able to pair it again. Any scales that
> were paired prior to this date, and remain paired, will continue to sync.
> Previously synced data will not be impacted."

It adds "Aria Air is not impacted by this change", and that security updates
ended in 2020 for the original Aria and in 2022 for the Aria 2.

**The date in that sentence was changed on 2026-11-23, while this note was
being written.** What the fetches returned (all times UTC; plain fetches of
the public pages, no account). Rows marked "saved copy" are pages saved the
same day by other parts of this project's research, not fetched for this
note; they are timed by the saved file's time, as the 05:44 and 05:51 rows
are:

| When | Edition | Date in the notice |
|---|---|---|
| 2026-11-20 | English, as quoted by the press article of that day | November 28, 2026 |
| 2026-11-23 05:11 | English, first page | November 28, 2026 |
| 2026-11-23 05:44 and 05:51 | English, first and second pages (05:44) and third page (05:51) | November 28, 2026 |
| 2026-11-23 06:00 to 06:21 | English, first page (06:00, 06:01) and second page (06:01, 06:04, 06:21); saved copies | November 28, 2026 |
| 2026-11-23 22:33 | English, first page; saved copy | November 9, 2026 |
| 2026-11-23 23:07 | English, first and second pages | November 9, 2026 |
| 2026-11-23 23:26 | English, third page; saved copy | November 9, 2026 |
| 2026-11-23 23:40 | English, first and second pages | November 9, 2026 |
| 2026-11-24 00:04 to 00:29 | English, all three pages, with and without a language chosen; the first page also with the British, Australian and Canadian English settings | November 9, 2026 |
| 2026-11-24 00:23 | German, French, Spanish, Italian, Dutch, Swedish, Japanese and Portuguese (`hl=pt-BR`) editions of the first page | 28 November 2026 |
| 2026-11-24 00:57 | German, French and Japanese editions of the first page; the English edition fetched in the same minute said November 9 | 28 November 2026 |
| 2026-11-24 01:54 | English, all three pages | November 9, 2026 |
| 2026-11-24 01:54 | German, French, Spanish and Japanese editions of the first page | 28 November 2026 |
| 2026-11-24 02:49 | English, all three pages (fetched by the reviewer of this note's revision) | November 9, 2026 |
| 2026-11-24 02:49 | The same eight other-language editions of the first page as at 00:23 (same reviewer) | 28 November 2026 |
| 2026-11-24 03:10 | English, all three pages | November 9, 2026 |
| 2026-11-24 03:10 | German, French and Japanese editions of the first page | 28 November 2026 |

So, on 2026-11-23, the English text of the first page changed after 06:01
and by 22:33 UTC, that of the second page after 06:21 and by 23:07, and that
of the third page after 05:51 and by 23:26. On the first page the date is the
only wording that differs between the two English versions; on the second and
third pages the labels of some links to other help articles changed as well.
Nothing else in the sentence changed. Google has published no explanation of
the change.

One correction to an earlier draft of this note: it listed a reading of
November 28 "saved at 23:09" on 2026-11-23 and concluded that both versions
might have been served side by side. That file is a text copy, written at
23:09, of the pages fetched at 05:44 and 05:51; regenerating it from those
fetches gives a byte-identical file. It was never a separate observation, and
nothing shows the two versions being served at the same time.

| Point | What Google states |
|---|---|
| Date | **2026-11-09** (English text since 2026-11-23); 2026-11-28 (the English text before that, and eight other language editions on 2026-11-24) |
| App version | Google Health 5.12 |
| What stops | Pairing and re-pairing; an unpaired scale cannot come back |
| What continues | Scales "paired prior to this date" that "remain paired, will continue to sync" |
| Stored data | Not affected |
| End date for syncing | **None given** |
| Any promise that syncing continues | **None made** |
| Whether changing the Wi-Fi network counts as "re-pairing" | **Not defined.** Google's own wording calls the network change setup and pairing (see "Avoid changing your Wi-Fi" above) |
| Where the block is enforced (app, servers, or both) | **Not said** |
| Which of the two dates its systems enforce | **Not said** |

The model numbers do not appear on these pages; the scales are told apart by
their batteries.

### Is pairing an Aria 2 already blocked?

**By Google's English notice, yes, since 2026-11-09 (vendor). No owner report
of an Aria 2 being refused, or accepted, was found (not found).**

- For the **original Aria** the block is already visible: on 2026-11-23 its web
  setup address redirected to a page titled "Aria is no longer supported" (see
  `docs/devices/fitbit-aria-wifi-scale.md`). That page's `Last-Modified`
  header reads 2026-11-09 17:02:17 GMT (fetched 2026-11-24), the day the
  English notice now names.
- A press article of 2026-11-20 says some Aria *and Aria 2* owners can no
  longer pair, "despite Google saying the cutoff should not arrive until
  November 28"
  (<https://gadgetsandwearables.com/2026/11/20/fitbit-aria-support-cutoff-early/>,
  reported). The only mechanism it describes is the **web setup flow**, which
  is the original Aria's path. The Aria 2 is set up in the app over Bluetooth
  and has no web flow. The article shows no Aria 2 being refused.
- No owner report of an Aria 2 pairing attempt, successful or refused, dated
  after app 5.12 began rolling out, was found. Reddit could not be searched.
  The one owner report that could be traced, second-hand through an article
  quoting a thread that could not be read, concerns two original Arias.

So the vendor's statement is the only evidence for the Aria 2, and it comes in
two versions. An owner can add to it in a minute without risk: experiment 1.
An owner whose scale is *already* unpaired or reset has no pairing left to
lose by trying setup now, and the point at which it is refused is itself
wanted (inferred; experiment 7).

### Where Google's own pages disagree

1. **The date differs by language and was edited.** The English notice says
   2026-11-09. Until 2026-11-23 it said 2026-11-28, which is also what the
   press article of 2026-11-20 quotes and what eight other language editions
   still said on 2026-11-24. Every version ties its date to "the release of
   app version 5.12". Google's community post announcing 5.12 is dated
   2026-11-06 ("rolling out starting today"), and 5.13 followed on 2026-11-20;
   neither post mentions a scale. So 9 November falls inside the 5.12 rollout
   and matches the timestamp of the page that replaced the original Aria's web
   setup, while 28 November was three weeks after the named version shipped.
   Google has not explained the edit or said which date its systems enforce.
   (<https://support.google.com/googlehealth/blog/475060763>,
   <https://support.google.com/googlehealth/thread/478477332>)

   One more observation belongs beside those, for both dates. 28 November 2026
   is also the date Google gives for a *different* change: the end of
   installing or updating third-party apps and clock faces on Fitbit
   smartwatches. That change was announced in a community post timestamped
   2026-11-09 20:35 UTC, and it is repeated in the 5.13 post and on a help
   page whose notice also names app version 5.12 (vendor;
   <https://support.google.com/googlehealth/thread/477099339>,
   <https://support.google.com/googlehealth/answer/14237121>). So each of the
   two dates the scale notice has carried coincides with a day of that other
   change: 9 November with its announcement, 28 November with its effect.
   Whether the scale notice's earlier date was tied to that change, and why
   the English text now says 9 November, Google has not said. **This reopens
   no window:** by the English notice, pairing of the Aria 2 has ended.
2. **Aria 2 security updates.** The help-page notice says they "ended in
   2022". Google's security-update table guarantees the Aria 2 "until at
   least" **September 2023**
   (<https://support.google.com/product-documentation/answer/15181553>). Both
   were live on 2026-11-23.
3. **Destructive advice left standing.** The page that announces the cutoff
   still tells Aria 2 owners to factory-reset and set up again for guest
   problems, and still describes the in-app Wi-Fi change, with no mention that
   either may now be final. The sync-troubleshooting page its Aria 2 error
   table points to still says to remove "other Fitbit devices" from the
   account, and to "Disconnect device" then "Add device" to clear connection
   errors, with no exception for a scale that cannot be added back
   (<https://support.google.com/googlehealth/answer/14236618>).
4. **"Will continue to sync" against "no longer connect".** The help notice
   says paired scales keep syncing. The page that now replaces the original
   Aria's web setup says Google no longer supports "or connect to these smart
   scales" and that the data can no longer be viewed in the app. That page is
   titled for the Aria and does not name the Aria 2; whether its wording is
   meant to reach the Aria 2 is not stated.
5. **Web API switch-off day.** Google's developer site says the legacy Fitbit
   Web API was turned off 2026-11-02; the older banner on the Fitbit developer
   site still says 2026-10-30.

A sixth point is a gap rather than a disagreement inside Google: whether a
mere Wi-Fi change counts as re-pairing. The notice does not define the word.
Google's own manuals, set-up article and menu label describe the network
change as setup and pairing (vendor wording, quoted under "Avoid changing your
Wi-Fi" above), and the press article asserts outright that a router change
strands the scale. That the block covers the Wi-Fi change is therefore
inferred, not stated by Google.

## What the vendor documents

### Network requirements

- 802.11b/g/n at 2.4 GHz; WEP, WPA or WPA2 personal; automatic (DHCP)
  addressing only, a static address is not supported (vendor, manual and
  <https://support.google.com/googlehealth/answer/14236818>).
- Network name and password each at most 32 characters (vendor).
- Phone hotspots are discouraged (vendor). Public networks that need a sign-in
  or acceptance page do not work (vendor).

### Setup, as the vendor describes it

Recorded as documentation of what used to work. By Google's English notice
this procedure has been refused since 2026-11-09.

1. User: pull the battery tab (three AA cells are pre-installed); the scale
   powers on.
2. User, in the phone app: Connections, Add device, choose the scale, follow
   the prompts that pair the scale with the phone.
3. User, in the app: choose the Wi-Fi network from the list offered, or enter
   one by hand, and type its password. The scale attempts to connect.
4. User: choose a personal icon. Setup is complete.
5. If setup stalls: briefly press the button in the battery compartment to
   restart the scale and begin again.

At launch the supported setup clients were iOS, Android and Windows 10 (vendor,
manual). Today Google names only the Google Health app on iPhone, iPad and
Android, and that app needs Android 14 or iOS 16.4 or later (vendor,
<https://support.google.com/product-documentation/answer/14226283>).

There is no on-scale access point and no browser procedure for the Aria 2;
that was the original Aria's method (vendor, by absence).

Not documented anywhere: what makes the scale start advertising over Bluetooth
after first setup, for how long, and whether a set-up scale advertises at all
when idle. A four-digit code shown on the scale and typed into the app is
mentioned only by a forum snippet and a low-quality guide site (unverified);
neither manual edition read mentions a code.

### Changing the network, as the vendor describes it

1. User: with the scale and the router nearby, open the Google Health app.
2. User, in the app: Connections, then Aria 2.
3. User, in the app: "Wi-Fi Network" or "Pair Scale to Different Network".
4. User, in the app: Next, then "follow the on-screen instructions to
   reconnect your scale to your network" (vendor,
   <https://support.google.com/googlehealth/answer/14236805>).

What those on-screen instructions are is not published: whether the app asks
the owner to do anything to the scale itself is unknown. Whether the control
still works since app 5.12 is unknown (experiment 1 looks; experiment 2 logs
it).

### Restart and factory reset

| | Procedure | Effect | Label |
|---|---|---|---|
| Battery pull | Remove the batteries, wait at least 10 seconds, reinsert. Google says "at least 10 seconds" or "10 seconds" in three places and "30 seconds" in the guest advice; it states no maximum | Google's first step for a paired scale that misbehaves | vendor |
| Restart | Brief press of the battery-bay button | Described as a restart, for a stuck setup. What it keeps is not stated | vendor |
| Factory reset | Cover off; batteries out; press and hold the small button directly above the battery slots; reinsert the batteries while holding; hold at least 10 seconds; cover on; turn over | Clears all user data including stored weights and Wi-Fi networks; the scale prompts for setup. **One-way since the cutoff** | vendor for the steps (manual, <https://support.google.com/googlehealth/answer/14236515>, <https://support.google.com/googlehealth/answer/14236401>); the one-way consequence is inferred |

### What the display says

Text: `WRONG PASSWORD`; `CAN'T CONNECT` (router reached, no internet);
`NO WIFI` (router not reachable); `WEAK SIGNAL`; `CONNECTION ERROR` (cause
unknown); `!` (possible hardware fault); `400+` / `180+` / `28+` (over range);
`GUEST`. Numbers: `1` stayed on too long; `2` too much weight on one section;
`3` and `5` weigh-in could not complete; `6` weight not centred. No code 4 is
listed (vendor, <https://support.google.com/googlehealth/answer/14236805>).

Two of these matter to anyone experimenting:

- Google separates "can connect to the router but has no internet access"
  (`CAN'T CONNECT`) from a catch-all `CONNECTION ERROR`, which it describes as
  failing to connect to the Wi-Fi network for a cause it calls unknown
  (vendor). Which of the two the scale shows when it reaches a server and the
  exchange fails is not documented; record it in experiments 8 and 9.
- For `CONNECTION ERROR`, Google says that after more than four in a row you
  should wait a day before weighing again. Whether that is a retry back-off in
  the scale or a limit on the server is unknown. Keep deliberate failed syncs
  to four or fewer a day.

## What is not known

Each row is a **finding of absence**: no public source gives it. None of these
may be filled in from a neighbouring product.

| Area | Not published |
|---|---|
| Bluetooth identity | Advertised name; advertised service UUIDs; manufacturer-data company identifier; address type |
| Bluetooth setup service | The GATT table; whether the link is bonded or encrypted and by which pairing method; what the reported four-digit code is for; whether the Wi-Fi network list shown in the app comes from the scale or the phone; how the Wi-Fi password is protected in transit; whether Google's servers take part in the exchange |
| Wi-Fi identity | MAC prefix; DHCP hostname and options |
| Wi-Fi upload | Any DNS name; port; whether the transport is plain HTTP or TLS; any certificate observation; request path; payload; response contents; retry rules; how many weigh-ins are kept while offline |
| LAN side | Any listening port, mDNS or other multicast traffic |
| Firmware | Any image, update address, extraction or analysis; how an update is authenticated; any CVE or advisory; any open-source licence notice that would name its software stack |
| Interception | Any attempt, successful or failed |
| Hardware | The radio chip; the exact microcontroller; the chip under the barcode label; the function of the board's test pads; the microcontroller's read-out protection level; what the flash chip holds; which load-cell lead is which |

Do **not** borrow from neighbours:

- **Original Aria (FB201).** Its plain-HTTP upload to `www.fitbit.com` is
  documented by several projects. Nobody has pointed an Aria 2 at one of those
  servers and reported what happened. The one issue on the subject assumes the
  Aria 2 "probably uses a different API". Its Wi-Fi module, serial console and
  download mode are a different design and are not on this board.
- **Aria Air (FB203).** Bluetooth only, a different FCC filing, no Wi-Fi.
  Nothing links its GATT layout to the Aria 2.
- **Fitbit trackers.** Their proprietary Bluetooth service has been studied in
  academic work. The Aria 2 is added in the same app, so reuse would be
  unsurprising, but no source shows it, the papers never mention a scale, and
  trackers have no Wi-Fi to provision. It is a hypothesis for experiment 4,
  not a fact, and no identifier from that work belongs in a matcher for this
  scale. The next section says what that work did establish.

Firmware version strings quoted in snippets of the retired Fitbit forum:
23.21.6.0, 23.25.4.0 and 23.27.2.0 as the latest (unverified). The FCC sample's
"10.2" belongs to the unit tested in 2017 and is not in that series.

## Fitbit tracker research, and whether it applies

The nearest body of public reverse engineering is academic work on Fitbit
*trackers*. It is recorded here because the Aria 2 is added in the same app,
and because the host chip photo-read on its board comes from the same maker
as the host chip of the tracker those authors took apart. **No source links
the two.** Three papers were text-searched (IMWUT 2018, RAID 2017, TCHES
2022): the word "Aria" never appears, and "scale" appears only in the sense of
"at scale" or "large scale".

What the 2018 paper established, **for trackers**, in this note's words
(academic):

| Established for trackers | What it would mean here if the scale shared the design (inferred, unproven) |
|---|---|
| The link between app and tracker is opened by a proprietary exchange, not standard Bluetooth pairing, and that exchange has no security of its own: any device in radio range could open it and request data or deliver a server reply | An owner's own computer could probably open a link to the scale. That says nothing about being allowed to change its network |
| Tying a tracker to an account ran through the vendor's servers, with proof of presence such as tapping the tracker or typing a code it shows | First-time setup would need Google, which is the step Google says has ended. Whether a later Wi-Fi change also needs the servers is the open question (experiment 2) |
| Tracker data is encrypted with a 128-bit key set per device at manufacture. Models before 2015 could run unencrypted; Fitbit then moved them to always encrypt | A 2017 product would be expected to always encrypt, so its exchanges would be unreadable without a key held inside the device |
| A firmware update reaches a tracker inside a server reply relayed by the app, normally encrypted with that key, protected by checksums. Trackers running unencrypted accepted modified and older images over Bluetooth, and so did two early models once their key had been read out through a weakness patched in October 2017. The firmware is in two sections, a small loader and the main program, so that one can repair the other | Route 8, and why it is not available |
| The firmware contained a factory console with no authentication, able to set a tracker's serial number and key | Why route 6 says to listen to a serial line and never type into it |
| One tracker's hardware: an ST ARM microcontroller as host and a separate Bluetooth chip from another maker | The same maker as the ARM chip photo-read here. Nothing more follows |

**The service a scan should look for.** One hobbyist's published scan of a
Charge 2 tracker shows its proprietary service as
`adabfb00-6e7d-4601-bda2-bffaa68956ba`, with characteristics
`adabfb01-6e7d-4601-bda2-bffaa68956ba` to
`adabfb04-6e7d-4601-bda2-bffaa68956ba`, and a second service
`558dfa00-4fa8-4105-9f02-4eaa93e62980` (reported; one source, one tracker
model; the papers themselves do not print these values). **Whether the Aria 2
carries that service is unknown.**

The read-only scan that would settle it is experiment 4: look for
`adabfb00-6e7d-4601-bda2-bffaa68956ba` among the services the scale
advertises, and, if the scale accepts a connection without pairing, in its
service list. Write to nothing.

- Present: the scale reuses the tracker stack, and the tracker research
  becomes relevant to it, with Wi-Fi provisioning as a step no tracker had.
- Absent from the full service list: it is a different service, standard or
  bespoke, and the tracker work does not apply.
- Absent from the advertisement only: nothing is settled, because a device
  need not advertise every service it has.

Even if it is present, that UUID is shared with trackers, so it could never
identify this scale by itself; a matcher would still need the advertised name
or manufacturer data.

## How the search was done

Searched 2026-11-23 with web search plus direct fetches. Recorded so that
nobody repeats it.

| Place | How | Result |
|---|---|---|
| General web | "Aria 2" and FB202 with: reverse engineering, protocol, GATT, UUID, the common Bluetooth scanner and capture tools, traffic-interception tools, certificate pinning, TLS, hostname, DNS, DNS-sinkhole logs, firewall, teardown, chipset families, firmware, CVE, bug bounty, self-hosted, fake cloud; German-language variants | Nothing technical about the Aria 2. Hits were vendor help, reviews, original-Aria projects and Aria Air work |
| GitHub repository search | `fitbit "aria 2"` (2 repositories); `fitbit aria scale` (20, both pages); `fitbit aria 2 OR FB202` through the search API (29), repeated in the second round | No repository implements or documents an Aria 2 device protocol |
| GitHub topic `fitbit-aria` | Topic page | One repository, for the original Aria |
| helvetic issue tracker | Issue 5 | The only Aria 2 issue: opened 2023-11-19, still open, no replies |
| openScale | Issue search for "aria"; supported-scales wiki page | One issue, about the Aria Air. No Fitbit scale in the supported list |
| Gadgetbridge | Device catalogue pages | Scales page lists one unrelated family; no Fitbit or Aria anywhere |
| Hacker News | Search API: stories "fitbit aria" (9), comments `"aria 2" fitbit` (0), comments "fitbit aria" (128, filtered for protocol terms) | 2013 stories about the original Aria; one 2026 story about the Aria Air; nothing on the Aria 2 |
| Hackaday | Web search | No article |
| Home Assistant forum | Web search, one thread read | No local integration; one thread about the cloud API migration. In it, an Aria 2 owner asks on 2026-06-16 how to get the scale into Home Assistant; another user says on 2026-07-03 that their Fitbit scales (model not named) had stopped syncing, and on 2026-07-08 that a newer cloud component supports scales; a post of 2026-09-28 describes the Health Connect route |
| Lemmy, self-hosting community | One 2024 thread, post and top 50 replies | An owner of a Fitbit Wi-Fi scale asks for replacements; nobody knows a local path |
| Academic IoT traffic studies | Four device-traffic corpora (IoTFinder, IoT Inspector, the IMC 2019 Mon(IoT)r study, the IMC 2020 "Haystack" study) text-searched for Fitbit | No Fitbit scale in any |
| Fitbit tracker security papers | IMWUT 2018, RAID 2017 and TCHES 2022 papers, text-searched for "scale" and "Aria" | Trackers only; none mentions a weighing scale. The 2022 paper is mainly about Xiaomi trackers and looks at two Fitbit trackers |
| Fitbit tracker Bluetooth write-ups | One hobbyist post imitating a Charge 2 | Gives the tracker service UUIDs; no scale |
| FCC | Grant, test report, SAR report 01, internal photographs, label, cover letter, the manual as filed in 2017. Second round: external photographs, test-setup photographs, SAR reports 04 and 05 | Radio and board facts above; no protocol. The second-round exhibits are images and tables that identify no chip |
| Web search for the board's markings | "375-02" and "MDL16-0009" | Nothing |

Search hygiene: "aria2" is also the name of an unrelated download utility, and
of the project `aria2mqtt` below, so that spelling returns noise. Search for
"Aria 2" with the space, or FB202, or XRAFB202.

### What was out of reach

These are gaps in coverage, **not** negative results. Whoever continues should
start here.

- **The old Fitbit Community forum.** Every thread address now redirects to
  the generic Google Health community page. The threads are gone from the live
  web, so anything cited from them is a search snippet.
- **Internet Archive and archive.ph.** Connections were reset by the research
  session's network proxy; no archived thread could be read. A reader with
  ordinary network access should retry the Wayback Machine first, for the
  thread addresses under [Sources](#sources). They are the richest unread
  source.
- **Reddit** (the Fitbit and Home Assistant communities): refused both direct
  fetches and the search tool. Not searched at all.
- **Gadgetbridge's issue tracker** refuses automated readers; only its device
  catalogue was read.
- Two FCC mirror sites and two product-review sites answered 403.
- The Wi-Fi Alliance product finder and the Bluetooth SIG listing search are
  script-driven; no record could be read.
- GitHub issue pages were read through a page-summarising tool, and project
  READMEs as raw files, not in a browser. The second round read helvetic
  issue 5 and the aria-spoof README again and found them as described.
- A 2017 conference talk on tracker firmware by two of the papers' authors
  (<https://media.ccc.de/v/34c3-8908-doping_your_fitbit>): the recording was
  not watched and the host of its slides was unreachable. Nothing suggests it
  covers a scale.

## Community projects, and why none applies

Dates are as listed on 2026-11-23 and were not re-checked.

| Project | What it really targets | Aria 2? | Licence |
|---|---|---|---|
| `micolous/helvetic` (last update 2018-12-08) | Original Aria: replacement server for its HTTP protocol | No. Issue 5, "Aria 2 Unsupported", says so | AGPL-3.0 |
| `ads04r/aria-spoof` (archived) and the fork `reibuehl/aria-spoof` | Original Aria: pass-through proxy that logs weights | README: works with Aria firmware 39, protocol v3, and is "*not* tested with an Aria 2" | The Unlicense, a public-domain dedication (both repositories' licence files, read 2026-11-24) |
| `bigbadbob2003/aria2mqtt` | Original Aria to MQTT. **The name means "Aria to MQTT", not "Aria 2".** It needs `www.fitbit.com` redirected and handles the scale's requests on port 80 | No | MIT, as reported |
| `m322345/fitbit-aria-php-server` | Original Aria: local PHP server | README does not mention the Aria 2 | not checked |
| `ty-machine/aria-bridge` | Original Aria, FB201B named in its README: local receiver feeding Apple Health | No | not checked |
| `stephenostermiller/health`, `johnnyfleet/aria-garmin-sync` | Original Aria local data or cloud import | Not shown to be | not checked |
| `CIRdata/fitbit` | The author owns an **Aria 2**; reads weights from the **cloud** through the legacy Fitbit Web API, now switched off | Cloud only, and dead | not checked |
| `SarelBeets/donna-fitbit-health` | Reads **Aria 2** weight and body fat through the **Google Health API** | Cloud only | not checked |
| `vzaliva/google-weight-to-sheet` | Google Health API weight to a spreadsheet | Cloud only | not checked |
| openScale issue 1105 | **Aria Air** Bluetooth protocol | No | openScale is GPL-3.0, not re-checked |
| Home Assistant | No local integration. A cloud "Google Health" integration is reported to cover scales | Cloud only | — |

All repositories are under `https://github.com/`. Every "Fitbit Aria" local
server is for the original Aria. The projects that do name the Aria 2 read it
from Google's cloud. Since the cutoff was announced, new activity was found
only on the original Aria and Aria Air sides; **no Aria 2 project has
appeared** (not found).

## Hardware, from the FCC photographs

No independent teardown names a chip. The only board image is one photograph
in the FCC internal-photographs exhibit. Everything in the table is
**photo-read**: separate passes of this project's research examined crops of
that photograph, at least two for every row, and agree except where a row
says otherwise. Nothing was checked against a unit, and a part being on the
board says nothing about what can be done through it.

| Part | What the photograph shows | What is not legible or not known |
|---|---|---|
| Layout | One main board in the centre of the base; a three-cell battery holder; a flat-flex connector for the display; two small antenna boards on thin coaxial leads to two connectors on the main board | — |
| Board markings | "375-02 Rev2 - 10/2016" and "MDL16-0009" | A web search for either marking returns nothing |
| Host microcontroller | A quad-flat chip of about 64 leads carrying the word "ARM" and an ST mark: an ST-made ARM microcontroller | The part number. One further look, by the reviewer of this note's first draft, found the ST and ARM marks faint: consistent with the reading, not independently legible |
| Second large chip | A larger quad-flat chip entirely under a two-dimensional barcode label | Maker and type |
| Flash memory | An eight-lead small-outline chip with the Macronix logo. Serial flash is inferred from the maker and the package | The part number. One pass read the start of one; the pass that checked it would not rely on the digits |
| Power | A small TI-logo part marked "62736", consistent with a low-power step-down converter (inferred) | — |
| Radio | Beside the two antenna connectors, an unmarked rectangular component with a small metal-can part next to it. It is the most likely position of the Wi-Fi and Bluetooth radio | Everything. **The radio chip is unidentified, and this note names no candidate** |
| Button | A tactile push-button at the board edge nearest the battery holder, matching the manual's "small button directly above the battery slots" | — |
| Test pads | Bare round pads with no labels. The readings differ. The two latest looks, on full-resolution crops (the review of this note's revision, repeated when that review was checked), read **two groups**. One is by a long edge of the board, between the two large chips: ten pads in an aligned two-by-five grid, between four large holes, with two small holes at one end and one at the other; the smaller gold dots around them have drill holes and are read as vias. The other is in the corner by the positive battery contact: six pads in a two-by-three grid with the same arrangement of holes, less sharp in the photograph. Earlier readings recorded one cluster "in two offset rows, flanked by tooling holes" and counted 11 or 12 pads in one pass and 10 to 14 in another | Any label. What each pad carries, and which chip each group serves, is unknown. What the holes are for is not stated anywhere |
| Load cells | Four, joined to the board by coloured leads on solder pads along both long edges. Conventional strain-gauge cells (inferred from the wiring) | Which lead is which |

This is not the original Aria's hardware. No Wi-Fi module of the kind the
FB201 uses is visible, so nothing documented for that module applies here.

Opening it (reported, iFixit disassembly guide, 2021-12-06): the label in the
battery bay hides two Torx T10 screws; the plastic base then pries off the
glass. The guide identifies no chips.

## Where sources disagree

| Subject | One source | Another | Reading |
|---|---|---|---|
| Aria 2 security updates ended | "2022" (help notice) | "until at least September 2023" (security table) | Both Google; unresolved |
| When the cutoff bites | 2026-11-09 (Google's English notice since 2026-11-23) | 2026-11-28 (the English notice before that; eight other language editions on 2026-11-24; the press article of 2026-11-20, which also reports owners already refused) | Unresolved between Google's own editions. 9 November matches the 5.12 rollout and the timestamp of the original Aria's replacement page. 28 November is also Google's date for a different change, third-party apps on Fitbit smartwatches, which was announced on 9 November; whether the two notices were ever linked is not said. The press example is the original Aria's web flow; nothing shown for the Aria 2. For an owner the safe reading is the earlier date: it has ended |
| Does a Wi-Fi change count as re-pairing? | Not defined in the notice; Google's own wording calls the network change setup and pairing | Yes (press assertion) | Unresolved. The vendor wording points towards yes (inferred); experiment 1 |
| Is logging the in-app Wi-Fi change safe for a scale you depend on? | The first draft of this note put it among experiments not safe for such a scale, because nobody knows what a refused change leaves behind | The second round and its check rate the capture read-only, with no risk to the scale or the pairing | Both hold: the log is read-only, and the change it records is untested since app 5.12. Route 2 states both, and rates the route as a whole by the stricter of the two: unknown |
| Legibility of the host chip's marks | Three passes of this project's research read "ARM" and an ST mark | One reviewer found them faint in a fresh crop | Consistent, not independently confirmed; the part number is illegible to all |
| Number and layout of test pads | One cluster in two offset rows: 11 or 12 pads in one reading, 10 to 14 in another | Two groups in aligned grids, ten pads and six (the two latest looks, on full-resolution crops) | Readings differ and all are kept. The latest readings take the earlier counts to include the small drilled dots beside the pads, which they read as vias (inferred). A spare unit settles it (experiment 10) |
| When Fitbit-account sign-in ended | After 2026-05-19 (Google's help pages) | "In September", with app version 5.08 (one press article) | Not resolved; possibly the policy date and the app change. Either way a build from before then may not sign in (route 3) |
| Wi-Fi modes | b/g/n (vendor, and the FCC report tested g and n) | "802.11b only" (a low-quality guide site) | The guide repeats the original Aria's limit; treat it as wrong |
| Batteries | Three AA (vendor; the FCC photograph shows a three-cell holder) | "Four AA" (a search summary of one 2017 review; page unreadable) | Vendor and photograph win |
| Maximum Wi-Fi power | 19.1 dBm measured (test report) | 19.5 dBm (SAR report, maximum tune-up value) | Different quantities, not a conflict |
| Maximum weight in kilograms | 181.4 kg (manual) | 180 kg (help page and display) | Rounding |

## Open questions

None is answered by any public source.

**Bluetooth.** Advertised name and service UUIDs. When it advertises. The GATT
table. Bonding and pairing method. Whether a four-digit code exists and what it
proves. Who scans for Wi-Fi networks. How the password is protected. Whether
the cloud must approve or sign anything during provisioning: this decides
whether setup without Google is even conceivable.

**Wi-Fi.** MAC prefix. DHCP hostname and options. DNS names. Ports. Plain HTTP
or TLS. If TLS: version, server name, whether certificates are validated or
pinned, and what clock the scale uses to judge validity. Request path and
payload encoding. Whether anything resembles the original Aria's upload. What
the response carries. Retry and back-off rules. How many weigh-ins are kept
offline. Any listening port or multicast traffic.

**Lifecycle.** Which of Google's two published dates, 2026-11-09 or
2026-11-28, its systems enforce for the Aria 2. Whether the in-app "Wi-Fi
Network" item still works for a paired scale on app 5.12 and later. Whether
the block is in the app, on Google's
servers, or both: an app-side block might be sidestepped by another client, a
server-side one could not. Whether a paired scale rejoins a cloned network.
Whether a brief button press keeps settings. Whether flat batteries can lose
the Wi-Fi settings. Whether a person removed from the scale can be added back.
How long Google keeps the sync service running.

**Hardware.** Microcontroller, radio and flash part numbers. What the test
pads carry.

Added by the second round, each with the cheapest experiment that settles it:

| Question | Cheapest experiment |
|---|---|
| Does the scale carry the Fitbit tracker service `adabfb00-6e7d-4601-bda2-bffaa68956ba`? | 4: a passive scan; nothing is written |
| Does the scale offer any weight over Bluetooth at all? Not expected | 4: the optional service listing |
| Does changing the network on a paired scale need anything from Google's servers, or is it an exchange between phone and scale only? | 2: the Bluetooth log with a router log beside it. It may already be impossible |
| Is the pairing block in the app, on the servers, or both? | 7: a setup attempt on a scale that is already unpaired, with the current app and with a build older than 5.12 |
| What does the app ask the owner to do to the scale during a Wi-Fi change? | 1 shows whether the control exists; 2 shows the rest |
| Does the scale ever contact a server other than at a weigh-in, for example to check for firmware, and where? | 3, left running over several days. Look only; never answer it |
| Does the scale accept firmware over Bluetooth at all? | Not something to test on a scale you keep. 2 and 4 may show a service that carries it; never provoke an update |
| How many pad groups are there, which pad carries what, and is a debug port, a boot-select pin or a serial line among them? | 10: a continuity map of both groups on an opened spare with the batteries out |
| What is the microcontroller's read-out protection level? | 11: one identity read and one read attempt on a spare; stop at the first refusal |
| Is there a serial console, and does it say anything? | 11: listen only |
| What does the flash chip hold? | 12: a clip-on read on a spare |
| Can a second amplifier share the load cells with the Fitbit board? | 13: on the bench, on a spare |
| Which chip is the radio, and what is under the barcode label? | 10: photographs of an opened spare |

## Experiments an owner can run

Rules for whoever runs these and writes them up:

- Observe **your own** scale and network only.
- Before anything is sent to this project, replace your LAN addresses,
  hostnames you set, network name, Wi-Fi password, serial number and account
  identifiers with placeholders. Of a MAC or Bluetooth address, report **only
  the first three bytes**: that prefix is a wanted fact, the rest identifies
  your unit.
- Send facts, never the capture file. A Bluetooth log of a Wi-Fi change may
  hold your Wi-Fi password in whatever form the app sends it.
- Keep deliberately failed syncs to four or fewer a day.
- On a scale you want to keep: never unpair it, never reset it, never press
  or hold its button, never write to anything over Bluetooth, and never
  answer a request from it that looks like an update check.

The order is by value now that pairing has ended: first what can only be
captured while it still exists, then what an owner most needs answered, then
what the catalogue needs, then work that needs a scale with nothing to lose.

| # | Experiment | What it touches | Who should run it |
|---|---|---|---|
| 1 | Look at what the app offers | Nothing | Every owner, now |
| 2 | Log the app's own Wi-Fi change | The log: nothing. The change it records: the scale's network settings, through Google's own control | Anyone about to change network anyway; a spare; an owner who accepts the stated unknown |
| 3 | Passive network log of one weigh-in | Nothing | Any owner who can log at the router |
| 4 | Passive Bluetooth scan, with a look for the tracker service | Nothing; the optional connect step is not passive | Any owner with a scanner |
| 5 | Cloned-network test | The scale's network, for a while | Any owner with a second access point |
| 6 | Offline behaviour | The scale's network, for a day | Any owner |
| 7 | Setup attempts, current app and an older build | Whatever the scale still holds | **Only** a scale that is already unpaired or reset |
| 8 | Certificate test | What the scale's sync reaches | Not a scale you depend on |
| 9 | Pass-through capture | What the scale's sync reaches | Not a scale you depend on |
| 10 | Board photographs and a pad map | The case | An opened spare |
| 11 | Debug-port identity read, serial listen | The board | An opened spare; advanced |
| 12 | Clip-on read of the flash chip | The board | An opened spare |
| 13 | Load-cell tap on the bench | The cell wiring | An opened spare |

Experiments 1 and 3 to 6 use none of the app's setup, network or removal
functions and never press the scale's button, so they leave the pairing and
the account link alone. Two limits on that, both because nobody has tested
them on this scale: experiments 5 and 6 take the scale's network away for a
while, and that its stored Wi-Fi settings survive failed joins is inferred
(Google's troubleshooting assumes a scale survives a router restart); and the
optional connect step in experiment 4 has an unknown effect on the scale.

### On a paired scale

**1. Look at what the app offers. One minute, no risk; do it now.**
Open Connections, then Aria 2. Note the app version, the date, and whether
"Wi-Fi Network" or "Pair Scale to Different Network" is offered. Look at the
"Add device" list and note whether the Aria 2 is still listed. **Look, do not
tap through either one.** A second look a week or two later costs another
minute. The other language editions still say 28 November, so it would show
whether anything changes then. That date is not a deadline: by the English
notice the change has already happened.
*Settles:* the first dated evidence on whether the block has reached the
Aria 2, and whether the Wi-Fi change survives app 5.12.
*Catalogue publishes:* a dated observation in this note and in the owner
guidance. No spec yet.

**2. Log the app's own Wi-Fi change. For an owner who must change network
anyway, a spare, or an owner who accepts the unknown stated below; and only
if experiment 1 shows the control is still offered. Then at once, because it
may be gone tomorrow.**

**Before you tap:** the log is read-only, but what it records is the app
changing the scale's network. Nobody has published a run of that since app
5.12. If the app starts the change and is then refused or interrupted, nobody
knows what the scale is left holding, and a lost network can no longer be
repaired by re-pairing. If the app asks you to remove the scale, reset it,
press or hold its button, or set it up as new, stop and back out: nobody has
published what even a brief press of the button keeps.

How: on an Android phone, switch on the developer option that logs Bluetooth
traffic ("Enable Bluetooth HCI snoop log") and turn Bluetooth off and on.
Start the router log of experiment 3 for both the phone and the scale. In the
app: Connections, Aria 2, "Wi-Fi Network" or "Pair Scale to Different
Network", Next, and enter the **same** network the scale is already on. Let
it finish, weigh once, and wait for the check mark. Then export the log (it
is inside an Android bug report) and read it in a protocol analyser. No
method is given here for an iPhone.

Record: which services and characteristics the app uses, and whether one is
`adabfb00-6e7d-4601-bda2-bffaa68956ba`; whether the link is encrypted;
whether the phone contacts Google's servers during the exchange, from the
router log; whether the network name and password cross in clear (say yes or
no, do not send them); what the scale then does on Wi-Fi; what its display
shows; and what the app asked you to do to the scale.

The log holds your network name and password, the scale's Bluetooth address
and serial number, and possibly an account token. Keep the file; send only
derived facts.

*Settles:* whether changing the network is a local exchange between phone and
scale or needs a round trip to Google; which characteristics carry it;
whether the link is encrypted; in practice, whether "re-pair" covers the
Wi-Fi change.
*Catalogue publishes:* the provisioning stage of the spec's setup block. If
the exchange is local, this is the fact that lets an owner move a paired scale
to a new network without Google, and it would be worth a setup spec of its
own.

**3. Passive network log of one normal weigh-in. Highest value to the
catalogue, and only possible while Google's servers still answer.**
Log DNS at your resolver and capture the scale's traffic at the router or a
mirrored switch port. Step on; wait for the check mark. Record: the first three
bytes of the scale's MAC; DHCP hostname, vendor class and requested options;
every DNS name it asks for; destination ports; whether it asks for the time;
for plain HTTP, the request line, header names and body length; for TLS, the
protocol version, the server name it sends, and the issuer of the certificate
it is shown; any broadcast or multicast traffic; total bytes each way. Do it
twice to see what is constant. If the log can be left running for several
days, note any contact that is not a weigh-in. Look only: never answer it.
*Settles:* which names the scale depends on, HTTP or TLS, any resemblance to
the original Aria (visible at once if it is plain HTTP), and the first
identifiers a matcher could use.
*Catalogue publishes:* **an identify-only spec**,
`device-specs/devices/fitbit-aria-2.yaml`, with the observed prefix in
`identification.mac_prefixes` and each observed name in `cloud.egress` as
`verification: reported`. The sync name would be entered with
`when_blocked.impact: breaks`, so that no generated blocklist ever sinkholes
the one name a paired scale needs. If the prefix turns out to be registered to
another company rather than to Fitbit, as both prefixes seen on original Arias
are, it is published with that caveat, because it then also matches unrelated
devices.

**4. Passive Bluetooth scan, with a look for the tracker service. No
writes.**
With a Bluetooth scanner, check whether the scale advertises when idle, when
stepped on, and just after a weigh-in. Do not press the button. Record the
advertised name, service UUIDs, manufacturer-data company identifier, address
type and whether it is connectable. Note in particular whether
`adabfb00-6e7d-4601-bda2-bffaa68956ba` is among the advertised services. The
scan is the safe part. Optional, and no longer passive: if it is connectable,
connect, decline any pairing prompt, list the services and characteristics
with their properties, read the standard device-information strings, and
disconnect. Note whether the tracker service, its neighbour
`558dfa00-4fa8-4105-9f02-4eaa93e62980`, or any standard weight service is in
the list. Write to nothing, and do not switch notifications on: that is a
write. **The effect of a connection from an unknown device on this scale is
not documented by anyone; that it is harmless is inferred. Skip the connect
on a scale you depend on.**
*Settles:* an identity matcher on the setup radio; whether the scale reuses the
Fitbit tracker service; whether any weight is offered over Bluetooth.
*Catalogue publishes:* the Bluetooth identification for the identify-only spec
(`identification.local_name_prefix`, `manufacturer_data`, and service UUIDs
only where they are specific to the product). Either experiment 3 or 4 alone is
enough to publish that spec.

**5. Cloned-network test. Highest value to owners.**
Bring up a second access point with the identical network name, security mode
and passphrase; switch the original off; weigh in. Does the scale join and show
its check mark? If you can, vary one thing at a time: another channel,
WPA2-only against a WPA2/WPA3 mixed mode, 802.11b rates disabled.
Switch the original back on afterwards.
*Settles:* whether a router replacement can be survived with no app at all.
*Catalogue publishes:* the answer to the router-replacement question
(`setup.rejoin` in the spec), and the "untested" label comes off route 1 and
the owner guidance above.

**6. Offline behaviour.**
With the access point off, weigh in. Does the display show weight only, or
body fat as well, for a recognised person? Weigh three or four times over a
day, no more, writing each reading down by hand, since it is not known whether
the scale keeps them. Restore Wi-Fi, weigh once, and count what reaches the
account and whether the times are right.
*Settles:* whether offline weigh-ins are kept at all, a lower bound on how
many, and how useful a stranded but still configured scale is.
*Catalogue publishes:* the buffering and standalone behaviour as reported
facts in the spec's notes.

### Only on a scale that is already unpaired or reset

**7. Setup attempts, with the current app and with a build older than 5.12.**
**Never unpair or reset a working scale to run this.** A failed attempt costs
no pairing, because none is left. One thing may be at stake: a scale that was
removed from the account but never reset may still hold its people and its
network, and whether a failed setup clears them is not documented.
First scan the scale as in experiment 4, since its setup state may advertise
differently. Then attempt setup in the current app with the Bluetooth log and
the router log of experiment 2 running, and note exactly where it is refused.
Then, if you have a phone or tablet whose app is older than 5.12, attempt it
there with the same logs. Do not expect it to work. Press reports say old
builds are being shut out (reported; route 3), so the older app may refuse to
run, or insist on updating, before it reaches setup; if it does, that is the
result to write down. See the three cautions under route 3 before installing
an app from anywhere but the official store.
*Settles:* where the block lives. Refused before any Bluetooth traffic means
the app; refused after an exchange with the scale and a server round trip means
the servers. An older build getting through would mean the block is in the
app.
*Catalogue publishes:* the pairing and setup blocks of the spec, with the
refusal point as a dated fact; and, if an older build pairs, that as a dated
owner route with its conditions.

### Changes what the scale talks to: not for a scale you depend on

While either of these is running, the scale's sync depends on your equipment
and not on Google's. Each failed attempt is a failed sync, and nobody has
published what repeated failed syncs do to an Aria 2. That is why they are
for a spare, or for an owner who accepts it, four or fewer a day.

**8. Certificate test.** Only if experiment 3 showed the upload is TLS; if it
showed plain HTTP, skip to experiment 9. Point the observed name at a TLS
listener you run, by a DNS override scoped to the scale, one case per attempt:
a self-signed certificate; a certificate for the right name from an authority
you created; a publicly trusted certificate for a different name; an expired
certificate. For each, record whether the scale completes the handshake and
sends a request or aborts, the alert it gives, and what the display says.
The listener only completes or refuses the handshake: it sends no reply, and
it never answers anything that looks like an update check.
Remove the override afterwards and confirm a normal sync.
*Settles:* whether the scale checks who it is talking to, and so whether a
local stand-in is possible at all.
*Catalogue publishes:* if the scale refuses everything but the vendor's server,
the spec records that door as closed, with the evidence, and
`local_access.status` stays `none_known`. If it accepts one, experiment 9
becomes possible.

**9. Pass-through capture.** Only if experiment 3 showed plain HTTP, or
experiment 8 showed the scale accepts a certificate that is not the vendor's.
Relay the sync through your own host while still forwarding to the
real server, and record request and response. Forward rather than answer
locally until the response is understood, so the scale's user table is never
lost. **Never alter or invent a reply that tells the scale an update is
available**: a wrong or cut-off image could leave it unable to start, and no
image exists to restore it.

**A genuine update can arrive while the relay is in the path.** The scale
updates itself, and while it syncs through your host anything the real
server starts travels through it. How this scale fetches an update is not
known to anyone, so this is this note's reasoning and not an observation
(inferred). Three rules follow:

- Relay every request and every reply unchanged and whole, not only the
  weigh-in upload.
- If your relay cannot pass a large download whole, do not run this
  experiment: a relay that drops a transfer part-way could leave the scale
  with the cut-off image described above.
- If the scale shows its updating icon, leave the relay, the network and the
  batteries alone until it finishes, and do not step on. Google's icon table
  says of that icon: "Wait until the process completes before stepping on"
  (vendor, <https://support.google.com/googlehealth/answer/14236805>).

*Settles:* the upload and response formats.
*Catalogue publishes:* possibly more than identify-only: an owner-run server
contract of the kind the original Aria has, with independent test vectors.

### Case open: an opened spare only

The two rules under
[Case open](#case-open-bench-work-on-a-spare-never-on-a-scale-you-depend-on)
apply to all four: nobody stands or presses on the scale while anything is
attached, nothing powered from the mains is in circuit with a person, and
facts are reported, never memory contents.

**10. Board photographs and a pad map.** Photograph every chip marking: the
host chip's part number, the flash chip's part number, the unmarked component
by the antenna connectors. The barcode label hides one chip; peeling it is for
a unit you are prepared to lose. Photograph the test pads square-on and say
how many groups there are and how many pads in each: the readings of the FCC
photograph differ (one cluster, or a group of ten and a group of six). With
the batteries out and a meter only, trace each pad in every group to the chip
pin it reaches. Report part numbers and pad functions only.
*Settles:* the radio and microcontroller; how many pads there are and what
they carry; whether a debug port, a boot-select pin or a serial line is
brought out.
*Catalogue publishes:* hardware facts on the device page.

**11. Debug-port identity read and a serial listen. Advanced.** Only after
experiment 10 has identified the pads. Attach a debug probe and read the
chip's identity code. Attempt one read of the program memory. **If it is
refused, stop: read-out protection is on. Never issue the command that turns
it off. That erases the chip, there is no Aria 2 image to put back, and the
scale is dead for good.** The built-in serial loader is behind the same
protection and ends the same way. On any serial line found, listen only:
ground and the adapter's receive line, never its transmit line, after
measuring the board's logic voltage.
*Settles:* the read-out protection level; whether a console exists and what
it prints at start-up.
*Catalogue publishes:* hardware facts only. No image or code.

**12. Clip-on read of the flash chip.** With the batteries out, clip a
serial-flash reader onto the eight-lead chip and read it twice; the two reads
must match. Do not write. Treat the dump as a secret: it may hold your network
password and account material. Report what kinds of data it holds, not the
data.
*Settles:* what the external flash holds, and whether a firmware image or the
stored network lives there.
*Catalogue publishes:* derived facts only.

**13. Load-cell tap on the bench.** On the table, with the Fitbit board still
connected and running from its batteries, connect a hobby load-cell amplifier
across the cell wiring without cutting anything. **The amplifier and whatever
reads it both run from batteries, with no lead to a computer or anything else
plugged into the mains**, because a fault there could reach whoever touches
the scale. Load the platform with known weights set down on it, not by
pressing with a hand or standing on it: with the Fitbit board running, its
measuring current can reach whoever touches the glass (inferred from the
vendor's description of how it measures body fat). Does the amplifier read a
load, and does the scale's own reading stay right?
*Settles:* whether the less destructive fallback exists; which lead is which.
*Catalogue publishes:* the wiring facts, and whether route 11 is real.

### What moves this note

| Result | The catalogue publishes |
|---|---|
| Any one observed matcher (experiment 3 or 4): a MAC prefix, an advertised Bluetooth name, product-specific service UUID or manufacturer data | An identify-only spec and device page: identity, vendor-documented setup and reset with their basis, the cloud dependency, the owner guidance above |
| Experiment 5 | The router-replacement answer, tested |
| Experiment 2 shows a local exchange | Possibly a Wi-Fi re-provisioning spec |
| Experiment 7: an older build pairs | A dated owner route for stranded scales |
| Experiment 8: every stand-in refused | The same spec, with the Wi-Fi door recorded as closed |
| Experiment 9 succeeds | Possibly an upload-server spec |

Experiments 1, 3, 4 and 5 together take under an hour and do not touch the
pairing.

## Sources

Read 2026-11-23. "Live" means the address answered 200 to a plain fetch at the
end of that day. The first three pages, the sync-troubleshooting page, and the
addresses marked "added 2026-11-24" were fetched on 2026-11-24 between
00:22 and 00:30 UTC; the three notice pages, "About Fitbit Aria 2" and the
sync-troubleshooting page once more at 01:54 UTC. The three notice pages were
fetched again at 03:10 UTC, together with the addresses marked "added
2026-11-24, 03:10".

| Source | What it gave | State |
|---|---|---|
| <https://support.google.com/googlehealth/answer/14236805> | "How do I use my Fitbit scale?" Covers Aria, Aria 2 and Aria Air: the cutoff notice, the guest advice that ends in a factory reset, the Wi-Fi change, the icon and error tables | Live. English notice on this page: November 28 at 2026-11-23 05:11, 05:44 and 06:01 UTC, November 9 at 22:33 UTC and in every later fetch, the last at 2026-11-24 03:10 UTC (the 06:01 and 22:33 readings are saved copies; see [The cutoff](#the-cutoff)) |
| <https://support.google.com/googlehealth/answer/14236818> | "Set up your Fitbit device" (other Google pages link to it as "How do I set up my Fitbit device?"). Covers all three scales: the notice again, Aria 2 router requirements and setup, the hotspot note about updates, the steps for removing a device from an account | Live |
| <https://support.google.com/googlehealth/answer/14236515> | "How do I erase my Fitbit device?" Covers all three scales: the notice again, the Aria 2 erase steps | Live |
| <https://support.google.com/googlehealth/answer/14236401> | "About Fitbit Aria 2". Aria 2 only: users, modes, erase steps. Says nothing about firmware or updates | Live |
| <https://support.google.com/googlehealth/answer/14237221>, <https://support.google.com/googlehealth/answer/14236618> | How devices sync; "Fix syncing issues with Google Health", the sync troubleshooting, including the advice to remove other Fitbit devices and to disconnect and re-add a device | Live |
| <https://support.google.com/googlehealth/answer/14236615> | Exporting Google Health data | Live |
| <https://support.google.com/googlehealth/answer/14506680> | "How do I use Health Connect with the Google Health app?" The table of data types the app can read from and write to Health Connect | Live; added 2026-11-24 |
| <https://support.google.com/product-documentation/answer/15181553> | Security-update end dates | Live |
| <https://support.google.com/googlehealth/blog/475060763>, <https://support.google.com/googlehealth/thread/478477332> | Google Health app 5.12 and 5.13 rollout posts. Neither mentions a scale; the 5.13 post repeats the 28 November date of the smartwatch app change | Live |
| <https://support.google.com/googlehealth/thread/477099339>, <https://support.google.com/googlehealth/answer/14237121> | Google's post announcing the end of third-party apps and clock faces on Fitbit smartwatches from 28 November 2026, timestamped 2026-11-09 20:35 UTC; the help page that repeats it. Neither mentions a scale. Recorded only because the scale notice has carried both of those dates | Live; added 2026-11-24, 03:10 |
| <https://storage.googleapis.com/support-kms-prod/maAIG2kfodcmEajCR4DmV73m2pVsfok940UY> | **Aria 2 (FB202) manual**, 31 pages, PDF dated 2023-06-22: the newest edition found. Its text does not extract; its factory-reset page was read by rendering it | Live, 3.9 MB |
| <https://staticcs.fitbit.com/content/assets/help/manuals/manual_aria_2_en_US.pdf> | **Aria 2 (FB202) manual**, older edition, 30 pages, PDF dated 2019-01-25, with readable text. The manual quotations above, including the sentence on automatic firmware updates, come from this edition | Live, 6.7 MB. Some downloads through the research session's proxy were cut short at 6.3 MB; fetch it from an ordinary network |
| <https://fccid.io/XRAFB202> | FCC record for the Aria 2: grant, exhibit list, confidentiality | Live |
| <https://fccid.io/XRAFB202/Test-Report/DTS-Report-3510920.pdf> | Radio test report R105487 Rev 1 | Live |
| <https://fccid.io/XRAFB202/Test-Report/SAR-report-01-3510912.pdf> | SAR report 01: sample revision, antenna chains | Live |
| <https://fccid.io/XRAFB202/Internal-Photos/Internal-Photos-3510908.pdf> | Board photographs: the one board image every photo-read fact comes from | Live |
| <https://fccid.io/XRAFB202/Label/Label-3510909.pdf> | Label and its location | Live |
| <https://fccid.io/XRAFB202/User-Manual/Users-manual-3510922.pdf> | The Aria 2 manual as filed with the FCC: first edition, 21 pages, PDF dated 2017-08-14. Reference only; the two editions above are the owner manuals | Live |
| <https://blog.google/products-and-platforms/devices/fitbit/fitbit-introduces-aria-2-smart-scale/> | Launch post, 2017-08-28 | Live |
| <https://www.fitbit.com/pdfs/doc/CE_DoC_FB202_Aria2_Updated_102020.pdf> | EU declaration of conformity | Live |
| <https://developers.google.com/health/about>, <https://developers.google.com/health/data-types> | Web API switch-off and the statement that all Google Health API scopes are restricted; the data types and their compatible devices | Live |
| <https://developers.google.com/health/app-verification> | The 100-user limit for an unverified app | Live; added 2026-11-24 |
| <https://dev.fitbit.com/build/> | The older banner that still gives 2026-10-30 for the Web API switch-off | Live |
| <https://support.google.com/product-documentation/answer/14226283> | Phone requirements of the Google Health app | Live |
| <https://support.google.com/googlehealth/answer/17068213>, <https://support.google.com/googlehealth/answer/14237024> | "Changes in the Google Health app": the Fitbit app became the Google Health app on 2026-05-19. "How to move your Fitbit Account to a Google Account": Fitbit-account sign-in ended after that date | Live; added 2026-11-24 |
| <https://aria1.fitbit.com/> | The "Aria is no longer supported" page that the original Aria's web setup address now redirects to | Live |
| <https://gadgetsandwearables.com/2026/11/20/fitbit-aria-support-cutoff-early/> | Press report of the early cutoff | Read earlier that day; later fetches met a bot check. Blocked to scripts, not dead |
| <https://gadgetsandwearables.com/2026/06/25/google-is-about-to-kill-the-old-fitbit-app-workaround/>, <https://gadgetsandwearables.com/2026/10/11/fitbit-holdouts-forced-google-health-update/> | Press reports, same outlet, published 2026-06-25 and 2026-10-11: app versions older than 5.0 said to stop working on 2026-07-15; owners on the old app met by update prompts; app version 5.08 said to have removed Fitbit-account sign-in in September. The basis of the third caution under route 3 | Live; added 2026-11-24, 03:10 |
| <https://www.ifixit.com/Guide/Fitbit+Aria+2+Disassembly/146762> | Disassembly guide (CC BY-NC-SA; facts only) | Live |
| <https://github.com/micolous/helvetic/issues/5>, <https://github.com/oliexdev/openScale/issues/1105> | The Aria 2 issue; the Aria Air issue | Read through a page-summarising tool. The second round read the helvetic issue again: open, no replies. GitHub pages answer 403 to this session's scripts: blocked, not dead |
| Project READMEs named in the table above | Whether each concerns the Aria 2 | Read as raw files earlier that day. The aria-spoof README was read again in the second round, and the licence files of both aria-spoof repositories on 2026-11-24 |
| <https://lemmy.world/post/23147220> | Self-hosting thread, 2024-12-14 | Read through its API; 403 to a plain fetch |
| <https://community.home-assistant.io/t/fitbit-migration-to-google-health/1010341> | Cloud API migration thread | Read through a page-summarising tool on 2026-11-23, when plain fetches got 403; read directly on 2026-11-24, when it answered 200 |
| <https://homepages.inf.ed.ac.uk/ppatras/pub/imwut18.pdf> | IMWUT 2018 paper on Fitbit tracker security: the source of every "academic" statement above. No scale in it | Live; text-searched again 2026-11-24 |
| <https://arxiv.org/pdf/1706.09165> | RAID 2017 paper on Fitbit tracker security; no scale in it | Live |
| <https://nebelwelt.net/files/22CHES.pdf> | TCHES 2022 paper on fitness-tracker security: Xiaomi trackers and two Fitbit trackers; no scale | Live; added 2026-11-24. The same path under `www.` fails its certificate name check, and an earlier pass recorded the download as failed |
| <https://remyhax.xyz/posts/adventures-in-bluetooth-2/> | A hobbyist's write-up of imitating a Charge 2 tracker: the tracker service and characteristic UUIDs, as seen in a scan of one tracker. No scale. Facts only | Live; added 2026-11-24 |
| <https://media.ccc.de/v/34c3-8908-doping_your_fitbit> | Recording page of a 2017 conference talk on tracker firmware | Live; added 2026-11-24. Not watched; listed for whoever continues |

Unread threads of the retired Fitbit forum, known only as search snippets
(unverified). Each address now redirects to the Google Health community home;
try the Wayback Machine:

- `https://community.fitbit.com/t5/Aria-Scales/How-does-Aria-2-actually-use-Bluetooth/m-p/4088125`
  — what Bluetooth is used for.
- `https://community.fitbit.com/t5/Aria-Scales/Does-the-Aria-2-store-data/m-p/4498046`
  — owners saying offline weigh-ins appeared later. (The "16 weigh-ins" figure
  that circulates belongs to the original Aria; do not transfer it.)
- `https://community.fitbit.com/t5/Aria-Scales/Aria-2-can-t-be-set-up-through-my-Windows-10-laptop/td-p/4098606`
  — setup from a Windows PC, and the four-digit code.
- `https://community.fitbit.com/t5/Aria-Scales/Can-t-set-up-my-Aria-2-with-a-laptop-s-Bluetooth/td-p/4414273`
  — owners whose setup failed from a Windows PC and succeeded from a phone.
- `https://community.fitbit.com/t5/Aria-Scales/Aria-2-displays-a-quot-Connection-Error-quot-message/td-p/3383540`
  and
  `https://community.fitbit.com/t5/Aria-Scales/Tips-for-the-Aria-2-Connection-Error/m-p/3834928`
  — owners' accounts of connection errors on particular networks.
- `https://community.fitbit.com/t5/Aria-Scales/What-is-the-current-firmware-version-of-Aria-2/td-p/2550295`
  — firmware version strings.
- `https://community.fitbit.com/t5/Aria-Scales/Fitbit-Aria-2-firmware-update-inquiry/td-p/5374199`
  — a 2023 question about firmware updates; the other source of the version
  strings.

Not done, by rule: no vendor app, package or firmware image was downloaded;
nothing was decompiled; no fetched code was run; no address was guessed and
probed.
