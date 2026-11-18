"""Independent InfiniTime 1.16 transcriptions using the standard library.

CTS/ANS roles, Simple Weather, BLE FS and legacy DFU are rebuilt from the spec,
not imported from InfiniTime or another client. All weather/file values are
invented; no watch, firmware image or health recording is accessed.
"""

from pathlib import Path
import struct

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = ROOT / "device-specs" / "devices" / "pinetime-infinitime.yaml"


@pytest.fixture(scope="module")
def spec():
    return yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))


def hx(value):
    return bytes.fromhex(value)


def build_cts(year, month, day, hour, minute, second, weekday=0, fraction=0, reason=1):
    return struct.pack(
        "<HBBBBBBBB",
        year,
        month,
        day,
        hour,
        minute,
        second,
        weekday,
        fraction,
        reason,
    )


def build_ans(category, count, *fields):
    return bytes([category, count, 0]) + b"\x00".join(
        field.encode("utf-8") for field in fields
    )


def test_cts_vector_and_companion_roles(spec):
    vector = spec["protocol_details"]["cts"]["test_vector"]
    assert build_cts(2026, 11, 17, 12, 34, 56, weekday=3) == hx(vector["value_hex"])
    roles = spec["protocol_details"]["ble_roles"]
    assert "Companion is GATT server" in roles["companion_cts"]["direction"]
    assert "PineTime is GATT client" in roles["companion_cts"]["direction"]
    assert "reads the 10-byte" in roles["companion_cts"]["operation"]
    assert "Companion is GATT server" in roles["companion_ans"]["direction"]
    assert "subscribes" in roles["companion_ans"]["operation"]
    assert "PineTime is GATT server" in roles["watch_cts"]["direction"]
    assert "PineTime is GATT server" in roles["watch_ans"]["direction"]
    watch_services = {service["uuid"] for service in spec["services"]}
    assert roles["companion_cts"]["service"] in watch_services
    assert roles["companion_ans"]["service"] in watch_services
    assert roles["companion_cts"]["service"] != roles["watch_ans"]["service"]


def test_ans_examples_and_call_event(spec):
    examples = spec["protocol_details"]["ans"]["examples"]
    assert build_ans(0, 1, "Test Title", "Test Body") == hx(examples["simple"]["hex"])
    assert build_ans(3, 1, "Alex") == hx(examples["call"]["hex"])
    call = next(
        characteristic
        for service in spec["services"]
        for characteristic in service.get("characteristics", [])
        if characteristic["uuid"] == "00020001-78fc-48fe-8e23-433b3a1942d0"
    )
    assert call["properties"] == ["notify"]
    assert call["format"][0]["values"] == {0: "decline", 1: "accept", 2: "mute"}


def build_current_weather(version, timestamp, current, minimum, maximum, location, icon, sunrise=-1, sunset=-1):
    encoded_location = location.encode("utf-8")[:32]
    if version == 0:
        return struct.pack(
            "<BBQhhh32sB",
            0,
            0,
            timestamp,
            current,
            minimum,
            maximum,
            encoded_location,
            icon,
        )
    if version == 1:
        return struct.pack(
            "<BBQhhh32sBhh",
            0,
            1,
            timestamp,
            current,
            minimum,
            maximum,
            encoded_location,
            icon,
            sunrise,
            sunset,
        )
    raise ValueError("current-weather version")


def parse_current_weather(frame):
    if len(frame) < 2 or frame[0] != 0 or frame[1] not in (0, 1):
        raise ValueError("type/version")
    version = frame[1]
    expected = 49 if version == 0 else 53
    if len(frame) != expected:
        raise ValueError("length")
    values = {
        "timestamp": struct.unpack_from("<Q", frame, 2)[0],
        "current": struct.unpack_from("<h", frame, 10)[0] / 100,
        "minimum": struct.unpack_from("<h", frame, 12)[0] / 100,
        "maximum": struct.unpack_from("<h", frame, 14)[0] / 100,
        "location": frame[16:48].split(b"\x00", 1)[0].decode(),
        "icon": frame[48],
    }
    if version == 1:
        values["sun"] = validate_sun(
            struct.unpack_from("<h", frame, 49)[0],
            struct.unpack_from("<h", frame, 51)[0],
        )
    return values


def validate_sun(sunrise, sunset):
    if sunrise == -1 or sunset == -1:
        return (-1, -1)
    if not (-2 <= sunrise <= 1439 and -2 <= sunset <= 1439):
        return (-1, -1)
    if sunrise == -2 and sunset != -2:
        return (-1, -1)
    if sunrise >= 0 and sunset >= 0 and sunrise >= sunset:
        return (-1, -1)
    return (sunrise, sunset)


def build_forecast(timestamp, days):
    if len(days) > 5:
        raise ValueError("too many days")
    frame = bytearray(struct.pack("<BBQB", 1, 0, timestamp, len(days)))
    for minimum, maximum, icon in days:
        frame += struct.pack("<hhB", minimum, maximum, icon)
    frame += bytes(25 - 5 * len(days))
    assert len(frame) == 36
    return bytes(frame)


