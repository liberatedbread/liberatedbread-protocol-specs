# Logitech Harmony remotes — USB programming, backup and setup

## Target metadata
- target_id: logitech-harmony-usb-remotes
- app package_id(s): none. These remotes were never programmed from a phone:
  Logitech shipped Windows/macOS desktop software (Harmony Remote Software 7
  for the older models, MyHarmony for the later ones), and the open-source
  **concordance** / libconcord project speaks the same USB protocols.
- device class: universal infrared remote; also the Harmony Link and Harmony
  Hub, which answer the same USB protocol as the later remotes
- transport(s): USB — HID (64-byte interrupt reports) for almost every model;
  USB networking (CDC Ethernet) for the Harmony 900/1000/1100
- local-only viability: **high for keeping a remote alive, nil for authoring a
  new configuration.** See the next section; it is the whole story.

Members, by the USB protocol they speak (from concordance's supported-model
table; models not listed there are not claimed):

| Protocol family | Models | How it is recognised | Config | IR learn | Firmware |
| --- | --- | --- | --- | --- | --- |
| Classic HID | 745; 748, 768; 6xx; 720, 785, 88x, Monster AV-100, Harman Kardon TC-30; 36x, 51x, 52x, 55x; One; 700 | Any HID interface at `046d:c110`–`046d:c14f` not claimed below, or `0400:c359`; model from the identity reply | read/write | yes | 748/768, 6xx, 88x, 5xx family only |
| Z-Wave over HID | 890, 890 Pro, 895, Monster AVL-300 | `046d:c112`–`046d:c115` | read/write | no | no |
| Z-Wave over USB networking | 900, 1000, 1000i, 1100, the Xbox 360 edition listed with them | CDC Ethernet (`046d:c11f`); the remote answers at `169.254.1.2` | read/write | no | no |
| MyHarmony ("MH") HID | 200, 300, Harmony Link, Harmony Hub, Harmony Touch / Ultimate | `046d:c125`, `046d:c124`, `046d:c126`, `046d:c129`, `046d:c12b` | read/write (not the Link or Touch, which hold no config file) | yes | no |

`0400` is National Semiconductor's vendor ID; libconcord's architecture table
records a National USBN9603/9604 USB controller on the oldest boards, which is
consistent with that ID belonging to one of them. Which model presents it is
not stated anywhere found.

## Why this, and why now

A Harmony remote does not know what a television is. Logitech's service held
the device database and the logic that turns "Watch TV on this Sony with this
Denon" into IR codes, key maps and activity macros; it compiled all of it into
a binary blob, and the desktop software's only job was to copy that blob onto
the remote over USB. Concordance's README is explicit that this is true of
Logitech's software and of concordance alike.

**On 28 May 2025 Logitech shut down Harmony Remote Software and the service
behind it** (`members.harmonyremote.com`). Its notice lists the remotes that
can no longer be reconfigured: the 510, 515, 520, 522, 525, 550, 555, 610,
620, 628, 655, 659, 660, 670, 675, 676, 680, 688, 720, 745, 748, 768, 785,
810, 820, 850, 880, 882, 885, 890, 890 Pro, 892, 895, 897, 900, 1000, 1000i,
1100, 1100i and the Harmony for Xbox 360 — every Logitech Z-Wave remote and
most of the classic family. The blob format was never reverse-engineered —
there is no open compiler for it — so nobody can author a new configuration
for those remotes today.

The notice says every other remote stays supported through the MyHarmony
desktop software or the Harmony app. That covers the One, 650, 665 and 700,
the 200, 300, Touch and Ultimate, and the Hub, all absent from its list. For
those, Logitech still compiles configs as of this writing, and everything
below about backup is insurance rather than rescue. The Harmony Link went the
other way first: its service ended on 16 March 2018, and Logitech replaced
Links with Hubs.

What still works for every remote, and is the point of this document:

1. **Back up** the configuration a working remote carries. For a remote on
   Logitech's list it is the only copy of that compiled config that will ever
   exist.
2. **Restore** that backup to the same remote after a failure, or to a
   replacement of the same model — the repair-café case: a dead remote with a
   perfect setup, and a second-hand one of the same model with none.
3. **Learn IR** from an original remote, as raw timings, for use by anything
   that can transmit them.
