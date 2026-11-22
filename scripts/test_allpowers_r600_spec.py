"""Independent stdlib transcription of the ALLPOWERS R600 read-only codec."""

from __future__ import annotations

STATUS_REQUEST = bytes.fromhex("a5 65 b1 00 01 06 01 00 00 00 00 00")
STATUS = bytes.fromhex("a5 65 00 00 00 08 01 13 49 01 2c 00 96 00 78 50")
SETTINGS = bytes.fromhex("a5 65 00 00 00 06 03 b5 04 aa 55 03 af 27")


def xor_bytes(data: bytes) -> int:
    result = 0
    for value in data:
        result ^= value
    return result


def build_notification(command: int, payload: bytes) -> bytes:
    raw = bytes((0xA5, 0x65, 0, 0, 0, len(payload), command)) + payload
    return raw + bytes((xor_bytes(raw),))


def decode_notification(frame: bytes) -> dict:
    if len(frame) < 8:
        raise ValueError("short frame")
    if frame[:2] != b"\xa5\x65":
        raise ValueError("bad header")
    length = frame[5]
    if length > 128 or len(frame) != length + 8:
        raise ValueError("bad length")
    if xor_bytes(frame):
        raise ValueError("bad XOR")
    command = frame[6]
    payload = frame[7:-1]
    if command == 0x01:
        if len(payload) < 8:
            raise ValueError("short status")
        if payload[1] > 100:
            raise ValueError("invalid battery")
        return {
            "command": command,
            "dc": bool(payload[0] & 0x01),
            "ac": bool(payload[0] & 0x02),
            "light": bool(payload[0] & 0x10),
            "battery": payload[1],
            "input_w": int.from_bytes(payload[2:4], "big"),
            "output_w": int.from_bytes(payload[4:6], "big"),
            "remaining_min": int.from_bytes(payload[6:8], "big"),
        }
    if command == 0x03:
        if len(payload) < 6:
            raise ValueError("short settings")
        return {
            "command": command,
            "flags": payload[0],
            "eco_hours": payload[1],
            "reserved": payload[2:4],
            "hardware": payload[4],
            "firmware": payload[5],
        }
    return {"command": command, "payload": payload}


class StreamDecoder:
    def __init__(self) -> None:
        self.buffer = bytearray()
        self.discarded_bytes = 0
        self.discarded_frames = 0

    def feed(self, data: bytes) -> list[dict]:
        packets = []
        for start in range(0, len(data), 1024):
            self.buffer.extend(data[start : start + 1024])
            if len(self.buffer) > 4096:
                drop = len(self.buffer) - 4096
                del self.buffer[:drop]
                self.discarded_bytes += drop
            packets.extend(self._drain())
        return packets

    def _drain(self) -> list[dict]:
        packets = []
        while self.buffer:
            header = self.buffer.find(b"\xa5\x65")
            if header < 0:
                keep = 1 if self.buffer[-1] == 0xA5 else 0
                drop = len(self.buffer) - keep
                del self.buffer[:drop]
                self.discarded_bytes += drop
                break
            if header:
                del self.buffer[:header]
                self.discarded_bytes += header
            if len(self.buffer) < 7:
                break
            length = self.buffer[5]
            if length > 128:
                self.discarded_frames += 1
                del self.buffer[0]
                continue
            total = length + 8
            if len(self.buffer) < total:
                break
            candidate = bytes(self.buffer[:total])
            try:
                packet = decode_notification(candidate)
            except ValueError:
                self.discarded_frames += 1
                del self.buffer[0]
            else:
                del self.buffer[:total]
                packets.append(packet)
        return packets


def test_public_status_and_settings_vectors() -> None:
    status = decode_notification(STATUS)
    assert status == {
        "command": 1,
        "dc": True,
        "ac": True,
        "light": True,
        "battery": 73,
        "input_w": 300,
        "output_w": 150,
        "remaining_min": 120,
    }
    settings = decode_notification(SETTINGS)
    assert settings["hardware"] == 0x03
    assert settings["firmware"] == 0xAF
    assert settings["flags"] == 0xB5
    assert settings["eco_hours"] == 4
    assert settings["reserved"] == b"\xaa\x55"


def test_fixed_status_request_is_not_response_framed() -> None:
    assert STATUS_REQUEST.hex(" ") == "a5 65 b1 00 01 06 01 00 00 00 00 00"
    assert len(STATUS_REQUEST) == 12
    # The request has no response payload-length/checksum interpretation.
    assert STATUS_REQUEST[5] == 0x06
    assert STATUS_REQUEST[6] == 0x01


def test_fragmentation_coalescing_noise_and_partial_header() -> None:
    decoder = StreamDecoder()
    assert decoder.feed(b"noise\xa5") == []
    assert decoder.feed(STATUS[1:4]) == []
    assert decoder.feed(STATUS[4:10]) == []
    packets = decoder.feed(STATUS[10:] + SETTINGS)
    assert [packet["command"] for packet in packets] == [1, 3]
    assert not decoder.buffer


def test_bad_checksum_oversize_and_invalid_payload_recover() -> None:
    decoder = StreamDecoder()
    bad_status = bytearray(STATUS)
    bad_status[-1] ^= 0x80
    oversize = b"\xa5\x65\x00\x00\x00\xc8\x01"
    bad_battery = build_notification(1, bytes((0, 101, 0, 0, 0, 0, 0, 0)))
    packets = decoder.feed(bytes(bad_status) + oversize + bad_battery + STATUS)
    assert packets == [decode_notification(STATUS)]
    assert decoder.discarded_frames == 3


def test_invalid_outer_candidate_rescans_valid_inner_status() -> None:
    outer = bytearray(build_notification(0x35, b"\x00" + STATUS))
    outer[-1] ^= 0x80
    decoder = StreamDecoder()
    assert decoder.feed(outer) == [decode_notification(STATUS)]
    assert decoder.discarded_frames == 1
    assert not decoder.buffer


def test_short_long_and_checksum_validation() -> None:
    for malformed in (b"", b"\xa5\x65", STATUS[:-1], STATUS + b"\x00"):
        try:
            decode_notification(malformed)
        except ValueError:
            pass
        else:
            raise AssertionError("malformed frame accepted")
    bad = bytearray(STATUS)
    bad[0] = 0
    for mutate in (bad, STATUS[:-1] + bytes((STATUS[-1] ^ 1,))):
        try:
            decode_notification(bytes(mutate))
        except ValueError:
            pass
        else:
            raise AssertionError("bad frame accepted")


def test_oversized_noise_is_bounded_and_resynchronizes() -> None:
    decoder = StreamDecoder()
    assert decoder.feed(b"\x01" * 10000) == []
    assert len(decoder.buffer) <= 4096
    decoder.feed(b"\xff" * 5000 + STATUS[:1])
    packets = decoder.feed(STATUS[1:])
    assert packets == [decode_notification(STATUS)]
