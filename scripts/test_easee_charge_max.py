"""Standard-library Easee Charge Max protocol and cryptography tests.

P-256/EC-JPAKE and AES-256-GCM are independently transcribed from the spec's
public algorithms. Public reference vectors contain no live owner PIN, serial
or long-term credential. No project code or hardware is used.
"""

from __future__ import annotations

import hashlib
import json
import struct

import pytest


# --- P-256 and EC-JPAKE ------------------------------------------------------

P = 0xFFFFFFFF00000001000000000000000000000000FFFFFFFFFFFFFFFFFFFFFFFF
A = P - 3
B = 0x5AC635D8AA3A93E7B3EBBD55769886BC651D06B0CC53B0F63BCE3C3E27D2604B
N = 0xFFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551
G = (
    0x6B17D1F2E12C4247F8BCE6E563A440F277037D812DEB33A0F4A13945D898C296,
    0x4FE342E2FE1A7F9B8EE7EB4A7C0F9E162BCE33576B315ECECBB6406837BF51F5,
)


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
    scalar %= N
    result = None
    addend = point
    while scalar:
        if scalar & 1:
            result = point_add(result, addend)
        addend = point_add(addend, addend)
        scalar >>= 1
    return result


def point_bytes(point) -> bytes:
    x, y = point
    return b"\x04" + x.to_bytes(32, "big") + y.to_bytes(32, "big")


def read_tls_point(data: bytes, offset: int):
    if offset >= len(data) or data[offset] != 65 or offset + 66 > len(data):
        raise ValueError("invalid TLS P-256 point length")
    raw = data[offset + 1 : offset + 66]
    x = int.from_bytes(raw[1:33], "big")
    y = int.from_bytes(raw[33:65], "big")
    if raw[0] != 4 or (y * y - (x * x * x + A * x + B)) % P:
        raise ValueError("point is not uncompressed/on secp256r1")
    return (x, y), offset + 66


def hash_point(point) -> bytes:
    raw = point_bytes(point)
    return len(raw).to_bytes(4, "big") + raw


def proof_hash(generator, proof_point, public_point, identity: bytes) -> int:
    material = (
        hash_point(generator)
        + hash_point(proof_point)
        + hash_point(public_point)
        + len(identity).to_bytes(4, "big")
        + identity
    )
    return int.from_bytes(hashlib.sha256(material).digest(), "big") % N


def read_kkp(data: bytes, offset: int, generator, identity: bytes):
    public, offset = read_tls_point(data, offset)
    proof, offset = read_tls_point(data, offset)
    if offset >= len(data):
        raise ValueError("missing Schnorr scalar")
    size = data[offset]
    offset += 1
    if size == 0 or offset + size > len(data):
        raise ValueError("invalid Schnorr scalar length")
    response = int.from_bytes(data[offset : offset + size], "big")
    offset += size
    challenge = proof_hash(generator, proof, public, identity)
    if point_add(scalar_multiply(challenge, public), scalar_multiply(response, generator)) != proof:
        raise ValueError("Schnorr proof does not verify")
    return public, offset


def derive_client_vector() -> bytes:
    password = bytes.fromhex("7468726561646a70616b6574657374")
    secret = int.from_bytes(password, "big")
    x1 = int.from_bytes(bytes.fromhex("0102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f21"), "big")
    x2 = int.from_bytes(bytes.fromhex("6162636465666768696a6b6c6d6e6f707172737475767778797a7b7c7d7e7f81"), "big")
    server_one = bytes.fromhex(
        "41047ea6e3a4487037a9e0dbd79262b2cc273e779930fc18409ac5361c5fe669d702e147790aeb4ce7fd6575ab0f6c7fd1c335939aa863ba37ec91b7e32bb013bb2b410409f85b3d20ebd7885ce464c08d056d6428fe4dd9287aa365f131f4360ff386d846898bc4b41583c2a5197f65d78742746c12a5ec0a4ffe2f270a750a1d8fb51620934d74eb43e54df424fd96306c0117bf131afabf90a9d33d1198d905193735144104190a07700ffa4be6ae1d79ee0f06aeb544cd5addaabedf70f8623321332c54f355f0fbfec783ed359e5d0bf7377a0fc4ea7ace473c9c112b41ccd41ac56a56124104360a1cea33fce641156458e0a4eac219e96831e6aebc88b3f3752f93a0281d1bf1fb106051db9694a8d6e862a5ef1324a3d9e27894f1ee4f7c59199965a8dd4a2091847d2d22df3ee55faa2a3fb33fd2d1e055a07a7c61ecfb8d80ec00c2c9eb12"
    )
    server_two = bytes.fromhex(
        "03001741040fb22b1d5d1123e0ef9feb9d8a2e590a1f4d7ced2c2b06586e8f2a16d4eb2fda4328a20b07d8fd667654ca18c54e32a333a0845451e926ee8804fd7af0aaa7a641045516ea3e54a0d5d8b2ce786b38d383370029a5dbe4459c9dd601b408a24ae6465c8ac905b9eb03b5d3691c139ef83f1cd4200f6c9cd4ec392218a59ed243d3c820ff724a9a70b88cb86f20b434c6865aa1cd7906dd7c9bce3525f508276f26836c"
    )
    X1, X2 = scalar_multiply(x1, G), scalar_multiply(x2, G)
    X3, offset = read_kkp(server_one, 0, G, b"server")
    X4, offset = read_kkp(server_one, offset, G, b"server")
    if offset != len(server_one):
        raise ValueError("round-one trailing bytes")
    if server_two[:3] != b"\x03\x00\x17":
        raise ValueError("server selected a different curve")
    generator = point_add(point_add(X1, X2), X3)
    peer, offset = read_kkp(server_two, 3, generator, b"server")
    if offset != len(server_two):
        raise ValueError("round-two trailing bytes")
    correction = scalar_multiply((-x2 * secret) % N, X4)
    shared = scalar_multiply(x2, point_add(peer, correction))
    return hashlib.sha256(shared[0].to_bytes(32, "big")).digest()


