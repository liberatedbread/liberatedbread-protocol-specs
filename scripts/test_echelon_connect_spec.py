#!/usr/bin/env python3
"""Independent checks of the Echelon Connect / Stride spec (stdlib + yaml only).

Every example write is rebuilt from the frame layout the spec states
(f0, type, payload length, payload, sum8 of all earlier bytes), and every
example notification is decoded with the stated offsets and scales. The
vectors are invented values, not captures.
"""

from pathlib import Path

import pytest
import yaml

SPEC = yaml.safe_load(
    (Path(__file__).parents[1] / "device-specs/devices/echelon-connect.yaml").read_text()
)
VECTORS = SPEC["protocol_details"]["test_vectors"]
WRITE_UUID = "0bf669f2-45f2-11e7-9598-0800200c9a66"
NOTIFY_UUIDS = {
    "0bf669f3-45f2-11e7-9598-0800200c9a66",
    "0bf669f4-45f2-11e7-9598-0800200c9a66",
}


def frame(kind, payload=b""):
    body = bytes([0xF0, kind, len(payload)]) + bytes(payload)
    return body + bytes([sum(body) & 0xFF])


def checked(data):
    assert data[0] == 0xF0
    assert data[2] == len(data) - 4, "length byte must count the payload"
    assert sum(data[:-1]) & 0xFF == data[-1]
    return data


def be16(data, offset):
    return (data[offset] << 8) | data[offset + 1]


def vector(name):
    return bytes.fromhex(VECTORS[name]["hex"])


def commands():
    for service in SPEC["services"]:
        for char in service["characteristics"]:
            if char["uuid"] == WRITE_UUID:
                return char["commands"]
    raise AssertionError("write characteristic missing")


def notify_format():
    for service in SPEC["services"]:
        for char in service["characteristics"]:
            if "format" in char:
                return char
    raise AssertionError("format missing")


def encode(name, **values):
    """Encode a templated command using only what the spec declares."""
    cmd = commands()[name]
    params = cmd.get("parameters", {})
    out = bytearray()
    for item in cmd["template"]:
        if isinstance(item, int):
            out.append(item)
            continue
        key = item.strip("{}")
        spec = params[key]
        if spec.get("auto") == "checksum":
            out.append(sum(out[spec.get("checksum_start", 1):]) & 0xFF)
            continue
        raw = round(values[key] / spec.get("scale", 1))
        assert spec["min"] <= raw <= spec["max"]
        width = 2 if spec["type"] == "uint16" else 1
        order = spec.get("endianness", "little")
        out += raw.to_bytes(width, order)
    return bytes(out)


def test_every_fixed_write_is_a_valid_frame():
    for cmd in commands().values():
        if "value" in cmd:
            checked(bytes(cmd["value"]))
    for step in SPEC["initialization"]:
        if "write" in step:
            assert step["characteristic"] == WRITE_UUID
            checked(bytes(step["write"]))


def test_fixed_writes_rebuild_from_layout():
    cmds = commands()
    assert bytes(cmds["query_a1"]["value"]) == frame(0xA1)
    assert bytes(cmds["query_a3"]["value"]) == frame(0xA3)
    assert bytes(cmds["treadmill_query_a4"]["value"]) == frame(0xA4)
    assert bytes(cmds["start_stream_or_belt"]["value"]) == frame(0xB0, b"\x01")
    assert bytes(cmds["stop_belt"]["value"]) == frame(0xB0, b"\x00")
    assert bytes(cmds["treadmill_start_d0_00"]["value"]) == frame(0xD0, b"\x00")
    assert bytes(cmds["treadmill_start_d0_11"]["value"]) == frame(0xD0, b"\x11")


def test_subscriptions_are_executable_and_come_first():
    steps = SPEC["initialization"]
    subs = [s["characteristic"] for s in steps if s.get("subscribe")]
    assert set(subs) == NOTIFY_UUIDS
    assert all(s.get("subscribe") for s in steps[:2])


