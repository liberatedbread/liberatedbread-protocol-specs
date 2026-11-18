"""Independent standard-library vectors for Danalock V3 DMI BLE.

PyYAML only loads the document. DMI framing, CRC, RPD, AFI primitives, TLS PRF
and broadcast checks are implemented here without importing public clients or
repository code. OpenSSL supplies an independent AES implementation.
"""

import hashlib
import hmac
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
SPEC = yaml.safe_load(
    (ROOT / "device-specs" / "devices" / "danalock-v3-ble.yaml").read_text(
        encoding="utf-8"
    )
)
DETAILS = SPEC["protocol_details"]


def _hex(value):
    return bytes.fromhex(value)


def _crc16_ccitt_false(data):
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def _escape(data):
    replacements = {0xC0: b"\xc2\x40", 0xC1: b"\xc2\x41", 0xC2: b"\xc2\x42"}
    return b"".join(replacements.get(byte, bytes([byte])) for byte in data)


def _unescape(data):
    output = bytearray()
    position = 0
    while position < len(data):
        if data[position] == 0xC2 and position + 1 < len(data):
            output.append(data[position + 1] | 0x80)
            position += 2
        else:
            output.append(data[position])
            position += 1
    return bytes(output)


def _build_frame(destination, source, frame_type, ports, seq_ack, payload=b""):
    if len(destination) != 6 or len(source) != 6:
        raise ValueError("DMI addresses must be 6 bytes")
    logical = (
        b"\x00\xf1"
        + destination
        + source
        + bytes([frame_type, ports, seq_ack])
        + payload
    )
    logical += _crc16_ccitt_false(logical).to_bytes(2, "little")
    return logical, b"\xc0" + _escape(logical) + b"\xc1"


def _parse_logical(logical):
    if len(logical) < 19:
        raise ValueError("short DMI frame")
    if logical[:2] != b"\x00\xf1":
        raise ValueError("bad DMI magic")
    expected = int.from_bytes(logical[-2:], "little")
    if _crc16_ccitt_false(logical[:-2]) != expected:
        raise ValueError("bad DMI CRC")
    return {
        "destination": logical[2:8],
        "source": logical[8:14],
        "frame_type": logical[14],
        "ports": logical[15],
        "seq_ack": logical[16],
        "payload": logical[17:-2],
    }


def _stream_decode(chunks):
    buffer = bytearray()
    frames = []
    errors = 0
    for chunk in chunks:
        buffer.extend(chunk)
        while True:
            try:
                start = buffer.index(0xC0)
            except ValueError:
                buffer.clear()
                break
            del buffer[:start]
            try:
                end = buffer.index(0xC1, 1)
            except ValueError:
                break
            wire = bytes(buffer[: end + 1])
            del buffer[: end + 1]
            try:
                frames.append(_parse_logical(_unescape(wire[1:-1])))
            except ValueError:
                errors += 1
    return frames, bytes(buffer), errors


def _aes_cbc_zero_iv(key, data):
    if shutil.which("openssl") is None:
        pytest.skip("openssl binary not available")
    command = [
        "openssl",
        "enc",
        "-aes-128-cbc",
        "-d",
        "-K",
        key.hex(),
        "-iv",
        "00" * 16,
        "-nopad",
    ]
    return subprocess.run(command, input=data, capture_output=True, check=True).stdout


def _decode_broadcast(payload, key):
    if len(payload) != 24:
        raise ValueError("broadcast must be 24 bytes")
    if len(key) != 16:
        raise ValueError("broadcast key must be 16 bytes")
    if payload[0] != 2:
        raise ValueError("not a normal DMI broadcast")
    plaintext = _aes_cbc_zero_iv(key, payload[8:24])
    expected = int.from_bytes(plaintext[:2], "little")
    if _crc16_ccitt_false(plaintext[2:16]) != expected:
        raise ValueError("broadcast CRC mismatch")
    lock_flags = int.from_bytes(plaintext[10:12], "little")
    return {
        "serial": payload[1:7].hex(),
        "counter": int.from_bytes(plaintext[2:4], "little"),
        "battery_raw": plaintext[6],
        "device_flags_raw": int.from_bytes(plaintext[4:6], "little"),
        "lock_flags_raw": lock_flags,
        "locked": bool(lock_flags & 1),
    }


