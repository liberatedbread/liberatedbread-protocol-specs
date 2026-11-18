import struct


def make_history_block(voltage_mv, record_index):
    block = bytearray(230)
    struct.pack_into("<8H", block, 0, 11, 12, 13, 14, 15, 16, 17, 18)
    struct.pack_into("<HH", block, 16, 26, 18)
    block[222] = 0
    block[223] = 1
    struct.pack_into("<H", block, 224, voltage_mv)
    block[226] = 0
    block[227] = 11
    struct.pack_into("<H", block, 228, record_index)
    return bytes(block)


def decode_history_block(block):
    assert len(block) == 230
    first_ten = struct.unpack_from("<10H", block, 0)
    return {
        "radon_summary_available": all(value != 0xFFFF for value in first_ten),
        "invalid": block[222] != 0,
        "dataset": block[223],
        "voltage_mv": struct.unpack_from("<H", block, 224)[0],
        "orientation_waves": block[226],
        "last_slot": block[227],
        "record_index": struct.unpack_from("<H", block, 228)[0],
    }


def build_report_request(operator, flags, sensor, dataset_offset, minimum, maximum):
    return struct.pack(
        "<BBBBBHH", 0x01, operator, flags, sensor, dataset_offset, minimum, maximum
    )


def decode_clock(frame, rtc_initialized):
    assert len(frame) == 10 and frame[0] == 0x74
    value = struct.unpack_from("<I", frame, 6)[0]
    return value, "unix" if rtc_initialized else "boot"


def test_public_history_tails_and_multiple_blocks():
    first = make_history_block(2770, 2)
    second = make_history_block(2793, 3)
    assert first[222:230] == bytes.fromhex("00 01 d2 0a 00 0b 02 00")
    assert second[222:230] == bytes.fromhex("00 01 e9 0a 00 0b 03 00")
    assert decode_history_block(first)["voltage_mv"] == 2770
    assert decode_history_block(second)["voltage_mv"] == 2793
    assert decode_history_block(first)["record_index"] == 2
    assert decode_history_block(second)["record_index"] == 3
    assert decode_history_block(first)["last_slot"] == 11
    completion = bytes.fromhex("01 00 02 00 00 00")
    assert struct.unpack_from("<H", completion, 2)[0] == 2


def test_radon_summary_sentinel_checks_all_initial_u16_fields():
    for field_index in range(10):
        block = bytearray(make_history_block(2793, 3))
        struct.pack_into("<H", block, field_index * 2, 0xFFFF)
        assert not decode_history_block(block)["radon_summary_available"]
    block = bytearray(make_history_block(2793, 3))
    block[222] = 1
    assert decode_history_block(block)["invalid"]


def test_public_report_request_offsets():
    request = build_report_request(2, 0, 0, 0, 2, 0)
    assert request == bytes.fromhex("01 02 00 00 00 02 00 00 00")
    assert request[1] == 2
    assert request[4] == 0
    assert struct.unpack_from("<H", request, 5)[0] == 2
    assert struct.unpack_from("<H", request, 7)[0] == 0


def test_public_pre_and_post_rtc_clock_vectors():
    pre = bytes.fromhex("74 00 01 00 00 00 93 01 00 00")
    post = bytes.fromhex("74 00 01 00 00 00 e7 e0 8b 64")
    assert decode_clock(pre, False) == (403, "boot")
    assert decode_clock(post, True) == (1686888679, "unix")


def test_empty_slot_sentinel_and_two_byte_external_version_request():
    response = bytes.fromhex("02 00 9f e0 8b 64 01 ff 25 14 00 00 00 00")
    assert response[7] == 0xFF
    assert response[7] != 255 - 256
    request = bytes([0x72, 0x01])
    assert request == bytes.fromhex("72 01")
    assert len(request) == 2
    response = bytes.fromhex("72 00 02 00 11 00")
    assert (response[2], response[3], response[4]) == (2, 0, 17)
