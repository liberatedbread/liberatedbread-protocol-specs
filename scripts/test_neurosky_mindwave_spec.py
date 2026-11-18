"""Independent ThinkGear transcriptions for neurosky-mindwave.yaml.

Only Python's standard library implements the packet parser. PyYAML is used solely
to read the published vectors; no repository client or upstream parser is imported.
All synthetic signal values are invented and no hardware is contacted.
"""

from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = ROOT / "device-specs" / "devices" / "neurosky-mindwave.yaml"


@pytest.fixture(scope="module")
def spec():
    return yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))


def hx(value):
    return bytes.fromhex(value)


def checksum(payload):
    return (~sum(payload)) & 0xFF


def packet(payload):
    return b"\xAA\xAA" + bytes([len(payload)]) + payload + bytes([checksum(payload)])


def parse_rows(payload):
    rows = []
    pos = 0
    while pos < len(payload):
        extended = 0
        while pos < len(payload) and payload[pos] == 0x55:
            extended += 1
            pos += 1
        if pos >= len(payload):
            raise ValueError("extended code has no row code")
        code = payload[pos]
        pos += 1
        if code == 0xAA:
            raise ValueError("reserved row code")
        if code >= 0x80:
            if pos >= len(payload):
                raise ValueError("missing value length")
            length = payload[pos]
            pos += 1
        else:
            length = 1
        end = pos + length
        if end > len(payload):
            raise ValueError("truncated row")
        value = payload[pos:end]
        pos = end
        if code == 0x80 and length != 2:
            raise ValueError("raw sample width")
        if code == 0x83 and length != 24:
            raise ValueError("EEG power width")
        rows.append((extended, code, value))
    return rows


class ThinkGearParser:
    def __init__(self):
        self.buffer = bytearray()
        self.packets = []
        self.errors = []

    def feed(self, data):
        self.buffer.extend(data)
        while True:
            start = self.buffer.find(b"\xAA\xAA")
            if start < 0:
                self.buffer[:] = self.buffer[-1:] if self.buffer.endswith(b"\xAA") else b""
                return
            if start:
                del self.buffer[:start]
            if len(self.buffer) < 3:
                return
            length = self.buffer[2]
            if length > 169:
                self.errors.append("length")
                del self.buffer[0]
                continue
            total = length + 4
            if len(self.buffer) < total:
                return
            payload = bytes(self.buffer[3 : 3 + length])
            received_checksum = self.buffer[total - 1]
            if checksum(payload) != received_checksum:
                self.errors.append("checksum")
                del self.buffer[0]
                continue
            try:
                rows = parse_rows(payload)
            except ValueError:
                self.errors.append("row")
                del self.buffer[0]
                continue
            self.packets.append((payload, rows))
            del self.buffer[:total]


def values(rows):
    result = {}
    for extended, code, value in rows:
        if code == 0x80:
            result[code] = int.from_bytes(value, "big", signed=True)
        elif code == 0x83:
            result[code] = [
                int.from_bytes(value[offset : offset + 3], "big")
                for offset in range(0, 24, 3)
            ]
        else:
            result[(extended, code)] = value
    return result


def test_official_guide_vector(spec):
    vector = spec["protocol_details"]["thinkgear_stream"]["test_vectors"][0]
    parser = ThinkGearParser()
    parser.feed(hx(vector["packet_hex"]))
    assert len(parser.packets) == 1
    rows = values(parser.packets[0][1])
    assert rows[(0, 0x02)] == b"\x20"
    assert rows[(0, 0x01)] == b"\x7e"
    assert rows[(0, 0x04)] == b"\x12"
    assert rows[(0, 0x05)] == b"\x60"
    assert vector["expect"] == {
        "poor_signal": 32,
        "battery": 126,
        "attention": 18,
        "meditation": 96,
    }


