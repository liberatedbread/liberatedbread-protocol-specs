# Cricut legacy USB cutters (stock firmware, query only)

> **Status**: Spec Available — reported protocol, untested on hardware
> **Protocol**: USB serial / legacy binary queries
> **Manufacturer**: Cricut, Inc. (formerly Provo Craft & Novelty; legacy workflow unsupported)

## Overview and scope

This guide covers only four read-only queries on stock legacy Cricut USB
cutters: model/firmware, cartridge/mat status, mat bounds, and cartridge
information. The machine-readable source is
`device-specs/devices/cricut-legacy-usb.yaml`; all facts are `reported` and
`device.testing` is `untested`.

**No motion, cutting, start/stop transaction, design upload, command key or
firmware operation is included.** Explore Air 2 and modern Bifrost machines use
different protocols and are excluded. Replacement-firmware protocols are not
stock Cricut protocols and are also excluded.

## Models and evidence limits

| Model | Reported compatibility | Important caveat |
|-------|------------------------|------------------|
| Personal | libcutter 1.31/1.34 works; 1.00 too old | Model ID `0x000a` |
| Create | libcutter 1.51/1.54 should work | Numeric model ID not established by the query parser |
| Expression | libcutter 2.31 works; 2.34/2.43 should work; 2.00 too old | Model ID `0x0014` |
| Cake | libcutter 2.35 should work; licut's alpha release also supports it | Numeric model ID not established |
| Cake Mini | libcutter 1.54 should work | Numeric model ID and physical Reset All documentation not established |

These are the community projects' compatibility statements, not hardware
verification by this project and not permission to use their motion paths.
**Cricut Mini is different:** libcutter marks model ID `0x001e` detectable but
unsupported, and its official legacy workflow is defunct. It is not a variant
in this spec. Do not assign Expression's model ID to Create, Cake or Cake Mini.

## Manual selection, not universal USB discovery

There is no universal Cricut USB VID/PID matcher in this spec. licut's
adapter-specific lookup is not evidence that every legacy model or modern
Cricut uses the same identity.

1. Identify the exact model from its physical label and manual.
2. Connect it by USB and choose the corresponding host serial device,
   excluding other serial equipment.
3. Configure the reported serial parameters below.
4. Send `0x12` alone and require its exact six-byte response body. Only then
   issue the other read-only queries independently.

Do not probe an unknown modern cutter or another serial peripheral with these
requests. Keep one query outstanding and one process on the serial port.

## Serial parameters and documentary discrepancies

### Baud and stop intervals

The primary reported configuration is **200000 baud, 8 data bits, no parity,
one stop bit on receive, and two stop intervals on host transmit**. licut
achieves the second output interval with a 1 ms delay after every output byte,
including the last; libcutter alternatively enables 8N2 output and also delays
output bytes. Receive remains 8N1 in either case.

Two unresolved conflicts are preserved:

- libcutter and licut report **200000 baud**, but libcutter explicitly says it
  needs remeasurement; cricut-re-toolkit separately reports **198347 baud**.
  The alternate is not a proven correction or automatic fallback.
- licut's examples show **six-byte** requests, while its builder and
  libcutter's fixed command writer both emit **five bytes**. The sixth byte in
  the example is an extra-zero documentary inconsistency, not a wire variant.

Choose the baud only from evidence for the selected unit. Always emit the
five-byte implementation request. Do not cycle baud rates or send the six-byte
example after a timeout.

### Request width

For an allowed opcode `XX`, the sole executable request is:

```text
04 XX 00 00 00
```

The separate six-byte comment is retained only as evidence of the documentary
inconsistency. Do not concatenate forms, send both, or infer that a missing
response licenses another opcode. Only `11`, `12`, `14` and `18` (hex) are
allowed in this spec.

### Response framing

A response starts with one length byte counting **only the body**, not the
length byte itself. The response contains no opcode echo, so it belongs to the
one outstanding query. Read the length byte and then exactly that many body
bytes; serial reads may fragment or coalesce frames. Reject truncated,
oversized and trailing data rather than zero-filling it.

Expected body lengths are 8 for `0x11`, 6 for `0x12`, 4 for `0x14`, and 38 for
`0x18` in the published examples. Cartridge revision is at body offset
`4 + name_offset`; bounds-check that offset instead of trusting it.

## The four queries and exact published vectors

The following are licut's published examples, not captures made by this
project. Independent standard-library tests rebuild the five-byte request and
parse every response, including all truncation and malformed-offset cases.

### Model and firmware — `0x12`

```text
Request (sole executable): 04 12 00 00 00
Response:                  06 00 14 00 02 00 22
```

After the length byte `06`, three big-endian uint16 values decode as:

| Value | Meaning |
|-------|---------|
| `00 14` = 20 | Expression model ID |
| `00 02` = 2 | Firmware major 2 |
| `00 22` = 34 | Firmware minor 34, displayed as 2.34 |

Known model IDs are `0x000a` Personal, `0x0014` Expression and `0x001e` Mini
(detection-only, unsupported). Other numeric IDs remain unknown.

### Cartridge and mat status — `0x14`

