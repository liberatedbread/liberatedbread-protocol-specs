"""Independent vectors for the lock/home protocol corrections.

Frame construction and parsing below use only the Python standard library and
are transcribed from the specs. PyYAML is used only to read the specification;
no repository helper or client implementation is imported.
"""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
NAMES = (
    "nuki-smart-lock",
    "yale-august-ble",
    "schlage-smart-locks",
    "ttlock-sciener-ble",
    "sesame-candyhouse-ble",
    "safetech-smart-padlock",
    "biokey-touchlock-fingerprint-lock",
    "switchbot-ble",
    "eqiva-eq3-ble-trv",
    "devolo-home-control",
    "chamberlain-garage-opener-secplus",
)
SPECS = {
    name: yaml.safe_load(
        (ROOT / "device-specs" / "devices" / f"{name}.yaml").read_text(
            encoding="utf-8"
        )
    )
    for name in NAMES
}


def _characteristic(spec, uuid):
    for service in spec["services"]:
        for characteristic in service.get("characteristics", []):
            if characteristic["uuid"] == uuid:
                return service, characteristic
    raise AssertionError(f"characteristic {uuid} not found")


def _commands(spec):
    result = {}
    for service in spec["services"]:
        for characteristic in service.get("characteristics", []):
            result.update(characteristic.get("commands", {}))
    return result


def _yale_frame(template):
    frame = [0 if value == "{checksum}" else value for value in template]
    frame[3] = (-sum(frame)) & 0xFF
    return bytes(frame)


def _safetech_input(ui_hex):
    return bytes([0]) + bytes.fromhex(ui_hex) + bytes(4)


def _safetech_update(current_ui_hex, new_ui_hex):
    return bytes([1]) + bytes.fromhex(current_ui_hex) + bytes.fromhex(new_ui_hex)


def _eq3_status(frame, fields):
    return {
        field["name"]: frame[field["offset"] : field["offset"] + field["length"]][0]
        for field in fields
    }


def _decode_signed16(raw):
    return raw - 0x10000 if raw & 0x8000 else raw


def test_yale_operation_frames_checksums_and_channels():
    spec = SPECS["yale-august-ble"]
    _, normal = _characteristic(spec, "bd4ac611-0b45-11e3-8ffd-0800200c9a66")
    _, response = _characteristic(spec, "bd4ac612-0b45-11e3-8ffd-0800200c9a66")
    _, setup = _characteristic(spec, "bd4ac613-0b45-11e3-8ffd-0800200c9a66")
    commands = normal["commands"]

    assert "Normal operation" in normal["name"]
    assert "Normal operation" in response["name"]
    assert "Setup and shutdown only" in setup["notes"]
    assert "commands" not in setup
    assert spec["entities"][0]["command_characteristic"] == normal["uuid"]

    expected = {
        "unlock": (0x0A, 0x00, 0x06),
        "lock": (0x0B, 0x00, 0x05),
        "get_lock_status": (0x02, 0x02, 0x0C),
        "get_door_status": (0x02, 0x2E, 0xE0),
        "get_door_and_lock_status": (0x02, 0x2F, 0xDF),
        "get_battery_status": (0x02, 0x0F, 0xFF),
        "get_unread_activity_count": (0x02, 0x09, 0x05),
    }
    for name, (opcode, subtype, checksum) in expected.items():
        command = commands[name]
        frame = (
            _yale_frame(command["template"])
            if "template" in command
            else bytes(command["value"])
        )
        assert len(frame) == 18, name
        assert frame[0] == 0xEE, name
        assert frame[1] == opcode, name
        assert frame[3] == checksum, name
        assert frame[4] == subtype, name
        assert frame[16:] == b"\x02\x00", name
        assert sum(frame) % 256 == 0, name

    assert "does not consume" in commands["get_unread_activity_count"]["description"]
    assert "0x2D GETLOG" in spec["device"]["notes"]
    assert "pops the oldest" in spec["device"]["notes"]
    assert spec["device"]["identification"]["manufacturer_data"][
        "additional_company_ids"
    ] == [302]
    scan = spec["device"]["discovery"]["methods"][0]["ble"]
    assert scan["manufacturer_data"]["additional_company_ids"] == [302]
    assert "AES-ECB" in spec["device"]["notes"]
    assert "that session key, not the offline key directly" in spec["device"]["notes"]


def test_safetech_nine_byte_raw_password_vectors():
    assert _safetech_input("01234567") == bytes.fromhex("00 01 23 45 67 00 00 00 00")
    assert _safetech_update("01234567", "89abcdef") == bytes.fromhex(
        "01 01 23 45 67 89 ab cd ef"
    )

    spec = SPECS["safetech-smart-padlock"]
    _, characteristic = _characteristic(spec, "0000ffd6-0000-1000-8000-00805f9b34fb")
    assert "Both operations are nine bytes" in characteristic["description"]
    assert "four raw bytes, not eight ASCII bytes" in characteristic["description"]
    unknowns = spec["protocol_details"]["command_protocol"]["remaining_unknowns"]
    assert any("factory default password" in item for item in unknowns)
    assert not any("raw hex bytes vs ASCII" in item for item in unknowns)


