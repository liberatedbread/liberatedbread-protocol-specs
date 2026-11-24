"""Proves the Fitbit Aria (FB201) spec can be implemented from the spec alone.

`device-specs/devices/fitbit-aria-wifi-scale.yaml` documents a scale that is an
HTTP *client*: the owner runs a small server and answers the vendor hostname
with it. The spec claims to carry everything that server needs. This module is
how that claim is kept honest.

Everything below is an independent transcription of what the YAML says, using
the standard library plus PyYAML and pytest and importing none of this
repository's code. The request and reply bytes are BUILT from the spec's own
offset tables, length formulas, enumerations and CRC parameters, then compared
byte for byte with the hex vectors the spec publishes and parsed back to the
decoded values it declares. Change an offset, a size, a scale or an enum value
in the YAML and something here fails.

The vectors are synthetic (documentation-range MAC, invented auth code, round
timestamps) and were never sent to a scale. Passing proves the document is
internally consistent and complete enough to build from; it proves nothing
about hardware, which this project has not driven.

The second half pins what an owner acts on: that nothing in the file signals
a firmware update, that the vendor's pairing cut-off is stated as already
past, that the route which cannot be undone is marked as such at the step
itself, and that unsettled facts are recorded as two readings, not as a
constant. The last part reads the device page: its hand-written layout tables
are compared with the fields they restate, and the warnings an owner meets
there are pinned sentence by sentence.

There is no server implementation here on purpose. The spec is the product.
"""

from __future__ import annotations

import binascii
import re
import struct
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
STEM = "fitbit-aria-wifi-scale"
SPEC_PATH = ROOT / "device-specs" / "devices" / f"{STEM}.yaml"
PAGE_PATH = ROOT / "docs" / "devices" / f"{STEM}.md"

SPEC_TEXT = SPEC_PATH.read_text(encoding="utf-8")
SPEC = yaml.safe_load(SPEC_TEXT)
FORMATS = SPEC["payload_formats"]
DETAILS = SPEC["protocol_details"]
SERVER = DETAILS["upload_server"]
MESSAGES = SERVER["messages"]
CRC = SERVER["crc"]
VECTORS = SERVER["test_vectors"]
REFUSAL = SERVER["firmware_update_refusal"]

REQUEST_VECTORS = ["upload_request_two_records", "upload_request_no_records"]
# What a server built from the spec sends.
LOCAL_REPLY_VECTORS = ["upload_reply_one_user", "upload_reply_no_users", "upload_reply_two_users"]
# The shape of what the vendor's server sent; for parsers and relays only.
VENDOR_FORM_VECTORS = ["vendor_form_reply_one_user"]
REPLY_VECTORS = LOCAL_REPLY_VECTORS + VENDOR_FORM_VECTORS

INTEGER_WIDTHS = {"uint8": 1, "uint16": 2, "uint32": 4}


# ── Transcription of the spec ────────────────────────────────────────────────
#
# Nothing here imports our own code. Each function names the spec block it
# reads, so a failure points at the table that needs fixing.


def crc16(data: bytes, params: dict = CRC) -> int:
    """Per protocol_details.upload_server.crc: bit-at-a-time, no reflection."""
    width = params["width_bits"]
    assert width == 16, "the transcription covers the declared 16-bit CRC only"
    assert params["reflect_input"] is False and params["reflect_output"] is False
    top, mask = 1 << (width - 1), (1 << width) - 1
    crc = params["initial_value"]
    for byte in data:
        crc ^= byte << (width - 8)
        for _ in range(8):
            crc = ((crc << 1) ^ params["polynomial"]) & mask if crc & top else (crc << 1) & mask
    return crc ^ params["final_xor"]


def field_of(fmt: str, name: str) -> dict:
    return next(f for f in FORMATS[fmt]["fields"] if f["name"] == name)


def raw_value(field: dict, value):
    """An enumerated field is written by label in the vectors; map it back."""
    if isinstance(value, str) and field["type"] in INTEGER_WIDTHS:
        by_label = {label: raw for raw, label in field["values"].items()}
        return by_label[value]
    return value


def pack_field(field: dict, value) -> bytes:
    """Per the field keys every payload_formats table declares."""
    kind, length = field["type"], field["length"]
    value = raw_value(field, value)
    if kind in INTEGER_WIDTHS:
        assert INTEGER_WIDTHS[kind] == length, field["name"]
        order = "little" if length == 1 else field["endianness"]
        return int(value).to_bytes(length, order)
    if kind == "float32":
        assert length == 4, field["name"]
        return struct.pack("<f" if field["endianness"] == "little" else ">f", value)
    if kind == "bytes":
        data = bytes.fromhex(value)
        assert len(data) == length == field["min_length"] == field["max_length"], field["name"]
        return data
    if kind == "string":
        data = value.encode(field["encoding"])[: field["truncate_to_bytes"]]
        assert field["truncate_to_bytes"] == length, field["name"]
        return data + bytes([field["pad_byte"]]) * (length - len(data))
    raise AssertionError(f"undocumented field type {kind!r}")


def unpack_field(field: dict, data: bytes):
    kind, length = field["type"], field["length"]
    assert len(data) == length, field["name"]
    if kind in INTEGER_WIDTHS:
        return int.from_bytes(data, "little" if length == 1 else field["endianness"])
    if kind == "float32":
        return struct.unpack("<f" if field["endianness"] == "little" else ">f", data)[0]
    if kind == "bytes":
        return data.hex()
    if kind == "string":
        return data.rstrip(bytes([field["pad_byte"]])).decode(field["encoding"])
    raise AssertionError(f"undocumented field type {kind!r}")


def build_struct(fmt: dict, values: dict) -> bytes:
    """Lay the fields down in offset order; they must tile with no gap or overlap."""
    out = bytearray()
    for field in sorted(fmt["fields"], key=lambda f: f["offset"]):
        assert field["offset"] == len(out), f"{field['name']} does not start where the last field ended"
        if field["name"] in values:
            value = values[field["name"]]
        else:
            value = field["constant"] if "constant" in field else field["server_sends"]
        out += pack_field(field, value)
    return bytes(out)


def parse_struct(fmt: dict, data: bytes) -> dict:
    return {
        field["name"]: unpack_field(field, data[field["offset"] : field["offset"] + field["length"]])
        for field in fmt["fields"]
    }


def section_start(section: dict, count: int) -> int:
    if "offset" in section:
        return section["offset"]
    per = section.get("offset_per_record", section.get("offset_per_user"))
    return section["offset_base"] + per * count


def build_message(message: dict, parts: dict, count: int) -> bytes:
    """Per protocol_details.upload_server.messages.*.sections.

    `parts` maps a format name to its values: a dict for a `repeat: once`
    section, a list for a repeated one, or a callable taking the bytes built
    so far for a trailer that is computed from them.
    """
    out = bytearray()
    for section in message["sections"]:
        fmt = FORMATS[section["format"]]
        assert section_start(section, count) == len(out), section["format"]
        values = parts[section["format"]]
        if callable(values):
            values = values(bytes(out))
        items = [values] if section["repeat"] == "once" else values
        if section["repeat"] != "once":
            assert len(items) == count
        for item in items:
            blob = build_struct(fmt, item)
            assert len(blob) == section["length"], section["format"]
            out += blob
    return bytes(out)


def build_upload(header: dict, records: list[dict]) -> bytes:
    message = MESSAGES["upload_request"]
    blob = build_message(
        message,
        {
            "AriaUploadRequestHeader": header,
            "AriaUploadRecord": records,
            "AriaUploadRequestTrailer": lambda body: {"crc": crc16(body)},
        },
        len(records),
    )
    total = message["total_length"]
    assert len(blob) == total["base"] + total["per_record"] * len(records)
    return blob


def build_reply(header: dict, users: list[dict], tail: dict) -> bytes:
    message = MESSAGES["upload_reply"]
    length_field = message["length_field"]["base"] + message["length_field"]["per_user"] * len(users)
    blob = build_message(
        message,
        {
            "AriaUploadReplyHeader": header,
            "AriaUploadReplyUser": users,
            "AriaUploadReplyTail": tail,
            "AriaUploadReplyTrailer": lambda body: {"crc": crc16(body), "length": length_field},
        },
        len(users),
    )
    total = message["total_length"]
    assert len(blob) == total["base"] + total["per_user"] * len(users)
    return blob


def parse_upload(blob: bytes) -> dict:
    """Per payload_formats.AriaUploadRequestHeader.parse_rules and messages.upload_request.validation."""
    message = MESSAGES["upload_request"]
    rules = message["validation"]
    header_section, record_section, trailer_section = message["sections"]
    if len(blob) < rules["min_length"]:
        raise ValueError("upload shorter than the minimum")
    if (len(blob) - rules["min_length"]) % rules["record_length"]:
        raise ValueError("upload length is not header + whole records + CRC")
    header = parse_struct(FORMATS["AriaUploadRequestHeader"], blob[: header_section["length"]])
    if header["protocol_version"] != rules["required_protocol_version"]:
        raise ValueError("unsupported protocol version")
    count = (len(blob) - rules["min_length"]) // rules["record_length"]
    if header["record_count"] != count:
        raise ValueError("record count does not match the body length")
    records = [
        parse_struct(
            FORMATS["AriaUploadRecord"],
            blob[
                record_section["offset"] + record_section["length"] * i : record_section["offset"]
                + record_section["length"] * (i + 1)
            ],
        )
        for i in range(count)
    ]
    trailer_at = section_start(trailer_section, count)
    assert trailer_at + trailer_section["length"] == len(blob)
    trailer = parse_struct(FORMATS["AriaUploadRequestTrailer"], blob[trailer_at:])
    return {
        "header": header,
        "records": records,
        "crc": trailer["crc"],
        "crc_ok": trailer["crc"] == crc16(blob[:trailer_at]),
    }


def parse_reply(blob: bytes) -> dict:
    """Per messages.upload_reply and payload_formats.AriaUploadReplyTail.parse_rules.

    A reply that is longer than the formula allows, or whose tail carries a
    value the spec forbids, is the update form or something unknown: refuse
    it, as the tail's parse rules say.
    """
    message = MESSAGES["upload_reply"]
    header_section, user_section, tail_section, trailer_section = message["sections"]
    header = parse_struct(FORMATS["AriaUploadReplyHeader"], blob[: header_section["length"]])
    count = header["user_count"]
    total = message["total_length"]
    if len(blob) != total["base"] + total["per_user"] * count:
        raise ValueError("reply length is not header + users + tail + CRC + length")
    users = [
        parse_struct(
            FORMATS["AriaUploadReplyUser"],
            blob[
                user_section["offset"] + user_section["length"] * i : user_section["offset"]
                + user_section["length"] * (i + 1)
            ],
        )
        for i in range(count)
    ]
    tail_at = section_start(tail_section, count)
    trailer_at = section_start(trailer_section, count)
    assert tail_at + tail_section["length"] == trailer_at
    assert trailer_at + trailer_section["length"] == len(blob)
    tail = parse_struct(FORMATS["AriaUploadReplyTail"], blob[tail_at:trailer_at])
    if any(word not in REFUSAL["allowed_tail_word_values"] for word in tail.values()):
        raise ValueError("tail word outside the values the spec allows")
    trailer = parse_struct(FORMATS["AriaUploadReplyTrailer"], blob[trailer_at:])
    return {
        "header": header,
        "users": users,
        "tail": tail,
        "crc": trailer["crc"],
        "length": trailer["length"],
        "crc_ok": trailer["crc"] == crc16(blob[:trailer_at]),
    }


def as_raw(fmt: dict, values: dict) -> dict:
    """The spec's decoded values with enumerated labels turned into numbers."""
    fields = {field["name"]: field for field in fmt["fields"]}
    return {name: raw_value(fields[name], value) for name, value in values.items()}


def vector_bytes(name: str) -> bytes:
    return bytes.fromhex(VECTORS[name]["hex"])


def flat(text: str) -> str:
    return " ".join(text.split())


