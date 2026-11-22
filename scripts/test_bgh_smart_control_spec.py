# Copyright 2026 Pigs Can Fly Labs LLC
# SPDX-License-Identifier: Apache-2.0
"""Proves the BGH Smart Control spec's frames are what the document says.

`device-specs/devices/bgh-smart-control.yaml` states one rule for every
datagram: a 17-byte header (version 0x00, six zero bytes of source MAC, the
destination MAC, a sequence byte, source and destination endpoints, a command
byte), then the payload, and nothing after it -- no length field and no
checksum. Each command publishes a byte `template` and an `example_body`
built from invented values (the RFC 7042 documentation MAC
00:00:5E:00:53:01, a placeholder SSID and passphrase).

This module transcribes the header rule and the template encoding with the
standard library alone, renders every command from the invented values its
`example_notes` describe, and holds the result to the spec's own example. It
then decodes the spec's status, ACK, IR-status, enumerate and codec frames
with the layouts `payload_formats` states and checks them against the
decoded values the spec publishes -- the contract `test_wemo_spec.py` keeps
for the Wemo crypto.
"""

from __future__ import annotations

import re
import struct
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SPEC_PATH = REPO_ROOT / "device-specs" / "devices" / "bgh-smart-control.yaml"
PLACEHOLDER = re.compile(r"^\{([A-Za-z_][A-Za-z0-9_]*)\}$")

UNIT_MAC = bytes.fromhex("00005e005301")
BROADCAST_MAC = b"\xff" * 6

# Caller-supplied and read-back values for each command, matching what its
# example_notes say it was rendered with. `sequence` comes from the notes.
INVENTED = {
    "set_hvac_mode": {"mode": 1, "fan": 2, "flags": 0, "target_raw": 2400},
    "set_temperature": {"mode": 1, "fan": 2, "flags": 0, "target_raw": 2250},
    "set_fan_mode": {"mode": 1, "fan": 3, "flags": 0, "target_raw": 2400},
    "set_swing": {"mode": 1, "fan": 2, "flags": 0x10, "target_raw": 2400},
    "set_ir_codec": {"codec": 60, "sensor": 1},
    "set_temperature_offset": {"offset_raw": -50},
    "set_cloud_ip": {"cloud_ip": "192.168.1.50"},
    "wifi_join": {"ssid": "ExampleNet", "password": "correct horse",
                  "security": 3, "encryption": 4},
}

WIDTHS = {"uint8": (1, False), "int8": (1, True), "uint16": (2, False),
          "int16": (2, True), "uint32": (4, False), "int32": (4, True)}


@pytest.fixture(scope="module")
def spec() -> dict:
    return yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def proto(spec) -> dict:
    return spec["protocol_details"]["bgh_udp"]


def build_header(dest_mac: bytes, sequence: int, src_ep: int, dst_ep: int,
                 command: int) -> bytes:
    """protocol_details.bgh_udp.header, transcribed."""
    assert len(dest_mac) == 6
    return bytes([0x00]) + bytes(6) + dest_mac + bytes(
        [sequence & 0xFF, src_ep, dst_ep, command]
    )


def encode(value, definition: dict) -> bytes:
    """One template hole, by the parameter's declared type."""
    kind = definition["type"]
    if kind == "bytes":
        assert len(value) == definition["max_length"] == definition["min_length"]
        return bytes(value)
    if kind == "string":
        # protocol_details.bgh_udp.string_fields: UTF-8, truncated and
        # NUL-padded to exactly max_length.
        raw = value.encode("utf-8")[: definition["max_length"]]
        return raw.ljust(definition["max_length"], b"\x00")
    width, signed = WIDTHS[kind]
    order = definition.get("endianness", "little")
    return int(value).to_bytes(width, order, signed=signed)


def render(name: str, command: dict, sequence: int) -> bytes:
    params = command.get("parameters") or {}
    supplied = {"device_mac": UNIT_MAC, "sequence": sequence, **INVENTED.get(name, {})}
    out = bytearray()
    for element in command["template"]:
        if isinstance(element, int):
            out.append(element)
            continue
        key = PLACEHOLDER.match(element).group(1)
        definition = params[key]
        if definition.get("auto") == "sequence":
            value = sequence
        elif key in supplied:
            value = supplied[key]
        else:
            value = definition["default"]
        out += encode(value, definition)
    return bytes(out)


