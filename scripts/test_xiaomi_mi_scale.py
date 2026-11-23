"""Xiaomi Mi Scale discovery: name-only, as openScale's Mi Scale handler does."""

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC = yaml.safe_load(
    (ROOT / "device-specs/devices/xiaomi-mi-scale.yaml").read_text(encoding="utf-8")
)
V1 = "0000181d-0000-1000-8000-00805f9b34fb"
V2 = "0000181b-0000-1000-8000-00805f9b34fb"


def test_sig_scale_services_are_declared_but_not_identity():
    identification = SPEC["device"]["identification"]
    assert "service_uuids" not in identification
    assert "local_name_prefix" not in identification
    assert identification["local_name_prefixes"] == ["MIBCS", "MIBFS", "MI_SCALE"]
    assert identification["local_names"] == ["MI SCALE2"]
    ble = SPEC["device"]["discovery"]["methods"][0]["ble"]
    assert "service_uuids" not in ble
    declared = {service["uuid"] for service in SPEC["services"]}
    assert {V1, V2} <= declared


def test_discovery_regex_mirrors_openscale_names():
    ble = SPEC["device"]["discovery"]["methods"][0]["ble"]
    assert ble["local_name"]["match"] == "regex"
    needle = re.compile(ble["local_name"]["value"])
    for name in ("MIBCS", "MIBFS", "MI_SCALE", "MI_SCALE_XYZ", "MI SCALE2"):
        assert needle.search(name), name
    for name in ("MI", "MIscooter1234", "MI SCALE2X", "MI SCALE", "Mi Band", "Generic Scale"):
        assert not needle.search(name), name
    description = SPEC["device"]["setup"]["methods"][0]["description"]
    assert "generation alternatives" in description
    assert "0x181B Body Composition (v2)" in description
