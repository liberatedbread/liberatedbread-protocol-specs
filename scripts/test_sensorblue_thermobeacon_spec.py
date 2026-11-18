#!/usr/bin/env python3
"""Independent SensorBlue/ThermoBeacon passive-codec checks.

Only the public 20-byte measurement layout is transcribed. The 22-byte form is
accepted for identification but never decoded as measurements.
"""

from pathlib import Path

import pytest
import yaml

SPEC = yaml.safe_load(
    (Path(__file__).parents[1] / "device-specs/devices/sensorblue-thermobeacon.yaml").read_text()
)
SERVICE_UUID = "0000fff0-0000-1000-8000-00805f9b34fb"
KNOWN_IDS = {0x10, 0x11, 0x14, 0x15, 0x18, 0x1B, 0x30}
VECTORS = SPEC["protocol_details"]["test_vectors"]


def identify(service_uuid, numeric_id, reconstructed):
    return service_uuid == SERVICE_UUID and numeric_id in KNOWN_IDS and len(reconstructed) in {20, 22}


def battery_estimate(millivolts):
    if millivolts >= 3000:
        return 100
    if millivolts >= 2600:
        return 60 + (millivolts - 2600) * 0.1
    if millivolts >= 2500:
        return 40 + (millivolts - 2500) * 0.2
    if millivolts >= 2450:
        return 20 + (millivolts - 2450) * 0.4
    return 0


def decode(reconstructed, service_uuid=SERVICE_UUID):
    if len(reconstructed) < 2:
        raise ValueError("missing numeric ID")
    numeric_id = int.from_bytes(reconstructed[:2], "little")
    if not identify(service_uuid, numeric_id, reconstructed):
        raise ValueError("not a supported ThermoBeacon record")
    if len(reconstructed) != 20:
        raise ValueError("only the 20-byte form emits measurements")
    battery_mv = int.from_bytes(reconstructed[10:12], "little")
    temperature = int.from_bytes(reconstructed[12:14], "little", signed=True) / 16
    humidity = int.from_bytes(reconstructed[14:16], "little") / 16
    if temperature > 100 or humidity > 100:
        raise ValueError("out-of-range environmental reading")
    return {
        "device_type": reconstructed[0],
        "button_pressed": bool(reconstructed[3] & 0x80),
        "battery_mv": battery_mv,
        "temperature_c": temperature,
        "humidity_percent": humidity,
        "estimated_battery_percent": battery_estimate(battery_mv),
    }


def vector(name):
    row = next(row for row in VECTORS if row["name"] == name)
    return bytes.fromhex(row["reconstructed_hex"]), row["expected"]


@pytest.mark.parametrize(
    "name",
    [
        "public_id_10_measurements",
        "public_id_30_measurements",
        "synthetic_signed_temperature_and_estimated_battery",
    ],
)
def test_public_and_synthetic_vectors(name):
    payload, expected = vector(name)
    decoded = decode(payload)
    for field, expected_value in expected.items():
        if isinstance(expected_value, bool):
            assert decoded[field] is expected_value
        else:
            assert decoded[field] == pytest.approx(expected_value), field


def test_22_byte_form_identifies_without_emitting_measurements():
    payload = bytes.fromhex("150000f0050000d76ebe0165000000a7010000000000")
    assert len(payload) == 22
    assert identify(SERVICE_UUID, 0x15, payload)
    with pytest.raises(ValueError, match="20-byte"):
        decode(payload)


@pytest.mark.parametrize("length", [0, 1, 2, 19, 21, 23, 32])
def test_other_lengths_are_rejected(length):
    with pytest.raises(ValueError):
        decode(bytes([0x10, 0]) + bytes(max(0, length - 2)))


@pytest.mark.parametrize("numeric_id", [0, 0x12, 0x31, 0xFFFF])
def test_unknown_numeric_ids_are_not_model_guesses(numeric_id):
    payload, _ = vector("public_id_10_measurements")
    changed = numeric_id.to_bytes(2, "little") + payload[2:]
    with pytest.raises(ValueError, match="not a supported"):
        decode(changed)


def test_missing_or_shared_service_uuid_alone_is_not_identification():
    payload, _ = vector("public_id_10_measurements")
    with pytest.raises(ValueError, match="not a supported"):
        decode(payload, service_uuid="0000ffe0-0000-1000-8000-00805f9b34fb")


@pytest.mark.parametrize(
    ("temperature_raw", "humidity_raw"),
    [(1601, 800), (800, 1601), (32767, 1601)],
)
def test_out_of_range_values_discard_the_whole_measurement(temperature_raw, humidity_raw):
    payload = bytearray(vector("public_id_10_measurements")[0])
    payload[12:14] = temperature_raw.to_bytes(2, "little", signed=True)
    payload[14:16] = humidity_raw.to_bytes(2, "little")
    with pytest.raises(ValueError, match="out-of-range"):
        decode(payload)


@pytest.mark.parametrize(
    ("millivolts", "expected"),
    [
        (0, 0),
        (2449, 0),
        (2450, 20),
        (2499, 39.6),
        (2500, 40),
        (2599, 59.8),
        (2600, 60),
        (2999, 99.9),
        (3000, 100),
        (3500, 100),
    ],
)
def test_battery_percentage_is_piecewise_estimate(millivolts, expected):
    assert battery_estimate(millivolts) == pytest.approx(expected)


def test_signed_temperature_is_not_clamped_to_zero():
    payload, _ = vector("synthetic_signed_temperature_and_estimated_battery")
    decoded = decode(payload)
    assert decoded["temperature_c"] == -1
    assert decoded["button_pressed"] is True
    assert decoded["estimated_battery_percent"] == pytest.approx(35.2)


def test_numeric_ids_have_no_retail_model_mapping():
    for row in SPEC["protocol_details"]["numeric_device_ids"]:
        assert row["retail_model_mapping"] == "unresolved"
    assert SPEC["device"]["testing"]["status"] == "untested"


def test_shared_service_is_not_an_identity_matcher():
    assert "service_uuids" not in SPEC["device"]["identification"]
    for method in SPEC["device"]["discovery"]["methods"]:
        assert "service_uuids" not in method.get("ble", {})
