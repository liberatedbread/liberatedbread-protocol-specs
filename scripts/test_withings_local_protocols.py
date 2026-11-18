"""Independent stdlib vectors for Withings BLE WPP and WBS06 Classic FragFsm."""

from __future__ import annotations

import hashlib
import hmac
import struct
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
BLE = yaml.safe_load(
    (ROOT / "device-specs/devices/withings-body-smart-comp-ble.yaml").read_text(
        encoding="utf-8"
    )
)
CLASSIC = yaml.safe_load(
    (ROOT / "device-specs/devices/withings-body-wbs06-classic.yaml").read_text(
        encoding="utf-8"
    )
)
BLE_WPP = BLE["protocol_details"]["wpp"]
CLASSIC_WPP = CLASSIC["protocol_details"]["wpp"]
V = BLE_WPP["test_vectors"]
MAC = V["mac"]
KL = V["kl"]
DEVICE_CHALLENGE = bytes.fromhex(V["device_challenge_hex"])
CLIENT_CHALLENGE = bytes.fromhex(V["client_challenge_hex"])


class WppError(ValueError):
    pass


def pack_value(value: str | bytes) -> bytes:
    raw = value.encode("ascii") if isinstance(value, str) else value
    if len(raw) > 255:
        raise WppError("length-prefixed value is too long")
    return bytes((len(raw),)) + raw


def encode_tlv(kind: int, value: bytes) -> bytes:
    return struct.pack(">HH", kind, len(value)) + value


def encode_message(command: int, tlvs: list[tuple[int, bytes]] | None = None) -> bytes:
    payload = b"".join(encode_tlv(kind, value) for kind, value in tlvs or [])
    return struct.pack(">BHH", 1, command, len(payload)) + payload


def decode_message(raw: bytes) -> tuple[int, list[tuple[int, bytes]]]:
    if len(raw) < 5:
        raise WppError("short WPP header")
    version, command, length = struct.unpack_from(">BHH", raw)
    if version != 1 or len(raw) != 5 + length:
        raise WppError("bad WPP version or message length")
    tlvs = []
    offset = 5
    while offset < len(raw):
        if offset + 4 > len(raw):
            raise WppError("truncated TLV header")
        kind, size = struct.unpack_from(">HH", raw, offset)
        offset += 4
        if offset + size > len(raw):
            raise WppError("truncated TLV value")
        tlvs.append((kind, raw[offset : offset + size]))
        offset += size
    return command, tlvs


class WppReassembler:
    def __init__(self) -> None:
        self.buffer = bytearray()

    def feed(self, chunk: bytes) -> list[tuple[int, list[tuple[int, bytes]]]]:
        self.buffer.extend(chunk)
        messages = []
        while len(self.buffer) >= 5:
            if self.buffer[0] != 1:
                raise WppError("WPP stream is out of sync")
            length = struct.unpack_from(">H", self.buffer, 3)[0]
            if len(self.buffer) < 5 + length:
                break
            raw = bytes(self.buffer[: 5 + length])
            del self.buffer[: 5 + length]
            messages.append(decode_message(raw))
        return messages


def auth_answer(challenge: bytes, mac: str = MAC, kl: str = KL) -> bytes:
    if len(challenge) != 16:
        raise WppError("challenge must be exactly 16 bytes")
    if len(kl) != 32:
        raise WppError("kl must be exactly 32 characters")
    return hashlib.sha1(challenge + mac.encode("ascii") + kl.encode("ascii")).digest()


def challenge_reply() -> bytes:
    return encode_message(
        296,
        [
            (291, pack_value(auth_answer(DEVICE_CHALLENGE))),
            (290, pack_value(MAC) + pack_value(CLIENT_CHALLENGE)),
        ],
    )


def scale_proof() -> bytes:
    return encode_message(257, [(291, pack_value(auth_answer(CLIENT_CHALLENGE)))])


def verify_scale_proof(raw: bytes) -> bool:
    command, tlvs = decode_message(raw)
    if command != 257:
        return False
    proofs = [value for kind, value in tlvs if kind == 291]
    if len(proofs) != 1 or not proofs[0] or proofs[0][0] != 20:
        return False
    proof = proofs[0][1:]
    return len(proof) == 20 and hmac.compare_digest(
        proof, auth_answer(CLIENT_CHALLENGE)
    )