```text
Request (sole executable): 04 14 00 00 00
Response:                  04 00 01 00 01
```

The four body bytes are two big-endian uint16 flags: cartridge loaded = 1 and
mat loaded = 1. Both fields accept only 0 or 1.

### Mat bounds — `0x11`

```text
Request (sole executable): 04 11 00 00 00
Response:                  08 01 3c 00 32 13 62 12 58
```

After the length byte `08`, four big-endian uint16 coordinates are:

| Field | Raw | Exact conversion at 404 units/inch |
|-------|----:|------------------------------------|
| `x_min` | 316 | `79/101` in (approximately 0.7822) |
| `y_min` | 50 | `25/202` in (approximately 0.1238) |
| `x_max` | 4962 | `2481/202` in (approximately 12.2822) |
| `y_max` | 4696 | `1174/101` in (approximately 11.6238) |

libcutter uses 404 internal position units per inch. The boundary origin,
per-model interpretation and whether every boundary uses that motion scale
still need stock-hardware confirmation.

### Cartridge information — `0x18`

```text
Request (sole executable): 04 18 00 00 00
Response:
26 00 01 00 21 43 72 69 63 75 74 28 52 29 20 43
61 6b 65 20 42 61 73 69 63 73 00 00 00 00 00 00
00 00 00 00 00 00 23
```

The `26` prefix declares 38 body bytes. They decode as:

| Body offset | Width | Meaning |
|------------:|------:|---------|
| 0 | 2 | Cartridge present, big-endian uint16 = 1 |
| 2 | 2 | `name_offset`, big-endian uint16 = 33 |
| 4 | 33 | Name region: `Cricut(R) Cake Basics`, then NUL/zero padding |
| `4 + 33 = 37` | 1 | Cartridge revision = `0x23` = 35 |

A parser must require `4 + name_offset` to be inside the body. With a cartridge
present, it must find a NUL in the name region and decode a nonempty ASCII name
only before that NUL. Never read a revision through an unchecked offset or
assume every future name region is 33 bytes.

With no cartridge, `present = 0` and `name_offset = 0` explicitly permit an
empty name without a terminator. The spec and tests include a synthetic vector
of `26` followed by 38 zero bytes, which decodes as no cartridge, empty name,
and revision zero at body offset 4. This boundary is not a hardware capture.

## Pairing, credentials and network rejoin

There is no pairing, bond, account, network credential or application session
key for these four queries. Physical access and manual model selection are the
only gate. One host process owns the serial port; close other clients and drain
stale input if a response is stale.

There is no network binding or router to rejoin. Moving hosts means closing the
old client and manually selecting the correct model and serial port on the new
host. licut's embedded command keys are not reproduced; libcutter's
owner-provided motion keys are outside this read-only surface.

## Physical Reset All

Reset All is a **single physical key press**, not a serial operation and not a
firmware reset. Use it with the machine on and no cut in progress:

- **Personal:** clears the LCD and restores factory defaults (manual page 9).
- **Create:** clears the display and restores defaults; no key should remain
  backlit green (page 12).
- **Expression:** same display/default and no-green-backlight indication
  (page 13).
- **Cake:** same display/default and no-green-backlight indication (page 13).

Cake Mini's procedure is not established by the manuals reviewed here. Do not
silently apply Cake's instructions to it. Reset All is not needed to move USB
hosts and is not an unpairing operation.

## Evidence and remaining unknowns

Evidence is pinned public source: libcutter
`d7711ed396aac542781fc4c81dbe6d0eb787b3fd`, licut
`a90f4d735d04df758d0fb385e4967b5daa21058f`, and cricut-re-toolkit
`fa09550991380668681a6f20df96d5995fa4de3a`, plus official model manuals. No
community implementation was executed and no stock unit was probed.

**licut has no license grant found.** This work derives protocol facts and its
published vectors only; it copies no implementation code or embedded command
keys. libcutter is LGPL-2.1; cricut-re-toolkit is MIT.

Open items are the two baud values, two request widths, Create/Cake/Cake Mini
model IDs, field/version variation, boundary origin/scale, and Cake Mini reset.
Modern Bifrost, Explore Air 2, motion, upload, start/stop and firmware behavior
remain deliberately unimplemented and unverified.

## Manual and implementation references

- [vangdfang/libcutter](https://github.com/vangdfang/libcutter)
- [Geremia/licut](https://github.com/Geremia/licut)
- [christianmeurer/cricut-re-toolkit](https://github.com/christianmeurer/cricut-re-toolkit)
- [Personal Electronic Cutter user manual](https://d2e2oszluhwxlw.cloudfront.net/help/manuals/cricut-personal-electronic-cutter-user-manual.pdf)
- [Cricut Create user manual](https://d2e2oszluhwxlw.cloudfront.net/help/manuals/cricut-create-user-manual.pdf)
- [Cricut Expression user manual](https://d2e2oszluhwxlw.cloudfront.net/help/manuals/cricut-expression-user-manual.pdf)
- [Cricut Cake user manual](https://d2e2oszluhwxlw.cloudfront.net/help/manuals/cricut-cake-user-manual.pdf)
