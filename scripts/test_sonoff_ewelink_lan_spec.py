"""Offline Sonoff stock/DIY discovery, AES and envelope conformance."""

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
SPEC = yaml.safe_load((ROOT / "device-specs/devices/sonoff-ewelink-lan.yaml").read_text())
DETAILS = SPEC["protocol_details"]
OPENSSL = shutil.which("openssl")


def aes128_cbc(data: bytes, key: bytes, iv: bytes, *, decrypt: bool = False) -> bytes:
    assert OPENSSL, "OpenSSL is required for the independent AES vector check"
    command = [OPENSSL, "enc", "-aes-128-cbc", "-nopad", "-K", key.hex(), "-iv", iv.hex()]
    if decrypt:
        command.append("-d")
    result = subprocess.run(command, input=data, capture_output=True, check=False)
    if result.returncode:
        raise ValueError("AES-128-CBC failed")
    return result.stdout


def pkcs7(data: bytes) -> bytes:
    count = 16 - len(data) % 16
    return data + bytes([count]) * count


def pkcs7_strip(data: bytes) -> bytes:
    if not data or len(data) % 16:
        raise ValueError("invalid padded length")
    count = data[-1]
    if not 1 <= count <= 16 or data[-count:] != bytes([count]) * count:
        raise ValueError("invalid PKCS7 padding")
    return data[:-count]


def encrypt_stock(data: dict, devicekey: str, iv: bytes) -> str:
    plaintext = json.dumps(data, separators=(",", ":")).encode()
    key = hashlib.md5(devicekey.encode()).digest()
    return base64.b64encode(aes128_cbc(pkcs7(plaintext), key, iv)).decode()


def decrypt_stock(encoded: str, devicekey: str, iv64: str) -> dict:
    key = hashlib.md5(devicekey.encode()).digest()
    iv = base64.b64decode(iv64, validate=True)
    if len(iv) != 16:
        raise ValueError("invalid IV length")
    padded = aes128_cbc(base64.b64decode(encoded, validate=True), key, iv, decrypt=True)
    return json.loads(pkcs7_strip(padded))


def service_address(ipv4: str, srv_port: int | None) -> str:
    """SRV is authoritative; 8081 is only a missing-port fallback."""
    return f"http://{ipv4}:{srv_port if srv_port else 8081}"


def joined_txt(parts: dict[str, str]) -> str:
    return "".join(parts[f"data{index}"] for index in range(1, 5) if f"data{index}" in parts)


def test_stock_aes_raw_md5_iv_and_ciphertext_vector():
    vector = DETAILS["stock_crypto"]["test_vector"]
    devicekey = vector["devicekey"]
    key = hashlib.md5(devicekey.encode()).digest()
    assert key.hex() == vector["key_md5_hex"]
    assert len(key) == 16
    iv = vector["iv_ascii"].encode()
    assert base64.b64encode(iv).decode() == vector["iv_base64"]
    assert base64.b64decode(vector["iv_base64"]) == iv
    ciphertext = encrypt_stock(json.loads(vector["plaintext_data_json"]), devicekey, iv)
    assert ciphertext == vector["ciphertext_base64"]
    assert decrypt_stock(ciphertext, devicekey, vector["iv_base64"]) == {"switch": "on"}


def test_stock_request_example_has_string_data_and_all_required_fields():
    vector = DETAILS["stock_crypto"]["test_vector"]
    expected = json.loads(vector["request_example"])
    assert expected == {
        "sequence": "1700000000000",
        "deviceid": "10000000d0",
        "selfApikey": "00000000-0000-4000-8000-020000000002",
        "iv": vector["iv_base64"],
        "encrypt": True,
        "data": vector["ciphertext_base64"],
    }
    assert isinstance(expected["data"], str)
    assert len(expected["sequence"]) == 13
    encrypted = encrypt_stock({"switch": "on"}, vector["devicekey"], vector["iv_ascii"].encode())
    assert encrypted == expected["data"]
    plaintext_stock = dict(expected, encrypt=False, data=json.dumps({"switch": "on"}, separators=(",", ":")))
    assert isinstance(plaintext_stock["data"], str)
    for required in ("sequence", "deviceid", "selfApikey", "iv", "encrypt", "data"):
        assert required in plaintext_stock


def test_txt_data1_through_data4_join_precedes_json_and_base64_decode():
    plaintext = json.dumps({"switch": "on", "note": "x" * 300}, separators=(",", ":"))
    chunks = {
        f"data{index + 1}": plaintext[index * 249 : (index + 1) * 249]
        for index in range(4)
        if plaintext[index * 249 : (index + 1) * 249]
    }
    assert len(chunks) == 2
    assert len(chunks["data1"]) == 249
    assert json.loads(joined_txt(chunks)) == json.loads(plaintext)
    vector = DETAILS["stock_crypto"]["test_vector"]
    encoded = vector["ciphertext_base64"]
    encrypted_chunks = {"data1": encoded[:10], "data2": encoded[10:]}
    with pytest.raises((ValueError, TypeError)):
        base64.b64decode(encrypted_chunks["data1"], validate=True)
    assert joined_txt(encrypted_chunks) == encoded
    assert decrypt_stock(joined_txt(encrypted_chunks), vector["devicekey"], vector["iv_base64"]) == {"switch": "on"}