def walk(node, path=()):
    """Yield (path, key, value) for every mapping entry in the document."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield path, key, value
            yield from walk(value, (*path, key))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from walk(value, (*path, index))


# ── CRC ──────────────────────────────────────────────────────────────────────


def test_crc_parameters_reproduce_the_standard_check_value():
    check = CRC["check_input_ascii"].encode("ascii")
    assert check == b"123456789"
    assert crc16(check) == CRC["check_value"] == int(CRC["check_value_hex"], 16) == 0x31C3
    # CPython ships an independent implementation of the same CRC.
    assert binascii.crc_hqx(check, CRC["initial_value"]) == CRC["check_value"]
    assert CRC["name"] == "CRC-16/XMODEM"
    assert CRC["polynomial"] == int(CRC["polynomial_hex"], 16) == 0x1021
    assert (CRC["initial_value"], CRC["final_xor"]) == (0, 0)


def test_crc_goes_on_the_wire_low_byte_first():
    assert CRC["wire_byte_order"] == "little"
    check = VECTORS["crc_check"]
    value = crc16(check["input_ascii"].encode("ascii"))
    assert value == int(check["value_hex"], 16)
    assert value.to_bytes(2, CRC["wire_byte_order"]).hex() == check["wire_hex"] == "c331"
    for name in ("AriaUploadRequestTrailer", "AriaUploadReplyTrailer"):
        assert field_of(name, "crc")["endianness"] == "little"


def test_the_commonly_confused_crc_variant_is_documented_as_wrong():
    wrong = dict(CRC, initial_value=CRC["common_mistake"]["initial_value"])
    assert wrong["initial_value"] == 0xFFFF
    assert crc16(b"123456789", wrong) == int(CRC["common_mistake"]["check_value_hex"], 16) == 0x29B1
    request, reply = vector_bytes("upload_request_two_records"), vector_bytes("upload_reply_one_user")
    assert crc16(request[:-2], wrong) == int(
        VECTORS["upload_request_two_records"]["derived"]["wrong_crc_with_initial_value_ffff_hex"], 16
    )
    assert crc16(reply[:-4], wrong) == int(
        VECTORS["upload_reply_one_user"]["derived"]["wrong_crc_with_initial_value_ffff_hex"], 16
    )
    assert crc16(request[:-2], wrong) != crc16(request[:-2])


# ── Layout tables ────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("name", "size"),
    [
        ("AriaUploadRequestHeader", 46),
        ("AriaUploadRecord", 32),
        ("AriaUploadRequestTrailer", 2),
        ("AriaUploadReplyHeader", 11),
        ("AriaUploadReplyUser", 77),
        ("AriaUploadReplyTail", 12),
        ("AriaUploadReplyTrailer", 4),
    ],
)
def test_every_table_tiles_its_structure_exactly(name, size):
    position = 0
    for field in sorted(FORMATS[name]["fields"], key=lambda f: f["offset"]):
        assert field["offset"] == position, f"{name}.{field['name']}"
        assert field["length"] > 0
        if field["type"] in INTEGER_WIDTHS:
            assert INTEGER_WIDTHS[field["type"]] == field["length"]
        if field["length"] > 1 and field["type"] in (*INTEGER_WIDTHS, "float32"):
            assert field["endianness"] == MESSAGES["byte_order"] == "little", field["name"]
        assert field["verification"] in {"reported", "hypothesis"}
        position += field["length"]
    assert position == size
    sections = [
        section
        for message in (MESSAGES["upload_request"], MESSAGES["upload_reply"])
        for section in message["sections"]
        if section["format"] == name
    ]
    assert [section["length"] for section in sections] == [size]


def test_every_number_a_server_stores_carries_a_unit_and_a_scale():
    def semantics(fmt, name):
        field = field_of(fmt, name)
        return field.get("unit"), field.get("scale", 1)

    assert semantics("AriaUploadRequestHeader", "battery_percent") == ("%", 1)
    assert semantics("AriaUploadRequestHeader", "scale_clock") == ("s", 1)
    assert semantics("AriaUploadRecord", "weight") == ("g", 1)
    assert semantics("AriaUploadRecord", "measured_at") == ("s", 1)
    assert semantics("AriaUploadRecord", "body_fat") == ("%", 0.001)
    assert semantics("AriaUploadReplyHeader", "server_time") == ("s", 1)
    assert semantics("AriaUploadReplyUser", "weight_min") == ("g", 1)
    assert semantics("AriaUploadReplyUser", "weight_max") == ("g", 1)
    assert semantics("AriaUploadReplyUser", "age") == ("years", 1)
    assert semantics("AriaUploadReplyUser", "height") == ("mm", 1)
    # Unsettled facts stay out of the fields: no unit is claimed for the
    # impedance word, the second body-fat figure or the covariance float.
    for name in ("impedance", "body_fat_2", "covariance"):
        assert semantics("AriaUploadRecord", name) == (None, 1)
    unknown = {
        f["name"]
        for fmt in FORMATS.values()
        for f in fmt["fields"]
        if f.get("meaning_unknown")
    }
    assert {"auth_code", "unknown_34", "record_constant", "covariance", "body_fat_2"} <= unknown
    assert {"unknown_6", "reserved_zero", "unknown_57", "last_covariance"} <= unknown
    # Which tail word carries the update status is not settled, so none of
    # the three claims a meaning.
    assert {"tail_word_0", "tail_word_1", "tail_word_2"} <= unknown


def test_the_previous_value_words_of_the_user_record_are_pinned():
    """Offsets 57 to 76: zero from local servers, real values from the vendor."""
    expected = [
        # name, offset, type, unit, scale
        ("unknown_57", 57, "uint32", None, 1),
        ("last_body_fat", 61, "uint32", "%", 0.001),
        ("last_covariance", 65, "float32", None, 1),
        ("last_weight", 69, "uint32", "g", 1),
        ("last_weight_time", 73, "uint32", "s", 1),
    ]
    for name, offset, kind, unit, scale in expected:
        field = field_of("AriaUploadReplyUser", name)
        assert (field["offset"], field["length"], field["type"]) == (offset, 4, kind), name
        assert (field.get("unit"), field.get("scale", 1)) == (unit, scale), name
    assert field_of("AriaUploadReplyUser", "unknown_57")["constant"] == 0
    for name in ("last_body_fat", "last_covariance", "last_weight", "last_weight_time"):
        assert field_of("AriaUploadReplyUser", name)["server_sends"] == 0


def test_enumerations_carry_the_documented_values():
    def values(fmt, name):
        return field_of(fmt, name)["values"]

    assert values("AriaUploadReplyHeader", "display_unit") == {0: "lb", 1: "st", 2: "kg"}
    assert values("AriaUploadReplyHeader", "status") == {0x32: "configured", 0x64: "unconfigured"}
    assert values("AriaUploadRecord", "user_id") == {0: "guest"}
    # Which of two described status values a server sends is data, not prose.
    status = field_of("AriaUploadReplyHeader", "status")
    assert status["server_sends"] == 0x32 and status["values"][status["server_sends"]] == "configured"


def test_the_sex_byte_is_two_readings_not_a_settled_enum():
    field = field_of("AriaUploadReplyUser", "sex")
    # What a local server sends ...
    assert field["values"] == {0x00: "female", 0x02: "male"}
    # ... and what the vendor was seen to send, which the enum cannot explain.
    assert field["other_values_seen"] == [0x34, 0x36]
    sex = SERVER["users"]["sex_byte"]
    assert sex["settled"] is False
    assert sex["server_sends"] == sorted(field["values"])
    assert sex["observed_from_vendor"] == field["other_values_seen"]
    assert [r["id"] for r in sex["readings"]] == ["enumeration", "bit_field"]
    for reading in sex["readings"]:
        assert reading["claim"].strip() and reading["evidence"].strip() and reading["problem"].strip()
    assert "20 of 20" in sex["readings"][1]["evidence"]
    assert sex["parsing"] == "Accept any value."
    # 0x36 is 0x34 with the bit local servers use for male.
    assert 0x36 == 0x34 | 0x02
    assert any("0x36" in item and "0x02" in item for item in SPEC["remaining_unknowns"])


def test_size_examples_follow_the_length_formulas():
    examples = MESSAGES["size_examples"]
    request, reply = MESSAGES["upload_request"], MESSAGES["upload_reply"]
    assert (request["total_length"]["base"], request["total_length"]["per_record"]) == (48, 32)
    assert (reply["total_length"]["base"], reply["total_length"]["per_user"]) == (27, 77)
    assert (reply["length_field"]["base"], reply["length_field"]["per_user"]) == (0x19, 0x4D)
    assert examples["request_bytes_by_record_count"] == {
        str(n): 48 + 32 * n for n in (0, 1, 2, 16, 17)
    }
    assert examples["reply_bytes_by_user_count"] == {str(n): 27 + 77 * n for n in (0, 1, 2, 8)}
    assert examples["reply_length_field_by_user_count"] == {
        str(n): 0x19 + 0x4D * n for n in (0, 1, 2, 8)
    }
    # The two length bytes reported from the vendor: one user, two users.
    assert (0x19 + 0x4D * 1).to_bytes(2, "little").hex() == "6600"
    assert (0x19 + 0x4D * 2).to_bytes(2, "little").hex() == "b300"
    assert request["record_count_range_seen"] == {"min": 0, "max": 17}


# ── Vectors: build from the tables, compare byte for byte, parse back ────────


@pytest.mark.parametrize("name", REQUEST_VECTORS)
def test_upload_request_vector_is_rebuilt_byte_for_byte(name):
    vector = VECTORS[name]
    decoded = vector["decoded"]
    built = build_upload(decoded["header"], decoded["records"])
    assert built.hex() == vector_bytes(name).hex()
    assert len(built) == vector["content_length"]
    assert decoded["header"]["record_count"] == len(decoded["records"])
    assert built[-2:] == decoded["crc"].to_bytes(2, "little")
    assert decoded["crc"] == int(decoded["crc_hex"], 16) == binascii.crc_hqx(built[:-2], 0)


@pytest.mark.parametrize("name", REQUEST_VECTORS)
def test_upload_request_vector_parses_back_to_the_declared_values(name):
    decoded = VECTORS[name]["decoded"]
    parsed = parse_upload(vector_bytes(name))
    assert parsed["crc_ok"]
    assert parsed["crc"] == decoded["crc"]
    assert parsed["header"] == as_raw(FORMATS["AriaUploadRequestHeader"], decoded["header"])
    assert parsed["records"] == [
        as_raw(FORMATS["AriaUploadRecord"], record) for record in decoded["records"]
    ]


@pytest.mark.parametrize("name", REPLY_VECTORS)
def test_upload_reply_vector_is_rebuilt_byte_for_byte(name):
    vector = VECTORS[name]
    decoded = vector["decoded"]
    built = build_reply(decoded["header"], decoded["users"], decoded["tail"])
    assert built.hex() == vector_bytes(name).hex()
    assert len(built) == vector["content_length"]
    assert decoded["header"]["user_count"] == len(decoded["users"])
    assert built[-4:-2] == decoded["crc"].to_bytes(2, "little")
    assert built[-2:] == decoded["length"].to_bytes(2, "little")
    assert decoded["crc"] == int(decoded["crc_hex"], 16) == binascii.crc_hqx(built[:-4], 0)
    # The length counts everything before itself, the CRC included.
    assert decoded["length"] == len(built) - 2


@pytest.mark.parametrize("name", REPLY_VECTORS)
def test_upload_reply_vector_parses_back_to_the_declared_values(name):
    decoded = VECTORS[name]["decoded"]
    parsed = parse_reply(vector_bytes(name))
    assert parsed["crc_ok"]
    assert (parsed["crc"], parsed["length"]) == (decoded["crc"], decoded["length"])
    assert parsed["header"] == as_raw(FORMATS["AriaUploadReplyHeader"], decoded["header"])
    assert parsed["users"] == [as_raw(FORMATS["AriaUploadReplyUser"], user) for user in decoded["users"]]
    assert parsed["tail"] == as_raw(FORMATS["AriaUploadReplyTail"], decoded["tail"])


def test_every_reply_vector_says_who_sends_it():
    labelled = {name for name, vector in VECTORS.items() if isinstance(vector, dict) and "sender" in vector}
    assert set(REPLY_VECTORS) == labelled
    for name in LOCAL_REPLY_VECTORS:
        assert VECTORS[name]["sender"] == "local_server", name
    for name in VENDOR_FORM_VECTORS:
        assert VECTORS[name]["sender"] == "vendor_form", name
        assert "PARSERS AND RELAYS ONLY" in VECTORS[name]["note"]


def test_constants_in_the_vectors_are_the_constants_in_the_tables():
    request = VECTORS["upload_request_two_records"]["decoded"]
    reply = VECTORS["upload_reply_two_users"]["decoded"]
    samples = {
        "AriaUploadRequestHeader": [request["header"]],
        "AriaUploadRecord": request["records"],
        "AriaUploadReplyHeader": [reply["header"]],
        "AriaUploadReplyUser": reply["users"],
        "AriaUploadReplyTail": [reply["tail"]],
    }
    constants = server_sends = 0
    for name, items in samples.items():
        for field in FORMATS[name]["fields"]:
            # A field is either one value ever reported, or a choice a server makes.
            assert not ("constant" in field and "server_sends" in field), field["name"]
            for item in items:
                if "constant" in field:
                    assert raw_value(field, item[field["name"]]) == field["constant"], field["name"]
                    constants += 1
                if "server_sends" in field:
                    assert raw_value(field, item[field["name"]]) == field["server_sends"], field["name"]
                    server_sends += 1
    # 1 header constant + 2 records x 1 + 1 reply-header constant + 2 users x 2.
    assert constants == 8
    # status + 2 users x 4 previous-value words + 3 tail words.
    assert server_sends == 12


def test_format_examples_are_hex_slices_of_the_vectors():
    def example(name):
        text = FORMATS[name]["example"]
        assert re.fullmatch(r"[0-9a-f ]+", text), f"{name}: the example is hex only"
        assert FORMATS[name]["example_notes"].strip()
        return bytes.fromhex(text)

    request, reply = vector_bytes("upload_request_two_records"), vector_bytes("upload_reply_one_user")
    assert example("AriaUploadRequestHeader") == request[:46]
    assert example("AriaUploadRecord") == request[46:78]
    assert example("AriaUploadRequestTrailer") == request[-2:]
    assert example("AriaUploadReplyHeader") == reply[:11]
    assert example("AriaUploadReplyUser") == reply[11:88]
    assert example("AriaUploadReplyTail") == reply[88:100]
    assert example("AriaUploadReplyTrailer") == reply[100:]
    # Every key the tables use beyond the common ones is explained in the legend.
    legend = flat(FORMATS["AriaUploadRequestHeader"]["description"])
    for key in (
        "constant",
        "server_sends",
        "values",
        "other_values_seen",
        "values_seen",
        "never_send",
        "meaning_unknown",
        "encoding",
        "pad_byte",
        "truncate_to_bytes",
        "example_notes",
    ):
        assert f"`{key}" in legend, key


def test_derived_values_follow_from_the_vector_and_the_tables():
    vector = VECTORS["upload_request_two_records"]
    header, records, derived = vector["decoded"]["header"], vector["decoded"]["records"], vector["derived"]
    mac = bytes.fromhex(header["mac"])
    assert ":".join(f"{b:02x}" for b in mac) == derived["mac_text"] == "00:00:5e:00:53:01"
    assert mac.hex().upper() == derived["register_serial_number"]
    # Setup SSID: the declared prefix plus the last three MAC bytes, upper-case hex.
    softap = next(m for m in SPEC["device"]["setup"]["methods"] if m["type"] == "softap_http")["softap"]
    ssid = softap["ssid_prefix"] + mac[-3:].hex().upper()
    assert ssid == derived["setup_ssid"] == softap["ssid_examples"][0]
    assert softap["ssid_prefix"] == SPEC["device"]["identification"]["ssid_prefix"] == "Aria "
    assert re.fullmatch(DETAILS["setup_access_point"]["ssid_regex"], ssid)
    # DHCP host name: the declared word plus the same three bytes, lower-case hex.
    dhcp = DETAILS["station_mode"]["dhcp"]
    host_name = "GainSpan" + mac[-3:].hex()
    assert host_name == derived["dhcp_host_name"] == dhcp["host_name_example"]
    assert re.fullmatch(dhcp["host_name_regex"], host_name)
    # Case is part of both patterns: upper-case hex in the network name,
    # lower-case in the host name (checked with another documentation-range suffix).
    assert re.fullmatch(dhcp["host_name_regex"], "GainSpan0053af")
    assert not re.fullmatch(dhcp["host_name_regex"], "GainSpan0053AF")
    assert re.fullmatch(DETAILS["setup_access_point"]["ssid_regex"], "Aria 0053AF")
    assert not re.fullmatch(DETAILS["setup_access_point"]["ssid_regex"], "Aria 0053af")

    fat = field_of("AriaUploadRecord", "body_fat")
    assert [round(r["body_fat"] * fat["scale"], 6) for r in records] == derived["body_fat_percent"]
    user = field_of("AriaUploadRecord", "user_id")
    assert [user["values"].get(r["user_id"]) == "guest" for r in records] == derived["guest"]
    for record, is_guest in zip(records, derived["guest"], strict=True):
        if is_guest:
            zeroed = SERVER["users"]["guest"]["zero_fields"]
            assert [record[name] for name in zeroed] == [0, 0.0, 0]

    # Clock: true_time = server_now - (scale_clock - measured_at).
    assert SERVER["clock"]["rebase_formula"] == "true_time = server_now - (scale_clock - measured_at)"
    ages = [header["scale_clock"] - r["measured_at"] for r in records]
    assert ages == derived["record_age_s"]
    assert [derived["server_now"] - age for age in ages] == derived["rebased_measured_at"]
    # The reply that answers this request carries the same server time.
    assert VECTORS["upload_reply_one_user"]["decoded"]["header"]["server_time"] == derived["server_now"]
    # The edge case the formula cannot place is named, and named as a suggestion.
    assert "not a device fact" in flat(SERVER["clock"]["when_measured_at_is_later_than_scale_clock"])


def test_the_vendor_form_vector_decodes_with_the_same_tables():
    """A parser built from the tables reads what the vendor sent, 0x36 and all."""
    vector = VECTORS["vendor_form_reply_one_user"]
    parsed = parse_reply(vector_bytes("vendor_form_reply_one_user"))
    user, derived = parsed["users"][0], vector["derived"]
    assert parsed["crc_ok"] and parsed["length"] == 0x66
    assert user["sex"] == int(derived["sex_byte_hex"], 16) == 0x36
    assert user["sex"] not in field_of("AriaUploadReplyUser", "sex")["values"]
    assert user["sex"] in field_of("AriaUploadReplyUser", "sex")["other_values_seen"]
    fat = field_of("AriaUploadReplyUser", "last_body_fat")
    assert round(user["last_body_fat"] * fat["scale"], 6) == derived["last_body_fat_percent"]
    assert user["last_covariance"] == 0.5
    # The vendor's window: the previous weight minus and plus 4000 g, exactly.
    half = SERVER["users"]["window"]["vendor_half_width_g"]
    assert user["last_weight"] == derived["window_centre_g"]
    assert (user["weight_min"], user["weight_max"]) == (user["last_weight"] - half, user["last_weight"] + half)
    # Its "time of last weight" is the re-based time of the reading just uploaded.
    request = VECTORS["upload_request_two_records"]["derived"]
    assert user["last_weight_time"] == request["rebased_measured_at"][0]
    assert list(parsed["tail"].values()) == [0, 0, 0]


def test_the_reply_vector_answers_the_request_vector():
    request = VECTORS["upload_request_two_records"]["decoded"]
    reply = VECTORS["upload_reply_one_user"]["decoded"]
    known = request["records"][0]
    user = reply["users"][0]
    assert user["user_id"] == known["user_id"] != 0
    half = SERVER["users"]["window"]["vendor_half_width_g"]
    assert (user["weight_min"], user["weight_max"]) == (known["weight"] - half, known["weight"] + half)
    assert user["weight_min"] <= known["weight"] <= user["weight_max"]
    guest = request["records"][1]
    assert not user["weight_min"] <= guest["weight"] <= user["weight_max"]
    assert user["name"] == user["name"].upper() and len(user["name"]) <= 20


def test_a_long_name_is_cut_to_the_field_before_padding():
    name = field_of("AriaUploadReplyUser", "name")
    assert (name["length"], name["truncate_to_bytes"], name["pad_byte"], name["encoding"]) == (
        20,
        20,
        0x20,
        "ascii",
    )
    assert pack_field(name, "ABCDEFGHIJKLMNOPQRSTUVWXYZ") == b"ABCDEFGHIJKLMNOPQRST"
    assert pack_field(name, "AB") == b"AB" + b" " * 18


def test_dedup_key_names_real_fields():
    header = {f["name"] for f in FORMATS["AriaUploadRequestHeader"]["fields"]}
    record = {f["name"] for f in FORMATS["AriaUploadRecord"]["fields"]}
    assert SERVER["delivery"]["dedup_key"] == ["mac", "measured_at", "weight"]
    assert set(SERVER["delivery"]["dedup_key"]) <= header | record


def test_the_first_weight_window_is_stated_as_unsettled_not_invented():
    """What to send for a user with no weight yet: servers differ, no rule exists."""
    first = SERVER["users"]["first_window"]
    assert first["rule"].startswith("None established")
    assert first["vendor"] == "unknown"
    servers = {entry["server"]: entry for entry in first["known_servers"]}
    assert len(servers) >= 5
    for entry in servers.values():
        assert entry["sends"].strip() and entry["evidence"].strip()
    assert "weight_min 0 and weight_max 0" in servers["helvetic (the Django application)"]["sends"]
    assert "starting weight" in servers["PHP server"]["sends"]
    assert "guest" in first["consequence_of_no_window"]
    # Unknown in the field AND in the list of unknowns.
    assert any("first_window" in item and "0 to 0" in item for item in SPEC["remaining_unknowns"])
    must = {rule["id"]: rule["rule"] for rule in SERVER["requirements"]["must"]}
    assert "no rule is established" in must["user_record_content"]
    # The vendor's own window, where a weight exists, is data.
    assert SERVER["users"]["window"]["vendor_half_width_g"] == 4000


# ── Malformed uploads ────────────────────────────────────────────────────────


def _tampered(change) -> bytes:
    blob = bytearray(vector_bytes("upload_request_two_records"))
    change(blob)
    return bytes(blob)


def _truncate_to(length):
    def change(blob):
        del blob[length:]

    return change


def _set_u32(offset, value):
    def change(blob):
        blob[offset : offset + 4] = value.to_bytes(4, "little")

    return change


@pytest.mark.parametrize(
    "blob",
    [
        b"",
        _tampered(_truncate_to(47)),
        _tampered(_truncate_to(111)),
        _tampered(_truncate_to(81)),
        _tampered(_set_u32(0, 2)),
        _tampered(_set_u32(42, 1)),
        _tampered(_set_u32(42, 3)),
    ],
    ids=["empty", "short", "one-byte-short", "ragged", "version-2", "count-low", "count-high"],
)
def test_malformed_uploads_are_rejected(blob):
    with pytest.raises(ValueError):
        parse_upload(blob)


def test_a_flipped_bit_is_caught_by_the_crc():
    good = vector_bytes("upload_request_two_records")
    assert parse_upload(good)["crc_ok"]
    weight_offset = 46 + 8
    bad = _tampered(lambda blob: blob.__setitem__(weight_offset, blob[weight_offset] ^ 0x01))
    assert not parse_upload(bad)["crc_ok"]
    rules = MESSAGES["upload_request"]["validation"]
    assert (rules["min_length"], rules["record_length"], rules["required_protocol_version"]) == (48, 32, 3)


def test_a_malformed_upload_has_a_stated_answer():
    malformed = MESSAGES["upload_request"]["validation"]["on_malformed_upload"]
    assert malformed["status"] == 400
    assert "never a binary reply" in malformed["body"]
    assert malformed["basis"].strip() and "again" in malformed["consequence"]
    should = {rule["id"] for rule in SERVER["requirements"]["should"]}
    assert "malformed_gets_400" in should


# ── Routes and HTTP framing ──────────────────────────────────────────────────


def test_routes_are_the_three_the_scale_calls():
    routes = {route["name"]: route for route in SERVER["routes"]}
    assert set(routes) == {"register", "validate", "upload"}
    assert (routes["register"]["method"], routes["register"]["path"]) == ("GET", "/scale/register")
    assert (routes["validate"]["method"], routes["validate"]["path"]) == ("GET", "/scale/validate")
    assert (routes["upload"]["method"], routes["upload"]["path"]) == ("POST", "/scale/upload")
    assert [p["name"] for p in routes["register"]["query_parameters"]] == ["serialNumber", "token", "ssid"]
    assert [p["name"] for p in routes["validate"]["query_parameters"]] == ["serialNumber", "token"]

    register, validate = routes["register"]["reply"], routes["validate"]["reply"]
    assert (register["status"], bytes.fromhex(register["body_hex"])) == (200, b"")
    assert register["required_headers"] == {"Content-Length": "0"}
    assert (validate["status"], bytes.fromhex(validate["body_hex"])) == (200, b"T")
    assert validate["body_ascii"] == "T"
    # The vendor framed this one byte two ways and the scale carried on after
    # both, so Content-Length is recommended here, not required.
    assert "required_headers" not in validate
    assert validate["recommended_headers"] == {"Content-Length": str(len(b"T"))}
    framing = " ".join(validate["framing_observed_from_vendor"])
    assert "Content-Length: 1" in framing and "chunked" in framing
    assert routes["upload"]["reply"]["status"] == 200
    assert "Content-Length" in routes["upload"]["reply"]["required_headers"]
    for name in ("register", "validate"):
        observed = routes[name]["request_headers_observed"]
        assert observed["header_names"] == ["Host"] and observed["host_value"] == "www.fitbit.com"
        assert observed["http_version"] == "HTTP/1.1" and observed["firmware"] == [37]
    for route in routes.values():
        assert route["safe_binding"] is False
        assert route["verification"] == "reported" and route["basis"].strip()


def test_the_captured_request_head_adds_up():
    observed = next(r for r in SERVER["routes"] if r["name"] == "upload")["request_headers_observed"]
    head = "".join(line + "\r\n" for line in observed["lines"]) + "\r\n"
    assert len(head.encode("ascii")) == observed["header_block_bytes"] == 146
    assert observed["firmware"] == [35, 37]
    assert observed["lines"][0] == "POST /scale/upload HTTP/1.1"
    assert "Host: www.fitbit.com" in observed["lines"]
    assert not any(line.lower().startswith("user-agent") for line in observed["lines"])
    # The declared Content-Length is a one-record body; a zero-record body
    # has a two-digit length as well, so the head is the same size.
    assert "Content-Length: 80" in observed["lines"]
    assert MESSAGES["size_examples"]["request_bytes_by_record_count"]["1"] == 80
    assert len(head.replace("Content-Length: 80", "Content-Length: 48")) == 146
    assert MESSAGES["size_examples"]["request_bytes_by_record_count"]["0"] == 48


def test_the_server_listens_where_the_scale_calls():
    listen = SERVER["listen"]
    assert (listen["scheme"], listen["tls"], listen["transport"], listen["port"]) == (
        "http",
        False,
        "tcp",
        80,
    )
    assert listen["host_header_sent_by_scale"] == "www.fitbit.com"
    assert "none has been tested for" in flat(listen["notes"])
    reply = SERVER["http_reply"]
    assert reply["status"] == 200
    assert [h["name"] for h in reply["required_headers"]] == ["Content-Length"]
    never = " ".join(reply["never"]).lower()
    assert "3xx" in never and "redirect" in never and "https" in never and "chunked" in never
    connection = reply["connection"]
    assert connection["http_version"] == "HTTP/1.1"
    assert "validate on the connection that carried register" in connection["observed_with_vendor"]
    assert connection["guidance"].strip() and connection["unknown"].strip()


# ── Safety invariants, asserted as data ──────────────────────────────────────


def test_no_reply_in_the_file_signals_a_firmware_update():
    """Never signal an update: pinned without claiming which word is the signal.

    The evidence no longer supports "the middle word is the status and 3 is
    the only no-update value": the vendor's own server sent 0, 0, 0. So the
    invariant is stated over all three words.
    """
    tail = FORMATS[REFUSAL["in_format"]]["fields"]
    assert [f["name"] for f in tail] == ["tail_word_0", "tail_word_1", "tail_word_2"]
    forbidden, allowed = REFUSAL["never_send_in_any_tail_word"], REFUSAL["allowed_tail_word_values"]
    assert forbidden == [1] and allowed == [0, 3]
    for field in tail:
        assert field["never_send"] == forbidden, field["name"]
        assert set(field["values_seen"]) <= set(allowed), field["name"]
        assert field["server_sends"] in allowed and field["server_sends"] not in forbidden
        assert "NEVER 1" in field["description"]
        # No enum label for the update form exists anywhere in the tables.
        assert "values" not in field and "constant" not in field
    assert [f["server_sends"] for f in tail] == REFUSAL["tail_words_to_send"] == [0, 3, 0]
    assert REFUSAL["never_append_bytes"] is True
    assert REFUSAL["never_serve_path_prefix"] == "/scale/firmware/"

    seen_elsewhere = [entry["words"] for entry in REFUSAL["other_tails_seen_meaning_no_update"]]
    assert [0, 0, 0] in seen_elsewhere
    vendor = next(e for e in REFUSAL["other_tails_seen_meaning_no_update"] if e["words"] == [0, 0, 0])
    assert "20 of 20" in vendor["evidence"]
    for words in [REFUSAL["tail_words_to_send"], *seen_elsewhere]:
        assert set(words) <= set(allowed) and not set(words) & set(forbidden)

    reply_total = MESSAGES["upload_reply"]["total_length"]
    for name in REPLY_VECTORS:
        blob = vector_bytes(name)
        parsed = parse_reply(blob)
        words = list(parsed["tail"].values())
        assert not set(words) & set(forbidden), name
        assert set(words) <= set(allowed), name
        # Nothing is appended: the update form is reported to add a URL.
        assert len(blob) == reply_total["base"] + reply_total["per_user"] * parsed["header"]["user_count"]
        if name in LOCAL_REPLY_VECTORS:
            assert words == REFUSAL["tail_words_to_send"], name
        else:
            assert words in seen_elsewhere, name
    assert "update_available" not in str(VECTORS) and "update_available" not in str(FORMATS)


def test_which_tail_word_is_the_update_status_is_recorded_as_unsettled():
    status = REFUSAL["status_word"]
    assert status["settled"] is False
    assert [r["position"] for r in status["readings"]] == ["tail_word_0", "tail_word_1"]
    assert all(r["evidence"].strip() for r in status["readings"])
    may = " ".join(REFUSAL["what_a_server_may_send"])
    never = " ".join(REFUSAL["what_a_server_must_never_send"])
    assert "0, 3, 0" in may and "0, 0, 0" in may
    assert "1 in any of the three tail words" in never and "/scale/firmware/" in never
    assert any("0, 0, 0" in item and "Never send 1" in item for item in SPEC["remaining_unknowns"])


@pytest.mark.parametrize("word", [0, 1, 2])
@pytest.mark.parametrize("value", [1, 2, 4])
def test_a_reply_with_a_forbidden_tail_word_is_refused_by_the_parser(word, value):
    decoded = VECTORS["upload_reply_one_user"]["decoded"]
    tail = dict(decoded["tail"], **{f"tail_word_{word}": value})
    blob = build_reply(decoded["header"], decoded["users"], tail)
    with pytest.raises(ValueError):
        parse_reply(blob)


def test_a_reply_with_bytes_added_is_refused_by_the_parser():
    blob = vector_bytes("upload_reply_one_user")
    with pytest.raises(ValueError):
        parse_reply(blob[:100] + b"http://x\x00" + blob[100:])


def test_firmware_update_is_declared_for_refusal_only():
    features = [f for f in SPEC["features"] if f["type"] == "firmware_update"]
    assert len(features) == 1
    dfu = features[0]["dfu"]
    assert dfu["mechanisms"] == ["vendor_cloud"]
    assert dfu["enter"]["how"] == "automatic" and "command" not in dfu["enter"]
    assert "endpoint" not in dfu
    assert dfu["image"]["signing"] == "unknown"
    assert dfu["recovery"]["interrupted"] == "unknown"
    assert dfu["verification"] == "reported"
    assert "REFUSAL ONLY" in dfu["notes"] and "must never be sent" in dfu["notes"]
    assert "never put 1 in any tail word" in flat(dfu["notes"])


def test_firmware_is_a_danger_section_with_facts_and_no_procedure():
    danger = DETAILS["firmware_danger"]
    assert danger["status"].startswith("A danger to avoid, not a route")
    facts = " ".join(danger["facts"])
    for phrase in (
        "plain HTTP",
        "whatever answers www.fitbit.com",
        "/scale/firmware/",
        "2026-11-23",
        "no image fetched",
        "Nobody has built or flashed a modified image",
        "abandoned",
        "No recovery from a bad image has been shown",
    ):
        assert phrase in facts, phrase
    assert len(danger["rules"]) == 5 and all(rule.startswith("Never") for rule in danger["rules"])
    # A relay is not neutral: with the redirect in place the image request
    # arrives at the relay, so the file may not say the exposure is unchanged.
    assert "A relay therefore changes this exposure" in facts
    assert "neither adds to it nor removes" not in flat(SPEC_TEXT)
    assert any("relay" in rule and "/scale/firmware/" in rule for rule in danger["rules"])
    # No procedure: nothing to run, fetch or flash is spelled out.
    assert "steps" not in danger and "procedure" not in danger
    # No complete address of an image appears anywhere in the file.
    assert not re.search(r"https?://[^\s\"']*/scale/firmware/\d", SPEC_TEXT)
    assert "serialNumber=" not in SPEC_TEXT


def test_must_never_rules_name_the_two_that_matter_most():
    rules = SERVER["requirements"]
    for group in ("must", "should", "must_never"):
        ids = [rule["id"] for rule in rules[group]]
        assert len(ids) == len(set(ids)) and all(rule["rule"].strip() for rule in rules[group])
    never = {rule["id"]: rule["rule"] for rule in rules["must_never"]}
    assert {"signal_firmware_update", "redirect_to_https", "serve_firmware_path"} <= set(never)
    assert {"crc_init_ffff", "non_200_for_valid_upload", "publish_identifiers"} <= set(never)
    assert "0, 3, 0" in never["signal_firmware_update"]
    assert "ANY of the three tail words" in never["signal_firmware_update"]
    assert "never add bytes" in never["signal_firmware_update"]
    must = {rule["id"] for rule in rules["must"]}
    assert {"answer_register", "answer_validate", "read_raw_body", "reply_exact_layout"} <= must


def test_the_vendor_name_is_redirected_and_never_blockable():
    egress = {entry["host"]: entry for entry in SPEC["cloud"]["egress"]}
    assert len(egress) == len(SPEC["cloud"]["egress"])
    upload = egress["www.fitbit.com"]
    assert upload["when_blocked"]["impact"] == "breaks"
    effect = flat(upload["when_blocked"]["effect"])
    assert effect.startswith("REDIRECT this name")
    assert "never sinkhole or block it" in effect
    assert upload.get("match", "exact") == "exact"
    assert upload["contacted_by"] in {"device", "both"}
    assert {"device_cloud", "time"} <= set(upload["roles"])
    assert upload["ports"] == [{"port": 80, "protocol": "tcp"}]
    # No parent or wildcard entry that a generated list could block instead.
    assert "fitbit.com" not in egress
    assert all(entry.get("match", "exact") == "exact" for entry in egress.values())
    # The egress text is shown without the rest of the file, so it carries
    # its own warnings: who must leave the name alone, and that a network of
    # the scale's own is not something to move a joined scale onto.
    assert "Leave the name alone entirely if the scale still syncs to Fitbit" in effect
    workaround = flat(upload["when_blocked"]["workaround"])
    assert "per-device DHCP option" in workaround
    assert "only if the scale is already on it" in workaround and "needs setup mode" in workaround
    assert "Once the scale is run locally, keep the override permanently" in workaround
    # Every other name is the browser's, so no list is ever generated for it.
    assert all(e["contacted_by"] == "app" for host, e in egress.items() if host != "www.fitbit.com")
    for entry in egress.values():
        assert entry["verification"] == "reported" and entry["basis"].strip()

    override = SERVER["dns_override"]
    assert (override["name"], override["action"]) == ("www.fitbit.com", "redirect")
    assert SPEC["cloud"]["required"] is False
    assert SPEC["local_access"]["status"] == "native"


def test_the_lines_an_owner_copies_name_one_host_and_nothing_wider():
    override = SERVER["dns_override"]
    assert "not fitbit.com" in override["match"] and "not a wildcard" in override["match"]
    assert len(override["examples"]) == 3
    for key, line in override["examples"].items():
        assert "www.fitbit.com" in line, key
        assert "/fitbit.com/" not in line and "*" not in line and ".fitbit.com," not in line.replace(
            "www.fitbit.com,", ""
        ), key
        assert "192.168.1.50" in line, key
    scoped = override["scale_only_example"]
    assert "00:00:5e:00:53:01" in scoped["dnsmasq_dhcp"]
    # The resolver handed to the scale is its own placeholder, with a
    # sentence saying it must actually be a resolver.
    assert "192.168.1.51" in scoped["dnsmasq_dhcp"] and "192.168.1.51" in scoped["placeholders"]
    assert "must actually run a resolver" in scoped["placeholders"]
    assert "not a browser" in flat(override["check"])
    # The redirect is not for everyone, and a battery pull is not how it takes effect.
    assert "keep" in override["who_should_not_add_it"] and "relay" in override["who_should_not_add_it"]
    assert "Do NOT pull a battery" in flat(override["takes_effect"])
    assert "Aria 2" in flat(override["scope"])


def test_nothing_claims_hardware_verification():
    testing = SPEC["device"]["testing"]
    assert testing["status"] == "untested" and "detail" not in testing
    for path, key, value in walk(SPEC):
        where = "/".join(map(str, path))
        if key == "verification":
            assert value in {"reported", "hypothesis"}, f"{where}: {value!r}"
        if key == "verified":
            assert value is False, where
        if key == "confidence":
            assert value in {"low", "medium"}, f"{where}: {value!r}"
    assert "confirmed" not in {value for _, key, value in walk(SPEC) if key == "verification"}


def test_direction_and_scope_are_not_flattened_into_a_device_api():
    device = SPEC["device"]
    assert (device["protocol"], device["transport"]) == ("wifi", "http")
    assert device["integration"] == "identify_only"
    assert device["model"] == "FB201" and "variants" not in device
    assert device["category"] == "scale"
    assert device["category_hierarchy"] == ["measurement", "health", "body_composition"]
    assert "DIRECTION MATTERS" in device["notes"]
    assert not {"http_endpoints", "commands", "entities", "services"} & set(SPEC)
    assert SERVER["direction"] == "scale_initiates_http_to_owner_server"
    assert SERVER["executable"] is False
    assert SERVER["declared_as_device_local_control"] is False
    assert SERVER["protocol_version"] == 3
    assert "none" in device["discovery"] and "methods" not in device["discovery"]
    assert "default_port" not in device["identification"]


# ── The vendor's cut-off: already past ───────────────────────────────────────


def test_the_vendor_cutoff_is_stated_as_already_past():
    status = DETAILS["vendor_status"]
    cutoff, edit = status["stated_cutoff"], status["observed_edit"]
    assert cutoff["date"] == "2026-11-09"
    assert cutoff["quote"].startswith("Starting November 9, 2026, with the release of app version 5.12")
    # The page has been edited once without notice, so the spec tells
    # maintainers to re-read it: the reading time is free to move forward,
    # but never to before the first reading of the present wording.
    stamp = re.compile(r"2026-\d\d-\d\dT\d\d:\d\dZ")
    for moment in (cutoff["read_at"], edit["new_wording_read"]["latest"], status["as_of"]):
        assert stamp.fullmatch(moment), moment
        assert moment >= edit["new_wording_read"]["first"], moment
    assert "Re-read it before quoting either date" in edit["caution"]
    # The earlier wording is an observation with its fetch times, not the date.
    assert edit["earlier_date"] == "2026-11-28"
    assert edit["earlier_quote"].startswith("Starting November 28, 2026")
    assert edit["earlier_quote"].replace("November 28", "November 9") == cutoff["quote"]
    assert edit["earlier_wording_read"] == {"first": "2026-11-23T05:11Z", "last": "2026-11-23T06:57Z"}
    assert edit["new_wording_read"]["first"] == "2026-11-23T23:07Z"
    other = edit["other_language_editions"]
    assert other["still_say"] == "2026-11-28" and set(other["editions_checked"]) == {"de", "fr", "ja"}
    assert "already ended" in status["owner_rule"] and "2026-11-28" in status["owner_rule"]
    quotes = [entry["quote"] for entry in status["unchanged_statements"]]
    assert "Aria Air is not impacted by this change." in quotes
    assert any("will continue to sync" in quote for quote in quotes)


def test_no_text_gives_an_owner_time_left():
    """2026-11-28 may appear only as the earlier wording, never as the date."""
    methods = {m["type"]: m for m in SPEC["device"]["setup"]["methods"]}
    vendor = flat(methods["cloud_account"]["description"])
    assert "2026-11-09" in vendor and "2026-11-28" not in vendor
    notes = flat(SPEC["device"]["notes"])
    assert "VENDOR PAIRING HAS ENDED" in notes and "ended on 2026-11-09" in notes
    assert "Do not plan around the 28th" in notes
    failure = flat(SPEC["cloud"]["failure_mode"])
    assert "have ended" in failure and "2026-11-09" in failure
    whole = flat(SPEC_TEXT)
    for phrase in (
        "ends on 2026-11-28",
        "ends 2026-11-28",
        "from 2026-11-28",
        "after 2026-11-28",
        "before 2026-11-28",
        "until 2026-11-28",
        "stated 2026-11-28",
        "Vendor's stated end",
    ):
        assert phrase not in whole, phrase
    # Wherever the later date is printed, the same passage says what it is.
    for match in re.finditer(r"2026-11-28|November 28|28 November|the 28th", whole):
        window = whole[max(0, match.start() - 420) : match.end() + 320]
        assert re.search(
            r"2026-11-09|November 9|earlier|until 2026-11-23|still sa|at the time|quotes", window
        ), window


# ── Setup: route order and the one-way door ──────────────────────────────────


def test_setup_puts_the_route_that_changes_nothing_first():
    setup = SPEC["device"]["setup"]
    assert setup["required"] is True and setup["confidence"] == "medium"
    override, same_network, direct, vendor = setup["methods"]
    assert [m["type"] for m in setup["methods"]] == ["none", "none", "softap_http", "cloud_account"]
    assert [m["role"] for m in setup["methods"]] == ["primary", "alternative", "alternative", "historical"]
    assert all(m["verified"] is False and m["basis"].strip() for m in setup["methods"])
    for method in setup["methods"]:
        for step in method["steps"]:
            assert step["actor"] in {"user", "client", "device"} and step["action"].strip()

    # Primary: nothing done at the scale, and it says who must not use it.
    assert "no setup mode" in override["name"]
    assert override["brick_risk"] == "none"
    assert "vendor sync" in override["not_for"] and "relay" in override["not_for"]
    add = next(step for step in override["steps"] if step["action"].startswith("Add the DNS override"))
    assert "CONSEQUENCE" in add["notes"] and "never reach the Fitbit account" in flat(add["notes"])
    # The first thing the owner does touches neither the scale nor DNS.
    assert "WITHOUT changing DNS" in override["steps"][0]["action"]
    assert not any("battery out" in step["action"].lower() for step in override["steps"])
    weigh = next(step for step in override["steps"] if step["action"].startswith("Step on the scale"))
    assert "Do not pull a battery" in weigh["action"]

    # Before setup mode: the untested recreated network, labelled as such.
    assert "(untested)" in same_network["name"]
    assert same_network["evidence_level"].startswith("inferred")
    assert "reconnected" in flat(same_network["basis"])

    assert vendor["cloud"]["local_alternative"].strip().startswith("Yes")
    assert "Do not start here" in vendor["steps"][0]["action"]
    assert "Do not unpair or remove a scale that still syncs" in flat(vendor["steps"][0]["action"])

    # Who should not touch anything is said in the block's own notes.
    notes = flat(setup["notes"])
    assert "WHO SHOULD NOT TOUCH ANYTHING" in notes
    assert "Do not enter setup mode and do not re-run setup" in notes
    assert "Do not add the DNS override on the network the scale uses" in notes
    assert "do not pull a battery on a working scale without a reason" in notes


def test_the_one_way_door_is_marked_at_the_step_itself():
    setup = SPEC["device"]["setup"]
    direct = next(m for m in setup["methods"] if m["type"] == "softap_http")
    assert direct["name"].startswith("ONE-WAY DOOR")
    assert direct["pairing_impact"].strip().startswith("ONE-WAY")
    basis = flat(direct["basis"])
    for firmware in ("firmware 35", "firmware 37", "firmware 39", "firmware 38"):
        assert firmware in basis
    assert "issue 4" in basis and "unresolved" in basis and "no log shows it" in basis
    level = flat(direct["evidence_level"])
    assert "no success report on 38" in level and "author-reported on 37" in level
    # Firmware 39: the request was accepted; the join has never been shown.
    assert level.startswith("hardware-demonstrated on firmware 35;")
    assert "on 39 the request returned 200 but no public log shows the scale joining" in level
    assert level.count("hardware-demonstrated") == 1

    door = direct["one_way_door"]
    assert "TAP TO CHANGE" in door["point_of_no_return"]
    # A battery re-insert is expected to be harmless, not established to be.
    assert "not established on firmware 38 and 39" in door["point_of_no_return"]
    assert len(door["consequences"]) >= 4 and len(door["before_you_start"]) >= 3
    assert any("DNS override and the server answering first" in item for item in door["before_you_start"])
    assert any("cannot be paired again" in item for item in door["consequences"])

    steps = direct["steps"]
    # The server and the override come before anything is done to the scale.
    assert "BEFORE touching the scale" in steps[0]["action"]
    assert "STOP HERE" in steps[0]["notes"]
    press = next(step for step in steps if "TAP TO CHANGE" in step["action"])
    assert press["action"].startswith("POINT OF NO RETURN")
    assert "CONSEQUENCE" in press["notes"] and "the stored network is gone" in flat(press["notes"])
    assert "will not pair it again" in flat(press["notes"])
    assert steps.index(press) > 0
    battery = steps[steps.index(press) - 1]
    assert "Do not press or step on the scale" in battery["action"]
    join = next(step for step in steps if step["action"].startswith("From a computer that is NOT"))
    assert "nobody reports doing this from a phone" in flat(join["notes"])

    softap = direct["softap"]
    assert softap["open_network"] is True
    assert (softap["gateway_ip"], softap["port"]) == ("192.168.240.1", 80)
    requests = [step["request"] for step in steps if "request" in step]
    assert len(requests) == 1
    assert (requests[0]["protocol"], requests[0]["action"]) == ("http", "GET /scale/setup")
    # Where each argument travels is data: a request built from the list
    # puts two in the query string and the token in a cookie.
    assert [(a["name"], a["in"]) for a in requests[0]["arguments"]] == [
        ("ssid", "query"),
        ("custom_password", "query"),
        ("token", "cookie"),
    ]
    limits = {a["name"]: a.get("max_characters") for a in requests[0]["arguments"]}
    assert limits == {"ssid": None, "custom_password": 31, "token": 31}
    # The passphrase limit is the vendor's; the token limit is a third
    # party's reading of firmware images, and says so.
    token = requests[0]["arguments"][2]
    assert "Reported, not tested" in token["max_characters_basis"]
    assert "summarising tool" in flat(token["max_characters_basis"])
    provisioning = DETAILS["setup_access_point"]["provisioning_request"]
    assert (provisioning["method"], provisioning["path"]) == ("GET", "/scale/setup")
    assert [p["name"] for p in provisioning["query_parameters"]] == ["ssid", "custom_password"]
    assert [c["name"] for c in provisioning["cookies"]] == ["token"]
    assert provisioning["cookies"][0]["max_characters"] == 31
    assert "Reported, not tested" in provisioning["cookies"][0]["max_characters_basis"]
    assert provisioning["query_parameters"][1]["max_characters"] == 31

    # The accidental-setup-mode recovery is a suggestion nobody has tried,
    # and a network name on the display is not proof that the key survived.
    accident = next(t for t in direct["troubleshooting"] if "by accident" in t["symptom"])
    advice = " ".join(accident["causes"])
    assert "UNTESTED SUGGESTION" in advice and "the name is still stored" in advice
    assert "weigh in to find out whether the scale can still join" in advice
    assert "the stored network was kept" not in flat(SPEC_TEXT)
    assert set(provisioning["reply_by_firmware"]) == {"35", "37", "38", "39"}
    assert DETAILS["setup_access_point"]["purpose"].startswith("A provisioning hook and nothing else")

    assert setup["credentials"]["wifi_passphrase_protection"] == "plaintext"
    rejoin = setup["rejoin"]
    assert rejoin == dict(rejoin, in_place_supported=False, requires_factory_reset=False)
    assert "First try without touching the scale" in rejoin["steps"][0]["action"]
    assert any("point of no return" in step["action"] for step in rejoin["steps"])
    assert "more than one stored network" not in flat(rejoin["notes"])


def test_battery_handling_claims_no_more_than_the_logs_show():
    reset = SPEC["device"]["setup"]["factory_reset"]
    assert reset["applicable"] == "unknown" and reset["confidence"] == "low"
    assert all(p["verified"] is False and p["basis"].strip() for p in reset["procedures"])
    effect = flat(reset["effect"])
    assert "does not show that the Wi-Fi key survived" in effect
    assert "not established on any firmware" in effect
    assert "only the clock" not in effect
    # The first thing the block tells an owner is what not to do, and the
    # console's clearing commands are named only to be refused.
    description = flat(reset["description"])
    assert description.startswith("Do not attempt a reset as troubleshooting, and do not remove the scale")
    assert "No way to clear a scale before it is sold or given away is established" in description
    assert "Do not run them" in description and "may destroy calibration or identity for good" in description
    procedure = reset["procedures"][0]
    assert "what it erases is not established" in procedure["name"]
    assert "CONSEQUENCE" in procedure["description"]
    assert "Do not press or step on the scale" in procedure["steps"][0]["action"]
    first = SPEC["remaining_unknowns"][0]
    assert first.startswith("HIGHEST PRIORITY") and "38 or 39" in first and "ONLY on a spare scale" in first
    # The battery-pull experiment on a working scale states what it risks.
    assert "RISK of (a)" in first and "the only way back is the direct setup request" in first
    assert "never on a scale whose vendor sync matters" in first
    # Nowhere is a battery pull recommended to refresh DNS.
    assert "makes it look the name up again" not in flat(SPEC_TEXT)


def test_pairing_says_who_the_scale_trusts():
    pairing = SPEC["device"]["pairing"]
    assert pairing["required"] is False
    assert (pairing["security_mode"], pairing["bonding"]) == ("none", "none")
    assert pairing["enter_pairing_mode"]["required"] is False
    assert pairing["confidence"] == "medium"
    assert "www.fitbit.com" in pairing["notes"] and "does not authenticate" in pairing["notes"]
    assert "cannot be undone" in pairing["notes"]


# ── Other local routes, rated ────────────────────────────────────────────────


def test_local_routes_carry_the_ratings_and_the_refusals():
    routes = DETAILS["local_routes"]
    by_id = {r["id"]: r for r in routes["routes"]}
    assert list(by_id) == [
        "dns_override_lan_server",
        "pass_through_relay",
        "same_network_name_and_passphrase",
        "direct_setup_request",
        "plain_scale",
    ]
    for route in by_id.values():
        for key in ("evidence", "needs", "gives", "brick_risk", "pairing_impact"):
            assert route[key].strip(), f"{route['id']}.{key}"
    assert by_id["dns_override_lan_server"]["standing"] == "The primary route."
    assert "No setup mode needed" in by_id["dns_override_lan_server"]["pairing_impact"]
    assert "keep vendor sync" in by_id["dns_override_lan_server"]["who_should_not"]
    relay = by_id["pass_through_relay"]
    assert relay["evidence"].startswith("hardware-demonstrated")
    assert relay["pairing_impact"].startswith("None")
    # Not neutral for firmware: rated "none" only while no signal is handed on.
    assert relay["brick_risk"].startswith("none while no update signal is handed to the scale")
    assert "unknown for a relay that hands one on" in relay["brick_risk"]
    assert by_id["same_network_name_and_passphrase"]["evidence"] == "inferred"
    assert by_id["direct_setup_request"]["pairing_impact"].startswith("ONE-WAY")
    assert "provisioning hook only" in by_id["direct_setup_request"]["details"]
    assert by_id["plain_scale"]["evidence"] == "vendor-documented"

    variants = {v["id"]: v for v in routes["variants_of_the_primary_route"]}
    assert set(variants) == {
        "per_device_dhcp_resolver",
        "destination_nat",
        "dedicated_access_point_or_travel_router",
        "all_in_one_esp32",
    }
    for variant in variants.values():
        assert variant["brick_risk"] == "none" and variant["evidence"].strip()
    assert variants["per_device_dhcp_resolver"]["evidence"].startswith("inferred")
    assert "nobody has published it for this scale" in variants["destination_nat"]["evidence"]
    assert "pieces demonstrated, bundle not published" in variants["dedicated_access_point_or_travel_router"]["evidence"]
    esp32 = variants["all_in_one_esp32"]
    assert esp32["evidence"].startswith("author-reported on firmware 37")
    assert "pounds" in esp32["limits"] and "one user" in esp32["limits"]

    notes = {n["id"]: n for n in routes["research_notes"]}
    assert set(notes) == {"serial_console", "listen_only_logger", "load_cell_retrofit"}
    console = notes["serial_console"]
    assert console["standing"].startswith("Diagnostics only. It cannot redirect the scale")
    assert console["brick_risk"].startswith("unknown") and "4.0 V" in console["brick_risk"]
    warnings = " ".join(console["warnings"])
    assert "NEVER STAND ON THE SCALE WHILE IT IS WIRED TO MAINS-POWERED EQUIPMENT" in warnings
    assert "do not run them" in warnings
    assert notes["listen_only_logger"]["standing"] == "An idea. Nobody has built it."
    logger_needs = notes["listen_only_logger"]["needs"]
    assert "BATTERY OR ISOLATED POWER" in logger_needs
    for caution in ("series resistor", "Measure the line's level first", "Never leave an unpowered logger attached"):
        assert caution in logger_needs, caution
    assert notes["load_cell_retrofit"]["standing"].startswith("Last resort")
    assert notes["load_cell_retrofit"]["brick_risk"].startswith("recoverable (inferred")

    refused = {n["id"]: n["statement"] for n in routes["not_routes"]}
    assert set(refused) == {
        "bluetooth",
        "inbound_service_on_the_lan",
        "setup_page_alone_in_a_browser",
        "phone_app_for_setup",
        "state_changing_console_commands",
        "module_program_mode",
        "jtag",
        "internal_bus_tap",
        "modified_firmware_or_provoked_update",
    }
    assert refused["bluetooth"].startswith("The FB201 has no Bluetooth")
    assert refused["inbound_service_on_the_lan"].startswith("Never tested")
    for key in ("module_program_mode", "jtag"):
        assert "on an Aria" in refused[key] and "any erase is permanent" in refused[key]
    # One sentence each, and nothing that reads as a how-to.
    for key, statement in refused.items():
        assert len(statement) < 420, key
    assert len(routes["honest_negatives"]) == 5
    assert DETAILS["station_mode"]["inbound_services"].strip().startswith("NEVER TESTED")
    assert DETAILS["hardware"]["bluetooth"] == "None."


def test_a_relay_changes_the_firmware_exposure_and_has_rules():
    """With the redirect in place the scale's image request reaches the relay.

    So a relay is told to check the tail of every vendor reply, to withhold
    an update-form reply, and never to answer or forward the firmware path.
    The rule is this project's inference and is labelled as such.
    """
    relay = next(r for r in DETAILS["local_routes"]["routes"] if r["id"] == "pass_through_relay")
    exposure = relay["firmware_exposure"]
    assert exposure.startswith("A relay CHANGES the firmware-update exposure")
    assert "arrives at the relay, not at Fitbit" in exposure
    assert "nobody has published what a scale does when that fetch fails" in exposure
    rules = relay["relay_rules"]
    assert "inference" in rules["status"] and "nobody has tested it" in rules["status"]
    # The rule points at a table that exists and is stated in the table's terms.
    fmt, key = rules["check_every_vendor_reply_with"].split(".")[1:]
    assert FORMATS[fmt][key] and fmt == REFUSAL["in_format"]
    assert any("relay" in rule.lower() for rule in FORMATS[fmt][key])
    allowed = " or ".join(str(v) for v in REFUSAL["allowed_tail_word_values"])
    total = MESSAGES["upload_reply"]["total_length"]
    assert f"each {allowed}" in rules["hand_on_only"]
    assert f"exactly {total['base']} + {total['per_user']} * user_count" in rules["hand_on_only"]
    assert "Do not hand it to the scale" in rules["withhold"] and "error status" in rules["withhold"]
    assert rules["never_answer_or_forward_path_prefix"] == REFUSAL["never_serve_path_prefix"]
    assert rules["error_status"].startswith("Any status other than 200, with no binary body")
    # Withholding has a consequence, and so has each way out of it.
    consequence = rules["consequence_of_withholding"]
    for phrase in ("NO SYNC", "the owner's decision", "neither choice has been tested", "vendor sync ends"):
        assert phrase in consequence, phrase
    assert "no recovery from a failed update has been shown" in consequence
    # The relay's own parser, applied to the vectors: local and vendor-form
    # replies pass, and an update-form reply is refused (see the tail tests).
    for name in REPLY_VECTORS:
        assert parse_reply(vector_bytes(name))["crc_ok"]

    # Falling back to a local reply is a decision with a stated cost.
    limits = relay["limits"]
    assert "a decision, not an automatic fallback" in limits
    assert "never reach the Fitbit account" in limits and "replaces the scale's user list" in limits
    assert "needs a fallback" not in flat(SPEC_TEXT)
    outage = rules["on_vendor_error_or_timeout"]
    assert "error status" in outage and "not with a locally written reply" in outage
    assert "what happens when it fills is unknown" in outage

    never = {rule["id"]: rule["rule"] for rule in SERVER["requirements"]["must_never"]}
    assert "untested" in never["relay_hands_on_update_form"]
    assert "/scale/firmware/" in never["relay_hands_on_update_form"]
    assert "One exception, for a pass-through relay only" in never["non_200_for_valid_upload"]


def test_no_tail_summary_claims_more_agreement_than_the_project_table_shows():
    """0, 3, 0 is the recommendation; it is not what every hardware report sent."""
    whole = flat(SPEC_TEXT)
    for phrase in (
        "every local server with a hardware report",
        "the only one with hardware reports",
        "The only other tail with evidence",
        "the three local servers with hardware reports",
    ):
        assert phrase not in whole, phrase
    may = REFUSAL["what_a_server_may_send"]
    assert [entry.split(":")[0] for entry in may] == ["0, 3, 0", "0, 0, 0", "3, 3, 0"]
    assert may[0].startswith("0, 3, 0: the recommended tail")
    assert "aria-bridge" in may[2] and "not the recommendation" in may[2]
    # Everything a server "may send" is a tail the file records as seen.
    seen = [REFUSAL["tail_words_to_send"], *(e["words"] for e in REFUSAL["other_tails_seen_meaning_no_update"])]
    assert sorted(seen) == sorted([int(w) for w in entry.split(":")[0].split(", ")] for entry in may)
    bridge = next(p for p in DETAILS["public_implementations"]["projects"] if p["name"] == "aria-bridge")
    assert "firmware 39" in bridge["hardware_reported"] and "3, 3, 0" in bridge["caveats"]
    assert "aria-bridge" in field_of("AriaUploadReplyTail", "tail_word_0")["description"]
    assert "aria-bridge" in FORMATS["AriaUploadReplyTail"]["example_notes"]


def test_contributors_are_told_what_not_to_send():
    guidance = DETAILS["capture_guidance"]
    never = guidance["never"]
    for phrase in (
        "Do not test the firmware-update form on a scale",
        "Do not send test traffic to the vendor with a real serial",
        "Do not weigh on a scale that is wired to mains-powered equipment",
    ):
        assert phrase in never, phrase
    # The scale's own page and scripts are the vendor's code: facts, not files.
    assert "vendor's code" in guidance["do_not_share"] and "in your own words" in guidance["do_not_share"]
    assert not any("raw reply bytes" in item for item in guidance["capture"])
    assert "one-way door" in guidance["which_scale"] and "spare scale" in guidance["which_scale"]
    web_server = next(item for item in SPEC["remaining_unknowns"] if item.startswith("The setup web server"))
    assert "do not share the page or script files" in web_server and "spare scale" in web_server


def test_the_public_capture_set_is_cited_and_not_copied():
    captures = DETAILS["public_captures_2016"]
    assert captures["paper"]["arxiv"] == "1611.04880"
    assert captures["paper"]["url"] == "https://arxiv.org/abs/1611.04880"
    assert "CITED, NEVER COMMITTED" in captures["handling"]
    assert "available on request for research use" in captures["dataset_terms"]
    assert captures["verification"] == "reported"
    adds = " ".join(captures["adds"])
    for phrase in ("0, 0, 0 in 20 of 20", "0x36 in 20 of 20", "register, validate", "DHCP host name"):
        assert phrase in adds, phrase
    assert any("local server" in item for item in captures["does_not_show"])
    # Cited by repository, never by a file an owner could fetch by mistake.
    assert "raw.githubusercontent.com" not in SPEC_TEXT and ".pcap" not in SPEC_TEXT
    artifact = next(a for a in SPEC["evidence"]["artifacts"] if a["type"] == "public_capture_dataset")
    assert "never committed" in artifact["obtained_via"].lower()
    station = DETAILS["station_mode"]
    assert station["dhcp"]["parameter_request_list"] == [1, 3, 6, 15, 66, 67, 13, 44]
    assert station["dns"]["queries_per_session"] == 1
    assert len(station["sequence_after_setup"]) == 5


def test_advisories_are_present_and_cited():
    security = SPEC["device"]["security_advisory"]
    assert security["severity"] == "reported" and security["advisory_url"].startswith("https://")
    for phrase in ("OPEN", "clear-text", "plain HTTP", "2020", "protocol_details.firmware_danger"):
        assert phrase in security["detail"], phrase
    # The advisory is shown without the rest of the file. Its precautions
    # must not walk an owner of a working scale into setup mode.
    detail = flat(security["detail"])
    assert "NEVER re-provision a working scale for this" in detail
    assert "needs setup mode, which is a one-way door" in detail
    assert "leave the network it knows exactly as it is" in detail
    assert "For a scale that is run locally, keep the DNS override in place for good" in detail
    assert "an owner who keeps vendor sync adds no override" in detail
    # Nothing tells an owner to "clear" a scale, because no way to is established.
    assert "clear or keep hold" not in detail
    assert "no way to clear the stored passphrase or users is established" in detail
    assert "an Aria that stays in the house would then need setup mode" in detail
    safety = SPEC["device"]["safety_advisory"]
    assert safety["severity"] == "caution"
    assert "pacemaker" in safety["summary"] and "pregnancy" in safety["summary"]
    assert "MAINS-POWERED EQUIPMENT" in safety["detail"]
    assert safety["advisory_url"].endswith("manual_aria_en_US.pdf")
    assert safety["advisory_archive_url"].startswith("https://web.archive.org/web/2")


ISOLATION_ADVICE = re.compile(
    r"network name and passphrase of its own|separate (?:small )?network|guest or IoT network"
    r"|network segment does|its own small network|dedicated access point or travel router"
)


@pytest.mark.parametrize("path", [SPEC_PATH, PAGE_PATH], ids=["spec", "page"])
def test_advice_to_give_the_scale_its_own_network_names_the_one_way_door(path):
    """A joined scale can only be moved to another network through setup mode.

    So wherever either file talks about a network of the scale's own, the
    same passage says what moving a joined scale costs.
    """
    text = flat(path.read_text(encoding="utf-8"))
    hits = list(ISOLATION_ADVICE.finditer(text))
    assert len(hits) >= 4
    for match in hits:
        window = text[max(0, match.start() - 500) : match.end() + 500]
        assert re.search(r"setup mode|one-way|ONE-WAY|direct setup", window), window
    assert "give the scale a separate network name and passphrase" not in text
    assert "give the scale its own network name and passphrase" not in text
    assert "Best is a resolver or network segment only the scale uses" not in text


def test_vendor_links_warn_where_the_vendor_text_would_lead_into_setup_mode():
    links = {entry["url"]: entry for entry in SPEC["helpful_urls"]}
    assert len(links) == len(SPEC["helpful_urls"])
    use = links["https://support.google.com/googlehealth/answer/14236805"]
    assert "reconnect steps that must NOT be followed for this model" in flat(use["description"])
    assert "one-way door" in flat(use["description"]) and "dead web page" in flat(use["description"])
    setup = links["https://support.google.com/googlehealth/answer/14236818"]
    # Titles are the pages' own headings as last read.
    assert setup["title"] == "Google Health help: Set up your Fitbit device"
    assert "dead web page" in flat(setup["description"])
    erase = links["https://support.google.com/googlehealth/answer/14236515"]
    assert "What it erases is not established" in flat(erase["description"])
    hardware = DETAILS["hardware"]
    # Two readings of the Canadian certification number, both kept.
    assert hardware["ised_certification"] == "8542A-0000F201A"
    assert hardware["ised_certification_other_reading"].startswith("8542A-F201A")


def test_identification_is_only_as_strong_as_the_evidence():
    identification = SPEC["device"]["identification"]
    prefixes = {entry["prefix"]: entry for entry in identification["mac_prefixes"]}
    assert set(prefixes) == {"00:1D:C9", "20:F8:5E"}
    for entry in prefixes.values():
        assert entry["confidence"] == "low" and "IEEE registry" in entry["notes"]
    assert "GainSpan" in identification["notes"] and "not proof" in flat(identification["notes"])
    hardware = DETAILS["hardware"]
    assert hardware["fcc_id"] == "XRAFB201A" and hardware["model"] == "FB201"
    assert "802.11b only" in hardware["radio"]["standard"]
    assert any("5 GHz" in item for item in hardware["radio"]["cannot_join"])


def test_every_unknown_comes_with_a_way_to_close_it():
    unknowns = SPEC["remaining_unknowns"]
    assert len(unknowns) >= 30
    for item in unknowns:
        assert "Cheapest" in item or "Do NOT test" in item or "Not safely testable" in item, item
    assert SPEC["evidence"]["open_questions"].strip()
    assert all(artifact["type"] for artifact in SPEC["evidence"]["artifacts"])
    commits = [p["commit"] for p in DETAILS["public_implementations"]["projects"]]
    assert all(re.fullmatch(r"[0-9a-f]{40}", commit) for commit in commits)
    # Anything that needs setup mode is steered to a spare scale.
    for item in unknowns:
        if "setup mode" in item or "SETUP ACTIVE" in item or "re-run setup" in item:
            assert "spare" in item or "Not safely testable" in item, item


def test_protocol_version_2_is_history_not_a_second_contract():
    old = DETAILS["protocol_version_2_historical"]
    assert old["verification"] == "hypothesis"
    assert "Historical and reconstructed" in old["status"]
    assert set(old) == {"status", "firmware_example", "summary", "verification", "basis"}


# ── Identifier scrub ─────────────────────────────────────────────────────────

FULL_MAC = re.compile(r"\b[0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5}\b")
PRIVATE_ADDRESS = re.compile(
    r"(?<![\w.])(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
    r"|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}"
    r"|192\.168\.\d{1,3}\.\d{1,3})(?!\d)"
)
PUBLIC_ADDRESS = re.compile(r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.]*\d)")
ALLOWED_ADDRESSES = {
    "192.168.240.1",  # product-fixed: the scale's own setup access point
    "192.168.240.0",  # only as the network 192.168.240.0/24
    "192.168.1.50",  # the catalogue's placeholder for the owner's server
    "192.168.1.51",  # the catalogue's placeholder for a resolver handed to the scale
}


@pytest.mark.parametrize("path", [SPEC_PATH, PAGE_PATH], ids=["spec", "page"])
def test_no_real_unit_identifier_is_published(path):
    text = path.read_text(encoding="utf-8")
    macs = FULL_MAC.findall(text)
    assert macs, "the documentation-range MAC should appear at least once"
    assert all(mac.lower().startswith("00:00:5e:00:53:") for mac in macs), macs
    assert set(PRIVATE_ADDRESS.findall(text)) <= ALLOWED_ADDRESSES
    # No other dotted address either: a relay's vendor address is the
    # operator's to look up, not ours to print.
    assert set(PUBLIC_ADDRESS.findall(text)) <= ALLOWED_ADDRESSES
    for match in re.finditer(r"192\.168\.240\.0", text):
        assert text[match.end() : match.end() + 3] == "/24"
    # Host names in the pattern the scale sends carry only the placeholder suffix.
    assert set(re.findall(r"GainSpan[0-9a-f]{6}\b", text)) <= {"GainSpan005301"}
    assert set(re.findall(r"Aria [0-9A-F]{6}\b", text)) <= {"Aria 005301"}
    # The vectors' MAC and auth code are the invented ones, wherever they appear.
    header = VECTORS["upload_request_two_records"]["decoded"]["header"]
    assert header["mac"] == "00005e005301"
    assert header["auth_code"] == bytes(range(0xA0, 0xB0)).hex()


# ── The device page says the same thing as the spec ─────────────────────────


def test_the_device_page_agrees_with_the_spec():
    page = PAGE_PATH.read_text(encoding="utf-8")
    text = flat(page)
    assert "| Pairing required | No" in page
    for fact in (
        "2026-11-09",
        "2026-11-23",
        "FB201",
        "XRAFB201A",
        "www.fitbit.com",
        "192.168.240.1",
        "/scale/setup",
        "/scale/register",
        "/scale/validate",
        "/scale/upload",
        "custom_password",
        "CRC-16/XMODEM",
        "0x31c3",
        "SETUP ACTIVE",
        "TAP TO CHANGE",
        "NO SYNC",
        "pacemaker",
        "GainSpan",
        "0x36",
        "arxiv.org/abs/1611.04880",
        "test_fitbit_aria_wifi_scale_spec.py",
    ):
        assert fact in text, fact
    assert "0, 3, 0" in text and "0, 0, 0" in text and "never" in text.lower()
    assert "redirect" in text.lower() and "untested" in text.lower()
    # Any hex vector quoted on the page is one of the spec's, byte for byte.
    spec_hex = {vector_bytes(name).hex() for name in REQUEST_VECTORS + REPLY_VECTORS}
    quoted = {
        "".join(block.split())
        for block in re.findall(r"```text\n((?:[0-9a-f]+\n)+)```", page)
    }
    assert quoted, "the page should quote at least one vector"
    assert quoted <= spec_hex
    # What the page tells a server to send is the tail the spec tells it to send.
    assert vector_bytes("upload_reply_one_user").hex() in quoted


def test_the_device_page_never_tells_an_owner_there_is_time_left():
    page = PAGE_PATH.read_text(encoding="utf-8")
    text = flat(page)
    status = next(line for line in page.splitlines() if line.startswith("> **Manufacturer Status**"))
    assert "has ended" in status and "2026-11-09" in status and "2026-11-28" not in status
    for phrase in (
        "Pairing ends",
        "ends 2026-11-28",
        "from 2026-11-28",
        "from **2026-11-28**",
        "after 2026-11-28",
        "before 2026-11-28",
        "while you still can pair",
    ):
        assert phrase not in text, phrase
    for match in re.finditer(r"2026-11-28|November 28|28 November", text):
        window = text[max(0, match.start() - 420) : match.end() + 320]
        assert re.search(r"2026-11-09|November 9|until 2026-11-23|still sa|at the time", window), window
    assert "Aria Air is not impacted by this change" in text
    assert "will continue to sync" in text


def test_the_device_page_carries_the_warnings_where_the_owner_acts():
    page = PAGE_PATH.read_text(encoding="utf-8")
    text = flat(page)
    # The redirect is not step one for everybody any more.
    assert "whichever situation you are in" not in text
    assert "Do not add the redirect" in text and "pass-through relay" in text
    # The one-way door, in those words, and the point of no return at the press.
    assert "one-way door" in text.lower() and "Point of no return" in text
    assert "Have the redirect and the server answering first" in text
    # Battery handling: no pull to refresh DNS; nothing stronger than the logs.
    assert "Do not pull a battery** to hurry it" in text
    assert "Do not pull a battery and do not press anything" in text
    assert "only the clock is lost" not in text
    assert "look the name up again" not in text
    # Firmware is a danger, and the other routes are rated.
    assert "\n### Firmware: a danger, not a route\n" in page
    assert "\n## Other local routes\n" in page
    assert "**Never stand on the scale while it is wired to mains-powered equipment.**" in text
    for phrase in (
        "No Bluetooth",
        "never tested",
        "Diagnostics only",
        "any erase is permanent",
        "mains-powered",
        "Nobody has built or flashed a modified image",
        "192.168.1.51",
        "not a browser",
    ):
        assert phrase in text, phrase
    # The two template paragraphs are no longer buried under the display table.
    assert page.index("**Factory reset**") < page.index("### What the display shows")
    assert page.index("**Rebinding to a new network**") < page.index("### What the display shows")


# ── The page's tables are the spec's tables ──────────────────────────────────
#
# The page restates the layouts by hand for people who will never open the
# YAML. A typo there is as harmful as one in the spec, so each hand-written
# row is compared with the field it describes.

PAGE_TYPE_NAMES = {
    "uint8": "u8",
    "uint16": "u16",
    "uint32": "u32",
    "float32": "float32",
    "bytes": "bytes",
    "string": "ASCII",
}
PAGE_UNIT_WORDS = {"g": "grams", "s": "Unix seconds", "%": "percent", "mm": "millimetres", "years": "years"}
PAGE_ENUM_WORDS = {"lb": "pounds", "st": "stone", "kg": "kilograms"}


def page_tables(page: str) -> list[dict]:
    """Every pipe table on the page: its header cells and its rows of cells."""
    tables, current = [], None
    for line in page.splitlines():
        if not line.startswith("|"):
            current = None
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if current is None:
            current = {"header": cells, "rows": []}
            tables.append(current)
        elif not set("".join(cells)) <= set("-: "):
            current["rows"].append(cells)
    return tables


def page_paragraph(page: str, start: str) -> str:
    """The one paragraph (or list item) of the page that begins with `start`."""
    found = [block for block in re.split(r"\n\s*\n", page) if block.lstrip().startswith(start)]
    assert len(found) == 1, f"{start!r}: {len(found)} paragraphs"
    return flat(found[0])


def _hex_or_decimal(value: int) -> tuple[str, str]:
    return str(value), f"`0x{value:02x}`"


def test_the_page_layout_tables_match_the_spec_field_for_field():
    page = PAGE_PATH.read_text(encoding="utf-8")
    layouts = [t for t in page_tables(page) if t["header"][0].startswith("Offset")]
    tail = FORMATS["AriaUploadReplyTail"]["fields"]
    trailer = [
        dict(field, offset=field["offset"] + MESSAGES["upload_reply"]["sections"][2]["length"])
        for field in FORMATS["AriaUploadReplyTrailer"]["fields"]
    ]
    expected = [
        FORMATS["AriaUploadRequestHeader"]["fields"],
        FORMATS["AriaUploadRecord"]["fields"],
        FORMATS["AriaUploadReplyHeader"]["fields"],
        FORMATS["AriaUploadReplyUser"]["fields"],
        [*tail, *trailer],
    ]
    assert len(layouts) == len(expected) == 5
    checked_values = 0
    for table, fields in zip(layouts, expected, strict=True):
        assert table["header"][1:4] == ["Length", "Field", "Type"]
        assert len(table["rows"]) == len(fields), table["header"]
        for row, field in zip(table["rows"], sorted(fields, key=lambda f: f["offset"]), strict=True):
            where = f"{field['name']}: {row}"
            assert (int(row[0]), int(row[1])) == (field["offset"], field["length"]), where
            assert row[3] == PAGE_TYPE_NAMES[field["type"]], where
            cell = row[4]
            if isinstance(field.get("constant"), int):
                assert any(f"always {text}" in cell for text in _hex_or_decimal(field["constant"])), where
                checked_values += 1
            if "server_sends" in field:
                assert any(f"send {text}" in cell for text in _hex_or_decimal(field["server_sends"])), where
                checked_values += 1
            for forbidden in field.get("never_send", []):
                assert f"**Never {forbidden}**" in cell, where
                assert f"send {forbidden}" not in cell and f"send `0x{forbidden:02x}`" not in cell, where
            if field.get("unit") in PAGE_UNIT_WORDS:
                assert PAGE_UNIT_WORDS[field["unit"]] in cell, where
            if field.get("scale") == 0.001:
                assert "thousandths" in cell, where
    # 4 constants (version, record constant, byte 6, word 57) and
    # 8 server choices (status, four previous-value words, three tail words).
    assert checked_values == 12

    def value_cell(table_index, name):
        fields = sorted(expected[table_index], key=lambda f: f["offset"])
        return layouts[table_index]["rows"][[f["name"] for f in fields].index(name)][4]

    unit = field_of("AriaUploadReplyHeader", "display_unit")
    unit_cell = value_cell(2, "display_unit")
    assert unit_cell == ", ".join(f"{raw} {PAGE_ENUM_WORDS[label]}" for raw, label in sorted(unit["values"].items()))
    sex = field_of("AriaUploadReplyUser", "sex")
    sex_cell = value_cell(3, "sex")
    for raw, label in sex["values"].items():
        assert f"`0x{raw:02x}` {label}" in sex_cell
    assert re.findall(r"0x[0-9a-f]{2}", sex_cell) == [f"0x{raw:02x}" for raw in sorted(sex["values"])]
    # The tail rows: what to send, and the one value never to send, on each.
    assert [value_cell(4, f"tail_word_{i}") for i in range(3)] == [
        f"send {word}. **Never 1**" for word in REFUSAL["tail_words_to_send"]
    ]

    # Headings and formulas carry the same numbers as the length tables.
    request, reply = MESSAGES["upload_request"], MESSAGES["upload_reply"]
    assert (
        f"### Upload request: `{request['total_length']['base']} + "
        f"{request['total_length']['per_record']} × records` bytes" in page
    )
    assert f"### Reply: `{reply['total_length']['base']} + {reply['total_length']['per_user']} × users` bytes" in page
    length = reply["length_field"]
    length_cell = value_cell(4, "length")
    assert length_cell.startswith(f"`{length['base']} + {length['per_user']} × users`")
    for users in (1, 2):
        assert f"`0x{length['base'] + length['per_user'] * users:02x}`" in length_cell

    # The route table names the three routes the spec declares, with their methods.
    routes = next(t for t in page_tables(page) if t["header"][:2] == ["Method", "Path"])
    assert [(row[0], row[1].strip("`").split("?")[0]) for row in routes["rows"]] == [
        (route["method"], route["path"]) for route in SERVER["routes"]
    ]


def test_the_page_states_the_crc_the_spec_declares():
    text = page_paragraph(PAGE_PATH.read_text(encoding="utf-8"), "CRC-16/XMODEM:")
    assert text.startswith(f"{CRC['name']}: polynomial `{CRC['polynomial_hex']}`, ")
    assert f"initial value `0x{CRC['initial_value']:04x}`, no reflection, no final XOR" in text
    assert f"is `{CRC['check_value_hex']}`" in text
    wire = bytes.fromhex(VECTORS["crc_check"]["wire_hex"])
    assert f"`{wire[0]:02x} {wire[1]:02x}`" in text
    # 0xffff appears once, and only as the mistake.
    mistake = f"0x{CRC['common_mistake']['initial_value']:04x}"
    assert text.count(mistake) == 1 and f"The usual mistake is initial value `{mistake}`" in text


def test_every_dns_line_on_the_page_names_one_host():
    page = PAGE_PATH.read_text(encoding="utf-8")
    name = SERVER["dns_override"]["name"]
    host_records = re.findall(r"host-record=([^,`\s]+),", page)
    address_lines = re.findall(r"address=/([^/`\s]+)/", page)
    arrows = re.findall(r"`([^`]+)` →\s+`192\.168\.1\.50`", page)
    assert host_records and address_lines and len(arrows) >= 3
    assert set(host_records) | set(address_lines) | set(arrows) == {name}
    for key, line in SERVER["dns_override"]["examples"].items():
        if key != "hosts_file_line":
            assert line in page, key
    # Wider names appear only where the page says not to use them.
    for wider in ("`fitbit.com`", "`*.fitbit.com`"):
        for match in re.finditer(re.escape(wider), page):
            assert re.search(r"[Nn]ot $", page[max(0, match.start() - 4) : match.start()]), wider
    assert "Redirect one name, do not block it." in page
    # The per-device form is the page's and the spec's, line for line.
    scoped = SERVER["dns_override"]["scale_only_example"]["dnsmasq_dhcp"].split("  and  ")
    assert len(scoped) == 2 and all(line in page for line in scoped)


def test_the_page_keeps_the_warnings_that_tests_did_not_pin_before():
    page = PAGE_PATH.read_text(encoding="utf-8")
    text = flat(page)
    # The danger box exists and says the thing it is there to say.
    box = re.search(r'\n!!! danger "One step cannot be undone"\n\n((?:    .*\n|\n)+)', page)
    assert box, "the one-way-door danger box is missing"
    box_text = flat(box.group(1))
    assert "one-way door" in box_text and "`SETUP ACTIVE`" in box_text
    assert "A scale that is already on your Wi-Fi never needs setup mode." in box_text

    unpairing = page_paragraph(page, "**Unpairing**")
    assert "Do not:" in unpairing and "cannot be paired again" in unpairing and "cannot be undone" in unpairing

    # The point of no return carries its consequence, and the method its scope.
    assert "From that moment assume the stored network is gone, even if you send nothing" in text
    assert "a scale which still synced to Fitbit has stopped for good" in text
    direct = page.split("### Last resort for Wi-Fi: direct setup (the one-way door)\n", 1)[1]
    assert direct.lstrip().startswith("For situation 4 only.")
    assert "http://192.168.240.1/scale/setup?ssid=" in direct
    assert "what follows is an untested suggestion" in flat(direct.split("\n### ", 1)[0]).replace("*", "")
    assert "the network was kept" not in text

    # Must never: the firmware bullet, in full.
    never = page.split("Your server **must never**:\n", 1)[1].split("\n### ", 1)[0]
    bullets = [flat(item) for item in re.split(r"(?m)^- ", never) if item.strip()]
    assert len(bullets) == 4
    bullet = bullets[0]
    assert bullet.startswith("**Signal a firmware update.** Never put 1 in any tail word")
    assert "never send a tail word other than 0 or 3" in bullet and "never add bytes to the reply" in bullet
    assert "Never serve anything under `/scale/firmware/`." in bullet

    # Isolation advice, selling, relay, experiments: the consequence is on the page.
    assert "**only if the scale is already on it**" in text
    assert "**do not move a working scale to another network for this**" in text
    assert "No way to clear the stored passphrase or users is established" in text
    assert "**A relay changes the firmware exposure.**" in text
    assert "neither adds to it nor removes" not in text and "needs a fallback" not in text
    assert "a decision, not an automatic fallback" in text.replace("** ", " ").replace("**", "")
    assert "Never answer or forward a request under `/scale/firmware/`." in text
    assert "**The risk:** if the key does not survive, the scale is off Wi-Fi" in text
    assert "**do not follow its reconnect steps for this model**" in text
    assert "**Do not share the scale's own setup page or script files**" in text
    assert "Every local server with a hardware report" not in text
    assert "aria-bridge, the one local server whose own author reports firmware 39, sends 3, 3, 0" in text


def test_the_page_route_table_rates_no_route_safer_than_the_spec():
    page = PAGE_PATH.read_text(encoding="utf-8")
    routes = DETAILS["local_routes"]
    by_id = {r["id"]: r for r in routes["routes"]}
    variants, notes = routes["variants_of_the_primary_route"], routes["research_notes"]
    in_page_order = [
        by_id["dns_override_lan_server"],
        by_id["pass_through_relay"],
        by_id["same_network_name_and_passphrase"],
        by_id["direct_setup_request"],
        *variants,
        by_id["plain_scale"],
        *notes,
    ]
    table = next(t for t in page_tables(page) if t["header"][:2] == ["Route", "Evidence"])
    assert table["header"] == ["Route", "Evidence", "Needs", "Brick risk", "Pairing impact"]
    assert len(table["rows"]) == len(in_page_order) == 12
    for row, entry in zip(table["rows"], in_page_order, strict=True):
        risk = row[3].replace("*", "").lower()
        rating = re.match(r"[a-z]+", entry["brick_risk"]).group(0)
        assert rating in {"none", "unknown", "recoverable", "unrecoverable"}, entry["id"]
        assert risk.startswith(rating), f"{entry['id']}: {row[3]!r}"
        # A rating that is qualified in the spec is qualified on the page.
        if "unknown" in entry["brick_risk"]:
            assert "unknown" in risk, entry["id"]
        if entry["pairing_impact"].startswith("ONE-WAY"):
            assert "one-way" in row[4].lower(), entry["id"]
        if "one-way" in entry["pairing_impact"]:
            assert "direct setup" in row[4].lower(), entry["id"]
    console_row = table["rows"][9]
    assert "serial console" in console_row[0] and console_row[3] == "**Unknown**"
