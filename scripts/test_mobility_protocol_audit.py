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

    prefix = bytes.fromhex("13 88 ff 06 13 88 17 70") + bytes(12)
    for operation, expected in ((0x00, (-2.5, 50, 60)), (0x80, (-25.0, 500, 600))):
        payload = prefix + bytes([operation])
        assert len(payload) == 21
        frame = bytes.fromhex("dd 03 00 15") + payload
        assert frame[24] == operation
        checksum = jbd_checksum(frame[1:])
        frame += checksum.to_bytes(2, "big") + b"\x77"
        assert len(frame) == 4 + frame[3] + 3
        factor = 10 if operation & 0x80 else 1
        current = int.from_bytes(payload[2:4], "big", signed=True) * 0.01 * factor
        remaining = int.from_bytes(payload[4:6], "big") * 0.01 * factor
        design = int.from_bytes(payload[6:8], "big") * 0.01 * factor
        assert (current, remaining, design) == expected

    text = spec("jbd-xiaoxiang-bms-ble")
    assert "4 + length + 3" in text
    assert "excluding DD, A5" in text
    assert "register + status + length + data" in text
    assert "payload_offset: 20, frame_offset: 24" in text
    assert 'type: "int16", endianness: "big", unit: "A"' in text
    assert 'type: "uint16", endianness: "big", unit: "Ah"' in text
    assert "operation_status bit 7 clear: current 10 mA" in text
    assert "set means current 100 mA" in text
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

    frame = bytes.fromhex("34 12 50 fb ff ff ff ff 02 77 f8 39 30 c0 36")
    layout = (
        ("time_to_go", 16),
        ("battery_voltage", 16),
        ("alarm_reason", 16),
        ("aux_input", 16),
        ("aux_input_type", 2),
        ("battery_current", 22),
        ("consumed_ah", 20),
        ("state_of_charge", 10),
    )
    offset = 0
    offsets = {}
    values = {}
    for name, width in layout:
        offsets[name] = offset
        raw = 0
        for position in range(width):
            raw |= ((frame[offset >> 3] >> (offset & 7)) & 1) << position
            offset += 1
        if name in ("battery_voltage", "battery_current"):
            raw -= (1 << width) if raw & (1 << (width - 1)) else 0
        values[name] = raw
    assert offset == 118
    assert offsets["aux_input_type"] == 64
    assert offsets["battery_current"] == 66
    assert offsets["consumed_ah"] == 88
    assert offsets["state_of_charge"] == 108
    assert 66 % 8 and 108 % 8
    assert values["time_to_go"] == 4660
    assert values["battery_voltage"] == -1200
    assert values["alarm_reason"] == 0xFFFF
    assert values["aux_input"] == 0xFFFF
    assert values["aux_input_type"] == 2
    assert round(values["aux_input"] / 100 - 273.15, 2) == 382.20
    assert values["battery_current"] == -123456
    assert values["consumed_ah"] == 12345
    assert values["state_of_charge"] == 876

    def signed_or_unavailable(raw: int, bits: int) -> int | None:
        sentinel = 0x7FFF if bits == 16 else (1 << bits) - 1
        if raw == sentinel:
            return None
        return raw - (1 << bits) if raw & (1 << (bits - 1)) else raw

    assert signed_or_unavailable(0x7FFF, 16) is None
    assert signed_or_unavailable(0x3FFFFF, 22) is None
    assert signed_or_unavailable(0x3FFFFE, 22) == -2
    assert signed_or_unavailable(0xFFFF, 16) == -1
    assert (None if values["consumed_ah"] == 0xFFFFF else -values["consumed_ah"] / 10) == -1234.5
    assert values["state_of_charge"] / 10 == 87.6

    text = spec("victron-instant-readout-ble")
    assert "17-20 byte record" in text
    assert "second counter block" in text
    assert text.count('bit_order: "lsb_first"') == 2
    assert frame.hex(" ") in text
    assert "16-bit SIGNED, 0.01 V" in text
    assert "valid full bitmask, NOT an unavailable sentinel" in text
    assert "Raw 0xFFFF is valid input, not a universal unavailable sentinel" in text
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
    phase4 = bytes(range(56))
    assert phase4[:32] == bytes(range(32))
    assert phase4[32:44] == bytes(range(32, 44))
    assert phase4[44:56] == bytes(range(44, 56))
    assert len(phase4[32:44]) == len(phase4[44:56]) == 12
    assert "bytes 32-43 are the TX nonce for client→XBee" in text
    assert "bytes 44-55 are the RX nonce for XBee→client" in text
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
    def parse_mode03(application: bytes) -> list[bytes]:
        assert application[0] == 0x43
        count = application[1]
        assert len(application) == 2 + 2 * count
        return [application[offset : offset + 2] for offset in range(2, len(application), 2)]

    for count in (0, 1, 2, 4):
        application = bytes([0x43, count]) + bytes(range(2 * count))
        dtcs = parse_mode03(application)
        assert len(dtcs) == count
        assert len(application) == 2 + 2 * count
        if count >= 3:
            assert len(application) > 7
        else:
            assert len(application) <= 7

    example = bytes.fromhex("43 03 01 23 04 56 07 89")
    assert len(example) == 8
    assert parse_mode03(example) == [b"\x01\x23", b"\x04\x56", b"\x07\x89"]
    text = spec("obd2-bluetooth-adapter")
    assert 'expected_response: "43 ??"' in text
    assert 'expected_response: "43 03' not in text
    assert "Separate three-DTC example: 43 03 01 23 04 56 07 89" in text
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
    for raw, expected in ((-100, -1.00), (-2500, -25.00), (-1234, -12.34), (-500, -5.00)):
        wire = raw.to_bytes(2, "little", signed=True)
        assert round(int.from_bytes(wire, "little", signed=True) * 0.01, 2) == expected

    text = spec("euc-wheellog-ble")
    other_brands = text.split("    ninebot_z:", 1)[0]
    king_song = text.split("    king_song:\n", 1)[1].split("    gotway_begode:", 1)[0]
    assert king_song.count('type: "int16"') == 4
    assert "voltage, speed,\n    current and temperature are each signed int16 little-endian" in text
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