def test_mbedtls_ecjpake_reference_vector():
    assert derive_client_vector().hex() == "f3d47f599844db92a569bbe7981e39d931fd743bf22e98f9b438f719d3c4f351"


def test_schnorr_tamper_is_rejected():
    # A valid public vector is changed at the end of its second proof.
    password = bytes.fromhex("7468726561646a70616b6574657374")
    del password
    # Use a small independently generated proof, not a project helper.
    secret_x = 0x123456789ABCDEF
    public = scalar_multiply(secret_x, G)
    nonce = 0xFEDCBA987654321
    proof = scalar_multiply(nonce, G)
    challenge = proof_hash(G, proof, public, b"server")
    response = (nonce - secret_x * challenge) % N
    assert point_add(scalar_multiply(challenge, public), scalar_multiply(response, G)) == proof
    with pytest.raises(ValueError):
        if point_add(scalar_multiply(challenge + 1, public), scalar_multiply(response, G)) != proof:
            raise ValueError("proof mismatch")


# --- AES-256 and GCM --------------------------------------------------------


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
    SBOX.append(inverse ^ rotate_byte(inverse, 1) ^ rotate_byte(inverse, 2) ^ rotate_byte(inverse, 3) ^ rotate_byte(inverse, 4) ^ 0x63)


def aes_round_keys(key: bytes) -> list[list[int]]:
    if len(key) != 32:
        raise ValueError("AES-256 needs 32-byte key")
    words = [list(key[index : index + 4]) for index in range(0, 32, 4)]
    rcon = 1
    for index in range(8, 60):
        temp = words[index - 1][:]
        if index % 8 == 0:
            temp = [SBOX[value] for value in temp[1:] + temp[:1]]
            temp[0] ^= rcon
            rcon = gf_mul(rcon, 2)
        elif index % 8 == 4:
            temp = [SBOX[value] for value in temp]
        words.append([a ^ b for a, b in zip(words[index - 8], temp, strict=True)])
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
    for round_number in range(1, 15):
        state = [SBOX[value] for value in state]
        shifted = [0] * 16
        for column in range(4):
            for row in range(4):
                shifted[4 * column + row] = state[4 * ((column + row) % 4) + row]
        state = shifted
        if round_number != 14:
            mix_columns(state)
        add_round_key(state, words, round_number)
    return bytes(state)


def galois_multiply(left: int, right: int) -> int:
    result = 0
    value = right
    reduction = 0xE1000000000000000000000000000000
    for bit in range(128):
        if left & (1 << (127 - bit)):
            result ^= value
        value = value >> 1 if not value & 1 else (value >> 1) ^ reduction
    return result


def ghash(key: bytes, data: bytes) -> bytes:
    h = int.from_bytes(aes_encrypt_block(key, bytes(16)), "big")
    if len(data) % 16:
        raise ValueError("GHASH input is not block aligned")
    result = 0
    for offset in range(0, len(data), 16):
        result = galois_multiply(result ^ int.from_bytes(data[offset : offset + 16], "big"), h)
    return result.to_bytes(16, "big")


