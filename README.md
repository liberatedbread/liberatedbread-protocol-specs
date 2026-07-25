# OpenGreenIoT Protocol Docs

[![Docs Build](https://github.com/PigsCanFlyLabs/opengreeniot-protocol-docs/actions/workflows/ci.yml/badge.svg)](https://github.com/PigsCanFlyLabs/opengreeniot-protocol-docs/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

> "We didn't reverse engineer it, we... liberated its documentation." -- Every RE engineer, probably

The **knowledge base** for reverse-engineered IoT device protocols. This is where we document
how abandoned IoT devices actually communicate, so we can keep them alive.

Part of the [OpenGreenIoT](https://github.com/PigsCanFlyLabs/opengreeniot) project by
[Pigs Can Fly Labs LLC](https://pigscanfly.ca).

## What's Here

- **Device Documentation**: Protocol specs for specific abandoned IoT devices
- **Methodology Guides**: How to approach reverse engineering IoT protocols
- **Tool Recommendations**: Software and hardware for capturing and analyzing traffic
- **Common Patterns**: BLE and WiFi protocol patterns we see across devices

## Viewing the Docs

### Locally

```bash
pip install -r requirements.txt
mkdocs serve
```

Then open http://localhost:8000

## Device Tooling

Local-first helper scripts, all standard-library only:

```bash
python scripts/wemo_discover.py --timeout 5     # find Wemo devices via SSDP
python scripts/wemo_control.py state --device 192.168.1.42:49153
python scripts/wemo_setup.py info               # provision/reset (dry-run by default)
python scripts/vector_discover.py --timeout 5   # mDNS discovery for other families
```

`scripts/wemo_setup.py` also needs the `openssl` binary for the passphrase
encryption Wemo devices require. See
[Wemo setup, reset and rebinding](docs/devices/wemo-setup.md) and
[Initial Device Setup](docs/protocols/device-setup.md).

## Adding a New Device

1. Copy `docs/devices/_template.md` to `docs/devices/your-device-name.md`
2. Fill in the template — including the setup, factory reset and rebinding section
3. Add your device to `docs/devices/index.md` and to `mkdocs.yml`'s nav
4. Add a spec under `device-specs/devices/` and validate it:
   `python scripts/validate_specs.py`
5. Submit a PR!

## Development

```bash
pip install -r requirements.txt -r requirements-dev.txt
ruff check .        # lint the helper scripts
pytest -q           # run the test suite
mkdocs build --strict
```

## Related Repos

- [opengreeniot](https://github.com/PigsCanFlyLabs/opengreeniot) - Project coordination
- [opengreeniot-website](https://github.com/PigsCanFlyLabs/opengreeniot-website) - Website & docs
- [opengreeniot-mobile](https://github.com/PigsCanFlyLabs/opengreeniot-mobile) - Flutter BLE app
- [opengreeniot-hub](https://github.com/PigsCanFlyLabs/opengreeniot-hub) - Home Assistant integration

## License

Apache 2.0 - See [LICENSE](LICENSE)

Copyright 2026 Pigs Can Fly Labs LLC

## Reverse-Engineering Workspace (Clean-Room)

This repository now includes an optional reverse-engineering coordination workspace focused on
**derived protocol specifications** and local-first replacement app planning.

### Quick start

```bash
./scripts/fetch_apks_apkeep.sh
./scripts/pull_apks_adb.sh
./scripts/run_static_target.sh pax-vape
# or run every APK at once:
./scripts/run_static_all.sh
./scripts/detect_devices.sh
./scripts/launch_agents_tmux.sh
```

### New planning and guardrail docs

- `docs/EXEC_SUMMARY.md`
- `docs/CLEANROOM_RULES.md`
- `docs/AUTODETECTION.md`
- `targets/targets.csv` + per-target starter templates
- `prompts/AGENT_META_PROMPT.md`

All heavy artifacts are kept under `workspace/` and gitignored by default.


## One-target-at-a-time workflow (APK decompile first)

When hardware is not available, work target-by-target using APK static analysis first:

```bash
# 1) pick one target
TARGET=pax-vape

# 2) fetch/pull APKs
./scripts/fetch_apks_apkeep.sh
# or
./scripts/pull_apks_adb.sh

# 3) decompile only that target
./scripts/run_static_target.sh "$TARGET"
```

Outputs are written to `workspace/static/<target_id>/...` and include logs plus protocol-hint greps.
