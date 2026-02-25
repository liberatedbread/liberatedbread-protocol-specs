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

## Adding a New Device

1. Copy `docs/devices/_template.md` to `docs/devices/your-device-name.md`
2. Fill in the template
3. Add your device to `docs/devices/index.md`
4. Submit a PR!

## Related Repos

- [opengreeniot](https://github.com/PigsCanFlyLabs/opengreeniot) - Project coordination
- [opengreeniot-website](https://github.com/PigsCanFlyLabs/opengreeniot-website) - Website & docs
- [opengreeniot-mobile](https://github.com/PigsCanFlyLabs/opengreeniot-mobile) - Flutter BLE app
- [opengreeniot-hub](https://github.com/PigsCanFlyLabs/opengreeniot-hub) - Home Assistant integration

## License

Apache 2.0 - See [LICENSE](LICENSE)

Copyright 2026 Pigs Can Fly Labs LLC
