"""Independent openScale reassembled-record layout and scaling vectors."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC = yaml.safe_load(
    (ROOT / "device-specs/devices/openscale-body-scales.yaml").read_text(
        encoding="utf-8"
    )
)
RECORDS = SPEC["protocol_details"]["reassembled_records"]


def build_beurer():
    values = {
        "unix_seconds": 1700000000,
        "weight": 1500,
        "impedance": 500,
        "fat": 250,
        "water": 400,
        "muscle": 300,
        "bone": 60,
        "bmr_raw": 1800,
        "amr_raw": 2200,
        "bmi": 247,
    }
    layout = RECORDS["beurer_sanitas"]
    output = bytearray(layout["length_bytes"])
    for field in layout["fields"]:
        output[field["offset"] : field["offset"] + field["length"]] = values[
            field["name"]
        ].to_bytes(field["length"], "big")
    return bytes(output)


def test_beurer_full_22_byte_big_endian_layout():
    layout = RECORDS["beurer_sanitas"]
    raw = build_beurer()
    decoded = {}
    for field in layout["fields"]:
        value = int.from_bytes(
            raw[field["offset"] : field["offset"] + field["length"]], "big"
        )
        decoded[field["name"]] = value * field.get("scale", 1)
    assert decoded == {
        "unix_seconds": 1700000000,
        "weight": 75.0,
        "impedance": 500,
        "fat": 25.0,
        "water": 40.0,
        "muscle": 30.0,
        "bone": 3.0,
        "bmr_raw": 1800,
        "amr_raw": 2200,
        "bmi": 24.700000000000003,
    }


def test_medisana_public_example_is_kg_only_scaling():
    layout = RECORDS["medisana_bs444"]
    raw = bytes.fromhex(layout["example_hex"])
    assert len(raw) == layout["length_bytes"] == 19
    weight = next(field for field in layout["fields"] if field["name"] == "weight_kg")
    value = int.from_bytes(raw[1:3], "little") * weight["scale"]
    assert value == 96.0
    assert "only for the kg example" in weight["notes"]


def parse_trisa(raw):
    output = {
        "weight": int.from_bytes(raw[1:4], "little")
        * 10 ** int.from_bytes(raw[4:5], "little", signed=True)
    }
    flags = raw[0]
    offset = 5
    for bit, name, size in (
        (1, "timestamp", 4),
        (2, "resistance_1", 4),
        (4, "resistance_2", 4),
        (8, "user_id", 1),
        (16, "measurement_status", 1),
    ):
        if flags & bit:
            output[name] = raw[offset : offset + size]
            offset += size
        else:
            output[name] = None
    output["bytes_consumed"] = offset
    return output


def test_trisa_public_mantissa_exponent_vector_and_service_docs():
    layout = RECORDS["trisa_body_analyze"]
    raw = bytes.fromhex(layout["example_hex"])
    assert len(raw) == layout["full_example_length_bytes"] == 20
    assert layout["maximum_length_bytes"] == 20
    mantissa = int.from_bytes(raw[1:4], "little")
    exponent = int.from_bytes(raw[4:5], "little", signed=True)
    assert mantissa == 7720
    assert exponent == -2
    assert mantissa * 10**exponent == layout["example_weight_kg"] == 77.20
    decoded = parse_trisa(raw)
    assert decoded["resistance_2"] == bytes.fromhex("60 14 00 ff")
    assert decoded["user_id"] == b"\x00"
    assert decoded["measurement_status"] == b"\x09"
    assert decoded["bytes_consumed"] == 19
    guide = (ROOT / "docs/devices/openscale-body-scales.md").read_text(
        encoding="utf-8"
    )
    assert "service **`0x7802`**, not `0x78b2`" in guide
    assert "Trisa: 0x78b2" not in guide


def test_trisa_resistance_2_moves_immediately_after_timestamp_without_r1():
    raw = bytes.fromhex("0d 28 1e 00 fe 04 0a 70 10 60 14 00 ff 00 09")
    decoded = parse_trisa(raw)
    assert decoded["timestamp"] == bytes.fromhex("04 0a 70 10")
    assert decoded["resistance_1"] is None
    assert decoded["resistance_2"] == bytes.fromhex("60 14 00 ff")
    assert decoded["user_id"] == b"\x00"
    assert decoded["measurement_status"] is None
    assert decoded["bytes_consumed"] == 14


def test_trisa_timestamp_absence_does_not_shift_fixed_weight_or_later_fields():
    raw = bytes.fromhex("04 28 1e 00 fe 60 14 00 ff")
    decoded = parse_trisa(raw)
    assert decoded["weight"] == 77.20
    assert decoded["timestamp"] is None
    assert decoded["resistance_1"] is None
    assert decoded["resistance_2"] == bytes.fromhex("60 14 00 ff")
    assert decoded["bytes_consumed"] == 9


def test_beurer_live_timestamp_bit_31_is_masked():
    layout = RECORDS["beurer_sanitas"]
    raw = bytes.fromhex("ea 92 90 c2")
    assert int.from_bytes(raw, "big") & layout["timestamp_mask"] == 0x6A9290C2
    assert 1700000000 & layout["timestamp_mask"] == 1700000000


def test_trisa_r2_offset_accounts_for_timestamp_and_r1():
    fields = RECORDS["trisa_body_analyze"]["fields"]
    declaration = next(field for field in fields if field["name"] == "resistance_2")
    assert declaration["offset_formula"] == "5 + 4*(flag bit 0) + 4*(flag bit 1)"
    for flags, expected_offset in (
        (0x04, 5),
        (0x05, 9),
        (0x06, 9),
        (0x07, 13),
        (0xDF, 13),
    ):
        offset = 5 + (4 if flags & 1 else 0) + (4 if flags & 2 else 0)
        assert offset == expected_offset


FFE0 = "0000ffe0-0000-1000-8000-00805f9b34fb"


def test_generic_ffe0_is_never_a_matcher_and_names_mirror_openscale():
    import re

    device = SPEC["device"]
    assert FFE0 not in device["identification"].get("service_uuids", [])
    methods = device["discovery"]["methods"]
    for method in methods:
        assert FFE0 not in method["ble"].get("service_uuids", [])
    assert FFE0 in {service["uuid"] for service in SPEC["services"]}

    beurer, medisana, trisa = (re.compile(m["ble"]["local_name"]["value"]) for m in methods)
    for name in ("BEURER BF700", "BF700", "bf-800", "RT-Libra-W", "SANITAS SBF70", "SBF75", "AICDSCALE1"):
        assert beurer.search(name), name
    for name in ("HMSoft", "MLT-BT05", "BF500", "SBF72", "Libra"):
        assert not beurer.search(name), name
    for name in ("013197ABCD", "0202B6", "0203b1"):
        assert medisana.search(name), name
    assert not medisana.search("X0203B")
    for name in ("01257B1234", "11257B"):
        assert trisa.search(name), name
    assert not trisa.search("21257B")


def test_medisana_bs430_epoch_is_unix_not_2010():
    notes = SPEC["device"]["notes"]
    assert "BS430" in notes and "Unix seconds" in notes and "0203B" in notes
    fields = {f["name"]: f for f in RECORDS["medisana_bs444"]["fields"]}
    assert "Unix seconds" in fields["seconds_since_2010"]["notes"]