4. **Set the clock.**
5. **Put a Hub on Wi-Fi over USB — untested.** Logitech documents a USB
   first-run for the Hub; libconcord implements the Wi-Fi files for the Link,
   and lists the Hub's product ID in the same protocol family. Whether the Hub
   takes the same files is the first experiment below.

The Harmony Hub's *local control* API, which works without any of this, is in
`device-specs/devices/logitech-harmony-hub.yaml`.

## Known facts (public)
Derived from concordance's protocol notes (`specs/protocol.txt`,
`specs/protocol_mh.txt`, `specs/protocol_z.txt`) and libconcord's source.
Nothing here has been read off a remote by this project: every value is what
the open-source tool does, precise enough to implement from, and `reported`
until the evidence checklist says otherwise.

### USB transport (all HID families)
- One HID interface (interface 0), one interrupt IN and one interrupt OUT
  endpoint, **64-byte reports with no report ID**. A host API that expects a
  report-ID prefix (hidapi) is given `0x00` followed by the 64 bytes.
  Short commands are zero-padded to 64.
- On Linux the kernel's HID driver may hold the interface; libconcord detaches
  it before claiming.
- Timeouts that work: 500 ms for an ordinary reply, 5 s after a flash erase or
  a flash-write block, 5 s for any MH reply, and **20 s** for the reply that
  follows the last packet of an MH file write — a Harmony Link takes seven
  seconds or more there.

### Classic HID protocol

**The opcode byte.** The high nibble is the command; the low nibble is a length
code, and what a length code means depends on the direction and the
remote's *protocol number* (from the identity reply):

| Length code → bytes that follow | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Replies, protocol 0 | 0 | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
| Replies, other protocols | 0 | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 14 | 30 | 62 |
| Flash data written, protocol 0 | — | 1 | 2 | 3 | 4 | 5 | 6 | 7 | — | — | — |
| Flash data written, other protocols | — | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 15 | 31 | 63 |

(Protocol-0 replies continue the same pattern to code 15 → 14 bytes.) Protocol
0 is the 745, and any remote in safe mode.

**Commands and replies.**

| Byte | Name | Arguments / payload |
| --- | --- | --- |
| `10` | Get version | none → `2n` reply |
| `35` | Begin flash write | 24-bit address BE, 16-bit length BE |
| `4n` | Flash write data | the data, sized by the length code |
| `55` | Read flash | 24-bit address BE, 16-bit length BE → `6n` replies, then `Fn` |
| `70` | Start IR capture | none → `9n` replies |
| `80` | Stop IR capture | none |
| `A1` / `A3` / `A5` | Write misc (no data / byte / word) | kind, then address and data (below) → `Fn` with `A0` in byte 1 |
| `B2` / `B3` | Read misc (byte / word) | kind, 8-bit or 16-bit BE address → `Cn` reply: kind, then the byte or BE word |
| `D3` | Erase flash sector | 24-bit sector start address BE |
| `E1` | Reset | kind: `01` USB link, `02` reboot the remote, `03` reboot and disconnect, `04` end-of-test reset |
| `F1` | Done | the command being finished, e.g. `F1 30` ends a flash write |

Misc *kinds*: `00` EEPROM, `01` state variables (the clock), `02` invalidate
flash, `06` RAM, `08` recalculate clock, `0A` restart config; `03` queue
action, `04` program, `05` interrupt, `07` register and `09` queue event are
named in the notes and unused. A word write is `A5 kind addrHi addrLo dataHi
dataLo`; a byte write is `A3 kind addr data`. The 880 answers a word read with
`C2` rather than `C3`, so match on the high nibble.

**Before anything else, send `E1 01`** (reset the USB link). The Harmony One
fails its first exchange without it, and the vendor software is reported to do
the same for most remotes. Some remotes (the 785) report a write error on this
command even though it worked; ignore that one error.

**Identity.** Send `10`; the reply's first byte is `2n` with `n` = 5, 7 or 8.
Byte 1: firmware major/minor (high/low nibble). Byte 2: hardware major/minor.
Byte 3: flash chip ID. Byte 4: flash manufacturer ID. When `n` is above 5:
byte 5 is architecture (high nibble) and firmware type (low nibble), and byte
6 is the *skin* — the model number, an index into libconcord's model table
(54 is the Harmony One, 15 the 880). With `n` = 5 the remote is a 745:
architecture 2, skin 2, protocol 0. libconcord takes the protocol number from
byte 7 when `n` is 7 and from the architecture when `n` is 8; concordance's
own notes put the protocol byte last, so that branch is recorded here as
reported and unexplained.

