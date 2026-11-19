"""Offline Meross discovery/signature/Encrypt.Suite conformance; no actuation."""

from __future__ import annotations

import base64
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
SPEC = yaml.safe_load((ROOT / "device-specs/devices/meross-wifi-appliances.yaml").read_text())
DETAILS = SPEC["protocol_details"]
OPENSSL = shutil.which("openssl")


def aes256_cbc_zero(data: bytes, key: bytes, iv: bytes, *, decrypt: bool = False) -> bytes:
    assert OPENSSL, "OpenSSL is required for the independent AES vector check"
    command = [OPENSSL, "enc", "-aes-256-cbc", "-nopad", "-K", key.hex(), "-iv", iv.hex()]
    if decrypt:
        command.append("-d")
    else:
        data = data + bytes(16 - len(data) % 16)
    result = subprocess.run(command, input=data, capture_output=True, check=False)
    if result.returncode:
        raise ValueError("AES-256-CBC failed")
    return result.stdout


def signed_message(namespace: str, method: str, payload: dict, *, message_id: str, timestamp: int, key: str, uuid: str, address: str = "192.0.2.10") -> dict:
    sign = hashlib.md5(f"{message_id}{key}{timestamp}".encode()).hexdigest()
    return {
        "header": {
            "messageId": message_id,
            "timestamp": timestamp,
            "sign": sign,
            "method": method,
            "namespace": namespace,
            "payloadVersion": 1,
            "from": f"http://{address}/config",
            "triggerSrc": "AndroidLocal",
            "uuid": uuid,
        },
        "payload": payload,
    }


def render_template(text: str, parameters: dict) -> str:
    for name, value in parameters.items():
        text = text.replace("{" + name + "}", str(value))
    assert all("{" + name + "}" not in text for name in ("user_id", "account_key", "mqtt_host", "device_uuid"))
    return text


def test_signature_vector_and_full_envelope():
    vector = DETAILS["envelope"]["test_vector"]
    message = signed_message(
        "Appliance.System.All",
        "GET",
        {},
        message_id=vector["message_id"],
        timestamp=vector["timestamp"],
        key=vector["account_key"],
        uuid="20000000-0000-4000-8000-020000000001",
    )
    assert message["header"]["sign"] == vector["expected_sign"]
    assert len(message["header"]["messageId"]) == 32
    assert message["header"]["payloadVersion"] == 1
    assert message["payload"] == {}
    assert json.loads(SPEC["http_endpoints"][0]["request_body"]["example"]) == message


def test_encrypt_suite_key_zero_padding_and_base64_vector():
    vector = DETAILS["encrypt_suite"]["test_vector"]
    material = (
        vector["uuid"][3:22]
        + vector["account_key"][1:9]
        + vector["mac"]
        + vector["account_key"][10:28]
    )
    assert material == vector["input_material"]
    key = hashlib.md5(material.encode()).hexdigest().encode()
    assert len(key) == 32
    assert key.hex() == vector["key_ascii_hex"]
    iv = DETAILS["encrypt_suite"]["iv_ascii"].encode()
    assert iv == b"0000000000000000"
    plaintext = vector["plaintext_json"].encode()
    ciphertext = aes256_cbc_zero(plaintext, key, iv)
    assert len(ciphertext) % 16 == 0
    assert base64.b64encode(ciphertext).decode() == vector["ciphertext_base64"]
    padded = aes256_cbc_zero(ciphertext, key, iv, decrypt=True)
    assert padded == plaintext + bytes(16 - len(plaintext) % 16)
    assert json.loads(padded.rstrip(b"\x00")) == {"togglex": {"channel": 0, "onoff": 1}}
    aligned = aes256_cbc_zero(b"x" * 16, key, iv)
    assert len(aligned) == 32, "aligned input gains a full zero block, not zero bytes"


def test_discovery_probe_ports_timing_and_identity():
    vector = DETAILS["udp_discovery"]["test_vector"]
    assert hashlib.md5(vector["userid"].encode()).hexdigest() == vector["id"]
    expected = {"id": vector["id"], "devName": "*"}
    assert json.loads(vector["request_json"]) == expected
    assert json.dumps(expected, separators=(",", ":")).encode().hex() == vector["probe_hex"]
    method = SPEC["device"]["discovery"]["methods"][0]["udp_broadcast"]
    assert method["port"] == 9988
    assert method["listen_port"] == 9989
    assert method["probe_hex"] == vector["probe_hex"]
    timing = DETAILS["udp_discovery"]
    assert (timing["send_count"], timing["interval_seconds"], timing["receive_seconds"]) == (5, 1, 5)
    assert timing["reply_limit_bytes"] == 300
    reply = {
        "uuid": "20000000-0000-4000-8000-020000000001",
        "mac": "02:00:00:00:00:01",
        "devName": "Example Plug",
        "deviceType": "mss110",
    }
    stable = [entry["source"].split(":", 1)[1] for entry in method["identity_mapping"]["stable_keys"]]
    assert [reply[key] for key in stable] == [reply["uuid"], reply["mac"]]


