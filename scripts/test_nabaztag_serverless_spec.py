"""Checks the Nabaztag spec against an independent OpenAPI 1.1.0 transcription.

No device or network is contacted. EXPECTED is written from upstream
vl/api/openapi.yaml; it is not derived from the device spec being checked.
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlencode, urlparse

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
SPEC_PATH = ROOT / "device-specs" / "devices" / "nabaztag-tag-serverless.yaml"

NO_CONTENT = {"204": {"description": "Command sent successfully."}}
AI_SETTINGS = {"204": {"description": "AI settings saved."}}
AI_TURN = {"204": {"description": "AI turn started asynchronously."}}
STATUS = {
    "200": {
        "description": "A JSON object with the device's status.",
        "content": {"application/json": {"schema": {"type": "object"}}},
    }
}
ANIMATIONS = {
    "200": {
        "description": "Animations grouped by service",
        "content": {"application/json": {"schema": {"type": "object"}}},
    }
}
TASKS = {
    "200": {
        "description": "A JSON object with the tasks status.",
        "content": {"application/json": {"schema": {"type": "object"}}},
    }
}
FORTH = {
    "200": {
        "description": "Forth code executed.",
        "content": {"application/json": {"schema": {"type": "object"}}},
    }
}


def query(name: str, schema: dict, required: bool = True) -> dict:
    return {"name": name, "in": "query", "required": required, "schema": schema}


def integer(**constraints) -> dict:
    return {"type": "integer", **constraints}


def string(**constraints) -> dict:
    return {"type": "string", **constraints}


LED_PATTERN = r"^(-1|#[0-9A-Fa-f]{6})$"
AI_SCHEMAS = {
    "e": integer(enum=[0, 1]),
    "b": integer(enum=[0, 1]),
    "w": integer(enum=[0, 1]),
    "s": integer(minimum=0, maximum=255),
    "r": integer(minimum=2, maximum=20),
    "t": integer(minimum=15, maximum=255),
    "u": string(maxLength=95),
    "m": string(maxLength=47, pattern=r"^[A-Za-z0-9._-]+$"),
    "v": string(maxLength=23, pattern=r"^[A-Za-z0-9._-]+$"),
    "l": string(maxLength=7, pattern=r"^[A-Za-z]{2}(-[A-Za-z]{2})?$"),
    "p": string(maxLength=2047),
    "o": string(maxLength=95),
    "n": string(maxLength=23),
}

# method, path -> query schemas, form schemas/required fields, responses.
EXPECTED = {
    ("GET", "/taichi"): ([], None, NO_CONTENT),
    ("GET", "/nose"): ([query("v", integer(enum=[0, 1, 2, 3, 4]))], None, NO_CONTENT),
    (
        "GET",
        "/left",
    ): (
        [query("p", integer(minimum=0, maximum=16)), query("d", integer(enum=[0, 1]))],
        None,
        NO_CONTENT,
    ),
    (
        "GET",
        "/right",
    ): (
        [query("p", integer(minimum=0, maximum=16)), query("d", integer(enum=[0, 1]))],
        None,
        NO_CONTENT,
    ),
    ("GET", "/clear"): ([], None, NO_CONTENT),
    ("GET", "/weather"): ([query("v", integer(enum=[0, 1, 2, 3, 4, 5]))], None, NO_CONTENT),
    ("GET", "/stock"): ([query("v", integer(enum=[0, 1, 2, 3, 4, 5, 6]))], None, NO_CONTENT),
    ("GET", "/traffic"): ([query("v", integer(enum=[0, 1, 2, 3, 4, 5, 6]))], None, NO_CONTENT),
    ("GET", "/pollution"): ([query("v", integer(minimum=0, maximum=10))], None, NO_CONTENT),
    ("GET", "/service4"): ([query("v", integer())], None, NO_CONTENT),
    ("GET", "/service5"): ([query("v", integer())], None, NO_CONTENT),
    ("GET", "/mail"): ([query("v", integer(enum=[0, 1, 2, 3]))], None, NO_CONTENT),
    (
        "POST",
        "/leds",
    ): (
        [],
        {
            "required": [],
            "fields": {
                "n": {**string(pattern=LED_PATTERN), "example": "-1"},
                "l": {**string(pattern=LED_PATTERN), "example": "#ff0000"},
                "c": {**string(pattern=LED_PATTERN), "example": "#00ff00"},
                "r": {**string(pattern=LED_PATTERN), "example": "-1"},
                "b": {**string(pattern=LED_PATTERN), "example": "-1"},
            },
        },
        NO_CONTENT,
    ),
    ("GET", "/communication"): ([], None, NO_CONTENT),
    ("GET", "/ack"): ([], None, NO_CONTENT),
    ("GET", "/abort"): ([], None, NO_CONTENT),
    ("GET", "/ministop"): ([], None, NO_CONTENT),
    ("GET", "/play"): ([query("u", string(format="uri"))], None, NO_CONTENT),
    ("GET", "/say"): ([query("t", string())], None, NO_CONTENT),
    ("GET", "/surprise"): ([], None, NO_CONTENT),
    ("GET", "/stop"): ([], None, NO_CONTENT),
    ("GET", "/sleep"): ([], None, NO_CONTENT),
    ("GET", "/wakeup"): ([], None, NO_CONTENT),
    ("GET", "/status"): ([], None, STATUS),
    ("GET", "/animations"): ([], None, ANIMATIONS),
    ("GET", "/update-time"): ([], None, NO_CONTENT),
    ("GET", "/update-weather"): ([], None, NO_CONTENT),
    ("GET", "/reboot"): ([], None, NO_CONTENT),
    (
        "GET",
        "/setup",
    ): (
        [
            query("j", {"type": "number"}, False),
            query("k", {"type": "number"}, False),
            query("l", string(enum=["uk", "it", "fr", "es", "de"]), False),
            query("c", string(), False),
            query("d", integer(enum=[0, 1]), False),
            query("w", integer(minimum=0, maximum=23), False),
            query("b", integer(minimum=0, maximum=23), False),
            query("t", integer(enum=[0, 40, 80, 255]), False),
        ],
        None,
        NO_CONTENT,
    ),
    ("GET", "/ask"): ([query("t", string(maxLength=4000))], None, AI_TURN),
    (
        "POST",
        "/setup-ai",
    ): (
        [],
        {"required": [], "fields": AI_SCHEMAS},
        AI_SETTINGS,
    ),
    (
        "GET",
        "/setup-ai",
    ): (
        [query(name, schema, False) for name, schema in AI_SCHEMAS.items()],
        None,
        AI_SETTINGS,
    ),
    ("GET", "/tasks"): ([], None, TASKS),
    (
        "POST",
        "/forth",
    ): (
        [],
        {
            "required": ["c"],
            "fields": {"c": {**string(), "example": "left-ear forward 10 move-ear"}},
        },
        FORTH,
    ),
}


@pytest.fixture(scope="module")
def spec() -> dict:
    return yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def endpoints(spec: dict) -> dict[tuple[str, str], dict]:
    result = {}
    for endpoint in spec["http_endpoints"]:
        key = (endpoint["method"], endpoint["path"])
        assert key not in result, f"duplicate operation {key}"
        result[key] = endpoint
    return result


def normalized_form(endpoint: dict) -> dict | None:
    body = endpoint.get("request_body")
    if body is None:
        return None
    assert body["content_type"] == "application/x-www-form-urlencoded"
    assert body["required"] is True
    fields = {}
    for field in body["fields"]:
        normalized = {"type": field["type"]}
        for key in ("enum", "min", "max", "maxLength", "pattern", "example"):
            if key in field:
                normalized[key] = field[key]
        fields[field["name"]] = normalized
    return {"required": body["required_fields"], "fields": fields}


def expected_form(form: dict | None) -> dict | None:
    if form is None:
        return None
    fields = {}
    for name, schema in form["fields"].items():
        normalized = dict(schema)
        if "minimum" in normalized:
            normalized["min"] = normalized.pop("minimum")
        if "maximum" in normalized:
            normalized["max"] = normalized.pop("maximum")
        fields[name] = normalized
    return {"required": form["required"], "fields": fields}


def test_every_openapi_route_method_parameter_and_response_matches(endpoints):
    assert set(endpoints) == set(EXPECTED)
    assert len(endpoints) == 34
    assert len({path for _, path in endpoints}) == 33

    for key, (parameters, form, responses) in EXPECTED.items():
        endpoint = endpoints[key]
        actual_parameters = [
            {
                "name": parameter["name"],
                "in": parameter["in"],
                "required": parameter["required"],
                "schema": parameter["schema"],
            }
            for parameter in endpoint.get("query_parameters", [])
        ]
        assert actual_parameters == parameters, f"{key}: query contract"
        assert normalized_form(endpoint) == expected_form(form), f"{key}: form contract"
        assert endpoint["responses"] == responses, f"{key}: response contract"


def test_only_json_documented_responses_have_json_content(endpoints):
    json_routes = {("GET", "/status"), ("GET", "/animations"), ("GET", "/tasks"), ("POST", "/forth")}
    for key, endpoint in endpoints.items():
        json_responses = [
            response
            for response in endpoint["responses"].values()
            if "content" in response
        ]
        if key in json_routes:
            assert len(json_responses) == 1
            content = json_responses[0]["content"]
            assert set(content) == {"application/json"}
            assert content["application/json"]["schema"] == {"type": "object"}
        else:
            assert not json_responses
            assert set(endpoint["responses"]) == {"204"}


def test_form_examples_percent_encode_literal_values_once(endpoints):
    leds = endpoints[("POST", "/leds")]
    led_values = [(field["name"], field["example"]) for field in leds["request_body"]["fields"]]
    assert urlencode(led_values) == "n=-1&l=%23ff0000&c=%2300ff00&r=-1&b=-1"
    assert leds["request_body"]["example"] == urlencode(led_values)
    assert "#ff0000" not in leds["request_body"]["example"].split("&")[1]

    forth = endpoints[("POST", "/forth")]
    code = forth["request_body"]["fields"][0]["example"]
    assert forth["request_body"]["example"] == urlencode({"c": code})
    assert forth["request_body"]["example"] == "c=left-ear+forward+10+move-ear"


def validate_value(value: object, schema: dict) -> None:
    value_type = schema["type"]
    if value_type == "integer":
        assert isinstance(value, int) and not isinstance(value, bool)
    elif value_type == "number":
        assert isinstance(value, (int, float)) and not isinstance(value, bool)
    elif value_type == "string":
        assert isinstance(value, str)
    else:
        raise AssertionError(value_type)
    if "enum" in schema:
        assert value in schema["enum"]
    if "minimum" in schema:
        assert value >= schema["minimum"]
    if "maximum" in schema:
        assert value <= schema["maximum"]
    if "maxLength" in schema:
        assert len(value) <= schema["maxLength"]
    if "pattern" in schema:
        assert re.fullmatch(schema["pattern"], value)
    if schema.get("format") == "uri":
        parsed = urlparse(value)
        assert parsed.scheme == "http" and parsed.netloc


def representative(schema: dict):
    if "enum" in schema:
        return schema["enum"][0]
    if "minimum" in schema:
        return schema["minimum"]
    if schema.get("format") == "uri":
        return "http://192.168.1.50/example.mp3"
    if "pattern" in schema:
        if schema["pattern"] == LED_PATTERN:
            return "#a0B1c2"
        if schema["pattern"] == r"^[A-Za-z0-9._-]+$":
            return "model-id.1_test"
        if schema["pattern"] == r"^[A-Za-z]{2}(-[A-Za-z]{2})?$":
            return "en-US"
    if schema["type"] == "string":
        return "x"
    if schema["type"] == "integer":
        return 0
    if schema["type"] == "number":
        return 0.5
    raise AssertionError(schema)


def test_every_query_schema_accepts_an_independent_representative():
    for _key, (parameters, _, _) in EXPECTED.items():
        for parameter in parameters:
            validate_value(representative(parameter["schema"]), parameter["schema"])


def test_ranges_patterns_and_transport_constraints(endpoints):
    for side in ("left", "right"):
        params = endpoints[("GET", f"/{side}")]["query_parameters"]
        assert params[0]["schema"]["minimum"] == 0
        assert params[0]["schema"]["maximum"] == 16
        assert params[1]["schema"]["enum"] == [0, 1]
        with pytest.raises(AssertionError):
            validate_value(17, params[0]["schema"])
        with pytest.raises(AssertionError):
            validate_value(2, params[1]["schema"])
    with pytest.raises(AssertionError):
        validate_value(11, EXPECTED[("GET", "/pollution")][0][0]["schema"])
    with pytest.raises(AssertionError):
        validate_value("#xyz", string(pattern=LED_PATTERN))
    with pytest.raises(AssertionError):
        validate_value("https://192.168.1.50/example.mp3", string(format="uri"))
    with pytest.raises(AssertionError):
        validate_value("x" * 4001, string(maxLength=4000))


def test_device_local_routes_do_not_acquire_platform_prefix(spec, endpoints):
    assert all(not path.startswith("/vl") for _, path in endpoints)
    platform = spec["protocol_details"]["platform_host"]
    assert platform["derived_root"] == "The firmware appends /vl to the configured host."
    assert "Rabbit -> configured HTTP platform server" in platform["direction"]
    assert spec["device"]["discovery"]["none"]


def test_external_dependencies_are_separate_and_relay_secrets_stay_off_rabbit(spec):
    external = spec["protocol_details"]["external_dependencies"]
    assert set(external) == {"resource_fetch", "weather", "ntp", "ai"}
    assert external["resource_fetch"]["requirement"].startswith("Plain HTTP only")
    assert "open-meteo" in external["weather"]["provider"]
    assert "not specified" in external["ntp"]["provider"]
    assert "Rabbit -> plain-HTTP LAN relay" in external["ai"]["direction"]
    secret_rule = external["ai"]["secret_rule"]
    for secret in ("OPENAI_API_KEY", "TTS_SIGNING_SECRET"):
        assert secret in secret_rule
    assert "never accepted by /setup-ai" in secret_rule
    assert "stored in rabbit flash" in secret_rule
    assert "exposed through /status" in secret_rule

    for endpoint in spec["http_endpoints"]:
        for parameter in endpoint.get("query_parameters", []):
            assert parameter["name"] not in {"key", "api_key", "apikey", "token", "password"}
        for field in endpoint.get("request_body", {}).get("fields", []):
            assert field["name"] not in {"key", "api_key", "apikey", "token", "password"}


def test_reboot_and_forth_are_advanced_and_status_entities_are_not_invented(spec, endpoints):
    assert endpoints[("GET", "/reboot")]["advanced"] is True
    assert endpoints[("GET", "/reboot")]["advanced_reason"]
    assert endpoints[("POST", "/forth")]["advanced"] is True
    assert endpoints[("POST", "/forth")]["advanced_reason"]
    assert spec["commands"]["reboot_rabbit"]["advanced"] is True
    entity_names = {entity["name"] for entity in spec["entities"]}
    assert "Device status" not in entity_names
    assert "Left ear position" in entity_names
    assert "Right ear position" in entity_names
    assert "Nose status" in entity_names
    assert spec["device"]["pairing"]["required"] == "unknown"
    assert spec["device"]["testing"]["status"] == "untested"
    assert spec["local_access"]["status"] == "firmware_replacement"


def test_softap_setup_and_rejoin_match_readme(spec):
    method = spec["device"]["setup"]["methods"][0]
    assert method["type"] == "softap_http"
    assert method["verified"] is False
    assert method["softap"]["gateway_ip"] == "192.168.0.1"
    assert method["softap"]["ssid_prefix"] == "Nabaztag"
    assert "without an HTTP scheme" in method["description"]
    steps = " ".join(step["action"] for step in method["steps"])
    assert "without http://" in steps
    assert spec["device"]["setup"]["credentials"]["wifi_passphrase_protection"] == "plaintext"
    assert spec["device"]["setup"]["factory_reset"]["applicable"] == "unknown"
    assert spec["device"]["setup"]["rejoin"]["requires_factory_reset"] is False
