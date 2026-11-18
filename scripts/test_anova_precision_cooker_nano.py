"""Independent standard-library checks for the Anova Nano COBS/proto2 spec.

Nothing here imports Anova's client, generated protobuf bindings, a BLE stack or
repository helper code. The COBS codec, varint encoder and small proto2 reader
are transcribed from the spec's own transport and message definitions. Vectors
are synthetic/offline values from the YAML; no cooker command is sent.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SPEC_PATH = REPO_ROOT / "device-specs" / "devices" / "anova-precision-cooker-nano.yaml"


@pytest.fixture(scope="module")
def spec() -> dict:
    return yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def commands(spec) -> dict[str, dict]:
    tx = spec["services"][0]["characteristics"][0]
    assert tx["uuid"] == "0e140001-0af1-4582-a242-773e63054c68"
    return tx["commands"]


def encode_varint(value: int) -> bytes:
    """Unsigned protobuf base-128 varint used by non-negative UI parameters."""
    if value < 0:
        raise ValueError("this spec's unsigned UI varint cannot encode a negative value")
    output = bytearray()
    while value >= 0x80:
        output.append((value & 0x7F) | 0x80)
        value >>= 7
    output.append(value)
    return bytes(output)


def read_varint(data: bytes, offset: int) -> tuple[int, int]:
    value = 0
    for index in range(10):
        if offset >= len(data):
            raise ValueError("truncated varint")
        byte = data[offset]
        offset += 1
        value |= (byte & 0x7F) << (7 * index)
        if not byte & 0x80:
            return value, offset
    raise ValueError("overlong varint")


def cobs_encode(data: bytes) -> bytes:
    """Standard COBS, without the transport delimiter."""
    output = bytearray((0,))
    code_offset = 0
    code = 1
    for byte in data:
        if byte == 0:
            output[code_offset] = code
            code_offset = len(output)
            output.append(0)
            code = 1
        else:
            output.append(byte)
            code += 1
            if code == 0xFF:
                output[code_offset] = code
                code_offset = len(output)
                output.append(0)
                code = 1
    output[code_offset] = code
    return bytes(output)


def frame(data: bytes) -> bytes:
    return cobs_encode(data) + b"\x00"


def cobs_decode_framed(data: bytes) -> bytes:
    """Strict delimiter removal and COBS decode per protocol_details.transport."""
    if not data or data[-1] != 0:
        raise ValueError("missing COBS frame delimiter")
    encoded = data[:-1]
    if not encoded or 0 in encoded:
        raise ValueError("zero inside COBS-encoded frame")
    output = bytearray()
    offset = 0
    while offset < len(encoded):
        code = encoded[offset]
        offset += 1
        if code == 0:
            raise ValueError("zero COBS code")
        if offset + code - 1 > len(encoded):
            raise ValueError("truncated COBS block")
        output.extend(encoded[offset : offset + code - 1])
        offset += code - 1
        if code < 0xFF and offset < len(encoded):
            output.append(0)
    return bytes(output)


def logical_command(command: dict, parameters: dict[str, int]) -> bytes:
    """Render a declared pre-COBS value/template; do not write it directly."""
    if "value" in command:
        assert not parameters
        return bytes(command["value"])
    output = bytearray()
    for item in command["template"]:
        if isinstance(item, int):
            output.append(item)
            continue
        name = item.strip("{}")
        definition = command["parameters"][name]
        assert definition["type"] == "varint"
        output.extend(encode_varint(parameters[name]))
    return bytes(output)


def parse_fields(data: bytes) -> list[tuple[int, int, int | bytes]]:
    """Small bounded proto2 reader for the messages declared in the spec."""
    fields = []
    offset = 0
    while offset < len(data):
        tag, offset = read_varint(data, offset)
        field_number, wire_type = tag >> 3, tag & 7
        if field_number == 0:
            raise ValueError("invalid field zero")
        if wire_type == 0:
            value, offset = read_varint(data, offset)
        elif wire_type == 2:
            length, offset = read_varint(data, offset)
            if offset + length > len(data):
                raise ValueError("truncated length-delimited field")
            value = data[offset : offset + length]
            offset += length
        else:
            raise ValueError(f"unsupported protobuf wire type {wire_type}")
        fields.append((field_number, wire_type, value))
    return fields


def decode_sensor_list(raw: bytes) -> list[dict[str, int]]:
    if raw[:2] != b"\x00\x05":
        raise ValueError("not the expected get_sensors response")
    sensors = []
    for field, wire, entry in parse_fields(raw[2:]):
        if field != 1 or wire != 2:
            raise ValueError("SensorValueList only declares repeated field 1 messages")
        values = {}
        for nested_field, nested_wire, value in parse_fields(entry):
            if nested_wire != 0 or nested_field not in (1, 2, 3):
                raise ValueError("unexpected SensorValue field")
            values[nested_field] = value
        if set(values) != {1, 2, 3}:
            raise ValueError("SensorValue requires value, units and sensorType")
        sensors.append({"value": values[1], "units": values[2], "sensor_type": values[3]})
    return sensors


def test_command_vectors_rebuild_from_pre_cobs_templates(spec, commands):
    vectors = spec["protocol_details"]["command_vectors"]
    assert len(vectors) == 8
    for vector in vectors:
        command = commands[vector["name"]]
        parameters = vector.get("parameters", {})
        raw = logical_command(command, parameters)
        assert raw == bytes.fromhex(vector["raw_hex"]), vector["name"]
        assert frame(raw) == bytes.fromhex(vector["framed_hex"]), vector["name"]
        assert cobs_decode_framed(frame(raw)) == raw, vector["name"]


def test_cobs_matches_independent_standard_examples():
    examples = {
        "": "01",
        "00": "01 01",
        "11 22 00 33": "03 11 22 02 33",
        "00 07": "01 02 07",
        "00 06 08 00": "01 03 06 08 01",
    }
    for raw_hex, encoded_hex in examples.items():
        raw = bytes.fromhex(raw_hex)
        assert cobs_encode(raw) == bytes.fromhex(encoded_hex)
        assert cobs_decode_framed(frame(raw)) == raw

    # Include code-0xff block boundaries and zero runs, not just short commands.
    for size in list(range(260)) + [300, 511, 600]:
        raw = bytes((index * 37 + index // 11) & 0xFF for index in range(size))
        assert cobs_decode_framed(frame(raw)) == raw
        assert 0 not in frame(raw)[:-1]


def test_framed_decoder_rejects_truncation_and_bad_delimiters():
    for value in (b"", b"\x01", b"\x00", b"\x02\x00", b"\x03\x01\x00"):
        with pytest.raises(ValueError):
            cobs_decode_framed(value)


def test_twenty_byte_chunking_preserves_complete_frame(commands):
    raw = logical_command(commands["set_target_temperature"], {"setpoint": 655})
    framed = frame(raw)
    chunks = [framed[index : index + 20] for index in range(0, len(framed), 20)]
    assert all(len(chunk) <= 20 for chunk in chunks)
    assert b"".join(chunks) == framed
    assert cobs_decode_framed(b"".join(chunks)) == raw


def test_sensor_response_vector_decodes_with_entry_units(spec):
    vector = spec["protocol_details"]["response_vectors"][0]
    raw = cobs_decode_framed(bytes.fromhex(vector["framed_hex"]))
    assert raw == bytes.fromhex(vector["raw_hex"])
    sensors = decode_sensor_list(raw)
    assert len(sensors) == 1
    sensor = sensors[0]
    expected = vector["expected"]
    assert sensor["sensor_type"] == expected["sensor_type"]
    assert sensor["units"] == expected["units"]
    assert sensor["value"] == expected["raw_value"]

    unit = next(row for row in spec["protocol_details"]["unit_types"] if row["value"] == sensor["units"])
    decoded = sensor["value"] * unit["scale"]
    assert decoded == expected["decoded_value"]
    assert unit["unit"] == expected["decoded_unit"]


def test_every_temperature_unit_has_the_documented_scale(spec):
    expected = {
        0: (0.1, "C"),
        1: (0.1, "F"),
        4: (0.01, "C"),
        5: (0.01, "F"),
        6: (1.0, "C"),
        7: (1.0, "F"),
    }
    rows = {row["value"]: row for row in spec["protocol_details"]["unit_types"]}
    assert set(rows) == set(range(8))
    for value, (scale, unit_name) in expected.items():
        assert rows[value]["scale"] == scale
        assert rows[value]["unit"] == unit_name
    assert rows[2]["scale"] == 1.0 and "motor" in rows[2]["unit"]
    assert rows[3]["scale"] == 1.0 and "false" in rows[3]["unit"]


def test_varint_encoding_is_not_fixed_width_little_endian():
    assert encode_varint(0) == b"\x00"
    assert encode_varint(60) == b"\x3c"
    assert encode_varint(655) == b"\x8f\x05"
    assert encode_varint(16_384) == b"\x80\x80\x01"
    for value in (0, 1, 60, 127, 128, 655, 16_384, 2**31 - 1):
        encoded = encode_varint(value)
        decoded, offset = read_varint(encoded, 0)
        assert decoded == value
        assert offset == len(encoded)
    with pytest.raises(ValueError):
        encode_varint(-1)


def test_start_and_setpoint_are_advanced_but_stop_is_not(commands):
    for name in ("start_cooking", "set_target_temperature"):
        assert commands[name]["advanced"] is True
        assert commands[name]["advanced_reason"]
    assert "advanced" not in commands["stop_cooking"]
    assert commands["start_cooking"]["value"] == [0, 10]
    assert commands["stop_cooking"]["value"] == [0, 11]
    assert commands["set_cooking_timer"]["parameters"]["minutes"]["unit"] == "min"
    assert commands["set_target_temperature"]["parameters"]["setpoint"]["scale"] == 0.1


def test_raw_templates_require_the_handler_and_configuration_domain(spec, commands):
    assert spec["protocol_handler"] == "anova_nano_cobs"
    assert spec["protocol_details"]["transport"]["configuration_domain"] == 0
    for name, command in commands.items():
        raw = logical_command(command, {"setpoint": 655, "unit": 0, "minutes": 60} if "template" in command else {})
        assert raw[0] == 0, name
        assert raw[1] == command["command_id"], name
    for vector in spec["protocol_details"]["command_vectors"]:
        command = commands[vector["name"]]
        parameters = vector.get("parameters", {})
        assert logical_command(command, parameters) != bytes.fromhex(vector["framed_hex"])


def test_initialization_subscribes_before_any_framed_unit_request(spec):
    initialization = spec["initialization"]
    assert initialization[0]["characteristic"].endswith("0002-0af1-4582-a242-773e63054c68")
    assert initialization[0]["subscribe"] is True
    assert initialization[1]["characteristic"].endswith("0003-0af1-4582-a242-773e63054c68")
    assert initialization[1]["subscribe"] is True
    assert "description" in initialization[2]
    assert "write" not in initialization[2], "00 07 must go through COBS, not a raw write"


def test_model_scope_and_unverified_boundaries(spec):
    device = spec["device"]
    assert device["model"] == "Precision Cooker Nano"
    assert device["testing"]["status"] == "untested"
    assert device["pairing"]["required"] == "unknown"
    assert device["setup"]["factory_reset"]["applicable"] == "unknown"
    assert "conflict" in device["openness"]["notes"]
    assert "excluded_operations" in spec["protocol_details"]
    unknowns = "\n".join(spec["remaining_unknowns"])
    for subject in ("ASYNC", "Pairing", "temperature range", "Timer", "MessageError"):
        assert subject.lower() in unknowns.lower()
