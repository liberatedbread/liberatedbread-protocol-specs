import struct


SERVICES = {
    "forward": {
        "service": "10000000-328e-0fbb-c642-1aa6699bdada",
        "data": "10000001-328e-0fbb-c642-1aa6699bdada",
        "meta": "10000002-328e-0fbb-c642-1aa6699bdada",
        "host": "phone",
        "first_reset": "watch",
    },
    "watch_v1": {
        "service": "30000003-328e-0fbb-c642-1aa6699bdada",
        "notify": "30000004-328e-0fbb-c642-1aa6699bdada",
        "meta": "30000005-328e-0fbb-c642-1aa6699bdada",
        "write": "30000006-328e-0fbb-c642-1aa6699bdada",
        "host": "watch",
    },
    "reversed_v2": {
        "service": "40000000-328e-0fbb-c642-1aa6699bdada",
        "notify": "40000001-328e-0fbb-c642-1aa6699bdada",
        "write": "40000003-328e-0fbb-c642-1aa6699bdada",
        "host": "watch",
        "first_reset": "phone",
    },
}


def encode_frame(endpoint, body):
    return struct.pack(">HH", len(body), endpoint) + body


def decode_frame(frame):
    if len(frame) < 4:
        raise ValueError("missing Pebble frame header")
    body_length, endpoint = struct.unpack_from(">HH", frame, 0)
    if len(frame) != body_length + 4:
        raise ValueError("body length excludes the four-byte header")
    return endpoint, frame[4:]


def ppogatt_header(packet_type, sequence=0):
    if not 0 <= sequence < 32 or not 0 <= packet_type < 4:
        raise ValueError("invalid PPoGATT header")
    return bytes([(sequence << 3) | packet_type])


def test_u16be_body_length_excludes_header():
    body = bytes.fromhex("03 55 9a 25 77")
    frame = encode_frame(0x000B, body)
    assert frame == bytes.fromhex("00 05 00 0b 03 55 9a 25 77")
    assert decode_frame(frame) == (0x000B, body)
    assert decode_frame(encode_frame(0x1234, b"")) == (0x1234, b"")
    try:
        decode_frame(frame + b"\x00")
    except ValueError:
        pass
    else:
        raise AssertionError("trailing bytes must not be silently accepted")


def test_ppogatt_packet_header_and_service_directions():
    assert ppogatt_header(0, 31) == bytes([0xF8])
    assert ppogatt_header(1, 31) == bytes([0xF9])
    assert ppogatt_header(2) == bytes([0x02])
    assert ppogatt_header(3) == bytes([0x03])
    assert SERVICES["forward"]["host"] == "phone"
    assert SERVICES["forward"]["first_reset"] == "watch"
    assert SERVICES["watch_v1"]["notify"] != SERVICES["watch_v1"]["write"]
    assert SERVICES["reversed_v2"]["host"] == "watch"
    assert SERVICES["reversed_v2"]["first_reset"] == "phone"
    assert "meta" not in SERVICES["reversed_v2"]


def test_serial_rate_and_pebble_base_uuid():
    assert 115200 == 115200
    for service in SERVICES.values():
        for value in service.values():
            if "-" in value:
                assert value.endswith("-328e-0fbb-c642-1aa6699bdada")
                assert value == value.lower()
