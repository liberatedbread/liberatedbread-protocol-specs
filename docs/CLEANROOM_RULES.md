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

## Purpose: repair
This work exists to support repair cafés, owner maintenance and independent servicing. The
deliverable is not a museum piece — it is enough documented protocol for someone to fix a
device they or their neighbour owns. Maintenance functions that write to a device (service
interval resets, sensor ID programming, clearing recorded faults) are in scope and are the
point.

Still out of scope, on every device class: firmware flashing and coding where a mistake
bricks the unit, tampering with usage records such as odometers, defeating immobilisers or
emissions controls, and anything performed on a vehicle in motion. Procedures that are
mechanically safety-critical — brake bleeding, for one — follow the manufacturer's service
manual; a protocol document is not a substitute for it.

## Consent + ownership
Reverse engineer only devices you own/control, on networks you own/control, or where you
have permission. At a repair café that means the owner's informed consent for each change,
and telling them afterwards what was changed.
