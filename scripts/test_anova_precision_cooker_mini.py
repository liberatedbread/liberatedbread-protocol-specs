"""Independent, standard-library transcription of the Anova Mini spec.

The protocol implementation below is derived from the YAML's Base64/JSON rules;
it imports none of the reference client or this repository's helper code. Exact
and synthetic vectors come from the spec itself. No BLE library or hardware is
used, and no heater command is sent.
"""

from __future__ import annotations

import base64
import binascii
import json
import math
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SPEC_PATH = REPO_ROOT / "device-specs" / "devices" / "anova-precision-cooker-mini.yaml"


@pytest.fixture(scope="module")
def spec() -> dict:
    return yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def characteristics(spec) -> dict[str, tuple[dict, dict]]:
    return {
        characteristic["uuid"]: (service, characteristic)
        for service in spec["services"]
        for characteristic in service["characteristics"]
    }


def decode_wire_object(data: bytes) -> dict:
    """Per protocol_details.json_base64_transport, with strict failures."""
    try:
        plaintext = base64.b64decode(data, validate=True)
        value = json.loads(plaintext.decode("utf-8"))
    except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("not a Base64/UTF-8 JSON value") from error
    if not isinstance(value, dict):
        raise ValueError("the Mini payload is not a JSON object")
    return value


