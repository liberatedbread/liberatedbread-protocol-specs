"""Independent Eye-Fi credential-vector transcription using only the stdlib."""

import hashlib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
NOTE = yaml.safe_load(
    (ROOT / "research-notes" / "eye-fi-cards.yaml").read_text(encoding="utf-8")
)
SPEC = yaml.safe_load(
    (ROOT / "device-specs" / "devices" / "eye-fi-cards.yaml").read_text(
        encoding="utf-8"
    )
)


def credential(*hex_parts: str) -> str:
    joined = "".join(hex_parts)
    assert len(joined) % 2 == 0
    return hashlib.md5(bytes.fromhex(joined)).hexdigest()


def assert_vectors(vectors):
    mac = vectors["mac"]
    key = vectors["x2_upload_key"]
    zero = vectors["mobi_zero_key"]

    assert credential(mac, vectors["cnonce"], key) == vectors[
        "x2_start_session_credential"
    ]
    assert credential(mac, key, vectors["snonce"]) == vectors[
        "x2_photo_status_credential"
    ]
    assert credential(mac, vectors["cnonce"], zero) == vectors[
        "mobi_start_session_credential"
    ]
    assert credential(mac, zero, vectors["snonce"]) == vectors[
        "mobi_photo_status_credential"
    ]


def test_eye_fi_credentials_match_synthetic_vectors():
    assert_vectors(NOTE["credentials"]["test_vectors"])


def test_device_spec_carries_the_same_implementable_vectors():
    assert_vectors(SPEC["protocol_details"]["credentials"]["test_vectors"])


def test_eye_fi_vectors_use_documentation_identity_and_16_byte_keys():
    vectors = NOTE["credentials"]["test_vectors"]
    assert vectors["mac"] == "00005e005301"
    assert len(bytes.fromhex(vectors["x2_upload_key"])) == 16
    assert len(bytes.fromhex(vectors["mobi_zero_key"])) == 16
    assert set(vectors["mobi_zero_key"]) == {"0"}


def test_receiver_direction_and_safe_local_profile_are_explicit():
    receiver = SPEC["protocol_details"]["receiver"]
    assert receiver["direction"] == "card_initiates_upload_to_host"
    assert receiver["listen_port"] == 59278
    assert SPEC["device"]["integration"] == "identify_only"
    assert SPEC["device"]["setup"]["methods"][-1]["role"] == "historical"
    assert SPEC["protocol_details"]["archive_policy"]["validate_before_extract"]
