"""Independent Bangle.js NUS/JSON transcriptions using the standard library.

No Gadgetbridge, Espruino or repository client code is imported. Test identifiers,
firmware versions, health values and files are invented. No BLE or HTTP call occurs.
"""

import json
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = ROOT / "device-specs" / "devices" / "banglejs-watches.yaml"


@pytest.fixture(scope="module")
def spec():
    return yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))


def hx(value):
    return bytes.fromhex(value)


def encode_gb(message):
    encoded = json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode()
    return b"\x10GB(" + encoded + b")\n"


def parse_gb_frame(frame):
    if not frame.startswith(b"\x10GB(") or not frame.endswith(b")\n"):
        raise ValueError("not one GB frame")
    message = json.loads(frame[4:-2].decode("utf-8"))
    if not isinstance(message, dict):
        raise ValueError("GB payload is not an object")
    return message


class GBParser:
    def __init__(self):
        self.buffer = bytearray()
        self.messages = []
        self.errors = []

    def feed(self, data):
        self.buffer.extend(data)
        while True:
            end = self.buffer.find(b"\n")
            if end < 0:
                return
            frame = bytes(self.buffer[: end + 1])
            del self.buffer[: end + 1]
            try:
                self.messages.append(parse_gb_frame(frame))
            except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
                self.errors.append(frame)


class WatchJSONParser:
    def __init__(self):
        self.buffer = bytearray()
        self.messages = []
        self.errors = []

    def feed(self, data):
        self.buffer.extend(data)
        while True:
            end = self.buffer.find(b"\n")
            if end < 0:
                return
            line = bytes(self.buffer[:end])
            del self.buffer[: end + 1]
            if not line.startswith(b"{"):
                continue
            try:
                message = json.loads(line.decode("utf-8"))
                if not isinstance(message, dict):
                    raise ValueError("not an object")
            except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
                self.errors.append(line)
                continue
            self.messages.append(message)


def test_find_watch_vector_and_command(spec):
    vector = spec["protocol_details"]["common_messages"]["test_vector"]
    frame = hx(vector["phone_frame_hex"])
    assert parse_gb_frame(frame) == {"t": "find", "n": True}
    assert encode_gb({"t": "find", "n": True}) == frame
    command = spec["services"][0]["characteristics"][0]["commands"]["find_watch_start"]
    assert bytes(command["value"]) == frame
    assert command["locate"] == "both"
    assert command.get("advanced") is not True


def test_phone_fragmentation_at_every_split():
    message = {
        "t": "weather",
        "temp": -3.5,
        "txt": "snow",
        "loc": "Testville",
        "nested": {"arbitrary": [1, 2, 3]},
    }
    wire = encode_gb(message)
    for split in range(len(wire) + 1):
        parser = GBParser()
        parser.feed(wire[:split])
        parser.feed(wire[split:])
        assert parser.errors == []
        assert parser.messages == [message], split


def test_watch_json_lines_console_noise_and_unknown_type(spec):
    lines = spec["protocol_details"]["common_messages"]["test_vector"]["watch_lines"]
    wire = b"REPL output\n" + lines.encode() + b'{"t":"newFutureType","x":7}\n'
    parser = WatchJSONParser()
    for byte in wire:
        parser.feed(bytes([byte]))
    assert parser.errors == []
    assert parser.messages[:2] == [
        {"t": "status", "bat": 87, "chg": 0},
        {"t": "ver", "fw": "2v99", "hw": "2"},
    ]
    assert parser.messages[2] == {"t": "newFutureType", "x": 7}
    assert parser.messages[2]["t"] != "notify"


def test_malformed_frames_do_not_consume_later_valid_messages():
    parser = GBParser()
    parser.feed(b"GB({\"t\":\"find\"})\n")
    parser.feed(b"\x10GB([1,2])\n")
    parser.feed(b"\x10GB({broken})\n")
    parser.feed(encode_gb({"t": "find", "n": False}))
    assert len(parser.errors) == 3
    assert parser.messages == [{"t": "find", "n": False}]

    watch = WatchJSONParser()
    watch.feed(b"{broken}\n[1,2]\n{\"t\":\"status\",\"bat\":50}\n")
    assert watch.messages == [{"t": "status", "bat": 50}]
    assert watch.errors == [b"{broken}"]


