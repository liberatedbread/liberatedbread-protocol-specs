"""Independent transcription of the Bridgething DEAD v2 document.

The codec below uses only the Python standard library. It imports no project
protocol implementation and never talks to hardware. YAML is used only to read
the published fixtures and declarations.
"""

from __future__ import annotations

import gzip
import json
import random
import struct
import uuid
import zlib
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
SPEC_PATH = ROOT / "device-specs" / "devices" / "spotify-car-thing-bridgething.yaml"
MAGIC = b"\xde\xad"
VERSION = 2
HEADER_LEN = 16
FRAME_CAP = 16 * 1024 * 1024
NETWORK_CAP = 1024 * 1024
GZIP_THRESHOLD = 16256
PRIORITIES = {0: "normal", 1: "bulk", 2: "background"}
UUID_KEYS = {"id", "requestId", "transferId", "webapp"}


@pytest.fixture(scope="module")
def spec() -> dict:
    return yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def details(spec: dict) -> dict:
    return spec["protocol_details"]


@pytest.fixture(scope="module")
def vectors(details: dict) -> dict[str, dict]:
    return {vector["name"]: vector for vector in details["test_vectors"]}


def msgpack_decode(data: bytes) -> object:
    """Decode the named-map MessagePack subset used by the golden fixtures."""

    def read(offset: int) -> tuple[object, int]:
        marker = data[offset]
        offset += 1
        if marker <= 0x7F:
            return marker, offset
        if marker >= 0xE0:
            return marker - 0x100, offset
        if 0x80 <= marker <= 0x8F:
            return read_map(offset, marker & 0x0F)
        if 0x90 <= marker <= 0x9F:
            return read_array(offset, marker & 0x0F)
        if 0xA0 <= marker <= 0xBF:
            return read_str(offset, marker & 0x1F)
        if marker == 0xC0:
            return None, offset
        if marker in (0xC2, 0xC3):
            return marker == 0xC3, offset
        if marker in (0xC4, 0xC5, 0xC6):
            width = {0xC4: 1, 0xC5: 2, 0xC6: 4}[marker]
            size = int.from_bytes(data[offset : offset + width], "big")
            offset += width
            end = offset + size
            return data[offset:end], end
        if marker in (0xCA, 0xCB):
            fmt, width = (">f", 4) if marker == 0xCA else (">d", 8)
            return struct.unpack(fmt, data[offset : offset + width])[0], offset + width
        if 0xCC <= marker <= 0xCF:
            width = 1 << (marker - 0xCC)
            return int.from_bytes(data[offset : offset + width], "big"), offset + width
        if 0xD0 <= marker <= 0xD3:
            width = 1 << (marker - 0xD0)
            return int.from_bytes(data[offset : offset + width], "big", signed=True), offset + width
        if marker in (0xD9, 0xDA, 0xDB):
            width = {0xD9: 1, 0xDA: 2, 0xDB: 4}[marker]
            size = int.from_bytes(data[offset : offset + width], "big")
            return read_str(offset + width, size)
        if marker in (0xDC, 0xDD):
            width = 2 if marker == 0xDC else 4
            size = int.from_bytes(data[offset : offset + width], "big")
            return read_array(offset + width, size)
        if marker in (0xDE, 0xDF):
            width = 2 if marker == 0xDE else 4
            size = int.from_bytes(data[offset : offset + width], "big")
            return read_map(offset + width, size)
        raise ValueError(f"unsupported MessagePack marker 0x{marker:02x}")

    def take(size: int, offset: int) -> tuple[bytes, int]:
        end = offset + size
        if end > len(data):
            raise ValueError("truncated MessagePack value")
        return data[offset:end], end

    def read_str(offset: int, size: int) -> tuple[str, int]:
        raw, end = take(size, offset)
        return raw.decode("utf-8"), end

    def read_array(offset: int, size: int) -> tuple[list, int]:
        result = []
        for _ in range(size):
            value, offset = read(offset)
            result.append(value)
        return result, offset

    def read_map(offset: int, size: int) -> tuple[dict, int]:
        result = {}
        for _ in range(size):
            key, offset = read(offset)
            value, offset = read(offset)
            result[key] = value
        return result, offset

    value, end = read(0)
    if end != len(data):
        raise ValueError("trailing bytes after one MessagePack envelope")
    return value


