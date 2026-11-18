"""Independent synthetic vectors for the bounded VanMoof S3/X3 legacy profile."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC = yaml.safe_load(
    (ROOT / "device-specs/devices/vanmoof-s3-x3.yaml").read_text(encoding="utf-8")
)
DETAILS = SPEC["protocol_details"]["legacy_sx3_crypto"]
VECTORS = DETAILS["test_vectors"]
KEY = bytes.fromhex(VECTORS["owner_key_hex"])
OPENSSL = shutil.which("openssl")


def aes_ecb(data: bytes, *, decrypt: bool = False) -> bytes:
    assert OPENSSL, "OpenSSL is required by the spec's named AES equivalent"
    assert len(data) % 16 == 0
    command = [OPENSSL, "enc", "-aes-128-ecb", "-nopad", "-K", KEY.hex()]
    if decrypt:
        command.append("-d")
    result = subprocess.run(command, input=data, capture_output=True, check=False)
    if result.returncode:
        raise ValueError("AES-128-ECB operation failed")
    return result.stdout


def authentication_payload(challenge: bytes, user_key_id: int) -> bytes:
    if len(challenge) != 2:
        raise ValueError("challenge must be exactly two bytes")
    if not 0 <= user_key_id <= 0xFF:
        raise ValueError("user key ID must fit one byte")
    return aes_ecb(challenge + bytes(14)) + bytes((0, 0, 0, user_key_id))


def command_payload(challenge: bytes, command_data: bytes) -> bytes:
    if len(challenge) != 2:
        raise ValueError("challenge must be exactly two bytes")
    plaintext = challenge + command_data
    plaintext += bytes(-len(plaintext) % 16)
    return aes_ecb(plaintext)


def decrypted_plaintext(ciphertext: bytes) -> bytes:
    if not ciphertext or len(ciphertext) % 16:
        raise ValueError("protected reads contain nonempty whole AES blocks")
    return aes_ecb(ciphertext, decrypt=True)


def test_nist_aes_128_vector() -> None:
    vector = VECTORS["nist_aes_128"]
    assert aes_ecb(bytes.fromhex(vector["plaintext_hex"])).hex() == vector["ciphertext_hex"]


def test_authentication_vector_and_clear_suffix() -> None:
    vector = VECTORS["authentication"]
    payload = authentication_payload(
        bytes.fromhex(vector["challenge_hex"]), vector["user_key_id"]
    )
    assert len(payload) == 20
    assert payload[:16].hex() == vector["ciphertext_hex"]
    assert payload.hex() == vector["payload_hex"]
    assert payload[16:] == bytes((0, 0, 0, 42))
    assert decrypted_plaintext(payload[:16]).hex() == vector["plaintext_hex"]


def test_lock_and_bell_commands_use_fresh_challenge_zero_padding() -> None:
    for name in ("lock_command", "bell_command"):
        vector = VECTORS[name]
        payload = command_payload(
            bytes.fromhex(vector["challenge_hex"]),
            bytes.fromhex(vector["command_data_hex"]),
        )
        assert payload.hex() == vector["ciphertext_hex"]
        assert decrypted_plaintext(payload).hex() == vector["plaintext_hex"]


def test_zero_padding_never_adds_an_aligned_extra_block() -> None:
    assert len(command_payload(b"\x01\x02", bytes(14))) == 16
    assert len(command_payload(b"\x01\x02", bytes(15))) == 32
    assert len(command_payload(b"\x01\x02", bytes(30))) == 32
    assert len(command_payload(b"\x01\x02", bytes(31))) == 48


@pytest.mark.parametrize("challenge", [b"", b"\x00", b"\x00\x00\x00"])
def test_authentication_and_commands_reject_bad_challenge_lengths(challenge: bytes) -> None:
    with pytest.raises(ValueError, match="exactly two bytes"):
        authentication_payload(challenge, 42)
    with pytest.raises(ValueError, match="exactly two bytes"):
        command_payload(challenge, b"\x01")


@pytest.mark.parametrize("user_key_id", [-1, 256])
def test_authentication_rejects_out_of_range_user_key_id(user_key_id: int) -> None:
    with pytest.raises(ValueError, match="one byte"):
        authentication_payload(b"\x01\x02", user_key_id)


def test_encrypted_telemetry_vectors_decode_only_the_declared_fields() -> None:
    expected = {row["name"]: row for row in VECTORS["decrypted_reads"]}
    plaintexts = {
        name: decrypted_plaintext(bytes.fromhex(row["ciphertext_hex"]))
        for name, row in expected.items()
    }
    for name, plaintext in plaintexts.items():
        assert plaintext.hex() == expected[name]["plaintext_hex"]
    assert plaintexts["motor_battery"][0] == 99
    assert plaintexts["module_battery"][0] == 98
    assert int.from_bytes(plaintexts["distance"][:4], "little") == 1234
    assert int.from_bytes(plaintexts["distance"][:4], "little") * 0.1 == pytest.approx(123.4)
    assert plaintexts["speed"][0] == 25
    assert plaintexts["lock_state"][0] == 2


@pytest.mark.parametrize("ciphertext", [b"", b"\x00", bytes(15), bytes(17)])
def test_short_or_unaligned_protected_reads_are_rejected(ciphertext: bytes) -> None:
    with pytest.raises(ValueError, match="whole AES blocks"):
        decrypted_plaintext(ciphertext)


def test_scope_is_s3_x3_and_only_bounded_commands_exist() -> None:
    assert SPEC["device"]["integration"] == "identify_only"
    assert SPEC["device"]["testing"]["status"] == "untested"
    assert {v["model"] for v in SPEC["device"]["variants"]} == {"S3", "X3"}
    assert SPEC["device"]["identification"]["service_uuids"] == [
        "6acc5500-e631-4069-944d-b8ca7598ad50"
    ]
    services = {service["uuid"]: service for service in SPEC["services"]}
    assert set(services) == {
        "6acc5500-e631-4069-944d-b8ca7598ad50",
        "6acc5520-e631-4069-944d-b8ca7598ad50",
        "6acc5530-e631-4069-944d-b8ca7598ad50",
        "6acc5540-e631-4069-944d-b8ca7598ad50",
        "6acc5570-e631-4069-944d-b8ca7598ad50",
    }
    commands = {
        name: command
        for service in services.values()
        for characteristic in service["characteristics"]
        for name, command in (characteristic.get("commands") or {}).items()
    }
    assert set(commands) == {"unlock", "lock", "set_bell_tone"}
    for command in commands.values():
        assert command["advanced"] is True
        reason = command["advanced_reason"].lower()
        assert "owner" in reason
        assert "readback" in reason
        assert command["verification"] == "reported"
    assert commands["unlock"]["value"] == [0]
    assert commands["lock"]["value"] == [1]
    tone = commands["set_bell_tone"]["parameters"]["tone"]
    assert (tone["min"], tone["max"]) == (22, 24)


def test_formats_carry_the_bounded_numeric_semantics() -> None:
    fields = {
        field["name"]: field
        for service in SPEC["services"]
        for characteristic in service["characteristics"]
        for field in characteristic.get("format") or []
    }
    assert fields["distance"]["endianness"] == "little"
    assert fields["distance"]["scale"] == 0.1
    assert fields["distance"]["unit"] == "km"
    assert fields["speed"]["type"] == "uint8"
    assert fields["speed"]["unit"] == "km/h"
    for name in ("motor_battery", "module_battery"):
        assert fields[name]["unit"] == "%"
        assert fields[name]["type"] == "uint8"
    assert fields["lock_state"]["values"] == {
        0: "unlocked",
        1: "locked",
        2: "awaiting_unlock",
    }
