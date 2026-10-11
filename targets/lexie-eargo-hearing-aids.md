# Lexie and Eargo OTC hearing aids (LXE Hearing wind-down) — target spec starter

## Target metadata
- target_id: lexie-eargo-hearing-aids
- app package_id(s): TBD (Lexie app; Eargo app) — collect NOW; both are
  being removed from the stores
- device class: over-the-counter hearing aids (Lexie B1/B2 "Powered by Bose",
  Lexie Lumen; Eargo 5/6/7/SE/Link) with phone-app control over Bluetooth
- transport(s): BLE (phone-direct); the apps also need the vendor cloud for
  sign-in and sync
- local-only viability: **medium**, and **time-critical**: LXE Hearing is
  winding down US operations. Reported dates: Lexie app removed and its cloud
  deactivated 2026-10-08; Eargo app 2026-10-22; support through 2026-10-22.
  Version 9 of each app is expected to keep working locally on a phone where
  it was installed and synced before the date; older versions stop.

## Known facts (public, 2026-07 → 2026-10)
- Sources: [HearingTracker: LXE to discontinue the apps](https://www.hearingtracker.com/news/lxe-announces-discontinuation-of-eargo-and-lexie-what-users-know) ·
  [HearingTracker: wind-down begins](https://www.hearingtracker.com/news/eargo-and-lexie-parent-lxe-hearing-begins-u-s-wind-down) ·
  [BBB profile for Eargo, Inc.](https://www.bbb.org/losangelessiliconvalley/quote/request-eargo-inc-415118)
  (lists both dates and the v9 behaviour; third-party record of LXE's notice) ·
  [Hearing Review](https://hearingreview.com/hearing-products/hearing-aids/otc/lxe-hearing-announces-wind-down-of-us-operations-affecting-eargo-lexie-and-go-brands).
- The aids keep amplifying with their last-saved settings and on-device
  controls after the cutoff; what is lost is app-side adjustment (volume,
  programs, environment presets, hearing-test-based tuning) and firmware.
- **No public protocol work found** for either brand (2026-10-11). Whether
  the Lexie B-series speak Bose's SoundControl protocol (the hardware is
  Bose-designed) is a hypothesis worth testing against any Bose BLE work.

## Device discovery signals
- BLE: unknown. Capture while a v9 app still pairs.

## Threat model + guardrails
- **Medical device.** A spec may carry volume, program and preset selection as
  the apps expose them to the wearer; nothing that changes gain beyond the
  fitting range, and no "hearing test" logic. Owner's own aids only.
- Captures contain nothing personal beyond the owner's settings; still
  placeholder the aids' addresses.

## First experiments (before 2026-10-22, or on a phone that still has v9)
1) Keep a phone with the v9 app installed and synced; do not reinstall.
2) HCI snoop: pair + change volume + change program, each brand.
3) Static: the APK's GATT UUIDs and whether a Bose SDK is inside the Lexie
   app.

## References (URLs only)
- https://www.hearingtracker.com/news/lxe-announces-discontinuation-of-eargo-and-lexie-what-users-know
- https://www.hearingtracker.com/news/eargo-and-lexie-parent-lxe-hearing-begins-u-s-wind-down
- https://www.bbb.org/losangelessiliconvalley/quote/request-eargo-inc-415118
