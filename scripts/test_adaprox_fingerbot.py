"""Independent Adaprox/Tuya v3 vectors; no hardware or real credentials."""

from __future__ import annotations

import hashlib
import struct
from pathlib import Path

import yaml
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = ROOT / "device-specs" / "devices" / "adaprox-fingerbot.yaml"
SPEC = yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))
TEXT = SPEC_PATH.read_text(encoding="utf-8")


def crc16_modbus(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ (0xA001 if crc & 1 else 0)
    return crc


def varint(value: int) -> bytes:
    assert value >= 0
    encoded = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        encoded.append(byte | (0x80 if value else 0))
        if not value:
            return bytes(encoded)


def fragment(envelope: bytes, protocol_nibble: int, mtu: int = 20) -> list[bytes]:
    writes = []
    packet_number = 0
    offset = 0
    while offset < len(envelope):
        header = bytearray(varint(packet_number))
        if packet_number == 0:
            header += varint(len(envelope))
            header.append(protocol_nibble)
        part = envelope[offset : offset + mtu - len(header)]
        writes.append(bytes(header) + part)
        offset += len(part)
        packet_number += 1
    return writes


def dp_value(dp_id: int, raw: int) -> bytes:
    return bytes([dp_id, 0x02, 0x04]) + struct.pack(">i", raw)


def test_crc16_modbus_standard_check_and_big_endian_append():
    vectors = SPEC["protocol_details"]["tuya_ble_v3"]["test_vectors"]
    assert crc16_modbus(vectors["crc16_modbus"]["input_ascii"].encode()) == 0x4B37
    assert vectors["crc16_modbus"]["expected_hex"] == "4b37"

    meaningful = struct.pack(">IIHH", 1, 0, 0, 0)
    assert crc16_modbus(meaningful) == 0x9269
    assert (meaningful + struct.pack(">H", crc16_modbus(meaningful))).hex() == (
        "0000000100000000000000009269"
    )


def test_frozen_device_info_crypto_and_two_fragment_vector():
    vector = SPEC["protocol_details"]["tuya_ble_v3"]["test_vectors"][
        "device_info"
    ]
    local_key = vector["local_key_ascii"].encode("ascii")
    secret = local_key[:6]
    assert secret == vector["secret_ascii"].encode("ascii")
    login_key = hashlib.md5(secret, usedforsecurity=False).digest()  # noqa: S324
    assert login_key.hex() == vector["login_key_md5_hex"]

    meaningful = struct.pack(
        ">IIHH",
        vector["sequence"],
        vector["response_to"],
        int(vector["function"], 0),
        0,
    )
    plaintext = meaningful + struct.pack(">H", crc16_modbus(meaningful))
    assert plaintext.hex() == vector["plaintext_with_crc_hex"]
    padded = plaintext + bytes((-len(plaintext)) % 16)
    assert padded == plaintext + bytes.fromhex(vector["zero_padding_hex"])

    iv = bytes.fromhex(vector["iv_hex"])
    encryptor = Cipher(algorithms.AES(login_key), modes.CBC(iv)).encryptor()
    ciphertext = encryptor.update(padded) + encryptor.finalize()
    envelope = bytes([vector["security_flag"]]) + iv + ciphertext
    assert envelope.hex() == vector["expected_encrypted_envelope_hex"]

    writes = fragment(envelope, int(vector["community_fragment_nibble"], 0))
    assert [len(write) for write in writes] == vector["gatt_write_lengths"] == [20, 17]
    assert writes[0].endswith(iv)
    assert writes[1].startswith(b"\x01")
    assert b"".join(writes).hex() == vector["expected_concatenated_writes_hex"]
    assert b"".join(writes).hex() == (
        "00213004000102030405060708090a0b0c0d0e0f"
        "01f8bc69d43b1f0e3bf28ac34ec4aa2723"
    )

    vendor_writes = fragment(envelope, int(vector["vendor_fragment_nibble"], 0))
    assert vendor_writes[0][2] == 0x20
    assert writes[0][2] == 0x30
    assert vendor_writes[0][3:] == writes[0][3:]
    assert vendor_writes[1] == writes[1]


def test_varint_fragmentation_is_independent_of_zero_padding():
    envelope = bytes(range(256)) + bytes(44)
    writes = fragment(envelope, 0x30)
    assert len(envelope) == 300
    assert writes[0][:4] == bytes.fromhex("00 ac 02 30")
    assert len(writes[0]) == 20
    assert varint(128) == bytes.fromhex("80 01")

    rebuilt = bytearray()
    for index, write in enumerate(writes):
        cursor = 0
        packet_number = 0
        shift = 0
        while True:
            byte = write[cursor]
            cursor += 1
            packet_number |= (byte & 0x7F) << shift
            shift += 7
            if not byte & 0x80:
                break
        assert packet_number == index
        if index == 0:
            declared = 0
            shift = 0
            while True:
                byte = write[cursor]
                cursor += 1
                declared |= (byte & 0x7F) << shift
                shift += 7
                if not byte & 0x80:
                    break
            assert declared == len(envelope)
            cursor += 1
        rebuilt += write[cursor:]
    assert bytes(rebuilt) == envelope


def test_three_vendor_products_have_three_bounded_layouts():
    expected = {
        "ltak7e1p": ("original_tenths", 111, [112, 113, 114, 115], 0.1),
        "y6kttvd6": ("adaprox_low_schedule", 3, [4, 5, 6, 7], 0.1),
        "blliqpsj": ("plus_seconds", 111, [112, 113, 114, 115], 1),
    }
    variants = SPEC["device"]["variants"]
    assert {v["identification"]["product_id"] for v in variants} == set(expected)
    layouts = SPEC["protocol_details"]["dp_layouts"]
    for product_id, (layout_name, timer, weeks, scale) in expected.items():
        layout = layouts[layout_name]
        assert layout["applies_to_product_ids"] == [product_id]
        assert layout["timer_dp"] == timer
        assert layout["week_program_dps"] == weeks
        sustain = layout["sustain_dp"]
        assert sustain["id"] == 10
        assert sustain["scale"] == scale
        assert sustain["unit"] == "s"

    common = layouts["common"]
    assert common["action_dp"]["id"] == 2
    assert common["action_dp"]["mode_dependent"] == {
        0: "Attended push/click in push mode",
        1: "Switch on/off in switch mode",
        2: "Start/stop program in program mode",
    }
    assert common["tap_enable_dp"]["id"] == 17
    assert common["tap_enable_dp"]["reported_product_ids"] == [
        "ltak7e1p",
        "blliqpsj",
    ]
    assert common["mode_dp"]["id"] == 8
    assert common["down_movement_dp"]["id"] == 9
    assert common["up_movement_dp"]["id"] == 15
    assert common["battery_dp"]["id"] == 12
    original_alternative = layouts["original_tenths"]["alternative_click_dp"]
    assert original_alternative["id"] == 101
    assert "ltak7e1p only" in original_alternative["scope"]
    assert "issue #9" in original_alternative["scope"]
    assert "not a second write after DP2" in original_alternative["scope"]
    assert "manual_control_dp" not in layouts["plus_seconds"]
    assert layouts["plus_seconds"]["loop_dp"]["id"] == 121


def test_dp_scaling_and_raw_schedule_vectors():
    layouts = SPEC["protocol_details"]["dp_layouts"]
    examples = layouts["dp_examples"]
    assert examples["push"]["record_hex"] == "02010101"
    assert "attended push in push mode" in examples["push"]["decode"]
    assert examples["original_alternative_click"]["record_hex"] == "65010101"
    assert "original ltak7e1p" in examples["original_alternative_click"]["decode"]
    assert "click" not in examples
    assert "toggle" not in examples
    assert dp_value(10, 50).hex() == examples["original_sustain_5_seconds"][
        "record_hex"
    ]
    assert 50 * layouts["original_tenths"]["sustain_dp"]["scale"] == 5
    assert dp_value(10, 5).hex() == examples["plus_sustain_5_seconds"][
        "record_hex"
    ]
    assert 5 * layouts["plus_seconds"]["sustain_dp"]["scale"] == 5

    timer = layouts["raw_timer"]["synthetic_vector"]
    encoded_timer = bytes([timer["operation"]]) + struct.pack(">I", timer["seconds"])
    assert len(encoded_timer) == layouts["raw_timer"]["length_bytes"] == 5
    assert encoded_timer.hex() == timer["expected_hex"] == "010000012c"

    week = layouts["week_program"]["synthetic_vector"]
    encoded_week = bytes(
        [
            week["operation"],
            int(week["days_enable_hex"], 16),
            week["hour"],
            week["minute"],
            week["second"],
        ]
    )
    assert len(encoded_week) == layouts["week_program"]["length_bytes"] == 5
    assert encoded_week.hex() == week["expected_hex"] == "0181061e00"
    assert "not a weekday assertion" in week["note"]
    assert "weekday" in layouts["week_program"]["days_enable"]
    assert "unresolved" in layouts["week_program"]["days_enable"]


def test_identify_only_gatt_scope_and_attended_actuation():
    assert SPEC["device"]["integration"] == "identify_only"
    assert SPEC["device"]["testing"]["status"] == "untested"
    discovery = SPEC["device"]["discovery"]
    assert "methods" not in discovery
    assert "Manual selection is required" in discovery["none"]
    assert "not an Adaprox Fingerbot" in discovery["none"]
    assert set(SPEC["device"]["identification"]) == {"notes"}
    advertisement = SPEC["protocol_details"]["tuya_ble_v3"]["advertisement"]
    assert advertisement["automatic_spec_selection"] is False
    assert advertisement["product_identity"] is False
    assert advertisement["service_data_matching_supported"] is False
    services = SPEC["services"]
    assert len(services) == 1
    service = services[0]
    assert service["uuid"] == "00001910-0000-1000-8000-00805f9b34fb"
    assert service["verification"] == "reported"
    characteristics = {c["uuid"]: c for c in service["characteristics"]}
    assert set(characteristics) == {
        "00002b11-0000-1000-8000-00805f9b34fb",
        "00002b10-0000-1000-8000-00805f9b34fb",
    }
    commands = characteristics["00002b11-0000-1000-8000-00805f9b34fb"][
        "commands"
    ]
    assert "DP2 BOOL true in push/click mode" in commands["press"]["description"]
    assert "DP2 BOOL write in program mode" in commands["program_action"]["description"]
    assert "Original ltak7e1p only" in commands["press_original_alternative"]["description"]
    for name in (
        "press",
        "toggle",
        "program_action",
        "press_original_alternative",
        "set_mode",
        "set_movement",
        "set_sustain",
        "set_timer",
        "set_week_program",
        "set_loop",
        "ota_transfer",
    ):
        assert commands[name]["advanced"] is True
        assert len(commands[name]["advanced_reason"]) > 40
        assert "value" not in commands[name]
        assert "template" not in commands[name]
        assert commands[name]["verification"] == "reported"

    assert "0000fd50-0000-1000-8000-00805f9b34fb" not in TEXT
    assert "3yqdo5yt" not in TEXT
    assert "xhf790if" not in TEXT
    legacy = SPEC["protocol_details"]["legacy_asb_abb_plaintext"]
    assert legacy["framing"] == "ASCII '*' || code || payload || '$' (literal form: *<code><payload>$)"
    assert "not SwitchBot" in legacy["notes"]
    assert "not the Tuya encrypted DP protocol" in legacy["notes"]
