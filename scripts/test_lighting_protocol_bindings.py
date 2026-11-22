"""Focused checks for lighting discovery, fixed frames and entity contracts."""

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEVICES = ROOT / "device-specs" / "devices"


def load(name):
    return yaml.safe_load((DEVICES / f"{name}.yaml").read_text(encoding="utf-8"))


def commands(spec):
    for service in spec["services"]:
        for characteristic in service["characteristics"]:
            yield from characteristic.get("commands", {}).items()


def test_aurora_power_roles_use_fixed_frames():
    spec = load("aurora-led-shoes")
    command_map = dict(commands(spec))
    assert command_map["power_on"]["value"] == [0x05, 0x01]
    assert command_map["power_off"]["value"] == [0x05, 0x00]
    assert spec["entities"][0]["commands"]["turn_on"] == "power_on"
    assert spec["entities"][0]["commands"]["turn_off"] == "power_off"


def test_seeblue_exact_names_and_response_subscription():
    spec = load("seeblue-motorcycle-led")
    matcher = spec["device"]["discovery"]["methods"][0]["ble"]["local_name"]
    assert matcher["match"] == "regex"
    for name in ("LEDGlowMoto", "LEDGlowV2"):
        assert re.fullmatch(matcher["value"], name)
    for name in ("LEDGlow", "LEDGlowMoto2", "LEDGlowV20", "other"):
        assert not re.fullmatch(matcher["value"], name)
    assert spec["initialization"][0]["characteristic"].endswith("ffe4-0000-1000-8000-00805f9b34fb")
    assert spec["initialization"][0]["subscribe"] is True


def test_xkglow_does_not_claim_controller_config_is_light_state():
    spec = load("xkglow-chrome")
    entity = spec["entities"][0]
    assert "state_characteristic" not in entity
    assert "readback are undocumented" in entity["notes"]


def test_proglow_password_is_exactly_six_bytes():
    spec = load("proglow-motorcycle-led")
    password = dict(commands(spec))["password"]["parameters"]["password"]
    assert password["min_length"] == password["max_length"] == 6


def test_ipixel_service_remains_source_derived():
    spec = load("ipixel-color-led-panel")
    assert spec["services"][0]["verification"] == "reported"
    assert spec["device"]["testing"]["status"] == "untested"


def test_magic_display_has_no_sibling_only_multiframe_command():
    spec = load("magic-display")
    assert "multi_frame_animation_start" not in dict(commands(spec))


def test_govee_h6001_spec_and_guide_do_not_imply_wifi():
    spec = load("govee-h6001-bulb")
    descriptions = "\n".join(item["description"] for item in spec["helpful_urls"])
    assert "H6001 is\n      BLE-only" in descriptions or "H6001 is BLE-only" in descriptions
    guide = (ROOT / "docs/devices/govee-h6001-bulb.md").read_text(encoding="utf-8")
    assert "The H6001 is BLE-only." in guide
    assert "The H6001 supports Govee's local Wi-Fi API" not in guide
