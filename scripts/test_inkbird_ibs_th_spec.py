import struct


def crc16_modbus(data):
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ (0xA001 if crc & 1 else 0)
    return crc & 0xFFFF


def history_layout(count):
    compressed_len = ((count - count % 10) // 10) * 4
    raw_offset = ((compressed_len + 19) // 20) * 20
    remainder_len = (count % 10) * 2
    return compressed_len, raw_offset, remainder_len


def make_history(count):
    groups = (count - count % 10) // 10
    compressed = b"".join(
        struct.pack("<hh", 1000 + group * 100, 1090 + group * 100)
        for group in range(groups)
    )
    remainder = b"".join(
        struct.pack("<h", 2000 + index) for index in range(count % 10)
    )
    compressed_len, raw_offset, remainder_len = history_layout(count)
    assert len(compressed) == compressed_len
    assert len(remainder) == remainder_len
    wire = compressed + bytes(raw_offset - compressed_len) + remainder
    return wire


def meaningful_history(wire, count):
    compressed_len, raw_offset, remainder_len = history_layout(count)
    assert wire[compressed_len:raw_offset] == bytes(raw_offset - compressed_len)
    return wire[:compressed_len] + wire[raw_offset : raw_offset + remainder_len]


def decode_advertisement(frame):
    assert len(frame) == 9
    return {
        "temperature": struct.unpack_from("<h", frame, 0)[0] / 100,
        "humidity": struct.unpack_from("<H", frame, 2)[0] / 100,
        "battery": frame[7],
        "route": "connected_read" if frame[8] == 6 else "advertisement_only",
    }


def ota_address(normal_address):
    octets = [int(part, 16) for part in normal_address.split(":")]
    octets[-1] += 1
    return ":".join(f"{part:02x}" for part in octets)


def test_public_advertisement_and_onboarding_routes():
    frame = bytes.fromhex("fc 07 c7 12 00 c8 3d 56 06")
    decoded = decode_advertisement(frame)
    assert decoded == {
        "temperature": 20.44,
        "humidity": 48.07,
        "battery": 86,
        "route": "connected_read",
    }
    other = bytearray(frame)
    other[8] = 0x08
    assert decode_advertisement(other)["route"] == "advertisement_only"


def test_history_padding_offsets_and_crc_excludes_padding():
    for count in (0, 1, 9, 10, 20, 21, 23, 50, 51, 55, 60):
        wire = make_history(count)
        meaningful = meaningful_history(wire, count)
        compressed_len, raw_offset, remainder_len = history_layout(count)
        assert len(meaningful) == compressed_len + remainder_len
        assert len(wire) == raw_offset + remainder_len
        assert crc16_modbus(meaningful) == crc16_modbus(
            wire[:compressed_len] + wire[raw_offset : raw_offset + remainder_len]
        )
    assert history_layout(23) == (8, 20, 6)
    assert history_layout(50) == (20, 20, 0)
    assert history_layout(51) == (20, 20, 2)


def test_header_crc_and_modbus_check_vector():
    assert crc16_modbus(b"123456789") == 0x4B37
    header = struct.pack("<I", 23)
    transmitted = header + struct.pack("<H", crc16_modbus(header))
    assert len(transmitted) == 6
    assert crc16_modbus(transmitted[:4]) == struct.unpack_from("<H", transmitted, 4)[0]


def test_invented_ota_address_and_entry_vectors():
    assert ota_address("02:00:00:00:00:20") == "02:00:00:00:00:21"
    assert bytes([0x01, 0x02]) == bytes.fromhex("01 02")
    assert bytes([0x01, 0x03]) == bytes.fromhex("01 03")
