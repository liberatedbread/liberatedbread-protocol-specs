# Copyright 2026 Pigs Can Fly Labs LLC
# SPDX-License-Identifier: Apache-2.0
"""Independent codec proof for the Ninebot Z WheelLog variant.

The encoder, decoder, field parser and stream reassembler below use only the
Python standard library and import none of this repository's code. PyYAML loads
the document and pytest supplies assertions; the vectors and every protocol
constant they check come from ``protocol_details.euc_frame_formats.ninebot_z``.
All session keys and serials in those vectors are invented. Passing tests prove
that the document is implementable and internally consistent, not that a wheel
has been driven from it.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SPEC_PATH = REPO_ROOT / "device-specs" / "devices" / "euc-wheellog-ble.yaml"
SPEC = yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))
NINEBOT = SPEC["protocol_details"]["euc_frame_formats"]["ninebot_z"]
VECTORS = {vector["name"]: vector for vector in NINEBOT["test_vectors"]}
HEADER = bytes.fromhex(NINEBOT["frame"]["header_hex"])


def xor_body(body: bytes, key: bytes) -> bytes:
    """Apply the spec's repeating XOR, leaving the body length byte clear."""
    assert len(key) == NINEBOT["frame"]["obfuscation"]["key_length_bytes"]
    transformed = bytearray(body)
    for index in range(1, len(transformed)):
        transformed[index] ^= key[(index - 1) % len(key)]
    return bytes(transformed)


def encode_frame(vector: dict) -> bytes:
    """Build one frame from its role addresses and plaintext payload."""
    payload = bytes.fromhex(vector["payload_hex"])
    body = bytes(
        [
            len(payload),
            vector["source"],
            vector["destination"],
            vector["command"],
            vector["parameter"],
        ]
    ) + payload
    checksum = (~sum(body)) & 0xFFFF
    plaintext = body + checksum.to_bytes(2, "little")
    key = bytes.fromhex(vector["session_key_hex"])
    return HEADER + xor_body(plaintext, key)


def decode_frame(frame: bytes, key: bytes) -> dict:
    """Decode and authenticate one complete frame, rejecting bad lengths/sums."""
    if not frame.startswith(HEADER):
        raise ValueError("missing 5A A5 header")
    if len(frame) < 9 or len(frame) != frame[2] + 9:
        raise ValueError("frame length does not match payload length")
    plaintext = xor_body(frame[len(HEADER) :], key)
    expected = (~sum(plaintext[:-2])) & 0xFFFF
    received = int.from_bytes(plaintext[-2:], "little")
    if received != expected:
        raise ValueError("checksum mismatch")
    return {
        "source": plaintext[1],
        "destination": plaintext[2],
        "command": plaintext[3],
        "parameter": plaintext[4],
        "payload": plaintext[5:-2],
    }


class Reassembler:
    """Notification-stream transcription of the spec's reassembly rules."""

    def __init__(self, key: bytes):
        self.key = key
        self.buffer = bytearray()

    def feed(self, chunk: bytes) -> list[dict]:
        self.buffer.extend(chunk)
        decoded = []
        while True:
            start = self.buffer.find(HEADER)
            if start < 0:
                trailing = 1 if self.buffer.endswith(HEADER[:1]) else 0
                del self.buffer[: len(self.buffer) - trailing]
                break
            if start:
                del self.buffer[:start]
            if len(self.buffer) < 3:
                break
            frame_length = self.buffer[2] + 9
            if len(self.buffer) < frame_length:
                break
            candidate = bytes(self.buffer[:frame_length])
            try:
                frame = decode_frame(candidate, self.key)
            except ValueError:
                del self.buffer[:2]
                continue
            decoded.append(frame)
            del self.buffer[:frame_length]
        return decoded


