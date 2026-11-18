"""Independent Blackmagic CCU transcription and packet tests.

Only Python's standard library (plus pytest's assertion/raises conveniences) is
used. Vectors are the vendor examples and synthetic values declared in
device-specs/devices/blackmagic-cinema-cameras.yaml; no project code is
imported and no camera is contacted.
"""

from __future__ import annotations

import pytest


WIDTHS = {0: None, 1: 1, 2: 2, 3: 4, 4: 8, 5: "string", 128: 2}


def fixed16(value: float) -> bytes:
    """Signed 5.11 fixed point, little-endian, per the vendor manual."""
    return int(round(value * 2048)).to_bytes(2, "little", signed=True)


def command(
    destination: int,
    category: int,
    parameter: int,
    data_type: int,
    operation: int,
    data: bytes = b"",
    *,
    command_id: int = 0,
) -> bytes:
    """Build one eight-byte-header CCU packet and its implicit alignment."""
    if not 0 <= len(data) <= 56:
        raise ValueError("CCU command length would exceed the 64-byte packet boundary")
    if operation == 1 and data_type == 0 and not data:
        raise ValueError("offset is invalid for void")
    packet = bytes(
        [destination, len(data) + 4, command_id, 0, category, parameter, data_type, operation]
    ) + data
    return packet + bytes((-len(packet)) % 4)


def parse_packets(chunks) -> list[dict]:
    """Defensive CCU stream decoder from protocol_details.receive_reassembly."""
    buffer = bytearray()
    result = []
    for chunk in chunks:
        buffer.extend(chunk)
        while buffer:
            if len(buffer) < 8:
                break
            length = buffer[1]
            if length < 4 or length > 60:
                raise ValueError("invalid CCU command length")
            data_length = length - 4
            total = 8 + data_length
            total += (-total) % 4
            if total > 64:
                raise ValueError("CCU packet exceeds 64 bytes")
            if len(buffer) < total:
                break
            packet = bytes(buffer[:total])
            del buffer[:total]
            if packet[3] != 0:
                raise ValueError("reserved byte is nonzero")
            if any(packet[8 + data_length :]):
                raise ValueError("nonzero alignment padding")
            command_id, data_type, operation = packet[2], packet[6], packet[7]
            if command_id != 0 or data_type >= 129 or operation >= 128:
                # Vendor-specific envelope: skip by aligned length only.
                result.append({"command_id": command_id, "skipped": True})
                continue
            if data_type not in WIDTHS:
                raise ValueError("reserved CCU data type")
            if operation not in (0, 1):
                raise ValueError("reserved CCU operation")
            width = WIDTHS[data_type]
            data = packet[8 : 8 + data_length]
            if width == "string":
                data.decode("utf-8")
            elif data_type == 0 and data_length not in (0, 1):
                raise ValueError("void/boolean must have zero or one byte")
            elif width not in (None, "string") and data_length % width:
                raise ValueError("non-integral CCU element width")
            if operation == 1 and data_type == 0 and data_length == 0:
                raise ValueError("offset operation on void")
            result.append(
                {
                    "command_id": 0,
                    "skipped": False,
                    "destination": packet[0],
                    "category": packet[4],
                    "parameter": packet[5],
                    "data_type": data_type,
                    "operation": operation,
                    "data": data,
                }
            )
    if buffer:
        raise ValueError("truncated trailing CCU packet")
    return result


VENDORS = {
    "autofocus": bytes.fromhex("04 04 00 00 00 01 00 00"),
    "ois": bytes.fromhex("ff 05 00 00 00 06 00 00 01 00 00 00"),
    "exposure": bytes.fromhex("04 08 00 00 01 05 03 00 10 27 00 00"),
    "zebra": bytes.fromhex("04 06 00 00 04 02 80 01 33 01 00 00"),
    "video_mode": bytes.fromhex("ff 09 00 00 01 00 01 00 18 01 03 00 00 00 00 00"),
    "gamma": bytes.fromhex("04 0c 00 00 08 01 80 01 00 00 9a fd 9a fd 00 00"),
}


def test_official_vendor_examples():
    assert command(4, 0, 1, 0, 0) == VENDORS["autofocus"]
    assert command(255, 0, 6, 0, 0, b"\x01") == VENDORS["ois"]
    assert command(4, 1, 5, 3, 0, (10000).to_bytes(4, "little", signed=True)) == VENDORS["exposure"]
    assert command(4, 4, 2, 128, 1, fixed16(0.15)) == VENDORS["zebra"]
    assert command(255, 1, 0, 1, 0, bytes([24, 1, 3, 0, 0])) == VENDORS["video_mode"]
    gamma = b"\x00\x00" + fixed16(-0.3) + fixed16(-0.3) + b"\x00\x00"
    assert command(4, 8, 1, 128, 1, gamma) == VENDORS["gamma"]


