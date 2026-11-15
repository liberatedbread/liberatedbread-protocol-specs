# Copyright 2026 Pigs Can Fly Labs LLC
# SPDX-License-Identifier: Apache-2.0
"""Proves the Cozmo spec's example frames follow its own stated layouts.

`device-specs/devices/anki-cozmo.yaml` says every UDP datagram is a 14-byte
header (the id "COZ\\x03RE\\x01", a frame type, and little-endian u16
first_seq / seq / ack) followed by packets of [type u8][length u16 LE][body],
where a Command or Event body starts with a message id and its length counts
that id. Ping frames carry the 17-byte Ping body straight after the header,
and RobotState is a 91-byte little-endian record. This module transcribes
those rules with the standard library alone, rebuilds every example frame
from invented values, and decodes the example RobotState frames back into
their fields, so an example that drifts from the stated layout fails here.
"""

from __future__ import annotations

import re
import struct
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SPEC_PATH = REPO_ROOT / "device-specs" / "devices" / "anki-cozmo.yaml"

FRAME_ID = b"COZ\x03RE\x01"
RESET, FIN, ENGINE, ROBOT, PING = 0x01, 0x03, 0x07, 0x09, 0x0B
PKT_CONNECT, PKT_DISCONNECT, PKT_COMMAND, PKT_EVENT, PKT_PING = 0x02, 0x03, 0x04, 0x05, 0x0B
OUT_OF_BAND = {PKT_EVENT, 0x0A, PKT_PING}

# Header every command example uses (spec: protocol_details...examples.notes).
EXAMPLE_FIRST_SEQ, EXAMPLE_SEQ, EXAMPLE_ACK = 16, 16, 7


def header(frame_type: int, first_seq: int, seq: int, ack: int) -> bytes:
    return FRAME_ID + struct.pack("<BHHH", frame_type, first_seq, seq, ack)


def packet(packet_type: int, body: bytes = b"") -> bytes:
    return struct.pack("<BH", packet_type, len(body)) + body


def command(message_id: int, payload: bytes = b"") -> bytes:
    return packet(PKT_COMMAND, bytes([message_id]) + payload)


def engine_frame(*packets: bytes) -> str:
    return (header(ENGINE, EXAMPLE_FIRST_SEQ, EXAMPLE_SEQ, EXAMPLE_ACK) + b"".join(packets)).hex()


def f32(*values: float) -> bytes:
    return struct.pack(f"<{len(values)}f", *values)


def ping_body(time_sent: float, counter: int) -> bytes:
    return struct.pack("<dIIB", time_sent, counter, 0, 0)


ROBOT_STATE_FORMAT = "<III16fI4HHB"
ROBOT_STATE_NAMES = (
    "timestamp pose_frame_id pose_origin_id pose_x pose_y pose_z pose_angle_rad "
    "pose_pitch_rad lwheel_speed_mmps rwheel_speed_mmps head_angle_rad lift_height_mm "
    "accel_x accel_y accel_z gyro_x gyro_y gyro_z battery_voltage status"
).split()


def decode_robot_state(payload: bytes) -> dict:
    values = struct.unpack(ROBOT_STATE_FORMAT, payload)
    state = dict(zip(ROBOT_STATE_NAMES, values[:20], strict=True))
    state["cliff_data_raw"] = list(values[20:24])
    state["backpack_touch_sensor_raw"] = values[24]
    state["curr_path_segment"] = values[25]
    return state


def parse_frame(raw: bytes) -> tuple[int, int, int, int, list[tuple[int, bytes]]]:
    assert raw[:7] == FRAME_ID
    frame_type, first_seq, seq, ack = struct.unpack_from("<BHHH", raw, 7)
    packets, offset = [], 14
    if frame_type in (ENGINE, ROBOT):
        while offset < len(raw):
            packet_type, length = struct.unpack_from("<BH", raw, offset)
            offset += 3
            packets.append((packet_type, raw[offset:offset + length]))
            offset += length
        assert offset == len(raw)
    return frame_type, first_seq, seq, ack, packets


@pytest.fixture(scope="module")
def spec() -> dict:
    return yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def cozmo(spec) -> dict:
    return spec["protocol_details"]["cozmo_udp"]


@pytest.fixture(scope="module")
def examples(cozmo) -> dict:
    return cozmo["examples"]


@pytest.fixture(scope="module")
def commands(spec) -> dict:
    return spec["commands"]


def test_header_layout_is_the_one_transcribed_here(cozmo):
    fields = {f["name"]: f for f in cozmo["frame_header"]["fields"]}
    assert bytes.fromhex(fields["id"]["value"]) == FRAME_ID
    assert [(f["offset"], f["length"]) for f in cozmo["frame_header"]["fields"]] == [
        (0, 7), (7, 1), (8, 2), (10, 2), (12, 2)
    ]
    assert cozmo["frame_header"]["size"] == 14 == len(header(RESET, 0, 0, 0))