def decode_numeric_fields(payload: bytes, layout: dict) -> dict:
    """Read the layouts' declared offsets, signedness, endianness and scales."""
    assert len(payload) == layout["payload_bytes"]
    result = {}
    for field in layout["fields"]:
        if field["type"] == "bytes":
            continue
        offset = field["offset"]
        raw_bytes = payload[offset : offset + field["length"]]
        raw = int.from_bytes(
            raw_bytes,
            field.get("endianness", "little"),
            signed=field["type"].startswith("int"),
        )
        result[field["name"]] = (
            raw * field.get("scale", 1) + field.get("value_offset", 0)
        )
    return result


def decode_identity(payload: bytes) -> dict:
    """Add the BMS serial, packed version and packed manufacture date."""
    layout = NINEBOT["layouts"]["bms_identity"]
    result = decode_numeric_fields(payload, layout)
    result["serial"] = payload[:14].decode("ascii")
    result["version"] = f"{payload[15]:X}.{payload[14] >> 4:X}.{payload[14] & 0x0F:X}"
    raw_date = int.from_bytes(payload[32:34], "little")
    year = raw_date >> 9
    month = (raw_date >> 5) & 0x0F
    day = raw_date & 0x1F
    result["manufacture_date"] = f"{day:02d}.{month:02d}.20{year:02d}"
    return result


def decode_cells(payload: bytes) -> dict:
    layout = NINEBOT["layouts"]["bms_cells"]
    repeated = layout["repeated_field"]
    assert len(payload) == layout["payload_bytes"]
    cells = []
    for index in range(repeated["count"]):
        offset = repeated["offset"] + index * repeated["stride"]
        raw = int.from_bytes(
            payload[offset : offset + repeated["stride"]], repeated["endianness"]
        )
        cells.append(raw * repeated["scale"])
    cell_count = 14
    if cells[14] > 0:
        cell_count = 15
    if cells[15] > 0:
        cell_count = 16
    return {"cells_v": cells, "cell_count": cell_count}


@pytest.mark.parametrize("name", list(VECTORS))
def test_vector_codec_round_trip(name):
    vector = VECTORS[name]
    expected_wire = bytes.fromhex(vector["frame_hex"])
    assert encode_frame(vector) == expected_wire
    decoded = decode_frame(expected_wire, bytes.fromhex(vector["session_key_hex"]))
    assert decoded["source"] == vector["source"]
    assert decoded["destination"] == vector["destination"]
    assert decoded["command"] == vector["command"]
    assert decoded["parameter"] == vector["parameter"]
    assert decoded["payload"].hex() == vector["payload_hex"]


def test_synthetic_parameter_00_vector_is_codec_only_not_negotiation_proof():
    assert NINEBOT["test_vectors_proof_scope"] == "codec_only"
    vector = VECTORS["synthetic_key_response_parameter_00"]
    assert vector["proof_scope"] == (
        "codec_only_not_an_observed_reply_or_negotiation_proof"
    )
    key_reply = decode_frame(bytes.fromhex(vector["frame_hex"]), bytes(16))
    transform_key = key_reply["payload"]
    assert len(transform_key) == 16
    assert transform_key.hex() == vector["expect"]["codec_transform_key_hex"]
    serial_reply = decode_frame(
        bytes.fromhex(VECTORS["controller_serial"]["frame_hex"]), transform_key
    )
    assert serial_reply["payload"].decode("ascii") == "Z10TEST0000001"
    assert serial_reply["payload"].decode("ascii") == VECTORS["controller_serial"][
        "expect"
    ]["serial"]


def test_upstream_01_key_sample_is_observed_but_unhandled():
    session = NINEBOT["session"]
    accepted = session["decoder_accepted_key_branch"]
    observed = session["observed_unhandled_key_reply"]
    assert accepted["parameter"] == 0x00
    assert accepted["status"] == "decoder_branch_only_not_established_response_selector"
    assert observed["parameter"] == 0x01
    assert observed["source"] == 0x16
    assert observed["command"] == 0x5B
    assert observed["resolution"] == "pending_capture"
    assert "does not install" in observed["handling"]
    assert session["key_installation_status"] == "pending_capture"
    assert "response_parameter" not in session["key_request"]


