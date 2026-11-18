# Brother My Stitch Monitor embroidery machines

> **Status**: Spec Available — reported protocol, untested on hardware
> **Protocol**: Wi-Fi / SNMPv1 discovery + HTTPS JSON monitoring
> **Manufacturer**: Brother Industries, Ltd. (active)

## Overview and safety boundary

This family specification covers **read-only local monitoring** for Brother
machines with documented My Stitch Monitor compatibility. It is not an EV1-only
spec and does not match a numeric EV1 model ID. The machine-readable source is
`device-specs/devices/brother-embroidery-lan.yaml`; all protocol facts are
`reported` and `device.testing` is `untested`.

Only these operations are in scope:

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/info` | Identity and monitoring-capability confirmation |
| GET | `/status` | Machine, hoop and storage state |
| GET | `/embinfo` | Current job, stitch/color and needle information |
| GET | `/embstatus` | Current job state, progress, time and position |

There is deliberately **no POST, design transfer, motion/start/stop control,
image or lens operation, push registration, or firmware update**. The shared
vendor library contains other methods; their existence does not establish
machine support or make them part of this spec.

The BLE-only Skitch PP1 stays in [its separate guide](brother-skitch-pp1.md).
ScanNCut is not added: a recovered document format without a recovered local
transport is not a local monitoring protocol.

## Compatible models and caveats

The variants are a compatibility roster, not a discovery matcher. A client
still has to prove the exact SNMP identity and `/info` capability on each unit.

| Models | Evidence and caveat |
|--------|---------------------|
| EV1, EV1LE | Official app list (written EV1-LE) and shared manual |
| BX1, BX1E, CX1E | Official app list; sewing-only CX1 is not claimed |
| XP2, XP3, XJ2, XE2, BP3700 | Official app list |
| XP1, XJ1, XE1, BP3600 | **Upgrade Kit I required** before monitoring |
| PR1055X, PR680W | Official app list |
| PR1060W | Official product page names My Stitch Monitor, although the global app list omitted it; recorded as a source discrepancy |

Artspira or Design Database Transfer support alone does not prove monitoring
support. NQ/NS/PE/SE/LB Wi-Fi models, Dream Machine, Quattro, Essence and
PR1050X are not added on that basis. PP1/PP1E are not variants here.

## Discovery: exact identity before any monitoring request

Use SNMPv1 on UDP port 161 with community `public` and these rules:

1. Generate a cryptographically fresh integer request ID in
   `1..2147483647` for every newly encoded datagram. An identical
   retransmission may reuse its ID; the fallback and later discovery rounds
   need fresh IDs. Accept only the matching response ID.
2. Send to the active IPv4 interface's **directed subnet broadcast** first.
3. If no valid machine answers, make **one** limited-broadcast attempt to
   `255.255.255.255`. Do not turn this into an unbounded unicast sweep.
4. Require GetResponse (`0xa2`), community `public`, error status/index zero,
   the outstanding request ID, and exact, case-sensitive host-resources
   description **`brother sewing`**.
5. Only then start TLS approval and fetch `/info`.

The monitor app's reported socket timeout is 1000 ms; this is an implementation
choice, not a device limit. A machine name or numeric model ID is never enough
to select this spec.

### OIDs

| OID | Role | Required |
|-----|------|----------|
| `1.3.6.1.2.1.1.1` | sysDescr diagnostics | No |
| `1.3.6.1.2.1.1.5` | sysName/model field, not a matcher | No |
| `1.3.6.1.2.1.1.6` | sysLocation/display-name fallback | No |
| `1.3.6.1.2.1.25.3.2.1.3.1` | Host-resources description, exactly `brother sewing` | **Yes** |
| `1.3.6.1.2.1.27.1.1.2.103` | Application name | No |
| `1.3.6.1.2.1.27.1.1.6.103` | Application operation status | No |
| `1.3.6.1.4.1.2435.2.4.3.1240.5.2.3.0` | Brother IP data | No |
| `1.3.6.1.2.1.2.2.1.6.1` | Physical/MAC address identity | No |

The spec also carries an **84-byte desktop-derived** SNMP GetRequest. Its
varbind order is host description, physical address, then Brother IP data. It
is reconstructed independently in `scripts/test_brother_embroidery_lan.py` and
is explicitly **not a network capture**.

## TLS: user-approved TOFU, never trust-all

The reviewed vendor client disables certificate-chain and hostname checks. That
is a security defect, not behavior a replacement should copy.

Before the first `/info` request, a client must:

1. Show the discovered address and SHA-256 fingerprint of the presented DER
   certificate and require user approval.
2. Hold the approved certificate or pin **only in memory** against the
   discovered address and MAC when available. No durable machine-id binding
   exists yet.
3. Fetch `/info` with that volatile pin. Require a nonempty `machine-id`,
   expected JSON field types, monitoring capability, and an unchanged
   discovered address. The machine-id's internal format is not assumed.
4. **Atomically** persist the certificate or pin to the validated `machine-id`,
   retaining address/MAC as metadata, before any `/status`, `/embinfo` or
   `/embstatus` request. Do not create this durable binding before `/info`.
5. Require the pinned identity on every later connection and stop for renewed
   approval if it changes. A changed certificate goes through the same volatile
   `/info` validation before replacing the durable binding.

There is no unverified fallback to HTTP and no trust-all certificate or
hostname mode. Client-side removal of the pin is enough to unpair; it does not
require a machine reset. Concurrent-client limits and certificate rotation are
unknown.

## `/info`: the second compatibility gate

After the certificate is approved, require one of:

- `apis.monitoring.version > 0`;
- `apis.monitoringpr.version > 0`; or
- `apis.monitoring.availableversion` whose first dotted component is `1`.

Zero or missing capability means **do not monitor**. Do not substitute a model
number for this check.

The known `/info` fields are:

| JSON path | Type / units |
|-----------|--------------|
| `features` | Object; `embheight`, `embwidth`, `needles` (count), `postsize` (integer) |
| `model`, `type`, `oem` | Integers; numeric model is not a matcher, `oem == 1` selects OEM behavior in the app |
| `version`, `machine-id`, `name`, `serial` | Strings |
| `apis.camera` | `version` integer, `hoopresolution` number; camera is out of scope |
| `apis.monitoring` | `version` integer, `previewresolution` integer, `availableversion` string |
| `apis.monitoringpr` | `version`, `previewresolution` integers; exact JSON spelling has no hyphen |
| `apis.pedxml`, `apis.streaming` | `version` integers; both workflows out of scope |
| `link` | Object with integer `version`; not a URL to follow |

Physical units for `embheight`, `embwidth`, `hoopresolution`,
`previewresolution` and `postsize` are not established. Do not infer
millimetres, pixels or bytes.

## Status and progress JSON

### `/status`

| JSON path | Meaning / units |
|-----------|-----------------|
| `emb` | Embroidery-related integer; vocabulary unknown |
| `status` | Machine-state enum below |
| `hoop.height`, `hoop.type`, `hoop.width` | Hoop metadata; units/type vocabulary unknown |
| `linkstatus` | Link-state integer; vocabulary unknown |
| `storage.capacity`, `storage.free` | Signed 64-bit values; storage unit unknown |

### `/embinfo`

The top-level fields are `id` (`-1` means no current job), `filename`, `left`,
`top`, `right`, `bottom`, `totaltime` (**minutes**), `totalstitches` (count),
`imglocation`, `totalcolors` (count), `spm` (stitches/minute),
`singlecolorset` (boolean) and `currentneedlebarnumber` (`-1` means no current
bar in the app). `imglocation` is opaque metadata, not a request to make.

Each `colors[]` entry carries `code`, `brand`, `name`, `r`, `g`, `b`,
`stitches` (count), `time` (**minutes**), `charm`, `colorchange` (negative
means not a change), `needlebar` and `pause`. RGB components are nominally
`0..255`. Each `needlebars[]` entry carries `anchor`, `b`, `g`, `r`,
`needlebarspm` (stitches/minute), `needlenumber`, `noneedlethreading`,
`threadbrand` and `threadcode`. Each `colorchangeinfo[]` entry has a singular
`bar` array with `needlenumber`, `threadbrand`, `threadcode`, `threadname`,
`r`, `g` and `b`.

Coordinate units for `left`/`top`/`right`/`bottom` remain unknown.

### `/embstatus`

| JSON path | Meaning / units |
|-----------|-----------------|
| `id` | Progress identifier; reviewed clients compare it to `/embinfo.id` for the job join |
| `embinfoid` | Additional identifier whose relationship to `/embinfo` is unresolved; do not use it for the join |
| `status` | Same state enum as `/status` |
| `currentstitch` | Current stitch count; compare with `/embinfo.totalstitches` only when the two `id` values match |
| `currenttime`, `stoptime` | **Minutes** |
| `reservestop` | Whether a stop is reserved |
| `color` | Zero-based index into `/embinfo` `colors`, not RGB |
| `x`, `y` | Current coordinates in the `/info` feature coordinate space; unit unknown |

### Shared status enum

| Value | State | Value | State |
|------:|-------|------:|-------|
| 10, 11 | Ready, home embroidery | 20 | Sewing |
| 12 | Ready, PR | 30 | Embroidering |
| 40 | Waiting for thread | 50 | Finished |
| 41 | Paused | 60, 61 | Thread error |
| 42 | Stopped | 62 | Thread broken error |
| 63, 70, 99 | Other error | 98 | Settings screen |

The vendor app maps an unlisted value to a waiting display. A safe replacement
must instead render **`unknown(<value>)`**, because an unlisted value has no
established meaning. Unknown JSON properties at any level are ignored without
changing known fields. Known properties with the wrong type are errors, and
truncated JSON or trailing non-whitespace content is rejected.

## Initial setup

Wireless provisioning is done on the machine; no Artspira account is needed for
local monitoring.

1. Confirm the model above and, where required, install and activate Upgrade
   Kit I.
2. Open the machine's wireless LAN settings, enable wireless LAN and start its
   connection wizard or Wireless LAN Connection screen.
3. Select the home SSID (or **Add network** for a hidden one), enter the key on
   the machine and connect. PR1055X/PR1060W requires 2.4 GHz 802.11b/g/n and
   does not support WPA/WPA2 Enterprise.
4. Keep **Wireless LAN Enable** on and run the SNMP identity check. Approve the
   certificate only into memory, fetch `/info`, validate `machine-id` and the
   capability gate, then atomically persist the pin before other monitoring
   reads.

EV1/EV1LE uses the Wireless LAN Connection flow on manual page 32.
PR1055X/PR1060W uses the setup wizard on pages 29–31. Other models have their
own labels; do not generalize one model's screens to the family.

## Reset and rejoin

A network change does not require a full reset. Open wireless LAN settings,
select the new SSID and enter its key, or choose a saved SSID. The old network
does not need to remain up. A changed certificate still requires fresh user
approval; DHCP address changes alone do not justify disabling the pin check.

Reset is physical and model-specific, never an API operation:

- **PR1060W full reset:** open Settings → general settings, locate **Reset to
  Default**, touch **Reset**, and leave the machine powered until the process
  finishes. The addendum says this deletes all saved data, customized settings
  and network information.
- **EV1/EV1LE network reset:** Settings → Wireless LAN Settings (page 11) →
  **Reset network settings**. This is not claimed to erase every saved design.
- **PR1055X/PR1060W network reset:** Settings → Wireless LAN settings →
  **Reset network operations**. This is narrower than the PR1060W full-data
  reset.

Use other variants' current manuals instead of assuming these labels. Reserve
PR1060W's full-data reset for transfer or disposal, not routine reconnection.

## Evidence and remaining unknowns

The evidence is static analysis of current and earliest public monitor apps,
the public desktop transfer client, official model/product lists, and vendor
manuals. No hardware, packets or live JSON documents were obtained. The
independent tests rebuild the SNMP request and parse synthetic JSON; they are
not hardware verification.

Still open: actual certificate behavior, complete field-presence variation,
coordinate/storage units, numeric `model`/`type`/`emb`/`linkstatus`/`hoop.type`
semantics, concurrent-client limits, per-model reset consistency, and PR1060W's
compatibility-list discrepancy. All write-side protocols are intentionally
unimplemented and unverified.

## Manual and official references

- [My Stitch Monitor compatible models](https://support.brother.com/g/s/hf/mobileapp_info/mystitchmonitor/msm_en.html)
- [PR1060W product page](https://www.brother-usa.com/p/sewing-embroidery/PR1060W)
- [EV1/EV1LE operation manual](https://download.brother.com/welcome/doch103008/ev1om05usas_en.pdf)
- [PR1055X/PR1060W operation manual](https://download.brother.com/welcome/doch101931/884t15-16_om03_en.pdf)
- [PR1060W addendum](https://download.brother.com/welcome/doch103087/884t16_ma01_en.pdf)
- [Luminaire XP3 embroidery manual](https://download.brother.com/welcome/doch102491/xp3_omemb01usca_en.pdf)
- [Innov-is XP1 Upgrade Kit I manual](https://download.brother.com/welcome/doch101746/xpugk1_om02en.pdf)
