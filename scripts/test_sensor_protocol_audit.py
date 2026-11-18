"""Independent standard-library vectors for the 2026-11 sensor protocol audit."""

from __future__ import annotations

import hashlib
import math
import struct
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def spec(name: str) -> str:
    return (ROOT / "device-specs" / "devices" / f"{name}.yaml").read_text(
        encoding="utf-8"
    )


def doc(name: str) -> str:
    return (ROOT / "docs" / "devices" / f"{name}.md").read_text(encoding="utf-8")


def test_aranet_radiation_length_offsets_and_vector():
    frame = bytes.fromhex(
        "02 20 00 01 00 00 00 00 10 27 00 00 20 4e 00 00 2c 01 00 5a 01 3c 00 05 00 07"
    )
    assert len(frame) == 26
    assert frame[0] == 2
    assert int.from_bytes(frame[8:12], "little") == 10000
    assert int.from_bytes(frame[12:16], "little") == 20000
    assert int.from_bytes(frame[16:18], "little") * 10 == 3000
    text = spec("aranet4")
    assert "26-byte Aranet Radiation" in text
    assert "dose_total" in text and "dose_duration" in text and "dose_rate" in text
    assert "24-byte family payloads are Aranet2/Radon" in text
    assert frame.hex(" ") in text


def test_sensorpush_revision_temperature_and_generation_boundaries():
    revision = bytes.fromhex("00 01 02 03 04 05 06")
    display = (
        f"{revision[0]:03d}_{revision[1]:03d}.{revision[2]:03d}_"
        f"{revision[3]:03d}.{revision[4]:03d}_{revision[5]:03d}.{revision[6]:03d}"
    )
    assert display == "000_001.002_003.004_005.006"
    assert revision[0] == 0
    assert struct.unpack("<i", bytes.fromhex("b2 07 00 00"))[0] / 100 == 19.70
    text = spec("sensorpush-ht1-htpxw")
    assert "encoding: uint8[7]" in text
    assert "encoding: ascii" not in text
    assert "byte 0 = model ID (0 = HTP.xw)" in text
    assert text.count("V2 vendor API marks this slot RESERVED") == 4
    assert "two int16 LE values" in text
    assert "HT1 trigger is 01 00 01 00" in text
    assert "V2 accepts any 32-bit trigger" in text
    assert "res/raw/definitions.json" not in text
    assert "no universal HTP.xw decoder is asserted" in text


def test_ruuvi_df3_official_vector_and_sign_magnitude_temperature():
    frame = bytes.fromhex("03 29 1a 1e ce 1e fc 18 f9 42 02 ca 0b 53")
    assert len(frame) == 14
    temperature = (-1 if frame[2] & 0x80 else 1) * (
        (frame[2] & 0x7F) + frame[3] / 100
    )
    assert math.isclose(temperature, 26.30)
    assert frame[1] * 0.5 == 20.5
    assert int.from_bytes(frame[4:6], "big") + 50000 == 102766
    assert struct.unpack(">hhh", frame[6:12]) == (-1000, -1726, 714)
    assert int.from_bytes(frame[12:14], "big") == 2899
    signed = bytes.fromhex("81 45")
    negative = (-1 if signed[0] & 0x80 else 1) * (
        (signed[0] & 0x7F) + signed[1] / 100
    )
    assert math.isclose(negative, -1.69)
    text = spec("ruuvitag-ble")
    assert frame.hex(" ") in text
    assert "Not int16" in text
    assert "Raw 0xFFFF is a valid pressure here" in text


def test_ruuvi_df5_power_vector_and_unavailable_sentinels():
    power = 0xAC36
    battery_raw = power >> 5
    tx_raw = power & 0x1F
    assert battery_raw + 1600 == 2977
    assert -40 + 2 * tx_raw == 4

    def battery(raw: int) -> int | None:
        return None if raw == 0x7FF else raw + 1600

    def tx_power(raw: int) -> int | None:
        return None if raw == 0x1F else -40 + 2 * raw

    assert battery(0x7FF) is None
    assert tx_power(0x1F) is None
    assert battery(battery_raw) == 2977
    assert tx_power(tx_raw) == 4
    text = spec("ruuvitag-ble")
    assert "battery raw 0x7FF" in text
    assert "TX raw 0x1F" in text
    assert "FF FF FF FF FF FF means unavailable" in text