def parse_measurement_messages(
    messages: list[tuple[int, list[tuple[int, bytes]]]],
) -> list[dict]:
    groups = []
    current = None
    for command, tlvs in messages:
        if command & ~0x4000 != 271:
            continue
        for kind, value in tlvs:
            if kind == 278:
                current = None
                try:
                    if len(value) < 7:
                        raise WppError("short META")
                    uid, valid, slot_count = struct.unpack_from(">IBB", value)
                    expected = 7 + slot_count * 4 + 4
                    if len(value) != expected or valid > slot_count:
                        raise WppError("bad META bounds")
                    ids = [
                        struct.unpack_from(">I", value, 6 + index * 4)[0]
                        for index in range(slot_count)
                    ]
                    attrib, timestamp = struct.unpack_from(">BI", value, 6 + slot_count * 4)
                    current = {
                        "uid": uid,
                        "user_ids": ids[:valid],
                        "attrib": attrib,
                        "time": timestamp,
                        "values": [],
                    }
                    groups.append(current)
                except (struct.error, WppError):
                    current = None
            elif kind == 279:
                if current is None:
                    continue
                if len(value) != 8:
                    current = None
                    continue
                raw, measure_type, exponent = struct.unpack(">iHh", value)
                current["values"].append(
                    {
                        "time": current["time"],
                        "type": measure_type,
                        "raw": raw,
                        "exponent": exponent,
                        "value": Decimal(raw) * (Decimal(10) ** exponent),
                    }
                )
    return groups


def deduplicate(groups: list[dict]) -> dict[tuple[int, int], dict]:
    result = {}
    for group in groups:
        for measure in group["values"]:
            result[(measure["time"], measure["type"])] = measure
    return result


def test_sha1_answers_and_exact_advertised_mac_string() -> None:
    assert len(KL) == 32
    assert auth_answer(DEVICE_CHALLENGE).hex() == V["device_answer_sha1_hex"]
    assert auth_answer(CLIENT_CHALLENGE).hex() == V["client_answer_sha1_hex"]
    uppercase = auth_answer(DEVICE_CHALLENGE, mac=MAC.upper())
    assert uppercase.hex() == V["uppercase_mac_answer_sha1_hex"]
    assert uppercase.hex() != V["device_answer_sha1_hex"]
    assert auth_answer(DEVICE_CHALLENGE, mac=MAC.replace(":", "")).hex() != V[
        "device_answer_sha1_hex"
    ]


def test_mutual_challenge_layout_and_strict_verification() -> None:
    assert challenge_reply().hex(" ") == V["challenge_reply_hex"]
    command, tlvs = decode_message(challenge_reply())
    assert command == 296
    assert tlvs[0][0] == 291 and tlvs[0][1][0] == 20
    assert tlvs[1][0] == 290
    assert tlvs[1][1] == pack_value(MAC) + pack_value(CLIENT_CHALLENGE)
    assert scale_proof().hex(" ") == V["scale_proof_hex"]
    assert verify_scale_proof(scale_proof())
    _, proof_tlvs = decode_message(scale_proof())
    bad = bytearray(proof_tlvs[0][1])
    bad[-1] ^= 1
    assert not verify_scale_proof(encode_message(257, [(291, bytes(bad))]))
    assert not verify_scale_proof(encode_message(257, []))
    assert not verify_scale_proof(encode_message(296, proof_tlvs))


@pytest.mark.parametrize("challenge", [b"", bytes(15), bytes(17)])
def test_auth_rejects_non_16_byte_challenges(challenge: bytes) -> None:
    with pytest.raises(WppError, match="exactly 16 bytes"):
        auth_answer(challenge)


def test_wpp_probe_and_read_only_request_vectors() -> None:
    fields = V["probe_codec_fields"]
    probe = encode_message(
        257,
        [
            (298, struct.pack(">BBI", 1, 1, int(fields["app_version_hex"], 16))),
            (2344, struct.pack(">H", fields["os_version"])),
        ],
    )
    assert probe.hex(" ") == V["probe_codec_hex"]
    get_state = encode_message(271, [(276, struct.pack(">Bb", 0, 0))])
    get_all = encode_message(271, [(276, struct.pack(">Bb", 1, 0))])
    assert get_state.hex(" ") == V["get_state_hex"]
    assert get_all.hex(" ") == V["get_all_hex"]
    assert encode_message(261).hex(" ") == V["battery_request_hex"]
    assert encode_message(261, [(263, struct.pack(">H", 81))]).hex(" ") == V[
        "battery_reply_hex"
    ]
    assert encode_message(277).hex(" ") == V["sync_ok_hex"]
    assert encode_message(272).hex(" ") == V["disconnect_hex"]
    assert decode_message(get_all) == (271, [(276, b"\x01\x00")])


