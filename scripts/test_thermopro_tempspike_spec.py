import math
import struct


def fahrenheit_plus_54_to_celsius(raw):
    return (raw - 54 - 32) * 5 / 9


def available_temperature(raw):
    value = fahrenheit_plus_54_to_celsius(raw)
    return None if value <= -30 else value


def decode_tp980(frame):
    opcode = frame[0]
    if opcode == 0x11:
        assert len(frame) >= 17
        scalar_offset, float_offsets = 1, (5, 9, 13)
    elif opcode == 0x20:
        assert len(frame) >= 18
        scalar_offset, float_offsets = 2, (6, 10, 14)
    else:
        raise ValueError("unknown TP980 opcode")
    scalar_raw = struct.unpack_from("<H", frame, scalar_offset)[0]
    scalar = None if scalar_raw == 0xFFFF else available_temperature(scalar_raw)
    floats = [
        available_temperature(struct.unpack_from("<f", frame, offset)[0])
        for offset in float_offsets
    ]
    return scalar, floats


def decode_tp97x_ambient(raw):
    return int(round(fahrenheit_plus_54_to_celsius(raw), 1))


def probe_battery_percent(millivolts):
    if millivolts < 2311:
        return 0
    if millivolts <= 2450:
        return 33
    if millivolts <= 2600:
        return 66
    return 100


def decode_tp980_metadata(frame):
    opcode = frame[0]
    if opcode == 0x11:
        battery_mv = struct.unpack_from("<H", frame, 3)[0]
        return None, battery_mv, probe_battery_percent(battery_mv)
    if opcode == 0x20:
        battery_mv = struct.unpack_from("<H", frame, 4)[0]
        return frame[1], battery_mv, probe_battery_percent(battery_mv)
    raise ValueError("unknown TP980 opcode")


def passive_battery_percent(millivolts):
    percent = 52.317286 * math.tanh(
        millivolts / 273.624277936 - 8.76485439394
    ) + 51.06925
    return max(0, min(100, percent))


def make_tp980(opcode, scalar, temperatures):
    frame = bytearray(18 if opcode == 0x20 else 17)
    frame[0] = opcode
    scalar_offset, float_offsets = (2, (6, 10, 14)) if opcode == 0x20 else (1, (5, 9, 13))
    struct.pack_into("<H", frame, scalar_offset, scalar)
    if opcode == 0x20:
        frame[1] = 3
        struct.pack_into("<H", frame, 4, 2500)
    else:
        struct.pack_into("<H", frame, 3, 2500)
    for offset, value in zip(float_offsets, temperatures, strict=True):
        struct.pack_into("<f", frame, offset, value)
    return bytes(frame)


def test_tp980_scalar_and_float_offsets_per_opcode():
    for opcode in (0x11, 0x20):
        scalar, floats = decode_tp980(make_tp980(opcode, 140, (122.0, 131.0, 140.0)))
        assert math.isclose(scalar, 30.0)
        expected = [20.0, 25.0, 30.0]
        for actual, wanted in zip(floats, expected, strict=True):
            assert math.isclose(actual, wanted, abs_tol=1e-5)
    scalar, _ = decode_tp980(make_tp980(0x11, 0xFFFF, (140.0, 140.0, 140.0)))
    assert scalar is None
    _, floats = decode_tp980(make_tp980(0x20, 140, (20.0, 140.0, 140.0)))
    assert floats[0] is None


def test_tp980_probe_index_and_battery_offsets():
    poll = make_tp980(0x11, 140, (140.0, 140.0, 140.0))
    automatic = make_tp980(0x20, 140, (140.0, 140.0, 140.0))
    assert struct.unpack_from("<H", poll, 3)[0] == 2500
    assert automatic[1] == 3
    assert struct.unpack_from("<H", automatic, 4)[0] == 2500
    assert decode_tp980_metadata(poll) == (None, 2500, 66)
    assert decode_tp980_metadata(automatic) == (3, 2500, 66)


def test_tp96x_seven_and_thirteen_byte_layouts():
    payload = struct.pack("<BHHH", 2, 55, 2800, 50)
    assert len(payload) == 7
    index, internal, millivolts, ambient = struct.unpack("<BHHH", payload)
    assert (index, internal - 30, ambient - 30, millivolts) == (2, 25, 20, 2800)
    extended = payload + bytes([1, 2, 3, 4, 5, 6])
    assert len(extended) == 13
    assert struct.unpack("<BHHH", extended[:7]) == (index, internal, millivolts, ambient)


def test_tp97x_integer_ambient_and_float_internal_layout():
    payload = struct.pack(
        "<BHHfffHHH", 1, 141, 2750, 122.0, 131.0, 140.0, 0, 0, 0
    )
    assert len(payload) == 23
    decoded = struct.unpack("<BHHfffHHH", payload)
    assert decoded[0] == 1
    assert decode_tp97x_ambient(decoded[1]) == 30
    assert decoded[2] == 2750
    for value, wanted in zip(decoded[3:6], (20.0, 25.0, 30.0), strict=True):
        assert math.isclose(fahrenheit_plus_54_to_celsius(value), wanted, abs_tol=1e-5)
    assert decoded[6:] == (0, 0, 0)


def test_tp97x_reference_round_once_then_truncate_including_negative():
    assert decode_tp97x_ambient(141) == 30
    assert decode_tp97x_ambient(31) == -30
    assert round(fahrenheit_plus_54_to_celsius(141)) == 31
    assert round(fahrenheit_plus_54_to_celsius(31)) == -31


def test_battery_paths_stay_separate():
    assert passive_battery_percent(0) == 0
    assert passive_battery_percent(65535) == 100
    assert passive_battery_percent(2501) > passive_battery_percent(2500)
    for raw, expected in ((0, 0), (1, 33), (2, 66), (3, 99), (4, 100), (255, 100)):
        assert min(100, raw * 33) == expected
    for low_battery, expected in ((0, 100), (1, 0), (255, 0)):
        assert (0 if low_battery > 0 else 100) == expected
    for millivolts, expected in ((2300, 0), (2311, 33), (2451, 66), (2601, 100)):
        assert probe_battery_percent(millivolts) == expected