def test_sesame_requests_write_property_and_status_sentinels():
    spec = SPECS["sesame-candyhouse-ble"]
    _, tx = _characteristic(spec, "16860002-a5ae-9856-b6d3-dbb4c676993e")
    _, rx = _characteristic(spec, "16860003-a5ae-9856-b6d3-dbb4c676993e")
    assert tx["properties"] == ["write_without_response"]
    assert tx["commands"]["lock"]["value"] == [0x52, 0x00]
    assert tx["commands"]["unlock"]["value"] == [0x53, 0x00]
    assert tx["commands"]["read_history_peek"]["value"] == [0x04, 0x01]

    battery_raw = 3450
    target_raw = 0x8000
    flags = 0x26
    assert battery_raw * 2 == 6900
    assert _decode_signed16(target_raw) == -32768
    assert bool(flags & 0x02) is True  # lock range
    assert bool(flags & 0x04) is True  # unlock range
    assert bool(flags & 0x20) is True  # low battery
    assert "raw*2 mV" in rx["notes"]
    assert "Target 0x8000" in rx["notes"]
    assert "before AES-CCM" in tx["commands"]["lock"]["description"]

    links = [entry["url"] for entry in spec["helpful_urls"]]
    assert any("docs/en/SesameOS3/bluetooth.md" in url for url in links)
    assert all("/master/SesameOS3/bluetooth.md" not in url for url in links)


def test_eq3_zero_based_status_and_special_temperature_range():
    spec = SPECS["eqiva-eq3-ble-trv"]
    _, command = _characteristic(spec, "3fa4585a-ce4a-3bad-db4b-b8df8179ea09")
    _, status = _characteristic(spec, "d0e8434d-cd29-0996-af41-6c90f4e0eb2a")
    assert command["properties"] == ["read", "write"]
    raw = command["commands"]["set_temperature"]["parameters"]["raw"]
    assert (raw["min"], raw["max"]) == (9, 60)
    assert spec["entities"][0]["max_temp"] == 30.0

    decoded = _eq3_status(bytes.fromhex("02 01 09 50 04 1e"), status["format"])
    assert decoded["response_type"] == 0x02
    assert decoded["status_marker"] == 0x01
    assert decoded["mode"] == 0x09
    assert decoded["valve_percent"] == 80
    assert decoded["temperature_marker"] == 0x04
    target = next(field for field in status["format"] if field["name"] == "target_temperature")
    assert decoded["target_temperature"] * target["scale"] == 15.0
    assert "raw 9 (4.5 °C) is the special off value" in raw["description"]
    assert "raw 60 (30.0 °C)" in raw["description"]


def test_switchbot_discovery_and_model_specific_layouts():
    spec = SPECS["switchbot-ble"]
    scan = spec["device"]["discovery"]["methods"][0]["ble"]
    assert "service_uuids" not in scan
    assert scan["service_data"] == ["0000fd3d-0000-1000-8000-00805f9b34fb"]
    assert scan["manufacturer_data"]["company_id"] == 0x0969

    _, rx = _characteristic(spec, "cba20003-224d-11e6-9fb8-0002a5d5c51b")
    assert [field["name"] for field in rx["format"]] == ["status"]
    bot_response = bytes([0x01, 85, 42])
    meter_response = bytes([0x01, 80, 41, 0x54, 0x00])
    sensor_response = bytes([0x01, 50, 22, 60])
    assert bot_response[1] == 85  # Bot GetBasicInfo battery
    assert bot_response[2] == 42  # Bot GetBasicInfo firmware
    assert meter_response[1:3] == bytes([80, 41])
    assert meter_response[3:] == bytes([0x54, 0x00])
    assert sensor_response[1:] == bytes([50, 22, 60])
    assert "A Meter's GetBasicInfo" in rx["notes"]
    assert "MeterReadSensor" in rx["notes"]

    assert all(
        entity.get("state_characteristic") != "00002a19-0000-1000-8000-00805f9b34fb"
        for entity in spec["entities"]
    )
    commands = _commands(spec)
    assert commands["bot_press"]["value"] == [0x57, 0x01, 0x00]
    assert commands["bot_turn_on"]["value"] == [0x57, 0x01, 0x01]
    assert commands["bot_turn_off"]["value"] == [0x57, 0x01, 0x02]
    assert commands["find_device"]["value"] == [0x57, 0x01, 0x03]
    assert "push-stop" in commands["find_device"]["description"]
    assert "0x04 to back" in commands["find_device"]["description"]


