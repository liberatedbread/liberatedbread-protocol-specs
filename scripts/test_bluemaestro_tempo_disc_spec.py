#!/usr/bin/env python3
"""Independent BlueMaestro advertisement codec checks using stdlib only.

The decoder is transcribed from the layouts in the YAML, not imported from the
upstream parser. Vectors are sanitized public physical fixtures or synthetic app
comparisons; no logger/configuration surface is exercised.
"""

import math
from pathlib import Path

import pytest
import yaml

SPEC = yaml.safe_load(
    (Path(__file__).parents[1] / "device-specs/devices/bluemaestro-tempo-disc.yaml").read_text()
)
FORMATS = {row["version"]: row for row in SPEC["protocol_details"]["advertisement_formats"]}
VECTORS = SPEC["protocol_details"]["test_vectors"]


def dew_point(temperature, humidity):
    if humidity <= 0 or humidity > 100 or temperature == -243.5:
        return None
    alpha = math.log(humidity / 100) + 17.67 * temperature / (temperature + 243.5)
    return math.floor(243.5 * alpha / (17.67 - alpha) * 100 + 0.5) / 100


def decode(payload, company_id=0x0133):
    if company_id != 0x0133:
        raise ValueError("not BlueMaestro environmental data")
    if not payload:
        raise ValueError("truncated measurement layout")
    version = payload[0]
    declaration = FORMATS.get(version)
    if declaration is None:
        raise ValueError("unsupported advertisement version")
    if len(payload) < declaration["minimum_bytes"]:
        raise ValueError("truncated measurement layout")
    kind = declaration["payload_format"]
    little = kind.startswith("Maxi")
    endian = "little" if little else "big"
    output = {"battery_percent": payload[1]}
    temperature = int.from_bytes(payload[15:17] if little else payload[6:8], endian, signed=True)
    output["temperature_c"] = temperature / (100 if little else 10)
    if kind == "LegacyTHD":
        output["humidity_percent"] = int.from_bytes(payload[8:10], "big") / 10
        output["dew_point_c"] = int.from_bytes(payload[10:12], "big", signed=True) / 10
    elif kind == "LegacyTHPD":
        output["humidity_percent"] = int.from_bytes(payload[8:10], "big") / 10
        output["pressure_mbar"] = int.from_bytes(payload[10:12], "big") / 10
    elif kind in {"MaxiTHD", "MaxiTHPD"}:
        output["humidity_percent"] = int.from_bytes(payload[17:19], "little", signed=True) / 100
        output["dew_point_c"] = dew_point(output["temperature_c"], output["humidity_percent"])
        if kind == "MaxiTHPD":
            output["pressure_mbar"] = int.from_bytes(payload[19:23], "little", signed=True) / 100
    return output


def vector(name):
    row = next(row for row in VECTORS if row["name"] == name)
    return row, bytes.fromhex(row["payload_hex"])


@pytest.mark.parametrize("row", VECTORS, ids=lambda row: row["name"])
def test_public_and_synthetic_vectors(row):
    decoded = decode(bytes.fromhex(row["payload_hex"]))
    for field, expected in row["expected"].items():
        if field == "battery_percent":
            assert decoded[field] == expected
        else:
            assert decoded[field] == pytest.approx(expected), field


def test_v23_transmitted_dew_point_is_not_recalculated():
    row, payload = vector("v23_public_transmitted_dew_point")
    decoded = decode(payload)
    assert decoded["dew_point_c"] == 4.9
    calculated = dew_point(decoded["temperature_c"], decoded["humidity_percent"])
    assert round(calculated, 1) == pytest.approx(row["app_calculated_dew_point_c"])
    assert decoded["dew_point_c"] != calculated


@pytest.mark.parametrize("version", sorted(FORMATS))
def test_every_truncated_prefix_is_rejected(version):
    row = next(row for row in VECTORS if row["version"] == version)
    payload = bytes.fromhex(row["payload_hex"])
    minimum = FORMATS[version]["minimum_bytes"]
    for length in range(minimum):
        with pytest.raises(ValueError, match="truncated"):
            decode(payload[:length])
    assert decode(payload[:minimum])


@pytest.mark.parametrize("row", VECTORS, ids=lambda row: row["name"])
def test_trailing_statistics_do_not_change_measurements(row):
    payload = bytes.fromhex(row["payload_hex"])
    assert decode(payload + bytes(range(32))) == decode(payload)


@pytest.mark.parametrize("version", [10, 100, 101, 255])
def test_gateway_and_unknown_versions_are_rejected(version):
    with pytest.raises(ValueError, match="unsupported"):
        decode(bytes([version]) + bytes(31))


def test_wrong_company_is_rejected():
    _, payload = vector("v13_public_temperature")
    with pytest.raises(ValueError, match="not BlueMaestro"):
        decode(payload, company_id=0x004C)


@pytest.mark.parametrize("raw_dew", [-123, 0, 49])
def test_signed_v23_dew_point_is_independent_of_temperature(raw_dew):
    _, payload = vector("v22_synthetic")
    changed = bytearray(payload)
    changed[10:12] = raw_dew.to_bytes(2, "big", signed=True)
    assert decode(changed)["dew_point_c"] == raw_dew / 10


def test_legacy_pressure_is_unsigned():
    _, payload = vector("v27_synthetic_pressure")
    changed = bytearray(payload)
    changed[10:12] = bytes.fromhex("9c40")
    assert decode(changed)["pressure_mbar"] == 4000


@pytest.mark.parametrize("version", [42, 43])
def test_zero_humidity_and_singular_temperature_make_dew_point_unknown(version):
    row = next(row for row in VECTORS if row["version"] == version)
    zero_humidity = bytearray.fromhex(row["payload_hex"])
    zero_humidity[17:19] = bytes(2)
    assert decode(zero_humidity)["dew_point_c"] is None
    singular = bytearray.fromhex(row["payload_hex"])
    singular[15:17] = (-24350).to_bytes(2, "little", signed=True)
    assert decode(singular)["dew_point_c"] is None


def test_only_public_capture_versions_are_marked_confirmed():
    confirmed = {row["version"] for row in FORMATS.values() if row["verification"] == "confirmed"}
    reported = {row["version"] for row in FORMATS.values() if row["verification"] == "reported"}
    assert confirmed == {13, 23}
    assert reported == {8, 22, 27, 41, 42, 43}
    assert SPEC["device"]["testing"]["status"] == "untested"
