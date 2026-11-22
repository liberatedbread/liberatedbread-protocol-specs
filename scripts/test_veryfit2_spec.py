import datetime
import struct


def decode_real_time(frame):
    assert len(frame) == 20 and frame[:2] == bytes([0x02, 0xA0])
    return {
        "steps": struct.unpack_from("<I", frame, 2)[0],
        "calorie_counter": struct.unpack_from("<I", frame, 6)[0],
        "distance_m": struct.unpack_from("<I", frame, 10)[0],
        "active_time_counter": struct.unpack_from("<I", frame, 14)[0],
        "heart_rate": frame[18],
        "padding": frame[19],
    }


def decode_battery(frame):
    assert len(frame) == 20 and frame[:2] == bytes([0x02, 0x05])
    return {
        "battery_type": frame[2],
        "voltage_raw": struct.unpack_from("<H", frame, 3)[0],
        "status": frame[5],
        "battery_percent": frame[6],
        "current_use_raw": struct.unpack_from("<I", frame, 7)[0],
        "total_use_raw": struct.unpack_from("<I", frame, 11)[0],
    }


def encode_set_time(when):
    payload = struct.pack(
        "<HBBBBBB",
        when.year,
        when.month,
        when.day,
        when.hour,
        when.minute,
        when.second,
        when.weekday(),
    )
    return bytes([0x03, 0x01]) + payload + bytes(20 - 2 - len(payload))


def test_public_real_time_vector():
    frame = bytes.fromhex(
        "02 a0 23 00 00 00 01 00 00 00 19 00 00 00 92 00 00 00 00 00"
    )
    assert decode_real_time(frame) == {
        "steps": 35,
        "calorie_counter": 1,
        "distance_m": 25,
        "active_time_counter": 146,
        "heart_rate": 0,
        "padding": 0,
    }


def test_invented_battery_layout_keeps_unproven_fields_raw():
    frame = bytearray(20)
    frame[:2] = bytes([0x02, 0x05])
    frame[2] = 1
    struct.pack_into("<H", frame, 3, 0x1234)
    frame[5] = 2
    frame[6] = 87
    struct.pack_into("<I", frame, 7, 100)
    struct.pack_into("<I", frame, 11, 5000)
    assert decode_battery(frame) == {
        "battery_type": 1,
        "voltage_raw": 0x1234,
        "status": 2,
        "battery_percent": 87,
        "current_use_raw": 100,
        "total_use_raw": 5000,
    }


def test_set_time_layout_and_monday_based_weekday():
    when = datetime.datetime(2026, 11, 17, 12, 34, 56)
    assert when.weekday() == 1
    encoded = encode_set_time(when)
    assert len(encoded) == 20
    assert encoded[:10] == bytes.fromhex("03 01 ea 07 0b 11 0c 22 38 01")
    assert encoded[10:] == bytes(10)
    sunday = encode_set_time(datetime.datetime(2026, 11, 15, 1, 2, 3))
    assert sunday[9] == 6
