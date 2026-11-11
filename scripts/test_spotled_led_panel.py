"""Independent SPOTLED frame transcriptions using only the standard library."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC = yaml.safe_load(
    (ROOT / "device-specs" / "devices" / "spotled-led-panel.yaml").read_text(
        encoding="utf-8"
    )
)
DETAILS = SPEC["protocol_details"]


def checksum(data: bytes) -> int:
    total = sum(data)
    return ((~total) + 1) & 0xFF if total > 0xFF else total


def test_empty_data_header_matches_spec_vector():
    vector = bytes.fromhex(DETAILS["test_vectors"]["empty_data_header_hex"])
    expected = DETAILS["test_vectors"]["empty_data_header_expected"]

    header_length = (15).to_bytes(4, "big")
    command_type = (0x8004).to_bytes(2, "big")
    serial = (1).to_bytes(4, "big")
    content_length = (0).to_bytes(4, "big")
    covered = header_length + command_type + serial + content_length
    encoded = covered + bytes([checksum(covered)])

    assert encoded == vector
    assert len(encoded) == expected["header_length"]
    assert int.from_bytes(encoded[4:6], "big") == expected["command_type"]
    assert int.from_bytes(encoded[6:10], "big") == expected["serial"]
    assert int.from_bytes(encoded[10:14], "big") == expected["content_length"]
    assert encoded[-1] == expected["checksum"]


def test_checksum_preserves_small_sum_and_negates_overflow():
    assert checksum(bytes([0x80, 0x04, 0x0F])) == 0x93
    assert checksum(bytes([0xFF, 0x02])) == 0xFF
    assert checksum(bytes([0xFF, 0x03])) == 0xFE


def test_display_info_response_matches_capture_derived_fields():
    raw = bytes.fromhex(DETAILS["test_vectors"]["display_info_response_hex"])
    expected = DETAILS["test_vectors"]["display_info_expected"]
    fields = DETAILS["legacy_responses"]["display_info"]["fields"]

    assert raw[0] == len(raw) == 13
    assert raw[1] == 19
    for name in (
        "width",
        "height",
        "color_type",
        "advertised_max_frames",
        "brightness",
        "word_stock",
    ):
        field = fields[name]
        value = int.from_bytes(
            raw[field["offset"] : field["offset"] + field["length"]],
            field.get("endianness", "big"),
        )
        assert value == expected[name]
    assert int.from_bytes(raw[2:4], "big") == expected["serial"]
    assert raw[4] == expected["status"] == 0


def test_continue_response_resume_offset_is_device_supplied():
    raw = bytes.fromhex(DETAILS["test_vectors"]["continue_response_hex"])
    expected = DETAILS["test_vectors"]["continue_expected"]
    resume = DETAILS["legacy_responses"]["flow_control"]["continue_resume_offset"]

    assert raw[0] == len(raw) == 10
    assert raw[1] == expected["response_type"] == 255
    assert int.from_bytes(raw[2:4], "big") == expected["serial"]
    assert int.from_bytes(raw[4:6], "big") == expected["command_type"] == 0x8004
    assert int.from_bytes(
        raw[resume["offset"] : resume["offset"] + resume["length"]], "big"
    ) == expected["resume_offset"] == 7280
