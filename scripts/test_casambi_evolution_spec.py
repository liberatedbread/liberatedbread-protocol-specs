"""Independent Casambi Evolution vectors using only the standard library.

PyYAML reads the document; every cryptographic and wire algorithm below is an
independent transcription. No Casambi client, project helper, hardware, owner
key, network topology, or cloud credential is used.
"""

from __future__ import annotations

import hashlib
import hmac
import struct
from pathlib import Path

import pytest
import yaml

SPEC_PATH = Path(__file__).resolve().parent.parent / "device-specs/devices/casambi-evolution-ble.yaml"

P = 0xFFFFFFFF00000001000000000000000000000000FFFFFFFFFFFFFFFFFFFFFFFF
A = P - 3
B = 0x5AC635D8AA3A93E7B3EBBD55769886BC651D06B0CC53B0F63BCE3C3E27D2604B
N = 0xFFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551
G = (
    0x6B17D1F2E12C4247F8BCE6E563A440F277037D812DEB33A0F4A13945D898C296,
    0x4FE342E2FE1A7F9B8EE7EB4A7C0F9E162BCE33576B315ECECBB6406837BF51F5,
)


def details() -> dict:
    with SPEC_PATH.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)["protocol_details"]


def point_add(left, right):
    if left is None:
        return right
    if right is None:
        return left
    x1, y1 = left
    x2, y2 = right
    if x1 == x2 and (y1 != y2 or y1 == 0):
        return None
    if left == right:
        slope = (3 * x1 * x1 + A) * pow(2 * y1, -1, P) % P
    else:
        slope = (y2 - y1) * pow(x2 - x1, -1, P) % P
    x3 = (slope * slope - x1 - x2) % P
    y3 = (slope * (x1 - x3) - y1) % P
    return x3, y3


def scalar_multiply(scalar: int, point):
    if not 1 <= scalar < N:
        raise ValueError("P-256 private scalar out of range")
    result = None
    addend = point
    while scalar:
        if scalar & 1:
            result = point_add(result, addend)
        addend = point_add(addend, addend)
        scalar >>= 1
    if result is None:
        raise ValueError("P-256 point at infinity")
    return result


def decode_public_key(data: bytes):
    if len(data) != 64:
        raise ValueError("P-256 public key must contain two 32-byte coordinates")
    x = int.from_bytes(data[:32], "little")
    y = int.from_bytes(data[32:], "little")
    if not (0 <= x < P and 0 <= y < P):
        raise ValueError("P-256 coordinate out of range")
    if (y * y - (x * x * x + A * x + B)) % P:
        raise ValueError("P-256 public key is not on the curve")
    return x, y


def derive_transport_key(client_private: int, node_public) -> tuple[bytes, bytes]:
    shared = scalar_multiply(client_private, node_public)
    secret = shared[0].to_bytes(32, "big")
    digest = hashlib.sha256(secret[::-1]).digest()
    key = bytes(left ^ right for left, right in zip(digest[:16], digest[16:], strict=True))
    return secret, key


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


def directional_nonce(base: bytes, packet_counter: int, outgoing: bool) -> bytes:
    if len(base) != 16 or not 0 < packet_counter <= 0xFFFFFFFF:
        raise ValueError("invalid nonce base or packet counter")
    counter = packet_counter.to_bytes(4, "little")
    return base[:4] + counter + base[8:] if outgoing else counter + base[4:]


def aes_ctr(key: bytes, nonce: bytes, data: bytes) -> bytes:
    if len(nonce) != 16:
        raise ValueError("CTR nonce must be 16 bytes")
    result = bytearray()
    for block_counter, offset in enumerate(range(0, len(data), 16)):
        block_nonce = nonce[:12] + block_counter.to_bytes(4, "little")
        stream = aes_encrypt_block(key, block_nonce)
        chunk = data[offset : offset + 16]
        result.extend(a ^ b for a, b in zip(chunk, stream, strict=False))
    return bytes(result)


def seal_packet(key: bytes, nonce: bytes, packet_counter: int, plaintext: bytes) -> bytes:
    clear_counter = packet_counter.to_bytes(4, "little")
    ciphertext = aes_ctr(key, nonce, plaintext)
    authenticated = clear_counter + ciphertext
    return authenticated + aes_cmac(key, authenticated)


