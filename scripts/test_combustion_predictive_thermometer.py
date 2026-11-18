"""Independent Combustion Probe decoder and UART checks.

Transcribes the public DRAFT Probe layouts and CRC using only the standard
library (plus pytest). All serial/session values and sensor values are
synthetic; nothing imports project code or talks to a probe.
"""

from __future__ import annotations

import pytest


TEMP_BLOCK = bytes.fromhex("20 c3 66 30 0d b1 81 37 1c 07 e9 d0 1d")
TEMPS = [20.0, 21.1, 22.2, 23.3, 24.4, 25.5, 26.6, 27.7]
STATUS_HEX = "010000002a00000020c366300db181371c07e9d01d2048638a4206e1803e0000000000000000000000000000000000008104000000000000000000000000000000000000000000000000000000000000000000000000000000000000000078563412e803"


def crc16_ccitt(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def decode_temperatures(block: bytes, *, instant_read: bool = False) -> list[float]:
    if len(block) != 13:
        raise ValueError("raw temperature block must be 13 bytes")
    packed = int.from_bytes(block, "little")
    raw = [(packed >> (13 * index)) & 0x1FFF for index in range(8)]
    if any(value > 7780 for value in raw):
        raise ValueError("thermistor is outside the documented -20..369 C range")
    if instant_read:
        return [raw[0] * 0.05 - 20]
    return [value * 0.05 - 20 for value in raw]


def packed_fields(data: bytes, layout: dict[str, tuple[int, int]]) -> dict[str, int]:
    value = int.from_bytes(data, "little")
    return {
        name: (value >> offset) & ((1 << width) - 1)
        for name, (offset, width) in layout.items()
    }


def decode_prediction(data: bytes) -> dict[str, int]:
    return packed_fields(
        data,
        {
            "state": (0, 4),
            "mode": (4, 2),
            "type": (6, 2),
            "setpoint": (8, 10),
            "heat_start": (18, 10),
            "seconds": (28, 17),
            "estimated_core": (45, 11),
        },
    )


def decode_alarm_records(data: bytes) -> list[dict]:
    if len(data) != 22:
        raise ValueError("alarm array must contain eleven uint16 records")
    result = []
    for index in range(11):
        raw = int.from_bytes(data[index * 2 : index * 2 + 2], "little")
        result.append(
            {
                "set": bool(raw & 1),
                "tripped": bool(raw & 2),
                "alarming": bool(raw & 4),
                "temperature_c": ((raw & 0xFFF8) >> 3) * 0.1 - 20,
            }
        )
    return result


def decode_status(data: bytes) -> dict:
    if len(data) not in (94, 100):
        raise ValueError("Probe Status must be 94 or 100 bytes")
    result = {
        "min_log": int.from_bytes(data[0:4], "little"),
        "max_log": int.from_bytes(data[4:8], "little"),
        "temperatures": decode_temperatures(data[8:21], instant_read=(data[21] & 3) == 1),
        "mode": data[21] & 3,
        "probe_id": ((data[21] >> 5) & 7) + 1,
        "low_battery": bool(data[22] & 1),
        "prediction": decode_prediction(data[23:30]),
        "overheating": [f"T{index + 1}" for index in range(8) if data[48] & (1 << index)],
        "high_radio_power": bool(data[49] & 4),
        "high_alarms": decode_alarm_records(data[50:72]),
        "low_alarms": decode_alarm_records(data[72:94]),
        "session": int.from_bytes(data[94:98], "little") if len(data) == 100 else None,
        "sample_period_ms": int.from_bytes(data[98:100], "little") if len(data) == 100 else None,
    }
    return result


def encode_request(message_type: int, payload: bytes = b"") -> bytes:
    body = bytes([message_type, len(payload)]) + payload
    return b"\xca\xfe" + crc16_ccitt(body).to_bytes(2, "little") + body


def encode_response(message_type: int, success: int, payload: bytes = b"") -> bytes:
    body = bytes([message_type, success, len(payload)]) + payload
    return b"\xca\xfe" + crc16_ccitt(body).to_bytes(2, "little") + body


def parse_uart(chunks) -> list[dict]:
    """Split/coalesce Probe responses and resynchronize malformed candidates."""
    buffer = bytearray()
    messages = []
    for chunk in chunks:
        buffer.extend(chunk)
        while buffer:
            start = buffer.find(b"\xca\xfe")
            if start < 0:
                buffer[:] = b"\xca" if buffer[-1:] == b"\xca" else b""
                break
            if start:
                del buffer[:start]
            if len(buffer) < 7:
                break
            total = 7 + buffer[6]
            if len(buffer) < total:
                break
            candidate = bytes(buffer[:total])
            if crc16_ccitt(candidate[4:]) != int.from_bytes(candidate[2:4], "little"):
                del buffer[0]
                continue
            messages.append(
                {
                    "type": candidate[4],
                    "success": candidate[5],
                    "payload": candidate[7:],
                }
            )
            del buffer[:total]
    return messages


def test_crc_public_check_value_and_request_vectors():
    assert crc16_ccitt(b"123456789") == 0x29B1
    assert encode_request(3) == bytes.fromhex("ca fe 5c 48 03 00")
    assert encode_request(4, bytes.fromhex("01 00 00 00 05 00 00 00")) == bytes.fromhex(
        "ca fe 65 9e 04 08 01 00 00 00 05 00 00 00"
    )
    assert encode_request(5, bytes.fromhex("b7 0a")) == bytes.fromhex("ca fe 35 70 05 02 b7 0a")
    assert encode_request(12) == bytes.fromhex("ca fe 62 58 0c 00")
    assert encode_request(10) == bytes.fromhex("ca fe c4 f2 0a 00")
    assert encode_request(11, bytes(44))[:6] == bytes.fromhex("ca fe d2 60 0b 2c")


def test_packed_temperature_vector_and_instant_read():
    assert decode_temperatures(TEMP_BLOCK) == pytest.approx(TEMPS)
    raw = [800, 0, 0, 0, 0, 0, 0, 0]
    packed = sum(value << (13 * index) for index, value in enumerate(raw)).to_bytes(13, "little")
    assert decode_temperatures(packed, instant_read=True) == [20.0]
    with pytest.raises(ValueError):
        decode_temperatures(TEMP_BLOCK[:-1])
    too_large = (7781).to_bytes(13, "little")
    with pytest.raises(ValueError):
        decode_temperatures(too_large)


def test_new_and_old_status_layouts():
    data = bytes.fromhex(STATUS_HEX)
    assert len(data) == 100
    parsed = decode_status(data)
    assert parsed["min_log"] == 1
    assert parsed["max_log"] == 42
    assert parsed["temperatures"] == pytest.approx(TEMPS)
    assert parsed["probe_id"] == 2
    assert parsed["overheating"] == ["T1", "T8"]
    assert parsed["high_radio_power"] is True
    assert parsed["session"] == 0x12345678
    assert parsed["sample_period_ms"] == 1000
    prediction = parsed["prediction"]
    assert prediction["state"] == 3
    assert prediction["mode"] == 2
    assert prediction["type"] == 1
    assert prediction["setpoint"] == 650
    assert prediction["heat_start"] == 400
    assert prediction["seconds"] == 3600
    assert prediction["estimated_core"] == 500
    assert prediction["estimated_core"] * 0.1 - 20 == 30.0

    legacy = decode_status(data[:94])
    assert len(data[:94]) == 94
    assert legacy["session"] is None
    assert legacy["sample_period_ms"] is None
    assert legacy["temperatures"] == pytest.approx(TEMPS)
    # A supplied zero session is ordinary, not exceptional.
    zero_session = bytearray(data)
    zero_session[94:98] = bytes(4)
    assert decode_status(bytes(zero_session))["session"] == 0


def test_alarm_bitfields_and_scaling():
    raw = 1 | 2 | 4 | (650 << 3)
    record = decode_alarm_records(raw.to_bytes(2, "little") + bytes(20))[0]
    assert record == {"set": True, "tripped": True, "alarming": True, "temperature_c": 45.0}


def test_response_crc_includes_success_and_stream_reassembly():
    response = bytes.fromhex("ca fe ca 21 03 01 06 78 56 34 12 e8 03")
    assert encode_response(3, 1, bytes.fromhex("78 56 34 12 e8 03")) == response
    other = encode_response(6, 1, b"\x01")
    coalesced = response + other
    messages = parse_uart([coalesced])
    assert len(messages) == 2
    assert messages[0] == {"type": 3, "success": 1, "payload": bytes.fromhex("78 56 34 12 e8 03")}
    assert messages[1]["type"] == 6
    assert parse_uart([bytes([value]) for value in coalesced]) == messages
    assert parse_uart([coalesced[:2], coalesced[2:9], coalesced[9:]]) == messages


def test_malformed_uart_data_never_becomes_a_valid_message():
    valid = encode_response(3, 1, bytes.fromhex("78 56 34 12 e8 03"))
    bad_crc = bytearray(valid)
    bad_crc[2] ^= 1
    # Bad prefix and bad CRC are skipped; the following valid frame survives.
    stream = b"noise" + bytes(bad_crc) + valid
    assert parse_uart([stream]) == [
        {"type": 3, "success": 1, "payload": bytes.fromhex("78 56 34 12 e8 03")}
    ]
    assert parse_uart([valid[:-1]]) == []
    failure = encode_response(5, 0)
    assert parse_uart([failure]) == [{"type": 5, "success": 0, "payload": b""}]
