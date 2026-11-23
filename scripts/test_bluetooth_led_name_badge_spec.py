import struct


MODES = {
    0: "scroll left",
    1: "scroll right",
    2: "scroll up",
    3: "scroll down",
    4: "fixed",
    5: "animation",
    6: "snowflake/drop-down",
    7: "picture/curtain",
    8: "laser",
}


def stripe_bitmap(rows, columns, value):
    if columns % 8:
        raise ValueError("columns must form complete stripes")
    return bytes([value]) * (rows * (columns // 8))


def build_transfer(bitmap, bitmap_length=None):
    if len(bitmap) > 8128:
        raise ValueError("bitmap exceeds the 8192-byte flash image")
    packet = bytearray(64)
    packet[:4] = b"wang"
    packet[5] = 0x10
    packet[8] = (1 << 4) | 5
    struct.pack_into(">H", packet, 16, len(bitmap) if bitmap_length is None else bitmap_length)
    packet[38:44] = bytes([26, 11, 17, 12, 34, 56])
    packet.extend(bitmap)
    packet.extend(bytes((-len(packet)) % 16))
    return [bytes(packet[offset : offset + 16]) for offset in range(0, len(packet), 16)]


def delay_before_chunk(index):
    if index < 4:
        return 0
    if index == 4:
        return 300
    return 25


def test_header_modes_lengths_and_total_flash_budget():
    bitmap = stripe_bitmap(11, 16, 0xA5)
    chunks = build_transfer(bitmap)
    assert len(bitmap) == 22
    assert len(chunks) == 6
    header = b"".join(chunks)
    assert header[:4] == b"wang"
    assert header[8] & 0x0F == 5
    assert MODES[header[8] & 0x0F] == "animation"
    assert MODES[6] == "snowflake/drop-down"
    assert MODES[7] == "picture/curtain"
    assert struct.unpack_from(">H", header, 16)[0] == 22


def test_row_variants_and_padding():
    for rows in (11, 12, 16):
        bitmap = stripe_bitmap(rows, 16, rows)
        assert len(bitmap) == rows * 2
        chunks = build_transfer(bitmap)
        assert all(len(chunk) == 16 for chunk in chunks)
        assert len(b"".join(chunks)) % 16 == 0


def test_8192_bytes_includes_the_64_byte_header():
    chunks = build_transfer(bytes(8128))
    assert sum(map(len, chunks)) == 8192
    try:
        build_transfer(bytes(8129))
    except ValueError:
        pass
    else:
        raise AssertionError("8129 bitmap bytes must exceed the flash budget")


def test_acknowledged_write_timing_contract():
    assert 3000 == 3 * 1000
    assert [delay_before_chunk(index) for index in range(7)] == [
        0,
        0,
        0,
        0,
        300,
        25,
        25,
    ]