def test_session_frames_rebuild(examples):
    assert examples["reset"] == header(RESET, 1, 1, 0).hex()
    assert examples["connect"] == (header(ROBOT, 1, 1, 1) + packet(PKT_CONNECT)).hex()
    body = ping_body(2.5, 4)
    assert len(body) == 17
    assert examples["ping"] == (header(PING, 0, 0, 1) + body).hex()
    assert examples["ping_echo"] == (header(ROBOT, 0, 0, 16) + packet(PKT_PING, body)).hex()
    assert examples["fin"] == header(FIN, 0, 0, 7).hex()


def test_ping_echo_copies_the_engine_ping(examples):
    ping = bytes.fromhex(examples["ping"])
    *_, packets = parse_frame(bytes.fromhex(examples["ping_echo"]))
    assert packets == [(PKT_PING, ping[14:])]


EXPECTED_COMMANDS = {
    "enable": command(0x25),
    "set_origin": command(0x45, struct.pack("<IIIffI", 0, 0, 1, 0.0, 0.0, 0x80000000)),
    "sync_time": command(0x4B, struct.pack("<II", 0, 0)),
    "enable_animation_state": command(0x9F),
    "drive_wheels": command(0x32, f32(50.0, 25.0, 100.0, 100.0)),
    "turn_in_place_at_speed": command(0x33, f32(40.0, 80.0) + struct.pack("<h", 1)),
    "stop_all_motors": command(0x3B),
    "enable_stop_on_cliff": command(0x60, b"\x01"),
    "move_head": command(0x35, f32(1.0)),
    "set_head_angle": command(0x37, f32(0.5, 10.0, 10.0, 0.0) + b"\x00"),
    "move_lift": command(0x34, f32(-2.0)),
    "set_lift_height": command(0x36, f32(60.0, 10.0, 10.0, 0.0) + b"\x00"),
    "display_image_clear": command(0x97, struct.pack("<H", 2) + b"\x3f\x3f"),
    "output_silence": command(0x8F),
    "set_robot_volume": command(0x64, struct.pack("<H", 20000)),
    "disconnect": packet(PKT_DISCONNECT),
}


@pytest.mark.parametrize("name", sorted(EXPECTED_COMMANDS))
def test_command_example_rebuilds_from_the_layout(commands, name):
    assert commands[name]["example_body"] == engine_frame(EXPECTED_COMMANDS[name])


@pytest.mark.parametrize("name", sorted(EXPECTED_COMMANDS))
def test_literal_body_matches_the_packet_in_its_example(commands, name):
    """Where `body` has no holes it is the packet itself, byte for byte."""
    body = commands[name]["body"]
    if "{" in body:
        pytest.skip("templated body")
    assert bytes.fromhex(body.replace(" ", "")) == EXPECTED_COMMANDS[name]


HOLE = re.compile(r"\{(\w+)\}")
WIDTH = {"float32": 4, "uint8": 1, "int16": 2, "uint16": 2}


@pytest.mark.parametrize("name", sorted(EXPECTED_COMMANDS))
def test_templated_body_widths_match_the_example(commands, name):
    """A template's literal bytes plus its declared field widths give the example packet."""
    cmd = commands[name]
    body = cmd["body"]
    if "{" not in body:
        pytest.skip("literal body")
    params = cmd["parameters"]
    size, prefix = 0, None
    for token in body.split():
        hole = HOLE.fullmatch(token)
        if hole:
            size += WIDTH[params[hole.group(1)]["type"]]
        else:
            size += len(bytes.fromhex(token))
            if prefix is None:
                prefix = bytes.fromhex(token)
    expected = EXPECTED_COMMANDS[name]
    assert size == len(expected)
    literal_head = bytes.fromhex("".join(t for t in body.split()[:4] if not HOLE.fullmatch(t)))
    assert expected.startswith(literal_head)
    assert set(HOLE.findall(body)) == set(params)


def test_length_fields_count_the_message_id(commands):
    for name, cmd in commands.items():
        raw = bytes.fromhex(cmd["example_body"]) if "example_body" in cmd else None
        if raw is None:
            continue
        frame_type, first_seq, seq, ack, packets = parse_frame(raw)
        assert (frame_type, first_seq, seq, ack) == (ENGINE, 16, 16, 7), name
        assert len(packets) == 1, name


def test_output_audio_and_firmware_templates_have_the_stated_sizes(commands):
    audio = commands["output_audio"]
    head = bytes.fromhex(audio["body"].split("{")[0].replace(" ", ""))
    assert head == struct.pack("<BH", PKT_COMMAND, 744 + 1) + b"\x8e"
    assert audio["parameters"]["samples"]["min_length"] == 744
    fw = commands["firmware_update_chunk"]
    head = bytes.fromhex(fw["body"].split("{")[0].replace(" ", ""))
    assert head == struct.pack("<BH", PKT_COMMAND, 1 + 2 + 1024) + b"\xaf"
    assert fw["advanced"] is True
    # The largest packet still fits the stated 1037-byte frame payload limit.
    assert 3 + 1 + 2 + 1024 <= 1037


