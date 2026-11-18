"""Independent ZeTime framing and payload checks using the standard library.

No ZeTimeConnect or repository implementation is imported. YAML supplies the spec
and its invented vectors; all stream parsing/time encoding below is transcribed
from the document. No watch or personal history is accessed.
"""

from datetime import datetime
from pathlib import Path
import struct

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = ROOT / "device-specs" / "devices" / "mykronoz-zetime.yaml"


@pytest.fixture(scope="module")
def spec():
    return yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))


def hx(value):
    return bytes.fromhex(value)


def build_frame(subject, frame_type, payload=b""):
    return (
        bytes([0x6F, subject, frame_type])
        + struct.pack("<H", len(payload))
        + payload
        + b"\x8f"
    )


def parse_frame(frame):
    if len(frame) < 6 or frame[0] != 0x6F or frame[-1] != 0x8F:
        raise ValueError("bad envelope")
    length = struct.unpack_from("<H", frame, 3)[0]
    if len(frame) != length + 6:
        raise ValueError("inconsistent length")
    return frame[1], frame[2], frame[5:-1]


class StreamParser:
    def __init__(self):
        self.buffers = {"responses": bytearray(), "requests": bytearray()}

    def feed(self, stream, data):
        buffer = self.buffers[stream]
        buffer.extend(data)
        output = []
        while True:
            start = buffer.find(0x6F)
            if start < 0:
                buffer.clear()
                return output
            if start:
                del buffer[:start]
            if len(buffer) < 5:
                return output
            total = 6 + struct.unpack_from("<H", buffer, 3)[0]
            if total > 4096:
                del buffer[0]
                continue
            if len(buffer) < total:
                return output
            if buffer[total - 1] != 0x8F:
                del buffer[0]
                continue
            frame = bytes(buffer[:total])
            del buffer[:total]
            output.append((stream, parse_frame(frame)))


def response_for(frames, subject):
    return [
        (stream, frame)
        for stream, frame in frames
        if stream == "responses" and frame[0] == subject and frame[1] == 0x80
    ]


def time_payload(when, offset_minutes):
    timezone_hour = int(offset_minutes / 60)
    timezone_minute = abs(offset_minutes) % 60
    return (
        struct.pack("<H", when.year)
        + bytes(
            [
                when.month,
                when.day,
                when.hour,
                when.minute,
                when.second,
                0,
                0,
                1,
                timezone_hour & 0xFF,
                timezone_minute,
            ]
        )
    )


def test_serial_vector_and_strict_envelope(spec):
    vector = spec["protocol_details"]["serial"]["test_vector"]
    subject, frame_type, payload = parse_frame(hx(vector["frame_hex"]))
    assert (subject, frame_type) == (0x02, 0x80)
    assert payload == b"000000000000"
    assert vector["serial"] == "000000000000"
    frame = build_frame(subject, frame_type, payload)
    assert frame == hx(vector["frame_hex"])
    with pytest.raises(ValueError):
        parse_frame(frame[:3] + b"\x0d" + frame[4:])
    with pytest.raises(ValueError):
        parse_frame(frame[:-1] + b"\x00")


@pytest.mark.parametrize("split", [1, 2, 3, 5, 19, 20, 21, 40, 65])
def test_fragmented_and_coalesced_frames(split):
    long_frame = build_frame(0x54, 0x80, bytes(range(60)))
    following = build_frame(0x02, 0x80, b"000000000000")
    parser = StreamParser()
    wire = long_frame + following
    frames = []
    for offset in range(0, len(wire), split):
        frames.extend(parser.feed("responses", wire[offset : offset + split]))
    assert [frame[1] for frame in frames] == [
        (0x54, 0x80, bytes(range(60))),
        (0x02, 0x80, b"000000000000"),
    ]


def test_two_streams_never_share_frames():
    parser = StreamParser()
    response = build_frame(0x02, 0x80, b"serial")
    request = build_frame(0xD0, 0x80, b"music")
    frames = parser.feed("responses", response)
    frames += parser.feed("requests", request)
    assert response_for(frames, 0x02) == [
        ("responses", (0x02, 0x80, b"serial"))
    ]
    assert response_for(frames, 0xD0) == []
    assert frames[1] == ("requests", (0xD0, 0x80, b"music"))