def test_wpp_reassembly_handles_fragmentation_and_back_to_back_messages() -> None:
    stream = bytes.fromhex(V["measurement_hex"]) + bytes.fromhex(V["list_end_hex"])
    for fragment_size in (1, 2, 3, 7, 17, len(stream)):
        reassembler = WppReassembler()
        messages = []
        for offset in range(0, len(stream), fragment_size):
            messages.extend(reassembler.feed(stream[offset : offset + fragment_size]))
        assert len(messages) == 2
        assert messages[0][0] == messages[1][0] == 271
        assert messages[1][1] == [(256, b"")]
        assert not reassembler.buffer


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        b"\x01\x01",
        b"\x02\x01\x01\x00\x00",
        b"\x01\x01\x01\x00\x05\x00\x01\x00\x09",
        b"\x01\x01\x01\x00\x01\x00",
    ],
)
def test_malformed_wpp_is_rejected(raw: bytes) -> None:
    with pytest.raises(WppError):
        decode_message(raw)


def test_exponent_scaling_metadata_and_timestamp_type_deduplication() -> None:
    messages = [
        decode_message(bytes.fromhex(V["measurement_hex"])),
        decode_message(bytes.fromhex(V["list_end_hex"])),
    ]
    groups = parse_measurement_messages(messages)
    assert len(groups) == 1
    group = groups[0]
    assert group["time"] == 1700000000
    assert group["user_ids"] == [42]
    assert 0xDEAD not in group["user_ids"] and 0xBEEF not in group["user_ids"]
    weight, fat_ratio = group["values"]
    assert weight["raw"] == 72345 and weight["exponent"] == -3
    assert weight["value"] == Decimal("72.345")
    assert fat_ratio["value"] == Decimal("21.5")
    duplicate_weight = dict(weight)
    heart_rate = {
        "time": weight["time"],
        "type": 11,
        "raw": 61,
        "exponent": 0,
        "value": Decimal(61),
    }
    deduped = deduplicate([group, {"values": [duplicate_weight, heart_rate]}])
    assert set(deduped) == {(1700000000, 1), (1700000000, 6), (1700000000, 11)}
    assert deduped[(1700000000, 1)]["value"] == Decimal("72.345")
    assert deduped[(1700000000, 11)]["value"] == Decimal(61)


def test_bad_metadata_drops_values_instead_of_moving_them_to_prior_group() -> None:
    _, good_tlvs = decode_message(bytes.fromhex(V["measurement_hex"]))
    good_meta = next(value for kind, value in good_tlvs if kind == 278)
    good_data = next(value for kind, value in good_tlvs if kind == 279)
    bad_meta = good_meta + b"\x00"
    groups = parse_measurement_messages(
        [
            (
                271,
                [(278, good_meta), (279, good_data), (278, bad_meta), (279, good_data)],
            )
        ]
    )
    assert len(groups) == 1
    assert len(groups[0]["values"]) == 1
    assert parse_measurement_messages([(271, [(279, good_data)])]) == []


def frag_frame(payload: bytes) -> bytes:
    if not 0 < len(payload) <= 0xFFFF:
        raise WppError("invalid FragFsm payload length")
    return struct.pack(">BBH", 1, 1, len(payload)) + payload


class FragFsm:
    def __init__(self) -> None:
        self.buffer = bytearray()

    def feed(self, chunk: bytes) -> list[bytes | None]:
        self.buffer.extend(chunk)
        events = []
        while len(self.buffer) >= 2:
            version, operation = self.buffer[:2]
            if version != 1 or operation not in (0, 1):
                raise WppError("bad FragFsm version or operation")
            if operation == 0:
                del self.buffer[:2]
                events.append(None)
                continue
            if len(self.buffer) < 4:
                break
            length = struct.unpack_from(">H", self.buffer, 2)[0]
            if length == 0:
                raise WppError("empty DATA frame")
            if len(self.buffer) < 4 + length:
                break
            events.append(bytes(self.buffer[4 : 4 + length]))
            del self.buffer[: 4 + length]
        return events


def test_fragfsm_reset_data_and_arbitrary_stream_fragmentation() -> None:
    vector = CLASSIC_WPP["test_vectors"]
    wpp = bytes.fromhex(vector["measurement_hex"])
    wrapped = frag_frame(wpp)
    assert wrapped.hex(" ") == vector["fragfsm_wrapped_measurement_hex"]
    stream = b"\x01\x00" + wrapped + frag_frame(bytes.fromhex(vector["list_end_hex"]))
    for fragment_size in (1, 2, 3, 4, 9, 31, len(stream)):
        frag = FragFsm()
        events = []
        for offset in range(0, len(stream), fragment_size):
            events.extend(frag.feed(stream[offset : offset + fragment_size]))
        assert events == [None, wpp, bytes.fromhex(vector["list_end_hex"])]
        assert not frag.buffer


