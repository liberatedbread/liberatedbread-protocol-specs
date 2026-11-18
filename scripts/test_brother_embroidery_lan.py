# Copyright 2026 Pigs Can Fly Labs LLC
# SPDX-License-Identifier: Apache-2.0
"""Independently exercise the reported Brother monitor discovery and JSON rules.

The BER/SNMP and JSON routines below use only the Python standard library and
import no project protocol implementation. PyYAML is used only to read the spec.
The 84-byte request is desktop-derived, not a capture. JSON documents are
synthetic and identify no real machine.
"""

from __future__ import annotations

import copy
import json
import secrets
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SPEC_PATH = REPO_ROOT / "device-specs" / "devices" / "brother-embroidery-lan.yaml"
DESKTOP_REQUEST = bytes.fromhex(
    "30815102010004067075626c6963a08143020101020100020100308137300f"
    "060b2b060102011903020103010500300e060a2b06010201020201060105003014"
    "06102b0601040193030204038958050203000500"
)
HOST_DESCRIPTION_OID = (1, 3, 6, 1, 2, 1, 25, 3, 2, 1, 3, 1)
MAC_OID = (1, 3, 6, 1, 2, 1, 2, 2, 1, 6, 1)
IP_DATA_OID = (1, 3, 6, 1, 4, 1, 2435, 2, 4, 3, 1240, 5, 2, 3, 0)


@pytest.fixture(scope="module")
def spec() -> dict:
    return yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def endpoints(spec) -> dict:
    return {entry["path"]: entry for entry in spec["http_endpoints"]}


class ProtocolError(ValueError):
    pass


