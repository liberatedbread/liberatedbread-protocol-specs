"""Independent stdlib parser for exact ThermoWorks BlueDOT notifications."""

from __future__ import annotations

import struct

CELSIUS = bytes.fromhex(
    "00 f6 ff ff ff 64 00 00 00 01 00 00 a5 01 53 00 5e 00 00 01"
)
FAHRENHEIT = bytes.fromhex(
    "00 48 00 00 00 96 00 00 00 00 00 01 00 01 53 00 5e 00 00 00"
)


def to_celsius(value: int, unit: int) -> float:
    if unit == 0:
        return float(value)
    if unit == 1:
        return round((value - 32) * 5 / 9, 1)
    raise ValueError("unknown temperature unit")


def parse_notification(data: bytes) -> dict:
    if len(data) != 20:
        raise ValueError("BlueDOT notifications are exactly 20 bytes")
    status = data[0]
    if status == 0:
        connected = True
    elif status == 3:
        connected = False
    else:
        connected = None
    unit = data[11]
    return {
        "probe_connected": connected,
        "temperature_c": to_celsius(struct.unpack_from("<i", data, 1)[0], unit),
        "alarm_temperature_c": to_celsius(struct.unpack_from("<i", data, 5)[0], unit),
        "alarm_silenced": data[9] != 0,
        "alarm_disabled": data[10] != 0,
        "unit": unit,
        "unknown": data[12],
        "address_bytes": data[13:19],
        "alarm_active": data[19] != 0,
    }


def test_celsius_signed_temperature_and_flags() -> None:
    reading = parse_notification(CELSIUS)
    assert reading["probe_connected"] is True
    assert reading["temperature_c"] == -10.0
    assert reading["alarm_temperature_c"] == 100.0
    assert reading["alarm_silenced"] is True
    assert reading["alarm_disabled"] is False
    assert reading["alarm_active"] is True
    assert reading["unknown"] == 0xA5
    assert reading["address_bytes"] == bytes.fromhex("01 53 00 5e 00 00")


def test_fahrenheit_conversion_for_both_temperatures() -> None:
    reading = parse_notification(FAHRENHEIT)
    assert reading["temperature_c"] == 22.2
    assert reading["alarm_temperature_c"] == 65.6
    assert reading["unit"] == 1
    assert reading["alarm_active"] is False
    negative = bytearray(FAHRENHEIT)
    struct.pack_into("<i", negative, 1, -4)
    assert parse_notification(negative)["temperature_c"] == -20.0


def test_disconnected_and_unknown_probe_states_are_not_current() -> None:
    disconnected = bytearray(CELSIUS)
    disconnected[0] = 3
    assert parse_notification(disconnected)["probe_connected"] is False
    unknown = bytearray(CELSIUS)
    unknown[0] = 1
    assert parse_notification(unknown)["probe_connected"] is None


def test_wrong_lengths_and_units_are_rejected() -> None:
    for length in (0, 1, 10, 19, 21, 40):
        try:
            parse_notification(bytes(length))
        except ValueError:
            pass
        else:
            raise AssertionError(f"accepted length {length}")
    invalid = bytearray(CELSIUS)
    invalid[11] = 2
    try:
        parse_notification(invalid)
    except ValueError:
        pass
    else:
        raise AssertionError("unknown unit silently decoded")
