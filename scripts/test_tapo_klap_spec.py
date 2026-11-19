"""Offline Tapo TDP/KLAP/securePassthrough conformance; no device traffic.

AES-CBC is evaluated by the OpenSSL CLI through subprocess, while framing,
hashes, PKCS#7, RSA-1024 arithmetic and session policy use only the standard
library. Every secret is synthetic and no vendor client is imported.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import shutil
import subprocess
import zlib
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
SPEC = yaml.safe_load((ROOT / "device-specs/devices/tplink-tapo-klap.yaml").read_text())
DETAILS = SPEC["protocol_details"]
OPENSSL = shutil.which("openssl")


def aes_cbc(data: bytes, key: bytes, iv: bytes, *, decrypt: bool = False) -> bytes:
    assert OPENSSL, "OpenSSL is required for the independent AES vector check"
    command = [OPENSSL, "enc", "-aes-128-cbc", "-nopad", "-K", key.hex(), "-iv", iv.hex()]
    if decrypt:
        command.append("-d")
    result = subprocess.run(command, input=data, capture_output=True, check=False)
    if result.returncode:
        raise ValueError("AES-CBC failed")
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


def build_tdp(payload: bytes, flags: int, serial: int = 0x01020304) -> bytes:
    header = bytearray(16)
    header[0] = 2
    header[2:4] = (1).to_bytes(2, "big")
    header[4:6] = len(payload).to_bytes(2, "big")
    header[6] = flags
    header[8:12] = serial.to_bytes(4, "big")
    header[12:16] = bytes.fromhex("5a6b7c8d")
    crc = zlib.crc32(header + payload) & 0xFFFFFFFF
    header[12:16] = crc.to_bytes(4, "big")
    return bytes(header) + payload


def auth_hash(version: str, username: bytes, password: bytes) -> bytes:
    if version == "v1":
        return hashlib.md5(hashlib.md5(username).digest() + hashlib.md5(password).digest()).digest()
    return hashlib.sha256(hashlib.sha1(username).digest() + hashlib.sha1(password).digest()).digest()


def proofs(version: str, local: bytes, remote: bytes, auth: bytes) -> tuple[bytes, bytes]:
    if version == "v1":
        return hashlib.sha256(local + auth).digest(), hashlib.sha256(remote + auth).digest()
    return (
        hashlib.sha256(local + remote + auth).digest(),
        hashlib.sha256(remote + local + auth).digest(),
    )


def derive_session(local: bytes, remote: bytes, auth: bytes) -> dict:
    full_iv = hashlib.sha256(b"iv" + local + remote + auth).digest()
    initial = int.from_bytes(full_iv[12:16], "big") & 0x7FFFFFFF
    return {
        "key": hashlib.sha256(b"lsk" + local + remote + auth).digest()[:16],
        "sig": hashlib.sha256(b"ldk" + local + remote + auth).digest()[:28],
        "prefix": full_iv[:12],
        "initial": initial,
    }


def encrypt_request(session: dict, plaintext: bytes) -> tuple[bytes, int, bytes]:
    seq = session["initial"] + 1
    seq_bytes = seq.to_bytes(4, "big")
    iv = session["prefix"] + seq_bytes
    ciphertext = aes_cbc(pkcs7(plaintext), session["key"], iv)
    signature = hashlib.sha256(session["sig"] + seq_bytes + ciphertext).digest()
    return signature + ciphertext, seq, iv


def decrypt_response(session: dict, body: bytes, seq: int) -> bytes:
    if len(body) < 48 or len(body[32:]) % 16:
        raise ValueError("invalid KLAP response length")
    seq_bytes = seq.to_bytes(4, "big")
    expected = hashlib.sha256(session["sig"] + seq_bytes + body[32:]).digest()
    if not hmac.compare_digest(body[:32], expected):
        raise ValueError("invalid KLAP signature")
    return pkcs7_strip(aes_cbc(body[32:], session["key"], session["prefix"] + seq_bytes, decrypt=True))


class Http403(Exception):
    pass


def request_with_403_recovery(handshake, send):
    """The spec's bounded recovery: fresh handshake, one retry, then fail."""
    handshake()
    try:
        return send()
    except Http403:
        handshake()
        return send()


