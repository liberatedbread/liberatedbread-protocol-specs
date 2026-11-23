"""Independent transcription tests for the bounded Wyze mesh-light LAN spec.

The protocol implementation below uses only Python's standard library and the
OpenSSL executable. It imports no project helper and no third-party crypto.
"""

from pathlib import Path
import base64
import json
import shutil
import subprocess

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
SPEC_PATH = ROOT / "device-specs" / "devices" / "wyze-mesh-light-lan.yaml"


@pytest.fixture(scope="module")
def spec() -> dict:
    return yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def api(spec) -> dict:
    return spec["protocol_details"]["local_mesh_api"]


def custom_pad(plaintext: bytes) -> bytes:
    """Transcribe encryption.padding, including its aligned full block."""
    return plaintext + b"\x05" * (16 - len(plaintext) % 16)


def encrypt_inner(enr: str, inner_json: str) -> str:
    """Transcribe inner_json/encryption with stdlib + OpenSSL, never PyCrypto."""
    key = enr.encode("ascii")
    assert len(key) == 16
    padded = custom_pad(inner_json.encode("ascii"))
    result = subprocess.run(
        [
            shutil.which("openssl"),
            "enc",
            "-aes-128-cbc",
            "-K",
            key.hex(),
            "-iv",
            key.hex(),
            "-nopad",
        ],
        input=padded,
        capture_output=True,
        check=True,
    )
    return base64.b64encode(result.stdout).decode("ascii")


def build_outer(api: dict, ciphertext_base64: str) -> str:
    """Transcribe outer_json without double-encoding its reverse solidus."""
    escaped = ciphertext_base64.replace("/", "\\/")
    return api["outer_json"]["exact_prefix"] + escaped + api["outer_json"]["exact_suffix"]


def build_inner(common: dict, plist: list[dict]) -> str:
    value = {
        "mac": common["mac"],
        "index": common["index"],
        "ts": common["ts"],
        "plist": plist,
    }
    return json.dumps(value, separators=(",", ":"), ensure_ascii=True)


def test_only_the_two_cloud_model_type_tuples_are_allowed(spec, api):
    variants = spec["device"]["variants"]
    assert {(v["model"], v["cloud_product_type"]) for v in variants} == {
        ("WLPA19C", "MeshLight"),
        ("HL_LSL", "LightStrip"),
    }
    allowed = {
        (row["product_model"], row["product_type"])
        for row in api["gate"]["allowed_tuples"]
    }
    assert allowed == {("WLPA19C", "MeshLight"), ("HL_LSL", "LightStrip")}
    excluded = {
        ("WLPA19CV2", "MeshLight"),
        ("WLPA19", "Light"),
        ("WLPA19C", "LightStrip"),
        ("HL_LSLP", "LightStrip"),
        ("HL_LSL", "MeshLight"),
    }
    assert excluded.isdisjoint(allowed)


def test_every_variant_has_a_real_firmware_gate(spec):
    for variant in spec["device"]["variants"]:
        gate = variant["firmware_gate"]
        assert gate["required_capability"] == "encrypted local HTTP API on port 88"
        assert gate["minimum_version"] == "unknown"
        assert "do not write" in gate["rule"]
        assert "cloud" in gate["rule"]


def test_one_route_has_vendor_cloud_then_lan_stages(spec):
    methods = spec["device"]["setup"]["methods"]
    assert len(methods) == 1
    method = methods[0]
    assert method["type"] == "cloud_account"
    assert [stage["type"] for stage in method["stages"]] == [
        "ble_provisioning",
        "cloud_account",
        "none",
    ]
    assert "2.4 GHz" in method["stages"][0]["name"]
    assert "no account-free" in method["cloud"]["local_alternative"]
    assert "none" in spec["device"]["discovery"]
    assert "methods" not in spec["device"]["discovery"]


def test_property_vocabulary_and_ranges(api):
    props = api["inner_json"]["properties"]
    assert props["P3"]["allowed"] == ["0", "1"]
    assert (props["P1501"]["min"], props["P1501"]["max"]) == (0, 100)
    assert (props["P1502"]["min"], props["P1502"]["max"]) == (1800, 6500)
    assert props["P1502"]["unit"] == "K"
    assert props["P1507"]["pattern"] == "^[0-9A-Fa-f]{6}$"
    assert "#" not in props["P1507"]["pvalue_type"].split("without")[0]
    assert props["P1508"]["allowed"] == ["1", "2"]
    assert props["P1508"]["labels"] == ["color", "white"]
    assert "MILLISECONDS" in api["inner_json"]["fields"]["ts"]


