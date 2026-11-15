# Anki / Digital Dream Labs Cozmo Robot

> **Status**: Research (transport and core messages transcribed from pycozmo; untested against hardware)
> **Protocol**: WiFi (robot-hosted access point; binary UDP on port 5551 with selective-repeat ARQ)
> **Manufacturer**: Anki (assets later Digital Dream Labs)
> **Manufacturer Status**: Shutdown (Anki closed in 2019; the app now comes from Digital Dream Labs)

## Overview

Cozmo is Anki's small tracked robot. It has a forklift-style lift, a tilting
head with an OLED face, a camera, a speaker and three Bluetooth light cubes.
Almost all of its "brain" runs in the phone app, not on the robot. The robot
streams its sensor state and carries out low-level commands, so whatever runs
the protocol on the phone decides whether Cozmo still works. Anki shut down in
2019. The companion app now comes from Digital Dream Labs, which the
Pennsylvania Attorney General sued in 2024 (see the
[Vector page](vector-robot.md#vendor-context-why-this-path-matters)).

This page and `device-specs/devices/anki-cozmo.yaml` describe the protocol on
the phone-to-robot link, so another program can take the app's place. Every
protocol fact comes from [pycozmo](https://github.com/zayfod/pycozmo) (MIT),
an independent Python implementation of that program. cozmo-stack was not used,
because it was built from decompiled vendor material.

There is a separate spec for Anki's other product,
[Anki Overdrive](anki-overdrive-ble.md). It uses BLE and a different protocol.

## Hardware

| Property | Value |
|----------|-------|
| Model Number | Cozmo (body hardware version 5 on production units, 7 on development units, per pycozmo) |
| Chipset | Head: Espressif ESP8266 (Wi-Fi, OTA, NV storage) and NXP Kinetis K02 (display, audio, camera, IMU). Body: Nordic nRF51822 (motors, cliff sensor, LEDs, cube BLE) |
| Radio | 2.4 GHz Wi-Fi access point (802.11b/g in pycozmo's capture); BLE to the cubes only |
| FCC ID | Not recorded here |
| Category | `robot` |
| Aliases | Anki Cozmo; Collector's Edition (liquid metal) and Limited Edition (blue) body colours |
| Companion apps | Cozmo app (Anki, then Digital Dream Labs) |

## Initial Setup

| Property | Value |
|----------|-------|
| Setup required | No provisioning. The robot is always its own access point |
| Method | `none` (the client joins the robot's AP) |
| Setup AP / advertised name | `Cozmo_XXXXXX` (six upper-case hex digits, unique per robot) |
| Passphrase protection | not_applicable. The WPA2 passphrase is different on every robot and is shown on its face |
| Confidence | medium (pycozmo documentation, not replayed) |

1. Put the robot on its charging platform to wake it.
2. Raise and lower the lift by hand. The robot then shows its Wi-Fi passphrase
   on its face.
3. Join the `Cozmo_XXXXXX` network with that passphrase. The robot runs DHCP
   and gives out addresses in `172.31.1.0/24`. It is always host `.1` of that
   network (see `ap_ip` in the spec).
4. Send the Reset frame to the robot on UDP 5551.

The phone has no internet access while it is joined to the robot. That is
expected.

**Factory reset**: unknown. pycozmo describes no reset procedure. The robot
stores app data (progress, enrolled faces, saved cube ids) in NV storage, which
can be erased one entry at a time with the NvStorageOp message. That is a memory
operation, not a documented reset, and the spec leaves it out.

**Rebinding to a new network**: does not apply. The robot never joins a home
network.

## Pairing

| Property | Value |
|----------|-------|
| Pairing required | No |
| Security mode | `none` (the Wi-Fi passphrase is the only gate) |
| Bonding | `none` |
| PIN source | `device_screen` (the Wi-Fi passphrase on the robot's face) |
| One central at a time | Unknown (pycozmo's model has one engine per session) |
| One bond at a time | No |
| Confidence | medium |

The only gate is joining the robot's access point. After that, a Reset frame
opens a session with no key or challenge. The robot accepts datagrams only from
`172.31.1.0/24`. Close the Cozmo app on every phone before another client
connects.

## Protocol Summary

### Frames

Each UDP datagram is one frame. All integers are little-endian, and all floats
are IEEE-754 single precision unless stated otherwise.

| Offset | Length | Field |
|--------|--------|-------|
| 0 | 7 | id `43 4f 5a 03 52 45 01` ("COZ", 0x03, "RE", 0x01) |
| 7 | 1 | frame type |
| 8 | 2 | first_seq: first sequenced packet in this frame, or 0 |
| 10 | 2 | seq: last sequenced packet in this frame, or 0 |
| 12 | 2 | ack: newest sequence number received from the peer, or 0 |
| 14 | — | packets |

| Type | From | Meaning |
|------|------|---------|
| 0x01 | engine | Reset (opens a session; header only) |
| 0x02 | robot | Reset ACK (listed by pycozmo; in practice the robot answers with 0x09) |
| 0x03 | engine | Disconnect (header only) |
| 0x04 | engine | One command, sent as its id and payload with no packet header |
| 0x07 | engine | Zero or more packets |
| 0x09 | robot | Zero or more packets |
| 0x0b | engine | Out-of-band ping (17-byte body directly after the header) |

In 0x07 and 0x09 frames, each packet is `[type u8][length u16][body]`. Packet
types are 0x02 Connect, 0x03 Disconnect, 0x04 Command, 0x05 Event, 0x0a
Keyframe and 0x0b Ping. A Command or Event body starts with a one-byte message
id, and its length includes that id byte. Message ids 0x00–0xAF go from the
engine to the robot. Ids 0xB0–0xFF go from the robot to the engine. Ids
0xF0–0xFF are out-of-band Event streams.

### Selective-repeat ARQ

- Connect, Disconnect and Command packets are numbered by each sender, starting
  at 1 per session. The numbers wrap from 0xFFFE to 1, and 0 means "none".
  Event, Keyframe and Ping packets are out-of-band: they get no number and are
  never resent.
- The packets in a frame are numbered consecutively from `first_seq`, and `seq`
  is the number of the last one.
- `ack` is cumulative. Everything up to and including it leaves the sender's
  retransmission window.
- pycozmo uses a 62-packet window. It buffers out-of-order packets that fall
  inside the window and drops duplicates. It resends all unacknowledged packets
  with their original numbers if no ack arrives for 100 ms. The robot's own
  timer and window size are not documented.

### Session

1. Engine → `Reset` frame: first_seq 1, seq 1, ack 0.
2. Robot → 0x09 frame (1, 1, 1) holding `Connect` (`02 00 00`). The session is
   now open.
3. Robot → `HardwareInfo` (0xC9) and `FirmwareSignature` (0xEE). The signature
   is a JSON string that includes the firmware version. pycozmo targets
   firmware 2381.
4. Engine → `Enable` (0x25), sent twice. This powers the body, and the robot
   replies with `BodyInfo` (0xED).
5. Engine → `SetOrigin` (0x45) and `SyncTime` (0x4B). This starts the
   `RobotState` stream, which arrives about every 30 ms.
6. Engine → `EnableAnimationState` (0x9F) before it uses the face or the
   speaker.

**Keep-alive**: the engine sends a 0x0b ping frame every 0.5 s. The ping body is
an f64 time, a u32 counter, a u32 that is always 0, and one more byte that is
always 0. The robot echoes the body back in a Ping packet. After 5 s with no
ping, the robot drops the session and shows "COZMO 01".

**Disconnect**: send a 0x03 frame or a Disconnect packet in a 0x07 frame, then
send nothing more. pycozmo warns that packets sent after a disconnect have
rebooted robots or sent them back to factory firmware.

### Core commands

| Id | Name | Payload |
|----|------|---------|
| 0x32 | DriveWheels | f32 left speed mm/s, f32 right speed mm/s, f32 left accel, f32 right accel |
| 0x33 | TurnInPlaceAtSpeed | f32 speed mm/s, f32 accel, i16 direction |
| 0x34 / 0x35 | MoveLift / MoveHead | f32 speed rad/s |
| 0x36 | SetLiftHeight | f32 height mm (32–92), f32 max speed, f32 accel, f32 duration, u8 action id |
| 0x37 | SetHeadAngle | f32 angle rad (−25° to 44.5°), f32 max speed, f32 accel, f32 duration, u8 action id |
| 0x3B | StopAllMotors | — |
| 0x60 | EnableStopOnCliff | bool |
| 0x97 | DisplayImage | u16 length + run-length-encoded 128×32 image (structure only) |
| 0x8E / 0x8F | OutputAudio / OutputSilence | 744 u-law samples / — |
| 0x64 | SetRobotVolume | u16 0–65535 |
| 0xAF | FirmwareUpdate | u16 chunk id + 1024 bytes |

**Safety**: the treads keep turning until the next drive command or
`StopAllMotors`. Cozmo usually sits on a table, and it will drive off the edge
unless cliff stop is on or the client watches the `CLIFF_DETECTED` flag. The
spec marks the drive and spin commands `advanced`.

**Face and speaker**: the 128×64 OLED is used as a 128×32 image, because
alternate rows are interleaved to limit burn-in. Images use a column-wise
run-length code, and the two bytes `3f 3f` clear the face. pycozmo sends one
audio packet (OutputAudio or OutputSilence) and one image every 1/30 s. The
robot stops showing an image if it is not refreshed for 30 s.

### Robot state (0xF0)

This is a 91-byte out-of-band Event with these fields: u32 timestamp, u32 pose
frame id, u32 pose origin id, f32 pose x/y/z, f32 pose angle and pitch (rad),
f32 left and right wheel speed (mm/s), f32 head angle (rad), f32 lift height
(mm), f32 accelerometer x/y/z, f32 gyro x/y/z, f32 battery (V), u32 status
flags, 4 × u16 raw cliff readings, u16 raw backpack touch reading, and u8 path
segment. The status bits include IS_MOVING (0x1), IS_PICKED_UP (0x8),
LIFT_IN_POS (0x100), HEAD_IN_POS (0x200), IS_ON_CHARGER (0x1000), IS_CHARGING
(0x2000) and CLIFF_DETECTED (0x4000). The full table is in the spec.

### Firmware update

Images are `cozmo.safe` files. Each one starts with a JSON signature and holds
images for all three controllers. The engine sends the image in 1024-byte
`FirmwareUpdate` chunks, and the robot acknowledges each chunk with
`FirmwareUpdateResult` status 0. Chunk id 0xFFFF with zero data ends the
transfer, and the robot answers with status 10. The file format beyond its
header, and whether the robot checks the signatures, are unknown.

## Tools Used

- Reading pycozmo's documentation and source (no code was executed, and no
  hardware was available).

## References

- [zayfod/pycozmo](https://github.com/zayfod/pycozmo): the MIT-licensed engine every fact here comes from
- [pycozmo — Cozmo Protocol](https://github.com/zayfod/pycozmo/blob/master/docs/protocol.md)
- [pycozmo — Cozmo Functions](https://github.com/zayfod/pycozmo/blob/master/docs/functions.md)
- [pycozmo documentation](https://pycozmo.readthedocs.io/)

## Contributors

- Initial spec transcribed from pycozmo's documentation and code
