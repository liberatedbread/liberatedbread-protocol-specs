"""Check the gitamini spec's documented command/chunk framing."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC = yaml.safe_load(
    (ROOT / "device-specs" / "devices" / "piaggio-gita-mini.yaml").read_text(
        encoding="utf-8"
    )
)


def _commands():
    return SPEC["services"][0]["characteristics"][1]["commands"]


def _no_data(opcode: int) -> list[int]:
    return [opcode, 0x7F, 0, 0, 0, 0, 0, 0, 0, 0]


def _chunks(ciphertext: bytes) -> list[bytes]:
    chunks = []
    for offset in range(0, len(ciphertext), 181):
        part = ciphertext[offset : offset + 181]
        final = int(offset + 181 >= len(ciphertext))
        chunks.append(part + bytes([final]))
    return chunks


def test_no_data_command_frames():
    commands = _commands()
    expected = {
        "get_ap_list": 50,
        "get_ip_address": 53,
        "get_gita_version": 81,
        "get_gita_uptime": 86,
        "get_ota_status": 90,
        "lock_latch": 78,
        "unlock_latch": 79,
        "update_gita": 80,
        "download_new_software": 85,
    }
    for name, opcode in expected.items():
        assert commands[name]["value"] == _no_data(opcode)
        assert len(commands[name]["value"]) == 10


def test_wifi_join_payload_is_inside_encrypted_frame():
    command = _commands()["set_wifi_connection"]
    assert command["template"][:2] == [0x33, 0x7F]
    assert command["template"][2] == "{ssid_and_password}"
    assert command["advanced"] is True
    assert command["parameters"]["ssid_and_password"]["type"] == "string"


def test_chunk_boundaries_and_final_markers():
    chunks = _chunks(bytes(range(200)) * 2)
    assert [len(chunk) for chunk in chunks] == [182, 182, 39]
    assert [chunk[-1] for chunk in chunks] == [0, 0, 1]
    assert b"".join(chunk[:-1] for chunk in chunks) == bytes(range(200)) * 2


def test_model_ids_and_gatt_map():
    device = SPEC["device"]
    assert device["identification"]["manufacturer_data"]["company_id"] == 2107
    assert device["identification"]["service_uuids"] == [
        "00009999-0000-1000-8000-00805f9b34fb"
    ]
    variants = {variant["model"]: variant for variant in device["variants"]}
    assert "model 2" in variants["gitamini"]["identification"]["manufacturer_data"][
        "description"
    ]
    assert "model 3" in variants["gita pro"]["identification"]["manufacturer_data"][
        "description"
    ]

    service = SPEC["services"][0]
    assert service["uuid"] == "87654321-1234-5678-1234-56789abcdef0"
    assert len(service["characteristics"]) == 11
    assert service["characteristics"][1]["role"] == "command"


def test_unknown_payload_opcodes_are_not_made_executable():
    commands = _commands()
    assert "connect_hidden_wifi" not in commands
    assert "connect_wifi" not in commands
    assert "activate_gita" not in commands
    assert "disable_ssh" not in commands


def test_session_initialization_orders_dependencies_before_auth():
    feedback = "87654321-1234-5678-1234-56789abcdef9"
    session_auth = "87654321-1234-5678-1234-56789abcdef1"
    session_key_exchange = "87654321-1234-5678-1234-56789abcdefb"
    initialization = SPEC["initialization"]
    positions = {
        item["characteristic"]: index for index, item in enumerate(initialization)
    }
    for auth in (session_auth, session_key_exchange):
        assert positions[feedback] < positions[auth]
    assert positions[session_key_exchange] < positions[session_auth]

    for method in SPEC["device"]["setup"]["methods"]:
        actions = [step["action"] for step in method["steps"]]
        subscribed = next(
            index for index, action in enumerate(actions) if "Subscribe" in action
        )
        for index, action in enumerate(actions):
            if index <= subscribed:
                continue
            if any(
                f"command {opcode}" in action
                for opcode in (8, 9, 60, 61, 62, 63, 68)
            ):
                assert subscribed < index, action


def test_saved_session_wire_exchange_and_success_gate():
    auth = SPEC["protocol_details"]["session_authentication"]
    existing = auth["verify_existing"]
    assert existing["request"]["plaintext"] == "[0x3f][0x7f][user_id_utf8][n1_ascii]"
    assert "ECDH" in existing["request"]["encryption"]
    assert existing["success_response"]["type"] == 109
    assert existing["success_response"]["inner_plaintext"] == (
        "[n1_ascii][.][n2_ascii]"
    )
    assert "saved cloud-issued credential" in existing["authenticate"]["encryption"]
    assert existing["authenticate"]["plaintext"] == "[0x09][0x7f][n2_ascii]"
    assert existing["failure_and_completion"]["expired_type"] == 110
    assert existing["failure_and_completion"]["invalid_type"] == 111
    assert existing["failure_and_completion"]["timeout_seconds"] == 8
    assert "no dedicated success reply" in existing["failure_and_completion"][
        "notes"
    ]
    assert "version read" in existing["failure_and_completion"]["notes"]

    fresh = auth["request_fresh"]
    assert fresh["request"]["opcode"] == 62
    assert fresh["request"]["plaintext"] == "[0x3e][0x7f][user_id_utf8][n1_ascii]"
    assert fresh["robot_reply"]["plaintext"] == (
        "[payloadKey][.][n2_ascii][.][payload]"
    )
