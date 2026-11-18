import struct
import zlib


HEADER = struct.Struct("<HBBBIIHB")


def draw_pixel(mode, red, green, blue, x, y):
    return bytes([0x0A, 0x00, 0x05, 0x01, mode, red, green, blue, x, y])


def make_frame(command, payload, chunk_flag=0, delay=0, material_type=12):
    checksum = zlib.crc32(payload) & 0xFFFFFFFF
    header = HEADER.pack(
        16 + len(payload),
        command,
        0,
        chunk_flag,
        len(payload),
        checksum,
        delay,
        material_type,
    )
    return header + payload


def decode_gatt_properties(property_byte):
    properties = set()
    if property_byte & 0x02:
        properties.add("read")
    if property_byte & 0x04:
        properties.add("write_without_response")
    if property_byte & 0x08:
        properties.add("write")
    if property_byte & 0x10:
        properties.add("notify")
    return properties


def test_public_draw_pixel_vector():
    vector = draw_pixel(0, 255, 0, 0, 31, 31)
    assert vector == bytes.fromhex("0a 00 05 01 00 ff 00 00 1f 1f")
    assert (vector[4], vector[5:8], vector[8], vector[9]) == (
        0,
        b"\xff\x00\x00",
        31,
        31,
    )


def test_public_capture_lengths_and_crc_fields():
    for frame_length, payload_length, expected_crc in (
        (50, 34, 0x10907EC7),
        (234, 218, 0xE72B5848),
    ):
        header = HEADER.pack(
            frame_length, 2, 0, 0, payload_length, expected_crc, 0, 12
        )
        decoded = HEADER.unpack(header)
        assert decoded[0] == frame_length == 16 + payload_length
        assert decoded[4] == payload_length
        assert decoded[5] == expected_crc


def test_independent_payload_only_crc_and_little_endian_lengths():
    payload = bytes(range(34))
    frame = make_frame(2, payload)
    assert len(frame) == 50
    assert frame[:2] == (50).to_bytes(2, "little")
    assert struct.unpack_from("<I", frame, 5)[0] == 34
    assert struct.unpack_from("<I", frame, 9)[0] == zlib.crc32(payload)
    assert frame[16:] == payload
    assert zlib.crc32(frame[:16]) != struct.unpack_from("<I", frame, 9)[0]


def test_capture_gatt_property_bytes():
    assert decode_gatt_properties(0x0C) == {"write", "write_without_response"}
    assert decode_gatt_properties(0x10) == {"notify"}
    assert "read" not in decode_gatt_properties(0x10)


def test_primary_service_expansion():
    assert f"{0x00FA:08x}-0000-1000-8000-00805f9b34fb" == (
        "000000fa-0000-1000-8000-00805f9b34fb"
    )