def open_packet(key: bytes, base_nonce: bytes, frame: bytes, last_counter: int) -> tuple[int, bytes]:
    if len(frame) < 20:
        raise ValueError("encrypted packet is too short")
    counter = int.from_bytes(frame[:4], "little")
    if not 0 < counter - last_counter < 100:
        raise ValueError("packet counter outside the receive window")
    authenticated, tag = frame[:-16], frame[-16:]
    if not hmac.compare_digest(aes_cmac(key, authenticated), tag):
        raise ValueError("CMAC mismatch")
    nonce = directional_nonce(base_nonce, counter, outgoing=False)
    return counter, aes_ctr(key, nonce, authenticated[4:])


def parse_node_info(data: bytes) -> dict:
    if len(data) != 23 or data[0] != 1:
        raise ValueError("node-information packet must be exactly 23 bytes and type 1")
    version = data[1] & 0x1F
    mtu = data[2]
    unit_id, flags = struct.unpack_from(">HH", data, 3)
    if version not in (10, 11):
        raise ValueError("unsupported Evolution network protocol")
    if not 1 <= mtu <= 517:
        raise ValueError("node-information packet MTU out of range")
    if unit_id > 255:
        raise ValueError("node-information packet unit id out of range")
    return {
        "raw_version": data[1],
        "protocol": version,
        "mtu": mtu,
        "unit_id": unit_id,
        "flags": flags,
        "nonce": data[7:],
    }


def pack_xy(x: int, y: int) -> bytes:
    if not (0 <= x <= 2047 and 0 <= y <= 2047):
        raise ValueError("XY coordinate out of 11-bit range")
    return ((x << 11) | y).to_bytes(3, "little")


def encode_invocation(opcode: int, target: int, payload: bytes, origin: int = 1) -> bytes:
    if not 0 <= opcode <= 255 or not 0 <= target <= 0xFFFF:
        raise ValueError("invocation opcode or target out of range")
    if not 1 <= origin <= 0xFFFF or len(payload) > 63:
        raise ValueError("invocation origin or payload length out of range")
    header = (5 << 11) | len(payload)
    return struct.pack(">HBHHH", header, opcode, origin, target, 0) + payload


def parse_invocations(data: bytes) -> list[dict]:
    records = []
    offset = 0
    while offset < len(data):
        if len(data) - offset < 9:
            raise ValueError("trailing or truncated invocation header")
        header, opcode, origin, target, age = struct.unpack_from(">HBHHH", data, offset)
        offset += 9
        origin_handle = None
        if header & 0x0200:
            if offset >= len(data):
                raise ValueError("truncated origin handle")
            origin_handle = data[offset]
            offset += 1
        length = header & 0x3F
        if offset + length > len(data):
            raise ValueError("truncated invocation payload")
        records.append(
            {
                "header": header,
                "opcode": opcode,
                "origin": origin,
                "target": target,
                "age": age,
                "origin_handle": origin_handle,
                "payload": data[offset : offset + length],
            }
        )
        offset += length
    return records


def pack_fixture_state(controls: list[dict], values: dict[str, int], state_length: int) -> bytes:
    result = bytearray(state_length)
    for control in controls:
        name = control["name"]
        value = values[name]
        offset = control["offset"]
        length = control["length"]
        if not 0 <= value < 1 << length:
            raise ValueError("fixture control value out of range")
        if offset + length > state_length * 8:
            raise ValueError("fixture control exceeds state vector")
        result_int = int.from_bytes(result, "little")
        result_int |= value << offset
        result = bytearray(result_int.to_bytes(state_length, "little"))
    return bytes(result)


def unpack_fixture_state(controls: list[dict], state: bytes) -> dict[str, int]:
    raw = int.from_bytes(state, "little")
    values = {}
    for control in controls:
        if control["offset"] + control["length"] > len(state) * 8:
            raise ValueError("fixture definition exceeds received state")
        values[control["name"]] = (raw >> control["offset"]) & ((1 << control["length"]) - 1)
    return values


