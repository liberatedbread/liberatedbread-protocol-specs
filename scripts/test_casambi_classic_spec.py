"""Independent Casambi Classic full-session golden and malformed-input tests.

PyYAML reads the document; AES-CMAC, framing, and state parsing are independent
standard-library transcriptions. The separate direct/FE3D API is deliberately
not implemented or mixed into these full-session vectors.
"""

from __future__ import annotations

import hmac
import struct
from pathlib import Path

import pytest
import yaml

SPEC_PATH = Path(__file__).resolve().parent.parent / "device-specs/devices/casambi-classic-ble.yaml"

OPERATION_TYPES = {
    "SetLevel": {"network": 4, "unit": 7, "group": 26, "scene": 1},
    "SetTemperature": {"network": 5, "unit": 8, "group": 27},
    "SetColor": {"network": 6, "unit": 9, "group": 28},
    "SetVertical": {"network": 22, "unit": 24, "group": 29},
    "SetWhite": {"network": 23, "unit": 25, "group": 30},
}


def details() -> dict:
    with SPEC_PATH.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)["protocol_details"]


def gf_mul(left: int, right: int) -> int:
    result = 0
    for _ in range(8):
        if right & 1:
            result ^= left
        left = ((left << 1) ^ 0x11B) & 0xFF if left & 0x80 else (left << 1) & 0xFF
        right >>= 1
    return result


def gf_pow(value: int, exponent: int) -> int:
    result = 1
    while exponent:
        if exponent & 1:
            result = gf_mul(result, value)
        value = gf_mul(value, value)
        exponent >>= 1
    return result


def rotate_byte(value: int, count: int) -> int:
    return ((value << count) | (value >> (8 - count))) & 0xFF


SBOX = []
for _x in range(256):
    inverse = gf_pow(_x, 254) if _x else 0
    SBOX.append(
        inverse
        ^ rotate_byte(inverse, 1)
        ^ rotate_byte(inverse, 2)
        ^ rotate_byte(inverse, 3)
        ^ rotate_byte(inverse, 4)
        ^ 0x63
    )


def aes_round_keys(key: bytes) -> list[list[int]]:
    if len(key) != 16:
        raise ValueError("AES-128 needs a 16-byte key")
    words = [list(key[index : index + 4]) for index in range(0, 16, 4)]
    rcon = 1
    for index in range(4, 44):
        temp = words[index - 1][:]
        if index % 4 == 0:
            temp = [SBOX[value] for value in temp[1:] + temp[:1]]
            temp[0] ^= rcon
            rcon = gf_mul(rcon, 2)
        words.append([a ^ b for a, b in zip(words[index - 4], temp, strict=True)])
    return words


def add_round_key(state, words, round_number):
    for column in range(4):
        for row in range(4):
            state[4 * column + row] ^= words[4 * round_number + column][row]


def mix_columns(state):
    for column in range(4):
        a = state[4 * column : 4 * column + 4]
        state[4 * column : 4 * column + 4] = [
            gf_mul(a[0], 2) ^ gf_mul(a[1], 3) ^ a[2] ^ a[3],
            a[0] ^ gf_mul(a[1], 2) ^ gf_mul(a[2], 3) ^ a[3],
            a[0] ^ a[1] ^ gf_mul(a[2], 2) ^ gf_mul(a[3], 3),
            gf_mul(a[0], 3) ^ a[1] ^ a[2] ^ gf_mul(a[3], 2),
        ]


def aes_encrypt_block(key: bytes, block: bytes) -> bytes:
    if len(block) != 16:
        raise ValueError("AES block must be 16 bytes")
    words = aes_round_keys(key)
    state = list(block)
    add_round_key(state, words, 0)
    for round_number in range(1, 11):
        state = [SBOX[value] for value in state]
        shifted = [0] * 16
        for column in range(4):
            for row in range(4):
                shifted[4 * column + row] = state[4 * ((column + row) % 4) + row]
        state = shifted
        if round_number != 10:
            mix_columns(state)
        add_round_key(state, words, round_number)
    return bytes(state)


