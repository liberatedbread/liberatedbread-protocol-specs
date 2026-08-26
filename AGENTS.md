# Agent guide — Liberated Bread Protocol Specs

Guidance for AI coding agents (Claude Code and others) working in this repo.
Humans: start with [README.md](README.md).

## What this is

The clean-room **knowledge base** of reverse-engineered protocols for
locally-controllable IoT devices — so abandoned hardware keeps working without
the vendor cloud. The two most common transports, and the ones the mobile app
speaks, are:

- **BLE** (`protocol: ble` / `ble_gatt`) — GATT services, characteristics,
  message formats.
- **Wi-Fi/LAN** (`protocol: wifi`, with `http` / `soap` / `ssdp` / `udp`
  transport blocks) — discovery via mDNS/DNS-SD and SSDP/UPnP, control over HTTP
  and SOAP, and device provisioning.

Specs are not limited to those two. The authoritative `device.protocol` enum in
`device-specs/schema.json` also covers `zigbee`, `zwave`, `obd2`, `uart`, and
`can` (e-bikes, OBD-II dongles, and other wired/radio buses) — treat that enum
as the source of truth for what a spec may declare.

**The specs are the product.** `device-specs/devices/*.yaml` is written to be
implementable on its own, validated against `device-specs/schema.json`. We do
**not** ship a supported device-client library; helper scripts under `scripts/`
are verification/research scaffolding, not a client surface.

## Clean-room rules (absolute)

See [docs/CLEANROOM_RULES.md](docs/CLEANROOM_RULES.md). In short:

- **Never commit APKs, decompiled source trees, or vendor assets.** They are
  gitignored (`workspace/`, `*.apk`, `*.pcap`, …) — keep it that way.
- Do not paste vendor app strings/UI copy beyond short paraphrases.
- Do not name the vendor app's internal classes, methods or source paths.
  Describe the role instead: "the app's BLE scanner", not `SenseScanner.java`.
  Citing an *open-source* project by file is fine — that is attribution.
- **Scrub identifiers that are yours, not the device's.** Hardware
  verification fills your notes with the LAN address, MAC, hostname, serial
  and keys of your own unit; none of it is reusable and all of it is public
  once committed. Replace with a placeholder (`aa:bb:cc:dd:ee:ff`,
  `192.168.1.50`, `<user-key>`) and keep the format so the example still
  teaches. Keep OUI prefixes and product-fixed addresses like a SoftAP's
  `10.10.100.254` — those are the fact. Applies to `research-notes/` and
  `docs/devices/` too.
- Only commit **derived** facts, protocol details, and your own writing.

## Setup, test, lint

- **Claude Code on the web:** `.claude/hooks/session-start.sh` installs the
  Python deps automatically.
- **Local:**

```bash
pip install -r requirements.txt -r requirements-dev.txt
ruff check .                      # lint the helper scripts
pytest -q                         # test suite
python scripts/validate_specs.py  # validate every spec against schema.json
python scripts/validate_glyphs.py # glyph references, manifest and SVG hygiene
python scripts/build_index.py --check   # JSON API freshness (what CI checks)
mkdocs build --strict             # docs must build clean
```

CI (`.github/workflows/ci.yml`) runs exactly these.

**Do not commit `device-specs/index.json`.** It is generated, and CI's
`publish-index` job rebuilds and commits it on every push to main — that is the
whole reason it moved out of branches: with several spec PRs open at once, a
60 kB machine-written file that every one of them touches conflicts with every
other one. A PR carrying it fails CI (`Reject a hand-carried index.json`) with
the command to drop it. If you want to see the index your specs produce,
`python scripts/generate_index.py` still writes it locally — just leave it out
of the commit (`python scripts/generate_index.py --check` reports staleness
without writing).

## Instruction glyphs (`glyphs/`)

Small **original** drawings of the hardware a reset or pairing step refers to —
which button, what the LED does — referenced from specs by `glyph` /
`indicator_glyph` and rendered beside the step. Full guide:
[docs/contributing/glyphs.md](docs/contributing/glyphs.md). The three rules
worth knowing before you touch the directory:

- **Draw it, never derive it.** Vendor artwork is inadmissible in any processed
  form — not a manual crop, not a trace over a product photo, not a recoloured
  app asset. `origin: original_drawing` in `glyphs/MANIFEST.yaml` is an
  attestation, and it is the only value the validator accepts.
- **Tracked with Git LFS.** Run `git lfs install` in a fresh clone or you get
  pointer files instead of drawings.
- **Every glyph is referenced and every reference resolves.** An orphan in the
  store is a validation failure. Run `python scripts/validate_glyphs.py`.

## Adding or changing a device

1. `docs/devices/_template.md` → `docs/devices/<device>.md` (include setup,
   pairing, factory reset, rebinding).
2. Add the device to `docs/devices/index.md` and to `mkdocs.yml`'s nav.
3. Add a spec under `device-specs/devices/`, then
   `python scripts/validate_specs.py`. A BLE spec must carry a
   `device.pairing` block — "nothing pairs" is the usual answer and saying it
   is the point; see
   [docs/protocols/pairing.md](docs/protocols/pairing.md). The index picks the spec up on its own
   once this merges — do not commit `device-specs/index.json`.
4. For net-new reverse engineering, follow the per-target clean-room workflow in
   [prompts/AGENT_META_PROMPT.md](prompts/AGENT_META_PROMPT.md).

## Downstream

Specs here are vendored into
[liberatedbread-mobile](https://github.com/liberatedbread/liberatedbread-mobile)
as a git subtree; the mobile app renders these YAML specs directly for both BLE
and Wi-Fi/LAN devices. Keep specs implementable from the document alone.
