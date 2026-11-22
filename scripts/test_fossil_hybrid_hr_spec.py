#!/usr/bin/env python3
"""Independent checks of the Fossil Hybrid HR / Gen 6 Hybrid spec (stdlib + yaml only).

Every example frame in the spec is rebuilt here from the rules the spec states:
the key handshake (one AES-128 block under the watch key), the file-transfer IV,
per-packet AES-128-CTR, the 16-byte file container with CRC-32C, the CRC-32 the
watch reports, the notification payload and the configuration items. AES,
CTR and CRC-32C are transcribed below from their public definitions (FIPS-197,
SP 800-38A, RFC 3720) so the test imports nothing from this repository and no
crypto library. Every key, random number and address is invented.
"""

from __future__ import annotations

import json
import struct
import zlib
from pathlib import Path

import pytest
import yaml

SPEC = yaml.safe_load(
    (Path(__file__).parents[1] / "device-specs/devices/fossil-hybrid-hr.yaml").read_text(
        encoding="utf-8"
    )
)
DETAILS = SPEC["protocol_details"]
VECTORS = DETAILS["test_vectors"]
KEY = bytes.fromhex(VECTORS["watch_key_hex"])
SERVICE = "3dda0001-957f-7d4a-34a6-74696673696d"


def char_uuid(n: int) -> str:
    return f"3dda000{n}-957f-7d4a-34a6-74696673696d"


def h(text: str) -> bytes:
    return bytes.fromhex(text)


# --- AES-128 (FIPS-197), encryption and decryption of one block -------------


def _xtime(a: int) -> int:
    a <<= 1
    return (a ^ 0x11B) & 0xFF if a & 0x100 else a


def _gmul(a: int, b: int) -> int:
    result = 0
    while b:
        if b & 1:
            result ^= a
        a = _xtime(a)
        b >>= 1
    return result


def _build_sbox() -> list[int]:
    inverse = [0] * 256
    for i in range(1, 256):
        for j in range(1, 256):
            if _gmul(i, j) == 1:
                inverse[i] = j
                break
    box = []
    for i in range(256):
        x = y = inverse[i]
        for _ in range(4):
            x = ((x << 1) | (x >> 7)) & 0xFF
            y ^= x
        box.append(y ^ 0x63)
    return box


SBOX = _build_sbox()
INV_SBOX = [SBOX.index(i) for i in range(256)]
MIX = ((2, 3, 1, 1), (1, 2, 3, 1), (1, 1, 2, 3), (3, 1, 1, 2))
INV_MIX = ((14, 11, 13, 9), (9, 14, 11, 13), (13, 9, 14, 11), (11, 13, 9, 14))


def _round_keys(key: bytes) -> list[list[int]]:
    assert len(key) == 16
    words = [list(key[i:i + 4]) for i in range(0, 16, 4)]
    rcon = 1
    for i in range(4, 44):
        temp = list(words[i - 1])
        if i % 4 == 0:
            temp = [SBOX[b] for b in temp[1:] + temp[:1]]
            temp[0] ^= rcon
            rcon = _xtime(rcon)
        words.append([a ^ b for a, b in zip(words[i - 4], temp, strict=True)])
    return [sum(words[r * 4:r * 4 + 4], []) for r in range(11)]


def _shift_rows(state: list[int], inverse: bool = False) -> list[int]:
    out = [0] * 16
    for col in range(4):
        for row in range(4):
            src = (col - row) % 4 if inverse else (col + row) % 4
            out[col * 4 + row] = state[src * 4 + row]
    return out


def _mix_columns(state: list[int], matrix) -> list[int]:
    out = []
    for col in range(4):
        column = state[col * 4:col * 4 + 4]
        for row in range(4):
            out.append(
                _gmul(matrix[row][0], column[0]) ^ _gmul(matrix[row][1], column[1])
                ^ _gmul(matrix[row][2], column[2]) ^ _gmul(matrix[row][3], column[3])
            )
    return out


