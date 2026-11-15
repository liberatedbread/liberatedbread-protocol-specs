# Copyright 2026 Pigs Can Fly Labs LLC
# SPDX-License-Identifier: Apache-2.0
"""Proves the Slingbox spec's example frames follow its own stated rules.

`device-specs/devices/slingbox.yaml` says a control message is a 32-byte
little-endian header (type, session id, message id, 0, sequence, 6 zero
bytes, payload length, cipher mode, 4 zero bytes, parity, 6 zero bytes)
followed by a payload encrypted with TEA in ECB mode: under a fixed key in
mode 0x2000, under a session key derived from a client random, the session
id and a box challenge in mode 0x8000. This module transcribes those rules
with the standard library alone and rebuilds every example in the spec from
them, using the invented password "example-pw", session id 0x5A3C and the
invented random and challenge the spec gives. The session-key rule is
transcribed twice, once from the prose (bit lists) and once as integer bit
rotation, and the two must agree.
"""

from __future__ import annotations

import struct
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SPEC_PATH = REPO_ROOT / "device-specs" / "devices" / "slingbox.yaml"
PASSWORD = "example-pw"  # invented
SESSION_ID = 0x5A3C  # invented
MASK = 0xFFFFFFFF
DELTA = 0x9E3779B9


@pytest.fixture(scope="module")
def spec() -> dict:
    return yaml.safe_load(SPEC_PATH.read_text())


@pytest.fixture(scope="module")
def details(spec) -> dict:
    return spec["protocol_details"]


@pytest.fixture(scope="module")
def fixed_key(details) -> tuple[int, ...]:
    text = " ".join(details["cipher"]["fixed_key"].split())
    words = text.split("words ")[1].split(" (")[0].replace(",", "").split()
    key = tuple(int(w, 16) for w in words)
    as_bytes = text.split("word: ")[1].split(")")[0]
    assert struct.pack("<4I", *key).hex() == as_bytes
    return key


@pytest.fixture(scope="module")
def ex(details) -> dict:
    return details["session_key"]["example"]


def tea_encrypt(v0: int, v1: int, k: tuple[int, ...]) -> tuple[int, int]:
    total = 0
    for _ in range(32):
        total = (total + DELTA) & MASK
        v0 = (v0 + ((((v1 << 4) & MASK) + k[0]) ^ (v1 + total) ^ ((v1 >> 5) + k[1]))) & MASK
        v1 = (v1 + ((((v0 << 4) & MASK) + k[2]) ^ (v0 + total) ^ ((v0 >> 5) + k[3]))) & MASK
    return v0, v1


def tea_decrypt(v0: int, v1: int, k: tuple[int, ...]) -> tuple[int, int]:
    total = 0xC6EF3720
    for _ in range(32):
        v1 = (v1 - ((((v0 << 4) & MASK) + k[2]) ^ (v0 + total) ^ ((v0 >> 5) + k[3]))) & MASK
        v0 = (v0 - ((((v1 << 4) & MASK) + k[0]) ^ (v1 + total) ^ ((v1 >> 5) + k[1]))) & MASK
        total = (total - DELTA) & MASK
    return v0, v1


def ecb(data: bytes, key: tuple[int, ...], fn=tea_encrypt) -> bytes:
    assert len(data) % 8 == 0
    out = b""
    for i in range(0, len(data), 8):
        out += struct.pack("<2I", *fn(*struct.unpack("<2I", data[i : i + 8]), key))
    return out


# --- session key, transcription 1: bit lists, as the spec's prose reads ---
def bits(data: bytes) -> list[int]:
    return [(byte >> i) & 1 for byte in data for i in range(8)]


def unbits(seq: list[int]) -> bytes:
    return bytes(sum(seq[i + j] << j for j in range(8)) for i in range(0, len(seq), 8))


