"""Independent standard-library vectors for Wyze Lock Bolt v1.

PyYAML only loads the spec. CRC, framing, TLVs and validation are transcribed
without repository/community imports. OpenSSL is invoked as an independent AES
implementation; no crypto package or real credential is used.
"""

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
SPEC = yaml.safe_load(
    (ROOT / "device-specs" / "devices" / "wyze-lock-bolt.yaml").read_text(
        encoding="utf-8"
    )
)
DETAILS = SPEC["protocol_details"]


def _hex(value):
    return bytes.fromhex(value)


def _crc16_arc(data):
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc & 0xFFFF


def _pack_l1(flags, sequence, payload):
    return (
        b"\xab"
        + bytes([flags])
        + len(payload).to_bytes(2, "big")
        + _crc16_arc(payload).to_bytes(2, "big")
        + sequence.to_bytes(2, "big")
        + payload
    )


def _extract_l1(buffer):
    buffer = bytearray(buffer)
    frames = []
    errors = 0
    while buffer:
        try:
            start = buffer.index(0xAB)
        except ValueError:
            buffer.clear()
            break
        del buffer[:start]
        if len(buffer) < 8:
            break
        length = int.from_bytes(buffer[2:4], "big")
        total = 8 + length
        if len(buffer) < total:
            break
        frame = bytes(buffer[:total])
        del buffer[:total]
        payload = frame[8:]
        if _crc16_arc(payload) != int.from_bytes(frame[4:6], "big"):
            errors += 1
            continue
        frames.append((frame[1], int.from_bytes(frame[6:8], "big"), payload))
    return frames, bytes(buffer), errors


def _parse_l2(payload):
    if len(payload) < 2:
        raise ValueError("short L2 header")
    command, flags = payload[:2]
    version = flags >> 4
    if version == 0:
        key_width = 1
    elif version == 7:
        key_width = 2
    else:
        raise ValueError("unsupported L2 version")
    fields = {}
    position = 2
    while position < len(payload):
        header_width = key_width + 2
        if position + header_width > len(payload):
            raise ValueError("truncated TLV header")
        key = int.from_bytes(payload[position : position + key_width], "big")
        length = int.from_bytes(
            payload[position + key_width : position + header_width], "big"
        )
        position += header_width
        if key in fields:
            raise ValueError("duplicate TLV key")
        if position + length > len(payload):
            raise ValueError("truncated TLV value")
        fields[key] = payload[position : position + length]
        position += length
    return command, flags, fields


def _aes_ecb(key, data, *, decrypt=False):
    if shutil.which("openssl") is None:
        pytest.skip("openssl binary not available")
    command = ["openssl", "enc", "-aes-128-ecb", "-K", key.hex(), "-nopad"]
    if decrypt:
        command.append("-d")
    return subprocess.run(command, input=data, capture_output=True, check=True).stdout


def _decode_status(ciphertext, key, *, battery=False):
    if len(ciphertext) != 16:
        raise ValueError("status must be one block")
    if len(key) != 16:
        raise ValueError("status key must be 16 bytes")
    plaintext = _aes_ecb(key, ciphertext, decrypt=True)
    if plaintext[11:16] != b"loock":
        raise ValueError("loock marker missing")
    if plaintext[5:11] != bytes(6):
        raise ValueError("zero padding missing")
    payload = plaintext[0]
    if battery and payload != 0xFF and not 0 <= payload <= 100:
        raise ValueError("invalid battery percentage")
    timestamp = int.from_bytes(plaintext[1:5], "big")
    return payload, timestamp


def _build_legacy(operation, vector):
    token = vector["ble_token_ascii"].encode("ascii")
    if len(token) != 32:
        raise ValueError("token must have 32 ASCII characters")
    challenge = _hex(vector["challenge_hex"])
    if len(challenge) != 16:
        raise ValueError("challenge must be 16 bytes")
    encrypted = _aes_ecb(token[16:], challenge)
    first = {"unlock": 1, "lock": 2}[operation]
    magic = bytes([first]) + bytes(10) + b"loock"
    response = bytes(left ^ right for left, right in zip(encrypted, magic, strict=True))
    ble_id = int(vector["ble_key_id"], 0)
    l2 = (
        bytes.fromhex("04 00 05 00 02")
        + ble_id.to_bytes(2, "big")
        + bytes.fromhex("04 00 10")
        + response
        + bytes.fromhex("ad 00 01 00 f4 00 01 01 f7 00 01 01")
    )
    return response, _pack_l1(0, 2, l2)


def test_crc16_arc_known_answer_and_empty_ack():
    crc = DETAILS["l1_transport"]["crc"]
    assert _crc16_arc(b"123456789") == int(crc["known_answer"]["output"], 0) == 0xBB3D
    assert _crc16_arc(b"") == 0
    assert _pack_l1(0x08, 1, b"") == bytes.fromhex("ab 08 00 00 00 00 00 01")


def test_l1_challenge_request_and_response_vectors():
    request = DETAILS["l2_payload"]["challenge_request"]
    command, flags, fields = _parse_l2(_hex(request["l2_hex"]))
    assert (command, flags, fields) == (0x91, 0, {0x0A: b"\x27"})
    assert _pack_l1(0, 1, _hex(request["l2_hex"])) == _hex(request["l1_hex"])

    response = DETAILS["l2_payload"]["challenge_response"]
    command, flags, fields = _parse_l2(_hex(response["synthetic_l2_hex"]))
    assert command == 0x86 and flags == 0
    assert fields[0xD2] == bytes(range(16))
    assert _pack_l1(0x40, 2, _hex(response["synthetic_l2_hex"])) == _hex(
        response["synthetic_l1_hex"]
    )


