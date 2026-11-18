import io
import json
import struct
import zipfile


def make_rf_packet(group_id, sequence, page, mode, flags):
    packet = bytearray(21)
    struct.pack_into(">H", packet, 0, group_id)
    struct.pack_into("<I", packet, 2, sequence)
    packet[6:10] = bytes([1, 2, 3, 4])
    packet[10:15] = bytes([10, 20, 30, 40, 50])
    packet[15] = 0x3F
    packet[18] = page
    packet[19] = mode
    packet[20] = flags
    return bytes(packet)


def emitted_open_revision_groups(learned, public):
    return tuple(learned)


def make_fwimg(data, meta):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("meta", json.dumps(meta))
        archive.writestr("data", data)
    return buffer.getvalue()


def parse_fwimg(archive_bytes):
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        if set(archive.namelist()) != {"meta", "data"}:
            raise ValueError("fwimg requires exactly meta and data")
        meta = json.loads(archive.read("meta"))
        if not isinstance(meta, dict):
            raise ValueError("meta must be a JSON object")
        return meta, archive.read("data")


def make_data_report(offset, image):
    chunk = image[offset : offset + 60]
    chunk += bytes(60 - len(chunk))
    return struct.pack("<I60s", 0x80, chunk)


def test_rf_sync_packet_is_21_bytes_with_separate_mode_and_flags():
    packet = make_rf_packet(0x1234, 0x01020304, 5, 7, 0x40)
    assert len(packet) == 21
    assert packet[0:2] == bytes.fromhex("12 34")
    assert packet[2:6] == bytes.fromhex("04 03 02 01")
    assert packet[18] == 5
    assert packet[19] == 7
    assert packet[20] == 0x40
    assert emitted_open_revision_groups([42, 43], [1, 2, 3, 4, 5]) == (42, 43)


def test_fwimg_container_and_60_byte_padding():
    image = bytes(range(61))
    meta = {
        "usb_vid": 0xF107,
        "usb_pid": 0x1000,
        "fw_rev": 522,
        "hw_rev": 0x500,
        "fw_date": 1760000000,
        "git_rev": "invent1",
        "fw_ident": "invented-test-image",
    }
    parsed_meta, parsed_data = parse_fwimg(make_fwimg(image, meta))
    assert parsed_meta == meta
    assert parsed_data == image
    padded = parsed_data + bytes((-len(parsed_data)) % 60)
    assert len(padded) == 120
    assert make_data_report(0, padded) == struct.pack("<I60s", 0x80, padded[:60])
    second = make_data_report(60, padded)
    assert len(second) == 64
    assert second[4:] == padded[60:120]


def test_update_and_bootloader_reset_layouts():
    update = struct.pack("<IIIHHH", 0x01, 120, 0, 0xF107, 0x1000, 0x500)
    assert len(update) == 18
    assert update[:4] == bytes.fromhex("01 00 00 00")
    assert struct.pack("<II", 0xFF, 1) == bytes.fromhex("ff 00 00 00 01 00 00 00")


def test_fwimg_rejects_non_object_meta_and_missing_entries():
    try:
        parse_fwimg(make_fwimg(b"abc", ["not", "an", "object"]))
    except ValueError:
        pass
    else:
        raise AssertionError("array metadata must be rejected")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("data", b"abc")
    try:
        parse_fwimg(buffer.getvalue())
    except ValueError:
        pass
    else:
        raise AssertionError("missing meta must be rejected")
