"""Independent YUNMAI connected/broadcast transcriptions in the standard library.

No openScale or repository handler is imported. The only captured fixture is the
public address-zeroed M1827CH frame named in the spec; every other profile,
address and measurement is invented. No scale is contacted.
"""

from pathlib import Path
import struct

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = ROOT / "device-specs" / "devices" / "yunmai-scales.yaml"


@pytest.fixture(scope="module")
def spec():
    return yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))


def hx(value):
    return bytes.fromhex(value)


def xor_bytes(values):
    result = 0
    for value in values:
        result ^= value
    return result


def set_time_frame(timestamp):
    body = bytearray([0x0D, 0x0D, 0x11]) + struct.pack(">I", timestamp) + bytes(5)
    body.append(xor_bytes(body[1:]))
    return bytes(body)


def build_connected(protocol, timestamp=315532800, user=12345, weight=8000, impedance=500, inline=2500, response_type=2):
    if protocol < 0x1E:
        frame = bytearray(18)
    elif protocol <= 0x1F:
        frame = bytearray(20)
    else:
        raise ValueError("unsupported protocol")
    frame[0:5] = bytes([0x0D, protocol, len(frame), response_type, 0])
    frame[5:9] = struct.pack(">I", timestamp)
    frame[9:13] = struct.pack(">I", user)
    frame[13:15] = struct.pack(">H", weight)
    frame[15:17] = struct.pack(">H", impedance)
    if len(frame) == 20:
        frame[17:19] = struct.pack(">H", inline)
    frame[-1] = xor_bytes(frame[1:-1])
    return bytes(frame)


def parse_connected(frame, expected_user, host_time=None):
    if len(frame) < 5 or frame[0] != 0x0D:
        raise ValueError("bad response")
    if frame[2] != len(frame):
        raise ValueError("packet size")
    if xor_bytes(frame[1:-1]) != frame[-1]:
        raise ValueError("checksum")
    response_type = frame[3]
    if response_type == 1:
        return None
    if response_type != 2:
        raise ValueError("unknown response type")
    protocol = frame[1]
    expected_length = 18 if protocol < 0x1E else 20 if protocol <= 0x1F else None
    if expected_length is None:
        raise ValueError("unsupported protocol")
    if len(frame) != expected_length:
        raise ValueError("version length")
    timestamp, user = struct.unpack_from(">II", frame, 5)
    if user != expected_user:
        raise ValueError("target user")
    weight_raw, impedance = struct.unpack_from(">HH", frame, 13)
    if weight_raw == 0:
        raise ValueError("zero weight")
    if timestamp < 315532800 and host_time is not None:
        timestamp = host_time
    result = {
        "protocol": protocol,
        "timestamp": timestamp,
        "target_user_id": user,
        "weight_kg": weight_raw / 100,
        "impedance": impedance,
    }
    if expected_length == 20:
        result["inline_raw"] = struct.unpack_from(">H", frame, 17)[0] / 100
    return result


def test_set_time_and_older_final_vectors(spec):
    vectors = spec["protocol_details"]["connected_transport"]["test_vectors"]
    assert set_time_frame(315532800) == hx(vectors["set_time"]["frame_hex"])
    older = hx(vectors["older_final"]["frame_hex"])
    assert build_connected(0x13) == older
    decoded = parse_connected(older, 12345)
    assert decoded == {
        "protocol": 0x13,
        "timestamp": 315532800,
        "target_user_id": 12345,
        "weight_kg": 80.0,
        "impedance": 500,
    }


def test_connected_version_bounds_and_inline_field():
    for version in (0x00, 0x13, 0x1D):
        assert len(parse_connected(build_connected(version), 12345)["timestamp"].to_bytes(4, "big")) == 4
    for version in (0x1E, 0x1F):
        decoded = parse_connected(build_connected(version), 12345)
        assert decoded["inline_raw"] == 25.0
        assert decoded["weight_kg"] == 80.0
    future = bytearray(build_connected(0x1F))
    future[1] = 0x20
    future[-1] = xor_bytes(future[1:-1])
    with pytest.raises(ValueError, match="unsupported protocol"):
        parse_connected(future, 12345)


def test_connected_rejects_checksum_length_type_and_user_mismatch():
    frame = bytearray(build_connected(0x13))
    frame[-1] ^= 1
    with pytest.raises(ValueError, match="checksum"):
        parse_connected(frame, 12345)

    with pytest.raises(ValueError, match="packet size"):
        parse_connected(build_connected(0x13) + b"\x00", 12345)
    wrong_length = bytearray(build_connected(0x1E)[:18])
    wrong_length[2] = len(wrong_length)
    wrong_length[-1] = xor_bytes(wrong_length[1:-1])
    with pytest.raises(ValueError, match="version length"):
        parse_connected(wrong_length, 12345)
    with pytest.raises(ValueError, match="unknown response type"):
        parse_connected(build_connected(0x13, response_type=3), 12345)
    assert parse_connected(build_connected(0x13, response_type=1), 12345) is None
    with pytest.raises(ValueError, match="target user"):
        parse_connected(build_connected(0x13), 54321)


def test_timestamp_fallback_and_zero_weight():
    decoded = parse_connected(build_connected(0x13, timestamp=0), 12345, host_time=1760000000)
    assert decoded["timestamp"] == 1760000000
    with pytest.raises(ValueError, match="zero weight"):
        parse_connected(build_connected(0x13, weight=0), 12345)