def test_uart_roles_and_active_scan(spec):
    roles = spec["protocol_details"]["uart_roles"]
    assert roles["host_to_watch"]["characteristic"].endswith("0002-b5a3-f393-e0a9-e50e24dcca9e")
    assert roles["watch_to_host"]["characteristic"].endswith("0003-b5a3-f393-e0a9-e50e24dcca9e")
    assert "0x10" in roles["host_to_watch"]["framing"]
    assert "no 0x10" in roles["watch_to_host"]["framing"]
    service = spec["services"][0]
    assert service["uuid"] == "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
    assert service["initialization"][0]["characteristic"] == roles["watch_to_host"]["characteristic"]
    discovery = spec["device"]["discovery"]["methods"][0]
    assert "active" in discovery["notes"].lower()
    assert "not enough" in spec["device"]["identification"]["notes"]


def test_common_message_families_remain_json_not_binary_gatt(spec):
    common = spec["protocol_details"]["common_messages"]
    phone = {entry["t"] for entry in common["phone_to_watch"]}
    watch = {entry["t"] for entry in common["watch_to_phone"]}
    assert {"notify", "alarm", "weather", "musicstate", "musicinfo", "call", "act", "calendar", "gps", "nav"} <= phone
    assert {"status", "ver", "findPhone", "music", "call", "notify", "act", "actTrk", "gps_power"} <= watch
    for characteristic in spec["services"][0]["characteristics"]:
        assert "format" not in characteristic or characteristic["uuid"].endswith("0002-b5a3-f393-e0a9-e50e24dcca9e")


def test_privileged_surfaces_are_optional_advanced_and_separate(spec):
    privileged = spec["protocol_details"]["privileged_surfaces"]
    entries = {entry["name"]: entry for entry in privileged["entries"]}
    assert {"arbitrary_javascript_repl", "app_loader_file_and_code_upload", "http_relay", "phone_file_write", "android_intents"} == set(entries)
    for entry in entries.values():
        assert entry["optional"] is True
        assert entry["advanced"] is True
        assert entry["default_enabled"] is False
        assert entry["advanced_reason"]
    assert "HTTPS" in entries["http_relay"]["advanced_reason"]
    assert "insecure:false" in entries["http_relay"]["advanced_reason"]
    command = spec["services"][0]["characteristics"][0]["commands"]["evaluate_javascript"]
    assert command["advanced"] is True
    assert "optional" not in command
    assert "OPTIONAL" in command["description"]
    assert command["advanced_reason"]
    assert len(spec["entities"]) == 1
    assert spec["entities"][0]["commands"] == {"press": "find_watch_start"}


def test_reset_clean_boot_and_unpair_are_distinct(spec):
    setup = spec["device"]["setup"]
    procedures = setup["factory_reset"]["procedures"]
    assert {procedure["applies_to"][0] for procedure in procedures[:2]} == {"Bangle.js 1", "Bangle.js 2"}
    assert all(procedure["verified"] is False for procedure in procedures)
    assert setup["rejoin"]["requires_factory_reset"] is False
    assert spec["device"]["pairing"]["unpair"]["requires_factory_reset"] is False
    assert "2v30+" in spec["device"]["pairing"]["unpair"]["procedures"][0]["name"]
    reset = spec["protocol_details"]["reset_vs_clean_boot"]
    assert "without deleting" in reset["clean_boot"]
    assert "not a factory reset" in reset["delete_pairing"]


def test_scope_excludes_bangle3_and_unverified_dfu_stack(spec):
    assert len(spec["device"]["variants"]) == 2
    assert "Bangle.js 3" in spec["protocol_details"]["out_of_scope"][0]
    for feature in spec["features"]:
        assert feature["dfu"]["mechanisms"] != ["nordic_secure_dfu"]
        assert feature["dfu"]["verification"] == "reported"
