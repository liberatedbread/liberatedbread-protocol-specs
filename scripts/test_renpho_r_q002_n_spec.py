"""Stdlib-only R-Q002 FTMS/CSC vectors and malformed-input checks."""

from __future__ import annotations

import struct

PUBLIC = bytes.fromhex("64 00 68 01 6a 00 83 00 49 00")
FULL = bytes.fromhex(
    "fe 1f d2 04 58 02 6e 00 64 00 40 0d 03 83 00 fe ff 49 00 "
    "c8 00 f4 01 05 53 35 20 00 0a 00"
)


def parse_indoor_bike(data: bytes) -> dict:
    if len(data) < 2:
        raise ValueError("missing flags")
    flags = int.from_bytes(data[:2], "little")
    if flags & 0xE000:
        raise ValueError("reserved flag bits")
    offset = 2
    result = {}

    def take(name: str, size: int, fmt: str, scale=1):
        nonlocal offset
        if offset + size > len(data):
            raise ValueError(f"truncated {name}")
        value = struct.unpack_from(fmt, data, offset)[0] * scale
        result[name] = value
        offset += size

    if not flags & 0x0001:
        take("speed", 2, "<H", 0.01)
    if flags & 0x0002:
        take("average_speed", 2, "<H", 0.01)
    if flags & 0x0004:
        take("cadence", 2, "<H", 0.5)
    if flags & 0x0008:
        take("average_cadence", 2, "<H", 0.5)
    if flags & 0x0010:
        if offset + 3 > len(data):
            raise ValueError("truncated distance")
        result["distance_m"] = int.from_bytes(data[offset : offset + 3], "little")
        offset += 3
    if flags & 0x0020:
        if offset + 2 > len(data):
            raise ValueError("truncated resistance")
        raw = int.from_bytes(data[offset : offset + 2], "little")
        result["resistance_raw"] = raw
        result["resistance"] = raw / 2
        offset += 2
    if flags & 0x0040:
        take("instantaneous_power", 2, "<h")
    if flags & 0x0080:
        take("average_power", 2, "<h")
    if flags & 0x0100:
        if offset + 5 > len(data):
            raise ValueError("truncated five-byte energy group")
        result["energy_kcal"] = int.from_bytes(data[offset : offset + 2], "little")
        result["energy_per_hour"] = int.from_bytes(data[offset + 2 : offset + 4], "little")
        result["energy_per_minute"] = data[offset + 4]
        offset += 5
    if flags & 0x0200:
        take("heart_rate", 1, "<B")
    if flags & 0x0400:
        take("metabolic_equivalent", 1, "<B", 0.1)
    if flags & 0x0800:
        take("elapsed_s", 2, "<H")
    if flags & 0x1000:
        take("remaining_s", 2, "<H")
    if offset != len(data):
        raise ValueError("unhandled trailing bytes")
    return result


def parse_csc(data: bytes) -> dict:
    if len(data) < 2:
        raise ValueError("missing CSC flags")
    flags = int.from_bytes(data[:2], "little")
    if flags & ~0x0003:
        raise ValueError("unsupported CSC flags")
    offset = 2
    result = {}
    if flags & 1:
        if offset + 6 > len(data):
            raise ValueError("truncated wheel group")
        result["wheel_revolutions"] = int.from_bytes(data[offset : offset + 4], "little")
        result["wheel_event_time"] = int.from_bytes(data[offset + 4 : offset + 6], "little") / 1024
        offset += 6
    if flags & 2:
        if offset + 4 > len(data):
            raise ValueError("truncated crank group")
        result["crank_revolutions"] = int.from_bytes(data[offset : offset + 2], "little")
        result["crank_event_time"] = int.from_bytes(data[offset + 2 : offset + 4], "little") / 1024
        offset += 4
    if offset != len(data):
        raise ValueError("trailing CSC bytes")
    return result


def test_public_capture_sample() -> None:
    parsed = parse_indoor_bike(PUBLIC)
    assert parsed["speed"] == 3.60
    assert parsed["cadence"] == 53.0
    assert parsed["resistance_raw"] == 131
    assert parsed["resistance"] == 65.5
    assert parsed["instantaneous_power"] == 73
    assert "distance_m" not in parsed


def test_full_optional_layout_signed_power_and_energy_group() -> None:
    parsed = parse_indoor_bike(FULL)
    assert parsed["speed"] == 12.34
    assert parsed["average_speed"] == 6.0
    assert parsed["cadence"] == 55.0
    assert parsed["average_cadence"] == 50.0
    assert parsed["distance_m"] == 200000
    assert parsed["resistance"] == 65.5
    assert parsed["instantaneous_power"] == -2
    assert parsed["average_power"] == 73
    assert parsed["energy_kcal"] == 200
    assert parsed["energy_per_hour"] == 500
    assert parsed["energy_per_minute"] == 5
    assert parsed["heart_rate"] == 83
    assert round(parsed["metabolic_equivalent"], 6) == 5.3
    assert parsed["elapsed_s"] == 32
    assert parsed["remaining_s"] == 10


def test_truncation_at_every_field_is_rejected() -> None:
    for length in range(len(FULL)):
        try:
            parse_indoor_bike(FULL[:length])
        except ValueError:
            pass
        else:
            raise AssertionError(f"truncated payload accepted at {length}")


def test_unknown_flags_and_trailing_bytes_are_rejected() -> None:
    for payload in (PUBLIC + b"\x00", b"\x00\x20\x00\x00", PUBLIC[:2] + PUBLIC[3:-1]):
        try:
            parse_indoor_bike(payload)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid payload accepted")


def test_csc_wheel_crank_groups_and_truncation() -> None:
    payload = struct.pack("<HIHHH", 3, 0x12345678, 1024, 512, 2048)
    parsed = parse_csc(payload)
    assert parsed == {
        "wheel_revolutions": 0x12345678,
        "wheel_event_time": 1.0,
        "crank_revolutions": 512,
        "crank_event_time": 2.0,
    }
    for malformed in (payload[:-1], payload + b"\x00", b"\x04\x00\x00\x00"):
        try:
            parse_csc(malformed)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid CSC payload accepted")


def test_cycling_power_is_signed_little_endian_at_offset_two() -> None:
    payload = b"\x30\x00\xfe\xff" + bytes(11)
    assert struct.unpack_from("<h", payload, 2)[0] == -2
    assert len(payload) == 15  # Capture shape; the unexplained trailing byte is not decoded.
