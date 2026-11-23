"""Silk'n Infinity level-five counter boundary and guide consistency."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC = yaml.safe_load(
    (ROOT / "device-specs/devices/silkn-infinity.yaml").read_text(encoding="utf-8")
)


def test_byte_19_is_level_five_high_byte_on_infinity():
    frame = bytearray(20)
    frame[18:20] = (0x1234).to_bytes(2, "big")
    characteristic = SPEC["services"][0]["characteristics"][0]
    level_five = next(
        field
        for field in characteristic["format"]
        if field["name"] == "level_5_counter"
    )
    offset = level_five["offset"]
    assert offset == 18
    assert level_five["length"] == 2
    assert level_five["endianness"] == "big"
    assert int.from_bytes(frame[offset : offset + 2], "big") == 0x1234
    assert frame[19] == 0x34
    assert "Only its Silkn7 role is unknown" in characteristic["notes"]


def test_guide_counter_offsets_include_byte_19():
    guide = (ROOT / "docs/devices/silkn-infinity.md").read_text(encoding="utf-8")
    assert "| 10–19 | 5 × 2 | u16 BE |" in guide
    assert "byte 19 is the level-5 high byte" in guide
    assert "Byte 19 is unused/unknown in both layouts" not in guide