def test_garbage_oversize_and_bad_terminator_resynchronize():
    parser = StreamParser()
    assert parser.feed("responses", b"\x00\xff\x6f\x02\x80\xff\xff") == []
    assert parser.feed("responses", b"\x6f\x02\x80\x01\x00\x00\x00") == []
    good = build_frame(0x02, 0x80, b"ok")
    frames = parser.feed("responses", good)
    assert frames == [("responses", (0x02, 0x80, b"ok"))]


def test_unrelated_subject_is_not_current_response():
    parser = StreamParser()
    parser.feed("responses", build_frame(0x99, 0x80, b"late"))
    frames = parser.feed("responses", build_frame(0x02, 0x80, b"good"))
    assert response_for(frames, 0x02) == [("responses", (0x02, 0x80, b"good"))]
    assert response_for(frames, 0x99) == []


def test_time_payload_vectors(spec):
    vectors = spec["protocol_details"]["time_sync"]["test_vectors"]
    positive = time_payload(datetime(2026, 11, 17, 12, 34, 56), 5 * 60 + 30)
    assert positive == hx(vectors[0]["payload_hex"])
    negative = time_payload(datetime(2026, 1, 6, 12, 0, 0), -(9 * 60 + 30))
    assert negative == hx(vectors[1]["payload_hex"])
    assert len(positive) == len(negative) == 12
    assert negative[10] == 0xF7 and negative[11] == 30


def test_history_layouts_and_short_bounds():
    availability = struct.pack("<HHHH", 4, 3, 2, 1)
    assert struct.unpack("<HHHH", availability) == (4, 3, 2, 1)

    activity = struct.pack("<HIIIII", 7, 1760000000, 1234, 56, 789, 12)
    assert len(activity) == 22
    assert struct.unpack("<HIIIII", activity) == (7, 1760000000, 1234, 56, 789, 12)

    sleep = struct.pack("<HIB", 8, 1760000001, 2)
    heart = struct.pack("<HIB", 9, 1760000002, 72)
    assert len(sleep) == len(heart) == 7
    assert struct.unpack("<HIB", sleep)[1:] == (1760000001, 2)
    assert struct.unpack("<HIB", heart)[1:] == (1760000002, 72)
    with pytest.raises(struct.error):
        struct.unpack("<HIIIII", activity[:-1])


def test_notification_vector_utf8_lengths(spec):
    payload = hx(spec["protocol_details"]["notification"]["test_vector"]["payload_hex"])
    kind, count, title_length, body_length = payload[:4]
    title_end = 4 + title_length
    body_end = title_end + body_length
    assert (kind, count, title_length, body_length) == (1, 1, 2, 3)
    assert payload[4:title_end] == b"Hi"
    assert payload[title_end:body_end] == b"abc"
    assert payload[body_end:] == b"20261117T123456"
    assert len(payload[body_end:]) == 15


def test_weather_signed_blocks_and_partial_semantics(spec):
    block = bytes([0, 18, 5, 21, 1])
    assert struct.unpack("<BbbbB", block) == (0, 18, 5, 21, 1)
    negative = struct.pack("<BbbbB", 0, -3, -7, 2, 7)
    assert struct.unpack("<BbbbB", negative) == (0, -3, -7, 2, 7)
    location = "Testville".encode()
    packet = block + negative + bytes(5) + bytes(5) + location
    assert len(packet) == 20 + len(location)
    assert packet[-len(location) :] == location
    boundary = spec["protocol_details"]["weather"]["support_boundary"]
    assert "J+1/J+2/J+3" in boundary
    assert "not implementable" in boundary


def test_gatt_commit_and_chunk_contract(spec):
    service = spec["services"][0]
    body = service["characteristics"][0]
    assert body["framing"]["max_chunk_size"] == 20
    assert body["properties"] == ["write_without_response"]
    responses = service["characteristics"][1]
    assert responses["commands"]["commit_message"]["value"] == [3]
    assert service["characteristics"][2]["properties"] == ["write_without_response"]
    assert service["characteristics"][3]["properties"] == ["notify"]