def mix_bits(data: bytes, sid: int, a: int, b: int) -> list[int]:
    t = bits(data)
    s = bits(struct.pack("<H", sid))
    v: list[int] | None = None
    for i in range(1, 17):
        r = i * (a if not (sid >> (i - 1)) & 1 else b)
        t = t[r:] + t[:r]
        t = [x ^ y for x, y in zip(t[:16], s, strict=True)] + t[16:]
        v = t if v is None else [x ^ y for x, y in zip(t, v, strict=True)]
    assert v is not None
    return v


def session_key_bits(sid: int, rand: bytes, chal: bytes) -> tuple[int, ...]:
    k = [x ^ y for x, y in zip(mix_bits(rand, sid, 2, 3), mix_bits(chal, sid, -1, -4), strict=True)]
    return struct.unpack("<4I", unbits(k))


# --- session key, transcription 2: one 128-bit integer, bit n = list index n ---
def mix_int(data: bytes, sid: int, a: int, b: int) -> int:
    t = int.from_bytes(data, "little")  # LSB-first bit order == little-endian integer
    full = (1 << 128) - 1
    v = 0
    for i in range(1, 17):
        r = (i * (a if not (sid >> (i - 1)) & 1 else b)) % 128
        # list rotation t[r:] + t[:r] moves bit r to position 0: a right shift
        t = ((t >> r) | (t << (128 - r))) & full
        t ^= sid & 0xFFFF
        v ^= t
    return v


def session_key_int(sid: int, rand: bytes, chal: bytes) -> tuple[int, ...]:
    k = mix_int(rand, sid, 2, 3) ^ mix_int(chal, sid, -1, -4)
    return struct.unpack("<4I", k.to_bytes(16, "little"))


def utf16(text: str) -> bytes:
    return text.encode("utf-16-le")


def frame(op: int, payload: bytes, sid: int, seq: int, mode: int, key: tuple[int, ...]) -> str:
    parity = 0
    if mode == 0x8000:
        for byte in payload:
            parity ^= byte
    head = struct.pack("<HHHHH6xHH4xH6x", 0x0101, sid, op, 0, seq, len(payload), mode, parity)
    assert len(head) == 32
    return (head + ecb(payload, key)).hex()


@pytest.fixture(scope="module")
def session_key(ex) -> tuple[int, ...]:
    sid = int(ex["session_id"], 16)
    assert sid == SESSION_ID
    return session_key_bits(sid, bytes.fromhex(ex["client_random"]), bytes.fromhex(ex["box_challenge"]))


def test_fixed_key_tea_round_trips(fixed_key):
    data = bytes(range(64))
    assert ecb(ecb(data, fixed_key), fixed_key, tea_decrypt) == data


def test_tea_matches_published_reference_vector():
    # The standard TEA test vector (all-zero key and block).
    assert tea_encrypt(0, 0, (0, 0, 0, 0)) == (0x41EA3A0A, 0x94BAA940)


def test_session_key_example(ex, session_key):
    words = tuple(int(w, 16) for w in ex["key_words"].split())
    assert session_key == words


@pytest.mark.parametrize("sid", [0, 1, 0x5A3C, 0x8001, 0xFFFF, 0x1234])
def test_two_session_key_transcriptions_agree(ex, sid):
    rand, chal = bytes.fromhex(ex["client_random"]), bytes.fromhex(ex["box_challenge"])
    assert session_key_bits(sid, rand, chal) == session_key_int(sid, rand, chal)


def test_discovery_probe_and_reply(spec):
    method = spec["device"]["discovery"]["methods"][0]["udp_broadcast"]
    probe = struct.pack("<HHH26x", 0x0101, 0, 0x0002)
    assert method["probe_hex"] == probe.hex()
    reply = bytearray(probe)
    reply[16] = 0x5C
    reply += bytes(6) + struct.pack(">H", 17) + bytes.fromhex("a0a1a2a3a4a5a6a7a8a9aaabacadaeaf")
    reply += utf16("Den").ljust(64, b"\x00") + struct.pack("<H", 5201) + bytes(2)
    assert len(reply) == 124
    assert spec["payload_formats"]["DiscoveryReply"]["example"] == reply.hex()


