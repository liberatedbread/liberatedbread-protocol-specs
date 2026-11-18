#!/usr/bin/env python3
"""Independent SOMA V2/V3 codec and generation-safety checks."""

from pathlib import Path

import pytest
import yaml

SPEC = yaml.safe_load(
    (Path(__file__).parents[1] / "device-specs/devices/soma-smart-shades.yaml").read_text()
)
VECTORS = {row["name"]: row for row in SPEC["protocol_details"]["test_vectors"]}
COMPANY_ID = 0x0370
V2_SERVICE = "00001861-b87f-490c-92cb-11ba5ea5167c"
V3_SERVICE = "8998a466-a65f-4d49-90b2-927f41c55190"


def select_generation(manufacturer_data, local_name):
    payload = manufacturer_data.get(COMPANY_ID)
    if payload is None or len(payload) < 3:
        raise ValueError("cannot select SOMA generation")
    if payload[0] < 0x10:
        if local_name != "S" or len(payload) < 4:
            raise ValueError("not a complete V2 identification")
        name = None
        if len(payload) >= 19:
            name = payload[4:19].decode("ascii", errors="ignore").rstrip()
            name = name.removesuffix("0").rstrip()
        return "V2", {
            "tilt": bool(payload[1] & 0x80),
            "current_closed": payload[2],
            "target_closed": payload[3],
            "name": name,
        }
    position, battery = payload[1], payload[2]
    if position > 100 or battery > 100:
        raise ValueError("invalid V3 percentage")
    return "V3", {"position_closed": position, "battery_percent": battery}


def build_v3(opcode, payload=b""):
    if len(payload) > 253:
        raise ValueError("payload too long")
    return bytes([opcode, len(payload)]) + payload


def parse_v3(reply, expected_opcode):
    if len(reply) < 2:
        raise ValueError("short frame")
    opcode, length = reply[0], reply[1]
    if opcode != expected_opcode:
        raise ValueError("stale response opcode")
    data = reply[2 : 2 + length]
    if len(data) != length:
        raise ValueError("truncated payload")
    return data


