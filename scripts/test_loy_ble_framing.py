"""LOY AA55 control vectors and BLE-versus-UDP framing boundaries."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEVICES = ROOT / "device-specs" / "devices"


def load(name):
    return yaml.safe_load((DEVICES / f"{name}.yaml").read_text(encoding="utf-8"))


def aa55(sequence, command_type, payload):
    frame = bytearray.fromhex("aa 55 ff ff")
    frame += (len(payload) + 6).to_bytes(2, "little")
    frame += sequence.to_bytes(2, "little")
    frame += bytes([0xC1, command_type])
    frame += payload
    frame += (sum(frame) & 0xFFFF).to_bytes(2, "little")
    return bytes(frame)


def test_device_information_audit_vector_has_no_outer_record_prefix():
    spec = load("autobaba-led-backpack")
    details = spec["protocol_details"]["panel_discovery"]
    expected = bytes.fromhex(details["source_derived_query_hex"])
    encoded = aa55(
        1,
        0x03,
        bytes.fromhex("0a 00 1b 00 04 00 06 00"),
    )
    assert encoded == expected
    assert len(encoded) == 20
    assert int.from_bytes(encoded[4:6], "little") == len(encoded) - 6
    assert int.from_bytes(encoded[-2:], "little") == sum(encoded[:-2]) & 0xFFFF
    assert details["observed_reply"]["frame_bytes"] == 151


def test_brightness_audit_vectors_match_shared_tlv_layout():
    spec = load("autobaba-led-backpack")
    details = spec["protocol_details"]["brightness_write"]
    for sequence, level, key in (
        (2, 6, "set_6_example_hex"),
        (3, 7, "restore_7_example_hex"),
    ):
        assert aa55(sequence, 2, bytes([6, 2, 0, level])) == bytes.fromhex(
            details[key]
        )


def test_loy_ble_framing_is_variant_specific_but_all_subscribe():
    for name in (
        "autobaba-led-backpack",
        "led-space",
        "nyan-bt-image-controller",
    ):
        spec = load(name)
        write = spec["services"][0]["characteristics"][1]
        assert write["uuid"] == "0000fff2-0000-1000-8000-00805f9b34fb"
        expected_prefix = name != "autobaba-led-backpack"
        assert write["framing"]["length_prefix"] is expected_prefix
        assert spec["initialization"][0] == {
            "characteristic": "0000fff1-0000-1000-8000-00805f9b34fb",
            "subscribe": True,
            "notes": spec["initialization"][0]["notes"],
        }
        brightness = write["commands"]["set_brightness"]
        assert "1-15" in brightness["description"]


def test_public_loy_power_capture_has_outer_length_and_inner_checksum():
    inner = aa55(3, 2, bytes.fromhex("04 02 00 01"))
    expected = bytes.fromhex(
        "10 00 aa 55 ff ff 0a 00 03 00 c1 02 04 02 00 01 d4 03"
    )
    assert len(inner).to_bytes(2, "little") + inner == expected
    assert int.from_bytes(expected[:2], "little") == len(expected) - 2 == 16
    assert int.from_bytes(expected[-2:], "little") == sum(expected[2:-2]) & 0xFFFF


def test_led_space_retains_udp_and_ble_length_prefixes():
    spec = load("led-space")
    udp = spec["protocol_details"]["popled_wifi_protocol"]["transport"]["udp"]
    assert "outer u16-LE length prefix" in udp["framing"]
    ble = spec["services"][0]["characteristics"][1]
    assert ble["framing"]["length_prefix"] is True
    assert "AUTOBABA is the separately capture-proven" in ble["notes"]
    assert ble["commands"]["set_brightness"]["verification"] == "reported"