def parse_forecast(frame):
    if len(frame) != 36 or frame[:2] != b"\x01\x00":
        raise ValueError("forecast type/version/length")
    count = frame[10]
    if count > 5:
        raise ValueError("day count")
    days = [struct.unpack_from("<hhB", frame, 11 + 5 * index) for index in range(count)]
    return struct.unpack_from("<Q", frame, 2)[0], days, frame[11 + 5 * count :]


def test_current_weather_v1_signed_temperature_and_length(spec):
    vector = spec["protocol_details"]["simple_weather"]["test_vectors"]["current_v1"]["fields"]
    frame = build_current_weather(
        1,
        vector["timestamp"],
        vector["temperature_raw"],
        vector["minimum_raw"],
        vector["maximum_raw"],
        vector["location"],
        vector["icon"],
        vector["sunrise"],
        vector["sunset"],
    )
    assert len(frame) == 53
    decoded = parse_current_weather(frame)
    assert decoded["current"] == -3.5
    assert decoded["minimum"] == -7.0
    assert decoded["maximum"] == 2.0
    assert decoded["location"] == "Oslo"
    assert decoded["icon"] == 7
    assert decoded["sun"] == (480, 960)
    assert frame[16:48] == b"Oslo" + bytes(28)


def test_current_v0_and_forecast_zero_fill(spec):
    vector = spec["protocol_details"]["simple_weather"]["test_vectors"]["current_v1"]["fields"]
    current = build_current_weather(
        0,
        0,
        vector["temperature_raw"],
        vector["minimum_raw"],
        vector["maximum_raw"],
        vector["location"],
        vector["icon"],
    )
    assert len(current) == 49
    assert "sun" not in parse_current_weather(current)

    forecast_vector = spec["protocol_details"]["simple_weather"]["test_vectors"]["forecast_v0"]["fields"]
    forecast = build_forecast(
        forecast_vector["timestamp"],
        [(
            forecast_vector["day0_min_raw"],
            forecast_vector["day0_max_raw"],
            forecast_vector["day0_icon"],
        )],
    )
    timestamp, days, unused = parse_forecast(forecast)
    assert timestamp == 0
    assert days == [(-700, 200, 7)]
    assert unused == bytes(20)


@pytest.mark.parametrize(
    "frame",
    [
        b"\x02\x00" + bytes(49),
        b"\x00\x02" + bytes(51),
        b"\x00\x01" + bytes(50),
        b"\x01\x01" + bytes(34),
        b"\x01\x00" + bytes(8) + b"\x06" + bytes(25),
    ],
)
def test_weather_rejects_unknown_versions_and_short_lengths(frame):
    if frame[0] == 1:
        with pytest.raises(ValueError):
            parse_forecast(frame)
    else:
        with pytest.raises(ValueError):
            parse_current_weather(frame)


def test_sun_validation_sentinels():
    assert validate_sun(-1, 900) == (-1, -1)
    assert validate_sun(-2, -2) == (-2, -2)
    assert validate_sun(-2, 900) == (-1, -1)
    assert validate_sun(600, 500) == (-1, -1)
    assert validate_sun(1440, 1500) == (-1, -1)


def test_weather_is_host_write_and_legacy_service_absent(spec):
    services = {service["uuid"]: service for service in spec["services"]}
    weather = services["00050000-78fc-48fe-8e23-433b3a1942d0"]
    assert weather["characteristics"][0]["properties"] == ["write"]
    assert "00040000-78fc-48fe-8e23-433b3a1942d0" not in services
    assert "00050001-78fc-48fe-8e23-433b3a1942d0" in weather["characteristics"][0]["uuid"]


def build_read_request(path, offset, chunk_size):
    encoded = path.encode("utf-8")
    return struct.pack("<BBHII", 0x10, 0, len(encoded), offset, chunk_size) + encoded


def build_read_continue(offset, chunk_size):
    return struct.pack("<BB2xII", 0x12, 1, offset, chunk_size)


def parse_read_response(frame):
    if len(frame) < 16 or frame[0] != 0x11:
        raise ValueError("read response")
    command, status, offset, total, chunk = struct.unpack_from("<Bb2xIII", frame, 0)
    data = frame[16:]
    if len(data) != chunk:
        raise ValueError("chunk length")
    return status, offset, total, data


def parse_list_response(frame):
    if len(frame) < 28 or frame[0] != 0x51:
        raise ValueError("list response")
    command, status, path_length, entry, total, flags, modified, size = struct.unpack_from(
        "<BbHIIIQI", frame, 0
    )
    path = frame[28:]
    if len(path) != path_length:
        raise ValueError("path length")
    return status, entry, total, flags, modified, size, path


def valid_path(path):
    encoded = path.encode("utf-8")
    if not path.startswith("/") or b"\x00" in encoded or len(encoded) > 255:
        raise ValueError("path")
    return encoded