def aes_encrypt_block(key: bytes, block: bytes) -> bytes:
    keys = _round_keys(key)
    state = [b ^ k for b, k in zip(block, keys[0], strict=True)]
    for rnd in range(1, 11):
        state = _shift_rows([SBOX[b] for b in state])
        if rnd != 10:
            state = _mix_columns(state, MIX)
        state = [b ^ k for b, k in zip(state, keys[rnd], strict=True)]
    return bytes(state)


def aes_decrypt_block(key: bytes, block: bytes) -> bytes:
    keys = _round_keys(key)
    state = [b ^ k for b, k in zip(block, keys[10], strict=True)]
    for rnd in range(9, -1, -1):
        state = [INV_SBOX[b] for b in _shift_rows(state, inverse=True)]
        state = [b ^ k for b, k in zip(state, keys[rnd], strict=True)]
        if rnd:
            state = _mix_columns(state, INV_MIX)
    return bytes(state)


def aes_ctr(key: bytes, iv: bytes, data: bytes) -> bytes:
    """One-shot CTR: 128-bit big-endian counter starting at iv."""
    counter = int.from_bytes(iv, "big")
    out = bytearray()
    for offset in range(0, len(data), 16):
        stream = aes_encrypt_block(key, (counter % (1 << 128)).to_bytes(16, "big"))
        out += bytes(a ^ b for a, b in zip(data[offset:offset + 16], stream, strict=False))
        counter += 1
    return bytes(out)


def crc32c(data: bytes) -> int:
    crc = 0xFFFFFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ (0x82F63B78 if crc & 1 else 0)
    return crc ^ 0xFFFFFFFF


# --- The protocol as the spec states it -------------------------------------


def auth_start(phone_random: bytes) -> bytes:
    assert len(phone_random) == 8
    return bytes([0x02, 0x01, 0x01]) + phone_random


def answer_challenge(key: bytes, frame: bytes, phone_random: bytes) -> tuple[bytes, bytes]:
    """Return (reply frame, watch_random) for the watch's step-1 frame."""
    if len(frame) < 20 or frame[1] != 0x01:
        raise ValueError("not a handshake challenge")
    plain = aes_decrypt_block(key, frame[4:20])
    watch_random, echo = plain[:8], plain[8:]
    if echo != phone_random:
        raise ValueError("phone random mismatch: wrong key")
    reply = bytes([0x02, 0x02, 0x01]) + aes_encrypt_block(key, phone_random + watch_random)
    return reply, watch_random


def file_iv(phone_random: bytes, watch_random: bytes) -> bytes:
    iv = bytearray(16)
    iv[2:8] = phone_random[:6]
    iv[7] = (iv[7] + 1) & 0xFF
    iv[9:16] = watch_random[:7]
    return bytes(iv)


def iv_plus(iv: bytes, amount: int) -> bytes:
    out = bytearray(iv)
    value = (int.from_bytes(out[12:16], "big") + amount) & 0xFFFFFFFF
    out[12:16] = value.to_bytes(4, "big")
    return bytes(out)


def container(handle: int, version: int, payload: bytes) -> bytes:
    return (
        struct.pack("<HHII", handle, version, 0, len(payload))
        + payload
        + struct.pack("<I", crc32c(payload))
    )


def put_open(handle: int, length: int) -> bytes:
    return bytes([0x03]) + struct.pack("<HIII", handle, 0, length, length)


def get_open(handle: int) -> bytes:
    return bytes([0x01]) + struct.pack("<HII", handle, 0, 0xFFFFFFFF)


def packets(blob: bytes, payload_bytes: int) -> list[bytes]:
    return [
        bytes([index & 0xFF]) + blob[offset:offset + payload_bytes]
        for index, offset in enumerate(range(0, len(blob), payload_bytes))
    ]