def test_b_parasite_default_bthome_objects_and_vector():
    frame = bytes.fromhex("40 01 5c 02 4d 09 05 13 8a 14 0c b8 0b 2e 23 2f 2a")
    widths = {0x01: 1, 0x02: 2, 0x05: 3, 0x0C: 2, 0x2E: 1, 0x2F: 1}
    objects = {}
    offset = 1
    while offset < len(frame):
        object_id = frame[offset]
        offset += 1
        width = widths[object_id]
        objects[object_id] = int.from_bytes(
            frame[offset : offset + width], "little", signed=object_id == 0x02
        )
        offset += width
    assert offset == len(frame)
    assert objects[0x01] == 92
    assert objects[0x02] / 100 == 23.81
    assert objects[0x05] / 100 == 13460.67
    assert objects[0x0C] / 1000 == 3.000
    assert objects[0x2E] == 35
    assert objects[0x2F] == 42
    text = spec("b-parasite-ble")
    assert 'name: "Battery"' in text
    assert 'name: "Illuminance"' in text
    assert "moisture object 0x2F" in text
    assert "humidity object 0x2E" in text
    reference = spec("bthome-v2")
    assert "0x2E humidity u8 1 %" in reference
    assert "0x2F moisture u8 1 %" in reference
    assert "0x03 humidity u16" in reference
    assert "0x14 moisture u16" in reference


def test_tuya_ble_v3_dp_signed_values_and_session_kdf():
    frame = bytes.fromhex("05 02 04 ff ff ff f6 03 02 04 00 00 00 32")
    values = []
    offset = 0
    while offset < len(frame):
        dp_id, dp_type, length = frame[offset : offset + 3]
        offset += 3
        payload = frame[offset : offset + length]
        assert len(payload) == length
        offset += length
        if dp_type in (0x02, 0x04):
            values.append((dp_id, int.from_bytes(payload, "big", signed=True)))
    assert values == [(5, -10), (3, 50)]
    assert values[0][1] / 10 == -1.0

    secret = b"123456"
    device_random = bytes.fromhex("01 02 03 04 05 06")
    login = hashlib.md5(secret, usedforsecurity=False).hexdigest()  # noqa: S324
    session = hashlib.md5(  # noqa: S324 - Tuya BLE v3 specifies MD5
        secret + device_random, usedforsecurity=False
    ).hexdigest()
    assert login == "e10adc3949ba59abbe56e057f20f883e"
    assert session == "b81578f4898234da5011f41415afdc3b"
    text = spec("tuya-bt-soil-tester")
    assert "[dp id u8][type u8][length u8][payload, exactly length bytes]" in text
    assert "signed four-byte big-endian" in text
    assert "UUID is NOT a session-key input" in text
    assert "UUID is not a session-key input" in doc("tuya-bt-soil-tester")
    assert "DP_V4 is not covered" in text


def test_zigbee_two_byte_dp_length_and_new_soil3_fingerprints():
    frame = bytes.fromhex("05 02 00 04 00 00 00 fa")
    assert frame[0] == 5 and frame[1] == 2
    length = int.from_bytes(frame[2:4], "big")
    payload = frame[4:]
    assert length == len(payload) == 4
    assert int.from_bytes(payload, "big") / 10 == 25.0
    text = spec("zigbee-soil-tester")
    page = doc("zigbee-soil-tester")
    assert "[dpid u8][type u8][length u16" in text
    for fingerprint in (
        "_TZE2841000000_nhgdf6qr",
        "_TZE284_ap9owrsa",
        "_TZE284_33bwcga2",
        "_TZE284_wckqztdq",
        "_TZE284_tgrzpqf4",
        "_TZE2841000000_tgrzpqf4",
    ):
        assert fingerprint in text
        assert fingerprint in page
    assert "only on _TZE284_3urschql" in text


def test_mopeka_ten_byte_layout_formulas_and_vector():
    frame = bytes.fromhex("03 50 28 e8 c3 00 00 00 00 00")
    assert len(frame) == 10
    assert frame[0] in (0x03, 0x06, 0x08, 0x0C)
    voltage = (frame[1] & 0x7F) / 32
    percent = int(max(0, min(100, (voltage - 2.2) / 0.65 * 100)))
    raw_t = frame[2] & 0x7F
    temperature = raw_t - 40
    raw_level = frame[3] | ((frame[4] & 0x3F) << 8)
    quality = frame[4] >> 6
    distance = int(
        raw_level * (0.573045 - 0.002822 * raw_t - 0.00000535 * raw_t**2)
    )
    assert voltage == 2.5
    assert percent == 46
    assert temperature == 0
    assert raw_level == 1000
    assert quality == 3
    assert distance == 451
    assert frame[5:] == bytes(5)
    text = spec("mopeka-pro-check-ble")
    assert "Bytes 5-9 are not decoded" in text
    assert "Reading Quality" in text
    assert "company_id: 89" not in text
    discovery = text.split("  discovery:\n", 1)[1].split("  setup:", 1)[0]
    assert "none: >" in discovery
    assert "methods:" not in discovery
    assert "shared Nordic company ID" in discovery
    assert "0x0059 alone must never select this spec" in discovery


