# Copyright 2026 Pigs Can Fly Labs LLC
# SPDX-License-Identifier: Apache-2.0
"""Holds the Coway local-protocol spec to its own stated rules.

`device-specs/devices/coway-air-purifier-local.yaml` documents three wire
layers: the Bluetooth setup messages (P001 key exchange, the AES-256-CBC
P002 Wi-Fi settings, the four-byte fragment header, the identity and scan
replies and the status notifications), the HTTP enrolment exchange the fan
runs against whatever server P002 named, and the JSON-over-MQTT messages it
trades with that server afterwards. This module re-implements each rule
from the spec's prose with nothing but the standard library (AES included,
from FIPS-197, so no crypto package is needed) and checks that the
transcription rebuilds and parses every example the spec carries. Every
value in the vectors is invented: a documentation-range MAC, a placeholder
LAN address and made-up tokens.
"""

from __future__ import annotations

import base64
import json
import re
import struct
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SPEC_PATH = REPO_ROOT / "device-specs" / "devices" / "coway-air-purifier-local.yaml"
DOC_PATH = REPO_ROOT / "docs" / "devices" / "coway-air-purifier-local.md"


# --------------------------------------------------------------------------
# AES (FIPS-197), enough for AES-256-CBC with PKCS#7 in both directions.
# --------------------------------------------------------------------------


def _xtime(a: int) -> int:
    a <<= 1
    return (a ^ 0x11B) & 0xFF if a & 0x100 else a


def _gmul(a: int, b: int) -> int:
    out = 0
    while b:
        if b & 1:
            out ^= a
        a = _xtime(a)
        b >>= 1
    return out


def _build_sbox() -> tuple[list[int], list[int]]:
    sbox = [0] * 256
    for x in range(256):
        # multiplicative inverse in GF(2^8), 0 maps to 0
        inv = 0 if x == 0 else next(y for y in range(1, 256) if _gmul(x, y) == 1)
        s = inv
        for shift in range(1, 5):
            s ^= ((inv << shift) | (inv >> (8 - shift))) & 0xFF
        sbox[x] = s ^ 0x63
    inverse = [0] * 256
    for x, s in enumerate(sbox):
        inverse[s] = x
    return sbox, inverse


SBOX, INV_SBOX = _build_sbox()


def _expand_key(key: bytes) -> list[list[int]]:
    nk = len(key) // 4
    assert nk in (4, 6, 8), "AES key must be 16, 24 or 32 bytes"
    rounds = nk + 6
    words = [list(key[4 * i : 4 * i + 4]) for i in range(nk)]
    rcon = 1
    for i in range(nk, 4 * (rounds + 1)):
        temp = list(words[i - 1])
        if i % nk == 0:
            temp = temp[1:] + temp[:1]
            temp = [SBOX[b] for b in temp]
            temp[0] ^= rcon
            rcon = _xtime(rcon)
        elif nk > 6 and i % nk == 4:
            temp = [SBOX[b] for b in temp]
        words.append([a ^ b for a, b in zip(words[i - nk], temp, strict=True)])
    return [sum(words[4 * r : 4 * r + 4], []) for r in range(rounds + 1)]


def _shift_rows(s: list[int], inverse: bool = False) -> list[int]:
    out = [0] * 16
    for c in range(4):
        for r in range(4):
            src = (c + r) % 4 if not inverse else (c - r) % 4
            out[4 * c + r] = s[4 * src + r]
    return out


def _mix_columns(s: list[int], inverse: bool = False) -> list[int]:
    m = (14, 11, 13, 9) if inverse else (2, 3, 1, 1)
    out = []
    for c in range(4):
        col = s[4 * c : 4 * c + 4]
        for r in range(4):
            out.append(
                _gmul(col[0], m[(0 - r) % 4])
                ^ _gmul(col[1], m[(1 - r) % 4])
                ^ _gmul(col[2], m[(2 - r) % 4])
                ^ _gmul(col[3], m[(3 - r) % 4])
            )
    return out


def aes_encrypt_block(key: bytes, block: bytes) -> bytes:
    keys = _expand_key(key)
    s = [b ^ k for b, k in zip(block, keys[0], strict=True)]
    for rnd in range(1, len(keys)):
        s = [SBOX[b] for b in s]
        s = _shift_rows(s)
        if rnd != len(keys) - 1:
            s = _mix_columns(s)
        s = [b ^ k for b, k in zip(s, keys[rnd], strict=True)]
    return bytes(s)


