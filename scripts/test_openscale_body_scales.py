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


def test_trisa_public_mantissa_exponent_vector_and_service_docs():
    layout = RECORDS["trisa_body_analyze"]
    raw = bytes.fromhex(layout["example_hex"])
    assert len(raw) == layout["length_bytes"] == 20
    mantissa = int.from_bytes(raw[1:4], "little")
    exponent = int.from_bytes(raw[4:5], "little", signed=True)
    assert mantissa == 7720
    assert exponent == -2
    assert mantissa * 10**exponent == layout["example_weight_kg"] == 77.20
    guide = (ROOT / "docs/devices/openscale-body-scales.md").read_text(
        encoding="utf-8"
    )
    assert "service **`0x7802`**, not `0x78b2`" in guide
    assert "Trisa: 0x78b2" not in guide