def test_synthetic_fixed16_white_balance_and_focus_vectors():
    white_balance = (5600).to_bytes(2, "little", signed=True) + (-2).to_bytes(2, "little", signed=True)
    assert command(255, 1, 2, 2, 0, white_balance) == bytes.fromhex(
        "ff 08 00 00 01 02 02 00 e0 15 fe ff"
    )
    assert command(255, 0, 0, 128, 0, fixed16(0.75)) == bytes.fromhex(
        "ff 06 00 00 00 00 80 00 00 06 00 00"
    )
    assert fixed16(-0.3).hex() == "9afd"
    assert int.from_bytes(fixed16(0.75), "little", signed=True) == 1536


def test_split_every_byte_and_coalesced_vendor_packets():
    stream = b"".join(VENDORS.values())
    expected = parse_packets([stream])
    assert len(expected) == len(VENDORS)
    assert parse_packets([bytes([b]) for b in stream]) == expected
    # Uneven splits retain an incomplete suffix until the next fragment.
    assert parse_packets([stream[:3], stream[3:17], stream[17:49], stream[49:]]) == expected


def test_typed_payload_decoding_and_unknown_command_skip():
    packets = parse_packets([VENDORS["exposure"] + VENDORS["zebra"]])
    assert int.from_bytes(packets[0]["data"], "little", signed=True) == 10000
    assert int.from_bytes(packets[1]["data"], "little", signed=True) / 2048 == pytest.approx(0.15, abs=1 / 2048)
    unknown = command(255, 250, 251, 1, 0, b"\x05")
    assert parse_packets([unknown])[0]["category"] == 250


@pytest.mark.parametrize(
    "bad",
    [
        b"\x00",
        bytes.fromhex("ff 03 00 00 00 01 00 00"),
        bytes.fromhex("ff 05 00 00 00 01 02 00 01 00 00 00"),  # int16 has odd data length
        bytes.fromhex("ff 04 00 00 00 01 00 00 01"),  # nonzero padding after an int8
        bytes.fromhex("ff 04 00 00 00 01 00 01"),  # void offset with empty payload
        bytes.fromhex("ff 05 00 00 00 01 06 00 01 00 00 00"),  # reserved operation? data_type 0 / op 1 is handled above only when void
        bytes.fromhex("ff 04 00 00 00 01 00 00 02"),  # reserved operation
        bytes.fromhex("ff 05 00 01 00 01 00 00 00 00 00 00"),  # nonzero reserved byte
        bytes.fromhex("ff 06 00 00 00 00 80 00 00 06"),  # truncated fixed16 packet
    ],
)
def test_malformed_packets_are_rejected(bad):
    with pytest.raises(ValueError):
        parse_packets([bad])


def test_nonzero_boolean_is_true_and_zero_is_false():
    on = parse_packets([VENDORS["ois"]])[0]["data"]
    off_packet = command(255, 0, 6, 0, 0, b"\x00")
    off = parse_packets([off_packet])[0]["data"]
    assert bool(on[0]) is True
    assert bool(off[0]) is False



def test_full_packet_boundary():
    packet = command(255, 250, 251, 1, 0, bytes(56))
    assert len(packet) == 64
    assert packet[1] == 60
    with pytest.raises(ValueError, match="64-byte"):
        command(255, 250, 251, 1, 0, bytes(57))



def test_vendor_specific_envelopes_are_skipped_then_known_packet_decodes():
    unknown_id = command(255, 1, 1, 1, 0, b"\x05", command_id=0x80)
    vendor_type = command(255, 1, 1, 0x81, 0, b"\x05")
    vendor_operation = command(255, 1, 1, 1, 0x80, b"\x05")
    stream = unknown_id + vendor_type + vendor_operation + VENDORS["exposure"]
    expected = [
        {"command_id": 0x80, "skipped": True},
        {"command_id": 0, "skipped": True},
        {"command_id": 0, "skipped": True},
    ]
    packets = parse_packets([stream])
    assert packets[:3] == expected
    assert packets[3]["command_id"] == 0
    assert packets[3]["skipped"] is False
    assert int.from_bytes(packets[3]["data"], "little", signed=True) == 10000
    assert parse_packets([bytes([value]) for value in stream]) == packets


def test_unknown_id_is_never_decoded_as_command_zero_even_with_reserved_type():
    unknown = command(255, 1, 1, 6, 2, b"\x05", command_id=0x81)
    stream = unknown + VENDORS["autofocus"]
    packets = parse_packets([stream])
    assert packets[0] == {"command_id": 0x81, "skipped": True}
    assert packets[1]["command_id"] == 0
    assert packets[1]["skipped"] is False
