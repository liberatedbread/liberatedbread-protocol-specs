"""Host-only checks for the direct PicoStill telemetry document."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
SPEC_PATH = ROOT / "device-specs" / "devices" / "picobrew-picostill.yaml"
FIELDS = ("t1", "t2", "t3", "t4", "pres", "ok", "d1", "d2", "errmsg")


@pytest.fixture(scope="module")
def spec() -> dict:
    return yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))


def parse_picostill(response: str) -> dict[str, str]:
    """Transcribe payload_formats.PicoStillData without coercing any value."""
    record = response.strip()
    if len(record) < 2 or not record.startswith("#") or not record.endswith("#"):
        raise ValueError("telemetry must be enclosed in #...#")
    values = record[1:-1].split(",")
    if len(values) != len(FIELDS):
        raise ValueError(f"expected nine fields, got {len(values)}")
    return dict(zip(FIELDS, values, strict=True))


def test_documented_example_parses_to_nine_raw_strings(spec):
    example = spec["payload_formats"]["PicoStillData"]["example"]
    parsed = parse_picostill(example)
    assert list(parsed) == list(FIELDS)
    assert parsed == {
        "t1": "01.20",
        "t2": "02.30",
        "t3": "03.40",
        "t4": "04.50",
        "pres": "05.60",
        "ok": "1",
        "d1": "07.80",
        "d2": "08.90",
        "errmsg": "OK",
    }
    assert all(type(value) is str for value in parsed.values())
    assert parsed["t1"] == "01.20"  # no float/rounding/unit conversion


def test_whitespace_is_stripped_but_field_text_is_preserved():
    parsed = parse_picostill("  #1,2,3,4,5,status,7,8,#\r\n")
    assert parsed["errmsg"] == ""
    assert parsed["ok"] == "status"


@pytest.mark.parametrize(
    "record",
    [
        "1,2,3,4,5,6,7,8,message#",
        "#1,2,3,4,5,6,7,8,message",
        "#1,2,3,4,5,6,7,8#",
        "#1,2,3,4,5,6,7,8,9,extra#",
        "#1,2,3,4,5,6,7,8,error,with,commas#",
        "#1,2,3,4,5,6,7,8,message#trailing",
        "",
        "##",
    ],
)
def test_malformed_delimiters_and_field_counts_are_rejected(record):
    with pytest.raises(ValueError):
        parse_picostill(record)


def test_spec_field_order_matches_independent_parser(spec):
    declared = spec["payload_formats"]["PicoStillData"]
    assert declared["delimiter"] == ","
    assert [field["name"] for field in declared["fields"]] == list(FIELDS)
    assert [field["index"] for field in declared["fields"]] == list(range(9))
    endpoint = spec["http_endpoints"][0]
    assert [field["name"] for field in endpoint["response_body"]["fields"]] == list(FIELDS)
    assert endpoint["response_body"]["example"] == declared["example"]


def test_route_roles_and_case_are_not_flattened(spec):
    details = spec["protocol_details"]
    direct = details["direct_appliance_telemetry"]
    replacement = details["replacement_server_routes"]
    assert direct["direction"] == "Monitoring client -> PicoStill appliance, GET /data"
    assert direct["server"] == "PicoStill appliance on port 80"
    assert direct["case_sensitive"] is True
    assert direct["methods"] == ["GET"]
    assert replacement["direction"] == "PicoStill or another PicoBrew appliance -> trusted replacement server"
    assert replacement["executable"] is False
    assert replacement["declared_as_appliance_local_control"] is False
    assert replacement["case_sensitive"] is True
    assert [route["path"] for route in replacement["routes"]] == [
        "/API/PicoStill/getFirmwareAddress",
        "/firmware/picostill/<file>",
        "/API/pico/picoChangeState",
    ]
    assert all(route["safe_binding"] is False for route in replacement["routes"])
    assert spec["device"]["discovery"]["none"]


def test_no_unsafe_or_unit_bearing_bindings(spec):
    assert spec["http_endpoints"] == [
        {
            **spec["http_endpoints"][0],
            "method": "GET",
            "path": "/data",
        }
    ]
    assert "commands" not in spec
    assert "entities" not in spec
    assert "features" not in spec

    def walk(value):
        if isinstance(value, dict):
            for key, part in value.items():
                yield key
                yield from walk(part)
        elif isinstance(value, list):
            for part in value:
                yield from walk(part)

    assert "unit" not in set(walk(spec["payload_formats"]))
    assert "unit" not in set(walk(spec["http_endpoints"]))
    assert spec["protocol_details"]["excluded_control_surfaces"]["top_level_commands"] is False
    assert spec["protocol_details"]["excluded_control_surfaces"]["unit_bearing_entities"] is False


def test_noop_state_change_and_session_closure_are_not_emergency_stops(spec):
    safety = spec["protocol_details"]["no_emergency_stop"]
    assert "performs no action" in safety["picoChangeState"]
    assert "not proof" in safety["session_closure"]
    assert "No HTTP route in this spec is an emergency-abort mechanism" in safety["requirement"]
    assert spec["device"]["safety_advisory"]["severity"] == "danger"
    assert "not an emergency stop" in spec["device"]["safety_advisory"]["summary"]


def test_untested_scope_and_full_lifecycle_answers(spec):
    assert spec["device"]["testing"]["status"] == "untested"
    assert spec["local_access"]["status"] == "native"
    assert spec["device"]["setup"]["required"] is False
    assert spec["device"]["setup"]["methods"][0]["verified"] is False
    assert spec["device"]["setup"]["factory_reset"]["applicable"] == "unknown"
    assert spec["device"]["setup"]["rejoin"]["requires_factory_reset"] is False
    assert spec["device"]["pairing"]["required"] is False
    assert spec["remaining_unknowns"]
    unknowns = " ".join(spec["remaining_unknowns"])
    assert "Units, scaling, precision" in unknowns
    assert "d1/d2" in unknowns
