"""Check iLEDColor packet checksums and advertised-geometry offsets."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC = yaml.safe_load(
    (ROOT / "device-specs" / "devices" / "iledcolor-led-panel.yaml").read_text(
        encoding="utf-8"
    )
)


def _commands():
    service = SPEC["services"][0]
    characteristic = service["characteristics"][0]
    return characteristic["commands"]


def _assert_big_endian_sum(packet: list[int]) -> None:
    assert sum(packet[:-2]) & 0xFFFF == (packet[-2] << 8) | packet[-1]


def test_fixed_command_checksums():
    commands = _commands()
    for name in ("connect", "test_pass_default", "end_stream"):
        command = commands[name]
        assert command["verification"] == "confirmed"
        _assert_big_endian_sum(command["value"])

    assert commands["connect"]["value"] == list(
        bytes.fromhex("54 0d 00 03 00 00 64")
    )
    assert commands["end_stream"]["value"] == list(
        bytes.fromhex("54 01 00 03 01 00 59")
    )


def test_advertised_geometry_offsets():
    feature = SPEC["features"][0]
    advertisement = feature["resolution_advertisement"]
    manufacturer_value = bytes.fromhex(
        "42 44 02 00 40 00 20 03 00 00 0d 00 3d 00 44 00 00 00"
    )

    width = int.from_bytes(
        manufacturer_value[
            advertisement["width_offset"] : advertisement["width_offset"] + 2
        ],
        "big",
    )
    height = int.from_bytes(
        manufacturer_value[
            advertisement["height_offset"] : advertisement["height_offset"] + 2
        ],
        "big",
    )
    assert (width, height) == (32, 64)
    assert advertisement["company_id"] == 0x5401
    assert feature["resolution_source"] == "device_reported"
    assert feature["animation"] is True


def test_vendor_native_animation_uses_raw_rgb_frames():
    upload = SPEC["protocol_details"]["live_upload"]
    native = upload["native_animation_example"]
    assert native["item_type"] == 2
    assert native["frames"] == 3
    assert native["pixel_format"] == "RGB row-major, 3 bytes per pixel"
    assert native["duration_bytes_per_frame"] == 2
    assert native["item_data_bytes"] == 18480
    assert native["stream_bytes"] == 18504
    assert native["chunks"] == 38
    assert native["chunk_payload_bytes"] == 492
    assert "restored the old program" in upload["legacy_acknowledged_gif_example"][
        "caveat"
    ]


def test_guide_default_password_checksum_matches_spec():
    packet = _commands()["test_pass_default"]["value"]
    _assert_big_endian_sum(packet)
    guide = (ROOT / "docs" / "devices" / "iledcolor-led-panel.md").read_text(
        encoding="utf-8"
    )
    expected = " ".join(f"{byte:02x}" for byte in packet)
    assert expected in guide
    assert "54 0f 00 08 00 00 00 00 00 00 00 6f" not in guide