def parse_state_records(data: bytes) -> list[dict]:
    records = []
    offset = 0
    while offset < len(data):
        if len(data) - offset < 4:
            raise ValueError("trailing or truncated unit-state header")
        unit_id, flags, state_info = struct.unpack_from(">BBB", data, offset)
        offset += 3
        extras = {}
        for bit, name in ((0x04, "con"), (0x08, "sid"), (0x10, "level")):
            if flags & bit:
                if offset >= len(data):
                    raise ValueError("truncated unit-state extra")
                extras[name] = data[offset]
                offset += 1
        state_length = (state_info >> 4) + 1
        padding = flags >> 6
        if offset + state_length + padding > len(data):
            raise ValueError("truncated unit-state vector or padding")
        records.append(
            {
                "unit_id": unit_id,
                "on": bool(flags & 1),
                "online": bool(flags & 2),
                "priority": state_info & 0x0F,
                "state": data[offset : offset + state_length],
                "padding": data[offset + state_length : offset + state_length + padding],
                **extras,
            }
        )
        if "level" not in extras:
            records[-1]["level"] = 255
        offset += state_length + padding
    return records


def test_aes128_and_cmac_primitive_vectors():
    key = bytes.fromhex("000102030405060708090a0b0c0d0e0f")
    plaintext = bytes.fromhex("00112233445566778899aabbccddeeff")
    assert aes_encrypt_block(key, plaintext).hex() == "69c4e0d86a7b0430d8cdb78070b4c55a"
    assert aes_cmac(bytes.fromhex("2b7e151628aed2a6abf7158809cf4f3c"), b"").hex() == (
        "bb1d6929e95937287fa37d129b756746"
    )
    message = bytes.fromhex("6bc1bee22e409f96e93d7e117393172a")
    assert aes_cmac(bytes.fromhex("2b7e151628aed2a6abf7158809cf4f3c"), message).hex() == (
        "070a16b46b4d4144f79bdd9dd04a287c"
    )


def test_node_info_vector_and_malformed_cases():
    vector = details()["test_vectors"]["node_info"]
    parsed = parse_node_info(bytes.fromhex(vector["hex"]))
    assert parsed["raw_version"] == vector["expected"]["raw_version"]
    assert parsed["protocol"] == vector["expected"]["protocol"]
    assert parsed["mtu"] == vector["expected"]["mtu"]
    assert parsed["unit_id"] == vector["expected"]["unit_id"]
    assert parsed["flags"] == vector["expected"]["flags"]
    assert parsed["nonce"].hex() == vector["expected"]["nonce_hex"]
    raw = bytes.fromhex(vector["hex"])
    mutations = [raw[:-1], raw + b"\x00", b"\x02" + raw[1:]]
    mutations += [raw[:1] + bytes([version]) + raw[2:] for version in (9, 12)]
    mutations += [raw[:2] + b"\x00" + raw[3:], raw[:3] + b"\x01\x00" + raw[5:]]
    for malformed in mutations:
        with pytest.raises(ValueError):
            parse_node_info(malformed)


def test_fresh_p256_ecdh_and_transport_key_vector():
    vector = details()["test_vectors"]["ecdh"]
    client_private = int(vector["client_private_hex"], 16)
    node_private = int(vector["node_private_hex"], 16)
    client_public = scalar_multiply(client_private, G)
    node_public = scalar_multiply(node_private, G)
    assert client_public[0].to_bytes(32, "little").hex() == vector["client_public_x_le_hex"]
    assert client_public[1].to_bytes(32, "little").hex() == vector["client_public_y_le_hex"]
    assert node_public[0].to_bytes(32, "little").hex() == vector["node_public_x_le_hex"]
    assert node_public[1].to_bytes(32, "little").hex() == vector["node_public_y_le_hex"]
    decoded = decode_public_key(bytes.fromhex(vector["node_public_key_le_hex"]))
    assert decoded == node_public
    secret, key = derive_transport_key(client_private, decoded)
    assert secret.hex() == vector["shared_secret_hex"]
    assert hashlib.sha256(secret[::-1]).hexdigest() == vector["reversed_secret_sha256_hex"]
    assert key.hex() == vector["transport_key_hex"]
    reverse_secret, reverse_key = derive_transport_key(node_private, client_public)
    assert reverse_secret == secret
    assert reverse_key == key
    with pytest.raises(ValueError):
        decode_public_key(bytes.fromhex(vector["node_public_key_le_hex"])[:-1])
    with pytest.raises(ValueError):
        decode_public_key(bytes(64))


