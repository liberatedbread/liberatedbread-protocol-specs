def decode_standard_battery_level(data):
    if len(data) != 1:
        raise ValueError("Battery Level is exactly one byte")
    percent = data[0]
    if percent > 100:
        raise ValueError("Battery Level is outside 0-100")
    return percent


def test_standard_u8_battery_values_need_no_affine_conversion():
    for raw, expected in ((0, 0), (1, 1), (50, 50), (87, 87), (100, 100)):
        assert decode_standard_battery_level(bytes([raw])) == expected


def test_invalid_battery_values_are_not_remapped():
    for raw in (101, 255):
        try:
            decode_standard_battery_level(bytes([raw]))
        except ValueError:
            pass
        else:
            raise AssertionError("out-of-range Battery Level must be rejected")
    try:
        decode_standard_battery_level(bytes([50, 0]))
    except ValueError:
        pass
    else:
        raise AssertionError("Battery Level is not a custom multi-byte field")