def finite_number(value, field: str) -> float:
    """Per payload_formats.CurrentTemperature: missing/bad is not zero."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} is not numeric")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{field} is not finite")
    return number


def test_gatt_map_and_clock_resolution(spec, characteristics):
    expected = {
        "0f5639f7-3c4e-47d0-9496-0672c89ea48a",
        "6ffdca46-d6a8-4fb2-8fd9-c6330f1939e3",
        "a2b179f8-944e-436f-a246-c66caaf7061f",
        "54e53c60-367a-4783-a5c1-b1770c54142b",
        "d8a89692-cae8-4b74-96e3-0b99d3637793",
        "153c9432-7c83-4b88-9252-7588229d5473",
    }
    assert set(characteristics) == expected
    assert [service["uuid"] for service in spec["services"]] == [
        "910772a8-a5e7-49a7-bc6d-701e9a783a5c"
    ]
    conflict = spec["protocol_details"]["source_conflicts"]["clock_uuid"]
    assert "96e3" in conflict and "96c3" in conflict
    assert "d8a89692-cae8-4b74-96c3-0b99d3637793" not in characteristics


def test_every_documented_command_vector_round_trips(spec):
    vectors = spec["protocol_details"]["test_vectors"]
    assert len(vectors) >= 5
    for vector in vectors:
        # The spec permits legal JSON whitespace. Its literal vectors use the
        # reference client's ordinary json.dumps spacing, reproduced here.
        value = json.loads(vector["json_text"])
        encoded = base64.b64encode(json.dumps(value).encode("utf-8"))
        assert encoded.decode("ascii") == vector["base64_ascii"], vector["name"]
        assert decode_wire_object(encoded) == value, vector["name"]


def test_vector_destinations_and_write_modes(spec, characteristics):
    routes = {
        "Set target to 65.0 in the current unit": (
            "0f5639f7-3c4e-47d0-9496-0672c89ea48a",
            "without_response",
        ),
        "Stop cooking": (
            "54e53c60-367a-4783-a5c1-b1770c54142b",
            "without_response",
        ),
        "Change unit to Celsius": (
            "54e53c60-367a-4783-a5c1-b1770c54142b",
            "without_response",
        ),
        "Start a documented example cook": (
            "54e53c60-367a-4783-a5c1-b1770c54142b",
            "without_response",
        ),
        "Set the documented UTC clock example": (
            "d8a89692-cae8-4b74-96e3-0b99d3637793",
            "with_response",
        ),
    }
    for vector in spec["protocol_details"]["test_vectors"]:
        uuid, mode = routes[vector["name"]]
        assert vector["characteristic"] == uuid
        assert vector["write_mode"] == mode
        _, characteristic = characteristics[uuid]
        if mode == "with_response":
            assert "write" in characteristic["properties"]
        else:
            assert "write_without_response" in characteristic["properties"]


def test_strict_decoder_rejects_malformed_or_non_object_values():
    for value in (b"not base64!", b"W10=", b"e30=broken"):
        with pytest.raises(ValueError):
            decode_wire_object(value)
    with pytest.raises(ValueError):
        decode_wire_object(base64.b64encode(b"[]"))
    with pytest.raises(ValueError):
        decode_wire_object(base64.b64encode(b"{} trailing"))
    with pytest.raises(ValueError):
        decode_wire_object(b"\xff")


def test_response_examples_decode_without_unit_double_conversion(spec):
    state = json.loads(spec["payload_formats"]["State"]["example"])
    temperature = json.loads(spec["payload_formats"]["CurrentTemperature"]["example"])
    timer = json.loads(spec["payload_formats"]["Timer"]["example"])

    # The number is already in the device unit. It is not a binary-scaled value
    # and must not undergo the reference plotter's second C-to-F conversion.
    state["temperatureUnit"] = "F"
    assert finite_number(temperature["current"], "current") == 65.0
    assert state["timer"]["remaining"] == 0
    assert timer["remaining"] == 3600
    assert timer["running"] is True


def test_missing_or_non_finite_temperature_never_becomes_zero():
    for value in (None, "65.0", True, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            finite_number(value, "current")
    with pytest.raises(ValueError):
        finite_number({}.get("current"), "current")


def test_commands_require_the_outer_encoder_and_gate_heater_writes(spec, characteristics):
    assert spec["protocol_handler"] == "anova_mini_base64_json"
    commands = {
        name: command
        for _, (_, characteristic) in characteristics.items()
        for name, command in (characteristic.get("commands") or {}).items()
    }
    assert commands
    for command in commands.values():
        assert command["encoding"] == "json"
    for name in ("start_cooking", "set_target_temperature"):
        assert commands[name]["advanced"] is True
        assert commands[name]["advanced_reason"]
    assert "advanced" not in commands["stop_cooking"]
    assert commands["stop_cooking"]["payload"]["key"] == "command"
    assert "min" not in commands["set_target_temperature"]["parameters"]["setpoint"]
    assert "max" not in commands["set_target_temperature"]["parameters"]["setpoint"]


def test_model_scope_and_unverified_boundaries(spec):
    device = spec["device"]
    assert device["model"] == "Precision Cooker Mini"
    assert device["testing"]["status"] == "untested"
    assert device["pairing"]["required"] is True
    assert device["setup"]["factory_reset"]["applicable"] == "unknown"
    unknowns = "\n".join(spec["remaining_unknowns"])
    for subject in ("Notification", "temperature range", "timer zero", "MTU", "reset"):
        assert subject.lower() in unknowns.lower()
    assert not spec.get("initialization"), "no raw clock/start write belongs in generic initialization"


def _no_argument_action_is_fillable(entity: dict, role: str, commands: dict) -> bool:
    """Whether a generic entity action can run without gathering any fields."""
    command_name = (entity.get("commands") or {}).get(role)
    if command_name is None:
        return False
    parameters = commands[command_name].get("parameters") or {}
    return all(
        any(key in (parameter or {}) for key in ("default", "source", "auto"))
        for parameter in parameters.values()
    )


def test_mini_start_cannot_be_a_no_argument_climate_action(spec, characteristics):
    commands = {
        name: command
        for _, (_, characteristic) in characteristics.items()
        for name, command in (characteristic.get("commands") or {}).items()
    }
    climate = next(entity for entity in spec["entities"] if entity["name"] == "Mini Sous Vide")
    assert "turn_on" not in climate["commands"]
    assert climate["commands"]["turn_off"] == "stop_cooking"

    # Guard against reintroducing the binding: all four start fields still need
    # explicit values, so the no-argument entity-action contract cannot fill them.
    start = commands["start_cooking"]
    for field in ("setpoint", "timer", "cookable_id", "cookable_type"):
        parameter = start["parameters"][field]
        assert "default" not in parameter, field
        assert "source" not in parameter, field
        assert "auto" not in parameter, field
    probe = {
        **climate,
        "commands": {**climate["commands"], "turn_on": "start_cooking"},
    }
    assert not _no_argument_action_is_fillable(probe, "turn_on", commands)


def test_mini_pairing_requirement_does_not_prove_bonding(spec):
    assert spec["device"]["pairing"]["required"] is True
    assert spec["device"]["pairing"]["bonding"] == "unknown"


def test_unit_change_is_advanced_and_not_for_a_running_cook(spec):
    found = [
        characteristic["commands"]["set_temperature_unit"]
        for service in spec["services"]
        for characteristic in service["characteristics"]
        if "set_temperature_unit" in (characteristic.get("commands") or {})
    ]
    assert len(found) == 1
    command = found[0]
    assert command["advanced"] is True
    assert "not cooking" in command["advanced_reason"]