def msgpack_encode(value: object) -> bytes:
    """Encode named maps with the shortest integer/string widths."""

    def encode(item: object) -> bytes:
        if item is None:
            return b"\xc0"
        if item is False:
            return b"\xc2"
        if item is True:
            return b"\xc3"
        if isinstance(item, int):
            if 0 <= item <= 0x7F:
                return bytes([item])
            if -32 <= item < 0:
                return bytes([item & 0xFF])
            if item >= 0:
                for marker, width in ((0xCC, 1), (0xCD, 2), (0xCE, 4), (0xCF, 8)):
                    if item < 1 << (8 * width):
                        return bytes([marker]) + item.to_bytes(width, "big")
            else:
                for marker, width in ((0xD0, 1), (0xD1, 2), (0xD2, 4), (0xD3, 8)):
                    if -(1 << (8 * width - 1)) <= item < 1 << (8 * width - 1):
                        return bytes([marker]) + item.to_bytes(width, "big", signed=True)
            raise OverflowError(item)
        if isinstance(item, str):
            raw = item.encode("utf-8")
            size = len(raw)
            if size < 32:
                return bytes([0xA0 | size]) + raw
            for marker, width in ((0xD9, 1), (0xDA, 2), (0xDB, 4)):
                if size < 1 << (8 * width):
                    return bytes([marker]) + size.to_bytes(width, "big") + raw
            raise OverflowError("string too long")
        if isinstance(item, bytes):
            size = len(item)
            for marker, width in ((0xC4, 1), (0xC5, 2), (0xC6, 4)):
                if size < 1 << (8 * width):
                    return bytes([marker]) + size.to_bytes(width, "big") + item
            raise OverflowError("binary too long")
        if isinstance(item, (list, tuple)):
            size = len(item)
            if size < 16:
                prefix = bytes([0x90 | size])
            elif size < 1 << 16:
                prefix = b"\xdc" + size.to_bytes(2, "big")
            else:
                prefix = b"\xdd" + size.to_bytes(4, "big")
            return prefix + b"".join(encode(part) for part in item)
        if isinstance(item, dict):
            size = len(item)
            if size < 16:
                prefix = bytes([0x80 | size])
            elif size < 1 << 16:
                prefix = b"\xde" + size.to_bytes(2, "big")
            else:
                prefix = b"\xdf" + size.to_bytes(4, "big")
            return prefix + b"".join(encode(key) + encode(part) for key, part in item.items())
        raise TypeError(type(item))

    return encode(value)


def uuid_bytes(value: str) -> bytes:
    return uuid.UUID(value).bytes


def encode_golden_envelope(decoded: dict) -> bytes:
    """Apply the documented JSON/raw-UUID mapping before MessagePack encoding."""

    def convert(value: object, key: str | None = None) -> object:
        if isinstance(value, dict):
            return {name: convert(part, name) for name, part in value.items()}
        if isinstance(value, list):
            if key == "bytes" and all(isinstance(part, int) for part in value):
                return bytes(value)
            return [convert(part) for part in value]
        if isinstance(value, str) and key in UUID_KEYS:
            return uuid_bytes(value)
        return value

    return msgpack_encode(convert(decoded))


def header(payload_len: int, *, compression: int = 0, encoding: int = 0, priority: int = 0) -> bytes:
    return (
        MAGIC
        + bytes([VERSION, compression, encoding, priority])
        + b"\x00\x00"
        + payload_len.to_bytes(8, "big")
    )


def frame(payload: bytes, *, compression: int = 0, encoding: int = 0, priority: int = 0) -> bytes:
    return header(len(payload), compression=compression, encoding=encoding, priority=priority) + payload


def automatic_frame(payload: bytes, priority: str = "normal") -> bytes:
    compression = 0
    body = payload
    if priority == "normal" and len(payload) > GZIP_THRESHOLD:
        zipped = gzip.compress(payload, compresslevel=1, mtime=0)
        if len(zipped) < len(payload):
            body = zipped
            compression = 1
    return frame(body, compression=compression, priority={v: k for k, v in PRIORITIES.items()}[priority])