def test_ttlock_battery_service_parent():
    spec = SPECS["ttlock-sciener-ble"]
    service, battery = _characteristic(spec, "00002a19-0000-1000-8000-00805f9b34fb")
    assert service["uuid"] == "0000180f-0000-1000-8000-00805f9b34fb"
    assert service["uuid"] != "00001910-0000-1000-8000-00805f9b34fb"
    assert battery["format"][0]["offset"] == 0
    assert battery["format"][0]["unit"] == "%"


def test_nuki_pin_keypad_response_and_unknown_door_state():
    spec = SPECS["nuki-smart-lock"]
    assert "length" not in spec["device"]["pairing"]["pin"]
    keypad = spec["protocol_details"]["command_protocol"]["commands"]["keypad_code_id"]
    assert keypad["id"] == 0x42
    assert keypad["direction"] == "device_to_client"
    assert "0x0042" in keypad["name"]
    states = spec["protocol_details"]["command_protocol"]["door_sensor_states"]
    assert states[255].startswith("UNKNOWN")
    fields = spec["protocol_details"]["command_protocol"]["commands"][
        "keyturner_states"
    ]["fields"]
    door = next(field for field in fields if field["name"] == "doorSensorState")
    assert "0xFF=unknown on SL 3.0+" in door["description"]


def test_schlage_rxdata_subscription_and_reported_wire_facts():
    spec = SPECS["schlage-smart-locks"]
    initial = spec["initialization"][0]
    assert initial["characteristic"] == "26002998-e001-4812-8c08-5cd2afda0830"
    assert initial["subscribe"] is True
    assert "read" not in initial
    _, rx = _characteristic(spec, initial["characteristic"])
    assert rx["properties"] == ["indicate"]
    assert spec["cloud"]["auth"]["verification"] == "reported"
    commands = _commands(spec)
    for name in (
        "lock_unlock",
        "lock_state",
        "read_info",
        "set_access_code_length",
        "save_access_code",
        "delete_access_code",
        "delete_all_access_codes",
    ):
        assert commands[name]["verification"] == "reported", name


def test_biokey_capture_sentence_is_scoped_to_unlock():
    detail = SPECS["biokey-touchlock-fingerprint-lock"]["device"]["security_advisory"]["detail"]
    assert "no over-the-air capture exists" not in detail
    assert "crashed before the unlock exchange" in detail
    assert "reported rather than demonstrated" in detail


def test_devolo_cached_credentials_stay_local_without_fresh_cloud_minting():
    spec = SPECS["devolo-home-control"]
    failure = spec["cloud"]["failure_mode"]
    assert "already cached the account UUID and gateway passkey" in failure
    assert "acquiring those credentials afresh depends" in failure
    covers = " ".join(spec["local_access"]["covers"])
    assert "local JSON-RPC API" in covers
    gateway = spec["device"]["variants"][0]["notes"]
    assert "already cached" in gateway
    assert "cannot be reconfigured" not in gateway


def test_chamberlain_wired_generation_scope_keeps_no_pairing_requirement():
    spec = SPECS["chamberlain-garage-opener-secplus"]
    notes = spec["device"]["notes"]
    assert "1200 baud, 8E1" in notes
    assert "short wall-console commands and press/release" in notes
    assert "RF remote's rolling/fixed-code encoding is a different" in notes
    command = spec["bus"]["messages"][0]["notes"]
    assert "Security+ 1.0 instead emits its short command" in command
    assert "matching release command after a delay" in command
    assert spec["device"]["setup"]["credentials"]["stored_on_device"] == [
        "Security+ 2.0 rolling-code counter (persisted on the bridge board)"
    ]
    assert spec["device"]["pairing"]["required"] is False
    assert spec["device"]["pairing"]["enter_pairing_mode"]["required"] is False
    setup_steps = spec["device"]["setup"]["methods"][0]["steps"]
    assert all("press the opener's learn button to pair" not in step["action"].lower() for step in setup_steps)
    assert "No learn-button press is needed" in setup_steps[-1]["action"]


def test_kevo_gen2_doc_matches_existing_ten_second_procedure():
    spec = yaml.safe_load(
        (ROOT / "device-specs" / "devices" / "kwikset-kevo.yaml").read_text(
            encoding="utf-8"
        )
    )
    procedure = spec["device"]["setup"]["factory_reset"]["procedures"][0]
    assert procedure["hold_seconds"] == 10
    doc = (ROOT / "docs" / "devices" / "kwikset-kevo.md").read_text(encoding="utf-8")
    assert "Reset button on the back panel for **ten seconds**" in doc
    assert "~20 s" not in doc