def test_fresh_auth_ctr_cmac_and_directional_packet_vectors():
    vectors = details()["test_vectors"]
    base_nonce = bytes.fromhex(vectors["node_info"]["expected"]["nonce_hex"])
    network_key = bytes.fromhex(vectors["secure_session"]["network_key_hex"])
    key_id = vectors["secure_session"]["key_id"]
    transport_key = bytes.fromhex(vectors["ecdh"]["transport_key_hex"])
    digest = hashlib.sha256(
        network_key + base_nonce + transport_key
    ).digest()
    auth_plaintext = b"\x04" + bytes([key_id]) + digest
    assert auth_plaintext.hex() == vectors["secure_session"]["auth_plaintext_hex"]
    for name, outgoing in (
        ("outgoing_auth", True),
        ("outgoing_invocation", True),
        ("incoming_state", False),
    ):
        vector = vectors["secure_session"][name]
        plaintext = bytes.fromhex(vector["plaintext_hex"])
        counter = vector["counter"]
        nonce = directional_nonce(base_nonce, counter, outgoing=outgoing)
        assert nonce.hex() == vector["nonce_hex"]
        ciphertext = aes_ctr(transport_key, nonce, plaintext)
        assert ciphertext.hex() == vector["ciphertext_hex"]
        frame = seal_packet(transport_key, nonce, counter, plaintext)
        assert frame.hex() == vector["frame_hex"]
        assert frame[-16:].hex() == vector["cmac_hex"]
        if name == "outgoing_invocation":
            stream = aes_ctr(transport_key, nonce, bytes(len(plaintext)))
            assert stream.hex() == vector["keystream_hex"]
        if not outgoing:
            last, decoded = open_packet(transport_key, base_nonce, frame, counter - 1)
            assert last == counter
            assert decoded == plaintext
            with pytest.raises(ValueError):
                open_packet(transport_key, base_nonce, frame, counter)
            tampered = bytearray(frame)
            tampered[-1] ^= 1
            with pytest.raises(ValueError):
                open_packet(transport_key, base_nonce, bytes(tampered), counter - 1)


def test_invocation_opcode_target_and_malformed_vectors():
    vectors = details()["test_vectors"]["invocations"]
    for vector in vectors:
        raw = encode_invocation(
            vector["opcode"], vector["target"], bytes.fromhex(vector["payload_hex"])
        )
        assert raw.hex() == vector["raw_hex"]
        parsed = parse_invocations(raw)
        assert parsed[0]["opcode"] == vector["opcode"]
        assert parsed[0]["target"] == vector["target"]
        assert parsed[0]["payload"].hex() == vector["payload_hex"]
        if vector["opcode"] == 54:
            assert pack_xy(512, 1024).hex() == "000410"
            assert vector["payload_hex"] == "000410"
            with pytest.raises(ValueError):
                pack_xy(2048, 0)
        if vector["name"] == "set_level_unit_bitmap_16_17_20":
            payload = parsed[0]["payload"]
            base = payload[1]
            bitmap = payload[2:]
            units = [
                base + byte_index * 8 + bit
                for byte_index, byte in enumerate(bitmap)
                for bit in range(8)
                if byte & (1 << bit)
            ]
            assert parsed[0]["target"] >> 8 == 1
            assert units == [16, 17, 20]
        with pytest.raises(ValueError):
            parse_invocations(raw[:-1])
    level = vectors[0]
    with pytest.raises(ValueError):
        encode_invocation(1, 0x0501, bytes(64))
    with pytest.raises(ValueError):
        parse_invocations(bytes.fromhex(level["raw_hex"]) + b"\x00")
    with_handle = bytearray.fromhex(level["raw_hex"])
    with_handle[0:2] = (int.from_bytes(with_handle[:2], "big") | 0x0200).to_bytes(2, "big")
    with_handle[9:9] = b"\x7f"
    parsed = parse_invocations(bytes(with_handle))
    assert parsed[0]["origin_handle"] == 0x7F
    assert parsed[0]["payload"].hex() == level["payload_hex"]
    with pytest.raises(ValueError):
        parse_invocations(bytes(with_handle[:9]))