def decrypt_download(key: bytes, iv: bytes, encrypted: list[bytes], size: int) -> tuple[bytes, int]:
    """Decrypt per the spec: packet N at IV + step*N, step searched on packet 1."""
    data = bytearray()
    step = 0x1F
    for index, packet in enumerate(encrypted):
        if index == 1:
            for candidate in range(0x1E, 0x30):
                trial = aes_ctr(key, iv_plus(iv, candidate), packet)
                last = len(data) + len(trial) - 1 == size
                if trial[0] == (0x81 if last else 0x01):
                    step = candidate
                    break
            else:
                raise ValueError("no IV step matched")
        plain = aes_ctr(key, iv_plus(iv, step * index), packet)
        assert plain[0] & 0x3F == index & 0x3F
        data += plain[1:]
    assert plain[0] & 0x80, "last packet carries bit 7"
    assert len(data) == size
    return bytes(data), step


def config_items(payload: bytes) -> dict[int, bytes]:
    items, pos = {}, 0
    while pos < len(payload):
        ident, length = struct.unpack_from("<HB", payload, pos)
        items[ident] = payload[pos + 3:pos + 3 + length]
        pos += 3 + length
    assert pos == len(payload)
    return items


def notification_payload(kind: int, flags: int, title: str, sender: str, message: str,
                         notification_id: int, app_crc: int) -> bytes:
    t, s, m = (x.encode() + b"\x00" for x in (title, sender, message))
    total = 10 + 4 + 4 + len(t) + len(s) + len(m)
    return (
        struct.pack("<HBBBBBBBB", total, 10, kind, flags, 4, 4, len(t), len(s), len(m))
        + struct.pack("<II", notification_id, app_crc)
        + t + s + m
    )


def characteristic(uuid: str) -> dict:
    for service in SPEC["services"]:
        for char in service.get("characteristics") or []:
            if char["uuid"] == uuid:
                return char
    raise KeyError(uuid)


# --- Tests ------------------------------------------------------------------


def test_aes_and_crc_transcriptions_match_published_vectors():
    v = VECTORS["fips197_aes128"]
    key, plain = h(v["key_hex"]), h(v["plaintext_hex"])
    assert aes_encrypt_block(key, plain).hex() == v["ciphertext_hex"]
    assert aes_decrypt_block(key, h(v["ciphertext_hex"])) == plain
    check = VECTORS["crc32c_check"]
    assert crc32c(check["input_ascii"].encode()) == check["crc"]
    assert zlib.crc32(b"123456789") == 0xCBF43926


def test_handshake_frames_rebuild_from_the_stated_rule():
    v = VECTORS["handshake"]
    phone, watch = h(v["phone_random_hex"]), h(v["watch_random_hex"])
    assert auth_start(phone).hex() == v["auth_start_hex"]
    challenge = h(v["watch_challenge_hex"])
    # The watch encrypts watch_random || phone_random; rebuild its block too.
    assert challenge[4:20] == aes_encrypt_block(KEY, watch + phone)
    reply, recovered = answer_challenge(KEY, challenge, phone)
    assert recovered == watch
    assert reply.hex() == v["auth_reply_hex"]
    assert len(reply) == 19
    result = h(v["result_success_hex"])
    assert result[1] == 0x02 and DETAILS["result_codes"][result[2]] == "success"
    assert file_iv(phone, watch).hex() == v["file_iv_hex"]


def test_wrong_key_is_rejected_by_the_echo_check():
    v = VECTORS["handshake"]
    wrong = bytes(16)
    with pytest.raises(ValueError, match="wrong key"):
        answer_challenge(wrong, h(v["watch_challenge_hex"]), h(v["phone_random_hex"]))


def test_iv_layout_and_counter_arithmetic():
    phone, watch = bytes(range(1, 9)), bytes(range(0xF1, 0xF9))
    iv = file_iv(phone, watch)
    assert iv[:2] == b"\x00\x00" and iv[8] == 0
    assert iv[2:7] == phone[:5] and iv[7] == (phone[5] + 1) & 0xFF
    assert iv[9:] == watch[:7]
    # The counter add touches only bytes 12-15 and wraps at 32 bits.
    top = bytes(12) + b"\xff\xff\xff\xff"
    assert iv_plus(top, 1) == bytes(16)