def v2_battery(raw):
    if len(raw) < 2:
        raise ValueError("short voltage")
    millivolts = int.from_bytes(raw[:2], "little") * 10
    estimate = max(0, min(100, (millivolts - 3600) * 100 // 500))
    return millivolts, estimate


def v3_set_position(position):
    if not 0 <= position <= 100:
        raise ValueError("position out of range")
    return build_v3(0x08, bytes([position]))


def payload(name):
    return bytes.fromhex(VECTORS[name]["payload_hex"])


def test_v2_tilt_advertisement_and_name_terminator():
    generation, decoded = select_generation({COMPANY_ID: payload("v2_tilt_advertisement")}, "S")
    assert generation == "V2"
    assert decoded == {
        "tilt": True,
        "current_closed": 100,
        "target_closed": 50,
        "name": "Room 10",
    }


def test_v3_advertisement_and_percentages():
    generation, decoded = select_generation({COMPANY_ID: payload("v3_open_advertisement")}, None)
    assert generation == "V3"
    assert decoded == {"position_closed": 0, "battery_percent": 62}


def test_v2_voltage_is_not_an_advertised_battery_percentage():
    millivolts, estimate = v2_battery(payload("v2_voltage_3850"))
    assert millivolts == 3850
    assert estimate == 50
    fields = SPEC["payload_formats"]["V2Advertisement"]["fields"]
    assert all(field["name"] != "battery_percent" for field in fields)


@pytest.mark.parametrize(
    ("millivolts", "expected"),
    [(3500, 0), (3600, 0), (3850, 50), (4100, 100), (4200, 100)],
)
def test_v2_voltage_estimate_boundaries(millivolts, expected):
    raw = (millivolts // 10).to_bytes(2, "little")
    assert v2_battery(raw) == (millivolts, expected)


def test_v3_set_position_frame_and_reply():
    assert v3_set_position(20) == payload("v3_set_20_percent")
    data = parse_v3(payload("v3_position_100"), 0x0A)
    assert data == bytes([100])
    data = parse_v3(payload("v3_battery_61"), 0x0B)
    assert data == bytes([61])


def test_v3_parser_ignores_only_declared_trailing_extension_bytes():
    reply = payload("v3_position_100") + bytes.fromhex("a5a5")
    assert parse_v3(reply, 0x0A) == bytes([100])


@pytest.mark.parametrize("bad", [b"", b"\x0a", bytes.fromhex("0a02ff")])
def test_malformed_v3_frames_are_rejected(bad):
    with pytest.raises(ValueError):
        parse_v3(bad, 0x0A)


def test_stale_v3_response_is_not_success():
    with pytest.raises(ValueError, match="stale"):
        parse_v3(payload("v3_battery_61"), 0x0A)


def test_position_and_payload_limits():
    with pytest.raises(ValueError, match="out of range"):
        v3_set_position(101)
    with pytest.raises(ValueError, match="too long"):
        build_v3(0x15, bytes(254))
    with pytest.raises(ValueError, match="short voltage"):
        v2_battery(b"\x01")


@pytest.mark.parametrize("payload_bytes", [b"", b"\x10", b"\x10\x00"])
def test_missing_advertisement_fails_closed(payload_bytes):
    with pytest.raises(ValueError, match="cannot select"):
        select_generation({COMPANY_ID: payload_bytes}, None)


def test_v2_requires_exact_name_and_complete_position_bytes():
    valid = payload("v2_tilt_advertisement")
    with pytest.raises(ValueError, match="complete V2"):
        select_generation({COMPANY_ID: valid}, "Smart Shades")
    with pytest.raises(ValueError, match="complete V2"):
        select_generation({COMPANY_ID: valid[:3]}, "S")


@pytest.mark.parametrize("bad", [bytes([0x10, 200, 50]), bytes([0x10, 50, 101])])
def test_out_of_range_v3_advertising_is_rejected(bad):
    with pytest.raises(ValueError, match="invalid V3"):
        select_generation({COMPANY_ID: bad}, None)


def test_other_company_is_not_soma():
    with pytest.raises(ValueError, match="cannot select"):
        select_generation({0x004C: bytes.fromhex("10003e")}, None)


def test_v3_read_frame_can_never_be_a_bare_v2_reset_write():
    danger = SPEC["protocol_details"]["dangerous_frame_difference"]
    assert build_v3(0x51) == bytes.fromhex("5100")
    assert build_v3(0x51) != bytes([0x51])
    assert "factory reset" in danger["v2"]
    assert "00001890-b87f-490c-92cb-11ba5ea5167c" in danger["v2"]
    assert "Never write 0x51 or 51 00" in danger["rule"]
    v2 = next(service for service in SPEC["services"] if service["uuid"] == V2_SERVICE)
    for char in v2["characteristics"]:
        for command in char.get("commands", {}).values():
            assert command.get("value") not in ([0x51], [0x51, 0x00])


def test_services_and_commands_do_not_cross_generations():
    v2 = next(service for service in SPEC["services"] if service["uuid"] == V2_SERVICE)
    v3 = next(service for service in SPEC["services"] if service["uuid"] == V3_SERVICE)
    assert all(not char["uuid"].startswith("8998a466") for char in v2["characteristics"])
    assert all(not char["uuid"].endswith("b87f-490c-92cb-11ba5ea5167c") for char in v3["characteristics"])
    commands = {
        name
        for service in (v2, v3)
        for char in service["characteristics"]
        for name in char.get("commands", {})
    }
    assert not any(any(term in name for term in ("calibrat", "schedule", "trigger", "ota", "dfu")) for name in commands)
    assert "features" not in SPEC


def test_unverified_pairing_is_not_claimed_verified():
    assert SPEC["device"]["pairing"]["required"] == "unknown"
    assert SPEC["device"]["testing"]["status"] == "untested"
    assert SPEC["device"]["setup"]["factory_reset"]["applicable"] == "unknown"


def command_definition(name):
    for service in SPEC["services"]:
        for characteristic in service["characteristics"]:
            if name in characteristic.get("commands", {}):
                return characteristic, characteristic["commands"][name]
    raise AssertionError(f"missing command {name}")


def cover_for_variant(model):
    return next(
        entity
        for entity in SPEC["entities"]
        if entity["platform"] == "cover" and model in entity.get("variants", [])
    )


def test_v3_calibrated_open_and_close_use_position_frames():
    _, open_command = command_definition("v3_open")
    _, close_command = command_definition("v3_close")
    assert open_command["value"] == [0x08, 0x01, 0x00]
    assert close_command["value"] == [0x08, 0x01, 0x64]

    v3_cover = cover_for_variant("Smart Shades 3 (V3)")
    assert v3_cover["commands"]["open_cover"] == "v3_open"
    assert v3_cover["commands"]["close_cover"] == "v3_close"
    for name, value in (
        ("v3_raw_jog_open", [0x01, 0x00]),
        ("v3_raw_jog_close", [0x02, 0x00]),
    ):
        _, command = command_definition(name)
        assert command["value"] == value
        assert command["advanced"] is True
        assert "uncalibrated" in command["description"]
        assert name not in v3_cover["commands"].values()


def v2_entity_bindings():
    v2_models = {"Smart Shades 2 (V2)", "Tilt 2 (V2)"}
    return [
        entity
        for entity in SPEC["entities"]
        if v2_models.intersection(entity.get("variants", []))
    ]


def consumer_entities_for_variant(model):
    if SPEC["device"].get("integration") == "identify_only":
        return []
    return [entity for entity in SPEC["entities"] if model in entity.get("variants", [])]


def test_tilt2_open_command_stays_position_50_without_a_generic_v2_binding():
    characteristic, command = command_definition("tilt2_open")
    assert characteristic["uuid"] == "00001526-b87f-490c-92cb-11ba5ea5167c"
    assert command["value"] == [0x32]
    assert command_definition("v2_open")[0]["uuid"] != characteristic["uuid"]
    assert all("tilt2_open" not in entity.get("commands", {}).values() for entity in SPEC["entities"])


def test_v2_name_is_exact_and_tilt_is_discriminated_by_payload():
    identification = SPEC["device"]["identification"]
    assert identification["local_names"] == ["S"]
    assert "local_name_prefix" not in identification
    for variant in SPEC["device"]["variants"]:
        assert "local_name_prefix" not in variant.get("identification", {})

    _, decoded = select_generation({COMPANY_ID: payload("v2_tilt_advertisement")}, "S")
    selected_variant = "Tilt 2 (V2)" if decoded["tilt"] else "Smart Shades 2 (V2)"
    assert selected_variant == "Tilt 2 (V2)"
    with pytest.raises(ValueError, match="complete V2"):
        select_generation({COMPANY_ID: payload("v2_tilt_advertisement")}, "S2")


@pytest.mark.parametrize(
    ("tilt_byte", "expected_variant"),
    [(0x00, "Smart Shades 2 (V2)"), (0x80, "Tilt 2 (V2)")],
)
def test_generic_consumer_renders_no_v2_entities_for_either_valid_variant(tilt_byte, expected_variant):
    advertisement = bytearray(payload("v2_tilt_advertisement"))
    advertisement[1] = tilt_byte
    generation, decoded = select_generation({COMPANY_ID: bytes(advertisement)}, "S")
    assert generation == "V2"
    selected_variant = "Tilt 2 (V2)" if decoded["tilt"] else "Smart Shades 2 (V2)"
    assert selected_variant == expected_variant

    assert SPEC["device"]["integration"] == "identify_only"
    assert v2_entity_bindings() == []
    assert consumer_entities_for_variant(selected_variant) == []