def test_fragfsm_rejects_bad_frames_without_rescanning_payload() -> None:
    with pytest.raises(WppError, match="payload length"):
        frag_frame(b"")
    with pytest.raises(WppError, match="payload length"):
        frag_frame(bytes(65536))
    for raw in (b"\x02\x00", b"\x01\x02", b"\x01\x01\x00\x00"):
        with pytest.raises(WppError):
            FragFsm().feed(raw)
    partial = FragFsm()
    assert partial.feed(b"\x01") == []
    assert partial.feed(b"\x01\x00") == []
    assert partial.buffer


def test_ble_model_profiles_and_sync_ok_are_not_interchangeable() -> None:
    variants = {row["model"]: row for row in BLE["device"]["variants"]}
    assert set(variants) == {"WBS13", "WBS12"}
    services = {service["uuid"]: service for service in BLE["services"]}
    assert services["00000020-5749-5448-0010-000000000000"]["variants"] == [
        "WBS13"
    ]
    assert services["00000000-0000-5749-5448-494e47530000"]["variants"] == [
        "WBS12"
    ]
    wbs13 = services["00000020-5749-5448-0010-000000000000"]["characteristics"][0]
    wbs12 = services["00000000-0000-5749-5448-494e47530000"]["characteristics"][0]
    assert wbs13["uuid"] == "00000024-5749-5448-0010-000000000000"
    assert wbs12["uuid"] == "00000004-0000-5749-5448-494e47530000"
    operations = BLE_WPP["read_only_session"]["ordered_operations"]
    assert any("WBS13 only" in operation for operation in operations)
    assert any("WBS12: never" in operation for operation in operations)
    assert BLE["protocol_details"]["prohibited_writes"]["sync_ok"].startswith(
        "Prohibited on WBS12"
    )
    advertising = BLE["protocol_details"]["advertising"]
    assert advertising["with_uuid"]["accepted_models"] == [16]
    assert advertising["fd77"]["accepted_models"] == [18]


def test_wbs06_is_incoming_classic_weight_time_battery_only() -> None:
    classic = CLASSIC["bluetooth_classic"]
    assert CLASSIC["device"]["protocol"] == "bluetooth_classic"
    assert CLASSIC["device"]["integration"] == "identify_only"
    assert "none" in CLASSIC["device"]["discovery"]
    assert [profile["uuid"] for profile in classic["profiles"]] == [
        "00000001-e1ba-dfb7-c7f0-da2b149de289",
        "00009990-0000-1000-8000-00805f9b34fb",
    ]
    framing = classic["serial"]["framing"]
    assert framing["length_offset"] == 2
    assert framing["length_endianness"] == "big"
    assert framing["length_adjust"] == 4
    published = CLASSIC_WPP["read_only_session"]["published_values"]
    assert set(published) == {
        "weight",
        "weigh_in_time",
        "battery",
        "last_sync",
        "excluded",
    }
    operations = CLASSIC_WPP["read_only_session"]["ordered_operations"]
    assert any("Do NOT send or echo SYNC_OK" in operation for operation in operations)
    core = next(
        row
        for row in CLASSIC["device"]["host_compatibility"]
        if row["stack"] == "corebluetooth"
    )
    assert core["status"] == "incompatible"
    assert core["cause"] == {"missing_api": "rfcomm"}
    incompatible = CLASSIC["protocol_details"]["classic_listener"]["incompatible_hosts"]
    assert any("ESPHome" in host for host in incompatible)


def test_shared_synthetic_auth_vectors_do_not_drift_between_transports() -> None:
    classic_vectors = CLASSIC_WPP["test_vectors"]
    for key in (
        "mac",
        "kl",
        "device_challenge_hex",
        "client_challenge_hex",
        "device_answer_sha1_hex",
        "client_answer_sha1_hex",
        "challenge_reply_hex",
        "scale_proof_hex",
        "get_state_hex",
        "get_all_hex",
        "battery_request_hex",
        "battery_reply_hex",
        "disconnect_hex",
        "measurement_hex",
    ):
        assert classic_vectors[key] == V[key]
    for spec in (BLE, CLASSIC):
        assert spec["device"]["testing"]["status"] == "untested"
        assert spec["device"]["integration"] == "identify_only"
