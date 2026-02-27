# APK decompile playbook (one target at a time)

Use this when you do **not** have the physical device.

## Goal
Produce a clean-room, derived protocol lead sheet for a single target from APK static analysis.

## Steps
1. Pick one `target_id` from `targets/targets.csv`.
2. Acquire APK(s) for that target:
   - `./scripts/fetch_apks_apkeep.sh`
   - or `./scripts/pull_apks_adb.sh`
3. Run one-target static analysis:
   - `./scripts/run_static_target.sh <target_id>`
4. Read `workspace/static/<target_id>/summary.md`.
5. Extract only derived facts into `docs/specs/<target_id>.md` and/or `targets/<target_id>.md`:
   - transports used (BLE, Wi-Fi, etc.)
   - probable endpoint domains
   - UUID/characteristic constants
   - protocol framing clues (opcodes, CRC, chunk sizes)

## What to avoid
- Do not commit APKs or decompiled vendor code.
- Do not copy vendor strings/UI content verbatim beyond minimal paraphrase.

## Suggested first targets
- `leds2rave4-lunchbox-led`
- `autobaba-led-backpack`
- `nyan-bt-image-controller`