def test_tdp_broadcast_and_unicast_vectors_rebuild_from_payload():
    vectors = DETAILS["tdp"]["test_vectors"]
    for key, flags in (("broadcast_packet_hex", 0x11), ("unicast_packet_hex", 0x21)):
        packet = bytes.fromhex(vectors[key])
        assert len(packet) == 16 + int.from_bytes(packet[4:6], "big")
        payload = packet[16:]
        assert json.loads(payload)["params"]["rsa_key"].startswith("-----BEGIN PUBLIC KEY-----\n")
        assert build_tdp(payload, flags) == packet
        placeholder = packet[:12] + bytes.fromhex("5a6b7c8d") + packet[16:]
        assert int.from_bytes(packet[12:16], "big") == zlib.crc32(placeholder) & 0xFFFFFFFF
        assert packet[6] == flags
        assert packet[:2] == b"\x02\x00"
        assert packet[2:4] == b"\x00\x01"
    methods = SPEC["device"]["discovery"]["methods"]
    assert [item["udp_broadcast"]["port"] for item in methods] == [20002, 20004]
    assert all(item["udp_broadcast"]["probe_hex"] == vectors["broadcast_packet_hex"] for item in methods)


@pytest.mark.parametrize("version", ["v1", "v2"])
def test_fixed_seed_handshake_and_session_vectors(version):
    vectors = DETAILS["klap"]["test_vectors"]
    expected = vectors[version]
    username = vectors["username"].encode()
    password = vectors["password"].encode()
    local = bytes.fromhex(vectors["local_seed_hex"])
    remote = bytes.fromhex(vectors["remote_seed_hex"])
    assert len(local) == 16
    auth = auth_hash(version, username, password)
    assert auth.hex() == expected["auth_hash_hex"]
    device_proof, client_proof = proofs(version, local, remote, auth)
    handshake1_response = remote + device_proof
    assert len(handshake1_response) == 48
    assert device_proof.hex() == expected["device_proof_hex"]
    assert client_proof.hex() == expected["client_proof_hex"]
    session = derive_session(local, remote, auth)
    assert session["key"].hex() == expected["key_hex"]
    assert session["sig"].hex() == expected["sig_hex"]
    assert session["prefix"].hex() == expected["iv_prefix_hex"]
    assert session["initial"] == expected["initial_sequence"]
    body, seq, iv = encrypt_request(session, vectors["plaintext_json"].encode())
    assert seq == expected["request_sequence"]
    assert iv.hex() == expected["request_iv_hex"]
    assert body.hex() == expected["request_body_hex"]
    assert decrypt_response(session, body, seq) == vectors["plaintext_json"].encode()
    tampered = bytearray(body)
    tampered[0] ^= 1
    with pytest.raises(ValueError, match="signature"):
        decrypt_response(session, bytes(tampered), seq)


def test_v1_and_v2_hashes_differ_but_all_seed_proofs_are_sha256():
    vectors = DETAILS["klap"]["test_vectors"]
    for version in ("v1", "v2"):
        assert len(bytes.fromhex(vectors[version]["device_proof_hex"])) == 32
        assert len(bytes.fromhex(vectors[version]["client_proof_hex"])) == 32
    assert vectors["v1"]["auth_hash_hex"] != vectors["v2"]["auth_hash_hex"]
    assert len(bytes.fromhex(vectors["v1"]["auth_hash_hex"])) == 16
    assert len(bytes.fromhex(vectors["v2"]["auth_hash_hex"])) == 32