class StreamDecoder:
    """Incremental RFCOMM/iAP2 decoder with bounded gzip expansion."""

    def __init__(self) -> None:
        self.buffer = bytearray()

    def feed(self, chunk: bytes) -> list[dict]:
        self.buffer.extend(chunk)
        output = []
        while True:
            if len(self.buffer) < 2:
                return output
            if self.buffer[:2] != MAGIC:
                next_magic = self.buffer.find(MAGIC, 1)
                if next_magic < 0:
                    del self.buffer[:-1]
                    return output
                del self.buffer[:next_magic]
                continue
            if len(self.buffer) < HEADER_LEN:
                return output
            if self.buffer[2] != VERSION:
                del self.buffer[0]
                continue
            length = int.from_bytes(self.buffer[8:16], "big")
            if length > FRAME_CAP:
                del self.buffer[0]
                continue
            total = HEADER_LEN + length
            if len(self.buffer) < total:
                return output
            raw_header = bytes(self.buffer[:HEADER_LEN])
            body = bytes(self.buffer[HEADER_LEN:total])
            del self.buffer[:total]
            compression = raw_header[3]
            if compression == 1:
                inflater = zlib.decompressobj(wbits=31)
                payload = inflater.decompress(body, FRAME_CAP + 1)
                if len(payload) > FRAME_CAP or inflater.unconsumed_tail:
                    raise ValueError("decompressed payload exceeds 16 MiB")
                payload += inflater.flush()
                if len(payload) > FRAME_CAP:
                    raise ValueError("decompressed payload exceeds 16 MiB")
            elif compression == 0:
                payload = body
            else:
                raise ValueError(f"unknown compression {compression}")
            encoding = raw_header[4]
            if encoding == 0:
                message = msgpack_decode(payload)
            elif encoding == 1:
                message = json.loads(payload)
            else:
                raise ValueError(f"unknown encoding {encoding}")
            output.append(
                {
                    "header": raw_header,
                    "priority": PRIORITIES.get(raw_header[5], "normal"),
                    "payload": payload,
                    "message": message,
                }
            )


def normalize_decoded(value: object, key: str | None = None) -> object:
    if isinstance(value, dict):
        return {name: normalize_decoded(part, name) for name, part in value.items()}
    if isinstance(value, list):
        return [normalize_decoded(part) for part in value]
    if isinstance(value, bytes):
        if key in UUID_KEYS and len(value) == 16:
            return str(uuid.UUID(bytes=value))
        return list(value)
    return value


def decode_vector(vector: dict) -> dict:
    wire = bytes.fromhex(vector["framed_hex"])
    decoder = StreamDecoder()
    frames = decoder.feed(wire)
    assert len(frames) == 1
    assert not decoder.buffer
    return frames[0]


def validate_network_message(message: bytes) -> list[dict]:
    if len(message) > NETWORK_CAP:
        raise ValueError("network gateway message exceeds 1 MiB")
    decoder = StreamDecoder()
    frames = decoder.feed(message)
    if decoder.buffer:
        raise ValueError("network message ends part-way through a DEAD frame")
    if not frames:
        raise ValueError("network message carries no complete frame")
    return frames


def assemble_transfer(fragments: list[dict], total_size: int) -> bytes:
    if total_size > 256 * 1024:
        raise ValueError("transfer exceeds 256 KiB")
    expected_offset = 0
    output = bytearray()
    for fragment in fragments:
        offset = fragment["offset"]
        body = fragment["bytes"]
        if offset != expected_offset:
            raise ValueError(f"gap/out-of-order fragment: expected {expected_offset}, got {offset}")
        if expected_offset + len(body) > total_size:
            raise ValueError("fragment exceeds declared totalSize")
        output.extend(body)
        expected_offset += len(body)
    if expected_offset != total_size:
        raise ValueError(f"incomplete transfer: {expected_offset} of {total_size}")
    return bytes(output)


def test_header_and_golden_fixtures_decode(details, vectors):
    fields = details["dead_v2"]["fields"]
    assert [(field["name"], field["offset"], field["size"]) for field in fields[:7]] == [
        ("magic", 0, 2),
        ("version", 2, 1),
        ("compression", 3, 1),
        ("encoding", 4, 1),
        ("priority", 5, 1),
        ("reserved", 6, 2),
        ("length", 8, 8),
    ]
    for vector in vectors.values():
        decoded = decode_vector(vector)
        wire = bytes.fromhex(vector["framed_hex"])
        assert int.from_bytes(wire[8:16], "big") == len(wire) - HEADER_LEN
        assert decoded["priority"] == vector["priority"]
        assert normalize_decoded(decoded["message"]) == vector["decoded_json"]


