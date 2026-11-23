"""Smarter iKettle status, calibrated water and command-ACK vectors."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC = yaml.safe_load(
    (ROOT / "device-specs/devices/smarter-ikettle.yaml").read_text(encoding="utf-8")
)
PROTOCOL = SPEC["protocol_details"]["smarter_protocol"]


def test_off_base_status_vector_uses_big_endian_water_and_7f_unavailable():
    vector = PROTOCOL["status_frame"]["synthetic_off_base_vector"]
    frame = bytes.fromhex(vector["frame_hex"])
    assert len(frame) == PROTOCOL["status_frame"]["full_frame_bytes"] == 7
    assert frame[0] == 0x14 and frame[-1] == 0x7E
    flag = frame[1]
    assert PROTOCOL["status_frame"]["flags"][flag] == vector["expected_flag"]
    temperature = None if frame[2] == 0x7F else frame[2]
    assert temperature is vector["expected_temperature"]
    water_raw = int.from_bytes(frame[3:5], "big")
    assert water_raw == vector["expected_water_raw"] == 2007
    assert water_raw != int.from_bytes(frame[3:5], "little")
    assert frame[5] == vector["expected_unknown"]


def test_ack_result_values_and_layout():
    ack = PROTOCOL["command_ack"]
    assert ack["layout"] == "[0x03][result][0x7e]"
    assert ack["results"] == {0: "success", 1: "busy", 4: "failed", 105: "invalid"}
    for result, meaning in ack["results"].items():
        frame = bytes([0x03, result, 0x7E])
        assert len(frame) == ack["full_frame_bytes"] == 3
        assert ack["results"][frame[ack["result_offset"]]] == meaning