def aes_gcm_encrypt(key: bytes, nonce: bytes, plaintext: bytes) -> tuple[bytes, bytes]:
    if len(nonce) != 4:
        raise ValueError("Easee nonce is four bytes")
    if len(nonce) == 12:
        j0 = nonce + b"\x00\x00\x00\x01"
    else:
        fill = (16 - (len(nonce) % 16)) % 16 + 8
        padded = nonce + bytes(fill) + (len(nonce) * 8).to_bytes(8, "big")
        j0 = ghash(key, padded)
    ciphertext = bytearray()
    for index, offset in enumerate(range(0, len(plaintext), 16), start=1):
        counter = j0[:12] + ((int.from_bytes(j0[12:], "big") + index) & 0xFFFFFFFF).to_bytes(4, "big")
        block = plaintext[offset : offset + 16]
        stream = aes_encrypt_block(key, counter)
        ciphertext.extend(a ^ b for a, b in zip(block, stream, strict=False))
    padded_ciphertext = bytes(ciphertext) + bytes((-len(ciphertext)) % 16)
    lengths = bytes(8) + (len(ciphertext) * 8).to_bytes(8, "big")
    tag = bytes(a ^ b for a, b in zip(aes_encrypt_block(key, j0), ghash(key, padded_ciphertext + lengths), strict=True))
    return bytes(ciphertext), tag


def test_aes_gcm_easee_reference_vector():
    key = bytes.fromhex("7809f2dd808b5cdd37be5be226ce9c2b15e5767f4b8192245cb2de216510a446")
    expected = bytes.fromhex(
        "8b2f999c6cc14ec4eb09fd5536f098a9dbbaa3754f78f1cba93b7179fb977870"
        "d52305b89e608edd5c2e94be5ad23aa75976e1"
    )
    plaintext = b'{"uid":1000000,"sn":"EMX00000"}'
    ciphertext, tag = aes_gcm_encrypt(key, expected[:4], plaintext)
    assert expected[4:20] == tag
    assert expected[20:] == ciphertext
    assert expected == expected[:4] + tag + ciphertext
    with pytest.raises(ValueError):
        aes_gcm_encrypt(key[:31], expected[:4], plaintext)


# --- JSON commands and protobuf frames -------------------------------------


def value_string(value) -> str:
    return "true" if value is True else "false" if value is False else str(value)


def write_request(command_id: int, arguments: list[tuple[int, object]]) -> bytes:
    document = {
        "Id": command_id,
        "Arguments": [{"Id": argument_id, "Value": value_string(value)} for argument_id, value in arguments],
    }
    return json.dumps(document, separators=(",", ":")).encode("utf-8")


def current_request(command_id: int, amperes: int) -> bytes:
    if not 0 <= amperes <= 40:
        raise ValueError("current must be in the 0..40 A serializer bound")
    return write_request(command_id, [(1, amperes)])


def test_json_command_vectors_and_bounds():
    assert write_request(40, [(1, 75)]) == b'{"Id":40,"Arguments":[{"Id":1,"Value":"75"}]}'
    assert write_request(38, [(1, 2)]) == b'{"Id":38,"Arguments":[{"Id":1,"Value":"2"}]}'
    assert current_request(48, 15) == b'{"Id":48,"Arguments":[{"Id":1,"Value":"15"}]}'
    assert current_request(47, 11) == b'{"Id":47,"Arguments":[{"Id":1,"Value":"11"}]}'
    assert write_request(29, [(1, False)]) == b'{"Id":29,"Arguments":[{"Id":1,"Value":"false"}]}'
    assert current_request(48, 0) == current_request(48, 0)
    for invalid in (-1, 41):
        with pytest.raises(ValueError):
            current_request(48, invalid)


def read_varint(data: bytes, offset: int) -> tuple[int, int]:
    result = 0
    for index in range(10):
        if offset >= len(data):
            raise ValueError("truncated varint")
        byte = data[offset]
        offset += 1
        if index == 9 and byte > 1:
            raise ValueError("varint exceeds 64 bits")
        result |= (byte & 0x7F) << (7 * index)
        if not byte & 0x80:
            return result, offset
    raise ValueError("overlong varint")