def test_shared_init_never_starts_a_belt():
    belt = list(commands()["start_stream_or_belt"]["value"])
    assert all(s.get("write") != belt for s in SPEC["initialization"])
    assert commands()["start_stream_or_belt"]["advanced"] is True


def test_poll_vector():
    v = VECTORS["poll_counter_5"]
    assert frame(0xA0, bytes([v["counter"]])) == vector("poll_counter_5")
    cmd = commands()["poll"]
    out = bytearray()
    for item in cmd["template"]:
        if isinstance(item, int):
            out.append(item)
        elif item == "{counter}":
            out.append(v["counter"])
        else:
            out.append(sum(out) & 0xFF)
    assert bytes(out) == vector("poll_counter_5")


def test_set_resistance_vector():
    level = VECTORS["set_resistance_12"]["level"]
    assert encode("set_resistance", level=level) == vector("set_resistance_12")
    assert frame(0xB1, bytes([level])) == vector("set_resistance_12")


def test_set_incline_vector():
    incline = VECTORS["set_incline_4"]["incline"]
    assert encode("set_incline", incline=incline) == vector("set_incline_4")


def test_set_speed_vector_is_big_endian_thousandths():
    kmh = VECTORS["set_speed_8_5_kmh"]["speed_kmh"]
    built = encode("set_speed", speed=kmh)
    assert built == vector("set_speed_8_5_kmh")
    assert built[3:5] == (8500).to_bytes(2, "big")


def test_treadmill_writes_are_flagged():
    cmds = commands()
    for name in ("set_speed", "set_incline", "start_stream_or_belt",
                 "treadmill_start_d0_00", "treadmill_start_d0_11"):
        assert cmds[name]["advanced"] is True
        assert cmds[name]["advanced_reason"]
    assert SPEC["device"]["safety_advisory"]["severity"] in {"warning", "danger"}


def test_bike_d1_decodes_with_declared_format():
    data = checked(vector("bike_d1"))
    char = notify_format()
    assert data[char["format_match"]["offset"]] == char["format_match"]["value"]
    fields = {f["name"]: f for f in char["format"]}
    out = {}
    for name in ("elapsed", "distance", "cadence"):
        f = fields[name]
        raw = int.from_bytes(data[f["offset"]:f["offset"] + f["length"]],
                             f.get("endianness", "little"))
        out[name] = raw * f.get("scale", 1)
    v = VECTORS["bike_d1"]
    assert len(data) == 13
    assert out["elapsed"] == v["elapsed_s"] == be16(data, 3)
    assert out["distance"] == pytest.approx(v["distance_raw_x0_01"])
    assert out["cadence"] == v["cadence_rpm"]


def test_treadmill_d1_heart_rate():
    data = checked(vector("treadmill_d1_hr_130"))
    offset = next(f["offset"] for f in notify_format()["format"] if f["name"] == "heart_rate")
    assert data[offset] == VECTORS["treadmill_d1_hr_130"]["heart_rate_bpm"]


def test_d2_resistance_and_incline():
    bike = checked(vector("bike_d2_resistance_20"))
    assert bike[1] == 0xD2 and bike[3] == VECTORS["bike_d2_resistance_20"]["resistance"]
    tread = checked(vector("treadmill_d2_incline_3"))
    assert tread[3] == VECTORS["treadmill_d2_incline_3"]["incline"]


def test_d3_speed():
    data = checked(vector("treadmill_d3_7_kmh"))
    scale = SPEC["payload_formats"]["Treadmill_Speed_D3"]["fields"][0]["scale"]
    assert data[1] == 0xD3
    assert be16(data, 3) * scale == pytest.approx(VECTORS["treadmill_d3_7_kmh"]["speed_kmh"])


def test_entity_bindings_resolve():
    cmds = commands()
    names = {v["model"] for v in SPEC["device"]["variants"]}
    for entity in SPEC["entities"]:
        assert set(entity.get("variants", [])) <= names
        for target in entity.get("commands", {}).values():
            assert target in cmds


def test_scope_statement_present():
    assert "July 2025" in SPEC["protocol_details"]["scope"]