**Where the config lives.** Per architecture: a base address, a *cookie* at the
start of the config that says it is valid, and the offset of a 24-bit
little-endian *end address* inside the config's first kilobyte. Cookies are
read little-endian; they are ASCII when printed high byte first.

| Arch | Models | Config base | Cookie (size) | End-address offset | Serial (48 bytes) |
| --- | --- | --- | --- | --- | --- |
| 2 | 745 | `0x006000` | `0x03A5` (2) | 2 | EEPROM `0x10` |
| 3 | 748, 768 | `0x020000` | `0x0369` (2) | 2 | flash `0x000110` |
| 7 | 6xx | `0x020000` | `0x4D424D42` "MBMB" (4) | 5 | flash `0x000110` |
| 8 | 720, 785, 88x | `0x020000` | `0x50545054` "PTPT" (4) | 4 | flash `0x000110` |
| 9 | 36x, 52x, 55x | `0x820000` (flash base `0x800000`) | `0x4D434841` "MCHA" (4) | 4 | flash `0x200010` |
| 12 | One | `0x040000` | `0x4D505347` "MPSG" (4) | 4 | flash `0xFFF400` |
| 14 | 700 | `0x030000` | `0x4D505347` "MPSG" (4) | 4 | flash `0xFFF400` |

Read the first 1024 bytes at the config base. If the cookie matches, the
config's length is `end − (config_base − flash_base) + 4`; if it does not, the
remote holds no valid config. The 48 serial bytes are three 16-byte GUIDs; on
the classic remotes other than arch 14 the first three groups of each are
stored byte-swapped (bytes 3,2,1,0 then 5,4 then 7,6).

**Reading.** `55`, address, length, in chunks of at most 700 bytes on protocol
0 and 1022 otherwise. The remote answers with `6n` packets whose byte 1 is a
sequence number — **1 for the first packet, then +0x11 each time**, wrapping
at 256 — and whose data starts at byte 2, sized by the reply length map. A
`Fn` packet ends the chunk.

**Writing a configuration**, in this order:
1. Arch 14 only: write misc byte, kind `0A` (restart config), address 2 ← 0,
   then address 5 ← 0.
2. Invalidate flash (`A1 02`), so the firmware stops reading the config while
   it is replaced. Expect `Fn A0`.