def test_encrypted_set_time_put():
    v = VECTORS["set_time_encrypted_put"]
    hs = VECTORS["handshake"]
    item = struct.pack("<HBIHh", 0x0C, 8, v["utc_epoch"], v["milliseconds"],
                       v["utc_offset_minutes"])
    assert item.hex() == v["item_hex"]
    blob = container(0x0800, 0x0002, item)
    assert blob.hex() == v["container_hex"]
    assert put_open(0x0800, len(blob)).hex() == v["put_open_hex"]
    assert v["packet_payload_bytes"] == min(v["mtu"] - 3, 512) - 1
    plain = packets(blob, v["packet_payload_bytes"])
    assert [p.hex() for p in plain] == v["plaintext_packets_hex"]
    iv = h(hs["file_iv_hex"])
    # Every upload packet restarts at the same IV.
    assert [aes_ctr(KEY, iv, p).hex() for p in plain] == v["encrypted_packets_hex"]
    assert zlib.crc32(blob) == v["expected_crc32"]
    assert bytes([0x04]) + struct.pack("<H", 0x0800) == h(v["close_hex"])


def test_encrypted_configuration_get_and_battery_item():
    v = VECTORS["read_configuration_encrypted_get"]
    iv = h(VECTORS["handshake"]["file_iv_hex"])
    assert get_open(0x0800).hex() == v["get_open_hex"]
    reply = h(v["open_reply_hex"])
    assert reply[0] & 0x0F == 1 and reply[1:3] == b"\x00\x08" and reply[3] == 0
    size = struct.unpack_from("<I", reply, 4)[0]
    data, step = decrypt_download(KEY, iv, [h(p) for p in v["encrypted_packets_hex"]], size)
    assert step == v["iv_step"]
    assert data.hex() == v["container_hex"]
    done = h(v["complete_reply_hex"])
    assert done[0] & 0x0F == 8 and done[1:3] == b"\x00\x08" and done[3] == 0
    assert struct.unpack_from("<I", done, 8)[0] == zlib.crc32(data)
    handle, version, offset, length = struct.unpack_from("<HHII", data)
    assert (handle, version, offset) == (0x0800, 2, 0)
    payload = data[12:12 + length]
    assert struct.unpack_from("<I", data, 12 + length)[0] == crc32c(payload)
    battery = config_items(payload)[0x0D]
    millivolts, percent = struct.unpack("<HB", battery)
    assert (millivolts, percent) == (v["battery_millivolts"], v["battery_percent"])


def test_device_info_supported_versions():
    v = VECTORS["device_info_payload"]
    payload, pos, versions, security = h(v["payload_hex"]), 0, {}, None
    while pos < len(payload):
        kind, length = struct.unpack_from("<HB", payload, pos)
        value = payload[pos + 3:pos + 3 + length]
        if kind == 0x0A:
            for i in range(0, len(value), 3):
                major, version = struct.unpack_from("<BH", value, i)
                versions[major] = version
        elif kind == 0x0E:
            security = list(value)
        pos += 3 + length
    assert versions == v["supported_versions"]
    assert security == v["security_version"]


def test_text_notification_payload_and_container():
    v = VECTORS["text_notification"]
    app_crc = zlib.crc32(v["package"].encode())
    assert app_crc == v["app_crc32"]
    body = notification_payload(3, 0x02, v["package"], v["sender"], v["message"],
                                v["notification_id"], app_crc)
    assert body.hex() == v["payload_hex"]
    assert struct.unpack_from("<H", body)[0] == len(body)
    blob = container(0x0900, v["file_version"], body)
    assert blob.hex() == v["container_hex"]
    assert put_open(0x0900, len(blob)).hex() == v["put_open_hex"]


def test_button_json_put_is_raw_on_a_0x05_handle():
    v = VECTORS["button_json_put"]
    document = json.loads(v["json"])
    buttons = document["push"]["set"]["master._.config.buttons"]
    assert {b["button_evt"] for b in buttons} <= {
        f"{pos}_{evt}" for pos in ("top", "middle", "bottom")
        for evt in ("short_press_release", "single_click", "hold")
    }
    raw = v["json"].encode()
    handle = 0x0500 | v["json_index"]
    assert put_open(handle, len(raw)).hex() == v["put_open_hex"]
    assert zlib.crc32(raw) == v["expected_crc32"]


