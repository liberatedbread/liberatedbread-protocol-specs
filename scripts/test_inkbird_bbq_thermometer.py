"""INKBIRD final-slot ambient, sentinel and model-scoped status vectors."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC = yaml.safe_load(
    (ROOT / "device-specs/devices/inkbird-bbq-thermometer.yaml").read_text(
        encoding="utf-8"
    )
)


def test_four_probe_ambient_is_final_slot_not_probe_four():
    frame = (100).to_bytes(2, "little") * 4 + (200).to_bytes(2, "little")
    fields = SPEC["services"][0]["characteristics"][0]["data_format"]["fields"]
    ambient = next(field for field in fields if field["name"] == "ambient_temp")
    assert ambient["bytes"] == [-2, -1]
    assert ambient["bytes"] == [-2, -1]
    assert int.from_bytes(frame[-2:], "little", signed=True) == 200
    assert int.from_bytes(frame[6:8], "little", signed=True) == 100


def test_multi_probe_sentinels_and_single_probe_narrower_faults():
    sentinels = SPEC["protocol_details"]["data_format"]["temperature"]["sentinels"]
    for wire, raw, meaning in (
        ("fe 7f", 0x7FFE, "disconnected/fault"),
        ("ff 7f", 0x7FFF, "high_range"),
        ("00 80", 0x8000, "low_range"),
    ):
        decoded = int.from_bytes(bytes.fromhex(wire), "little")
        assert decoded == raw
        assert sentinels["multi_probe"][raw] == meaning
    assert sentinels["single_probe_bg_bt1x"] == {
        0x7FFF: "fault",
        0x8000: "fault",
    }


def test_ibt4xs_status_scope_and_backlight_off_warning():
    status = SPEC["services"][0]["characteristics"][3]["data_format"]
    bits = {entry["bit"]: entry for entry in status["bitfield"] if "bit" in entry}
    assert bits[16]["name"] == "device_temp_alarm_high"
    assert bits[17]["name"] == "device_temp_alarm_low"
    assert bits[18]["name"] == "charging"
    for bit in (16, 17, 18):
        assert "IBT-4XS only" in bits[bit]["description"]
    assert bits[19]["name"] == "unknown_19"

    commands = SPEC["services"][0]["characteristics"][1]["data_format"]["commands"]
    named = {entry["name"]: entry for entry in commands}
    assert named["get_light_switch"]["hex"] == named["set_light_off"]["hex"]
    assert "also turn the LCD backlight off" in named["get_light_switch"]["description"]
