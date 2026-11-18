"""Independent standard-library vectors for the 2026-11 mobility protocol audit."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def spec(name: str) -> str:
    return (ROOT / "device-specs" / "devices" / f"{name}.yaml").read_text(
        encoding="utf-8"
    )


def doc(name: str) -> str:
    return (ROOT / "docs" / "devices" / f"{name}.md").read_text(encoding="utf-8")


def jbd_checksum(data: bytes) -> int:
    return (-sum(data)) & 0xFFFF


def test_jbd_request_response_checksum_and_fragment_reassembly():
    for register, expected in ((0x03, 0xFFFD), (0x04, 0xFFFC), (0x05, 0xFFFB)):
        request_data = bytes([register, 0x00])
        assert jbd_checksum(request_data) == expected
        request = bytes([0xDD, 0xA5]) + request_data + expected.to_bytes(2, "big") + b"\x77"
        assert jbd_checksum(request[2:4]) == expected
        assert jbd_checksum(request[1:4]) != expected

    response_data = bytes.fromhex("03 00 02 12 34")
    checksum = jbd_checksum(response_data)
    assert checksum == 0xFFB5
    response = b"\xdd" + response_data + checksum.to_bytes(2, "big") + b"\x77"
    length = response[3]
    assert len(response) == 4 + length + 3
    fragments = (response[:2], response[2:5], response[5:8], response[8:])
    assembled = b"".join(fragments)
    assert assembled == response
    assert assembled[-1] == 0x77
    assert jbd_checksum(assembled[1:-3]) == int.from_bytes(assembled[-3:-1], "big")

    text = spec("jbd-xiaoxiang-bms-ble")
    assert "4 + length + 3" in text
    assert "excluding DD, A5" in text
    assert "register + status + length + data" in text
    assert "Operation-status bit 7 selects 100 mA" in text
    assert "otherwise 10 mA" in text
    assert "service_uuids:" not in text.split("services:", 1)[0]
    assert "Manually select the BMS candidate" in text


def test_bluetti_identity_output_gates_and_serial_scrubbing():
    text = spec("bluetti-power-station")
    page = doc("bluetti-power-station")
    for content in (text, page):
        assert "EP5002142000061564" not in content
        assert "2142000061564" not in content
        assert "EP500<serial>" in content
    assert "service_uuids:" not in text.split("services:", 1)[0]
    assert "Never use FF00 alone" in text
    assert "read-only model/serial confirmation is mandatory" in text
    for alias in ("ac_output_on", "ac_output_off", "dc_output_on", "dc_output_off"):
        block = text.split(f"          {alias}:\n", 1)[1].split("            template:", 1)[0]
        assert "advanced: true" in block
        assert "advanced_reason:" in block


def test_victron_second_ctr_block_and_sentinel_before_sign_rules():
    def counter_blocks(record_length: int) -> int:
        return (record_length + 15) // 16

    assert counter_blocks(16) == 1
    assert counter_blocks(17) == 2
    assert counter_blocks(20) == 2

    def signed_or_unavailable(raw: int, bits: int) -> int | None:
        sentinel = 0x7FFF if bits == 16 else (1 << bits) - 1
        if raw == sentinel:
            return None
        return raw - (1 << bits) if raw & (1 << (bits - 1)) else raw

    assert signed_or_unavailable(0x7FFF, 16) is None
    assert signed_or_unavailable(0x3FFFFF, 22) is None
    assert signed_or_unavailable(0x3FFFFE, 22) == -2
    assert signed_or_unavailable(0xFFFF, 16) == -1

    consumed_raw = 0xFFFFF
    soc_raw = 0x3FF
    consumed = None if consumed_raw == 0xFFFFF else -consumed_raw * 0.1
    soc = None if soc_raw == 0x3FF else soc_raw * 0.1
    assert consumed is None
    assert soc is None

    text = spec("victron-instant-readout-ble")
    assert "17-20 byte record" in text
    assert "second counter block" in text
    assert text.count('bit_order: "lsb_first"') == 2
    assert "22-bit SIGNED" in text
    assert "20-bit UNSIGNED, then negate" in text
    assert "10-bit UNSIGNED" in text
    assert "raw 0x3FFFFF = unavailable before 22-bit sign extension" in text
    assert (
        "https://www.victronenergy.com/upload/documents/"
        "Manual_SmartSolar_MPPT_75-10_up_to_100-20/"
        "29694-MPPT_solar_charger_manual-pdf.pdf"
    ) in text


def test_enphase_password_aes_srp_poll_write_and_relay_directions():
    text = spec("enphase-iqbattery-ble")
    normalized = " ".join(text.lower().split())
    page = doc("enphase-iqbattery-ble")
    assert 'ensemble_provisioning_link_key_verification_and_live_data: "030609"' in text
    assert 'separate_range_test_and_gateway_helpers: "password"' in text
    assert 'value: "030609"' in text
    assert "four-frame SRP-6a" in text
    assert "AES-256-CTR" in text
    assert "32-byte session key" in text
    assert "direction-specific 12-byte nonces" in text
    assert "initial remaining counter value 1" in text.lower()
    assert "Poll requests are [type, 0]" in text
    assert "byte 1 is NOT universally zero" in text
    assert "[01][10][16 key bytes]" in text
    assert "not a demonstrated fallback mesh key" in text.lower()
    assert "separate numeric pan-id write is not established" in normalized
    assert "0x2D User Data Relay remains client-to-device" in text
    assert "0xAD User Data Relay Output remains device-to-client" in text
    assert "`0x2D` User Data Relay (client→device)" in page
    assert "`0xAD`" in page and "device→client" in page


def test_obd_three_dtc_multiframe_and_iso_tp_pending_padding_scope():
    dtc_count = 3
    application = bytes([0x43, dtc_count]) + bytes(2 * dtc_count)
    assert len(application) == 8
    assert len(application) > 7
    assert len(bytes([0x43, 2]) + bytes(4)) == 6
    text = spec("obd2-bluetooth-adapter")
    assert 'requires: ["single_frame", "multiframe_rx"]' in text
    assert "1 + 1 + 6 = 8" in text
    assert "each responding ECU separately" in text

    pending = bytes.fromhex("7f 22 78")
    assert pending[0] == 0x7F
    assert pending[1] == 0x22
    assert pending[2] == 0x78
    iso = spec("iso15765-2-can-transport")
    assert "7F <request-SID> 78" in iso
    assert "wait for the final response" in iso
    assert "follow the ECU's session timing" in iso
    assert "classic CAN normal addressing without an address-extension byte" in iso
    assert "only when padding is enabled" in iso
    assert "permits shorter DLCs" in iso


def test_uds_odd_seed_and_following_even_key():
    for seed in (0x01, 0x03, 0x05):
        assert seed % 2 == 1
        assert seed + 1 in (0x02, 0x04, 0x06)
    text = spec("uds-services-reference")
    assert "Odd subfunction = request seed" in text
    assert "immediately following even subfunction = send key" in text
    assert "01/02, 03/04, 05/06" in text
    assert "even+1 = send key" not in text


def test_openevse_current_conversion_and_resume_retains_override():
    assert 32120 / 1000 == 32.12
    text = spec("openevse")
    assert "Both /status amp and MQTT amp are integer milliamps" in text
    assert "retains the override and does not clear it" in text
    resume = text.split("  resume:\n", 1)[1].split("    verification:", 1)[0]
    assert 'body: \'{"state":"active"}\'' in resume
    assert "clear override)." not in resume
    assert "32120 mA = 32.12 A" in doc("openevse")


def test_concept2_mux_and_ftms_resistance_range_and_scale():
    concept2 = spec("concept2-pm5")
    assert "`xxxx` is the" in concept2
    assert "FIRST payload byte identifies which" in concept2
    assert "last byte identifies which" not in concept2
    assert "FIRST byte" in doc("concept2-pm5")

    raw = 25
    level = raw * 0.1
    assert level == 2.5
    assert round(level * 10) == raw
    ftms = spec("ftms-fitness-machine-service")
    assert 'type: "uint8"\n                scale: 0.1' in ftms
    assert "00002ad6-0000-1000-8000-00805f9b34fb" in ftms
    assert "Supported Resistance Level Range (0x2AD6)" in ftms
    assert "Set target power (op 0x05) — s16 watts" in ftms


def test_vesc_crc16_parameters_and_exact_frame():
    def crc16(data: bytes) -> int:
        crc = 0x0000
        for byte in data:
            crc ^= byte << 8
            for _ in range(8):
                if crc & 0x8000:
                    crc = ((crc << 1) ^ 0x1021) & 0xFFFF
                else:
                    crc = (crc << 1) & 0xFFFF
        return crc

    payload = b"\x04"
    crc = crc16(payload)
    assert crc == 0x4084
    frame = b"\x02" + bytes([len(payload)]) + payload + crc.to_bytes(2, "big") + b"\x03"
    assert frame == bytes.fromhex("02 01 04 40 84 03")
    text = spec("vesc-ble-uart")
    assert "polynomial 0x1021" in text
    assert "CRC = poly 0x1021" in text
    assert "initial value 0x0000" in text
    assert "init 0x0000" in text
    assert "no reflection" in text
    assert "no final XOR" in text


def test_bosch_and_urevo_vendor_internal_labels_are_scrubbed():
    bosch = spec("bosch-ebike-cx-gen4")
    for label in (
        "SimpleTransportMessage",
        "SimpleMessage",
        "DisablerServiceBuiRequest",
        "postLockService",
        "postUnlockService",
        "encryptedPreSharedKey",
    ):
        assert label not in bosch
    assert "message-envelope domain" in bosch
    assert "transport fragments" in bosch

    urevo = spec("urevo-walking-pad") + doc("urevo-walking-pad")
    for label in (
        "BlueDIS",
        "readSupportSpeedRange",
        "readSupportInclinationRange",
        "BluePack",
        "EquipmentFactory",
        "WSEquipment",
        "ResponseFactory",
        "BlueNumExt",
        "UREquipment",
        "onParseData",
        "libapp.so",
        "package:urevo_bluetooth",
        "DeviceConfig",
    ):
        assert label not in urevo
    assert "device-information reader" in urevo
    assert "Frame-A grammar" in urevo



def test_wheellog_other_brand_scales_and_shared_transport():
    for wire, expected in ((bytes.fromhex("00 64"), 3.6), (bytes.fromhex("ff 9c"), -3.6)):
        raw = int.from_bytes(wire, "big", signed=True)
        assert raw in (100, -100)
        assert round(raw * 3.6 / 100, 6) == expected
        assert round(raw * 0.036, 6) == expected

    veteran_speed = int.from_bytes(bytes.fromhex("00 19"), "big", signed=True)
    veteran_current = int.from_bytes(bytes.fromhex("ff e7"), "big", signed=True)
    assert veteran_speed * 0.1 == 2.5
    assert veteran_current * 0.1 == -2.5
    assert round(10080 * 0.01, 2) == 100.80
    assert round(2500 * 0.01, 2) == 25.00

    assert round(6650 * 0.01, 2) == 66.50
    assert round(2500 * 0.01, 2) == 25.00
    assert round(1234 * 0.01, 2) == 12.34
    assert round(2345 * 0.01, 2) == 23.45

    text = spec("euc-wheellog-ble")
    other_brands = text.split("    ninebot_z:", 1)[0]
    assert "raw * 3.6 / 100 = raw * 0.036 km/h" in text
    assert 'scale: 0.036, unit: "km/h"' in text
    assert 'scale: 0.1, unit: "km/h"' in text
    assert 'scale: 0.1, unit: "A"' in text
    assert other_brands.count('scale: 0.01, unit: "V"') == 2
    assert other_brands.count('scale: 0.01, unit: "C"') == 2
    assert "no universal 24S" in text
    assert "km/h=x3.6" not in text
    assert "x10 signed" not in text
    assert "0000ffe0-0000-1000-8000-00805f9b34fb" in text
    assert "0000ffe1-0000-1000-8000-00805f9b34fb" in text
    assert "complete GATT-layout comparison" in text
    assert "Deliberate manual selection" in text
    assert "FFE0/FFE1 alone" in text
    assert "Gotway" in doc("euc-wheellog-ble")