def test_move_hands_frame_matches_command_template():
    v = VECTORS["move_hands_absolute"]
    frame = bytes([0x02, 0x15, 0x03, 0x02, 0x02])
    for hand, degrees in ((1, v["hour_degrees"]), (2, v["minute_degrees"])):
        frame += bytes([hand]) + struct.pack("<H", degrees) + bytes([0x03, 0x01])
    assert frame.hex() == v["frame_hex"]
    command = characteristic(char_uuid(2))["commands"]["move_hands"]
    rendered = b""
    for part in command["template"]:
        if isinstance(part, int):
            rendered += bytes([part])
        else:
            name = part.strip("{}")
            rendered += struct.pack("<H", v[name])
    assert rendered == frame


def test_fixed_command_bytes():
    basic = characteristic(char_uuid(2))["commands"]
    assert basic["request_hand_control"]["value"] == [2, 0x15, 1, 1, 0, 0]
    assert basic["release_hand_control"]["value"] == [2, 0x15, 2, 0, 0]
    assert basic["factory_reset"]["value"] == [2, 0xF1, 0x23] + [0xFF] * 5
    auth = characteristic(char_uuid(5))["commands"]
    confirm = bytes(auth["confirm_on_watch"]["value"])
    assert struct.unpack_from("<I", confirm, 2)[0] == 30000
    file_cmds = characteristic(char_uuid(3))["commands"]
    assert file_cmds["file_lookup"]["template"][:2] == [0x02, 0xFF]
    assert file_cmds["file_delete"]["template"][0] == 0x0B


def test_structure_scope_and_flags():
    device = SPEC["device"]
    assert device["manufacturer_status"] == "abandoned"
    assert device["integration"] == "identify_only"
    assert device["testing"]["status"] == "untested"
    assert device["identification"]["service_uuids"] == [SERVICE]
    assert "entities" not in SPEC
    vendor = next(s for s in SPEC["services"] if s["uuid"] == SERVICE)
    assert {c["uuid"] for c in vendor["characteristics"]} == {char_uuid(n) for n in range(2, 8)}
    data_char = characteristic(char_uuid(4))
    assert data_char["encryption"]["algorithm"] == "aes-128-ctr"
    for service in SPEC["services"]:
        for char in service.get("characteristics") or []:
            assert char["verification"] in {"reported", "hypothesis"}
            for name, command in (char.get("commands") or {}).items():
                assert command["verification"] == "reported", name
    commands = {
        name: command
        for service in SPEC["services"]
        for char in service.get("characteristics") or []
        for name, command in (char.get("commands") or {}).items()
    }
    for name in ("factory_reset", "save_calibration", "file_delete"):
        assert commands[name]["advanced"] is True
        assert commands[name]["advanced_reason"]
    key_param = commands["auth_reply"]["parameters"]["response_block"]
    assert key_param["source"] == "credential:watch_key"
    issued = device["setup"]["methods"][0]["issues_credentials"]
    assert issued["watch_key"]["user_entered"] is True


def test_firmware_update_feature_marks_unknowns():
    (feature,) = [f for f in SPEC["features"] if f["type"] == "firmware_update"]
    dfu = feature["dfu"]
    assert dfu["mechanisms"] == ["vendor_ble"]
    assert dfu["image"]["signing"] == "unknown"
    assert dfu["recovery"]["interrupted"] == "unknown"
    assert dfu["enter"]["how"] == "in_place"
    assert "0x00ff" in dfu["enter"]["notes"]
    assert feature["dfu"]["verification"] == "reported"


def test_examples_use_invented_identifiers():
    assert VECTORS["example_address"].lower().startswith("00:00:5e:00:53:")
    text = (Path(__file__).parents[1] / "device-specs/devices/fossil-hybrid-hr.yaml").read_text(
        encoding="utf-8"
    )
    assert VECTORS["watch_key_hex"] in text
    assert VECTORS["watch_key_hex"] == "0f1e2d3c4b5a69788796a5b4c3d2e1f0"