def test_cleartext_exemptions_are_exact_and_include_negotiation():
    assert DETAILS["encrypt_suite"]["cleartext_namespace_exemptions"] == [
        "Appliance.System.All",
        "Appliance.System.Firmware",
        "Appliance.System.Ability",
        "Appliance.Encrypt.Suite",
        "Appliance.Encrypt.ECDHE",
    ]
    assert "Appliance.Control.ToggleX" not in DETAILS["encrypt_suite"]["cleartext_namespace_exemptions"]
    assert "Appliance.GarageDoor.State" not in DETAILS["encrypt_suite"]["cleartext_namespace_exemptions"]
    assert "unresolved" in DETAILS["encrypt_suite"]["setup_boundary"]


def test_config_key_is_owner_selected_reprovision_not_recovery():
    command = SPEC["commands"]["owner_config_key"]
    values = {
        "user_id": "123456",
        "account_key": "0123456789abcdef0123456789abcdef",
        "mqtt_host": "broker.example.internal",
    }
    payload = json.loads(render_template(command["body"], values))
    assert payload == {
        "key": {
            "userId": "123456",
            "key": "0123456789abcdef0123456789abcdef",
            "gateway": {
                "host": "broker.example.internal",
                "port": 443,
                "secondHost": "broker.example.internal",
                "secondPort": 443,
                "redirect": 0,
            },
        }
    }
    assert command["namespace"] == "Appliance.Config.Key"
    assert command["advanced"] is True
    assert "not recovered stock material" in command["parameters"]["account_key"]["description"]
    methods = SPEC["device"]["setup"]["methods"]
    assert "owner-selected Config.Key" in methods[0]["name"]
    assert "legacy" in methods[0]["description"]
    assert "not universal recovery" in SPEC["device"]["setup"]["notes"]


def test_togglex_and_garage_payloads_are_exact_and_advanced():
    assert json.loads(SPEC["commands"]["togglex_on"]["body"]) == {"togglex": {"channel": 0, "onoff": 1}}
    assert json.loads(SPEC["commands"]["togglex_off"]["body"]) == {"togglex": {"channel": 0, "onoff": 0}}
    assert json.loads(SPEC["commands"]["get_garage_state"]["body"]) == {"state": {"channel": 0}}
    for name, opened in (("garage_open", 1), ("garage_close", 0)):
        command = SPEC["commands"][name]
        body = json.loads(render_template(command["body"], {"device_uuid": "20000000-0000-4000-8000-020000000001"}))
        assert body == {"state": {"channel": 0, "open": opened, "uuid": "20000000-0000-4000-8000-020000000001"}}
        assert command["namespace"] == "Appliance.GarageDoor.State"
        assert command["advanced"] is True
        assert command["advanced_reason"]
    for name in ("togglex_on", "togglex_off"):
        assert SPEC["commands"][name]["advanced"] is True


def test_safety_lifecycle_and_reported_status():
    assert SPEC["device"]["integration"] == "identify_only"
    assert SPEC["device"]["testing"]["status"] == "untested"
    advisory = SPEC["device"]["safety_advisory"]
    assert advisory["acknowledge_required"] is True
    assert "not a safety interlock" in advisory["summary"]
    setup = SPEC["device"]["setup"]
    assert setup["factory_reset"]["applicable"] == "unknown"
    assert setup["rejoin"]["requires_factory_reset"] is False
    assert setup["rejoin"]["in_place_supported"] is False
    assert SPEC["device"]["pairing"]["security_mode"] == "app_layer"
    assert SPEC["remaining_unknowns"]


def validate_reply(request: dict, response: dict, account_key: str) -> dict:
    """Correlate, require ACK, authenticate, and only then return payload."""
    request_header = request["header"]
    response_header = response["header"]
    if response_header.get("messageId") != request_header["messageId"]:
        raise ValueError("messageId mismatch")
    if response_header.get("namespace") != request_header["namespace"]:
        raise ValueError("namespace mismatch")

    def authenticate():
        expected = hashlib.md5(
            f"{response_header['messageId']}{account_key}{response_header['timestamp']}".encode()
        ).hexdigest()
        if response_header.get("sign") != expected:
            raise ValueError("signature mismatch")
        if response_header.get("uuid") != request_header["uuid"]:
            raise ValueError("UUID mismatch")

    if response_header.get("method") == "ERROR":
        authenticate()
        return {"error": response["payload"]["error"]["code"]}

    expected_ack = "GETACK" if request_header["method"] == "GET" else "SETACK"
    if response_header.get("method") != expected_ack:
        raise ValueError("acknowledgement mismatch")
    authenticate()
    return response["payload"]


