"""Synthetic Remootio API-v3 crypto/session tests; no network or actuation."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import shutil
import subprocess

SECRET = bytes(range(32))
AUTH = bytes(range(32, 64))
SESSION = bytes(range(64, 96))
IV = bytes(range(16))
PLAINTEXT = b'{"action":{"type":"QUERY","id":42}}'
PAYLOAD = "sg5Om4B3mVoggnU+mDxKYCFq96dz3GJGD6tHD1LxgRk338M9ZDOMS5oS9j0Irt9Y"
MAC = "eIrTgACvnou/sHiPaiY6SD+Hk6ZR9aklfgwWtl07WpE="
FRAME = (
    '{"type":"ENCRYPTED","data":{"iv":"AAECAwQFBgcICQoLDA0ODw==",'
    f'"payload":"{PAYLOAD}"'
    f'}},"mac":"{MAC}"'
    "}"
)
OPENSSL = shutil.which("openssl")


def aes_cbc(data: bytes, key: bytes, iv: bytes, decrypt: bool = False) -> bytes:
    assert OPENSSL, "OpenSSL is required for the spec's named AES equivalent"
    command = [OPENSSL, "enc", "-aes-256-cbc", "-nopad", "-K", key.hex(), "-iv", iv.hex()]
    if decrypt:
        command.append("-d")
    result = subprocess.run(command, input=data, capture_output=True, check=False)
    if result.returncode:
        raise ValueError("AES-CBC operation failed")
    return result.stdout


def pkcs7_pad(data: bytes) -> bytes:
    count = 16 - len(data) % 16
    return data + bytes((count,)) * count


def pkcs7_unpad(data: bytes) -> bytes:
    if not data or len(data) % 16:
        raise ValueError("invalid padded length")
    count = data[-1]
    if not 1 <= count <= 16 or data[-count:] != bytes((count,)) * count:
        raise ValueError("invalid PKCS7 padding")
    return data[:-count]


def data_mac(iv64: str, payload64: str) -> str:
    exact = json.dumps({"iv": iv64, "payload": payload64}, separators=(",", ":"))
    return base64.b64encode(hmac.new(AUTH, exact.encode(), hashlib.sha256).digest()).decode()


def encrypt_inner(plaintext: bytes, key: bytes = SESSION) -> dict:
    ciphertext = aes_cbc(pkcs7_pad(plaintext), key, IV)
    iv64 = base64.b64encode(IV).decode()
    payload64 = base64.b64encode(ciphertext).decode()
    return {
        "type": "ENCRYPTED",
        "data": {"iv": iv64, "payload": payload64},
        "mac": data_mac(iv64, payload64),
    }


def decode_frame(text: str, key: bytes = SESSION) -> dict:
    outer = json.loads(text)
    if outer.get("type") != "ENCRYPTED":
        raise ValueError("not an encrypted frame")
    data = outer["data"]
    iv64 = data["iv"]
    payload64 = data["payload"]
    try:
        iv = base64.b64decode(iv64, validate=True)
        ciphertext = base64.b64decode(payload64, validate=True)
        received_mac = base64.b64decode(outer["mac"], validate=True)
    except Exception as error:
        raise ValueError("invalid base64") from error
    if len(iv) != 16 or len(received_mac) != 32 or not ciphertext or len(ciphertext) % 16:
        raise ValueError("invalid encrypted field length")
    expected_mac = base64.b64decode(data_mac(iv64, payload64))
    if not hmac.compare_digest(received_mac, expected_mac):
        raise ValueError("MAC mismatch")
    plaintext = pkcs7_unpad(aes_cbc(ciphertext, key, iv, decrypt=True))
    return json.loads(plaintext.decode("latin-1"))


def next_action_id(last: int) -> int:
    return (last + 1) % 0x7FFFFFFF


def require_next_action_id(last: int, candidate: int) -> int:
    expected = next_action_id(last)
    if candidate != expected:
        raise ValueError("reused or out-of-order action id")
    return candidate


def test_synthetic_query_vector_reproduction() -> None:
    frame = encrypt_inner(PLAINTEXT)
    assert frame["data"]["iv"] == "AAECAwQFBgcICQoLDA0ODw=="
    assert frame["data"]["payload"] == PAYLOAD
    assert frame["mac"] == MAC
    assert json.dumps(frame, separators=(",", ":")) == FRAME
    assert base64.b64decode("QEFCQ0RFRkdISUpLTE1OT1BRUlNUVVZXWFlaW1xdXl8=") == SESSION
    assert bytes.fromhex(SECRET.hex()) == SECRET


def test_decrypt_validate_and_fragmented_json() -> None:
    for fragments in ((FRAME,), tuple(FRAME[index : index + 7] for index in range(0, len(FRAME), 7))):
        decoded = decode_frame("".join(fragments))
        assert decoded == {"action": {"type": "QUERY", "id": 42}}


def test_mac_tampering_and_malformed_envelopes_are_rejected() -> None:
    tampered = json.loads(FRAME)
    tampered["data"]["payload"] = tampered["data"]["payload"][:-2] + "=="
    try:
        decode_frame(json.dumps(tampered, separators=(",", ":")))
    except (ValueError, KeyError, json.JSONDecodeError):
        pass
    else:
        raise AssertionError("tampered payload accepted")
    for mutate in (
        lambda frame: frame["data"].update(iv="not base64"),
        lambda frame: frame["data"].update(iv=base64.b64encode(b"short").decode()),
        lambda frame: frame.update(mac=base64.b64encode(b"short").decode()),
        lambda frame: frame["data"].update(payload="AA=="),
    ):
        candidate = json.loads(FRAME)
        mutate(candidate)
        try:
            decode_frame(json.dumps(candidate, separators=(",", ":")))
        except (ValueError, KeyError, json.JSONDecodeError):
            pass
        else:
            raise AssertionError("malformed envelope accepted")


def test_invalid_padding_is_rejected_even_with_valid_mac() -> None:
    padded = pkcs7_pad(PLAINTEXT)
    bad_padded = padded[:-1] + b"\x00"
    ciphertext = aes_cbc(bad_padded, SESSION, IV)
    iv64 = base64.b64encode(IV).decode()
    payload64 = base64.b64encode(ciphertext).decode()
    frame = {
        "type": "ENCRYPTED",
        "data": {"iv": iv64, "payload": payload64},
        "mac": data_mac(iv64, payload64),
    }
    try:
        decode_frame(json.dumps(frame, separators=(",", ":")))
    except ValueError as error:
        assert "padding" in str(error)
    else:
        raise AssertionError("invalid padding accepted")


def test_action_id_increment_wrap_and_replay_rejection() -> None:
    assert next_action_id(41) == 42
    assert next_action_id(0x7FFFFFFE) == 0
    assert require_next_action_id(41, 42) == 42
    for last, candidate in ((42, 42), (41, 43), (0x7FFFFFFE, 0x7FFFFFFF)):
        try:
            require_next_action_id(last, candidate)
        except ValueError:
            pass
        else:
            raise AssertionError("out-of-order action accepted")


def test_truncated_json_never_yields_an_action() -> None:
    try:
        decode_frame(FRAME[:-1])
    except json.JSONDecodeError:
        pass
    else:
        raise AssertionError("truncated JSON accepted")
