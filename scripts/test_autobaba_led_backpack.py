"""Reproduce the source-derived AUTOBABA information query independently."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC = yaml.safe_load(
    (ROOT / "device-specs" / "devices" / "autobaba-led-backpack.yaml").read_text(
        encoding="utf-8"
    )
)


def test_information_query_checksum_and_length():
    expected = bytes.fromhex(
        SPEC["protocol_details"]["panel_discovery"]["source_derived_query_hex"]
    )
    tlv = bytes.fromhex("0a 00 1b 00 04 00 06 00")
    frame = bytearray.fromhex("aa 55 ff ff")
    frame += (len(tlv) + 6).to_bytes(2, "little")
    frame += (1).to_bytes(2, "little")
    frame += bytes.fromhex("c1 03")
    frame += tlv
    frame += (sum(frame) & 0xFFFF).to_bytes(2, "little")

    assert bytes(frame) == expected
    assert len(frame) == 20
    assert int.from_bytes(frame[4:6], "little") == len(tlv) + 6
    assert int.from_bytes(frame[-2:], "little") == 0x03FF


def test_extended_tlv_length_81_c4_means_196_bytes():
    encoding = SPEC["protocol_details"]["panel_discovery"]["tlv_length_encoding"]
    assert encoding["extended_8"].startswith("81 LL")
    assert encoding["example"] == "13 81 c4 = type 0x13 with a 196-byte value"


def test_panel_dimensions_are_little_endian_after_type_byte():
    observed = SPEC["protocol_details"]["panel_discovery"]["observed_reply"]
    panel = bytes.fromhex("00 40 00 40")

    assert panel[0] == 0
    assert int.from_bytes(panel[1:3], "little") == observed["width"] == 64
    assert int.from_bytes(panel[3:5], "little") == observed["height"] == 64
    assert observed["width_height_endian"] == "little"


def test_raw_gif_write_fits_the_observed_mtu():
    upload = SPEC["protocol_details"]["raw_gif_upload"]
    assert upload["value_chunk_bytes"] == 196
    assert upload["gatt_write_bytes"] == 243
    assert upload["gatt_write_bytes"] <= upload["mtu"] - 3
