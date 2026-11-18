"""Independent standard-library vectors for FC SmartHome BLE.

PyYAML only loads the spec. FC/FD framing, XORs, record parsing and sequence
handling are transcribed without repository/community imports. OpenSSL supplies
an independent AES implementation; every key and identity is invented.
"""

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
SPEC = yaml.safe_load(
    (ROOT / "device-specs" / "devices" / "fc-smarthome-lock.yaml").read_text(
        encoding="utf-8"
    )
)
DETAILS = SPEC["protocol_details"]


def _hex(value):
    return bytes.fromhex(value)


def _aes_ecb(key, data, *, decrypt=False):
    if shutil.which("openssl") is None:
        pytest.skip("openssl binary not available")
    command = ["openssl", "enc", "-aes-128-ecb", "-K", key.hex(), "-nopad"]
    if decrypt:
        command.append("-d")
    return subprocess.run(command, input=data, capture_output=True, check=True).stdout


def _inner_xor(inner, *, android=False):
    length = int.from_bytes(inner[:2], "little")
    checksum = (length & 0xFF) ^ (length >> 8) ^ inner[6] ^ inner[7]
    for byte in inner[8:-1]:
        checksum ^= byte
    if android:
        for byte in inner[2:6]:
            checksum ^= byte
    return checksum & 0xFF


def _build_inner(sequence, category, command, data=b"", *, version=2, android=False):
    length = len(data) + (9 if version == 2 else 8)
    inner = length.to_bytes(2, "little") + sequence.to_bytes(4, "little")
    inner += bytes([category, command]) + data
    if version == 2:
        inner += b"\x00"
        inner = inner[:-1] + bytes([_inner_xor(inner, android=android)])
    return inner


def _build_frame(key, inner, *, version, pid):
    encrypted = _aes_ecb(key, inner + bytes((-len(inner)) % 16))
    total = 6 + len(encrypted)
    checksum = pid ^ (total & 0xFF) ^ (total >> 8)
    for byte in encrypted:
        checksum ^= byte
    start = 0xFD if version == 2 else 0xFC
    return bytes([start, pid]) + total.to_bytes(2, "little") + encrypted + bytes([checksum, 0xFE])


def _parse_inner(plaintext, *, version):
    minimum = 9 if version == 2 else 8
    if len(plaintext) < minimum or len(plaintext) % 16:
        raise ValueError("bad decrypted block length")
    inner_length = int.from_bytes(plaintext[:2], "little")
    if inner_length < minimum or inner_length > len(plaintext):
        raise ValueError("bad inner length")
    if any(plaintext[inner_length:]):
        raise ValueError("nonzero zero-fill")
    sequence = int.from_bytes(plaintext[2:6], "little")
    category, command = plaintext[6:8]
    data_end = inner_length - 1 if version == 2 else inner_length
    data = plaintext[8:data_end]
    variant = "none"
    if version == 2:
        inner = plaintext[:inner_length]
        if inner[-1] == _inner_xor(inner):
            variant = "normal"
        elif category == 0xF0 and command == 0x30 and inner[-1] == _inner_xor(inner, android=True):
            variant = "android"
        else:
            raise ValueError("bad inner XOR")
    return {
        "sequence": sequence,
        "category": category,
        "command": command,
        "data": data,
        "xor_variant": variant,
    }


def _parse_frames(chunks, key):
    buffer = bytearray()
    messages = []
    errors = 0
    for chunk in chunks:
        buffer.extend(chunk)
        while True:
            start = next((index for index, byte in enumerate(buffer) if byte in (0xFC, 0xFD)), None)
            if start is None:
                buffer.clear()
                break
            del buffer[:start]
            if len(buffer) < 6:
                break
            total = int.from_bytes(buffer[2:4], "little")
            if total < 22 or total > 1024 or (total - 6) % 16:
                del buffer[0]
                errors += 1
                continue
            if len(buffer) < total:
                break
            frame = bytes(buffer[:total])
            del buffer[:total]
            if frame[-1] != 0xFE:
                errors += 1
                continue
            encrypted = frame[4:-2]
            checksum = frame[1] ^ frame[2] ^ frame[3]
            for byte in encrypted:
                checksum ^= byte
            if checksum != frame[-2]:
                errors += 1
                continue
            try:
                plaintext = _aes_ecb(key, encrypted, decrypt=True)
                message = _parse_inner(plaintext, version=2 if frame[0] == 0xFD else 1)
            except ValueError:
                errors += 1
                continue
            message["pid"] = frame[1]
            messages.append(message)
    return messages, bytes(buffer), errors