def encode_length(length: int, force_long: bool = False) -> bytes:
    if length < 0:
        raise ProtocolError("negative length")
    if force_long and length < 0x80:
        return b"\x81" + bytes([length])
    if length < 0x80:
        return bytes([length])
    body = length.to_bytes((length.bit_length() + 7) // 8, "big")
    return bytes([0x80 | len(body)]) + body


def tlv(tag: int, value: bytes, force_long: bool = False) -> bytes:
    return bytes([tag]) + encode_length(len(value), force_long) + value


def integer(value: int) -> bytes:
    if not 0 <= value <= 0x7FFFFFFF:
        raise ProtocolError("request ID outside positive SNMP Integer32 range")
    width = max(1, (value.bit_length() + 7) // 8)
    return tlv(0x02, value.to_bytes(width, "big"))


def dotted_oid(parts: tuple[int, ...]) -> bytes:
    if len(parts) < 2 or parts[0] > 2 or parts[1] > 39:
        raise ProtocolError("invalid OID")
    encoded = bytearray([40 * parts[0] + parts[1]])
    for part in parts[2:]:
        if part < 0:
            raise ProtocolError("negative OID arc")
        groups = [part & 0x7F]
        part >>= 7
        while part:
            groups.append(part & 0x7F)
            part >>= 7
        for index in range(len(groups) - 1, -1, -1):
            continuation = 0x80 if index > 0 else 0
            encoded.append(groups[index] | continuation)
    return bytes(encoded)


def null_varbind(parts: tuple[int, ...]) -> bytes:
    return tlv(0x30, tlv(0x06, dotted_oid(parts)) + b"\x05\x00")


def value_varbind(parts: tuple[int, ...], value: bytes) -> bytes:
    return tlv(0x30, tlv(0x06, dotted_oid(parts)) + tlv(0x04, value))


def snmp_packet(request_id: int, pdu_tag: int, varbinds: list[bytes]) -> bytes:
    pdu = tlv(
        pdu_tag,
        integer(request_id)
        + integer(0)
        + integer(0)
        + tlv(0x30, b"".join(varbinds), force_long=True),
        force_long=True,
    )
    return tlv(0x30, integer(0) + tlv(0x04, b"public") + pdu, force_long=True)


def desktop_request(request_id: int = 1) -> bytes:
    return snmp_packet(
        request_id,
        0xA0,
        [null_varbind(oid) for oid in (HOST_DESCRIPTION_OID, MAC_OID, IP_DATA_OID)],
    )


def fresh_request_id() -> int:
    return 1 + secrets.randbelow(0x7FFFFFFF)


class Reader:
    def __init__(self, data: bytes):
        self.data = data
        self.offset = 0

    def take(self, count: int) -> bytes:
        end = self.offset + count
        if count < 0 or end > len(self.data):
            raise ProtocolError("truncated BER value")
        result = self.data[self.offset : end]
        self.offset = end
        return result

    def read_tlv(self, expected_tag: int | None = None) -> tuple[int, bytes]:
        tag = self.take(1)[0]
        first_length = self.take(1)[0]
        if first_length < 0x80:
            length = first_length
        else:
            width = first_length & 0x7F
            if width == 0 or width > 4:
                raise ProtocolError("invalid BER length")
            length_bytes = self.take(width)
            if length_bytes[0] == 0:
                raise ProtocolError("non-minimal BER length")
            length = int.from_bytes(length_bytes, "big")
        if expected_tag is not None and tag != expected_tag:
            raise ProtocolError(f"expected tag {expected_tag:#x}, got {tag:#x}")
        return tag, self.take(length)

    def finish(self) -> None:
        if self.offset != len(self.data):
            raise ProtocolError("trailing BER data")


def decode_positive_integer(data: bytes) -> int:
    if not data or data[0] & 0x80:
        raise ProtocolError("negative or empty SNMP integer")
    if len(data) > 1 and data[0] == 0:
        raise ProtocolError("non-minimal SNMP integer")
    return int.from_bytes(data, "big")


def decode_oid(data: bytes) -> tuple[int, ...]:
    if not data:
        raise ProtocolError("empty OID")
    arcs = [data[0] // 40, data[0] % 40]
    offset = 1
    while offset < len(data):
        value = 0
        while True:
            byte = data[offset]
            offset += 1
            value = (value << 7) | (byte & 0x7F)
            if not byte & 0x80:
                break
            if offset == len(data):
                raise ProtocolError("unterminated OID arc")
        arcs.append(value)
    return tuple(arcs)


def discovery_response(request_id: int, description: bytes = b"brother sewing") -> bytes:
    return snmp_packet(
        request_id,
        0xA2,
        [value_varbind(HOST_DESCRIPTION_OID, description), value_varbind(MAC_OID, b"\x00\x1b\xa9\x00\x00\x01")],
    )


def validate_discovery_response(data: bytes, expected_request_id: int) -> dict[tuple[int, ...], bytes]:
    outer = Reader(data)
    _, sequence = outer.read_tlv(0x30)
    outer.finish()
    message = Reader(sequence)
    version = decode_positive_integer(message.read_tlv(0x02)[1])
    if version != 0:
        raise ProtocolError("not SNMPv1")
    community = message.read_tlv(0x04)[1]
    if community != b"public":
        raise ProtocolError("wrong community")
    pdu_tag, pdu = message.read_tlv()
    if pdu_tag != 0xA2:
        raise ProtocolError("not GetResponse")
    message.finish()
    pdu_reader = Reader(pdu)
    request_id = decode_positive_integer(pdu_reader.read_tlv(0x02)[1])
    if request_id != expected_request_id:
        raise ProtocolError("response request ID mismatch")
    if decode_positive_integer(pdu_reader.read_tlv(0x02)[1]) != 0:
        raise ProtocolError("SNMP error status")
    if decode_positive_integer(pdu_reader.read_tlv(0x02)[1]) != 0:
        raise ProtocolError("SNMP error index")
    _, varbind_data = pdu_reader.read_tlv(0x30)
    pdu_reader.finish()
    values: dict[tuple[int, ...], bytes] = {}
    varbinds = Reader(varbind_data)
    while varbinds.offset < len(varbind_data):
        _, varbind = varbinds.read_tlv(0x30)
        item = Reader(varbind)
        oid = decode_oid(item.read_tlv(0x06)[1])
        _, value = item.read_tlv()
        item.finish()
        values[oid] = value
    if values.get(HOST_DESCRIPTION_OID) != b"brother sewing":
        raise ProtocolError("not an exact brother sewing responder")
    return values


def parse_json_document(document: str) -> dict:
    try:
        value = json.loads(document)
    except (json.JSONDecodeError, UnicodeError) as error:
        raise ProtocolError("invalid or truncated JSON") from error
    if not isinstance(value, dict):
        raise ProtocolError("JSON response is not an object")
    return value


def monitoring_capability(info: dict) -> bool:
    apis = info.get("apis")
    if not isinstance(apis, dict):
        return False
    positive = False
    for name in ("monitoring", "monitoringpr"):
        block = apis.get(name)
        if block is None:
            continue
        if not isinstance(block, dict):
            raise ProtocolError(f"{name} is not an object")
        version = block.get("version")
        if version is not None and type(version) is not int:
            raise ProtocolError(f"{name}.version is not an integer")
        positive |= version is not None and version > 0
    monitoring = apis.get("monitoring")
    if isinstance(monitoring, dict):
        available = monitoring.get("availableversion")
        if available is not None:
            if not isinstance(available, str):
                raise ProtocolError("availableversion is not a string")
            positive |= available.split(".", 1)[0] == "1"
    return positive


def status_label(value: int) -> str:
    if type(value) is not int:
        raise ProtocolError("status is not an integer")
    labels = {
        10: "ready_home_embroidery",
        11: "ready_home_embroidery",
        12: "ready_pr",
        30: "embroidering",
        40: "waiting_for_thread",
        41: "paused",
        42: "stopped",
        50: "finished",
        60: "thread_error",
        61: "thread_error",
        62: "thread_broken_error",
        63: "other_error",
        70: "other_error",
        98: "settings_screen",
        99: "other_error",
    }
    return labels.get(value, f"unknown({value})")


def walk_values(value, key: str):
    if isinstance(value, dict):
        for child_key, child in value.items():
            if child_key == key:
                yield child
            yield from walk_values(child, key)
    elif isinstance(value, list):
        for child in value:
            yield from walk_values(child, key)


def test_desktop_derived_84_byte_request_is_rebuilt_exactly(spec):
    vector = spec["protocol_details"]["snmp_discovery"]["desktop_derived_request"]
    rebuilt = desktop_request(1)
    assert rebuilt == DESKTOP_REQUEST
    assert bytes.fromhex(vector["frame_hex"]) == rebuilt
    assert len(rebuilt) == vector["length_bytes"] == 84
    assert "DESKTOP-DERIVED" in vector["provenance"]
    assert "NOT A NETWORK CAPTURE" in vector["provenance"]
    assert rebuilt[17:20] == b"\x02\x01\x01"


def test_request_ids_are_fresh_range_checked_and_encoded():
    first = desktop_request(fresh_request_id())
    second = desktop_request(fresh_request_id())
    assert first != second
    assert len(desktop_request(0x01020304)) == 87
    assert b"\x02\x04\x01\x02\x03\x04" in desktop_request(0x01020304)
    for invalid in (-1, 0x80000000):
        with pytest.raises(ProtocolError):
            desktop_request(invalid)


def test_valid_discovery_response_requires_exact_host_description():
    values = validate_discovery_response(discovery_response(0x10203040), 0x10203040)
    assert values[HOST_DESCRIPTION_OID] == b"brother sewing"
    assert values[MAC_OID] == bytes.fromhex("001ba9000001")


@pytest.mark.parametrize(
    "mutation",
    [
        lambda data: data.replace(b"brother sewing", b"Brother sewing"),
        lambda data: data.replace(b"brother sewing", b"brother sewing plus"),
        lambda data: data.replace(b"public", b"privat"),
        lambda data: data[:5] + b"\x01" + data[6:],
        lambda data: data[:14] + b"\xa0" + data[15:],
    ],
)
def test_discovery_rejects_wrong_identity_community_version_and_pdu(mutation):
    data = mutation(discovery_response(0x01020304))
    with pytest.raises(ProtocolError):
        validate_discovery_response(data, 0x01020304)


def test_discovery_rejects_wrong_request_id_and_snmp_errors():
    with pytest.raises(ProtocolError, match="request ID mismatch"):
        validate_discovery_response(discovery_response(2), 1
    )
    packet = bytearray(discovery_response(1))
    packet[22] = 1
    with pytest.raises(ProtocolError, match="error status"):
        validate_discovery_response(bytes(packet), 1)


def test_every_truncated_snmp_datagram_is_rejected():
    response = discovery_response(1)
    for cut in range(len(response)):
        with pytest.raises(ProtocolError):
            validate_discovery_response(response[:cut], 1)


def test_ber_parser_rejects_trailing_and_nonminimal_lengths():
    with pytest.raises(ProtocolError, match="trailing BER"):
        validate_discovery_response(discovery_response(1) + b"\x00", 1)
    packet = bytearray(discovery_response(1))
    packet[1] = 0x82
    with pytest.raises(ProtocolError, match="truncated BER"):
        validate_discovery_response(bytes(packet), 1)


def test_all_synthetic_endpoint_documents_parse_and_have_expected_values(endpoints):
    expected_paths = {"/info", "/status", "/embinfo", "/embstatus"}
    assert set(endpoints) == expected_paths
    documents = {
        path: parse_json_document(endpoints[path]["response_body"]["example"])
        for path in expected_paths
    }
    info = documents["/info"]
    assert monitoring_capability(info) is True
    assert info["features"]["needles"] == 10
    assert info["machine-id"] == "INVENTED-MACHINE-0000"
    assert info["apis"]["monitoring"]["availableversion"] == "1.0"
    assert documents["/status"]["status"] == 30
    embinfo = documents["/embinfo"]
    assert embinfo["totaltime"] == 12
    assert embinfo["totalstitches"] == 1200
    assert embinfo["colors"][0]["time"] == 12
    assert embinfo["needlebars"][0]["needlebarspm"] == 400
    assert embinfo["colorchangeinfo"][0]["bar"][0]["threadname"] == "Invented blue"
    embstatus = documents["/embstatus"]
    assert embstatus["currenttime"] == 6
    assert embstatus["currentstitch"] == 600
    assert embstatus["x"] == 100.5


def test_json_unknown_properties_and_statuses_are_tolerated(endpoints):
    info = parse_json_document(endpoints["/info"]["response_body"]["example"])
    info["apis"]["monitoring"]["new-version-field"] = {"anything": [1, 2]}
    info["whole-new-api"] = [True, None, "future"]
    assert monitoring_capability(info) is True
    assert status_label(30) == "embroidering"
    assert status_label(50) == "finished"
    assert status_label(777) == "unknown(777)"
    with pytest.raises(ProtocolError):
        status_label(True)


def test_monitoring_capability_gate_variants():
    base = parse_json_document(
        '{"apis":{"monitoring":{"version":0,"availableversion":"2.0"},"monitoringpr":{"version":0}}}'
    )
    assert monitoring_capability(base) is False
    for path, value in (
        (("monitoring", "version"), 1),
        (("monitoringpr", "version"), 2),
        (("monitoring", "availableversion"), "1.9"),
    ):
        candidate = copy.deepcopy(base)
        candidate["apis"][path[0]][path[1]] = value
        assert monitoring_capability(candidate) is True
    assert monitoring_capability({}) is False
    with pytest.raises(ProtocolError):
        monitoring_capability({"apis": {"monitoring": {"version": True}}})


@pytest.mark.parametrize("path", ["/info", "/status", "/embinfo", "/embstatus"])
def test_truncated_and_trailing_json_is_rejected(endpoints, path):
    document = endpoints[path]["response_body"]["example"]
    with pytest.raises(ProtocolError):
        parse_json_document(document[: len(document) // 2])
    with pytest.raises(ProtocolError):
        parse_json_document(document + "not-json")
    with pytest.raises(ProtocolError):
        parse_json_document("[]")


def test_scope_has_no_dangerous_endpoints_or_executable_features(spec):
    endpoints = spec["http_endpoints"]
    assert [(entry["method"], entry["path"]) for entry in endpoints] == [
        ("GET", "/info"),
        ("GET", "/status"),
        ("GET", "/embinfo"),
        ("GET", "/embstatus"),
    ]
    assert "commands" not in spec
    assert "features" not in spec
    monitoring = spec["protocol_details"]["https_monitoring"]
    assert monitoring["allowed_methods"] == ["GET"]
    assert monitoring["allowed_paths"] == [entry["path"] for entry in endpoints]
    assert spec["protocol_details"]["excluded_operations"]["executable"] is False


def test_tls_is_user_approved_tofu_never_trust_all(spec):
    tls = spec["device"]["identification"]["tls"]
    assert tls["verification"] == "trust_on_first_use"
    tofu = spec["protocol_details"]["https_monitoring"]["tofu"]
    assert tofu["approval_required_before_first_get"] is True
    assert "changed_certificate" in tofu
    assert "trust-all certificates" in tofu["forbidden"]
    assert "trust-all hostnames" in tofu["forbidden"]
    assert "disabled certificate verification" in tofu["forbidden"]
    assert "unverified fallback to HTTP" in tofu["forbidden"]
    assert "never" in tls["notes"].lower()
    pairing = spec["device"]["pairing"]
    assert pairing["security_mode"] == "app_layer"
    assert pairing["unpair"]["requires_factory_reset"] is False


def test_family_is_not_an_ev1_model_id_matcher_and_pp1_stays_separate(spec):
    variants = spec["device"]["variants"]
    assert len(variants) == 17
    names = {entry["model"] for entry in variants}
    assert {"EV1", "EV1LE", "PR1060W", "XP1", "BP3600"} <= names
    assert "PP1" not in names
    assert "PP1E" not in names
    assert "CX1" not in names
    assert all("identification" not in entry for entry in variants)
    match = spec["device"]["discovery"]["methods"][0]["udp_broadcast"]["response_match"]
    assert match == [
        {
            "source": "binary:hr_device_descr",
            "match": "exact",
            "value": "brother sewing",
        }
    ]
    targets = spec["protocol_details"]["snmp_discovery"]["ordered_targets"]
    assert targets[0]["target"].startswith("Each active IPv4 interface")
    assert targets[1]["target"] == "255.255.255.255"


def test_every_fact_is_reported_and_every_procedure_unverified(spec):
    assert spec["device"]["testing"]["status"] == "untested"
    assert set(walk_values(spec, "verification")) == {"reported", "trust_on_first_use"}
    assert all(value is False for value in walk_values(spec, "verified"))
    for procedure in spec["device"]["setup"]["factory_reset"]["procedures"]:
        assert procedure["basis"]
        assert procedure["applies_to"]