def aes_decrypt_block(key: bytes, block: bytes) -> bytes:
    keys = _expand_key(key)
    s = [b ^ k for b, k in zip(block, keys[-1], strict=True)]
    for rnd in range(len(keys) - 2, -1, -1):
        s = _shift_rows(s, inverse=True)
        s = [INV_SBOX[b] for b in s]
        s = [b ^ k for b, k in zip(s, keys[rnd], strict=True)]
        if rnd:
            s = _mix_columns(s, inverse=True)
    return bytes(s)


def cbc_encrypt(key: bytes, iv: bytes, plain: bytes) -> bytes:
    pad = 16 - len(plain) % 16
    data = plain + bytes([pad]) * pad
    out, prev = b"", iv
    for i in range(0, len(data), 16):
        prev = aes_encrypt_block(key, bytes(a ^ b for a, b in zip(data[i : i + 16], prev, strict=True)))
        out += prev
    return out


def cbc_decrypt(key: bytes, iv: bytes, cipher: bytes) -> bytes:
    assert len(cipher) % 16 == 0 and cipher
    out, prev = b"", iv
    for i in range(0, len(cipher), 16):
        block = cipher[i : i + 16]
        out += bytes(a ^ b for a, b in zip(aes_decrypt_block(key, block), prev, strict=True))
        prev = block
    pad = out[-1]
    assert 1 <= pad <= 16 and out.endswith(bytes([pad]) * pad), "bad PKCS#7 padding"
    return out[:-pad]


# --------------------------------------------------------------------------
# Protobuf subset: varint (wire type 0) and length-delimited (wire type 2).
# --------------------------------------------------------------------------


def varint(value: int) -> bytes:
    out = bytearray()
    while value > 0x7F:
        out.append((value & 0x7F) | 0x80)
        value >>= 7
    out.append(value)
    return bytes(out)


def encode_proto(fields: dict[int, int | bytes | str]) -> bytes:
    """Ascending field number; a zero integer or an empty string is omitted."""
    out = b""
    for number in sorted(fields):
        value = fields[number]
        if isinstance(value, int):
            if value:
                out += varint(number << 3) + varint(value)
        else:
            data = value.encode() if isinstance(value, str) else value
            if data:
                out += varint((number << 3) | 2) + varint(len(data)) + data
    return out


def decode_proto(data: bytes) -> dict[int, int | bytes]:
    fields: dict[int, int | bytes] = {}
    offset = 0

    def read() -> int:
        nonlocal offset
        value = shift = 0
        while True:
            byte = data[offset]
            offset += 1
            value |= (byte & 0x7F) << shift
            if not byte & 0x80:
                return value
            shift += 7

    while offset < len(data):
        tag = read()
        number, wire = tag >> 3, tag & 7
        assert number and number not in fields, "zero or duplicate field"
        if wire == 0:
            fields[number] = read()
        elif wire == 2:
            length = read()
            fields[number] = data[offset : offset + length]
            offset += length
            assert offset <= len(data), "truncated field"
        else:
            raise AssertionError(f"unsupported wire type {wire}")
    return fields


# --------------------------------------------------------------------------
# The spec's rules, transcribed.
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def spec() -> dict:
    return yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def details(spec) -> dict:
    return spec["protocol_details"]


@pytest.fixture(scope="module")
def vectors(details) -> dict:
    return details["test_vectors"]


def config_field_numbers(details) -> dict[str, int]:
    """name -> field number, read from the spec's own P002 field table."""
    table = details["ble_provisioning"]["p002"]["fields"]
    return {text.split(",")[0].strip(): int(number) for number, text in table.items()}


def p001(key: bytes) -> bytes:
    assert len(key) == 20
    return b"P001" + encode_proto({1: 1, 2: base64.b64encode(key).decode()})


def aes_key(key: bytes, mac: str) -> bytes:
    mac = mac.replace(":", "").upper()
    assert re.fullmatch(r"[0-9A-F]{12}", mac)
    return key + mac.encode()


def p002(plain: bytes, key: bytes, mac: str, iv: bytes) -> bytes:
    return b"P002" + base64.b64encode(iv + cbc_encrypt(aes_key(key, mac), iv, plain))