def test_secure_passthrough_rsa1024_wrap_and_aes_envelope():
    vector = DETAILS["secure_passthrough"]["test_vector"]
    n = int(vector["modulus_hex"], 16)
    e = vector["public_exponent"]
    d = int(vector["private_exponent_hex"], 16)
    assert n.bit_length() == 1024
    session = bytes.fromhex(vector["session_key_iv_hex"])
    assert len(session) == 32
    padding = bytes.fromhex(vector["pkcs1_padding_hex"])
    assert len(padding) == 128 - 3 - len(session)
    assert 0 not in padding
    encoded = b"\x00\x02" + padding + b"\x00" + session
    wrapped = pow(int.from_bytes(encoded, "big"), e, n).to_bytes(128, "big")
    assert base64.b64encode(wrapped).decode() == vector["wrapped_key_base64"]
    decrypted = pow(int.from_bytes(wrapped, "big"), d, n).to_bytes(128, "big")
    assert decrypted == encoded
    assert decrypted[-32:] == session
    ciphertext = aes_cbc(pkcs7(vector["plaintext_json"].encode()), session[:16], session[16:])
    assert base64.b64encode(ciphertext).decode() == vector["secure_request_base64"]
    outer = {
        "method": "securePassthrough",
        "params": {"request": vector["secure_request_base64"]},
    }
    assert json.dumps(outer, separators=(",", ":")) == vector["outer_json"]
    assert pkcs7_strip(aes_cbc(ciphertext, session[:16], session[16:], decrypt=True)).decode() == vector["plaintext_json"]


def test_403_forces_one_new_handshake_and_bounded_retry():
    events = []

    def handshake():
        events.append("handshake")

    def send():
        events.append("send")
        if events.count("send") == 1:
            raise Http403
        return "ok"

    assert request_with_403_recovery(handshake, send) == "ok"
    assert events == ["handshake", "send", "handshake", "send"]

    events.clear()

    def always_403():
        events.append("send")
        raise Http403

    with pytest.raises(Http403):
        request_with_403_recovery(handshake, always_403)
    assert events == ["handshake", "send", "handshake", "send"]


def test_commands_and_lifecycle_keep_documented_safety_boundaries():
    assert SPEC["device"]["integration"] == "identify_only"
    assert SPEC["device"]["testing"]["status"] == "untested"
    for name in ("plug_on", "plug_off"):
        command = SPEC["commands"][name]
        assert command["advanced"] is True
        assert command["advanced_reason"]
        assert command["transport"] == "http"
        assert "never send this plaintext body directly" in command["body_transform"]
        assert command["parameters"]["seq"]["required"] is True
    assert DETAILS["application"]["energy_monitoring"]["exposure"] == "advertised_only"
    assert not any(entity["platform"] == "sensor" for entity in SPEC["entities"])
    setup = SPEC["device"]["setup"]
    assert [item["hold_seconds"] for item in setup["factory_reset"]["procedures"]] == [5, 10]
    assert all(item["verified"] is False and item["basis"] for item in setup["factory_reset"]["procedures"])
    assert setup["rejoin"]["requires_factory_reset"] is False
    assert DETAILS["tpap_reported_appendix"]["verification"] == "reported"
    assert "extra_crypt" in DETAILS["tpap_reported_appendix"]["unresolved"]
    assert SPEC["remaining_unknowns"]


def decode_tdp_response(packet: bytes, serial: int = 0x01020304) -> dict:
    """Header/CRC first, JSON second; the generic binary reader cannot do this."""
    if len(packet) < 16:
        raise ValueError("short TDP datagram")
    if packet[0] != 2 or int.from_bytes(packet[2:4], "big") != 1:
        raise ValueError("unsupported TDP frame")
    if packet[7] not in (0, 1):
        raise ValueError("TDP error result")
    if int.from_bytes(packet[8:12], "big") != serial:
        raise ValueError("TDP serial mismatch")
    payload_length = int.from_bytes(packet[4:6], "big")
    if payload_length != len(packet) - 16:
        raise ValueError("TDP payload length mismatch")
    placeholder = packet[:12] + bytes.fromhex("5a6b7c8d") + packet[16:]
    if int.from_bytes(packet[12:16], "big") != zlib.crc32(placeholder) & 0xFFFFFFFF:
        raise ValueError("TDP CRC mismatch")
    return json.loads(packet[16:])