def _parse_handshake_response(data):
    if not data:
        raise ValueError("empty response")
    if data[0] not in (0, 0xF1):
        raise ValueError("identity rejected")
    if len(data) < 57:
        raise ValueError("short response")
    try:
        def text(start, end):
            return data[start:end].decode("ascii").strip("\x00 ")

        return {
            "result": data[0],
            "session_key": data[1:17],
            "mac_text": text(17, 29),
            "protocol_version": text(29, 32),
            "model": text(32, 40),
            "firmware": text(40, 55),
            "wake_source": int.from_bytes(data[55:57], "big"),
            "fingerprint_module_version": text(57, 72) if len(data) >= 72 else "",
        }
    except UnicodeDecodeError as error:
        raise ValueError("invalid response text") from error


def _parse_users(data):
    if not data or data[0] != 0:
        raise ValueError("bad user status")
    raw = data[1:]
    if len(raw) % 22:
        raise ValueError("partial user record")
    users = []
    for offset in range(0, len(raw), 22):
        record = raw[offset : offset + 22]
        users.append(
            {
                "user_id": int.from_bytes(record[0:2], "little"),
                "enabled": record[2] == 1,
                "user_type": record[3],
                "attributes": record[4],
                "start_time_raw": int.from_bytes(record[5:9], "little"),
                "end_time_raw": int.from_bytes(record[9:13], "little"),
                "undecoded": record[13:22],
            }
        )
    return users


def _parse_history(data):
    if not data or data[0] != 0:
        raise ValueError("bad history status")
    raw = data[1:]
    size = 9 if len(raw) % 9 == 0 and len(raw) <= 54 else 8
    if len(raw) % size:
        raise ValueError("partial history record")
    records = []
    for offset in range(0, len(raw), size):
        record = raw[offset : offset + size]
        records.append(
            {
                "timestamp_raw": int.from_bytes(record[:4], "little"),
                "model_value_1": record[4],
                "model_value_2": record[5],
                "record_type": record[6],
                "user_id": int.from_bytes(record[7:9], "little") if size == 9 else record[7],
            }
        )
    return records


def _next_sequence(response_sequence):
    return (response_sequence + 1) & 0xFFFFFFFF


def test_frame_vectors_rebuild_from_independent_rules():
    vectors = DETAILS["frame_test_vectors"]
    key = _hex(vectors["initial_key_hex"])
    for vector in vectors["vectors"]:
        inner = _hex(vector["inner_hex"])
        expected = _hex(vector["outer_frame_hex"])
        assert _build_frame(key, inner, version=vector["version"], pid=vector["pid"]) == expected
        messages, remaining, errors = _parse_frames([expected], key)
        assert remaining == b"" and errors == 0 and len(messages) == 1
        message = messages[0]
        assert message["sequence"] == vector["expected"]["sequence"]
        assert message["category"] == vector["expected"]["category"]
        assert message["command"] == vector["expected"]["command"]
        if "data_length" in vector["expected"]:
            assert len(message["data"]) == vector["expected"]["data_length"]
        else:
            assert message["data"] == _hex(vector["expected"].get("data_hex", ""))
        assert message["pid"] == vector["pid"]


def test_inner_builders_normal_android_v1_and_handshake_payload():
    assert _build_inner(2, 4, 1, version=1) == bytes.fromhex("08 00 02 00 00 00 04 01")
    normal = _build_inner(2, 0xF0, 0x30)
    android = _build_inner(2, 0xF0, 0x30, android=True)
    assert normal[-1] == 0xC9 and android[-1] == 0xCB
    identity = DETAILS["frame_test_vectors"]["vectors"][3]
    data = identity["identity_ascii"].encode("ascii") + bytes([26, 11, 18, 12, 34, 56, 2])
    assert len(data) == 39
    assert _build_inner(1, 2, 8, data, version=1) == _hex(identity["inner_hex"])
    assert _build_inner(1, 2, 8, data, version=1)[0] == 8 + 39


def test_fragmentation_noise_glue_and_bad_frames_fail_closed():
    key = _hex(DETAILS["frame_test_vectors"]["initial_key_hex"])
    first = _hex(DETAILS["frame_test_vectors"]["vectors"][0]["outer_frame_hex"])
    second = _hex(DETAILS["frame_test_vectors"]["vectors"][1]["outer_frame_hex"])
    for size in (1, 3, 7, 20):
        chunks = [first[index : index + size] for index in range(0, len(first), size)]
        messages, remaining, errors = _parse_frames(chunks, key)
        assert len(messages) == 1 and remaining == b"" and errors == 0
    messages, remaining, errors = _parse_frames([b"noise" + first + second], key)
    assert len(messages) == 2 and remaining == b"" and errors == 0
    messages, remaining, errors = _parse_frames([first[:-1]], key)
    assert messages == [] and remaining == first[:-1] and errors == 0
    for index in (-2, -1):
        bad = bytearray(first)
        bad[index] ^= 1
        messages, _, errors = _parse_frames([bytes(bad)], key)
        assert messages == [] and errors == 1
    bad_length = bytearray(first)
    bad_length[2:4] = (7).to_bytes(2, "little")
    messages, _, errors = _parse_frames([bytes(bad_length)], key)
    assert messages == [] and errors == 1