def correlated_pair(method="GET", namespace="Appliance.System.All", message_id="00112233445566778899aabbccddeeff"):
    key = DETAILS["envelope"]["test_vector"]["account_key"]
    uuid = "20000000-0000-4000-8000-020000000001"
    timestamp = 1700000000
    request = signed_message(
        namespace,
        method,
        {},
        message_id=message_id,
        timestamp=timestamp,
        key=key,
        uuid=uuid,
    )
    response = signed_message(
        namespace,
        "GETACK" if method == "GET" else "SETACK",
        {"answer": 42},
        message_id=message_id,
        timestamp=timestamp,
        key=key,
        uuid=uuid,
    )
    return key, request, response


def test_reply_correlation_ack_signature_uuid_then_payload():
    key, request, response = correlated_pair()
    assert validate_reply(request, response, key) == {"answer": 42}
    key, request, response = correlated_pair(method="SET", namespace="Appliance.Control.ToggleX")
    assert validate_reply(request, response, key) == {"answer": 42}

    key, request, response = correlated_pair()
    stale = signed_message(
        response["header"]["namespace"],
        "GETACK",
        {"answer": 999},
        message_id="ffeeddccbbaa99887766554433221100",
        timestamp=response["header"]["timestamp"],
        key=key,
        uuid=response["header"]["uuid"],
    )
    with pytest.raises(ValueError, match="messageId mismatch"):
        validate_reply(request, stale, key)

    wrong_namespace = signed_message(
        "Appliance.Control.ToggleX",
        "GETACK",
        {"answer": 999},
        message_id=request["header"]["messageId"],
        timestamp=response["header"]["timestamp"],
        key=key,
        uuid=response["header"]["uuid"],
    )
    with pytest.raises(ValueError, match="namespace mismatch"):
        validate_reply(request, wrong_namespace, key)

    wrong_ack = json.loads(json.dumps(response))
    wrong_ack["header"]["method"] = "SETACK"
    wrong_ack["header"]["sign"] = "not-even-a-valid-signature"
    with pytest.raises(ValueError, match="acknowledgement mismatch"):
        validate_reply(request, wrong_ack, key)

    bad_signature = json.loads(json.dumps(response))
    bad_signature["header"]["sign"] = "0" * 32
    with pytest.raises(ValueError, match="signature mismatch"):
        validate_reply(request, bad_signature, key)

    wrong_uuid = json.loads(json.dumps(response))
    wrong_uuid["header"]["uuid"] = "20000000-0000-4000-8000-020000000002"
    with pytest.raises(ValueError, match="UUID mismatch"):
        validate_reply(request, wrong_uuid, key)


def test_error_push_and_uncorrelated_replies_never_complete_a_write():
    key, request, response = correlated_pair(method="SET", namespace="Appliance.Control.ToggleX")
    error = signed_message(
        request["header"]["namespace"],
        "ERROR",
        {"error": {"code": 5001}},
        message_id=request["header"]["messageId"],
        timestamp=response["header"]["timestamp"],
        key=key,
        uuid=response["header"]["uuid"],
    )
    assert validate_reply(request, error, key) == {"error": 5001}

    bad_error = json.loads(json.dumps(error))
    bad_error["header"]["sign"] = "0" * 32
    with pytest.raises(ValueError, match="signature mismatch"):
        validate_reply(request, bad_error, key)

    push = signed_message(
        request["header"]["namespace"],
        "PUSH",
        {"togglex": {"channel": 0, "onoff": 1}},
        message_id=request["header"]["messageId"],
        timestamp=response["header"]["timestamp"],
        key=key,
        uuid=response["header"]["uuid"],
    )
    with pytest.raises(ValueError, match="acknowledgement mismatch"):
        validate_reply(request, push, key)

    missing_id = json.loads(json.dumps(response))
    del missing_id["header"]["messageId"]
    with pytest.raises(ValueError, match="messageId mismatch"):
        validate_reply(request, missing_id, key)

    policy = DETAILS["envelope"]["reply_validation"]
    assert "fresh messageId" in policy["uncorrelated_transport"]
    assert "Never match replies by arrival order" in policy["uncorrelated_transport"]
    assert "never as the answer that completes an in-flight command" in policy["unsolicited_push"]