class _RpdEndpoint:
    def __init__(self, isn, port):
        self.my_seq = isn
        self.my_port = port
        self.peer_port = 2
        self.peer_next = 0
        self.syn_sent = False

    def _ports(self):
        return self.my_port | (self.peer_port << 4)

    def _seq_ack(self):
        return self.my_seq | (self.peer_next << 4)

    def make_syn(self):
        if self.syn_sent:
            raise RuntimeError("SYN already sent")
        self.syn_sent = True
        result = (1, self._ports(), self._seq_ack())
        self.my_seq = (self.my_seq + 1) & 0xF
        return result

    def make_ack(self):
        return (0, self._ports(), self._seq_ack())

    def make_data(self):
        if not self.syn_sent:
            raise RuntimeError("no SYN")
        return (0, self._ports(), self._seq_ack())

    def make_fin(self):
        return (2, self._ports(), self._seq_ack())

    def on_frame(self, frame_type, ports, seq_ack, payload=b""):
        if ports >> 4 != self.my_port:
            raise ValueError("wrong receiver port")
        seq = seq_ack & 0xF
        ack = seq_ack >> 4
        accepted = False
        if frame_type == 1:
            self.peer_port = ports & 0xF
            self.peer_next = (seq + 1) & 0xF
            accepted = True
        elif frame_type == 0 and payload and seq == self.peer_next:
            self.peer_next = (seq + 1) & 0xF
            accepted = True
        elif frame_type == 2 and seq == self.peer_next:
            self.peer_next = (seq + 1) & 0xF
            accepted = True
        if frame_type == 0 and ack == (self.my_seq + 1) & 0xF:
            self.my_seq = (self.my_seq + 1) & 0xF
        return accepted


def _varint(value):
    if value < 0:
        raise ValueError("negative varint")
    output = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        output.append(byte | (0x80 if value else 0))
        if not value:
            return bytes(output)


def _read_varint(data):
    value = 0
    for index, byte in enumerate(data):
        value |= (byte & 0x7F) << (7 * index)
        if not byte & 0x80:
            return value, index + 1
        if index >= 4:
            break
    raise ValueError("truncated/unbounded varint")


