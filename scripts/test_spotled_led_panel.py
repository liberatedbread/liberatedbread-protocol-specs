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


def value_at(raw: bytes, field: dict) -> int:
    return int.from_bytes(
        raw[field["offset"] : field["offset"] + field["length"]],
        field.get("endianness", "big"),
    )


def assert_transfer_response(
    vector_hex: str, expected: dict, layout: dict
) -> bytes:
    raw = bytes.fromhex(vector_hex)

    assert value_at(raw, layout["total_length"]) == len(raw)
    assert value_at(raw, layout["response_type"]) == expected["response_type"]
    assert value_at(raw, layout["serial"]) == expected["serial"]
    assert value_at(raw, layout["command_type"]) == expected["command_type"]
    if "status" in layout:
        assert value_at(raw, layout["status"]) == expected["status"]
        assert expected["status"] == layout["status"]["success_value"] == 0
    else:
        assert layout["status_present"] is False
    return raw


def test_query_transfer_and_continue_response_scopes_are_disjoint():
    responses = DETAILS["legacy_responses"]
    query_types = set(responses["query_layout"]["response_types"])
    transfer_types = set(responses["transfer_ack_layout"]["response_types"])
    continue_types = set(responses["continue_layout"]["response_types"])

    assert query_types == {17, 19, 21, 27}
    assert transfer_types == {2, 4}
    assert continue_types == {255}
    assert query_types.isdisjoint(transfer_types | continue_types)
    assert transfer_types.isdisjoint(continue_types)


def test_display_info_response_matches_capture_derived_fields():
    raw = bytes.fromhex(DETAILS["test_vectors"]["display_info_response_hex"])
    expected = DETAILS["test_vectors"]["display_info_expected"]
    responses = DETAILS["legacy_responses"]
    layout = responses["query_layout"]
    fields = responses["display_info"]["fields"]

    assert 19 in layout["response_types"]
    assert value_at(raw, layout["total_length"]) == len(raw) == 13
    assert value_at(raw, layout["response_type"]) == 19
    for name in (
        "width",
        "height",
        "color_type",
        "advertised_max_frames",
        "brightness",
        "word_stock",
    ):
        assert value_at(raw, fields[name]) == expected[name]
    assert value_at(raw, layout["serial"]) == expected["serial"]
    assert value_at(raw, layout["status"]) == expected["status"]
    assert expected["status"] == layout["status"]["success_value"] == 0


def test_start_and_finish_acknowledgements_parse_status_and_command_type():
    vectors = DETAILS["test_vectors"]
    responses = DETAILS["legacy_responses"]
    acknowledgements = responses["transfer_acknowledgements"]

    for command, vector, expected in (
        ("sending_data_start", "start_response_hex", "start_expected"),
        ("sending_data_finish", "finish_response_hex", "finish_expected"),
    ):
        acknowledgement = acknowledgements[command]
        raw = assert_transfer_response(
            vectors[vector], vectors[expected], responses["transfer_ack_layout"]
        )
        assert len(raw) == acknowledgement["full_frame_bytes"] == 7
        assert vectors[expected]["response_type"] == acknowledgement["response_type"]


def test_continue_response_resume_offset_is_device_supplied():
    vectors = DETAILS["test_vectors"]
    expected = vectors["continue_expected"]
    responses = DETAILS["legacy_responses"]
    raw = assert_transfer_response(
        vectors["continue_response_hex"], expected, responses["continue_layout"]
    )
    flow = responses["flow_control"]

    assert len(raw) == flow["continue_full_frame_bytes"] == 10
    assert expected["response_type"] == flow["continue_response_type"] == 255
    assert expected["command_type"] == 0x8004
    assert value_at(raw, flow["continue_resume_offset"]) == expected["resume_offset"]
    assert expected["resume_offset"] == flow["confirmed_resume_offset"] == 7280



def test_capability_response_matches_captured_u16_fields():
    vectors = DETAILS["test_vectors"]
    raw = bytes.fromhex(vectors["capability_response_hex"])
    expected = vectors["capability_expected"]
    responses = DETAILS["legacy_responses"]
    layout = responses["query_layout"]
    capability = responses["animation_text_capability"]

    assert capability["response_type"] == 27
    assert capability["full_frame_bytes"] == len(raw) == 9
    assert value_at(raw, layout["total_length"]) == len(raw)
    assert value_at(raw, layout["response_type"]) == 27
    assert value_at(raw, layout["serial"]) == expected["serial"]
    assert value_at(raw, layout["status"]) == expected["status"] == 0
    for name in ("animation_frame_capacity", "character_capacity"):
        assert value_at(raw, capability["fields"][name]) == expected[name]
    assert capability["fields"]["optional_storage_bytes"]["offset"] == len(raw)
    assert capability["fields"]["optional_storage_bytes"]["verification"] == "reported"