def test_l1_fragmentation_noise_bad_crc_and_truncation():
    good = _hex(DETAILS["l2_payload"]["challenge_request"]["l1_hex"])
    other = _pack_l1(0x08, 9, b"")
    stream = b"noise" + good[:5]
    frames, remaining, errors = _extract_l1(stream)
    assert frames == [] and errors == 0
    assert remaining == good[:5]

    frames, remaining, errors = _extract_l1(remaining + good[5:] + other)
    assert len(frames) == 2 and errors == 0 and remaining == b""
    assert frames[0][:2] == (0, 1)
    assert frames[1][:2] == (8, 9)

    bad = bytearray(good)
    bad[4] ^= 1
    frames, remaining, errors = _extract_l1(bytes(bad) + other)
    assert frames == [(8, 9, b"")] and errors == 1 and remaining == b""

    frames, remaining, errors = _extract_l1(good[:-1])
    assert frames == [] and errors == 0 and remaining == good[:-1]
    with pytest.raises(ValueError):
        _parse_l2(good[8:9])


def test_legacy_and_id2_tlv_layouts_and_malformed_inputs():
    example = DETAILS["l2_payload"]["id2_syntax_example"]
    command, flags, fields = _parse_l2(_hex(example["l2_hex"]))
    assert (command, flags) == (0x91, 0x70)
    assert fields == {0x000A: b"\x27"}
    for payload in (
        b"\x91",
        b"\x91\x10",
        b"\x91\x00\x0a",
        b"\x91\x00\x0a\x00\x02\x27",
        b"\x91\x00\x0a\x00\x01\x27\x0a\x00\x01\x28",
        b"\x91\x70\x00\x0a\x00",
        b"\x91\x70\x00\x0a\x00\x02\x27",
    ):
        with pytest.raises(ValueError):
            _parse_l2(payload)


def test_legacy_unlock_and_lock_known_answers_without_actuation():
    vector = DETAILS["legacy_actuation"]["synthetic_vector"]
    for operation in ("unlock", "lock"):
        response, frame = _build_legacy(operation, vector)
        assert response == _hex(vector[f"{operation}_response_hex"])
        assert frame == _hex(vector[f"{operation}_l1_hex"])
        command, flags, fields = _parse_l2(frame[8:])
        assert command == 0x04 and flags == 0
        assert fields[0x05] == bytes.fromhex("12 34")
        assert fields[0x04] == response
        assert fields[0xAD] == b"\x00"
        assert fields[0xF4] == fields[0xF7] == b"\x01"
    unlock = _build_legacy("unlock", vector)[0]
    lock = _build_legacy("lock", vector)[0]
    assert bytes(a ^ b for a, b in zip(unlock, lock, strict=True)) == bytes.fromhex(
        "03 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00"
    )


def test_encrypted_status_marker_padding_timestamp_and_sentinel():
    vectors = DETAILS["status_test_vectors"]
    key = vectors["state_key_ascii"].encode("ascii")
    assert vectors["device_uuid"].encode("ascii")[-16:] == key
    for vector in vectors["vectors"]:
        ciphertext = _hex(vector["ciphertext_hex"])
        plaintext = _aes_ecb(key, ciphertext, decrypt=True)
        assert plaintext == _hex(vector["plaintext_hex"])
        if vector["name"] == "nonzero padding must fail":
            with pytest.raises(ValueError, match="zero padding"):
                _decode_status(ciphertext, key)
            continue
        payload, timestamp = _decode_status(ciphertext, key)
        expected = vector["expected"]
        assert payload == expected["payload"]
        assert timestamp == expected["timestamp"]
        if "battery_percent" in expected:
            assert _decode_status(ciphertext, key, battery=True)[0] == expected["battery_percent"]
        if expected.get("state") == "locked":
            assert payload == 1
        if expected.get("state") == "unknown":
            assert payload == 0xFF


def test_status_wrong_key_bad_length_padding_and_battery_range_fail_closed():
    vectors = DETAILS["status_test_vectors"]
    locked = next(v for v in vectors["vectors"] if v["name"] == "locked")
    with pytest.raises(ValueError, match="loock marker"):
        _decode_status(_hex(locked["ciphertext_hex"]), vectors["wrong_key_ascii"].encode())
    for malformed in vectors["malformed"]:
        if "input_hex" in malformed:
            with pytest.raises(ValueError, match="one block"):
                _decode_status(_hex(malformed["input_hex"]), b"0123456789abcdef")
    battery = next(v for v in vectors["vectors"] if "battery_percent" in v["expected"])
    invalid = bytearray(_hex(battery["plaintext_hex"]))
    invalid[0] = 101
    with pytest.raises(ValueError, match="battery percentage"):
        _decode_status(_aes_ecb(b"0123456789abcdef", bytes(invalid)), b"0123456789abcdef", battery=True)


def test_manual_identify_only_scope_and_no_generic_actions():
    device = SPEC["device"]
    assert device["integration"] == "identify_only"
    assert device["discovery"].get("methods") is None
    assert "none" in device["discovery"]
    assert not SPEC.get("entities")
    assert not SPEC.get("commands")
    assert len(device["variants"]) == 1
    assert device["variants"][0]["model"] == "WLCKB1"
    assert "v2" in device["notes"]
    for service in SPEC["services"]:
        for characteristic in service.get("characteristics", []):
            assert "commands" not in characteristic
    assert DETAILS["legacy_actuation"]["advanced"] is True
    assert DETAILS["legacy_actuation"]["attended"] is True
    assert DETAILS["legacy_actuation"]["generic_binding"] is False
    assert "not implemented" in DETAILS["id2_unresolved"]["status"]
