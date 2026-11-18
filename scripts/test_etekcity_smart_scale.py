"""Independent Etekcity ESN00 frame, checksum and weight-report vectors."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC = yaml.safe_load(
    (ROOT / "device-specs/devices/etekcity-smart-scale.yaml").read_text(
        encoding="utf-8"
    )
)
DETAILS = SPEC["protocol_details"]["esn00"]


def frame(report_type, payload):
    body = bytes([report_type, len(payload)]) + payload
    return bytes.fromhex("fe ef c0 a2") + body + bytes([sum(body) & 0xFF])


def decode(raw):
    assert raw[:4] == bytes.fromhex(DETAILS["framing"]["prefix_hex"])
    payload_length = raw[5]
    assert len(raw) == payload_length + 7
    payload = raw[6:-1]
    assert len(payload) == payload_length
    assert raw[-1] == (raw[4] + raw[5] + sum(payload)) & 0xFF
    return raw[4], payload


def test_set_unit_gram_audit_vector():
    vector = DETAILS["set_unit_gram_vector"]
    raw = bytes.fromhex(vector["frame_hex"])
    assert raw == frame(0xC0, b"\0")
    assert decode(raw) == (0xC0, b"\0")
    assert len(raw) == vector["total_length"] == 8
    assert raw[-1] == vector["checksum"] == 0xC1


def test_synthetic_weight_report_is_big_endian_and_scaled():
    raw = frame(0xD0, bytes.fromhex("00 03 e8 00 01"))
    report_type, payload = decode(raw)
    assert report_type == 0xD0
    assert raw.hex(" ") == "fe ef c0 a2 d0 05 00 03 e8 00 01 c1"
    assert payload[0] == 0
    assert int.from_bytes(payload[1:3], "big") * 0.1 == 100.0
    assert payload[3:5] == bytes([0, 1])
    assert DETAILS["reports"]["non_weight_fault_types"] == [0xE0, 0xE2]


def test_item_state_is_normal_presence_not_a_fault():
    item = DETAILS["reports"]["item_state"]
    for key, payload, expected in (
        ("present_frame_hex", 0, True),
        ("absent_frame_hex", 1, False),
    ):
        raw = bytes.fromhex(item[key])
        report_type, decoded_payload = decode(raw)
        assert report_type == 0xE4
        assert decoded_payload == bytes([payload])
        assert (decoded_payload[0] == 0) is expected
    assert "not a fault" in item["semantics"]
