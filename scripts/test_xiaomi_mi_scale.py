"""Xiaomi Mi Scale generation-alternative service discovery checks."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC = yaml.safe_load(
    (ROOT / "device-specs/devices/xiaomi-mi-scale.yaml").read_text(encoding="utf-8")
)
V1 = "0000181d-0000-1000-8000-00805f9b34fb"
V2 = "0000181b-0000-1000-8000-00805f9b34fb"


def test_identification_and_discovery_accept_either_generation_service():
    assert SPEC["device"]["identification"]["service_uuids"] == [V1, V2]
    ble = SPEC["device"]["discovery"]["methods"][0]["ble"]
    assert ble["service_uuids"] == [V1, V2]
    assert ble["local_name"]["value"] == "MI"
    description = SPEC["device"]["setup"]["methods"][0]["description"]
    assert "generation alternatives" in description
    assert "0x181B Body Composition (v2)" in description
