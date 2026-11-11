"""Independent Truma iNet X and legacy TRBT frame transcriptions."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
X_SPEC = yaml.safe_load(
    (ROOT / "device-specs" / "devices" / "truma-inet-x.yaml").read_text(
        encoding="utf-8"
    )
)
BOX_SPEC = yaml.safe_load(
    (ROOT / "device-specs" / "devices" / "truma-inet-box.yaml").read_text(
        encoding="utf-8"
    )
)


def characteristic(spec, uuid):
    for service in spec["services"]:
        for char in service.get("characteristics", []):
            if char["uuid"] == uuid:
                return char
    raise AssertionError(f"characteristic not found: {uuid}")


def test_inetx_protocol_version_request_matches_published_envelope():
    command = characteristic(
        X_SPEC, "fc314002-f3b2-11e8-8eb2-f2801f1b9fd1"
    )["commands"]["protocol_version"]
    raw = bytes(command["value"])
    expected = bytes.fromhex(
        X_SPEC["protocol_details"]["frame"]["protocol_version_example"]
    )

    assert raw == expected
    assert len(raw) == 25
    assert int.from_bytes(raw[4:6], "little") == 18
    assert len(raw) == int.from_bytes(raw[4:6], "little") + 7
    assert int.from_bytes(raw[6:8], "little") == 1
    assert raw[18:] == bytes.fromhex("a1 62 70 76 82 05 01")


def test_inetx_device_list_and_group_read_lengths_and_flags():
    commands = characteristic(
        X_SPEC, "fc314002-f3b2-11e8-8eb2-f2801f1b9fd1"
    )["commands"]
    device_list = bytes(commands["device_list"]["value"])

    assert len(device_list) == 18
    assert int.from_bytes(device_list[4:6], "little") == 11
    assert int.from_bytes(device_list[6:8], "little") == 2
    assert int.from_bytes(device_list[16:18], "little") == 1

    values = {
        "target_lo": 0x06,
        "target_hi": 0x04,
        "source_lo": 0x34,
        "source_hi": 0x12,
    }
    group_read = bytes(
        values.get(part.strip("{}"), part) if isinstance(part, str) else part
        for part in commands["group_read_template"]["template"]
    )
    assert len(group_read) == 18
    assert group_read[:4] == bytes.fromhex("06 04 34 12")
    assert int.from_bytes(group_read[4:6], "little") == 11
    assert int.from_bytes(group_read[6:8], "little") == 3
    assert int.from_bytes(group_read[16:18], "little") == 4


def test_inetx_strict_read_excludes_side_effecting_frames():
    strict = X_SPEC["protocol_details"]["strict_read"]
    assert [step["operation"] for step in strict["sequence"]] == [1, 3, 2, 3]
    assert "client-system-time" in strict["excluded"]
    assert "client-last-message" in strict["excluded"]
    assert not strict["hardware_validated"]


def build_vehicle_status_request():
    fields = ["0D"] + ["0000"] * 7 + ["00"] * 8
    payload = ":".join(fields) + ":"
    header = f"TRBT:{len(payload.encode('ascii')):04X}:0017:0002:"
    return (header + payload).encode("ascii")


def test_legacy_vehicle_status_request_matches_spec_and_command():
    raw = build_vehicle_status_request()
    vector = BOX_SPEC["protocol_details"]["trbt"]["test_vectors"]
    command = characteristic(
        BOX_SPEC, "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
    )["commands"]["query_vehicle_status"]

    assert raw.decode("ascii") == vector["vehicle_status_request"]
    assert raw == bytes(command["value"])
    assert raw[:20] == b"TRBT:003E:0017:0002:"
    assert len(raw[20:]) == vector["expected"]["payload_bytes"] == 62
    assert len(raw) == vector["expected"]["total_bytes"] == 82


def test_legacy_vehicle_status_layout_scales_and_sentinels():
    payload_format = BOX_SPEC["payload_formats"]["VehicleStatus"]
    fields = payload_format["fields"]
    values = ["00"] * 17
    values[2] = "0B9A"
    values[5] = "0079"
    values[8] = "64"

    inside = fields[2]
    starter = fields[5]
    soc = fields[8]
    inside_c = int(values[2], 16) * inside["scale"] + inside["value_offset"]
    starter_v = int(values[5], 16) * starter["scale"]
    soc_percent = int(values[8], 16) * soc["scale"]

    assert round(inside_c, 2) == 23.85
    assert round(starter_v, 2) == 12.1
    assert soc_percent == 50.0
    assert inside["unit"] == "temperature_c"
    assert starter["unit"] == "voltage_v"
    assert soc["unit"] == "%"
    assert "FD" in payload_format["parse_rules"][2]
    assert "unit" not in fields[14]
    assert "unit" not in fields[16]
