"""WLED segment-zero color JSON and current info-field contracts."""

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC = yaml.safe_load(
    (ROOT / "device-specs/devices/wled-controller.yaml").read_text(encoding="utf-8")
)


def walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def test_set_color_changes_only_segment_zero_primary_color():
    command = SPEC["commands"]["set_color"]
    body = command["body"]
    for channel, value in (("red", 0), ("green", 255), ("blue", 200)):
        body = body.replace("{" + channel + "}", str(value))
    assert json.loads(body) == {"seg": [{"id": 0, "col": [[0, 255, 200]]}]}
    assert SPEC["entities"][0]["commands"]["set_color"] == "set_color"


def test_info_uses_device_id_total_psram_size_and_free_bytes():
    info = next(
        endpoint
        for endpoint in SPEC["http_endpoints"]
        if endpoint["path"] == "/json/info"
    )
    fields = {
        item["name"]: item
        for item in walk(info)
        if isinstance(item, dict) and "name" in item and "description" in item
    }
    assert "deviceId" in fields
    assert "device_id" not in fields
    assert "MiB" in fields["psrSz"]["description"]
    assert "Free PSRAM in bytes" in fields["psram"]["description"]