def test_ble_fs_read_request_response_and_continuation(spec):
    vectors = spec["protocol_details"]["ble_fs"]["test_vectors"]
    assert build_read_request("/boot.txt", 0, 4) == hx(vectors["read_request"]["expected_hex"])
    status, offset, total, first = parse_read_response(hx(vectors["read_response"]["hex"]))
    assert (status, offset, total, first) == (1, 0, 9, b"boot")
    continuation = build_read_continue(4, 5)
    assert continuation == hx("12 01 00 00 04 00 00 00 05 00 00 00")
    second_response = bytearray(16)
    second_response[0:4] = hx("11 01 00 00")
    struct.pack_into("<III", second_response, 4, 4, 9, 5)
    status, offset, total, second = parse_read_response(bytes(second_response) + b"image")
    assert (status, offset, total, second) == (1, 4, 9, b"image")
    assert first + second == b"bootimage"
    with pytest.raises(ValueError, match="chunk length"):
        parse_read_response(hx(vectors["read_response"]["hex"])[:-1])


def test_ble_fs_list_and_signed_status(spec):
    vectors = spec["protocol_details"]["ble_fs"]["test_vectors"]
    list_request = struct.pack("<BBH", 0x50, 0, 1) + b"/"
    assert list_request == hx(vectors["list_request"]["expected_hex"])
    status, entry, total, flags, modified, size, path = parse_list_response(
        hx(vectors["list_final_response"]["hex"])
    )
    assert (status, entry, total, flags, modified, size, path) == (1, 2, 2, 0, 0, 0, b"")
    assert entry == total

    error = bytearray(16)
    error[0:4] = hx("11 fe 00 00")
    status, _, _, data = parse_read_response(bytes(error))
    assert status == -2
    assert data == b""


def test_ble_fs_path_rules_and_move_roles(spec):
    assert valid_path("/") == b"/"
    assert valid_path("/apps/demo.js") == b"/apps/demo.js"
    for path in ("relative", "/bad\x00path", "/" + "x" * 256):
        with pytest.raises(ValueError):
            valid_path(path)
    fs = spec["protocol_details"]["ble_fs"]["commands"]
    assert fs["read_begin"]["response_header_length"] == 16
    assert fs["list_directory"]["response_header_length"] == 28
    for operation in ("write_begin", "write_continue", "delete", "mkdir", "move"):
        assert fs[operation]["advanced"] is True
        assert fs[operation]["optional"] is True
        assert fs[operation]["advanced_reason"]


def test_motion_scaling_and_heart_rate_flag_boundary(spec):
    steps = struct.pack("<I", 123456)
    assert struct.unpack("<I", steps)[0] == 123456
    x, y, z = struct.unpack("<hhh", struct.pack("<hhh", 1024, -512, 0))
    assert (x / 1024, y / 1024, z / 1024) == (1.0, -0.5, 0.0)
    heart = next(
        characteristic
        for service in spec["services"]
        for characteristic in service.get("characteristics", [])
        if characteristic["uuid"] == "00002a37-0000-1000-8000-00805f9b34fb"
    )
    assert heart["format_match"] == {
        "offset": 0,
        "value": 0,
        "notes": "Current firmware emits flags 0 and one uint8 BPM. Any other flags require the full SIG parser.",
    }
    assert heart["format"][1]["type"] == "uint8"


def crc16_ccitt(data):
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def test_dfu_sizes_segments_receipts_and_advanced_gates(spec):
    assert crc16_ccitt(b"123456789") == 0x29B1
    image_size = bytes(8) + struct.pack("<I", 1024)
    assert len(image_size) == 12
    segments = [bytes(range(20))] * 51 + [bytes(range(4))]
    assert sum(map(len, segments)) == 1024
    sent = 0
    for index, segment in enumerate(segments, 1):
        sent += len(segment)
        if index % 10 == 0 and sent != 1024:
            receipt = b"\x11" + struct.pack("<I", sent)
            assert struct.unpack_from("<I", receipt, 1)[0] == sent
    service = next(service for service in spec["services"] if service["uuid"] == "00001530-1212-efde-1523-785feabcd123")
    control = service["characteristics"][0]
    for command in control["commands"].values():
        assert command["advanced"] is True
        assert "optional" not in command
        assert "optional" in command["description"].lower()
        assert command["advanced_reason"]
    packet = service["characteristics"][1]
    assert packet["framing"]["max_chunk_size"] == 20
    assert spec["features"][0]["dfu"]["mechanisms"] == ["nordic_legacy_dfu"]


def test_firmware_scope_and_requested_surfaces(spec):
    assert spec["protocol_details"]["firmware_scope"]["supported"] == ["1.16.0"]
    services = {service["uuid"] for service in spec["services"]}
    assert {
        "0000180f-0000-1000-8000-00805f9b34fb",
        "0000180d-0000-1000-8000-00805f9b34fb",
        "00001530-1212-efde-1523-785feabcd123",
        "00000000-78fc-48fe-8e23-433b3a1942d0",
        "00010000-78fc-48fe-8e23-433b3a1942d0",
        "00030000-78fc-48fe-8e23-433b3a1942d0",
        "00050000-78fc-48fe-8e23-433b3a1942d0",
        "0000febb-0000-1000-8000-00805f9b34fb",
    } <= services
    assert spec["device"]["testing"]["status"] == "untested"