def test_header_example(spec, session_key):
    assert spec["payload_formats"]["MessageHeader"]["example"] == frame(0x66, b"", SESSION_ID, 10, 0x8000, session_key)


def stream_settings(nonce: bytes) -> bytes:
    res, fps, bw, smooth, iframe, audio = 12, 30, 2000, 63, 5, 64
    words = (0xFF, 0xFF, res, 1, (iframe << 24) + (fps << 16) + bw, 0x10001 + (smooth << 8), 3, 1, audio, 0x4F, 1)
    payload = struct.pack("<11I16s2I92x", *words, nonce, 0x01012020, 1)
    assert len(payload) == 160
    return payload


NONCE = bytes.fromhex("0123456789abcdeffedcba9876543210")


def test_stream_settings_plaintext(spec):
    assert spec["payload_formats"]["StreamSettings"]["example"] == stream_settings(NONCE).hex()


def test_e1_password(details, fixed_key):
    e1 = details["e1_password"]
    assert e1["example_password"] == PASSWORD
    raw = bytes.fromhex(e1["example"].removeprefix("E1:"))
    clear = ecb(raw, fixed_key, tea_decrypt)
    end = next(i for i in range(0, len(clear), 2) if clear[i : i + 2] == b"\x00\x00")
    assert clear[:end].decode("utf-16-le") == PASSWORD
    assert set(clear[end:]) == {0}


def test_command_examples(spec, ex, fixed_key, session_key):
    cmds = spec["commands"]
    rand = bytes.fromhex(ex["client_random"])
    ir = bytes([4, 0, 0, 1]) + bytes(468) + struct.pack("<4H", 1, 0, 0, 0)
    assert len(ir) == 480
    expected = {
        "login": frame(0x67, struct.pack("<I32s32s132x", 0, utf16("admin"), utf16(PASSWORD)), 0, 1, 0x2000, fixed_key),
        "key_exchange": frame(0xC6, struct.pack("<I16s36x", 1, rand), SESSION_ID, 2, 0x2000, fixed_key),
        "start_session": frame(0x7E, struct.pack("<II", 1, 0), SESSION_ID, 3, 0x8000, session_key),
        "take_over": frame(0x93, struct.pack("<32s32s8x", utf16("admin"), utf16(PASSWORD)), SESSION_ID, 4, 0x8000, session_key),
        "select_input": frame(0x85, struct.pack("<4H", 1, 0, 0, 0), SESSION_ID, 4, 0x8000, session_key),
        "get_key_codes": frame(0x86, struct.pack("<H254x", 0x0400 + 1), SESSION_ID, 5, 0x8000, session_key),
        "prepare_stream": frame(
            0xA6,
            struct.pack("<10H76x", 0x01CF, 0, 0x40, 0x10, 0x5000, 0x0180, 1, 0x1E, 0, 0x3D),
            SESSION_ID, 6, 0x8000, session_key,
        ),
        "set_stream_settings": frame(0xB5, stream_settings(NONCE), SESSION_ID, 7, 0x8000, session_key),
        "send_ir_button": frame(0x87, ir, SESSION_ID, 8, 0x8000, session_key),
        "set_tuner_channel": frame(0x89, struct.pack("<IHBB8x", 2, 155, 0, 0), SESSION_ID, 9, 0x8000, session_key),
        "keepalive": frame(0x66, b"", SESSION_ID, 10, 0x8000, session_key),
        "logout": frame(0x68, b"", SESSION_ID, 11, 0x8000, session_key),
    }
    assert set(expected) == set(cmds)
    for name, hexframe in expected.items():
        assert cmds[name]["example_body"] == hexframe, name


def test_payload_lengths_are_tea_blocks(spec):
    for name, cmd in spec["commands"].items():
        raw = bytes.fromhex(cmd["example_body"])
        length = struct.unpack_from("<H", raw, 16)[0]
        assert len(raw) == 32 + length, name
        assert length % 8 == 0, name


def test_advanced_commands_explain_themselves(spec):
    for name, cmd in spec["commands"].items():
        if cmd.get("advanced"):
            assert cmd.get("advanced_reason"), name