def test_msgpack_ack_reencodes_byte_for_byte(vectors):
    vector = vectors["bridge_to_gateway/ack-response"]
    payload = encode_golden_envelope(vector["decoded_json"])
    assert frame(payload).hex() == vector["framed_hex"]
    assert msgpack_decode(payload)["data"] == {"type": "ack"}


def test_stream_splits_at_every_byte_and_coalesces_frames(vectors):
    first = bytes.fromhex(vectors["bridge_to_gateway/ack-response"]["framed_hex"])
    second = bytes.fromhex(vectors["bridge_to_gateway/done-response"]["framed_hex"])
    for split in range(len(first) + 1):
        decoder = StreamDecoder()
        frames = decoder.feed(first[:split])
        frames += decoder.feed(first[split:] + second)
        frames += decoder.feed(b"")
        assert [item["message"]["data"]["type"] for item in frames] == ["ack", "done"], split
        assert not decoder.buffer

    decoder = StreamDecoder()
    types = []
    for byte in first + second:
        types.extend(item["message"]["data"]["type"] for item in decoder.feed(bytes([byte])))
    assert types == ["ack", "done"]


def test_bad_magic_version_and_oversize_length_resync(vectors):
    good = bytes.fromhex(vectors["bridge_to_gateway/ack-response"]["framed_hex"])
    for corrupt in (
        b"\x01\x02\x03\xde\x00\xff",
        b"\xde\xad\x01" + good[3:16] + b"garbage",
        MAGIC + b"\x02\x00\x00\x00\x00\x00" + ((1 << 64) - 1).to_bytes(8, "big"),
    ):
        decoder = StreamDecoder()
        frames = decoder.feed(corrupt + good)
        frames += decoder.feed(b"")
        assert len(frames) == 1
        assert frames[0]["message"]["data"] == {"type": "ack"}


def test_unknown_priority_and_reserved_bytes_follow_decoder_rules(vectors):
    wire = bytearray.fromhex(vectors["bridge_to_gateway/ack-response"]["framed_hex"])
    wire[5] = 0xFF
    wire[6:8] = b"\xaa\x55"
    decoded = StreamDecoder().feed(bytes(wire))[0]
    assert decoded["priority"] == "normal"


def test_gzip_threshold_lane_and_smaller_rules():
    at_threshold = b"Z" * GZIP_THRESHOLD
    over_threshold = b"Z" * (GZIP_THRESHOLD + 1)
    assert automatic_frame(at_threshold)[3] == 0
    assert automatic_frame(over_threshold)[3] == 1
    assert automatic_frame(over_threshold, "bulk")[3] == 0
    assert automatic_frame(over_threshold, "background")[3] == 0

    noise = random.Random(7).randbytes(GZIP_THRESHOLD + 1)
    assert automatic_frame(noise)[3] == 0

    compressed = automatic_frame(over_threshold)
    declared = int.from_bytes(compressed[8:16], "big")
    assert declared == len(compressed) - HEADER_LEN
    assert declared < len(over_threshold)
    assert gzip.decompress(compressed[HEADER_LEN:]) == over_threshold


def test_decompressed_cap_is_enforced():
    bomb = gzip.compress(b"\x00" * (FRAME_CAP + 1), mtime=0)
    assert len(bomb) < FRAME_CAP
    with pytest.raises(ValueError, match="exceeds 16 MiB"):
        StreamDecoder().feed(frame(bomb, compression=1))


def test_network_websocket_requires_whole_frames_within_1mib(vectors):
    first = bytes.fromhex(vectors["bridge_to_gateway/ack-response"]["framed_hex"])
    second = bytes.fromhex(vectors["bridge_to_gateway/done-response"]["framed_hex"])
    assert len(validate_network_message(first + second)) == 2
    with pytest.raises(ValueError, match="part-way"):
        validate_network_message(first[:-1])
    with pytest.raises(ValueError, match="1 MiB"):
        validate_network_message(b"\x00" * (NETWORK_CAP + 1))


def test_uuid_correlation_and_json_envelopes(details, vectors):
    ack = normalize_decoded(decode_vector(vectors["bridge_to_gateway/ack-response"])["message"])
    assert ack["meta"]["kind"] == "response"
    assert ack["meta"]["data"]["requestId"] == "0192f2a0-bbb0-7c00-a000-000000000099"
    assert ack["id"] != ack["meta"]["data"]["requestId"]

    request = details["envelope"]["json_example_request"]
    response = details["envelope"]["json_example_response"]
    wire = frame(json.dumps(request, separators=(",", ":")).encode(), encoding=1)
    decoded = StreamDecoder().feed(wire)[0]["message"]
    assert decoded == request
    assert response["meta"]["data"]["requestId"] == request["id"]
    assert response["id"] != request["id"]