def open_p002(message: bytes, key: bytes, mac: str) -> bytes:
    assert message.startswith(b"P002")
    raw = base64.b64decode(message[4:], validate=True)
    return cbc_decrypt(aes_key(key, mac), raw[:16], raw[16:])


def fragments(message: bytes, value_size: int = 20) -> list[bytes]:
    body = value_size - 4
    count = -(-len(message) // body)
    return [
        struct.pack("<HH", count, index + 1) + message[index * body : (index + 1) * body]
        for index in range(count)
    ]


def reassemble(parts: list[bytes]) -> bytes:
    out, expected = b"", None
    for position, part in enumerate(parts, start=1):
        count, index = struct.unpack_from("<HH", part)
        expected = count if expected is None else expected
        assert count == expected and index == position, "out-of-order fragment"
        out += part[4:]
    assert expected == len(parts)
    return out


def parse_scan(data: bytes) -> list[dict]:
    assert data[:16] == b"*ICT*SCANRESULT:"
    out = []
    offset = 16
    while offset + 48 <= len(data):
        entry = data[offset : offset + 48]
        if entry[:4] == b"[OK]":
            break
        (length,) = struct.unpack_from("<H", entry, 2)
        assert length <= 32
        (rssi,) = struct.unpack_from("<i", entry, 42)
        out.append(
            {
                "ssid": entry[4 : 4 + length].decode(),
                "bssid": entry[36:42].hex(),
                "rssi": rssi,
                "security": entry[46],
                "channel": entry[47],
            }
        )
        offset += 48
    return out


def build_scan_entry(ssid: str, bssid: str, rssi: int, security: int, channel: int) -> bytes:
    raw = ssid.encode()
    return (
        b"\x00\x00"
        + struct.pack("<H", len(raw))
        + raw.ljust(32, b"\x00")
        + bytes.fromhex(bssid)
        + struct.pack("<i", rssi)
        + bytes([security, channel])
    )


def render(template: str, values: dict) -> str:
    def fill(match: re.Match) -> str:
        assert match.group(1) in values, f"no value for {{{match.group(1)}}}"
        return str(values[match.group(1)])

    return re.sub(r"\{([A-Za-z0-9_]+)\}", fill, template)


def reply_api(api: str) -> str:
    """The spec's rule: a reply's API number is the request's minus one."""
    return api[:-1] + str(int(api[-1]) - 1)


def decode_telemetry(attributes: dict) -> dict:
    out = {}
    for key, name, maximum, remaining in (
        ("A1020.0001", "pm25", None, False),
        ("A1020.0007", "illuminance", None, False),
        ("A1020.0011", "prefilter_remaining", 100, True),
        ("A1020.0012", "max2_remaining", 100, True),
    ):
        if key not in attributes:
            continue
        value = attributes[key]
        if type(value) is not int or value < 0 or (maximum is not None and value > maximum):
            out[name] = None
        else:
            out[name] = 100 - value if remaining else value
    return out


# --------------------------------------------------------------------------
# Tests
# --------------------------------------------------------------------------


def test_aes_transcription_reproduces_fips_197():
    key = bytes(range(32))
    plain = bytes.fromhex("00112233445566778899aabbccddeeff")
    cipher = aes_encrypt_block(key, plain)
    assert cipher.hex() == "8ea2b7ca516745bfeafc49904b496089"  # FIPS-197 C.3
    assert aes_decrypt_block(key, cipher) == plain


def test_identity_is_local0_plus_mac(vectors):
    assert vectors["serial"] == "LOCAL0" + vectors["mac"]
    assert len(vectors["serial"]) == 18
    assert vectors["config"]["serial"] == vectors["serial"]
    assert vectors["config"]["macAddr"] == vectors["mac"]


def test_p001_rebuilds_and_parses(vectors):
    key = vectors["p001_key"].encode()
    message = p001(key)
    assert message.hex() == vectors["p001_hex"]
    fields = decode_proto(message[4:])
    assert fields[1] == 1 and base64.b64decode(fields[2]) == key


def test_fragment_header_rebuilds_and_reassembles(vectors):
    message = bytes.fromhex(vectors["p001_hex"])
    parts = fragments(message)
    assert [p.hex() for p in parts] == vectors["p001_fragments_hex"]
    assert all(len(p) <= 20 for p in parts)
    assert reassemble([bytes.fromhex(h) for h in vectors["p001_fragments_hex"]]) == message
    assert len(fragments(vectors["p002"].encode())) == vectors["p002_fragment_count"]


def test_config_protobuf_follows_the_field_table(details, vectors):
    numbers = config_field_numbers(details)
    assert numbers["cmd"] == 1 and numbers["certSvrUrl"] == 12 and numbers["serial"] == 14
    fields = {numbers[name]: value for name, value in vectors["config"].items()}
    plain = encode_proto(fields)
    assert plain.hex() == vectors["config_protobuf_hex"]
    decoded = decode_proto(plain)
    by_name = {name: decoded[number] for name, number in numbers.items() if number in decoded}
    assert by_name["cmd"] == 2 and by_name["type"] == 1
    assert by_name["caUrl"].decode().startswith("http://")  # the plain-HTTP CA fetch
    assert by_name["certSvrUrl"].decode().startswith("https://")


def test_p002_rebuilds_and_decrypts(details, vectors):
    plain = bytes.fromhex(vectors["config_protobuf_hex"])
    key = vectors["p001_key"].encode()
    iv = vectors["p002_iv"].encode()
    message = p002(plain, key, vectors["mac"], iv)
    assert message.decode() == vectors["p002"]
    assert open_p002(vectors["p002"].encode(), key, vectors["mac"]) == plain
    # 20-byte key + 12-character MAC = a 32-byte (AES-256) key
    assert len(aes_key(key, vectors["mac"])) == 32
    assert "AES-256-CBC" in details["ble_provisioning"]["p002"]["layout"]


def test_cert_server_url_carries_the_bluetooth_name(vectors):
    name = base64.urlsafe_b64encode(vectors["bluetooth_name"].encode()).decode().rstrip("=")
    assert vectors["config"]["certSvrUrl"].endswith("/n/" + name)


def test_identity_reply_parses(vectors):
    fields = decode_proto(bytes.fromhex(vectors["identity_hex"]))
    assert fields[2].decode().replace(":", "").upper() == vectors["mac"]
    assert encode_proto({1: fields[1], 2: fields[2]}).hex() == vectors["identity_hex"]


def test_scan_reply_parses_and_rebuilds(vectors):
    data = bytes.fromhex(vectors["scan_hex"])
    assert parse_scan(data) == [vectors["scan_parsed"]]
    rebuilt = b"*ICT*SCANRESULT:" + build_scan_entry(**vectors["scan_parsed"]) + b"[OK]\r\n"
    assert rebuilt == data


def test_status_notifications_rebuild(spec, vectors):
    codes = spec["payload_formats"]["SetupStatus"]["values"]
    for label, command, code in (
        ("key_accepted", 1, 72),
        ("wifi_connected", 2, 10),
        ("broker_connected", 2, 61),
    ):
        message = encode_proto({1: command, 2: 1, 3: code})
        assert message.hex() == vectors["status_hex"][label]
        assert len(message) == 6
        assert decode_proto(message) == {1: command, 2: 1, 3: code}
        assert str(code) in codes
    assert spec["payload_formats"]["SetupStatus"]["example"] == vectors["status_hex"]["key_accepted"]


def test_enrolment_exchange_is_compact_json(details, vectors):
    request = json.loads(vectors["enrolment_request"])
    assert set(request) == {"macAddr", "certToken", "serial"}
    assert request["serial"] == "LOCAL0" + request["macAddr"]
    reply_text = vectors["enrolment_reply"]
    reply = json.loads(reply_text)
    # The 02F9R rejects a reply with spaces: it must equal its compact rendering.
    assert json.dumps(reply, separators=(",", ":")) == reply_text
    assert reply["header"] == {"success": True, "result": "S1000", "message": "SUCCESS"}
    payload = reply["payload"]
    assert {"host", "port", "certUrl", "privateUrl", "caUrl", "certSvrUrl", "svcCode"} <= set(payload)
    assert payload["port"] == details["server_roles"]["broker"]["default_port"] == 9883
    assert payload["svcCode"] == "002AIR007"
    assert payload["caUrl"] == vectors["config"]["caUrl"]
    assert payload["certToken"] == request["certToken"] == vectors["config"]["certToken"]


def test_mqtt_commands_render_their_examples(spec):
    request_id = re.compile(r"\d{13}-22")
    for name, command in spec["commands"].items():
        assert command["transport"] == "mqtt"
        assert command["path"] == "IoCare/MControl/002AIR007/{serial}"
        assert command["verification"] == "reported"
        example = json.loads(command["example_body"])
        header = example["header"]
        assert request_id.fullmatch(header["requestId"]), name
        values = {"request_id": header["requestId"], "serial": header["prodId"]}
        for attribute, value in example["attributes"].items():
            placeholder = re.search(
                r'"' + re.escape(attribute) + r'":\{([A-Za-z0-9_]+)\}', command["body"]
            )
            assert placeholder, f"{name}: body does not carry {attribute}"
            values[placeholder.group(1)] = value
            parameter = command["parameters"][placeholder.group(1)]
            if "enum" in parameter:
                assert value in parameter["enum"], name
            assert attribute.startswith(header["API_NO"] + ".")
        rendered = render(command["body"], values)
        assert rendered == command["example_body"], name
        assert json.loads(rendered) == example
        for reply in command.get("returns") or []:
            assert reply["name"] == reply_api(header["API_NO"]), name


def test_reply_numbering_rule(spec):
    values = spec["payload_formats"]["CowayMessage"]["values"]
    for request in ("A1011", "A1013", "A1051"):
        assert reply_api(request) in values


def test_state_example_parses(spec):
    message = json.loads(spec["payload_formats"]["CowayMessage"]["example"])
    assert message["header"]["API_NO"] == "A1010"
    settings = {key.split(".", 1)[1]: value for key, value in message["attributes"].items()}
    suffixes = {f["name"] for f in spec["payload_formats"]["SettingAttributes"]["fields"]}
    assert set(settings) <= suffixes
    assert settings["0001"] == 1 and settings["0003"] in (1, 2, 3)


def test_telemetry_example_decodes(spec, vectors):
    message = json.loads(spec["payload_formats"]["TelemetryAttributes"]["example"])
    assert message["header"]["API_NO"] == "A1020"
    assert decode_telemetry(message["attributes"]) == vectors["telemetry_decoded"]
    assert decode_telemetry({"A1020.0011": 101, "A1020.0001": -1}) == {
        "prefilter_remaining": None,
        "pm25": None,
    }


def test_key_facts_are_pinned(spec, details):
    device = spec["device"]
    assert device["manufacturer_status"] == "active"
    assert device["testing"]["status"] == "untested"
    assert device["protocol"] == "wifi" and device["transport"] == "mqtts"
    assert "security_advisory" not in device  # prose note only; an advisory would hide the controls
    assert "plain HTTP" in device["notes"]
    roles = details["server_roles"]
    assert roles["ca_download"]["scheme"] == "http" and roles["ca_download"]["default_port"] == 8080
    assert roles["enrolment"]["scheme"] == "https" and roles["enrolment"]["default_port"] == 9443
    assert "AES128-SHA256" in roles["tls"]["cipher"]
    hotspot = device["setup"]["methods"][1]
    assert hotspot["softap"]["port"] == 5040 and hotspot["softap"]["open_network"] is True
    topics = {t["topic"]: t for t in spec["mqtt_topics"]}
    assert topics["IoCare/MControl/002AIR007/{serial}"]["direction"] == "publish"
    assert "$aws/rules/AIR/IoCare/BEvent/002AIR007/{serial}" in topics
    assert "IoCare/MEvent/002AIR007/{serial}" in topics


def test_firmware_update_unknowns_are_marked_unknown(spec):
    (feature,) = [f for f in spec["features"] if f["type"] == "firmware_update"]
    dfu = feature["dfu"]
    assert dfu["mechanisms"] == ["unknown"]
    assert dfu["image"]["signing"] == "unknown" and dfu["image"]["source"] == "unknown"
    assert dfu["enter"]["how"] == "unknown"
    assert dfu["recovery"]["interrupted"] == "unknown"
    assert dfu["verification"] == "hypothesis"


def test_doc_page_exists_and_states_the_plain_http_fetch():
    text = DOC_PATH.read_text(encoding="utf-8")
    assert "coway-air-purifier-local.yaml" in text
    assert "plain HTTP" in " ".join(text.split())