def test_common_rows_unknown_extension_and_every_split(spec):
    vector = spec["protocol_details"]["thinkgear_stream"]["test_vectors"][1]
    payload = hx(vector["payload_hex"])
    wire = packet(payload)
    for split in range(len(wire) + 1):
        parser = ThinkGearParser()
        parser.feed(wire[:split])
        parser.feed(wire[split:])
        assert len(parser.packets) == 1, split
        decoded = values(parser.packets[0][1])
        assert decoded[(0, 0x04)] == b"\x2a"
        assert decoded[(0, 0x05)] == b"\x37"
        assert decoded[0x80] == -256
        assert decoded[(1, 0x90)] == b"\x01\x02\x03"
        assert decoded[0x83] == [1, 2, 3, 4, 5, 6, 7, 8]


def test_sync_loss_bad_checksum_and_byte_fragmentation():
    good = packet(b"\x04\x2a")
    bad = bytearray(packet(b"\x05\x63"))
    bad[-1] ^= 0x01
    parser = ThinkGearParser()
    for byte in b"noise" + bytes(bad) + good:
        parser.feed(bytes([byte]))
    assert parser.errors == ["checksum"]
    assert len(parser.packets) == 1
    assert values(parser.packets[0][1])[(0, 0x04)] == b"\x2a"


@pytest.mark.parametrize("length", [170, 171, 255])
def test_oversized_length_recovers(length):
    parser = ThinkGearParser()
    parser.feed(b"\xAA\xAA" + bytes([length]) + packet(b"\x04\x2a"))
    assert "length" in parser.errors
    assert len(parser.packets) == 1


def test_maximum_and_empty_payloads():
    empty = ThinkGearParser()
    empty.feed(b"\xAA\xAA\x00\xFF")
    assert empty.packets == [(b"", [])]

    payload = b"\x90\xA7" + bytes(167)
    parser = ThinkGearParser()
    parser.feed(packet(payload))
    assert len(parser.packets) == 1
    assert len(parser.packets[0][0]) == 169
    assert values(parser.packets[0][1])[(0, 0x90)] == bytes(167)


def test_malformed_rows_do_not_poison_next_packet():
    malformed = packet(b"\x80\x02\x01")
    good = packet(b"\x04\x2a")
    parser = ThinkGearParser()
    parser.feed(malformed + good)
    assert parser.errors == ["row"]
    assert len(parser.packets) == 1

    wrong_eeg_width = ThinkGearParser()
    wrong_eeg_width.feed(packet(b"\x83\x17" + bytes(23)))
    assert wrong_eeg_width.errors == ["row"]
    assert wrong_eeg_width.packets == []


def test_signed_raw_and_unsigned_24_bit_boundaries():
    payload = b"\x80\x02\x80\x00\x83\x18" + b"\xff\xff\xff" * 8
    parser = ThinkGearParser()
    parser.feed(packet(payload))
    decoded = values(parser.packets[0][1])
    assert decoded[0x80] == -32768
    assert decoded[0x83] == [16777215] * 8


def test_checksum_is_payload_complement_not_frame_sum():
    payload = b"\x02\x20\x01\x7e\x04\x12\x05\x60"
    assert checksum(payload) == 0xE3
    assert packet(payload).hex(" ") == "aa aa 08 02 20 01 7e 04 12 05 60 e3"


def test_classic_scope_and_corebluetooth_verdict(spec):
    text = SPEC_PATH.read_text(encoding="utf-8")
    assert "039aff" not in text
    assert spec["device"]["protocol"] == "bluetooth_classic"
    assert spec["bluetooth_classic"]["profiles"][0]["secure"] is True
    assert spec["bluetooth_classic"]["serial"]["framing"]["max_frame_bytes"] == 173
    verdict = next(
        item
        for item in spec["device"]["host_compatibility"]
        if item["stack"] == "corebluetooth"
    )
    assert verdict["status"] == "incompatible"
    assert verdict["cause"] == {"missing_api": "rfcomm"}
