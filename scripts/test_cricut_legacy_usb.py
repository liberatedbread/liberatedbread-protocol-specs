# Copyright 2026 Pigs Can Fly Labs LLC
# SPDX-License-Identifier: Apache-2.0
"""Independently decode the four reported stock Cricut USB query vectors.

Only Python's standard library supplies the request builder and response parser;
no project protocol implementation is imported. PyYAML is used only to read the
spec. Vectors are licut's published examples, not captures made by this project.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SPEC_PATH = REPO_ROOT / "device-specs" / "devices" / "cricut-legacy-usb.yaml"
QUERY_OPCODES = {0x11: 8, 0x12: 6, 0x14: 4, 0x18: 38}


@pytest.fixture(scope="module")
def spec() -> dict:
    return yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def vectors(spec) -> dict:
    return spec["protocol_details"]["published_vectors"]


class ProtocolError(ValueError):
    pass


def build_request(opcode: int, width: int = 5) -> bytes:
    if opcode not in QUERY_OPCODES:
        raise ProtocolError("opcode is outside the read-only query surface")
    if width != 5:
        raise ProtocolError("only the five-byte implementation request is executable")
    return bytes([0x04, opcode]) + bytes(width - 2)


def u16be(data: bytes) -> int:
    return int.from_bytes(data, "big")


def take_response(buffer: bytes, opcode: int) -> tuple[dict, bytes]:
    if not buffer:
        raise ProtocolError("truncated length prefix")
    body_length = buffer[0]
    expected = QUERY_OPCODES.get(opcode)
    if expected is None:
        raise ProtocolError("response opcode is outside the query surface")
    if body_length != expected:
        raise ProtocolError(f"opcode {opcode:#x} needs {expected} body bytes, got {body_length}")
    total = body_length + 1
    if len(buffer) < total:
        raise ProtocolError("truncated response body")
    frame, rest = buffer[:total], buffer[total:]
    return _parse_response(frame, opcode), rest


def parse_response(frame: bytes, opcode: int) -> dict:
    decoded, trailing = take_response(frame, opcode)
    if trailing:
        raise ProtocolError("trailing response data")
    return decoded


def _parse_response(frame: bytes, opcode: int) -> dict:
    body = frame[1:]
    if opcode == 0x12:
        return {
            "model_id": u16be(body[0:2]),
            "firmware_major": u16be(body[2:4]),
            "firmware_minor": u16be(body[4:6]),
        }
    if opcode == 0x14:
        cartridge_loaded = u16be(body[0:2])
        mat_loaded = u16be(body[2:4])
        if cartridge_loaded not in (0, 1) or mat_loaded not in (0, 1):
            raise ProtocolError("status flag is not boolean")
        return {"cartridge_loaded": cartridge_loaded, "mat_loaded": mat_loaded}
    if opcode == 0x11:
        coordinates = [u16be(body[index : index + 2]) for index in range(0, 8, 2)]
        decoded = dict(zip(("x_min", "y_min", "x_max", "y_max"), coordinates, strict=True))
        decoded["inches"] = {name: value / 404 for name, value in decoded.items()}
        return decoded
    present = u16be(body[0:2])
    if present not in (0, 1):
        raise ProtocolError("cartridge presence is not boolean")
    name_offset = u16be(body[2:4])
    version_offset = 4 + name_offset
    if version_offset >= len(body):
        raise ProtocolError("cartridge revision offset is outside the response")
    name_region = body[4:version_offset]
    if present:
        if b"\x00" not in name_region:
            raise ProtocolError("unterminated cartridge name")
        raw_name = name_region.split(b"\x00", 1)[0]
        if not raw_name:
            raise ProtocolError("present cartridge has an empty name")
    else:
        raw_name = name_region.split(b"\x00", 1)[0]
    try:
        name = raw_name.decode("ascii")
    except UnicodeDecodeError as error:
        raise ProtocolError("cartridge name is not ASCII") from error
    return {
        "cartridge_present": present,
        "name_offset": name_offset,
        "name": name,
        "cartridge_version": body[version_offset],
    }


def model_label(model_id: int) -> str:
    return {
        0x000A: "Personal",
        0x0014: "Expression",
        0x001E: "Mini (detection only; unsupported)",
    }.get(model_id, f"unknown({model_id})")


def test_published_request_and_response_vectors(spec, vectors):
    expected = {
        "model_firmware": 0x12,
        "status": 0x14,
        "mat_bounds": 0x11,
        "cartridge_info": 0x18,
    }
    messages = {entry["name"]: entry for entry in spec["bus"]["messages"]}
    assert set(messages) == set(expected)
    for name, opcode in expected.items():
        request = bytes.fromhex(vectors[name]["request_hex"])
        assert build_request(opcode) == request
        assert bytes.fromhex(messages[name]["request"]) == request
        assert len(request) == 5
        assert request[:2] == bytes([0x04, opcode])
        with pytest.raises(ProtocolError, match="only the five-byte"):
            build_request(opcode, 6)


def test_no_cartridge_empty_name_is_accepted(vectors):
    vector = vectors["no_cartridge"]
    response = bytes.fromhex(vector["response_hex"])
    assert len(response) == 39
    assert "synthetic" in vector["provenance"].lower()
    assert parse_response(response, 0x18) == vector["expected"] == {
        "cartridge_present": 0,
        "name_offset": 0,
        "name": "",
        "cartridge_version": 0,
    }


def test_model_firmware_vector_decodes_exactly(vectors):
    response = bytes.fromhex(vectors["model_firmware"]["response_hex"])
    assert len(response) == 7
    assert parse_response(response, 0x12) == {
        "model_id": 20,
        "firmware_major": 2,
        "firmware_minor": 34,
    }
    assert model_label(20) == "Expression"


def test_status_vector_decodes_exactly(vectors):
    response = bytes.fromhex(vectors["status"]["response_hex"])
    assert len(response) == 5
    assert parse_response(response, 0x14) == {
        "cartridge_loaded": 1,
        "mat_loaded": 1,
    }


def test_mat_bounds_vector_and_exact_404_scale(vectors):
    response = bytes.fromhex(vectors["mat_bounds"]["response_hex"])
    assert len(response) == 9
    decoded = parse_response(response, 0x11)
    assert {key: decoded[key] for key in ("x_min", "y_min", "x_max", "y_max")} == {
        "x_min": 316,
        "y_min": 50,
        "x_max": 4962,
        "y_max": 4696,
    }
    assert decoded["inches"]["x_min"] == pytest.approx(79 / 101)
    assert decoded["inches"]["y_min"] == pytest.approx(25 / 202)
    assert decoded["inches"]["x_max"] == pytest.approx(2481 / 202)
    assert decoded["inches"]["y_max"] == pytest.approx(1174 / 101)


def test_cartridge_vector_decodes_name_offset_and_revision(vectors):
    response = bytes.fromhex(vectors["cartridge_info"]["response_hex"])
    assert len(response) == 39
    assert parse_response(response, 0x18) == {
        "cartridge_present": 1,
        "name_offset": 33,
        "name": "Cricut(R) Cake Basics",
        "cartridge_version": 35,
    }


def test_every_message_field_decodes_its_vector_frame_relative(spec, vectors):
    """Decode each published response using only the spec's own field table.

    Offsets are frame-relative: the length byte is offset 0, so the body
    starts at 1. A field table written body-relative lands one byte early,
    e.g. a cartridge name starting inside name_offset.
    """
    messages = {message["name"]: message for message in spec["bus"]["messages"]}
    expected = {
        "status": {"cartridge_loaded": 1, "mat_loaded": 1},
        "cartridge_info": {
            "cartridge_present": 1,
            "name_offset": 33,
            "name_region": "Cricut(R) Cake Basics",
            "cartridge_version": 35,
        },
    }
    for name, want in expected.items():
        frame = bytes.fromhex(vectors[name]["response_hex"])
        assert len(frame) == messages[name]["length"]
        decoded = {}
        for field in messages[name]["fields"]:
            start, length = field["offset"], field["length"]
            assert start + length <= len(frame), field["name"]
            raw = frame[start : start + length]
            if field["type"] == "string":
                decoded[field["name"]] = raw.split(b"\0", 1)[0].decode("ascii")
            else:
                decoded[field["name"]] = int.from_bytes(raw, field.get("endianness", "big"))
        for key, value in want.items():
            assert decoded[key] == value, (name, key)

    fields = {f["name"]: f for f in messages["cartridge_info"]["fields"]}
    assert fields["name_region"]["offset"] == fields["name_offset"]["offset"] + 2
    assert fields["cartridge_version"]["offset"] == (
        fields["name_region"]["offset"] + 33
    )
    assert fields["cartridge_version"]["offset"] == messages["cartridge_info"]["length"] - 1


@pytest.mark.parametrize("name", ["model_firmware", "status", "mat_bounds", "cartridge_info"])
def test_every_truncated_response_is_rejected(vectors, name):
    opcode = {"model_firmware": 0x12, "status": 0x14, "mat_bounds": 0x11, "cartridge_info": 0x18}[name]
    response = bytes.fromhex(vectors[name]["response_hex"])
    for cut in range(len(response)):
        with pytest.raises(ProtocolError):
            parse_response(response[:cut], opcode)


@pytest.mark.parametrize("name", ["model_firmware", "status", "mat_bounds", "cartridge_info"])
def test_trailing_response_data_is_rejected(vectors, name):
    opcode = {"model_firmware": 0x12, "status": 0x14, "mat_bounds": 0x11, "cartridge_info": 0x18}[name]
    response = bytes.fromhex(vectors[name]["response_hex"])
    with pytest.raises(ProtocolError, match="trailing response data"):
        parse_response(response + b"\x00", opcode)


def test_stream_reader_handles_coalesced_frames_without_losing_boundaries(vectors):
    status = bytes.fromhex(vectors["status"]["response_hex"])
    model = bytes.fromhex(vectors["model_firmware"]["response_hex"])
    stream = status + model
    first, rest = take_response(stream, 0x14)
    second, rest = take_response(rest, 0x12)
    assert first["mat_loaded"] == 1
    assert second["firmware_minor"] == 34
    assert rest == b""


def test_invalid_length_prefix_and_unknown_opcode_are_rejected(vectors):
    with pytest.raises(ProtocolError, match="needs 4 body bytes"):
        parse_response(b"\x03\x00\x01\x00\x01", 0x14)
    with pytest.raises(ProtocolError, match="outside the query surface"):
        parse_response(b"\x04\x00\x01\x00\x01", 0x40)
    for opcode in (0x21, 0x22, 0x40, 0x00, 0xFF):
        with pytest.raises(ProtocolError):
            build_request(opcode, 5)


def test_nonboolean_status_is_rejected(vectors):
    response = bytearray.fromhex(vectors["status"]["response_hex"])
    response[1:3] = b"\x00\x02"
    with pytest.raises(ProtocolError, match="not boolean"):
        parse_response(bytes(response), 0x14)


def test_cartridge_offset_and_name_validation(vectors):
    response = bytearray.fromhex(vectors["cartridge_info"]["response_hex"])
    outside = bytearray(response)
    outside[3:5] = b"\xff\xff"
    with pytest.raises(ProtocolError, match="outside the response"):
        parse_response(bytes(outside), 0x18)
    unterminated = bytearray(response)
    unterminated[5:38] = b"A" * 33
    with pytest.raises(ProtocolError, match="unterminated cartridge name"):
        parse_response(bytes(unterminated), 0x18)
    non_ascii = bytearray(response)
    non_ascii[5] = 0xFF
    with pytest.raises(ProtocolError, match="not ASCII"):
        parse_response(bytes(non_ascii), 0x18)
    empty = bytearray(response)
    empty[5:38] = b"\x00" * 33
    with pytest.raises(ProtocolError, match="empty name"):
        parse_response(bytes(empty), 0x18)


def test_unknown_model_ids_are_not_assigned_to_other_variants():
    assert model_label(0x000A) == "Personal"
    assert model_label(0x0014) == "Expression"
    assert "unsupported" in model_label(0x001E)
    assert model_label(0xFFFF) == "unknown(65535)"


def test_executable_surface_has_no_dangerous_opcodes_or_features(spec):
    assert "http_endpoints" not in spec
    assert "commands" not in spec
    assert "features" not in spec
    messages = spec["bus"]["messages"]
    assert {bytes.fromhex(entry["request"])[1] for entry in messages} == QUERY_OPCODES.keys()
    for entry in messages:
        assert bytes.fromhex(entry["request"])[1] not in {0x21, 0x22, 0x40}
        assert entry["writes"] is False
    assert spec["protocol_details"]["excluded_operations"]["executable"] is False


def test_manual_selection_has_no_universal_usb_matcher(spec):
    assert "none" in spec["device"]["discovery"]
    assert "methods" not in spec["device"]["discovery"]
    forbidden_keys = {"vid", "pid", "vendor_id", "product_id", "usb_ids", "mac_prefixes"}

    def walk(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if isinstance(key, str):
                    assert key.lower() not in forbidden_keys
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(spec)
    assert "encryption" not in spec
    assert "command_keys" not in spec["protocol_details"]
    variants = {entry["model"] for entry in spec["device"]["variants"]}
    assert variants == {"Personal", "Create", "Expression", "Cake", "Cake Mini"}
    assert "Mini" not in variants
    assert not any("Bifrost" in entry or "Explore" in entry for entry in variants)


def test_serial_and_request_discrepancies_are_preserved(spec):
    assert spec["bus"]["link"]["baud"] == 200000
    assert "8N1 receive" in spec["bus"]["link"]["framing"]
    discrepancies = spec["protocol_details"]["serial_discrepancies"]
    assert discrepancies["baud"]["primary_reported"] == 200000
    assert discrepancies["baud"]["alternate_reported"] == 198347
    assert discrepancies["transmit_stop_intervals"] == 2
    assert discrepancies["receive_stop_intervals"] == 1
    assert discrepancies["inter_byte_gap_ms"] == 1
    widths = spec["protocol_details"]["request_width_discrepancy"]
    assert widths["executable_form"] == "[04][opcode][00][00][00]"
    assert widths["documentary_comment_only"].count("[00]") == 4
    assert "not a selectable wire form" in widths["rule"]
    assert "Always emit five bytes" in widths["rule"]
    assert "never used by the executable messages or test vectors" in widths["rule"]


def test_reset_all_is_physical_and_scoped_to_manual_models(spec):
    procedures = spec["device"]["setup"]["factory_reset"]["procedures"]
    covered = {model for procedure in procedures for model in procedure["applies_to"]}
    assert covered == {"Personal", "Create", "Expression", "Cake"}
    for procedure in procedures:
        assert procedure["verified"] is False
        assert procedure["basis"]
        assert procedure["press_count"] == 1
        assert procedure["power_state"] == "on"
    assert any("Cake Mini" in item for item in spec["remaining_unknowns"])
    assert spec["device"]["setup"]["rejoin"]["requires_factory_reset"] is False
    assert spec["device"]["setup"]["credentials"]["wifi_passphrase_protection"] == "not_applicable"


def walk_values(value, key: str):
    if isinstance(value, dict):
        for child_key, child in value.items():
            if child_key == key:
                yield child
            yield from walk_values(child, key)
    elif isinstance(value, list):
        for child in value:
            yield from walk_values(child, key)


def test_every_fact_is_reported_and_every_procedure_unverified(spec):
    assert spec["device"]["testing"]["status"] == "untested"
    assert set(walk_values(spec, "verification")) == {"reported"}
    assert all(value is False for value in walk_values(spec, "verified"))
    assert "no license grant" in spec["device"]["openness"]["notes"].lower()