def test_srv_port_is_authoritative_and_8081_is_fallback_only():
    assert service_address("192.0.2.20", 9090) == "http://192.0.2.20:9090"
    assert service_address("192.0.2.20", 8081) == "http://192.0.2.20:8081"
    assert service_address("192.0.2.20", None) == "http://192.0.2.20:8081"
    discovery = SPEC["device"]["discovery"]["methods"][0]["mdns"]
    assert discovery["service_type"] == "_ewelink._tcp.local."
    assert "8081 only if no SRV port" in SPEC["device"]["discovery"]["methods"][0]["notes"]
    for instance in ("eWeLink_10000000d0", "eWelink_10000000d0"):
        assert instance[8:] == "10000000d0"


def test_stock_and_diy_bodies_cannot_be_confused():
    for name in ("stock_switch_on", "stock_switch_off"):
        command = SPEC["commands"][name]
        inner = json.loads(command["body"])
        assert inner == {"switch": "on" if name.endswith("_on") else "off"}
        assert "stock_envelope" in command["body_transform"]
        assert {"deviceid", "devicekey", "self_apikey"} <= set(command["parameters"])
    on = json.loads(SPEC["commands"]["diy_switch_on"]["body"].replace("{deviceid}", "10000000d0"))
    assert on == {"deviceid": "10000000d0", "data": {"switch": "on"}}
    assert isinstance(on["data"], dict)
    assert not {"sequence", "selfApikey", "iv", "encrypt", "devicekey"} & set(on)
    diy = DETAILS["diy_mode"]
    assert "Basic R3, RFR3 and Mini" in diy["scope"]
    assert "type=diy_plug" in diy["discovery"]
    assert diy["request_interval_ms"] == 200


def test_multi_channel_startup_pulse_and_get_state_units():
    multi = json.loads(SPEC["commands"]["stock_switches_set"]["body"].replace("{state}", "on").replace("{outlet}", "0"))
    assert multi == {"switches": [{"switch": "on", "outlet": 0}]}
    assert isinstance(multi["switches"][0]["outlet"], int)
    startup = SPEC["commands"]["stock_startup"]
    assert set(startup["parameters"]["startup"]["values"]) == {"on", "off", "stay"}
    pulse = SPEC["commands"]["stock_pulse"]["parameters"]["pulse_width"]
    assert (pulse["min"], pulse["max"], pulse["unit"]) == (500, 36000000, "ms")
    assert SPEC["commands"]["stock_get_state"]["path"] == "/zeroconf/getState"
    assert "not universal" in DETAILS["commands"]["getState"]


def test_safety_reset_credential_and_ota_boundaries():
    assert SPEC["device"]["integration"] == "identify_only"
    assert SPEC["device"]["testing"]["status"] == "untested"
    for name in ("stock_switch_on", "stock_switch_off", "stock_switches_set", "stock_startup", "stock_pulse", "diy_switch_on", "diy_switch_off", "diy_ota_unlock", "diy_ota_flash"):
        assert SPEC["commands"][name]["advanced"] is True, name
        assert SPEC["commands"][name]["advanced_reason"]
    reset = SPEC["device"]["setup"]["factory_reset"]["procedures"][0]
    assert reset["hold_seconds"] == 5
    assert reset["applies_to"] == ["BASICR2", "RFR2"]
    assert reset["verified"] is False and reset["basis"]
    ap = DETAILS["setup_ap"]
    assert ap["address"] == "10.10.7.1"
    assert "not universal recovery" in ap["credential_boundary"]
    rejoin = SPEC["device"]["setup"]["rejoin"]
    assert rejoin["in_place_supported"] is False
    assert rejoin["requires_factory_reset"] is True
    assert rejoin["stock"] == {
        "in_place_supported": False,
        "requires_factory_reset": True,
        "procedure": rejoin["stock"]["procedure"],
    }
    assert rejoin["diy"]["in_place_supported"] is True
    assert rejoin["diy"]["requires_factory_reset"] is False
    assert SPEC["remaining_unknowns"]


def decode_documented_plaintext(data: bytes) -> dict:
    """Tolerate only the reported trailing 0x02 firmware-padding quirk."""
    return json.loads(data.rstrip(b"\x02"))


def test_cbc_decode_is_not_authenticated_and_cleanup_is_exact():
    vector = DETAILS["stock_crypto"]["test_vector"]
    assert decrypt_stock(vector["ciphertext_base64"], vector["devicekey"], vector["iv_base64"]) == {"switch": "on"}
    assert "never sender authenticity or message integrity" in DETAILS["stock_crypto"]["ciphertext"]
    assert "only those exact trailing 0x02 bytes" in DETAILS["commands"]["response_quirks"][-1]

    assert decode_documented_plaintext(b'{"switch":"on"}\x02\x02') == {"switch": "on"}
    for malformed in (
        b'{"switch":"on"}\x00',
        b'{"switch":"on"}\x03',
        b'{"switch":"on"}\x02\x00',
        b'{"switch":"on"}\x02garbage',
    ):
        with pytest.raises(json.JSONDecodeError):
            decode_documented_plaintext(malformed)
