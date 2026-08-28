# Baofeng UV-5R family — serial programming and its band limits

## Target metadata
- target_id: baofeng-uv5r-family
- app package_id(s): TBD (no vendor mobile app; the manufacturer ships a
  Windows CPS, and third-party open-source tools cover the protocol)
- device class: handheld VHF/UHF transceiver
- transport(s): USB serial over a K-plug cable, 9600 baud
- local-only viability: **high**. Cable, flat memory image, no network.

Members: the UV-5R itself and the many radios that program identically —
BF-F8HP, UV-82, GT-5R, the GMRS UV-5G, and the AR-152, which is reported to
program as a BF-F8HP.

This is the *older* family. It is not the UV-17Pro protocol and shares none of
its framing. Documented here because it is the family with a software transmit
range, and because a cable transport is the obvious next slice.

## Known facts (public + observed)
Derived from CHIRP's published driver. Nothing here has been read off a radio
by this project.

- **Session**: a binary ident sequence at 9600 baud, acknowledged with 0x06.
  The reply identifies the variant, including which of two firmware
  generations the radio is.
- **Framing**: single-letter opcodes with a 16-bit address and a length —
  `S` to read a block and `X` to write one, in 0x40-byte blocks. No byte
  substitution: this family sends its blocks in the clear.
- **Memory**: a flat image of 0x1808 bytes, holding 128 memory channels.
  Channel names are seven characters and live in their own block, separate
  from the channel records — unlike the newer family, where the name is
  inside the record.
- **Band limits exist here, and are editable.** The settings region carries,
  per band, a lower bound, an upper bound and an enable flag, in one of two
  layouts depending on firmware generation. They sit in the aux area around
  0x1FC0. These fields are what a "MARS/CAP modification done in software"
  actually edits, and they are exposed by ordinary programming tools.

## Device discovery signals
- USB: a K-plug cable presenting a generic USB-serial bridge. Common bridge
  chips are the usual CH340/CP210x/PL2303 family, and counterfeit PL2303
  clones are a well-known source of "the cable does not work on this OS"
  reports. The bridge identifies the cable, not the radio.
- No BLE. No network presence of any kind. Radios in this family that are
  programmed over Bluetooth do it through a separate dongle — see
  [radio-bt-programming-adapters.md](radio-bt-programming-adapters.md).

## Threat model + guardrails
- Scope: only radios the operator owns.
- Writing is destructive if it goes wrong. Read and store the existing image
  first; offer to restore it.
- **On the transmit-range fields, and a departure from a sibling target.**
  [ifreqtech-speaker-mic.md](ifreqtech-speaker-mic.md) sets an explicit
  non-goal: *"will NOT implement any functionality that modifies the radio's
  frequency, power, or other regulated parameters."* That is the right rule
  for the device it was written about — a Bluetooth speaker-mic, where the
  only way to touch a regulated parameter is by accident, and the hazard is a
  PTT bridge keying a transmitter nobody is holding.
  It is the wrong rule for a programmable transceiver. Setting frequencies is
  what programming software is *for*; a tool that refused to write a frequency
  would not be a tool. So this target documents the band-limit fields as
  facts, on the same footing as every other field, and records the reasoning
  rather than leaving a reader to find two documents that appear to
  contradict each other.
  What follows from that, for anything built on this:
  - Widening a transmit range is legal to *configure*. Transmitting outside
    one's own licence or authorization is not, and that is the operator's
    responsibility alone — MARS or CAP membership, or another lawful
    authority.
  - The expanded ranges reach spectrum allocated to public safety, commercial
    and government users. A tool should say so, in those words, before it
    offers the option.
  - It should be off by default, offered only where the fields actually
    exist (they do not exist in the UV-17Pro family at all), and paired with
    a way back to the factory values.
  - None of this is about evading anything. These fields are written by every
    mainstream programming tool including the manufacturer's; documenting
    them defeats no protection and hides nothing that is not already public.

## First experiments (do these first)
1. Identify the cable's bridge chip and confirm the host enumerates it.
2. Send the ident at 9600 baud and record the reply, including which firmware
   generation it reports.
3. Read the full image and confirm its length.
4. Cross-check the decode of the first twenty channels against an independent
   tool, field by field.
5. Read the settings region and locate the band-limit fields; record which
   layout this radio uses. **Read them before writing anything** — the
   factory values are what a restore puts back.
6. Write one channel to an unused slot, read it back, restore the backup.

## Protocol hypotheses (to validate)
- Pairing/bonding steps: none.
- Session state machine: ident → block reads and writes → close.
- Commands: `S` read, `X` write.
- Payload encoding: cleartext blocks; channel records and names in separate
  regions.
- Timing constraints: this family is widely reported to be sensitive to
  inter-block timing on some cables. Worth measuring rather than assuming.

## Control surface inventory (what the replacement app must support)
- Onboarding: identify the cable, pick the model, warn about counterfeit
  bridge chips.
- Core: read, decode, edit, encode, write, restore.
- Band limits: read, display, optionally widen, and always restore — behind
  the acknowledgement described above.
- Error handling: a refused write leaves the radio inconsistent; say so and
  point at the backup.

## Evidence checklist
- [ ] Cable enumerated; bridge chip identified
- [ ] Ident acknowledged; firmware generation recorded
- [ ] Full read of the expected length
- [ ] Decode cross-checked against an independent tool
- [ ] Band-limit fields located and their factory values recorded
- [ ] One channel written, read back, and the backup restored
- [ ] Inter-block timing sensitivity measured

## Spec output (clean-room)
Deferred, for the same reason as the newer family: the device-spec schema has
no vocabulary for a memory image.

## References (URLs only)
- https://chirpmyradio.com/projects/chirp/repository/github/revisions/master/entry/chirp/drivers/uv5r.py
- https://chirpmyradio.com/issues/9755
- https://chirpmyradio.com/projects/chirp/wiki/Baofeng_UV5R