def test_miflora_success_ack_and_two_step_destructive_clear():
    text = spec("xiaomi-miflora")
    start = text.index("          history_clear:")
    end = text.index("            verification:", start)
    clear = text[start:end]
    assert "value:" not in clear
    assert "advanced: true" in clear
    assert 'ordered_writes: ["a0 00 00", "a2 00 00"]' in text
    assert 'ordered_commands: ["history_read_init", "history_sync_success"]' in text
    assert "failure_acknowledgement: \"a3 00 00\"" in text
    assert "clear history (CONFIRMED)" not in text
    sync_start = text.index("          history_sync_success:")
    sync_end = text.index("          history_read_fail:", sync_start)
    sync = text[sync_start:sync_end]
    assert "advanced: true" in sync
    assert "irreversibly deletes stored history" in sync
    assert "Use history_read_fail (a3 00 00) instead when synchronization failed" in sync


def test_pvvx_custom_widths_and_vector_without_losing_newer_firmware_facts():
    frame = bytes.fromhex("00 00 5e 00 53 00 ce 08 94 13 b8 0b 64 2a")
    assert len(frame) == 14
    assert int.from_bytes(frame[6:8], "little", signed=True) / 100 == 22.54
    assert int.from_bytes(frame[8:10], "little") / 100 == 50.12
    assert int.from_bytes(frame[10:12], "little") == 3000
    assert frame[12] == 100
    assert frame[13] == 42
    assert len(frame + b"\x00") == 15
    text = spec("xiaomi-lywsd03mmc")
    assert "14-15 B" in text
    assert "13-14 B" not in text
    assert "14 bytes without trigger/status" in text
    assert "release 5.9" in text
    assert "Telink Flasher" in text
    assert "12 bytes for MiBeacon v2/v3" in text


def test_tuya_soil_protocol_specific_gatt_and_sgs01b_boundary():
    document = yaml.safe_load(spec("tuya-bt-soil-tester"))
    assert document["device"]["integration"] == "identify_only"
    assert document["device"]["testing"]["status"] == "untested"
    services = {service["uuid"]: service for service in document["services"]}
    assert set(services) == {
        "00001910-0000-1000-8000-00805f9b34fb",
        "0000fd50-0000-1000-8000-00805f9b34fb",
    }

    def characteristic_ids(service):
        return {item["uuid"] for item in service["characteristics"]}

    legacy = services["00001910-0000-1000-8000-00805f9b34fb"]
    current = services["0000fd50-0000-1000-8000-00805f9b34fb"]
    assert characteristic_ids(legacy) == {
        "00002b11-0000-1000-8000-00805f9b34fb",
        "00002b10-0000-1000-8000-00805f9b34fb",
    }
    assert characteristic_ids(current) == {
        "00000001-0000-1001-8001-00805f9b07d0",
        "00000002-0000-1001-8001-00805f9b07d0",
    }
    for characteristic in current["characteristics"]:
        assert "commands" not in characteristic

    discovery = document["device"]["discovery"]["methods"][0]["ble"]
    assert discovery["service_data"] == [
        "0000a201-0000-1000-8000-00805f9b34fb"
    ]
    assert discovery["manufacturer_data"]["company_id"] == 0x07D0
    assert "service_uuids" not in discovery
    assert "service_uuids" not in document["device"]["identification"]

    mappings = document["protocol_details"]["tuya_ble_protocol"]["gatt"]
    assert mappings["protocol_le_3"] == {
        "service": "0x1910",
        "write_characteristic": "0x2B11",
        "notify_characteristic": "0x2B10",
    }
    assert mappings["protocol_4"] == {
        "service": "0xFD50",
        "write_characteristic": "00000001-0000-1001-8001-00805f9b07d0",
        "notify_characteristic": "00000002-0000-1001-8001-00805f9b07d0",
    }
    ota_notes = document["features"][0]["dfu"]["enter"]["notes"]
    assert "0x2B11 within service 0x1910" in ota_notes
    assert "00000001-0000-1001-8001-00805f9b07d0" in ota_notes
    assert "exact OTA exchange is not established" in " ".join(ota_notes.split())

    variants = {
        variant["identification"]["product_id"]: variant
        for variant in document["device"]["variants"]
        if "identification" in variant
    }
    sgs01b = variants["gpkyrocn"]
    sgs01b_notes = " ".join(sgs01b["notes"].split())
    assert "BTU" in sgs01b_notes
    assert "TLSR8250" in sgs01b_notes
    assert "V1.1Pre2 development image" in sgs01b_notes
    assert "not a production-ready release" in sgs01b_notes
    assert "per-model reported boundary" in sgs01b_notes
    assert "NOT support" not in sgs01b["notes"]

    page = doc("tuya-bt-soil-tester")
    assert "`gpkyrocn`" in page
    assert "Tuya BTU" in page
    assert "V1.1Pre2 development image" in page
    assert "not production-ready" in page
    assert "it does NOT support the 2026 SGS01B" not in page
    for uuid in (
        "00001910-0000-1000-8000-00805f9b34fb",
        "00002b11-0000-1000-8000-00805f9b34fb",
        "00002b10-0000-1000-8000-00805f9b34fb",
        "0000fd50-0000-1000-8000-00805f9b34fb",
        "00000001-0000-1001-8001-00805f9b07d0",
        "00000002-0000-1001-8001-00805f9b07d0",
    ):
        assert uuid in page
