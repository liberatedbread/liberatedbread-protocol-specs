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

- **Harmony app over Bluetooth** — when the app asks, wait 30 seconds and press Pair/Reset on the back of the hub; the app pairs over Bluetooth LE and hands the hub the Wi-Fi password. The hub takes 2.4 GHz networks with WPA, WPA2-AES or WEP. The Bluetooth exchange itself is not publicly documented.
- **MyHarmony on a computer over USB** — for phones without Bluetooth LE. MyHarmony reaches the hub over a USB cable plugged straight into the computer. Over USB the hub is `046d:c129`, a device in the same USB protocol family as the Harmony 200/300 and the Harmony Link. The Link joined Wi-Fi by having a text file written to it over USB; whether the Hub takes the same file is untested. The byte-level protocol is in `targets/logitech-harmony-usb-remotes.md`.

The account step needs Logitech's service in both routes: the hub runs a configuration Logitech compiles, and nothing documented can author one locally. Control never needs it.

## Factory reset

Unplug the hub, hold the **Pair/Reset** button on the back, and plug the power back in while holding it. The LED flickers red until the reset finishes. Logitech says this erases the hub's account information, so the hub has to be configured from the account again — do not reset a working hub you cannot reconfigure.

## Service status

On 28 May 2025 Logitech shut down Harmony Remote Software, which configured its older USB remotes. The Hub is not affected and is still configured through the Harmony app and MyHarmony; no end date has been announced. Its predecessor, the Harmony Link, lost its service in March 2018.

## Related

`targets/logitech-harmony-usb-remotes.md` covers programming the USB Harmony remotes themselves (config backup and restore, IR learning, clock, firmware), which the Hub's USB port shares a protocol with.

## References

- <https://github.com/ehendrix23/aioharmony>
- <https://github.com/JordanMartin/harmonyhub-api>
- <https://www.home-assistant.io/blog/2018/12/17/logitech-harmony-removes-local-api/>
- <https://github.com/jaymzh/concordance>
- <https://support.logi.com/hc/en-us/articles/360023255354-Reset-the-Harmony-Hub>
- <https://members.harmonyremote.com/>