def der_length(size: int) -> bytes:
    if size < 128:
        return bytes([size])
    encoded = size.to_bytes((size.bit_length() + 7) // 8, "big")
    return bytes([0x80 | len(encoded)]) + encoded


def der(tag: int, content: bytes) -> bytes:
    return bytes([tag]) + der_length(len(content)) + content


def der_integer(value: int) -> bytes:
    encoded = value.to_bytes((value.bit_length() + 7) // 8, "big")
    if encoded[0] & 0x80:
        encoded = b"\x00" + encoded
    return der(2, encoded)


def rsa_public_spki(modulus: int, exponent: int) -> bytes:
    public_key = der(0x30, der_integer(modulus) + der_integer(exponent))
    algorithm = bytes.fromhex("300d06092a864886f70d0101010500")
    return der(0x30, algorithm + der(3, b"\x00" + public_key))


def normalized_session(cookies: dict, now: float) -> tuple[dict, float]:
    session_id = cookies.get("TP_SESSIONID") or cookies.get("SESSIONID")
    if not session_id:
        raise ValueError("missing session cookie")
    timeout = int(cookies.get("TIMEOUT", 86400))
    return {"TP_SESSIONID": session_id}, now + timeout - 1200


class AesAuthError(Exception):
    pass


def aes_request_with_recovery(handshake, login, operation, reconcile=None):
    """AES-only handshake+login recovery, deliberately not the KLAP helper."""
    handshake()
    login()
    try:
        return operation()
    except AesAuthError:
        handshake()
        login()
        if reconcile is None:
            return operation()
        actual = reconcile()
        return operation(actual)


def test_tdp_custom_decoder_and_absent_generic_identity_mapping():
    vectors = DETAILS["tdp"]["test_vectors"]
    for method in SPEC["device"]["discovery"]["methods"]:
        assert "identity_mapping" not in method["udp_broadcast"]
        assert method["udp_broadcast"]["response_format"] == "binary"
    assert "cannot skip this 16-byte header" in DETAILS["tdp"]["custom_handler_limitation"]
    packet = bytes.fromhex(vectors["broadcast_packet_hex"])
    decoded = decode_tdp_response(packet)
    assert decoded["params"]["rsa_key"].startswith("-----BEGIN PUBLIC KEY-----")
    tampered = bytearray(packet)
    tampered[-1] ^= 1
    with pytest.raises(ValueError, match="CRC"):
        decode_tdp_response(bytes(tampered))
    with pytest.raises(ValueError, match="serial"):
        decode_tdp_response(packet, serial=0x01020305)


def test_rsa_handshake_serialization_and_cookie_timeout():
    secure = DETAILS["secure_passthrough"]
    vector = secure["test_vector"]
    spki = rsa_public_spki(int(vector["modulus_hex"], 16), vector["public_exponent"])
    assert len(spki) == 162
    assert base64.b64encode(spki).decode() == vector["public_key_der_base64"]
    pem = (
        "-----BEGIN PUBLIC KEY-----\n"
        + vector["public_key_der_base64"]
        + "\n-----END PUBLIC KEY-----\n"
    )
    assert pem == vector["public_key_pem"]
    body = json.dumps({"method": "handshake", "params": {"key": pem}}, separators=(",", ":"))
    assert body == vector["handshake_json"]
    assert len(body.encode()) == 314
    assert secure["handshake_http"]["vector_content_length"] == len(body.encode())
    headers = secure["handshake_http"]["required_headers"]
    assert headers["Content-Type"] == "application/json"
    assert headers["requestByApp"] == "true"
    assert "500" in headers["Content-Length"]
    assert "chunked" in headers["Content-Length"]
    assert "lv == 2" in secure["login_version_selection"]
    assert "every other advertised value" in secure["login_version_selection"]

    cookie, expiry = normalized_session({"SESSIONID": "synthetic-session", "TIMEOUT": "86400"}, 1000.0)
    assert cookie == {"TP_SESSIONID": "synthetic-session"}
    assert expiry == 1000.0 + 86400 - 1200
    cookie, expiry = normalized_session({"TP_SESSIONID": "preferred", "SESSIONID": "ignored"}, 1000.0)
    assert cookie == {"TP_SESSIONID": "preferred"}
    assert expiry == 1000.0 + 86400 - 1200


def test_aes_auth_recovery_is_independent_of_klap_403_and_reconciles_relay():
    events = []

    def handshake():
        events.append("rsa_handshake")

    def login():
        events.append("login")

    def read():
        events.append("read")
        if events.count("read") == 1:
            raise AesAuthError
        return "ok"

    assert aes_request_with_recovery(handshake, login, read) == "ok"
    assert events == ["rsa_handshake", "login", "read", "rsa_handshake", "login", "read"]
    assert "seed_handshake" not in events
    assert "403" not in events

    def relay_operation():
        attempts = 0

        def operation(actual=None):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise AesAuthError
            if actual is True:
                return "already_on"
            events.append(("set_device_info", True))
            return "written"

        return operation

    events.clear()
    assert aes_request_with_recovery(
        handshake,
        login,
        relay_operation(),
        reconcile=lambda: events.append("get_device_info") or False,
    ) == "written"
    assert events == [
        "rsa_handshake", "login", "rsa_handshake", "login",
        "get_device_info", ("set_device_info", True),
    ]

    events.clear()
    assert aes_request_with_recovery(
        handshake,
        login,
        relay_operation(),
        reconcile=lambda: events.append("get_device_info") or True,
    ) == "already_on"
    assert ("set_device_info", True) not in events
    assert events[-1] == "get_device_info"

    events.clear()
    failures = iter([AesAuthError(), AesAuthError()])

    def always_fails():
        raise next(failures)

    with pytest.raises(AesAuthError):
        aes_request_with_recovery(handshake, login, always_fails)
    assert events == ["rsa_handshake", "login", "rsa_handshake", "login"]


def aes_recovery_action(http_status: int, error_code: int) -> str:
    if http_status != 200:
        return "transport_error"
    if error_code in {9999, 1111, 1100, 1003, -1501, -1005, -40412, -40401, -40413}:
        return "rsa_handshake_and_login_once"
    return "surface_application_error"


def run_coded_aes_recovery(http_status: int, error_code: int, events: list) -> str:
    action = aes_recovery_action(http_status, error_code)
    if action == "rsa_handshake_and_login_once":
        events.append("rsa_handshake")
        events.append("login")
    return action


def test_exact_aes_recovery_codes_and_http_status_both_directions():
    recovery = DETAILS["secure_passthrough"]["recovery"]
    expected = {9999, 1111, 1100, 1003, -1501, -1005, -40412, -40401, -40413}
    assert {int(code) for code in recovery["recovery_codes"]} == expected
    for code in sorted(expected):
        events = []
        assert run_coded_aes_recovery(200, code, events) == "rsa_handshake_and_login_once"
        assert events == ["rsa_handshake", "login"], code

    for code in (-1, -1002, -1301, 1200, 1002, 1112, -1001):
        events = []
        assert run_coded_aes_recovery(200, code, events) == "surface_application_error"
        assert events == [], code

    for status in (400, 401, 403, 500):
        events = []
        assert run_coded_aes_recovery(status, 9999, events) == "transport_error"
        assert events == [], status
    assert "Any non-200 response is a transport failure" in recovery["http_statuses"]["non_200"]
    assert "HTTP 400" in recovery["http_statuses"]["non_200"]
    assert "no RSA handshake/login" in recovery["non_recovery"]
