"""Stdlib-only F15/F31 delimited XOR decoder and stream fixtures."""

from __future__ import annotations

STOPPED = bytes.fromhex("02 51 00 51 03")
STARTING = bytes.fromhex("02 51 02 05 56 03")
RUNNING = bytes.fromhex("02 51 03 0d 00 20 00 09 00 03 00 00 00 53 00 26 03")
STOPPING = bytes.fromhex("02 51 04 0a 00 21 00 09 00 03 00 00 00 54 00 20 03")
POLL = bytes.fromhex("02 51 51 03")


def checksum(data: bytes) -> int:
    result = 0
    for value in data:
        result ^= value
    return result


def decode_frame(data: bytes) -> dict:
    if len(data) not in (5, 6, 17):
        raise ValueError("unsupported frame length")
    if len(data) > 108 or data[0] != 0x02 or data[-1] != 0x03:
        raise ValueError("bad delimiter or excess length")
    if checksum(data[1:-2]) != data[-2]:
        raise ValueError("bad XOR")
    if data[1] != 0x51:
        raise ValueError("unknown frame marker")
    mode = data[2]
    if mode not in (0, 2, 3, 4):
        raise ValueError("unknown operation mode")
    names = {0: "stopped", 2: "starting", 3: "running", 4: "stopping"}
    expected_lengths = {0: 5, 2: 6, 3: 17, 4: 17}
    if len(data) != expected_lengths[mode]:
        raise ValueError("operation mode and frame length do not match")
    result = {
        "mode": names[mode],
        "speed": 0.0,
        "heart_rate": 0,
        "elapsed_s": None,
        "distance_km": None,
    }
    if len(data) == 6:
        result["offset_3_raw"] = data[3]
    if len(data) == 17:
        result.update(
            speed=data[3] * 0.1,
            elapsed_s=int.from_bytes(data[5:7], "little"),
            distance_km=round(int.from_bytes(data[7:9], "little") * 0.001, 3),
            heart_rate=int.from_bytes(data[13:15], "little"),
        )
    return result


def expected_length(mode: int) -> int | None:
    return {0: 5, 2: 6, 3: 17, 4: 17}.get(mode)


class StreamDecoder:
    def __init__(self) -> None:
        self.buffer = bytearray()

    def feed(self, data: bytes) -> list[dict]:
        self.buffer.extend(data)
        output = []
        while self.buffer:
            start = self.buffer.find(0x02)
            if start < 0:
                self.buffer.clear()
                break
            if start:
                del self.buffer[:start]
            if len(self.buffer) < 5:
                break
            length = expected_length(self.buffer[2])
            if length is None:
                del self.buffer[0]
                continue
            if len(self.buffer) < length:
                break
            candidate = bytes(self.buffer[:length])
            try:
                output.append(decode_frame(candidate))
            except ValueError:
                del self.buffer[0]
                continue
            del self.buffer[:length]
        return output


def test_exact_mode_length_pairs_and_starting_reserved_byte() -> None:
    assert decode_frame(STARTING)["offset_3_raw"] == 0x05
    valid_lengths = {0: 5, 2: 6, 3: 17, 4: 17}
    for frame in (STOPPED, STARTING, RUNNING, STOPPING):
        for mode in (0, 2, 3, 4):
            if valid_lengths[mode] == len(frame):
                continue
            cross_combination = bytearray(frame)
            cross_combination[2] = mode
            cross_combination[-2] = checksum(cross_combination[1:-2])
            try:
                decode_frame(cross_combination)
            except ValueError:
                pass
            else:
                raise AssertionError("mode/length cross-combination accepted")
    for truncated in (STOPPED[:-1], STARTING[:-1], RUNNING[:-1], STOPPING[:-1]):
        try:
            decode_frame(truncated)
        except ValueError:
            pass
        else:
            raise AssertionError("truncated mode frame accepted")


def test_all_public_frame_vectors() -> None:
    assert decode_frame(STOPPED) == {
        "mode": "stopped",
        "speed": 0.0,
        "heart_rate": 0,
        "elapsed_s": None,
        "distance_km": None,
    }
    assert decode_frame(STARTING)["mode"] == "starting"
    running = decode_frame(RUNNING)
    assert running == {
        "mode": "running",
        "speed": 1.3,
        "elapsed_s": 32,
        "distance_km": 0.009,
        "heart_rate": 83,
    }
    stopping = decode_frame(STOPPING)
    assert stopping["mode"] == "stopping"
    assert stopping["speed"] == 1.0
    assert stopping["elapsed_s"] == 33
    assert stopping["distance_km"] == 0.009
    assert stopping["heart_rate"] == 84
    assert "incline" not in running and "energy" not in running


def test_fragmentation_and_coalesced_frames() -> None:
    stream = STOPPED + STARTING + RUNNING + STOPPING
    for fragment_size in (1, 2, 3, 7, 20):
        decoder = StreamDecoder()
        packets = []
        for offset in range(0, len(stream), fragment_size):
            packets.extend(decoder.feed(stream[offset : offset + fragment_size]))
        assert [packet["mode"] for packet in packets] == [
            "stopped",
            "starting",
            "running",
            "stopping",
        ]


def test_bad_checksum_recovers_at_next_valid_frame() -> None:
    bad = bytearray(RUNNING)
    bad[-2] ^= 1
    decoder = StreamDecoder()
    packets = decoder.feed(bytes(bad) + STOPPED)
    assert packets == [decode_frame(STOPPED)]


def test_malformed_delimiters_modes_lengths_and_truncation() -> None:
    unknown = bytearray(STOPPED)
    unknown[2] = 1
    unknown[-2] = checksum(unknown[1:-2])
    malformed = [
        b"",
        RUNNING[:-1],
        RUNNING + b"\x00",
        b"\x03" + RUNNING[1:],
        RUNNING[:-1] + b"\x04",
        bytes(unknown),
        b"\x02\x52\x00\x52\x03",
        bytes(7),
    ]
    for payload in malformed:
        try:
            decode_frame(payload)
        except ValueError:
            pass
        else:
            raise AssertionError("malformed frame accepted")


def test_fixed_status_poll_encoding_only() -> None:
    assert POLL == b"\x02\x51\x51\x03"
    assert len(POLL) == 4
