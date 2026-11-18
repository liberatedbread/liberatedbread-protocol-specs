import json


BATTERY_STATES = {
    0: "unknown",
    1: "low",
    2: "nominal",
    3: "full",
    "BATTERY_LEVEL_UNKNOWN": "unknown",
    "BATTERY_LEVEL_LOW": "low",
    "BATTERY_LEVEL_NOMINAL": "nominal",
    "BATTERY_LEVEL_FULL": "full",
}

ONBOARDING = {
    "service": "0000fee3-0000-1000-8000-00805f9b34fb",
    "write": "30619f2d-0f54-41bd-a65a-7588d8c85b45",
    "read_notify": "7d2a4bda-d29b-4152-b725-2491478c5cd7",
}


def decode_battery(document):
    response = json.loads(document)
    return {
        "level": BATTERY_STATES[response["battery_level"]],
        "voltage": float(response["battery_volts"]),
        "charging": bool(response["is_charging"]),
        "on_platform": bool(response["is_on_charger_platform"]),
    }


def test_numeric_and_named_battery_enums_with_separate_voltage():
    numeric = decode_battery(
        '{"battery_level": 2, "battery_volts": 3.834, '
        '"is_charging": true, "is_on_charger_platform": true}'
    )
    named = decode_battery(
        '{"battery_level": "BATTERY_LEVEL_NOMINAL", "battery_volts": 3.7, '
        '"is_charging": false, "is_on_charger_platform": true}'
    )
    assert numeric == {
        "level": "nominal",
        "voltage": 3.834,
        "charging": True,
        "on_platform": True,
    }
    assert named["level"] == "nominal"
    assert named["voltage"] == 3.7
    assert not named["charging"]
    assert named["on_platform"]


def test_battery_level_is_not_percent():
    for raw, expected in ((0, "unknown"), (1, "low"), (2, "nominal"), (3, "full")):
        assert BATTERY_STATES[raw] == expected
    assert 87 not in BATTERY_STATES


def test_signed_image_version_identity_and_onboarding_uuids():
    manifest = {"update_version": "2.0.1.6079", "ankidev": 0}
    extracted_os_version = "2.0.1.6079"
    assert manifest["update_version"] == extracted_os_version
    assert tuple(map(int, extracted_os_version.split("."))) > (2, 0, 1, 6076)
    assert ONBOARDING["service"].startswith("0000fee3-")
    assert ONBOARDING["write"] != ONBOARDING["read_notify"]