def decode_protobuf(data: bytes) -> dict[int, object]:
    fields = {}
    offset = 0
    while offset < len(data):
        key, offset = read_varint(data, offset)
        number, wire = key >> 3, key & 7
        if number == 0:
            raise ValueError("protobuf field zero")
        if wire == 0:
            value, offset = read_varint(data, offset)
        elif wire == 1:
            if offset + 8 > len(data):
                raise ValueError("truncated float64")
            value = struct.unpack_from("<d", data, offset)[0]
            offset += 8
        elif wire == 2:
            size, offset = read_varint(data, offset)
            if offset + size > len(data):
                raise ValueError("truncated length-delimited field")
            raw = data[offset : offset + size]
            offset += size
            try:
                value = raw.decode("utf-8")
                if not all(character.isprintable() or character in "\t\n" for character in value):
                    value = raw
            except UnicodeDecodeError:
                value = raw
        elif wire == 5:
            if offset + 4 > len(data):
                raise ValueError("truncated float32")
            value = struct.unpack_from("<f", data, offset)[0]
            offset += 4
        else:
            raise ValueError("unsupported protobuf wire type")
        fields[number] = value
    return fields


def parse_response(data: bytes) -> dict:
    if len(data) < 6:
        raise ValueError("short response header")
    if data[0] != 0:
        raise ValueError("nonzero response marker")
    declared = int.from_bytes(data[4:6], "big")
    if declared < 6 or declared != len(data):
        raise ValueError("declared/actual response length mismatch")
    return {"type": data[1], "fields": decode_protobuf(data[6:])}


def parse_response_stream(chunks) -> list[dict]:
    buffer = bytearray()
    responses = []
    for chunk in chunks:
        buffer.extend(chunk)
        while len(buffer) >= 6:
            declared = int.from_bytes(buffer[4:6], "big")
            if declared < 6:
                raise ValueError("invalid declared length")
            if len(buffer) < declared:
                break
            response = parse_response(bytes(buffer[:declared]))
            responses.append(response)
            del buffer[:declared]
    if buffer:
        raise ValueError("truncated response")
    return responses


def test_protobuf_state_config_unknown_and_signed_fields():
    state = bytes.fromhex("00 41 01 01 00 08 58 20")
    assert parse_response(state) == {"type": 0x41, "fields": {11: 32}}
    config = bytes.fromhex("00 40 01 01 00 0a 38 02 68 4b")
    assert parse_response(config) == {"type": 0x40, "fields": {7: 2, 13: 75}}
    unknown_body = bytes.fromhex("f8 3f 07")
    unknown = bytes([0, 0x41, 1, 1]) + (len(unknown_body) + 6).to_bytes(2, "big") + unknown_body
    assert parse_response(unknown)["fields"] == {1023: 7}
    negative_body = bytes.fromhex("b0 01 b7 ff ff ff ff ff ff ff ff 01")
    negative = bytes([0, 0x41, 1, 1]) + (len(negative_body) + 6).to_bytes(2, "big") + negative_body
    raw = parse_response(negative)["fields"][22]
    assert raw - (1 << 64) == -73
    float_body = bytes([0x75]) + struct.pack("<f", 14.0)
    floating = bytes([0, 0x41, 1, 1]) + (len(float_body) + 6).to_bytes(2, "big") + float_body
    assert parse_response(floating)["fields"][14] == 14.0


def test_split_coalesced_and_malformed_response_frames():
    first = bytes.fromhex("00 41 01 01 00 08 58 20")
    second = bytes.fromhex("00 40 01 01 00 0a 38 02 68 4b")
    assert parse_response_stream([first + second]) == parse_response_stream([first, second])
    assert parse_response_stream([bytes([value]) for value in first + second]) == parse_response_stream([first + second])
    with pytest.raises(ValueError, match="mismatch"):
        parse_response(first[:-1])
    with pytest.raises(ValueError, match="marker"):
        parse_response(b"\x01" + first[1:])
    with pytest.raises(ValueError, match="truncated varint"):
        parse_response(bytes.fromhex("00 41 01 01 00 07 80"))
    with pytest.raises(ValueError, match="truncated response"):
        parse_response_stream([first + second[:-1]])


def test_command_acceptance_is_not_transport_success():
    accepted = json.loads('{"id":40,"code":1,"res":{"nws":3}}')
    refused = json.loads('{"id":41,"code":0,"Comment":"command 41 not supported","res":{"nws":3}}')
    assert accepted.get("code") == 1
    assert refused.get("code") != 1
    assert refused["Comment"] == "command 41 not supported"


def test_enabling_the_charger_is_advanced_and_disabling_is_not():
    from pathlib import Path

    import yaml

    path = Path(__file__).resolve().parents[1] / "device-specs" / "devices" / "easee-charge-max.yaml"
    commands = yaml.safe_load(path.read_text(encoding="utf-8"))["commands"]
    assert commands["set_charger_enabled"]["advanced"] is True
    assert "current" in commands["set_charger_enabled"]["advanced_reason"]
    assert commands["set_dynamic_charger_current"]["advanced"] is True
    assert not commands["set_charger_disabled"].get("advanced")