def aes_cmac(key: bytes, data: bytes) -> bytes:
    zero = int.from_bytes(aes_encrypt_block(key, bytes(16)), "big")
    k1 = ((zero << 1) & ((1 << 128) - 1)) ^ (0x87 if zero >> 127 else 0)
    k2 = ((k1 << 1) & ((1 << 128) - 1)) ^ (0x87 if k1 >> 127 else 0)
    if data and len(data) % 16 == 0:
        last = int.from_bytes(data[-16:], "big") ^ k1
        body = data[:-16]
    else:
        final = data[-(len(data) % 16) :] if len(data) % 16 else b""
        padded = final + b"\x80" + bytes(15 - len(final))
        last = int.from_bytes(padded, "big") ^ k2
        body = data[: len(data) - len(final)]
    state = 0
    for offset in range(0, len(body), 16):
        block = int.from_bytes(body[offset : offset + 16], "big")
        state = int.from_bytes(aes_encrypt_block(key, (state ^ block).to_bytes(16, "big")), "big")
    return aes_encrypt_block(key, (state ^ last).to_bytes(16, "big"))


def sign_envelope(key: bytes, connection_hash: bytes, selector: int, sequence: int, payload: bytes) -> bytes:
    if len(connection_hash) != 8:
        raise ValueError("Classic connection hash must be eight bytes")
    if selector not in (2, 3):
        raise ValueError("signed Classic selector must be visitor or manager")
    if not 1 <= sequence <= 0xFFFF:
        raise ValueError("Classic sequence zero is not on the wire")
    body = sequence.to_bytes(2, "big") + payload
    signature_length = 4 if selector == 2 else 16
    signature = aes_cmac(key, connection_hash + body)[:signature_length]
    return bytes([selector]) + signature + body


def verify_envelope(key: bytes, connection_hash: bytes, frame: bytes) -> tuple[int, int, bytes]:
    if len(connection_hash) != 8 or not frame:
        raise ValueError("invalid Classic connection hash or empty frame")
    selector = frame[0]
    if selector not in (2, 3):
        raise ValueError("unsupported Classic key selector")
    signature_length = 4 if selector == 2 else 16
    if len(frame) < 1 + signature_length + 2:
        raise ValueError("truncated Classic signed envelope")
    signature = frame[1 : 1 + signature_length]
    body = frame[1 + signature_length :]
    expected = aes_cmac(key, connection_hash + body)[:signature_length]
    if not hmac.compare_digest(signature, expected):
        raise ValueError("Classic CMAC mismatch")
    return selector, int.from_bytes(body[:2], "big"), body[2:]


def encode_operation(operation: str, target_kind: str, target_id: int | None, payload: bytes, origin: int = 1) -> bytes:
    if operation not in OPERATION_TYPES or target_kind not in OPERATION_TYPES[operation]:
        raise ValueError("unsupported Classic operation/target combination")
    if not 1 <= origin <= 255:
        raise ValueError("Classic origin must roll through 1..255")
    type_byte = OPERATION_TYPES[operation][target_kind] | 0x40
    record = bytearray(3)
    if target_kind == "network":
        if target_id is not None:
            raise ValueError("network target has no id")
    else:
        if target_id is None or not 0 <= target_id <= 255:
            raise ValueError("Classic target id out of range")
        type_byte |= 0x80
        record.append(target_id)
    record[1] = type_byte
    record[2] = origin
    record.append(200)
    record.extend(payload)
    if len(record) > 16:
        raise ValueError("Classic command record exceeds its four-bit length")
    record[0] = 0xF0 | (len(record) - 1)
    return bytes(record)


def parse_operation(data: bytes) -> dict:
    if not 4 <= len(data) <= 16 or data[0] != 0xF0 | (len(data) - 1):
        raise ValueError("invalid Classic command-record length or marker")
    type_byte = data[1]
    if not type_byte & 0x40:
        raise ValueError("full-session operation requires an origin byte")
    offset = 2
    origin = data[offset]
    offset += 1
    target_id = None
    if type_byte & 0x80:
        if offset >= len(data):
            raise ValueError("truncated Classic target")
        target_id = data[offset]
        offset += 1
    if offset >= len(data):
        raise ValueError("truncated Classic lifetime")
    lifetime = data[offset]
    offset += 1
    return {
        "type": type_byte & 0x3F,
        "origin": origin,
        "target_id": target_id,
        "lifetime": lifetime,
        "payload": data[offset:],
    }