def test_motion_commands_are_advanced(commands):
    for name in ("drive_wheels", "turn_in_place_at_speed"):
        assert commands[name]["advanced"] is True
        assert "edge" in commands[name]["advanced_reason"]


def test_robot_state_layout_offsets_are_packed(cozmo):
    fields = cozmo["robot_state"]["fields"]
    widths = {"uint32": 4, "float32": 4, "uint16": 2, "uint8": 1, "uint16[4]": 8}
    offset = 0
    for field in fields:
        assert field["offset"] == offset, field["name"]
        offset += widths[field["type"]]
    assert offset == 91 == struct.calcsize(ROBOT_STATE_FORMAT)


def _robot_state(examples, key) -> tuple[tuple, dict]:
    raw = bytes.fromhex(examples[key])
    frame_type, first_seq, seq, ack, packets = parse_frame(raw)
    assert len(packets) == 1
    packet_type, body = packets[0]
    assert packet_type == PKT_EVENT and packet_type in OUT_OF_BAND
    assert body[0] == 0xF0 and len(body) == 92
    return (frame_type, first_seq, seq, ack), decode_robot_state(body[1:])


def test_robot_state_on_desk_decodes(examples, cozmo):
    head, state = _robot_state(examples, "robot_state_on_desk")
    # Events-only frame: no sequenced packets, so first_seq and seq are 0.
    assert head == (ROBOT, 0, 0, 16)
    assert state["timestamp"] == 123456
    assert (state["pose_frame_id"], state["pose_origin_id"]) == (0, 1)
    assert (state["pose_x"], state["pose_y"], state["pose_z"]) == (10.0, -5.0, 0.0)
    assert state["pose_angle_rad"] == 0.25
    assert state["head_angle_rad"] == -0.25
    assert state["lift_height_mm"] == 32.0
    assert state["battery_voltage"] == pytest.approx(3.9, abs=1e-6)
    assert state["cliff_data_raw"] == [200, 210, 205, 198]
    flags = {int(k, 16): v for k, v in cozmo["robot_state"]["status_flags"].items()}
    set_flags = {v for k, v in flags.items() if state["status"] & k}
    assert set_flags == {"LIFT_IN_POS", "HEAD_IN_POS"}


def test_robot_state_on_charger_decodes(examples, cozmo):
    _, state = _robot_state(examples, "robot_state_on_charger")
    assert state["timestamp"] == 987654
    assert (state["pose_frame_id"], state["pose_origin_id"]) == (2, 3)
    assert (state["pose_x"], state["pose_y"]) == (120.5, 40.0)
    assert state["pose_angle_rad"] == -1.5
    assert (state["lwheel_speed_mmps"], state["rwheel_speed_mmps"]) == (30.0, 30.0)
    assert state["head_angle_rad"] == pytest.approx(0.1, abs=1e-6)
    assert state["lift_height_mm"] == 45.0
    assert state["battery_voltage"] == 4.75
    assert state["cliff_data_raw"] == [180, 181, 182, 183]
    assert state["curr_path_segment"] == 2
    flags = {int(k, 16): v for k, v in cozmo["robot_state"]["status_flags"].items()}
    set_flags = {v for k, v in flags.items() if state["status"] & k}
    assert set_flags == {"IS_MOVING", "IS_ON_CHARGER", "IS_CHARGING"}


def test_payload_format_example_is_the_desk_state(spec, examples):
    raw = bytes.fromhex(examples["robot_state_on_desk"])
    assert spec["payload_formats"]["RobotState"]["example"] == raw[14 + 4:].hex()
    names = [f["name"] for f in spec["payload_formats"]["RobotState"]["fields"]]
    assert names == ROBOT_STATE_NAMES + [
        "cliff_data_raw", "backpack_touch_sensor_raw", "curr_path_segment"
    ]


def test_sequence_numbers_follow_the_stated_rule():
    """Sequenced packets in one frame are consecutive from first_seq; out-of-band
    packets take no number; wire numbers run 1..0xFFFE and wrap to 1."""

    def number(first_seq: int, packet_types: list[int]) -> int:
        seq, last = first_seq, None
        for packet_type in packet_types:
            if packet_type in OUT_OF_BAND:
                continue
            last = seq
            seq = 1 if seq == 0xFFFE else seq + 1
        return last

    assert number(2717, [PKT_COMMAND] * 4) == 2720
    assert number(5, [PKT_COMMAND, PKT_EVENT, PKT_COMMAND]) == 6
    assert number(0xFFFE, [PKT_COMMAND, PKT_COMMAND]) == 1


def test_examples_identify_no_real_unit(spec):
    text = SPEC_PATH.read_text(encoding="utf-8")
    assert not re.search(r"Cozmo_[0-9A-F]{6}(?![0-9A-Fa-f])", text), "use Cozmo_XXXXXX"
    assert spec["device"]["pairing"]["pin"]["source"] == "device_screen"
    assert "value" not in spec["device"]["pairing"]["pin"]