@pytest.mark.skipif(shutil.which("openssl") is None, reason="OpenSSL is required")
def test_independent_crypto_and_outer_json_vector(api):
    vectors = api["test_vectors"]
    common = vectors["common"]
    vector = vectors["crypto"]
    assert common["enr"].encode("ascii").hex() == common["enr_hex"]
    assert len(vector["inner_json"].encode("ascii")) == vector["plaintext_length"]
    assert len(custom_pad(vector["inner_json"].encode("ascii"))) == vector["padded_length"]

    ciphertext = encrypt_inner(common["enr"], vector["inner_json"])
    assert ciphertext == vector["ciphertext_base64"]
    outer = build_outer(api, ciphertext)
    assert outer == vector["outer_json"]
    assert "\\/" in outer
    assert "\\\\/" not in outer

    decoded_outer = json.loads(outer)
    assert decoded_outer == {
        "request": "set_status",
        "isSendQueue": 0,
        "characteristics": vector["ciphertext_base64"],
    }
    assert base64.b64decode(decoded_outer["characteristics"], validate=True)


def test_constant_padding_is_not_pkcs7(api):
    for vector in api["test_vectors"]["padding"]:
        plaintext = bytes.fromhex(vector["plaintext_hex"])
        assert custom_pad(plaintext).hex() == vector["expected_padded_hex"]
    aligned = bytes(range(16))
    assert custom_pad(aligned) == aligned + b"\x05" * 16
    assert custom_pad(b"A") != b"A" + bytes([15]) * 15


def test_every_property_vector_rebuilds_from_compact_inner_json(api):
    common = api["test_vectors"]["common"]
    vectors = api["test_vectors"]["properties"]
    assert set(vectors) == {
        "power_on",
        "power_off",
        "brightness",
        "white_4000k",
        "color_00ff80",
    }
    for vector in vectors.values():
        assert build_inner(common, vector["plist"]) == vector["inner_json"]
    assert vectors["white_4000k"]["plist"][-1] == {"pid": "P1508", "pvalue": "2"}
    assert vectors["color_00ff80"]["plist"][-1] == {"pid": "P1508", "pvalue": "1"}


def test_http_200_is_ack_only_and_cloud_state_poll_remains(spec, api):
    response = api["response"]
    assert response["success_transport"] == "HTTP 200"
    assert response["acknowledgement_only"] is True
    assert response["body_schema"] is None
    assert response["local_state_read_schema"] is None
    assert "cloud" in response["actual_state_source"]
    assert spec["device"]["integration"] == "identify_only"
    assert "commands" not in spec
    assert "entities" not in spec
    assert "protocol_handler" not in spec
    endpoint = spec["http_endpoints"][0]
    assert endpoint["path"] == "/device_request"
    assert endpoint.get("advanced", False) is False
    assert "response_body" not in endpoint


def test_reset_procedures_are_exactly_model_scoped(spec):
    procedures = spec["device"]["setup"]["factory_reset"]["procedures"]
    by_model = {p["applies_to"][0]: p for p in procedures}
    assert set(by_model) == {"WLPA19C", "HL_LSL"}
    assert len(by_model["WLPA19C"]["steps"]) == 2
    bulb_action = by_model["WLPA19C"]["steps"][0]["action"]
    assert "off and on three times" in bulb_action
    assert "within six seconds" in bulb_action
    assert by_model["HL_LSL"]["hold_seconds"] == 7
    assert "at least seven seconds" in by_model["HL_LSL"]["steps"][0]["action"]
    assert all(p["verified"] is False and p["basis"] for p in procedures)


def test_lifecycle_credentials_and_enr_uncertainty_are_explicit(spec):
    setup = spec["device"]["setup"]
    assert setup["rejoin"]["requires_factory_reset"] is True
    credentials = setup["credentials"]
    assert credentials["wifi_passphrase_protection"] == "unknown"
    assert any("enr" in value for value in credentials["issued_to_client"])
    pairing = spec["device"]["pairing"]
    assert pairing["security_mode"] == "app_layer"
    assert pairing["bonding"] == "none"
    assert "not proof" in pairing["unpair"]["notes"]
    assert spec["remaining_unknowns"]