def parse_connection_info(data: bytes) -> dict:
    if len(data) not in (8, 13):
        raise ValueError("Classic session read must be 8 or 13 bytes")
    result = {"connection_hash": data[:8]}
    if len(data) == 13:
        unit_id, flags_lo, mtu, protocol, flags_hi = struct.unpack_from(">BBBBB", data, 8)
        if not 5 <= protocol <= 9:
            raise ValueError("unsupported Classic full-session protocol")
        if mtu == 0:
            raise ValueError("Classic MTU must be nonzero")
        result.update(
            unit_id=unit_id,
            flags=flags_lo | (flags_hi << 8),
            mtu=mtu,
            protocol=protocol,
        )
    return result


def parse_incoming(data: bytes) -> list[dict]:
    if not data:
        raise ValueError("empty Classic notification")
    if data[0] in (0x00, 0xFF):
        return []
    if data[0] == 0xF0:
        if len(data) < 3:
            raise ValueError("truncated Classic response")
        return [{"kind": "response", "unit_id": data[1], "origin": data[2], "state": data[3:]}]
    records = []
    offset = 0
    while offset < len(data):
        if len(data) - offset < 2:
            raise ValueError("truncated Classic state header")
        unit_id, flags = data[offset], data[offset + 1]
        offset += 2
        state_length = flags & 0x0F
        level = None
        source = None
        if flags & 0x20:
            if offset >= len(data):
                raise ValueError("truncated Classic level extra")
            level = data[offset]
            offset += 1
        if flags & 0x40:
            if offset >= len(data):
                raise ValueError("truncated Classic source extra")
            source = data[offset]
            offset += 1
        if offset + state_length > len(data):
            raise ValueError("truncated Classic state vector")
        records.append(
            {
                "kind": "unit_state",
                "unit_id": unit_id,
                "on": bool(flags & 0x80),
                "source_flag": bool(flags & 0x10),
                "level": level,
                "source": source,
                "state": data[offset : offset + state_length],
            }
        )
        offset += state_length
    return records


def parse_direct_state(data: bytes) -> dict:
    if len(data) < 2:
        raise ValueError("truncated Classic direct-state header")
    unit_id, flags = data[0], data[1]
    state_length = flags & 0x0F
    offset = 2
    scene_id = None
    if flags & 0x40:
        if offset >= len(data):
            raise ValueError("truncated Classic direct-state scene id")
        scene_id = data[offset]
        offset += 1
    if offset + state_length != len(data):
        raise ValueError("Classic direct-state length mismatch or trailing bytes")
    return {
        "unit_id": unit_id,
        "scene_id": scene_id,
        "state": data[offset:],
    }


def unpack_fixture_state(controls: list[dict], state: bytes) -> dict[str, int]:
    raw = int.from_bytes(state, "little")
    values = {}
    for control in controls:
        if control["offset"] + control["length"] > len(state) * 8:
            raise ValueError("fixture definition exceeds received state")
        values[control["name"]] = (raw >> control["offset"]) & ((1 << control["length"]) - 1)
    return values


def test_aes_cmac_standard_and_classic_golden_vectors():
    key = bytes.fromhex("2b7e151628aed2a6abf7158809cf4f3c")
    message = bytes.fromhex("6bc1bee22e409f96e93d7e117393172a")
    assert aes_cmac(key, message).hex() == "070a16b46b4d4144f79bdd9dd04a287c"
    vectors = details()["test_vectors"]["crypto_session_vectors"]
    for vector in vectors:
        key = bytes.fromhex(vector["key_hex"])
        connection_hash = bytes.fromhex(vector["connhash_hex"])
        body = bytes.fromhex(vector["packet_hex"])
        sequence = int.from_bytes(body[:2], "big")
        payload = body[2:]
        frame = sign_envelope(key, connection_hash, vector["auth_level"], sequence, payload)
        assert frame[:1].hex() == f'{vector["auth_level"]:02x}'
        assert frame[1:-len(body)].hex() == vector["expected_sig_hex"]
        assert frame[1:].hex() == vector["expected_digested_hex"]
        assert frame.hex() == vector["expected_wire_hex"]
        assert verify_envelope(key, connection_hash, frame) == (
            vector["auth_level"],
            sequence,
            payload,
        )
        tampered = bytearray(frame)
        tampered[-1] ^= 1
        with pytest.raises(ValueError):
            verify_envelope(key, connection_hash, bytes(tampered))