3. Erase every sector that overlaps the config's range: one `D3` per sector
   start, 5 s timeout each. Sector boundaries come from the flash chip, which
   the identity reply names (manufacturer:ID — `01:37` AMD Am29LV008B, `01:49`
   Am29LV160BB, `01:4C` Am29LV116DB, `15:1C` EON F16-100HIP (the remote
   reports EON's two IDs swapped; match what it reports), `FF:11` 25F020,
   `FF:12` 25F040, `1F:C8` Atmel AT49BV322A); libconcord's `remote_info.h`
   carries the per-chip sector tables. Flash bits only go from 1 to 0, which is
   why the erase is not optional.
4. Write in chunks of at most 749 bytes (protocol 0) or 3150: `35` + address +
   chunk length, then `4n` data packets, each the largest block from the
   write-length map that fits what is left, then `F1 30`, then read one reply
   (5 s). A 100-byte chunk on a non-zero protocol goes as `4A` (63 bytes),
   `49` (31), `46` (6).
5. Verify: read the range back and compare.
6. Arch 14 only: kind `0A`, address 3 ← 1, then address 6 ← 0.
7. Reboot (`E1 02`), then set the clock.

**Clock.** State variables, written with kind `01`:
- Architectures below 8, byte writes: address 0 ← 0 (seconds, zeroed first),
  1 minute, 2 hour, 3 day − 1, 4 month − 1, 5 year − 2000; then address 0 ← the
  real seconds.
- Architecture 8 and later, word writes: address 0 ← 0, 1 minute, 2 hour,
  3 day − 1, 4 day of week, 5 month − 1, 6 year − 2000; then address 0 ←
  seconds. On architecture 8 (the 880 family) finish with `A1 08`, recalculate
  clock.
- Some remotes then send an `Fn`; read it if it comes, and do not treat a
  timeout as failure.

**IR learning.** Send `70`; point the original remote at the Harmony's learning
eye. The Harmony streams `9n` packets whose byte 1 is a sequence number
starting at 0 and rising by 0x10 (the 880 is reported to jump from `0x1F`
where `0x10` was expected; libconcord accepts that one irregularity). Byte 63
is the count of meaningful bytes and must be even; from byte 2 up to that
count the payload is big-endian 16-bit words, and the word stream continues
across packets:
- word 0 is ignored;
- word 1 is the first burst's on-time in microseconds;
- word 2 is the carrier cycle count of that burst, so the carrier is
  `cycles × 1 000 000 / on_time` Hz (10 cycles in 263 µs is 38 022 Hz);
- after that, even-numbered words are an on-time and odd-numbered words the
  on + off period, so off = period − on.
The capture is over when a decoded off-time reaches 500 ms (the gap after
the key is released) or an `Fn` packet arrives. libconcord treats a read
timeout — 5 s before the first packet, 500 ms between later ones — as a
failed capture, not as the end, and caps a capture at 5 s of signal and 1000
pulse/space entries. Then send `80` and drain until an `Fn` arrives.

**Backup file.** concordance writes a classic backup in the same shape the
Logitech site served: an XML document (`<INFORMATION>` with an
`<INTENDEDVERSION>` block giving protocol, skin, flash `mfg:id`, board and
firmware type, then `<BINARYDATASIZE>` and `<CHECKSUM>`), followed immediately
by the raw config bytes. The checksum is the XOR of every config byte, seeded
with `0x69`. The intended-version block is what stops a backup going onto the
wrong model.

### MyHarmony ("MH") protocol

Every report is either a **command** or a **data** packet.

- **Command:** `FF`, command, sequence, parameter count, parameters. The
  sequence runs `00`–`3F` and wraps; the remote answers with the same number
  with the top bit set. Each parameter is a length byte and that many bytes,
  except that length `80` introduces a NUL-terminated string.
- **Data:** sequence, length (at most `3E`, 62), data. From the remote, the top
  bit of both bytes is set; libconcord masks both with `3F`. Data packets
  share the command sequence counter.

| Command | Meaning | Parameters |
| --- | --- | --- |
| `01` | Open a file | path (string); `R` or `W` (string); for a write, length (4 bytes BE) |
| `03` | Write flow control | `01 <P>`, `01 <K>` |
| `04` | Read flow control | `01 <P>`, `01 <K>` |
| `05` | Sent after a config write | `01 05`, `01 00` |
| `06` | Config checksum | see *Writing the configuration* |
| `07` | End of transfer / reset sequence | `01 <P>` |

`P` is a session byte: the remote returns it at offset 5 of its reply to the
open, and it goes back in every flow-control and end message of that
transfer. `K` is **the number of data packets still to come, plus one, capped
at `0x33`**; the remote acknowledges every 50 packets and the host answers
each acknowledgement with a fresh `K`.

**Waking it.** Send `FF 00 00 01 01` five times without reading (the vendor
software does, and libconcord found it necessary), then `FF FF 01 01 01 66`
and read one reply, then `FF 00 02` and read one reply. A reset is the
sequence-less `FF FF 02 01 01`.

**Reading a file.** Open it: `FF 01 <seq> 02 80 <path> 00 80 52 00`. The reply
carries `P` at offset 5 and the file length, 32-bit big-endian, at offsets
7–10. Send read flow control `FF 04 <seq> 02 01 <P> 01 <K>` and read its reply,
whose sequence byte (offset 2, masked) is the base for the data that follows.
Read `ceil(length / 62)` data packets, each one sequence higher than the last;
after every 50, send another read flow-control message and resynchronise on
its reply. Finish with `FF 07 <seq> 01 01 <P>` and read the reply.

Reading `/sys/sysinfo` right after the wake-up, with sequence 3:
`FF 01 03 02 80 2F 73 79 73 2F 73 79 73 69 6E 66 6F 00 80 52 00`.

**Writing a file.** Open it: `FF 01 <seq> 03 80 <path> 00 80 57 00 04 <length,
4 bytes BE>`, read the reply for `P`. Send `FF 03 <seq> 02 01 <P> 01 <K>` —
**no reply comes** — then the data packets, zero-padded to 64. After every 50,
read the remote's acknowledgement and answer with write flow control and a
fresh `K`. After the last packet, read the reply (up to 20 s), then end with
`FF 07 <seq> 01 01 <P>`.

**Known files.**

| Path | Content |
| --- | --- |
| `/sys/sysinfo` | Identity, text, one key per line with the value after the first space: `fw_ver` (`major.minor`), `hw_ver`, `arch`, `fw_type` and `skin` (hex), `guid` (a two-character prefix then 96 hex digits — the same three 16-byte GUIDs as the classic serial), `serial_number` |
| `/cfg/usercfg` | The compiled configuration. Ends with the four bytes `50 54 59 59` ("PTYY"); the 200 returns padding after them and the 300 returns the config without them, so a reader appends them if absent and cuts at the first occurrence. The Link and Touch (arch 17) have no such file. |
| `/ir/ir_cap` | IR learning (below) |
| `/cfg/properties` | Link: `host_name,<v>`, `account_email,<v>`, `discovery_service_link,<v>`, one per line |
| `/sys/wifi/networks` | Link: a scan — repeated blocks beginning `item,` with `ssid`, `signal_strength`, `channel`, `encryption`, as `key,value` lines |
| `/sys/wifi/connect` | Link: write `ssid,<v>` `encryption,<v>` `user,` `password,<v>`, one per line, to join a network; read it back for `connect_status` and `error_code` |
| `/sys/time` | Arch 17 clock: year (16-bit BE), month, day, hour, minute, second, day of week, eight zero bytes, then a POSIX TZ string. The vendor software is reported to send US Eastern (`EST5EDT,M3.2.0,M11.1.0`) whatever the user's zone. |

Joining a Link to a network called ExampleNet: the 61-byte body
`ssid,ExampleNet\nencryption,WPA2\nuser,\npassword,correct-horse\n` is opened
with `FF 01 00 03 80 2F 73 79 73 2F 77 69 66 69 2F 63 6F 6E 6E 65 63 74 00 80
57 00 04 00 00 00 3D` and fits one data packet, so `K` is 2. The
`encryption` vocabulary is whatever the scan reports; no list of accepted
values was found.

**Writing the configuration** (`/cfg/usercfg`) differs from a plain file write
in five places, all transcribed from libconcord:
1. It starts `FF FF 00 01 01 66` (read a reply), not the five-fold wake-up.
2. The open uses sequence 1: `FF 01 01 03 80 2F 63 66 67 2F 75 73 65 72 63 66
   67 00 80 57 00 04 <length>` (read a reply).
3. Flow control is `FF 03 03 02 01 05 01 33` — sequence 3 and `P` fixed at
   `05` — with no reply; data packets then start at sequence 4.
4. After the data, a lone `7E` report marks the end of the stream (read a
   reply). `K` counts it.
5. Then the checksum, `FF 06 <seq> 07`, seven parameters: `01 05`, `01 01`,
   `80 "XOR" 00`, `02 <seed BE>`, `04 00 00 00 00`, `04 <length BE>`, `02
   <expected BE>`; read a reply. Then `FF 05 <seq> 02 01 05 01 00`, read a
   reply; then `FF 07 <seq> 01 01 05`, read a reply.

**The checksum.** XOR of the config taken as **little-endian** 16-bit words,
seeded with `0x4321`, over the first *length − 6* bytes, where length includes
the `PTYY` marker; a trailing odd byte is left out. The seed, length and
expected value travel as big-endian numbers in the message above. Worked
example: the 32-byte config `10 11 12 … 29 00 00 50 54 59 59` (26 bytes
counting up from `10`, two zero bytes, the marker) checksums its first 26
bytes to `0x6A09`, and with sequence 9 the message is
`FF 06 09 07 01 05 01 01 80 58 4F 52 00 02 43 21 04 00 00 00 00 04 00 00 00 1A
02 6A 09`.

**Backup file.** A zip holding `Result.EzHex` (the config bytes) and
`Description.xml`, whose `<FILE>` element names the file, its size, the target
path `/cfg/usercfg` and the operation type, and carries a `<CHECKSUM>` element
with `SEED`, `OFFSET`, `LENGTH`, `EXPECTEDVALUE` (hex) and `TYPE="XOR"`, with
the skin under `<INTENDED>`. This is the shape the Logitech service delivered
and the shape a restore needs, because the checksum message is filled from
it.

**IR learning.** Open `/ir/ir_cap` for reading (sequence 0), send read flow
control with `K` = 0 (`FF 04 01 02 01 <P> 01 00`) and read its reply, then
parse packets exactly as the classic `9n` stream, starting from sequence
`0x90` (from `0x00` on arch 17). End with `FF 06 02 02 01 <P> 01 06`, read the
reply, then `FF 07 03 01 01 <P>`.

MH remotes have no settable clock over USB except arch 17; libconcord treats a
clock write on the others as a no-op success.

### Z-Wave remotes (890 family, 900/1000/1100)

Less completely traced here; concordance's `specs/protocol_z.txt` is the
primary source and should be read alongside this summary.

- **890 family, over HID.** Short exchanges use a datagram form (byte 0 =
  length − 1, byte 1 = `01`, then message type — `00` request, `01` response —
  and command). Bulk transfers switch, via command `40`, to a
  connection-oriented form whose byte 1 carries SYN (`80`), ACK (`40`) and FIN
  (`20`) flags and bytes 2–3 sequence and acknowledgement numbers.
- **900/1000/1100, over USB networking.** The remote is a CDC Ethernet device
  at **`169.254.1.2`** and expects to be *given* an address by DHCP — the host
  side is `169.254.1.1/16`, and concordance ships a dnsmasq wrapper for
  exactly that. The protocol is **TCP port 3074**; each message is
  `(family << 4) | command-high-nibble`, command low byte, `80` for a request
  or a status for a response, then a parameter count and parameters whose
  length byte encodes a scale in its top two bits (×1, ×4, ×512). Family 2
  (client) carries everything below. The remote also serves HTTP on port 80;
  concordance reads `/xmluserrfsetting` from it during an update.
- **Commands** (client family): `61` system info (VID, PID, product type,
  firmware version and type, skin, board revision), `67` GUID, `6E` region
  IDs, `6F` region version, `87`/`89` node and home ID, `12` ping, `71` set
  time (year BE, month, day, hour, minute, second, day of week, UTC offset,
  then a zone name), `1B` reset. Configuration moves by **region**, the user
  config being region 4: write with `41` start, `42` header (size), `43` data
  in 1 KiB chunks, `44` data done, `45` checksum (seed `FF FF`), `46` finish
  (validate); read back with `47` (size), `48` (1 KiB chunks), `49` done.

## Device discovery signals
- USB only. No radio this protocol uses; the Link and Hub are on Wi-Fi, but
  their Wi-Fi presence is the Hub spec's business, not this document's.
- Match the Logitech range `046d:c110`–`046d:c14f` (plus `0400:c359`), then
  split by product ID as in the table at the top. Inside the classic family
  the model comes from the identity reply's skin byte, not from the product
  ID.
- A Z-Wave USB-networking remote appears as a network interface, not a HID
  device; probe TCP `169.254.1.2:3074` after DHCP has handed it its address.
- Remotes sleep. The vendor software's advice was to press a button to wake
  one before connecting, and a Linux host may need a moment after the device
  appears before the first write succeeds.

## Threat model + guardrails
- Scope: remotes the operator owns. Nothing here reaches any network.
- **The backup is irreplaceable.** Read and save the configuration before
  writing anything; a tool built on this should refuse to write a config to a
  remote whose current config it has not saved, or at least say plainly that
  the old one cannot be regenerated.
- **Restore only onto the same model.** The classic backup's intended-version
  block and the MH backup's skin say which remote a blob was compiled for;
  check them against the identity reply rather than trusting a filename.
- **Firmware writes are the one way to brick a remote**, and they are
  supported on few models. Documented, not recommended: treat as `advanced`,
  keep a dump of the old firmware (concordance can take one), and expect that
  a remote interrupted mid-write may need the firmware re-sent before it will
  do anything else. Whether these remotes have a recovery mode reachable by a
  button sequence was not found in any source read.
- A config write erases before it writes. An interrupted write leaves a remote
  with no config but with working firmware and USB, so the restore can simply
  be run again.
- The Wi-Fi file carries the passphrase in plain text over USB, and reading it
  back returns it. Anything that logs MH traffic should scrub it.

## First experiments (do these first)
1. On one remote of each family, connect and record the identity (classic:
   the `10` reply; MH: `/sys/sysinfo`). Scrub the GUIDs and serial before
   committing anything.
2. Dump the config with concordance, then read the same range with an
   independent implementation of the steps above and compare byte for byte.
3. Check the checksum: recompute the classic XOR or the MH word XOR over the
   dump and compare with what concordance wrote into the backup's XML.
4. On a sacrificial remote of the same model, restore the backup and confirm
   every activity still works — the one test that proves the repair story.
5. Plug in a Harmony Hub (`046d:c129`) and see whether it answers the MH
   wake-up and serves `/sys/sysinfo`, `/sys/wifi/networks` and
   `/sys/wifi/connect` like the Link. If it does, a Hub can be put on a new
   network with no app and no Logitech account.
6. Learn one known IR code (a TV power key whose NEC or RC-5 code is public)
   and check the decoded timings against it.

## Protocol hypotheses (to validate)
- The Harmony Hub speaks the Link's Wi-Fi files over USB. Only its product ID
  in libconcord's MH list supports this; concordance's supported-model table
  does not list the Hub.
- The identity reply's protocol byte: libconcord's use of byte 7 when the
  length code is 7, and of the architecture when it is 8, reads backwards
  against concordance's own notes.
- What the two fixed bytes before `PTYY` in an MH config are (they fall
  outside the checksum).
- What the MH command `05` after a config write does, and what the `66` in the
  wake-up and config-write preambles means. Both are replayed as observed.
- How long MyHarmony and the Harmony app keep compiling configs for the
  remotes the May 2025 notice did not list. No end date has been announced;
  this document does not rely on either service.

## Control surface inventory (what a replacement tool must support)
- Detect and identify: family, model, firmware, whether a valid config is
  present, how much of the flash it uses.
- Back up the configuration to a file that records which model it came from.
- Restore that file to a matching remote, verify it, reboot, set the clock.
- Set the clock on its own.
- Learn IR and export the timings (carrier + pulse/space list, microseconds).
- Hub (if confirmed; the Link is documented but its service is gone): scan
  Wi-Fi networks, join one, report the connection status.
- Firmware backup and write, behind a deliberate confirmation.

## Evidence checklist
- [ ] Identity replies from one remote per family (scrubbed)
- [ ] A config dump cross-checked between concordance and an independent reader
- [ ] One restore onto a second unit of the same model, activities confirmed
- [ ] A usbmon (Linux) or USBPcap (Windows) capture of a vendor-software
      session, for anything the notes describe as "unknown" — kept out of the
      repository (`*.pcap` is gitignored)
- [ ] Hub over USB: does it answer the MH wake-up?

## Why this is not a YAML spec yet
The schema has no home for USB: `device.protocol` has no `usb` value and the
wired `bus` block's `link.type` is `uart` or `can`. The protocol is
request/response over fixed 64-byte reports, which the `bus` block's `messages`
catalogue could otherwise carry almost unchanged. Adding a `usb_hid` link type
(and `usb_net` for the 1000 family) is the smallest schema change that would
let this become a spec, and it is a decision for the schema's consumers, not
for one target. Until then this document is the reference, as the Baofeng
programming targets are for theirs.

## References (URLs only)
- https://github.com/jaymzh/concordance
- https://github.com/jaymzh/concordance/blob/master/specs/protocol.txt
- https://github.com/jaymzh/concordance/blob/master/specs/protocol_mh.txt
- https://github.com/jaymzh/concordance/blob/master/specs/protocol_z.txt
- https://github.com/jaymzh/concordance/blob/master/SupportedModels.md
- https://github.com/congruity/congruity
- https://members.harmonyremote.com/ (Logitech's discontinuation notice and
  affected-model list)
- https://support.logi.com/hc/en-us/articles/360023255354-Reset-the-Harmony-Hub
- https://cdn-cx-images.dynamite.myharmony.com/usermanuals/harmonyhub-quickstartguide-en-de-fr-it-es-nl.pdf
  (Hub quick start: Bluetooth first-run, or a computer)
- https://www.logitech.com/assets/50381/harmony-smart-control-user-guide.pdf
  (Hub-based kit; MyHarmony syncs the hub over a USB cable)
