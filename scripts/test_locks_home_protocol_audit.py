"""Independent vectors for the lock/home protocol corrections.

Frame construction and parsing below use only the Python standard library and
are transcribed from the specs. PyYAML is used only to read the specification;
no repository helper or client implementation is imported.
"""

import shutil
import subprocess
from pathlib import Path

import pytest
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


def _security_terms(frame):
    assert len(frame) == 18
    return (
        int.from_bytes(frame[0:4], "little"),
        int.from_bytes(frame[4:8], "little"),
        int.from_bytes(frame[8:18], "little"),
    )


def _security_checksum(frame, *, zero_checksum=True):
    frame = bytearray(frame)
    if zero_checksum:
        frame[12:16] = bytes(4)
    return (-sum(_security_terms(frame))) & 0xFFFFFFFF


def _openssl_cbc(plaintext, key_hex, iv_hex, *, decrypt=False):
    command = [
        shutil.which("openssl"),
        "enc",
        "-aes-128-cbc",
        "-K",
        key_hex,
        "-iv",
        iv_hex,
        "-nopad",
    ]
    if decrypt:
        command.append("-d")
    return subprocess.run(command, input=plaintext, capture_output=True, check=True).stdout


def _decode_layout(frame, fields):
    decoded = {}
    for field in fields:
        offset = field["offset"]
        raw = frame[offset : offset + field["length"]]
        value = int.from_bytes(raw, field.get("endianness", "big"))
        if "mask" in field:
            value &= field["mask"]
        decoded[field["name"]] = value
    return decoded


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


def test_yale_application_frames_are_not_executable_bindings():
    spec = SPECS["yale-august-ble"]
    _, normal = _characteristic(spec, "bd4ac611-0b45-11e3-8ffd-0800200c9a66")
    _, response = _characteristic(spec, "bd4ac612-0b45-11e3-8ffd-0800200c9a66")
    _, setup = _characteristic(spec, "bd4ac613-0b45-11e3-8ffd-0800200c9a66")
    assert "commands" not in normal
    assert "commands" not in response
    assert "commands" not in setup
    assert not spec.get("entities")
    assert spec["protocol_details"]["consumer_limitations"]["executable_commands"] is False

    requests = spec["protocol_details"]["normal_operation"]["requests"]
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
        frame = bytes.fromhex(requests[name]["application_frame_hex"])
        assert len(frame) == 18, name
        assert frame[0] == 0xEE, name
        assert frame[1] == opcode, name
        assert frame[3] == checksum, name
        assert frame[4] == subtype, name
        assert frame[16:] == b"\x02\x00", name
        assert sum(frame) % 256 == 0, name
    assert "does not consume" in requests["get_unread_activity_count"]["description"]
    assert "not on-wire GATT values" in spec["protocol_details"]["normal_operation"]["application_frame"]["note"]

    crypto = spec["protocol_details"]["session_crypto"]["normal_operation"]
    assert "independent client-to-lock and lock-to-client" in crypto["key_installation"]
    assert "Persist each direction's CBC state" in crypto["chaining"]
    assert "A reconnect tears down both contexts" in crypto["reconnect"]
    assert "zero-IV encryptions" not in crypto["key_installation"]


def test_yale_secure_handshake_checksum_known_answer():
    spec = SPECS["yale-august-ble"]
    known = spec["protocol_details"]["session_crypto"]["secure_handshake"]["checksum"]["known_answer"]
    source = bytes.fromhex(known["input_hex"])
    assert _security_terms(source) == tuple(
        int(known[name], 0) for name in ("val1", "val2", "val3")
    )
    assert _security_checksum(source) == int(known["checksum"], 0)

    output = bytes.fromhex(known["output_hex"])
    assert len(output) == 18
    assert output[12:16] == int(known["checksum"], 0).to_bytes(4, "little")
    stored = int.from_bytes(output[12:16], "little")
    assert stored == _security_checksum(output, zero_checksum=False)
    assert stored != ((-sum(output)) & 0xFF)