def test_wire_error_is_typed_and_correlated(vectors):
    error = normalize_decoded(decode_vector(vectors["bridge_to_gateway/error-unsupported"])["message"])
    assert error["data"] == {"type": "error", "data": {"type": "unsupported"}}
    assert error["meta"]["data"]["requestId"] == "0192f2a0-bbb0-7c00-a000-000000000099"


def test_golden_transfer_fragments_and_gap_rejection(vectors):
    first = normalize_decoded(
        decode_vector(vectors["gateway_to_bridge/transfer-fragment-background-event"])["message"]
    )
    second = normalize_decoded(decode_vector(vectors["gateway_to_bridge/transfer-fragment-event"])["message"])
    first_data = first["data"]["data"]["data"]
    second_data = second["data"]["data"]["data"]
    assert first_data["offset"] == 0
    assert second_data["offset"] == 4096
    assert first_data["transferId"] == second_data["transferId"]
    assert first_data["bytes"] == second_data["bytes"] == [137, 80, 78, 71, 13, 10, 26, 10]

    with pytest.raises(ValueError, match="expected 8"):
        assemble_transfer([first_data, second_data], 81920)

    stream = decode_vector(vectors["gateway_to_bridge/asset-got-stream-response"])["message"]
    transfer = normalize_decoded(stream)["data"]["data"]["data"]["body"]["data"]
    assert transfer == {"id": first_data["transferId"], "totalSize": 81920}

    good = [
        {"offset": 0, "bytes": b"a" * 4096},
        {"offset": 4096, "bytes": b"b" * 4096},
    ]
    assert assemble_transfer(good, 8192) == b"a" * 4096 + b"b" * 4096
    with pytest.raises(ValueError, match="gap/out-of-order"):
        assemble_transfer(list(reversed(good)), 8192)
    with pytest.raises(ValueError, match="incomplete"):
        assemble_transfer(good[:1], 8192)
    with pytest.raises(ValueError, match="256 KiB"):
        assemble_transfer([], 256 * 1024 + 1)


def test_typed_catalogue_is_directional_and_complete(details):
    rows = details["typed_command_catalogue"]["rows"]
    keys = {(row["direction"], row["surface"], row["event"]) for row in rows}
    assert len(rows) == 122
    assert len(keys) == len(rows)
    assert {row["direction"] for row in rows} == {
        "gateway_to_bridge",
        "bridge_to_gateway",
        "client_to_bridge",
    }
    for required in (
        ("gateway_to_bridge", "chrome", "navigate"),
        ("gateway_to_bridge", "system", "otaActivate"),
        ("bridge_to_gateway", "player", "play"),
        ("bridge_to_gateway", "tunnel", "data"),
        ("client_to_bridge", "hardware", "displaySetLevel"),
        ("client_to_bridge", "system", "factoryReset"),
    ):
        if required[-1] == "factoryReset":
            assert any(
                row["direction"] == "client_to_bridge"
                and row["surface"] == "system"
                and row["event"] == "factoryReset"
                for row in details["typed_request_catalogue"]["rows"]
            )
        else:
            assert required in keys
    assert "websocket" not in yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))
    assert details["transports"]["local_webapp"]["binary_messages"] == "MessagePack."
    assert details["transports"]["stock_translation"]["url"] == "ws://{address}:8890/"
    assert details["transports"]["network_gateway"]["access_control"] == "unknown"


def test_scope_and_ios_alternative_are_explicit(spec):
    device = spec["device"]
    assert device["testing"]["status"] == "untested"
    assert spec["local_access"]["status"] == "firmware_replacement"
    assert "never stock" in spec["protocol_details"]["scope"]["firmware"]
    profile = spec["bluetooth_classic"]["profiles"][0]
    assert profile["uuid"] == "dead0000-854d-408e-81f0-fb6147f918fd"
    assert profile["channel"] == 1
    verdict = device["host_compatibility"][0]
    assert verdict["stack"] == "corebluetooth"
    assert verdict["status"] == "incompatible"
    assert verdict["cause"] == {"missing_api": "rfcomm"}
    assert spec["protocol_details"]["transports"]["iap2"]["protocol_name"] == "com.bridgething.gateway"