def _tlv_uint(tag, value):
    if value < 0:
        raise ValueError("negative TLV integer")
    width = max(1, (value.bit_length() + 7) // 8)
    raw = value.to_bytes(width, "big")
    return _varint(tag) + _varint(len(raw)) + raw


def _parse_tlv(data):
    members = {}
    position = 0
    while position < len(data):
        tag, tag_width = _read_varint(data[position:])
        position += tag_width
        length, length_width = _read_varint(data[position:])
        position += length_width
        if position + length > len(data):
            raise ValueError("truncated TLV member")
        if tag in members:
            raise ValueError("duplicate TLV tag")
        members[tag] = data[position : position + length]
        position += length
    return members


def _prf_sha384(secret, label, seed, length):
    a = label + seed
    output = b""
    while len(output) < length:
        a = hmac.new(secret, a, hashlib.sha384).digest()
        output += hmac.new(secret, a + label + seed, hashlib.sha384).digest()
    return output[:length]


def test_dmi_crc_and_canonical_escaping():
    assert _crc16_ccitt_false(b"123456789") == 0x29B1
    assert _escape(bytes([0xC0, 0xC1, 0xC2])) == bytes.fromhex("c2 40 c2 41 c2 42")
    assert _unescape(_escape(bytes(range(256)))) == bytes(range(256))
    assert _unescape(b"\xc2") == b"\xc2"


def test_dmi_frame_vectors_rebuild_and_parse():
    for vector in DETAILS["dmi_frame"]["vectors"]:
        logical = _hex(vector["logical_hex"])
        parsed = _parse_logical(logical)
        rebuilt_logical, wire = _build_frame(
            parsed["destination"],
            parsed["source"],
            parsed["frame_type"],
            parsed["ports"],
            parsed["seq_ack"],
            parsed["payload"],
        )
        assert rebuilt_logical == logical
        assert wire == _hex(vector["wire_hex"])
    escaped = DETAILS["dmi_frame"]["vectors"][1]
    parsed = _parse_logical(_hex(escaped["logical_hex"]))
    assert parsed["payload"] == _hex(escaped["expected"]["payload_hex"])


def test_dmi_stream_fragmentation_noise_bad_crc_and_malformed_input():
    wire = _hex(DETAILS["dmi_frame"]["vectors"][1]["wire_hex"])
    other = _hex(DETAILS["dmi_frame"]["vectors"][0]["wire_hex"])
    for size in (1, 7, 20):
        chunks = [wire[index : index + size] for index in range(0, len(wire), size)]
        frames, remaining, errors = _stream_decode(chunks)
        assert len(frames) == 1 and remaining == b"" and errors == 0
    frames, remaining, errors = _stream_decode([b"noise" + wire + other])
    assert len(frames) == 2 and remaining == b"" and errors == 0
    frames, remaining, errors = _stream_decode([wire[:-1]])
    assert frames == [] and remaining == wire[:-1] and errors == 0
    bad = bytearray(wire)
    bad[-2] ^= 1
    frames, _, errors = _stream_decode([bytes(bad)])
    assert frames == [] and errors == 1
    with pytest.raises(ValueError, match="short"):
        _parse_logical(b"\x00\xf1" + bytes(10))
    with pytest.raises(ValueError, match="magic"):
        _parse_logical(bytes(19))
    with pytest.raises(ValueError, match="6 bytes"):
        _build_frame(b"short", bytes(6), 0, 0x24, 0)


def test_rpd_session_sequence_duplicates_out_of_order_and_fin():
    vector = DETAILS["rpd"]["session_vector"]
    phone = _RpdEndpoint(vector["phone"]["isn"], vector["phone"]["port"])
    lock = _RpdEndpoint(vector["lock"]["isn"], vector["lock"]["port"])
    for step in vector["steps"]:
        sender, receiver = (phone, lock) if step["direction"] == "phone_to_lock" else (lock, phone)
        if step["kind"] == "SYN":
            produced = sender.make_syn()
            payload = b""
        elif step["kind"] == "empty ACK":
            produced = sender.make_ack()
            payload = b""
        else:
            produced = sender.make_data()
            payload = step["payload_ascii"].encode("ascii")
        assert produced == (int(step.get("kind") == "SYN"), int(step["ports"], 0), int(step["seq_ack"], 0))
        accepted = receiver.on_frame(*produced, payload)
        if step["kind"] in {"SYN", "data"}:
            assert accepted is True
        for role, endpoint in (("phone", phone), ("lock", lock)):
            key = f"{role}_next"
            if key in step:
                assert endpoint.my_seq == step[key]
        if "phone_peer_next" in step:
            assert phone.peer_next == step["phone_peer_next"]

    before = phone.peer_next
    assert phone.on_frame(0, 0x42, 0x71, b"y") is False
    assert phone.peer_next == before
    assert phone.on_frame(0, 0x42, 0x31, b"skipped") is False
    assert phone.peer_next == before
    assert phone.on_frame(2, 0x42, 0x72) is True
    assert phone.peer_next == 3
    assert phone.make_ack()[2] >> 4 == 3


def test_broadcast_decrypts_and_validates_independently():
    vector = DETAILS["broadcast"]["synthetic_vector"]
    decoded = _decode_broadcast(_hex(vector["payload_hex"]), _hex(vector["broadcast_key_hex"]))
    expected = vector["expected"]
    assert decoded["serial"] == expected["serial_hex"]
    assert decoded["counter"] == expected["counter"]
    assert decoded["battery_raw"] == expected["battery_raw"]
    assert decoded["locked"] is expected["locked"]
    assert decoded["device_flags_raw"] == 0x1F
    assert decoded["lock_flags_raw"] & 0x01
    assert decoded["lock_flags_raw"] & 0x04
    assert decoded["lock_flags_raw"] & 0x10
    with pytest.raises(ValueError, match="24 bytes"):
        _decode_broadcast(b"\x02", bytes(16))
    with pytest.raises(ValueError, match="normal DMI"):
        _decode_broadcast(b"\x03" + bytes(23), bytes(16))
    with pytest.raises(ValueError, match="CRC"):
        _decode_broadcast(_hex(vector["payload_hex"]), bytes(16))


def test_afi_varint_tlv_and_read_only_command_vectors():
    for vector in DETAILS["afi"]["primitive_vectors"]["varints"]:
        encoded = _varint(vector["value"])
        assert encoded == _hex(vector["hex"])
        assert _read_varint(encoded + b"\xaa") == (vector["value"], len(encoded))
    for vector in DETAILS["afi"]["primitive_vectors"]["tlv_uint"]:
        assert _tlv_uint(vector["tag"], vector["value"]) == _hex(vector["hex"])
    with pytest.raises(ValueError):
        _read_varint(b"\x80")
    with pytest.raises(ValueError, match="truncated TLV"):
        _parse_tlv(bytes.fromhex("01 05 00"))
    assert _parse_tlv(_tlv_uint(4, 0x1234) + _tlv_uint(3, 0x10000)) == {
        4: bytes.fromhex("12 34"),
        3: bytes.fromhex("01 00 00"),
    }
    with pytest.raises(ValueError):
        _varint(-1)
    commands = DETAILS["afi"]["commands"]
    assert commands["device_get_information"]["request_hex"] == "01 02 02"
    assert commands["lock_get_state"]["request_hex"] == "01 04 05"
    assert commands["power_source_get_information"]["request_hex"] == "01 0a 01"
    epoch = int(commands["time_set_utc"]["example_epoch"], 0)
    assert b"\x01\x03\x01" + epoch.to_bytes(4, "little") == _hex(
        commands["time_set_utc"]["request_hex"]
    )
    assert commands["lock_operate"]["advanced"] is True
    assert commands["lock_operate"]["attended"] is True
    assert commands["lock_operate"]["generic_binding"] is False


def test_tls_prf_and_empty_client_certificate_semantics():
    vector = DETAILS["tls_12"]["prf_sha384_test_vector"]
    actual = _prf_sha384(
        _hex(vector["secret_hex"]),
        vector["label_ascii"].encode("ascii"),
        _hex(vector["seed_hex"]),
        vector["output_length"],
    )
    assert actual == _hex(vector["expected_hex"])
    empty = _hex(DETAILS["tls_12"]["empty_client_certificate"]["handshake_message_hex"])
    assert empty == bytes.fromhex("0b 00 00 03 00 00 00")
    assert empty[0] == 0x0B
    assert int.from_bytes(empty[1:4], "big") == 3
    assert int.from_bytes(empty[4:7], "big") == 0
    validation = DETAILS["tls_12"]["certificate_validation"]
    assert validation["insecure_mode"].startswith("forbidden")
    assert len(validation["required_checks"]) == 5


def test_identify_only_no_plaintext_commands_and_btze_evidence_boundary():
    assert SPEC["device"]["integration"] == "identify_only"
    assert not SPEC.get("entities")
    assert not SPEC.get("commands")
    for service in SPEC["services"]:
        for characteristic in service.get("characteristics", []):
            assert "commands" not in characteristic
    assert SPEC["device"]["testing"]["status"] == "untested"
    assert "BTZE only" in SPEC["device"]["testing"]["notes"]
    assert DETAILS["consumer_limitations"]["insecure_tls_permitted"] is False