def test_yale_cbc_chains_two_commands_and_responses():
    if shutil.which("openssl") is None:
        pytest.skip("openssl binary not available")
    vectors = SPECS["yale-august-ble"]["protocol_details"]["synthetic_cbc_vectors"]
    key = vectors["key_hex"]
    iv = vectors["initial_iv_hex"]
    for direction in ("client_to_device", "device_to_client"):
        frames = vectors[direction]
        assert len(frames) == 2
        plaintext = b"".join(
            bytes.fromhex(frame["plaintext_hex"])[:16] for frame in frames
        )
        expected = b"".join(
            bytes.fromhex(frame["ciphertext_hex"])[:16] for frame in frames
        )
        actual = _openssl_cbc(plaintext, key, iv)
        assert actual == expected, direction
        assert _openssl_cbc(actual, key, iv, decrypt=True) == plaintext
        second_with_reset_iv = _openssl_cbc(plaintext[16:32], key, iv)
        assert second_with_reset_iv != actual[16:32], direction
        for frame in frames:
            ciphertext = bytes.fromhex(frame["ciphertext_hex"])
            plaintext_frame = bytes.fromhex(frame["plaintext_hex"])
            assert len(ciphertext) == len(plaintext_frame) == 18
            assert ciphertext[16:] == plaintext_frame[16:]
            assert ciphertext[:16] != plaintext_frame[:16]
            if direction == "client_to_device":
                assert ciphertext[16:] == b"\x02\x00"


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


def test_sesame_application_requests_are_not_executable_bindings():
    spec = SPECS["sesame-candyhouse-ble"]
    _, tx = _characteristic(spec, "16860002-a5ae-9856-b6d3-dbb4c676993e")
    _, rx = _characteristic(spec, "16860003-a5ae-9856-b6d3-dbb4c676993e")
    assert tx["properties"] == ["write_without_response"]
    assert "commands" not in tx
    assert not spec.get("entities")
    assert spec["protocol_details"]["consumer_limitations"]["entity_bindings"] is False

    requests = spec["protocol_details"]["application_layer"]["requests"]
    assert requests["lock"]["application_frame_hex"] == "52 00"
    assert requests["unlock"]["application_frame_hex"] == "53 00"
    assert requests["read_history_peek"]["application_frame_hex"] == "04 01"
    assert requests["lock"]["fields"][1] == {
        "offset": 1,
        "length": 1,
        "name": "history_tag_length",
        "value": 0,
    }
    assert requests["unlock"]["fields"][1] == requests["lock"]["fields"][1]
    assert requests["read_history_peek"]["fields"][1] == {
        "offset": 1,
        "length": 1,
        "name": "peek",
        "value": 1,
    }

    layers = spec["protocol_details"]["security_and_segment_layers"]
    assert "append its four-byte CCM tag" in layers["on_wire"]
    assert "0x05" in layers["on_wire"]
    assert "0x04" in layers["on_wire"]
    assert layers["ciphertext_vectors"].startswith("Not asserted")
    assert "do not publish a complete known-answer tuple" in layers["ciphertext_vectors"]

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
    methods = spec["device"]["discovery"]["methods"]
    assert len(methods) == 2
    newer, legacy = methods
    assert newer["ble"]["manufacturer_data"]["company_id"] == 0x0969
    assert "service_uuids" not in newer["ble"]
    assert legacy["ble"]["service_uuids"] == [
        "cba20d00-224d-11e6-9fb8-0002a5d5c51b"
    ]
    assert all("service_data" not in method["ble"] for method in methods)
    assert spec["protocol_details"]["discovery_limitations"]["service_data_matching"] is False

    _, rx = _characteristic(spec, "cba20003-224d-11e6-9fb8-0002a5d5c51b")
    assert [field["name"] for field in rx["format"]] == ["status"]
    variants = spec["protocol_details"]["response_layouts"]["get_basic_info"]["variants"]
    bot_response = bytes.fromhex(variants["Bot"]["response_hex"])
    bot = _decode_layout(bot_response, variants["Bot"]["fields"])
    assert len(bot_response) == 13
    assert bot == {
        "status": 1,
        "battery_percent": 100,
        "firmware_version_raw": 44,
        "strength": 100,
        "adc_raw": 0,
        "motor_calibration_raw": 0xA1,
        "timer_count": 0,
        "act_mode": 0,
        "hold_times": 0,
        "service_data_byte0": 0x48,
        "service_data_byte1": 0,
    }
    assert bot["firmware_version_raw"] * 0.1 == pytest.approx(4.4)
    assert "Official SwitchBot Bot BLE API" in variants["Bot"]["origin"]

    meter_response = bytes.fromhex(variants["Meter"]["response_hex"])
    meter = _decode_layout(meter_response, variants["Meter"]["fields"])
    assert len(meter_response) == 5
    assert meter == {
        "status": 1,
        "battery_percent": 80,
        "firmware_version_raw": 41,
        "service_data_byte0": 0x54,
        "service_data_byte1": 0,
    }
    assert "Synthetic full-layout vector" in variants["Meter"]["origin"]

    sensor_layout = spec["protocol_details"]["response_layouts"]["meter_read_sensor"]
    sensor_response = bytes.fromhex(sensor_layout["response_hex"])
    sensor = _decode_layout(sensor_response, sensor_layout["fields"])
    assert sensor == {
        "status": 1,
        "temperature_fraction": 5,
        "temperature_integer_and_sign": 22,
        "humidity_percent": 60,
    }

    advertisement = spec["protocol_details"]["advertisement_service_data"]
    assert advertisement["entity_binding"]["supported"] is False
    for vector in advertisement["vectors"]:
        service_data = bytes.fromhex(vector["service_data_hex"])
        decoded = _decode_layout(service_data, advertisement["fields"])
        assert decoded["battery_percent"] == vector["expected_battery_percent"]
    assert advertisement["vectors"][0]["service_data_hex"] == "48 90 D9"
    assert advertisement["vectors"][1]["service_data_hex"] == "54 00 E4 06 98 35"

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
    assert commands["find_device"]["advanced"] is True
    assert "not a locator" in commands["find_device"]["advanced_reason"].lower()
    assert "locate" not in commands["find_device"]
    for press in ("bot_press", "bot_turn_on", "bot_turn_off"):
        assert "advanced" not in commands[press]


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


