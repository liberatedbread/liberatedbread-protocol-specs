# BGH Smart Control (Wi-Fi air conditioners and HPA-4911 kit)

> **Status**: Spec available (unverified)
> **Protocol**: WiFi (binary UDP, commands to port 20910, broadcasts on 20911)
> **Manufacturer**: BGH (platform by Solidmation)
> **Manufacturer Status**: Shutdown. The Smart Control cloud and app stopped on 31 December 2025.

## Overview

BGH's "Smart Control" line, sold mainly in Argentina from about 2016, came in
two forms: BGH air conditioners with a built-in Wi-Fi module, and the
**HPA-4911 Smart Control Kit**, which retrofits any infrared-controlled split
unit. Solidmation built the platform. BGH closed the Smart Control cloud on
31 December 2025. The community thread that announced the local replacement
gives that date, and so do Argentine press reports quoting BGH's notice.
After that the vendor app could no longer sign in.

The units never needed the cloud to be controlled. On the LAN they speak a
plain binary UDP protocol with no encryption, no authentication and no
checksum. Three open-source clients have reverse-engineered it:
[arpena/hpa4911](https://github.com/arpena/hpa4911) (the Home Assistant
integration from the thread),
[firtman/bgh_smart](https://github.com/firtman/bgh_smart) and
[andrescerutti/bgh-smart-control-local](https://github.com/andrescerutti/bgh-smart-control-local).
They agree on the framing, the ports, the HVAC commands and the status
layout.

The kit has two halves. The **base** plugs into the wall, passes mains through
to the air conditioner, and carries the Wi-Fi module, a consumption sensor and
a link button with a red/green LED. The **IR unit** runs on batteries and
sticks onto the indoor unit facing its receiver. It measures room
temperature, has a vibration sensor, and talks to the base over BLE. A LAN
client only ever talks to the base. An ACK therefore means the base took the
command, not that the air conditioner did.

## Hardware

| Property | Value |
|----------|-------|
| Model Number | HPA-4911 (kit); BGH Smart AC units with built-in Wi-Fi |
| Chipset | Hi-Flying Wi-Fi module (inferred from the OUI, the SoftAP address and its UDP 48899 beacon); CSR1010 BLE in the kit, per one teardown |
| Radio | Wi-Fi 2.4 GHz only; BLE between the kit's halves |
| MAC prefix | `AC:CF:23` (the module vendor's block, so other products share it) |
| Category | `climate` |
| Companion app | BGH Smart Control (`com.solidmation.bghsmartcontrol`). Historical: its sign-in is gone. |

## Initial Setup

| Property | Value |
|----------|-------|
| Setup required | Yes for a new or reset unit. A unit set up before the shutdown already answers on the LAN. |
| Method | `softap_udp`: the unit's `BGH-…` AP and one UDP join frame |
| Setup AP | `BGH-XXXX` / `BGH-XXX-XXXXXXXXXX`, on 10.10.100.0/24, with the unit at the Hi-Flying module's standard gateway address (given in the spec) |
| Passphrase protection | `plaintext`: SSID and passphrase are sent in the clear |
| Confidence | medium (three open-source clients have run it; this project has not) |

1. Put the unit in setup mode. On a kit, use the reset below until the base
   LED blinks green. On an AC with built-in Wi-Fi, take its remote, set
   29 °C then 30 °C, and repeat until the AC turns itself off. Turn it on
   again and it is in connect mode.
2. Join the `BGH-…` network. To learn the unit's MAC, either listen on UDP
   20911 or send a keep-alive (command 255, broadcast MAC) and read bytes 1–6
   of the reply.
3. Send **Join (161), subcommand 3** to the unit on UDP 20910. The payload is
   the SSID NUL-padded to 33 bytes, then a security byte (3 = WPA2), an
   encryption byte (4 = AES), and the passphrase NUL-padded to 33 bytes.
   The whole frame is 86 bytes. A 17-byte ACK (command `0x80`) echoes your
   sequence number.
4. Within 10–30 s the AP disappears and the unit joins the home network. A
   kit base shows up as `HPA-4911` in the router.

**The kit needs two more steps:**

- **Pair the IR unit to the base.** Unplug the base. Hold the IR unit's
  button about 20 s until it blinks red, then pull a battery. Plug the base
  in and let it join Wi-Fi, then put the battery back. Within a few minutes
  the IR unit stops blinking, then the base does.
- **Learn the remote's IR codec.** Without it the IR unit transmits and the
  AC ignores it. Send Custom 162 `[90, 1]` to enter learning mode. Press
  ON/OFF on the AC's own remote twice; each press makes the base broadcast
  162 `[95, codec]`. Store the codec with 162 `[88, codec, sensor]`: sensor 1
  if the AC is plugged into the base, 2 for the IR unit's vibration sensor.
  "Toggle" codecs need one of the two, because they send the same code for on
  and off. Then, with the IR unit stuck in place and the AC off and stopped,
  send 162 `[100]` to calibrate the vibration zero, and 162 `[90, 0]`.

**Factory reset (kit).** This sequence comes from the community kit guide,
which says it follows BGH's help pages, and arpena's guide agrees:

1. Unplug the base.
2. Within 30 s, press the IR unit's recessed button with a clip. It blinks
   red.
3. Remove a battery from the IR unit.
4. Plug the base in. Its LED blinks red.
5. Hold the base button about 5 s, until the LED goes off and comes back.
   The base has now dropped its IR unit.
6. Hold the button again, about 10 s, until the LED blinks green. The base is
   in setup mode.

A unit still on the network can instead be sent **Leave (175)**. Send it four
times, as the app did. None of this has been run by this project.

**Rebinding to a new network.** Every source re-provisions through the setup
AP. Send Leave over the old network before you replace the router, or use the
buttons afterwards.

## Pairing

| Property | Value |
|----------|-------|
| Pairing required | No |
| Security mode | `none` (the network is the only gate) |
| Bonding | `none` |
| One client at a time | No (connectionless UDP) |
| Confidence | medium |

Commands are addressed by the unit's MAC. The unit broadcasts that MAC in
every status report and returns it to a broadcast enumerate, so the MAC is an
address, not a secret. The kit's link buttons pair its two halves over BLE.
That pairing happens inside the kit and does not authorise a client.

## Protocol Summary

Commands go to the unit on **UDP 20910**. Replies come back unicast to the
sender's port. The unit broadcasts status reports, debug text and codec
detections to **255.255.255.255:20911**, so a client binds 20911 to read
state.

### Header (17 bytes, every datagram)

| Offset | Length | Field |
|--------|--------|-------|
| 0 | 1 | Version, `0x00` |
| 1 | 6 | Source MAC: zeros from a client, the unit's MAC from the unit |
| 7 | 6 | Destination MAC: the unit's, or `ff:ff:ff:ff:ff:ff` for discover, poll and keep-alive |
| 13 | 1 | Sequence number, echoed in the ACK/NAK |
| 14 | 1 | Source endpoint |
| 15 | 1 | Destination endpoint: 0 for the device, 1 for the HVAC endpoint |
| 16 | 1 | Command |

The payload follows the header directly. There is no length field and no
checksum.

### Commands

| Command | Hex | Payload / notes |
|---------|-----|-----------------|
| HVAC SetMode (endpoint 1) | `61` | `mode, fan, flags, setpoint` (int16 LE, °C × 100). arpena also sends a one-byte `mode` form, used for off |
| ACK / NAK | `80` / `81` | unit → client |
| Join | `a1` | subcommands 4 enumerate (2 = reply), 3 Wi-Fi join, 5 scan, 7/8 get/set cloud IP, 12 subscribe |
| Custom (kit) | `a2` | 92 IR unit status, 90 learning mode, 88 set codec, 95 codec detected, 100 calibrate, 101 temperature offset |
| Reboot / Leave | `a4` / `af` | no payload |
| Poll (endpoint 1) | `e4` | the unit answers by broadcasting a status report |
| Debug / Status | `f5` / `fd` | broadcasts |
| Keep-alive | `ff` | the unit answers one sent to the broadcast MAC |

Modes: 0 off, 1 cool, 2 heat, 3 dry, 4 fan only, 254 auto. Turning the AC on
means choosing a mode. Fan: 1 low, 2 medium, 3 high, and 254 or 0 for auto
(the sources disagree). Flags: `0x10` is horizontal swing; turbo `0x08` and
vertical swing `0x20` are less certain. Each SetMode frame carries the whole
state, so read the current state back first, or the fields you did not mean
to change get overwritten.

### Status report (command 253, 29 bytes)

| Payload offset | Field |
|----------------|-------|
| 0 | Type, 6 = HVAC |
| 1 | Mode |
| 2 | Fan |
| 3 | Flags |
| 4–5 | Room temperature, int16 LE / 100 |
| 6–7 | Set point, int16 LE / 100 |
| 8–11 | Timer on / off minutes per arpena (firtman: padding) |

Subscribe with Join subcommand 12 and renew it every 120 s. Follow it with a
Poll to get a report straight away. The unit also reports every change. Filter
incoming datagrams by length and command byte: the unit also sends 22-byte
ACKs, and one client that parsed them as status showed 255 °C.

See `device-specs/devices/bgh-smart-control.yaml` for the full spec. Its
example frames are built from invented values, and
`scripts/test_bgh_smart_control_spec.py` rebuilds every one of them from the
header rule and decodes the status frames.

### Firmware update

Unknown. No source documents an update path for the base, the IR unit or the
built-in module, and the module's web interface rejected the default logins
in one owner's test.

## References

- [Home Assistant community: BGH Smart Control is dead, long life to local BGH Smart Control](https://community.home-assistant.io/t/bgh-smart-control-is-dead-long-life-to-local-bgh-smart-control/974020)
- [arpena/hpa4911](https://github.com/arpena/hpa4911) (MIT) and its [configuration guide](https://github.com/arpena/hpa4911/blob/main/CONFIGURING_NEW_DEVICES.md)
- [firtman/bgh_smart](https://github.com/firtman/bgh_smart) and the [community kit guide](https://github.com/firtman/bgh_smart/blob/main/docs/GUIA_BGH_SMART_CONTROL_KIT.md) (Spanish)
- [andrescerutti/bgh-smart-control-local](https://github.com/andrescerutti/bgh-smart-control-local) (MIT)
- [Via País: press report on the shutdown](https://viapais.com.ar/informacion-general/si-tenes-este-aire-acondicionado-hay-una-funcion-que-ya-no-podras-usar-a-que-se-debe/) (Spanish)