def build_set_user(user=12345, height=170, sex=1, age=35, unit=1, activity=0):
    frame = bytearray([0x0D, 0x12, 0x10, 0x01, 0x00, 0x00])
    frame += struct.pack(">H", user)
    frame += bytes([height, sex, age, 0x55, 0x5A, 0, 0, unit, activity])
    frame.append(xor_bytes(frame[1:]))
    return bytes(frame)


def test_synthetic_set_user_profile():
    frame = build_set_user()
    assert len(frame) == 18
    assert struct.unpack_from(">H", frame, 6)[0] == 12345
    assert frame[8:17] == bytes([170, 1, 35, 0x55, 0x5A, 0, 0, 1, 0])
    assert xor_bytes(frame[1:-1]) == frame[-1]


def build_broadcast(session=4, state=3, weight=8000, impedance=500, signature="0b 74 17"):
    prefix = hx("00 5e 00 00 " + signature)
    body = bytes([session, state]) + struct.pack(">HH", weight, impedance)
    payload = prefix + body
    return payload + bytes([xor_bytes(payload[7:13])])


def parse_broadcast(manufacturer_id, payload, address):
    if len(payload) != 14:
        raise ValueError("payload length")
    if payload[4:7] not in (hx("0b 74 17"), hx("06 52 11")):
        raise ValueError("signature")
    if xor_bytes(payload[7:13]) != payload[13]:
        raise ValueError("checksum")
    octets = [int(part, 16) for part in address.split(":")]
    if len(octets) != 6:
        raise ValueError("address")
    if manufacturer_id != ((octets[4] << 8) | octets[5]):
        raise ValueError("address echo")
    if payload[:4] != bytes([octets[3], octets[2], octets[1], octets[0]]):
        raise ValueError("address echo")
    weight, impedance = struct.unpack_from(">HH", payload, 9)
    return {"state": payload[8], "weight_kg": weight / 100, "impedance": impedance}


def test_synthetic_broadcast_and_address_echo(spec):
    payload = build_broadcast()
    decoded = parse_broadcast(0x5301, payload, "00:00:5e:00:53:01")
    assert decoded == {"state": 3, "weight_kg": 80.0, "impedance": 500}
    assert spec["protocol_details"]["broadcast_transport"]["synthetic_example"]["manufacturer_id"] == 0x5301
    assert payload[-1] == 0xAD


def test_public_sanitized_m1827ch_only_capture(spec):
    capture = spec["protocol_details"]["broadcast_transport"]["public_sanitized_m1827ch"]
    decoded = parse_broadcast(0, hx(capture["payload_hex"]), "00:00:00:00:00:00")
    assert decoded == {"state": 3, "weight_kg": 87.65, "impedance": 354}
    assert capture["decoded"] == {
        "weight_kg": 87.65,
        "impedance_ohm": 354,
        "session": 127,
        "checksum": 0,
    }
    assert capture["manufacturer_id"] == 0
    assert "Only public captured evidence" in capture["scope"]


@pytest.mark.parametrize("mutation", ["length", "signature", "checksum", "address"])
def test_broadcast_rejects_malformed_or_relocated_frames(mutation):
    payload = bytearray(build_broadcast())
    with pytest.raises(ValueError):
        if mutation == "length":
            parse_broadcast(0x5301, payload[:-1], "00:00:5e:00:53:01")
        elif mutation == "signature":
            payload[5] ^= 1
            parse_broadcast(0x5301, payload, "00:00:5e:00:53:01")
        elif mutation == "checksum":
            payload[10] ^= 1
            parse_broadcast(0x5301, payload, "00:00:5e:00:53:01")
        else:
            parse_broadcast(0x5301, payload, "aa:bb:cc:dd:ee:ff")


class FinalRearmer:
    def __init__(self):
        self.armed = True

    def handle(self, frame):
        state = frame["state"]
        if state in (1, 2):
            self.armed = True
            return "rearm"
        if state != 3:
            return "ignore"
        if not self.armed:
            return "duplicate"
        if frame["weight_kg"] <= 0:
            return "invalid"
        self.armed = False
        return "publish"


def test_final_rearming_and_unknown_states():
    handler = FinalRearmer()
    final = {"state": 3, "weight_kg": 80.0, "impedance": 500}
    assert handler.handle(final) == "publish"
    assert handler.handle(final) == "duplicate"
    assert handler.handle(final) == "duplicate"
    assert handler.handle({"state": 1, "weight_kg": 79.0, "impedance": 0}) == "rearm"
    assert handler.handle(final) == "publish"
    assert handler.handle({"state": 99, "weight_kg": 80.0, "impedance": 500}) == "ignore"
    assert handler.handle(final) == "duplicate"
    assert handler.handle({"state": 2, "weight_kg": 80.0, "impedance": 0}) == "rearm"
    assert handler.handle(final) == "publish"


def test_broadcast_identity_is_not_company_id_or_service_only(spec):
    assert "manufacturer_data" not in spec["device"]["identification"]
    broadcast_method = spec["device"]["discovery"]["methods"][1]["ble"]
    assert "service_uuids" not in broadcast_method
    assert "company_id" not in broadcast_method
    assert "full manufacturer-frame" in broadcast_method["notes"]
    assert "never to assign" in spec["protocol_details"]["broadcast_transport"]["candidate_rule"]