def test_all_relevant_classic_session_operation_golden_vectors():
    for vector in details()["test_vectors"]["classic_session_operations"]:
        raw = encode_operation(
            vector["opcode_name"],
            vector["target_type"],
            vector["target_id"],
            bytes.fromhex(vector["payload_hex"]),
        )
        assert raw.hex() == vector["expected_frame_hex"]
        parsed = parse_operation(raw)
        assert parsed["origin"] == 1
        assert parsed["target_id"] == vector["target_id"]
        assert parsed["lifetime"] == 200
        assert parsed["payload"].hex() == vector["payload_hex"]
        with pytest.raises(ValueError):
            parse_operation(raw[:-1])
    for operation, payload in (("SetTemperature", b"\x36"), ("SetColor", b"\xff\x80\x00")):
        with pytest.raises(ValueError):
            encode_operation(operation, "scene", 1, payload)
    operation_types = details()["command_records"]["operation_types"]
    assert "scene_temperature" not in operation_types
    assert "scene_color" not in operation_types
    unsupported = details()["command_records"]["unsupported_scene_operations"]
    assert unsupported["scene_temperature"]["type"] == 2
    assert unsupported["scene_color"]["type"] == 3
    assert all(not item["outgoing_full_session"] for item in unsupported.values())
    with pytest.raises(ValueError):
        encode_operation("SetLevel", "unit", 256, b"\xff")
    with pytest.raises(ValueError):
        encode_operation("SetLevel", "unit", 1, bytes(16))


def test_connection_info_version_and_signed_sequence_boundaries():
    vector = details()["test_vectors"]["connection_info"]
    parsed = parse_connection_info(bytes.fromhex(vector["hex"]))
    assert parsed["connection_hash"].hex() == vector["expected"]["connection_hash_hex"]
    assert parsed["unit_id"] == vector["expected"]["unit_id"]
    assert parsed["flags"] == vector["expected"]["flags"]
    assert parsed["mtu"] == vector["expected"]["mtu"]
    assert parsed["protocol"] == vector["expected"]["protocol"]
    assert parse_connection_info(bytes.fromhex(vector["expected"]["connection_hash_hex"])) == {
        "connection_hash": bytes.fromhex(vector["expected"]["connection_hash_hex"])
    }
    raw = bytes.fromhex(vector["hex"])
    for malformed in (raw[:7], raw + b"\x00", raw[:11] + b"\x04" + raw[12:], raw[:11] + b"\x0a" + raw[12:]):
        with pytest.raises(ValueError):
            parse_connection_info(malformed)
    key = bytes.fromhex("0102030405060708090a0b0c0d0e0f10")
    connection_hash = bytes.fromhex(vector["expected"]["connection_hash_hex"])
    with pytest.raises(ValueError):
        sign_envelope(key, connection_hash, 2, 0, b"\x00\x01\x0b")
    first = sign_envelope(key, connection_hash, 2, 0xFFFF, b"\x00\x01\x0b")
    assert verify_envelope(key, connection_hash, first)[1] == 0xFFFF
    with pytest.raises(ValueError):
        sign_envelope(key, connection_hash[:-1], 2, 1, b"\x00\x01\x0b")


def test_classic_incoming_state_response_and_malformed_cases():
    vector = details()["test_vectors"]["incoming_state"]
    records = parse_incoming(bytes.fromhex(vector["record_hex"]))
    assert records == [
        {
            "kind": "unit_state",
            "unit_id": vector["expected"]["unit_id"],
            "on": vector["expected"]["on"],
            "source_flag": vector["expected"]["source_flag"],
            "level": None,
            "source": None,
            "state": bytes.fromhex(vector["expected"]["state_hex"]),
        }
    ]
    response = parse_incoming(bytes.fromhex(vector["response_hex"]))[0]
    assert response["kind"] == "response"
    assert response["unit_id"] == vector["expected"]["unit_id"]
    assert response["origin"] == 1
    assert response["state"] == bytes.fromhex(vector["expected"]["state_hex"])
    assert parse_incoming(b"\x00configuration") == []
    assert parse_incoming(b"\xffdebug") == []
    transport = details()["security"]["incoming_notifications"]
    assert transport["cmac"] is False
    assert transport["sequence_replay_protection"] is False
    assert transport["encryption"] is False
    assert "no cmac" in details()["incoming_state"]["transport_security"].lower()
    for malformed in (b"", b"\x05", b"\x05\xa2\x10\xaa", b"\x05\x62\x11", b"\xf0\x05"):
        with pytest.raises(ValueError):
            parse_incoming(malformed)


