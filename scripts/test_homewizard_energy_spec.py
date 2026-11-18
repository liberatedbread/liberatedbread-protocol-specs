"""Offline conformance for HomeWizard P1 and Energy Socket specifications.

Protocol selection, alias mapping and token validation are transcribed with the
standard library. PyYAML/pytest only load the documents and execute checks; no
vendor client is imported and no discovery, token, TLS or device request is
made. Fixtures use invented serial 001122aabbcc and network name ExampleNet.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
P1_PATH = ROOT / "device-specs" / "devices" / "homewizard-p1-meter.yaml"
SOCKET_PATH = ROOT / "device-specs" / "devices" / "homewizard-energy-socket.yaml"
RESEARCH_PATH = ROOT / "research-notes" / "homewizard-energy.md"


@pytest.fixture(scope="module")
def p1() -> dict:
    return yaml.safe_load(P1_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def socket() -> dict:
    return yaml.safe_load(SOCKET_PATH.read_text(encoding="utf-8"))


def endpoint(spec, name):
    return next(item for item in spec["http_endpoints"] if item["name"] == name)


def response_fields(spec, name):
    fields = endpoint(spec, name)["response_body"]["fields"]
    return {field["name"]: field for field in fields}


def test_p1_v1_exact_measurement_schema_and_units(p1):
    fields = response_fields(p1, "v1 P1 Measurement")
    expected = {
        "unique_id", "smr_version", "meter_model", "wifi_ssid", "wifi_strength", "active_tariff",
        "total_power_import_kwh", "total_power_export_kwh",
        "active_power_w", "active_frequency_hz",
        "any_power_fail_count", "long_power_fail_count", "active_power_average_w",
        "montly_power_peak_w", "montly_power_peak_timestamp",
        "total_gas_m3", "gas_timestamp", "unique_gas_id", "gas_unique_id", "external",
    }
    for direction in ("import", "export"):
        expected.update(f"total_power_{direction}_t{index}_kwh" for index in range(1, 5))
    for phase in range(1, 4):
        expected.update(
            {
                f"active_power_l{phase}_w",
                f"active_voltage_l{phase}_v",
                f"active_current_l{phase}_a",
                f"voltage_sag_l{phase}_count",
                f"voltage_swell_l{phase}_count",
            }
        )
    assert set(fields) == expected
    assert all("required" not in field for field in fields.values())
    for name, field in fields.items():
        if name.endswith("_kwh"):
            assert field["unit"] == "kWh"
            assert field["unit"] != "Wh"
        elif name.endswith("_w"):
            assert field["unit"] == "W"
        elif name.endswith("_v"):
            assert field["unit"] == "V"
        elif name.endswith("_a"):
            assert field["unit"] == "A"
    assert fields["active_frequency_hz"]["unit"] == "Hz"
    assert fields["total_gas_m3"]["unit"] == "m³"
    assert fields["wifi_strength"]["unit"] == "%"
    assert "monthly_power_peak_w" not in fields
    assert "montly_power_peak_w" in fields
    assert "montly_power_peak_timestamp" in fields
    assert fields["montly_power_peak_timestamp"]["type"] == "integer"
    assert "UTC" not in fields["montly_power_peak_timestamp"].get("unit", "")


def test_p1_v2_exact_measurement_schema_and_units(p1):
    fields = response_fields(p1, "v2 P1 Measurement")
    expected = {
        "unique_id", "protocol_version", "meter_model", "timestamp", "tariff",
        "energy_import_kwh", "energy_export_kwh", "power_w",
        "voltage_v", "current_a", "frequency_hz",
        "any_power_fail_count", "long_power_fail_count",
        "average_power_15m_w", "monthly_power_peak_w", "monthly_power_peak_timestamp", "external",
    }
    for direction in ("import", "export"):
        expected.update(f"energy_{direction}_t{index}_kwh" for index in range(1, 5))
    for phase in range(1, 4):
        expected.update(
            {
                f"power_l{phase}_w",
                f"voltage_l{phase}_v",
                f"current_l{phase}_a",
                f"voltage_sag_l{phase}_count",
                f"voltage_swell_l{phase}_count",
            }
        )
    assert set(fields) == expected
    assert all("required" not in field for field in fields.values())
    for name, field in fields.items():
        if name.endswith("_kwh"):
            assert field["unit"] == "kWh"
        elif name.endswith("_w"):
            assert field["unit"] == "W"
        elif name.endswith("_v"):
            assert field["unit"] == "V"
        elif name.endswith("_a"):
            assert field["unit"] == "A"
    assert fields["frequency_hz"]["unit"] == "Hz"
    assert "montly_power_peak_w" not in fields
    assert fields["monthly_power_peak_timestamp"]["type"] == "string"
    assert "absolute" in fields["current_a"]["description"]


def test_p1_system_fields_have_exact_units(p1):
    fields = response_fields(p1, "v2 System Status")
    assert set(fields) == {
        "wifi_ssid", "wifi_rssi_db", "uptime_s", "cloud_enabled",
        "status_led_brightness_pct", "api_v1_enabled",
    }
    assert fields["wifi_rssi_db"]["unit"] == "dBm"
    assert fields["uptime_s"]["unit"] == "s"
    assert fields["status_led_brightness_pct"]["unit"] == "%"
    assert response_fields(p1, "v1 System Status") == {"cloud_enabled": {"name": "cloud_enabled", "type": "boolean"}}


def test_p1_v1_to_v2_aliases_are_exact(p1):
    aliases = p1["protocol_details"]["field_aliases"]
    expected = {
        "smr_version": "protocol_version",
        "active_tariff": "tariff",
        "active_power_w": "power_w",
        "active_frequency_hz": "frequency_hz",
        "active_power_average_w": "average_power_15m_w",
        "montly_power_peak_w": "monthly_power_peak_w",
        "montly_power_peak_timestamp": "monthly_power_peak_timestamp",
        "external": "external",
    }
    for direction, replacement in (("import", "energy_import"), ("export", "energy_export")):
        expected[f"total_power_{direction}_kwh"] = f"{replacement}_kwh"
        for tariff in range(1, 5):
            expected[f"total_power_{direction}_t{tariff}_kwh"] = f"{replacement}_t{tariff}_kwh"
    for phase in range(1, 4):
        expected[f"active_power_l{phase}_w"] = f"power_l{phase}_w"
        expected[f"active_voltage_l{phase}_v"] = f"voltage_l{phase}_v"
        expected[f"active_current_l{phase}_a"] = f"current_l{phase}_a"
    for direction in ("import", "export"):
        expected[f"total_power_{direction}_kwh"] = f"energy_{direction}_kwh"
    assert {key: value for key, value in aliases.items() if key != "semantics" and key != "verification"} == expected


def normalize_measurement(version, payload):
    """Apply protocol_details.field_aliases only by negotiated API version."""
    if version == "v2":
        return dict(payload)
    if version != "v1":
        raise ValueError("unsupported API")
    aliases = {
        "smr_version": "protocol_version",
        "active_tariff": "tariff",
        "active_power_w": "power_w",
        "active_power_l1_w": "power_l1_w",
        "active_power_l2_w": "power_l2_w",
        "active_power_l3_w": "power_l3_w",
        "active_voltage_l1_v": "voltage_l1_v",
        "active_voltage_l2_v": "voltage_l2_v",
        "active_voltage_l3_v": "voltage_l3_v",
        "active_current_l1_a": "current_l1_a",
        "active_current_l2_a": "current_l2_a",
        "active_current_l3_a": "current_l3_a",
        "active_frequency_hz": "frequency_hz",
        "active_power_average_w": "average_power_15m_w",
        "montly_power_peak_w": "monthly_power_peak_w",
        "montly_power_peak_timestamp": "monthly_power_peak_timestamp",
        "total_power_import_kwh": "energy_import_kwh",
        "total_power_export_kwh": "energy_export_kwh",
        "external": "external",
    }
    for direction in ("import", "export"):
        for tariff in range(1, 5):
            aliases[f"total_power_{direction}_t{tariff}_kwh"] = f"energy_{direction}_t{tariff}_kwh"
    normalized = dict(payload)
    for old, new in aliases.items():
        if old in payload:
            normalized[new] = payload[old]
    return normalized


def test_v1_fixture_aliases_work_without_wifi_ssid(p1):
    payload = json.loads(endpoint(p1, "v1 P1 Measurement")["response_body"]["example"])
    assert "wifi_ssid" not in payload
    normalized = normalize_measurement("v1", payload)
    assert normalized["protocol_version"] == 50
    assert normalized["energy_import_kwh"] == 13779.338
    assert normalized["energy_export_kwh"] == 0
    assert normalized["power_w"] == -543
    assert normalized["current_l1_a"] == -4
    assert normalized["monthly_power_peak_w"] == 1111.0
    assert normalized["monthly_power_peak_timestamp"] == 230101080010
    assert normalized["external"][1]["unit"] == "m3"
    assert normalized["external"][1]["value"] == 123.456
    assert isinstance(normalized["monthly_power_peak_timestamp"], int)


def test_v2_fixture_retains_naive_timestamp_and_absolute_current(p1):
    payload = json.loads(endpoint(p1, "v2 P1 Measurement")["response_body"]["example"])
    normalized = normalize_measurement("v2", payload)
    assert normalized["timestamp"] == "2024-06-28T14:12:34"
    assert not normalized["timestamp"].endswith("Z")
    assert normalized["monthly_power_peak_timestamp"] == "2024-06-04T10:11:22"
    assert normalized["current_a"] == sum(
        abs(normalized[f"current_l{phase}_a"]) for phase in range(1, 4)
    )
    assert normalized["current_a"] != sum(
        normalized[f"current_l{phase}_a"] for phase in range(1, 4)
    )


def test_missing_points_are_not_zero_and_external_units_survive():
    normalized = normalize_measurement("v1", {"external": [{"type": "heat_meter", "value": 2.5, "unit": "GJ"}]})
    assert "energy_import_kwh" not in normalized
    assert normalized.get("energy_import_kwh") is None
    assert normalized.get("energy_import_kwh", 0) == 0  # explicit caller default, never parser inference
    assert normalized["external"][0]["unit"] == "GJ"


def select_p1_api(candidates):
    """Select from advertised service/product/API metadata, never URL errors."""
    v2 = [
        item
        for item in candidates
        if item.get("service") == "_homewizard._tcp.local."
        and item.get("product_type") == "HWE-P1"
        and tuple(map(int, item.get("api_version", "0").split("."))) >= (2, 3, 0)
    ]
    if v2:
        return {"scheme": "https", "port": 443, "path": "/api/measurement"}
    v1 = [
        item
        for item in candidates
        if item.get("service") == "_hwenergy._tcp.local."
        and item.get("product_type") == "HWE-P1"
        and item.get("path") == "/api/v1"
        and item.get("api_enabled") == "1"
    ]
    if v1:
        return {"scheme": "http", "port": 80, "path": "/api/v1/data"}
    raise ValueError("no supported negotiated P1 API")


def test_api_selection_prefers_supported_v2_not_path_fallback(p1):
    v1 = {
        "service": "_hwenergy._tcp.local.", "product_type": "HWE-P1",
        "path": "/api/v1", "api_enabled": "1", "api_version": "v1",
    }
    v2 = {
        "service": "_homewizard._tcp.local.", "product_type": "HWE-P1", "api_version": "2.3.0",
    }
    assert select_p1_api([v1, v2]) == {"scheme": "https", "port": 443, "path": "/api/measurement"}
    assert select_p1_api([v1, {**v2, "api_version": "2.2.0"}]) == {
        "scheme": "http", "port": 80, "path": "/api/v1/data",
    }
    with pytest.raises(ValueError):
        select_p1_api([{**v2, "api_version": "2.2.0"}])
    with pytest.raises(ValueError):
        select_p1_api([{**v1, "product_type": "HWE-SKT"}, v2 | {"product_type": "HWE-SKT"}])
    selection = p1["protocol_details"]["api_selection"]
    assert selection["v1"]["port"] == 80
    assert selection["v2"]["port"] == 443
    assert selection["v2"]["minimum_api_version"] == "2.3.0"
    assert "Timeout, 404, 401, 503 and TLS failure" in selection["no_path_fallback"]


def test_v2_tls_uses_ca_and_p1dongle_certificate_hostname(p1):
    tls = p1["protocol_details"]["tls"]
    assert tls["expected_hostname"] == "appliance/p1dongle/<serial>"
    assert tls["product_type_mapping"] == {"HWE-P1": "p1dongle"}
    serial = "001122aabbcc"
    expected = f"appliance/{tls['product_type_mapping']['HWE-P1']}/{serial}"
    assert expected == "appliance/p1dongle/001122aabbcc"
    assert "HWE-P1" not in expected
    assert tls["ca_sha256_fingerprint"] == (
        "4E:C2:77:E6:20:33:FA:E8:BC:37:3E:3F:2A:97:66:76:"
        "D3:F6:65:68:38:73:F1:EA:8E:3B:DF:78:AC:68:00:03"
    )
    assert "server_hostname" in tls["verification_rule"]
    assert "--insecure" in tls["verification_rule"]  # named only as a prohibition
    assert "Do not use --insecure" in tls["verification_rule"]


def test_v2_name_and_token_regexes_match_official_rules(p1):
    flow = p1["protocol_details"]["token_flow"]
    name_pattern = re.compile(flow["name_regex"])
    token_pattern = re.compile(flow["token_regex"])
    for name in (
        "local/example-client",
        "local/a",
        "local/with spaces/#and\\slashes",
        "local/" + "x" * 40,
    ):
        assert name_pattern.fullmatch(name), name
    for name in (
        "cloud/example-client",
        "local/",
        "local/" + "x" * 41,
        "local/invalid@name",
        "local\nname",
    ):
        assert not name_pattern.fullmatch(name), name
    assert token_pattern.fullmatch("0123456789ABCDEF0123456789ABCDEF")
    for token in (
        "0123456789abcdef0123456789abcdef",
        "0123456789ABCDEF0123456789ABCDEG",
        "0123456789ABCDEF0123456789ABCDE",
        "0123456789ABCDEF0123456789ABCDEF0",
    ):
        assert not token_pattern.fullmatch(token), token
    assert flow["window_seconds"] == 30
    assert flow["initial_error"] == {"status": 403, "body": {"error": "user:creation-not-enabled"}}
    assert flow["unauthorized"]["status"] == 401


def create_user(name, *, button_pressed, elapsed_seconds):
    if not re.fullmatch(r"^local\/[a-zA-Z0-9\-_/\\# ]{1,40}$", name):
        return 400, {"error": "request:invalid-name"}
    if not button_pressed or elapsed_seconds >= 30:
        return 403, {"error": "user:creation-not-enabled"}
    return 200, {"name": name, "token": "0123456789ABCDEF0123456789ABCDEF"}


def test_p1_physical_button_flow_is_bounded_to_30_seconds():
    assert create_user("local/example-client", button_pressed=False, elapsed_seconds=0)[0] == 403
    status, response = create_user("local/example-client", button_pressed=True, elapsed_seconds=29.9)
    assert status == 200
    assert response["token"] == "0123456789ABCDEF0123456789ABCDEF"
    assert create_user("local/example-client", button_pressed=True, elapsed_seconds=30)[0] == 403


def test_p1_endpoints_and_headers_are_exact(p1):
    expected = {
        "v1 Device Information": ("GET", "/api"),
        "v1 P1 Measurement": ("GET", "/api/v1/data"),
        "v1 DSMR Telegram": ("GET", "/api/v1/telegram"),
        "v1 System Status": ("GET", "/api/v1/system"),
        "v2 Device Information": ("GET", "/api"),
        "v2 P1 Measurement": ("GET", "/api/measurement"),
        "v2 DSMR Telegram": ("GET", "/api/telegram"),
        "v2 System Status": ("GET", "/api/system"),
        "create_local_user": ("POST", "/api/user"),
    }
    assert {name: (endpoint(p1, name)["method"], endpoint(p1, name)["path"]) for name in expected} == expected
    for name in ("read_v2_device_info", "read_v2_measurement", "read_v2_telegram", "read_v2_system"):
        command = p1["commands"][name]
        assert command["headers"]["X-Api-Version"] == "2"
        assert command["headers"]["Authorization"] == "Bearer {token}"
        assert command["parameters"]["token"]["source"] == "credential:token"
        assert command["method"] == "GET"
    assert endpoint(p1, "v1 DSMR Telegram")["response_body"]["content_type"] == "text/plain"


def test_socket_exact_measurement_schema_and_units(socket):
    fields = response_fields(socket, "Socket Measurement")
    assert set(fields) == {
        "wifi_ssid", "wifi_strength",
        "total_power_import_kwh", "total_power_import_t1_kwh",
        "total_power_export_kwh", "total_power_export_t1_kwh",
        "active_power_w", "active_power_l1_w", "active_voltage_v", "active_current_a",
        "active_reactive_power_var", "active_apparent_power_va", "active_power_factor",
        "active_frequency_hz",
    }
    for name in (
        "total_power_import_kwh", "total_power_import_t1_kwh",
        "total_power_export_kwh", "total_power_export_t1_kwh",
    ):
        assert fields[name]["unit"] == "kWh"
    assert fields["active_power_w"]["unit"] == "W"
    assert fields["active_power_l1_w"]["unit"] == "W"
    assert fields["active_voltage_v"]["unit"] == "V"
    assert fields["active_current_a"]["unit"] == "A"
    assert fields["active_reactive_power_var"]["unit"] == "var"
    assert fields["active_apparent_power_va"]["unit"] == "VA"
    assert "unit" not in fields["active_power_factor"]
    assert fields["active_frequency_hz"]["unit"] == "Hz"
    assert fields["wifi_strength"]["unit"] == "%"
    assert "active_voltage_l1_v" not in fields
    assert "active_current_l1_a" not in fields
    assert "montly_power_peak_w" not in fields


def test_socket_fixture_duplicate_fields_are_not_summed(socket):
    payload = json.loads(endpoint(socket, "Socket Measurement")["response_body"]["example"])
    aggregate = {
        "import": payload.get("total_power_import_kwh"),
        "export": payload.get("total_power_export_kwh"),
        "power": payload.get("active_power_w"),
    }
    assert aggregate == {"import": 30.511, "export": 85.951, "power": 543.312}
    assert payload["total_power_import_t1_kwh"] == aggregate["import"]
    assert payload["total_power_export_t1_kwh"] == aggregate["export"]
    assert payload["active_power_l1_w"] == aggregate["power"]
    assert payload["active_reactive_power_var"] == 123.456
    assert payload["active_apparent_power_va"] == 666.768
    assert payload["active_power_factor"] == 0.81688
    assert payload["wifi_ssid"] == "ExampleNet"


def test_socket_state_fields_and_entities_preserve_get_only_boundary(socket):
    fields = response_fields(socket, "Socket State")
    assert set(fields) == {"power_on", "switch_lock", "brightness"}
    assert fields["power_on"]["type"] == "boolean"
    assert fields["switch_lock"]["type"] == "boolean"
    assert "0 (0%) to 255 (100%)" in fields["brightness"]["description"]
    assert all(item["method"] == "GET" for item in socket["http_endpoints"])
    assert {item["path"] for item in socket["http_endpoints"]} == {
        "/api", "/api/v1/data", "/api/v1/state", "/api/v1/system",
    }
    assert all(command["method"] == "GET" for command in socket["commands"].values())
    relay = next(entity for entity in socket["entities"] if entity["name"] == "Relay State")
    assert "commands" not in relay
    assert relay["state_mapping"] == {"is_on": "power_on"}
    for entity in socket["entities"]:
        assert "turn_on" not in entity.get("commands", {})
        assert "turn_off" not in entity.get("commands", {})
    assert "PUT" not in socket["protocol_details"]["read_only_boundary"]["included"]


def test_socket_skt21_payload_is_runtime_discovered_not_a_duplicate_identity(socket):
    variants = socket["device"]["variants"]
    assert len(variants) == 1
    assert variants[0]["model"] == "HWE-SKT"
    assert variants[0]["identification"]["model_prefix"] == "HWE-SKT"
    assert "runtime-discovered" in variants[0]["notes"]
    payload = json.loads(endpoint(socket, "Socket Measurement")["response_body"]["example"])
    for field_name, entity_name, unit in (
        ("active_reactive_power_var", "Reactive Power", "var"),
        ("active_apparent_power_va", "Apparent Power", "VA"),
        ("active_power_factor", "Power Factor", None),
    ):
        assert field_name in payload
        entity = next(item for item in socket["entities"] if item["name"] == entity_name)
        assert "variants" not in entity
        assert entity.get("unit") == unit
        assert entity["state_mapping"]["value"] == field_name
    # An older HWE-SKT simply omits these optional measurements; its identity
    # does not change and the extra entities remain unoffered by a runtime mapper.
    older = {key: value for key, value in payload.items() if key not in {
        "active_reactive_power_var", "active_apparent_power_va", "active_power_factor",
    }}
    assert "total_power_import_kwh" in older
    assert not {
        "active_reactive_power_var", "active_apparent_power_va", "active_power_factor",
    } & set(older)


def test_socket_has_no_v2_discovery_or_write_routes(socket):
    methods = socket["device"]["discovery"]["methods"]
    assert len(methods) == 1
    assert methods[0]["mdns"]["service_type"] == "_hwenergy._tcp.local."
    assert methods[0]["mdns"]["port"] == 80
    assert socket["device"]["identification"]["mdns_service_type"] == "_hwenergy._tcp.local."
    assert socket["protocol_details"]["api"]["version"] == "v1"
    assert socket["protocol_details"]["polling"]["minimum_interval_ms"] == 500
    for command in socket["commands"].values():
        assert command["path"] not in ("/api/measurement", "/api/user", "/api/telegram", "/api/system")


def test_all_new_specs_are_untested_and_complete(p1, socket):
    for spec in (p1, socket):
        assert spec["device"]["testing"]["status"] == "untested"
        setup = spec["device"]["setup"]
        assert {"factory_reset", "rejoin", "credentials", "methods"} <= set(setup)
        assert setup["factory_reset"]["applicable"] == "unknown"
        assert setup["rejoin"]["requires_factory_reset"] is False
        assert all(method["verified"] is False for method in setup["methods"])
        assert spec["remaining_unknowns"]
        assert spec["device"]["pairing"]["confidence"] == "medium"

        def walk(value):
            if isinstance(value, dict):
                for key, item in value.items():
                    if key == "verification":
                        assert item == "reported"
                    else:
                        walk(item)
            elif isinstance(value, list):
                for item in value:
                    walk(item)

        walk(spec)


def test_research_note_energy_totals_are_kwh_not_wh():
    text = RESEARCH_PATH.read_text(encoding="utf-8")
    assert "Socket: import/export kWh" in text
    assert "Socket: import Wh" not in text


def test_examples_are_sanitized_and_poll_limits_present(p1, socket):
    assert json.loads(endpoint(p1, "v1 Device Information")["response_body"]["example"])["serial"] == "001122aabbcc"
    assert json.loads(endpoint(socket, "Device Information")["response_body"]["example"])["serial"] == "001122aabbcc"
    assert json.loads(endpoint(socket, "Socket Measurement")["response_body"]["example"])["wifi_ssid"] == "ExampleNet"
    assert p1["protocol_details"]["polling"]["minimum_interval_ms"] == 500
    assert p1["protocol_details"]["polling"]["recommended_default_ms"] == 1000
    assert p1["protocol_details"]["polling"]["dsmr_5"] == {"power_update_seconds": 1, "gas_update_seconds": 300}
    assert p1["protocol_details"]["polling"]["older_dsmr"] == {"power_update_seconds": 10, "gas_update_seconds": 3600}
    token_example = json.loads(endpoint(p1, "create_local_user")["response_body"]["example"])
    assert token_example == {"name": "local/example-client", "token": "0123456789ABCDEF0123456789ABCDEF"}


def test_external_meter_timestamp_formats_are_split_by_api_version(p1):
    v1_format = p1["payload_formats"]["ExternalMeterV1"]
    v2_format = p1["payload_formats"]["ExternalMeterV2"]
    v1_timestamp = next(field for field in v1_format["fields"] if field["name"] == "timestamp")
    v2_timestamp = next(field for field in v2_format["fields"] if field["name"] == "timestamp")
    assert v1_timestamp["type"] == "integer"
    assert v2_timestamp["type"] == "string"

    v1_example = json.loads(v1_format["example"])
    v2_example = json.loads(v2_format["example"])
    assert v1_example["timestamp"] == 210606140015
    assert isinstance(v1_example["timestamp"], int)
    assert v2_example["timestamp"] == "2024-06-28T14:05:00"
    assert isinstance(v2_example["timestamp"], str)

    actual_v1 = json.loads(endpoint(p1, "v1 P1 Measurement")["response_body"]["example"])
    assert [entry["timestamp"] for entry in actual_v1["external"]] == [
        210606140010, 210606140015,
    ]
    assert all(isinstance(entry["timestamp"], int) for entry in actual_v1["external"])
    actual_v2 = json.loads(endpoint(p1, "v2 P1 Measurement")["response_body"]["example"])
    assert all(isinstance(entry["timestamp"], str) for entry in actual_v2["external"])
    assert all("T" in entry["timestamp"] for entry in actual_v2["external"])
