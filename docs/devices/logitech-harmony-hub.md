# Logitech Harmony Hub

> **Status**: Abandoned — Logitech ended Harmony manufacturing April 2021
> **Protocol**: WiFi
> **Manufacturer**: Logitech
> **Manufacturer Status**: Abandoned

## Overview

Logitech's IR/Bluetooth/IP universal-remote bridge. Logitech stopped making Harmony in 2021, but local control survives the cloud entirely.

## Protocol Summary

A local WebSocket API on TCP 8088; a one-time HTTP POST to port 8088 returns the `remoteId`, then JSON requests start/stop activities and send device commands. Idle sockets close after ~60s. SSDP search target `urn:myharmony-com:device:harmony:1`.

See `device-specs/devices/logitech-harmony-hub.yaml` for the full machine-readable spec.

## Setup

Three things, in order: put the hub on Wi-Fi, configure it from a Harmony account, then fetch its `remoteId` locally. Logitech documents two ways to do the first:

- **Bluetooth** — in the Harmony app, when it asks, wait 30 seconds and press Pair/Reset on the back of the hub. The Android app (and the open [harmony-hub-setup](https://github.com/captivus/harmony-hub-setup) tool, which does this step from Linux) talks to the hub over **Bluetooth Classic RFCOMM channel 1**, not GATT, sending JSON requests: scan with `wifi.networks`, join with `wifi.connect`. Logitech's guides say Bluetooth LE; whether the iOS app uses a GATT path instead is unknown. The hub takes 2.4 GHz networks with WPA, WPA2-AES or WEP.
- **USB** — for phones without Bluetooth. MyHarmony reaches the hub over a USB cable plugged straight into the computer; the open [harmony-hub-root](https://github.com/Ripthulhu/harmony-hub-root) tool does the same Wi-Fi write. Over USB the hub is `046d:c129` and speaks the same file protocol as the Harmony 200/300 and Link: Wi-Fi is the `/sys/wifi/connect` file. The byte-level protocol is in `targets/logitech-harmony-usb-remotes.md`.

On both links the Wi-Fi password travels in plain text. The account step needs Logitech's service in both routes: the hub runs a configuration Logitech compiles, and nothing documented can author one locally. Control never needs it.

## Factory reset

Unplug the hub, hold the **Pair/Reset** button on the back, and plug the power back in while holding it. The LED flickers red for about 30 seconds, then the hub is back in Bluetooth setup mode. Over USB, writing `1` to `/sys/factoryreset` and then rebooting does the same. Logitech says this erases the hub's account information, so the hub has to be configured from the account again — do not reset a working hub you cannot reconfigure.

## Service status

On 28 May 2025 Logitech shut down Harmony Remote Software, which configured its older USB remotes. The Hub is not affected and is still configured through the Harmony app and MyHarmony; no end date has been announced. Its predecessor, the Harmony Link, lost its service in March 2018.

## Related

`targets/logitech-harmony-usb-remotes.md` covers programming the USB Harmony remotes themselves (config backup and restore, IR learning, clock, firmware), which the Hub's USB port shares a protocol with. The Hub also takes Logitech `.hfw2` firmware bundles over USB; the spec's `features` block has the sequence.

## References

- <https://github.com/ehendrix23/aioharmony>
- <https://github.com/JordanMartin/harmonyhub-api>
- <https://www.home-assistant.io/blog/2018/12/17/logitech-harmony-removes-local-api/>
- <https://github.com/jaymzh/concordance>
- <https://github.com/captivus/harmony-hub-setup>
- <https://github.com/Ripthulhu/harmony-hub-root>
- <https://support.logi.com/hc/en-us/articles/360023255354-Reset-the-Harmony-Hub>
- <https://members.harmonyremote.com/>