# Rideable vehicles and bare motor controllers whose open BLE channel can
# change how the vehicle drives. Each must carry a device.safety_advisory
# (not only a SAFETY paragraph in notes, which no client renders).
RIDEABLE_WITH_OPEN_CONTROL = (
    "euc-wheellog-ble",
    "ninebot-segway-ble",
    "vesc-ble-uart",
    "xiaomi-m365-ble",
)


def test_rideable_open_control_specs_carry_a_safety_advisory():
    import yaml

    for name in RIDEABLE_WITH_OPEN_CONTROL:
        device = yaml.safe_load(spec(name))["device"]
        advisory = device.get("safety_advisory")
        assert advisory, f"{name}: missing device.safety_advisory"
        assert advisory["severity"] in ("warning", "danger"), name
        assert advisory.get("acknowledge_required") is True, name
        assert "stationary" in advisory["detail"], name


def test_m365_register_writes_are_advanced():
    """A T=0x03 register write changes the scooter mid-ride; reads stay plain."""
    import yaml

    data = yaml.safe_load(spec("xiaomi-m365-ble"))
    commands = data["services"][0]["characteristics"][0]["commands"]
    writes = {k: v for k, v in commands.items() if v["value"][4] == 0x03}
    assert "cruise_on" in writes
    for name, command in commands.items():
        if name in writes:
            assert command.get("advanced") is True, name
            assert command.get("advanced_reason"), name
        else:
            assert not command.get("advanced"), name
        frame = bytes(command["value"])
        checksum = (sum(frame[2:-2]) ^ 0xFFFF) & 0xFFFF
        assert frame[-2:] == checksum.to_bytes(2, "little"), name