def test_inner_xor_padding_and_android_scope_validation():
    key = _hex(DETAILS["frame_test_vectors"]["initial_key_hex"])
    good = _build_inner(2, 4, 1, version=2)
    malformed = (
        good[:-1] + bytes([good[-1] ^ 1]),
        good + b"\x01" + bytes(15),
        _build_inner(2, 4, 1, version=2, android=True),
    )
    for inner in malformed:
        frame = _build_frame(key, inner, version=2, pid=0)
        messages, _, errors = _parse_frames([frame], key)
        assert messages == [] and errors == 1
    heartbeat = _build_inner(2, 0xF0, 0x30, version=2, android=True)
    messages, _, errors = _parse_frames(
        [_build_frame(key, heartbeat, version=2, pid=0xFF)], key
    )
    assert len(messages) == 1 and errors == 0
    assert messages[0]["xor_variant"] == "android"
    with pytest.raises(ValueError, match="bad inner length"):
        _parse_inner(bytes.fromhex("ff ff") + bytes(14), version=2)


def test_handshake_response_session_key_model_firmware_and_wake():
    vector = DETAILS["handshake_response_vector"]
    parsed = _parse_handshake_response(_hex(vector["data_hex"]))
    expected = vector["expected"]
    assert parsed["result"] == expected["result"]
    assert parsed["session_key"].hex() == expected["session_key_hex"]
    assert parsed["mac_text"] == expected["mac_text"]
    assert parsed["protocol_version"] == expected["protocol_version"]
    assert parsed["model"] == expected["model"]
    assert parsed["firmware"] == expected["firmware"]
    assert parsed["wake_source"] == expected["wake_source"]
    assert parsed["fingerprint_module_version"] == expected["fingerprint_module_version"]
    accepted_f1 = bytearray(_hex(vector["data_hex"]))
    accepted_f1[0] = 0xF1
    assert _parse_handshake_response(bytes(accepted_f1))["result"] == 0xF1
    rejected = bytearray(accepted_f1)
    rejected[0] = 1
    with pytest.raises(ValueError, match="rejected"):
        _parse_handshake_response(bytes(rejected))
    with pytest.raises(ValueError, match="short"):
        _parse_handshake_response(bytes(56))


def test_users_history_and_partial_record_rejection():
    users = DETAILS["read_only_queries"]["users"]
    parsed = _parse_users(b"\x00" + _hex(users["synthetic_record_hex"]))
    expected = users["synthetic_expected"]
    assert len(parsed) == 1
    for key in ("user_id", "enabled", "user_type", "attributes", "start_time_raw", "end_time_raw"):
        assert parsed[0][key] == expected[key]
    with pytest.raises(ValueError, match="partial user"):
        _parse_users(b"\x00" + bytes(21))
    with pytest.raises(ValueError, match="status"):
        _parse_users(b"\x01" + bytes(22))

    history = DETAILS["read_only_queries"]["history"]
    for name in ("eight_byte_example", "nine_byte_example"):
        vector = history[name]
        records = _parse_history(b"\x00" + _hex(vector["raw_hex"]))
        assert records == [vector["expected"]]
    with pytest.raises(ValueError, match="partial history"):
        _parse_history(b"\x00" + bytes(10))


def test_response_sequence_and_pagination_rules():
    assert _next_sequence(1) == 2
    assert _next_sequence(5) == 6
    assert _next_sequence(0xFFFFFFFF) == 0
    pids = iter((2, 1, 0))
    requests = 0
    while True:
        pid = next(pids)
        requests += 1
        if pid == 0:
            break
    assert requests == 3
    sequence = DETAILS["inner_message"]["session_sequencing"]
    assert sequence["first"].startswith("Sequence 1")
    assert "response.sequence + 1" in sequence["after_response"]
    assert sequence["failed_handshake"].startswith("Reconnect")


def test_documentary_unlock_vector_and_stale_opcode_rejection():
    unlock = DETAILS["advanced_unlock_documentary"]
    key = _hex(DETAILS["frame_test_vectors"]["initial_key_hex"])
    inner = _hex(unlock["synthetic_vector"]["inner_hex"])
    assert inner == _build_inner(6, 4, 0x10, b"\x01")
    assert _build_frame(key, inner, version=2, pid=0) == _hex(
        unlock["synthetic_vector"]["outer_frame_hex"]
    )
    assert unlock["advanced"] is True and unlock["attended"] is True
    assert unlock["generic_binding"] is False
    assert unlock["stale_target_correction"]["action"].startswith("DO NOT SEND")
    assert not SPEC.get("entities") and not SPEC.get("commands")
    assert SPEC["device"]["integration"] == "identify_only"
    assert SPEC["device"]["testing"]["status"] == "untested"
