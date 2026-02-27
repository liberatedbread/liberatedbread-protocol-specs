# Clean-room rules (legal + ethical)

## What we do NOT commit
- APK files (or split APK bundles)
- Decompiled Java/Kotlin sources, smali, resources.arsc outputs
- Vendor images, fonts, animations, strings copied from the vendor app/UI
- Vendor documentation text beyond short, fair-use quotations (prefer paraphrase)

## What we MAY commit (derived facts)
- Hashes, package IDs, version codes, manifest-level permissions lists (summarized)
- BLE GATT service/characteristic UUIDs, characteristic properties
- Wire protocols: message formats, opcodes, CRCs, state machines
- Local network endpoints, ports, multicast discovery outputs (summarized)
- Test matrices and reproduction steps

## Scope limitations
- Exclude safety-critical medical devices.
- Exclude tobacco/vape devices except PAX (explicitly allowed by project policy).
- Prefer local-first control; if a device is cloud-only, document that and deprioritize.

## Consent + ownership
Reverse engineer only devices you own/control, on networks you own/control, or where you have permission.
