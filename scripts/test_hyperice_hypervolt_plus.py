"""Hyperice secure-read seed slicing without an invented fixed layout."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC = yaml.safe_load(
    (ROOT / "device-specs/devices/hyperice-hypervolt-plus.yaml").read_text(
        encoding="utf-8"
    )
)


def test_seed_is_only_the_last_three_bytes_of_any_read_length():
    secure = SPEC["services"][0]["characteristics"][0]
    assert "format" not in secure
    assert "value[-3:]" in secure["notes"]
    assert "never offset 0" in secure["notes"]
    for value in (
        bytes.fromhex("01 02 03"),
        bytes.fromhex("de ad be ef 01 01 02 03"),
        bytes.fromhex("00 00 00 00 00 00 00 00 00 00 00 01 02 03"),
    ):
        assert value[-3:] == bytes.fromhex("01 02 03")