def example_sequence(command: dict) -> int:
    match = re.search(r"[Ss]equence (\d+)", command["example_notes"])
    assert match, "example_notes must name the sequence the example used"
    return int(match.group(1))


def all_commands(spec):
    return sorted(spec["commands"].items())


def test_every_command_is_a_template_with_an_example(spec):
    for name, command in all_commands(spec):
        assert command["transport"] == "udp", name
        assert isinstance(command.get("template"), list), name
        assert command.get("example_body"), name
        assert command.get("verification") == "reported", name


@pytest.mark.parametrize("name", [
    "discover", "keepalive", "subscribe_status", "poll_hvac_status",
    "set_hvac_mode", "set_temperature", "set_fan_mode", "set_swing",
    "turn_off", "request_ir_status", "learn_mode_on", "learn_mode_off",
    "set_ir_codec", "calibrate_vibration", "set_temperature_offset",
    "get_cloud_ip", "set_cloud_ip", "wifi_scan", "wifi_join", "reboot",
    "leave", "ir_beep_test",
])
def test_template_renders_to_its_example(spec, name):
    command = spec["commands"][name]
    rendered = render(name, command, example_sequence(command))
    assert rendered.hex() == command["example_body"], name


def test_every_command_follows_the_header_rule(spec, proto):
    """Bytes 0-16 are exactly what build_header makes, and the command byte
    is one the spec's command table names."""
    table = {int(code, 16) for code in proto["commands"]}
    assert proto["header"]["length"] == 17
    for name, command in all_commands(spec):
        frame = bytes.fromhex(command["example_body"])
        dest = frame[7:13]
        assert dest in (UNIT_MAC, BROADCAST_MAC), name
        cmd = frame[16]
        assert cmd in table, f"{name}: command byte {cmd:#x} not in the table"
        # Endpoint 1 is the HVAC endpoint: SetMode (0x61) and Poll (0xE4).
        expected_dst_ep = 1 if cmd in (0x61, 0xE4) else 0
        assert frame[:17] == build_header(dest, frame[13], 0, expected_dst_ep, cmd), name


def test_frames_carry_no_checksum_or_length(spec):
    """Nothing follows the payload: header + payload is the whole datagram."""
    expected_payload = {
        "discover": 1, "keepalive": 0, "subscribe_status": 1,
        "poll_hvac_status": 0, "set_hvac_mode": 5, "set_temperature": 5,
        "set_fan_mode": 5, "set_swing": 5, "turn_off": 1,
        "request_ir_status": 2, "set_ir_codec": 3, "set_cloud_ip": 17,
        "wifi_join": 69, "reboot": 0, "leave": 0, "ir_beep_test": 5,
    }
    for name, length in expected_payload.items():
        frame = bytes.fromhex(spec["commands"][name]["example_body"])
        assert len(frame) == 17 + length, name
    assert len(bytes.fromhex(spec["commands"]["wifi_join"]["example_body"])) == 86


def test_setpoint_is_int16_le_hundredths(spec):
    frame = bytes.fromhex(spec["commands"]["set_temperature"]["example_body"])
    mode, fan, flags, raw = struct.unpack("<BBBh", frame[17:])
    assert (mode, fan, flags) == (1, 2, 0)
    assert raw * 0.01 == pytest.approx(22.5)
    param = spec["commands"]["set_temperature"]["parameters"]["target_raw"]
    assert param["scale"] == 0.01 and param["endianness"] == "little"
    assert param["type"] == "int16"


def test_beep_test_sends_the_no_setpoint_sentinel(spec, proto):
    frame = bytes.fromhex(spec["commands"]["ir_beep_test"]["example_body"])
    assert struct.unpack("<h", frame[20:22])[0] == -32768
    assert "0x8000" in proto["values"]["setpoint_sentinel"]


def test_wifi_join_layout_is_the_33_byte_form(spec):
    frame = bytes.fromhex(spec["commands"]["wifi_join"]["example_body"])
    payload = frame[17:]
    assert payload[0] == 3
    assert payload[1:34].rstrip(b"\x00") == b"ExampleNet"
    assert payload[34:36] == bytes([3, 4])
    assert payload[36:69].rstrip(b"\x00") == b"correct horse"