def test_fresh_fixture_state_and_unit_record_vector():
    protocol = details()
    fixture = protocol["fixture_cache"]["public_examples"]["cbu_dcs_9000"]
    vector = protocol["test_vectors"]["state"]
    offsets = {control["name"]: control["offset"] for control in fixture["controls"]}
    assert offsets["x"] == 47
    assert offsets["y"] == 36
    state = pack_fixture_state(fixture["controls"], vector["control_values"], fixture["state_length"])
    assert state.hex() == vector["state_hex"]
    assert unpack_fixture_state(fixture["controls"], state) == vector["control_values"]
    assert vector["expected"]["temperature_k"] == int(
        (vector["control_values"]["temperature_raw"] / 255) * 3800 + 2700
    )
    assert vector["expected"]["hue_normalized"] == vector["control_values"]["hue"] / 1023
    assert vector["expected"]["saturation_normalized"] == vector["control_values"]["saturation"] / 255
    assert vector["expected"]["x_normalized"] == vector["control_values"]["x"] / 2047
    assert vector["expected"]["y_normalized"] == vector["control_values"]["y"] / 2047
    record = bytes.fromhex(vector["record_hex"])
    parsed = parse_state_records(record)
    assert len(parsed) == 1
    item = parsed[0]
    assert item["unit_id"] == vector["expected"]["unit_id"]
    assert item["on"] is True
    assert item["online"] is True
    assert item["con"] == vector["expected"]["con"]
    assert item["sid"] == vector["expected"]["sid"]
    assert item["level"] == vector["expected"]["level"]
    assert item["priority"] == vector["expected"]["priority"]
    assert item["state"] == state
    assert item["padding"] == bytes(2)
    for malformed in (record[:3], record[:4], record[:-1], record + b"\x00"):
        with pytest.raises(ValueError):
            parse_state_records(malformed)
    with pytest.raises(ValueError):
        unpack_fixture_state(fixture["controls"], state[:-1])


def test_public_simple_fixture_and_scope():
    protocol = details()
    fixture = protocol["fixture_cache"]["public_examples"]["board_1"]
    state = pack_fixture_state(fixture["controls"], {"dimmer": 128}, fixture["state_length"])
    assert state == b"\x80"
    assert unpack_fixture_state(fixture["controls"], state) == {"dimmer": 128}
    assert protocol["scope"]["network_protocols"] == [10, 11]
    assert 12 in protocol["scope"]["unsupported_versions"]
    with SPEC_PATH.open(encoding="utf-8") as handle:
        document = yaml.safe_load(handle)
    assert document["device"]["integration"] == "identify_only"
    assert document["device"]["testing"]["status"] == "untested"
    assert all("commands" not in service for service in document["services"])
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


def test_no_dual_automatic_generation_selection():
    paths = [
        SPEC_PATH,
        SPEC_PATH.with_name("casambi-classic-ble.yaml"),
    ]
    for path in paths:
        with path.open(encoding="utf-8") as handle:
            document = yaml.safe_load(handle)
        identification = document["device"]["identification"]
        assert "service_uuids" not in identification
        assert "manufacturer_data" not in identification
        discovery = document["device"]["discovery"]
        assert "methods" not in discovery
        assert "never select both" in discovery["none"]
        assert document["protocol_details"]["scope"]["automatic_selection"] is False
        assert document["protocol_details"]["advertisements"]["generic_matcher"] is False


# Vendor-app internal names this spec used to carry, kept as (length,
# SHA-256 of the lowercased name) so the guard does not reintroduce them.
SCRUBBED_APP_LABELS = (
    (8, "962209de09c51e1bf430f92edd80b57190b70dbce6c981c7f6d0e6d34dd6744e"),
)


def test_vendor_app_internal_names_stay_scrubbed():
    import hashlib
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    text = "".join(
        (root / path).read_text(encoding="utf-8").lower()
        for path in ("device-specs/devices/casambi-evolution-ble.yaml", "docs/devices/casambi-evolution-ble.md")
    ).encode("utf-8")
    hits = [
        digest
        for length, digest in SCRUBBED_APP_LABELS
        for start in range(len(text) - length + 1)
        if hashlib.sha256(text[start : start + length]).hexdigest() == digest
    ]
    assert hits == []
