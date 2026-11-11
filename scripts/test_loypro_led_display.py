"""Independent LOY AA55/TLV transcription using only the standard library."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC = yaml.safe_load(
    (ROOT / "device-specs" / "devices" / "loypro-led-display.yaml").read_text(
        encoding="utf-8"
    )
)
DETAILS = SPEC["protocol_details"]


def tlv(tag: int, value: bytes) -> bytes:
    length = len(value)
    if length < 0x80:
        encoded_length = bytes([length])
    elif length < 0x100:
        encoded_length = bytes([0x81, length])
    else:
        encoded_length = b"\x82" + length.to_bytes(2, "little")
    return bytes([tag]) + encoded_length + value


def aa55(sequence: int, command_type: int, payload: bytes, flags: int = 0xC1) -> bytes:
    declared_length = 2 + 1 + 1 + len(payload) + 2
    packet_without_checksum = (
        b"\xaa\x55\xff\xff"
        + declared_length.to_bytes(2, "little")
        + sequence.to_bytes(2, "little")
        + bytes([flags, command_type])
        + payload
    )
    checksum = sum(packet_without_checksum) & 0xFFFF
    return packet_without_checksum + checksum.to_bytes(2, "little")


def program_header() -> bytes:
    return b"".join(
        [
            tlv(0x08, (0).to_bytes(2, "little")),
            tlv(0x09, b"\x01"),
            tlv(0x0C, b"\x00"),
            tlv(0x1C, bytes.fromhex("00 00 03 00 03 00")),
            tlv(0x0D, b"\x00"),
            tlv(0x1D, bytes.fromhex("00 00 00 00 30 00 10 00 00")),
        ]
    )


def graphic_item() -> bytes:
    return b"".join(
        [
            tlv(0x09, b"\x01"),
            tlv(0x0C, b"\x00"),
            tlv(0x0D, b"\x00"),
            tlv(0x0E, b"\x00"),
            tlv(0x14, bytes.fromhex("01 0d 03")),
            tlv(0x11, bytes.fromhex("00 01 00 0a")),
        ]
    )


def test_program_header_matches_sanitized_spec_vector():
    encoded = aa55(1, 0x02, program_header())
    expected = bytes.fromhex(DETAILS["program_upload"]["example_program_header_hex"])

    assert encoded == expected
    assert len(encoded) == int.from_bytes(encoded[4:6], "little") + 6
    assert int.from_bytes(encoded[-2:], "little") == sum(encoded[:-2]) & 0xFFFF
    assert encoded[10:14] == bytes.fromhex("08 02 00 00")


def test_graphic_item_matches_sanitized_spec_vector():
    encoded = aa55(2, 0x02, graphic_item())
    expected = bytes.fromhex(DETAILS["program_upload"]["example_graphic_item_hex"])

    assert encoded == expected
    assert len(encoded) == int.from_bytes(encoded[4:6], "little") + 6
    assert int.from_bytes(encoded[-2:], "little") == sum(encoded[:-2]) & 0xFFFF


def test_tlv_lengths_cover_short_extended_and_capture_chunk_sizes():
    assert tlv(0x13, b"abc") == bytes.fromhex("13 03 61 62 63")
    assert tlv(0x13, bytes(196))[:3] == bytes.fromhex("13 81 c4")
    assert tlv(0x13, bytes(960))[:4] == bytes.fromhex("13 82 c0 03")
    assert tlv(0x13, bytes(4551))[:4] == bytes.fromhex("13 82 c7 11")


def test_capture_chunk_accounting_and_delete_only_packet_is_not_upload():
    example = DETAILS["program_upload"]["geometry_examples"]
    whole, remainder = divmod(example["gif_bytes"], example["maximum_chunk_bytes"])

    assert (whole, remainder) == (4, 711)
    assert example["logical_chunks"] == whole + bool(remainder) == 5
    assert DETAILS["program_upload"]["sequence"] != [
        "08 02 00 00"
    ]
    assert "replaces" in DETAILS["program_upload"]["storage_effect"]


def test_query_vector_checksum_and_declared_length():
    raw = bytes.fromhex(DETAILS["read_only_identification"]["source_derived_query_hex"])

    assert len(raw) == 20
    assert len(raw) == int.from_bytes(raw[4:6], "little") + 6
    assert int.from_bytes(raw[-2:], "little") == sum(raw[:-2]) & 0xFFFF