def test_discovery_probe_is_the_discover_command(spec):
    method = spec["device"]["discovery"]["methods"][0]
    probe = method["udp_broadcast"]["probe_hex"]
    assert probe == spec["commands"]["discover"]["example_body"]
    assert method["udp_broadcast"]["port"] == 20910
    assert method["udp_broadcast"]["listen_port"] == 20911


# --- decoding the spec's own frames -----------------------------------------

def mac_str(raw: bytes) -> str:
    return ":".join(f"{b:02X}" for b in raw)


def decode(frame: bytes) -> dict:
    """The payload_formats layouts, transcribed."""
    assert frame[0] == 0x00 and len(frame) >= 17
    out = {"source_mac": mac_str(frame[1:7]), "sequence": frame[13],
           "command": frame[16]}
    payload = frame[17:]
    cmd = frame[16]
    if cmd == 0xFD:
        assert len(frame) == 29 and frame[7:13] == BROADCAST_MAC
        status_type, mode, fan, flags, room, target, t_on, t_off = struct.unpack(
            "<BBBBhhHH", payload
        )
        out.update(status_type=status_type, mode=mode, fan=fan, flags=flags,
                   room_temperature=room / 100, target_temperature=target / 100,
                   timer_on_minutes=t_on, timer_off_minutes=t_off)
    elif cmd == 0xA2 and payload[0] == 92:
        out.update(subcommand=92, rssi=payload[1],
                   battery=struct.unpack("<H", payload[2:4])[0],
                   ir_mac=mac_str(frame[-6:]))
    elif cmd == 0xA2 and payload[0] == 95:
        out.update(subcommand=95, codec=payload[1])
    elif cmd == 0xA1 and payload[0] == 2:
        info = payload[1:].split(b"\x00", 1)[0].decode("ascii")
        out.update(subcommand=2, info=info, firmware=info.split(",")[1])
    return out


def test_vectors_decode_to_what_the_spec_says(proto):
    vectors = proto["test_vectors"]["frames"]
    assert {v["name"] for v in vectors} >= {
        "status_report", "ack", "ir_status_reply", "enumerate_reply", "codec_detected"
    }
    for vector in vectors:
        got = decode(bytes.fromhex(vector["hex"]))
        for key, want in vector["decoded"].items():
            if isinstance(want, float):
                assert got[key] == pytest.approx(want), (vector["name"], key)
            else:
                assert got[key] == want, (vector["name"], key)


def test_status_vector_is_rebuilt_from_the_layout(proto, spec):
    """Encode the invented state with the stated layout; it must be the
    spec's status frame, which must also be payload_formats' example."""
    frame = build_header(BROADCAST_MAC, 0x2A, 1, 0, 0xFD)
    frame = bytes([0x00]) + UNIT_MAC + frame[7:]
    frame += struct.pack("<BBBBhhHH", 6, 1, 2, 0x10, 2375, 2400, 0, 0)
    vector = next(v for v in proto["test_vectors"]["frames"] if v["name"] == "status_report")
    assert frame.hex() == vector["hex"]
    assert spec["payload_formats"]["HvacStatusReport"]["example"] == vector["hex"]


def test_reply_examples_agree_with_the_vectors(spec, proto):
    by_name = {v["name"]: v["hex"] for v in proto["test_vectors"]["frames"]}
    formats = spec["payload_formats"]
    assert formats["IrUnitStatus"]["example"] == by_name["ir_status_reply"]
    assert formats["EnumerateReply"]["example"] == by_name["enumerate_reply"]
    assert formats["CodecDetected"]["example"] == by_name["codec_detected"]


def test_mode_codes_match_the_set_command(spec, proto):
    param = spec["commands"]["set_hvac_mode"]["parameters"]["mode"]
    table = proto["values"]["mode"]
    assert [int(k) for k in table] == param["allowed"]


def test_only_invented_identifiers(spec):
    """Every MAC in a vector is in the RFC 7042 documentation block."""
    text = SPEC_PATH.read_text(encoding="utf-8").lower()
    for match in re.finditer(r"\b([0-9a-f]{2}(?::[0-9a-f]{2}){5})\b", text):
        mac = match.group(1)
        assert mac.startswith("00:00:5e:00:53:") or mac == "ff:ff:ff:ff:ff:ff", mac
    for vector in spec["protocol_details"]["bgh_udp"]["test_vectors"]["frames"]:
        assert bytes.fromhex(vector["hex"])[1:7] == UNIT_MAC