# Lock specs whose actuation is documented. Each carries a physical-safety
# banner, and every characteristic command that can open the lock is advanced
# with a reason: unlocking is the one thing a user must not trip into.
# biokey-touchlock-fingerprint-lock and kwikset-kevo are not listed yet.
LOCKS_WITH_SAFETY_ADVISORY = {
    "danalock-v3-ble": (),
    "fc-smarthome-lock": (),
    "nuki-smart-lock": (),
    "safetech-smart-padlock": ("unlock",),
    "schlage-smart-locks": ("lock_unlock",),
    "ttlock-sciener-ble": (),
    "sesame-candyhouse-ble": (),
    "wyze-lock-bolt": (),
    "yale-august-ble": (),
}


def _all_characteristic_commands(spec):
    result = {}
    for service in spec.get("services") or []:
        for characteristic in service.get("characteristics") or []:
            result.update(characteristic.get("commands") or {})
    return result


@pytest.mark.parametrize("name", sorted(LOCKS_WITH_SAFETY_ADVISORY))
def test_lock_specs_carry_a_safety_advisory_and_gate_unlock(name):
    path = ROOT / "device-specs" / "devices" / f"{name}.yaml"
    spec = SPECS.get(name) or yaml.safe_load(path.read_text(encoding="utf-8"))
    assert spec["device"]["category"] == "lock"
    advisory = spec["device"]["safety_advisory"]
    assert advisory["severity"] in ("warning", "danger")
    assert advisory["summary"].strip() and advisory["detail"].strip()
    commands = _all_characteristic_commands(spec)
    gated = set(LOCKS_WITH_SAFETY_ADVISORY[name])
    gated |= {command for command in commands if "unlock" in command}
    for command in gated:
        assert commands[command].get("advanced") is True, f"{name}.{command}"
        assert commands[command]["advanced_reason"].strip(), f"{name}.{command}"


def test_yale_group_company_id_is_not_a_matcher():
    spec = SPECS["yale-august-ble"]
    blocks = [spec["device"]["identification"]["manufacturer_data"]]
    blocks += [
        method["ble"]["manufacturer_data"]
        for method in spec["device"]["discovery"]["methods"]
        if "manufacturer_data" in method.get("ble", {})
    ]
    for block in blocks:
        assert block["company_id"] == 0x01D1
        assert 0x012E not in block.get("additional_company_ids", [])
    assert "0x012E" in blocks[0]["description"]


def test_chamberlain_door_toggle_is_advanced_with_a_safety_advisory():
    spec = SPECS["chamberlain-garage-opener-secplus"]
    advisory = spec["device"]["safety_advisory"]
    assert advisory["severity"] == "warning"
    assert "door_command" in advisory["summary"]
    assert "SAFETY:" not in spec["device"]["notes"]
    (toggle,) = [m for m in spec["bus"]["messages"] if m["name"].startswith("door_command")]
    assert toggle["advanced"] is True
    reason = toggle["advanced_reason"]
    assert "crush" in reason and "door in view" in reason


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