def test_live_layout_offsets_signedness_scales_and_units():
    vector = VECTORS["live_data"]
    decoded = decode_numeric_fields(
        bytes.fromhex(vector["payload_hex"]), NINEBOT["layouts"]["live_data"]
    )
    assert decoded == pytest.approx(vector["expect"])
    assert decoded["temperature_c"] == -5.5
    assert decoded["current_a"] == -12.34


@pytest.mark.parametrize("name,source", [("bms1_identity", 0x11), ("bms2_identity", 0x12)])
def test_both_bms_identity_layouts(name, source):
    vector = VECTORS[name]
    assert vector["source"] == source
    assert decode_identity(bytes.fromhex(vector["payload_hex"])) == vector["expect"]


@pytest.mark.parametrize("name,source", [("bms1_status", 0x11), ("bms2_status", 0x12)])
def test_both_bms_status_layouts(name, source):
    vector = VECTORS[name]
    assert vector["source"] == source
    decoded = decode_numeric_fields(
        bytes.fromhex(vector["payload_hex"]), NINEBOT["layouts"]["bms_status"]
    )
    assert decoded == pytest.approx(vector["expect"])


@pytest.mark.parametrize(
    "name,source,count", [("bms1_cells_14", 0x11, 14), ("bms2_cells_16", 0x12, 16)]
)
def test_both_bms_cell_layouts(name, source, count):
    vector = VECTORS[name]
    assert vector["source"] == source
    decoded = decode_cells(bytes.fromhex(vector["payload_hex"]))
    assert decoded["cells_v"] == pytest.approx(vector["expect"]["cells_v"])
    assert decoded["cell_count"] == vector["expect"]["cell_count"] == count


def test_fragmented_frames_reassemble_at_every_split_point():
    vector = VECTORS["live_data"]
    wire = bytes.fromhex(vector["frame_hex"])
    key = bytes.fromhex(vector["session_key_hex"])
    for split in range(len(wire) + 1):
        stream = Reassembler(key)
        frames = stream.feed(wire[:split])
        if split < len(wire):
            assert frames == [], split
        frames.extend(stream.feed(wire[split:]))
        assert len(frames) == 1, split
        assert frames[0]["payload"].hex() == vector["payload_hex"], split


def test_noise_bad_checksum_and_coalesced_frames_recover():
    names = ["controller_serial", "live_data", "bms1_status", "bms2_cells_16"]
    vectors = [VECTORS[name] for name in names]
    key = bytes.fromhex(vectors[0]["session_key_hex"])
    damaged = bytearray.fromhex(VECTORS["bms2_identity"]["frame_hex"])
    damaged[-1] ^= 0x01
    wire = b"\x00\x5a\x00" + bytes(damaged) + b"".join(
        bytes.fromhex(vector["frame_hex"]) for vector in vectors
    )
    stream = Reassembler(key)
    decoded = []
    position = 0
    for size in [1, 2, 7, 3, 19, 4, 31, 5, 11]:
        decoded.extend(stream.feed(wire[position : position + size]))
        position += size
    while position < len(wire):
        decoded.extend(stream.feed(wire[position : position + 6]))
        position += 6
    assert [frame["parameter"] for frame in decoded] == [0x10, 0xB0, 0x30, 0x40]
    assert [frame["source"] for frame in decoded] == [0x14, 0x14, 0x11, 0x12]
    assert decoded[-1]["payload"].hex() == vectors[-1]["payload_hex"]


def test_documented_requests_are_read_only():
    assert NINEBOT["verification"] == "reported"
    assert SPEC["device"]["testing"]["status"] == "untested"
    for request in NINEBOT["read_requests"].values():
        if isinstance(request, dict):
            assert request["command"] == NINEBOT["commands"]["read"]
    assert NINEBOT["session"]["key_request"]["command"] == 0x5B
    assert NINEBOT["session"]["ble_version_request"]["command"] == 0x01
    assert NINEBOT["commands"] == {
        "read": 0x01,
        "read_response": 0x04,
        "get_session_key": 0x5B,
    }
