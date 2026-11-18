"""Independent Chef iQ advertisement layout and range-suppression vectors."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC = yaml.safe_load(
    (ROOT / "device-specs/devices/chef-iq-sense.yaml").read_text(encoding="utf-8")
)
DETAILS = SPEC["protocol_details"]["probe_advertisements"]


def decode_temperature(raw):
    if raw >= DETAILS["sentinel_min_raw"]:
        return None
    value = raw / 10
    if not DETAILS["minimum_c"] <= value <= DETAILS["maximum_c"]:
        return None
    return value


def test_major_nibble_and_v3_seven_field_layout():
    vector = DETAILS["synthetic_major_5_vector"]
    payload = bytearray.fromhex(vector["header_hex"])
    for raw in vector["raw_values"]:
        payload += raw.to_bytes(2, "little", signed=True)
    assert payload[1] >> 4 == 5
    layout = DETAILS["temperature_layouts"][5]
    offsets = [layout["ambient"], layout["food"], *layout["tips"], 14]
    decoded = [
        decode_temperature(int.from_bytes(payload[offset : offset + 2], "little", signed=True))
        for offset in offsets
    ]
    assert decoded == vector["expected_c"]


def test_no_reading_threshold_and_plausible_range_are_both_enforced():
    assert 32000 == 0x7D00
    assert decode_temperature(32000) is None
    assert decode_temperature(0x7FF0) is None
    assert decode_temperature(0x7FFF) is None
    assert decode_temperature(-400) == -40.0
    assert decode_temperature(6000) == 600.0
    assert decode_temperature(-401) is None
    assert decode_temperature(6001) is None


def test_exact_major_boundaries_and_status_fields_fail_closed():
    layouts = DETAILS["temperature_layouts"]
    assert set(layouts) == {2, 3, 4, 5}
    assert 6 not in layouts
    assert layouts[2]["battery"] is None
    assert layouts[3]["battery"] == 8
    assert layouts[2]["status_packet"] is False
    assert layouts[3]["status_packet"] is False
    assert layouts[4]["battery"] == 2
    assert layouts[4]["status_fields"] is False
    assert layouts[5]["battery"] is None
    assert layouts[5]["status_fields"] is True
    status = DETAILS["status"]
    assert status["minimum_major"] == 4
    assert status["sensor_fields_minimum_major"] == 5
    assert status["major_4_minimum_bytes"] == 8
    assert status["major_5_minimum_bytes"] == 10