def test_direct_state_layout_and_fixture_requirement():
    vector = details()["test_vectors"]["direct_state"]
    raw = bytes.fromhex(vector["record_hex"])
    assert raw[0] == vector["expected"]["unit_id"]
    assert raw[1] & 0x0F == len(raw) - 3
    assert raw[1] & 0x40
    assert raw[2] == vector["expected"]["scene_id"]
    assert raw[3:].hex() == vector["expected"]["state_hex"]
    assert parse_direct_state(raw) == {
        "unit_id": vector["expected"]["unit_id"],
        "scene_id": vector["expected"]["scene_id"],
        "state": bytes.fromhex(vector["expected"]["state_hex"]),
    }
    for malformed in (b"\x05", b"\x05\x40", raw[:-1], raw + b"\x00"):
        with pytest.raises(ValueError):
            parse_direct_state(malformed)
    fixture = details()["fixture_cache"]["public_examples"]["board_1"]
    assert unpack_fixture_state(fixture["controls"], raw[3:]) == {"dimmer": 128}
    with pytest.raises(ValueError):
        unpack_fixture_state(fixture["controls"], b"")
    with SPEC_PATH.open(encoding="utf-8") as handle:
        document = yaml.safe_load(handle)
    assert document["device"]["integration"] == "identify_only"
    assert document["device"]["testing"]["status"] == "untested"
    protocol = details()
    assert protocol["scope"]["network_protocols"] == [5, 6, 7, 8, 9]
    assert protocol["scope"]["evolution_protocols"] == [10, 11]
    assert protocol["scope"]["unsupported_from_protocol"] == 12
    assert "12 and newer are unsupported" in protocol["exclusions"]["evolution"]
    assert protocol["security"]["payload_encryption"] == "none"
    assert protocol["security"]["integrity"] == "aes-128-cmac"
    assert protocol["exclusions"]["direct_service_uuid"] == "0000fe3d-0000-1000-8000-00805f9b34fb"
    assert all(
        "commands" not in characteristic
        for service in document["services"]
        for characteristic in service["characteristics"]
    )


def test_cloud_provisioning_methods_headers_and_revision():
    flow = details()["cloud_provisioning"]["authorized_flow"]
    assert [(step["method"], step["path"]) for step in flow[:3]] == [
        ("GET", "/network/uuid/<48-bit-network-id>"),
        ("POST", "/network/<id>/session"),
        ("PUT", "/network/<id>/"),
    ]
    sync = flow[2]
    assert sync["json"]["formatVersion"] == 1
    assert sync["json"]["deviceName"] == "<client-name>"
    assert sync["json"]["revision"] == "<cached-revision-or-0>"
    assert sync["headers"] == {"X-Casambi-Session": "<session-from-POST>"}
    assert set(sync["response_handling"]) >= {
        "UPTODATE",
        "MERGED",
        "FETCHED",
        "CONFLICT",
        "HTTP_410",
    }
    assert flow[3]["method"] == "GET"
    assert flow[3]["path"] == "/fixture/<id>"


# Vendor-app internal names this spec used to carry, kept as (length,
# SHA-256 of the lowercased name) so the guard does not reintroduce them.
SCRUBBED_APP_LABELS = (
    (10, "9eed9c01c04bc2120bfd64e5c52f472641503fff6ff96eb6245234f00184358a"),
    (18, "f5b56d016c081ca8817f29276b0749373fa41f956d3de590de499309839d042e"),
    (12, "76e5386a2ede47115ca882ce9f62964500a69a81c0bb50de41665b3f7af2771f"),
    (16, "b703a5153dd25cae23e9766b685afe1162de075563fbbcc2a0bfe7aa63009ad5"),
    (8, "962209de09c51e1bf430f92edd80b57190b70dbce6c981c7f6d0e6d34dd6744e"),
)


def test_vendor_app_internal_names_stay_scrubbed():
    import hashlib
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    text = "".join(
        (root / path).read_text(encoding="utf-8").lower()
        for path in ("device-specs/devices/casambi-classic-ble.yaml", "docs/devices/casambi-classic-ble.md")
    ).encode("utf-8")
    hits = [
        digest
        for length, digest in SCRUBBED_APP_LABELS
        for start in range(len(text) - length + 1)
        if hashlib.sha256(text[start : start + length]).hexdigest() == digest
    ]
    assert hits == []
