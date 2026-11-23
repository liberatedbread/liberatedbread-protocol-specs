"""Independent stdlib parser and vectors for the Felicita Arc 18-byte frame."""

from __future__ import annotations

POSITIVE = bytes.fromhex(
    "aa 55 2b 30 31 32 33 34 35 00 00 00 00 00 00 81 00 00"
)
NEGATIVE = bytes.fromhex(
    "aa 55 2d 30 31 32 33 34 35 00 00 00 00 00 00 9e 00 00"
)


def decode_frame(data: bytes, last_battery=None) -> dict:
    if len(data) != 18:
        raise ValueError("Arc notifications are exactly 18 bytes")
    if any(value < 0x30 or value > 0x39 for value in data[3:9]):
        raise ValueError("weight is six ASCII digits")
    magnitude = int(data[3:9].decode("ascii"))
    weight = -magnitude if data[2] == 0x2D else magnitude
    raw_battery = data[15]
    if 129 <= raw_battery <= 158:
        battery = round((raw_battery - 129) * 100 / 29)
    else:
        battery = last_battery
    return {"weight_g": weight / 100, "battery": battery, "battery_raw": raw_battery}


def test_synthetic_weight_and_battery_vectors() -> None:
    assert decode_frame(POSITIVE) == {
        "weight_g": 123.45,
        "battery": 0,
        "battery_raw": 129,
    }
    assert decode_frame(NEGATIVE) == {
        "weight_g": -123.45,
        "battery": 100,
        "battery_raw": 158,
    }


def test_battery_raw_boundaries_are_not_clamped() -> None:
    low = bytearray(POSITIVE)
    low[15] = 128
    assert decode_frame(low)["battery"] is None
    assert decode_frame(low, last_battery=42)["battery"] == 42
    high = bytearray(POSITIVE)
    high[15] = 159
    assert decode_frame(high, last_battery=42)["battery"] == 42
    for raw in range(129, 159):
        frame = bytearray(POSITIVE)
        frame[15] = raw
        assert decode_frame(frame)["battery"] == round((raw - 129) * 100 / 29)


def test_non_dash_sign_is_positive_and_non_digits_rejected() -> None:
    frame = bytearray(POSITIVE)
    frame[2] = 0x2D - 1
    assert decode_frame(frame)["weight_g"] == 123.45
    for index in range(3, 9):
        frame = bytearray(POSITIVE)
        frame[index] = ord("x")
        try:
            decode_frame(frame)
        except ValueError:
            pass
        else:
            raise AssertionError(f"non-digit at {index} accepted")


def test_every_wrong_length_is_rejected() -> None:
    for length in (0, 1, 2, 17, 19, 32):
        try:
            decode_frame(bytes(length))
        except ValueError:
            pass
        else:
            raise AssertionError(f"accepted length {length}")


def test_one_byte_commands_are_inert_encoding_only() -> None:
    commands = {
        "tare": 0x54,
        "timer_start": 0x52,
        "timer_stop": 0x53,
        "timer_reset": 0x43,
    }
    assert bytes((commands["tare"],)) == b"T"
    assert bytes((commands["timer_start"],)) == b"R"
    assert bytes((commands["timer_stop"],)) == b"S"
    assert bytes((commands["timer_reset"],)) == b"C"
