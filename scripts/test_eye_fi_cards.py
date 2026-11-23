"""Independent Eye-Fi credential and digest transcriptions using the stdlib."""

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


def internet_checksum(block: bytes) -> int:
    assert len(block) % 2 == 0
    total = sum(
        int.from_bytes(block[offset : offset + 2], "big")
        for offset in range(0, len(block), 2)
    )
    while total > 0xFFFF:
        total = (total & 0xFFFF) + (total >> 16)
    return ~total & 0xFFFF


def integrity_digest(tar_bytes: bytes, upload_key: bytes) -> str:
    complete_length = len(tar_bytes) - len(tar_bytes) % 512
    checksums = b"".join(
        internet_checksum(tar_bytes[offset : offset + 512]).to_bytes(2, "big")
        for offset in range(0, complete_length, 512)
    )
    return hashlib.md5(checksums + upload_key).hexdigest()


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


def test_upload_photo_declares_action_ordered_parts_and_digest_format():
    sequence = SPEC["protocol_details"]["receiver"]["sequence"]
    upload = next(item for item in sequence if item["operation"] == "UploadPhoto")
    assert upload["soap_action"] == '"urn:UploadPhoto"'
    assert upload["verification"] == "reported"
    assert upload["multipart_fields"] == [
        "SOAPENVELOPE",
        "FILENAME",
        "INTEGRITYDIGEST",
    ]
    assert upload["multipart_order"] == "required_in_listed_order"
    assert upload["integrity_digest_format"] == "32 lowercase hexadecimal characters"


def test_integrity_digest_matches_synthetic_big_endian_vector():
    details = SPEC["protocol_details"]["resume"]["integrity_digest"]
    vector = details["test_vectors"]["synthetic_512_byte_tar_block"]
    tar_bytes = bytes.fromhex(vector["tar_bytes_hex"])
    upload_key = bytes.fromhex(vector["upload_key"])

    assert details["verification"] == "reported"
    assert details["word_byte_order"] == "big-endian"
    assert details["checksum_byte_order"] == "big-endian"
    assert len(tar_bytes) == 512
    assert len(upload_key) == 16
    assert internet_checksum(tar_bytes).to_bytes(2, "big").hex() == vector[
        "expected_block_checksum_hex"
    ]

    digest = integrity_digest(tar_bytes, upload_key)
    assert digest == vector["expected_integrity_digest"]
    assert len(digest) == 32
    assert set(digest) <= set("0123456789abcdef")
    assert integrity_digest(tar_bytes + b"trailing partial block", upload_key) == digest


def next_request_sequence(previous_rspc: int) -> int:
    assert 0 <= previous_rspc <= 0xFFFFFFFF
    if previous_rspc in (0, 0xFFFFFFFF):
        return 0x1234
    return (previous_rspc + 1) & 0xFFFFFFFF


def test_rspc_reseed_never_wraps_to_zero():
    assert next_request_sequence(0) == 0x1234
    assert next_request_sequence(1) == 2
    assert next_request_sequence(0x1234) == 0x1235
    assert next_request_sequence(0xFFFFFFFE) == 0xFFFFFFFF
    assert next_request_sequence(0xFFFFFFFF) == 0x1234
    assert next_request_sequence(0xFFFFFFFF) != 0

    sequence = SPEC["protocol_details"]["mounted_configuration"]["sequence_encoding"]
    assert "Sequence zero means no request" in sequence
    transaction = SPEC["protocol_details"]["mounted_configuration"]["transaction"]
    assert "0x00000000 or 0xffffffff" in transaction
    assert "use 0x1234" in transaction
    assert "Never wrap 0xffffffff to sequence zero" in transaction

    note_sequence = NOTE["configuration"]["sequence"]
    assert note_sequence["reseed_values"] == [0, 0xFFFFFFFF]
    assert note_sequence["reseed_to"] == 0x1234
    assert note_sequence["never_wrap_to_zero"] is True
    assert note_sequence["zero_means_no_request"] is True


def test_upload_key_recovery_is_limited_to_exact_reported_firmware():
    matrix = SPEC["protocol_details"]["mounted_configuration"][
        "firmware_key_recovery"
    ]
    direct_versions = {
        version
        for version, row in matrix.items()
        if isinstance(row, dict) and row.get("direct_o_0xfd", "").startswith("returns")
    }
    assert direct_versions == {"5.2010", "5.2011", "5.3008"}

    for version in ("5.0018", "5.0019"):
        row = matrix[version]
        assert row["card"] == "X2"
        assert row["direct_o_0xfd"] == "empty"
        assert "ordinary reboot" in row["dump_recovery"]
        assert "existing upload key" in row["dump_recovery"]

    assert matrix["5.3008"]["card"] == "Mobi Pro"
    assert "no dump obtainable" in matrix["5.3008"]["dump_recovery"]
    assert "static-analysis-derived only" in matrix["4.5166"]["dump_recovery"]
    assert "no live crash/dump confirmation" in matrix["4.5166"]["dump_recovery"]
    assert "no live 4.x card tested" in matrix["4.5166"]["card"]

    current = matrix["5.0020"]
    assert current["direct_o_0xfd"] == "lowercase o 0xfd returns no upload key/read"
    assert current["write_O_0xfd"] == "uppercase O 0xfd is rejected"
    assert current["generic_set_token"] is False
    assert "not established" in current["offline_activation"]
    assert "SetToken" in current["offline_activation"]
    assert current["dump_recovery"] == "not established"


def test_structured_note_firmware_and_mailbox_boundaries_match_spec():
    configuration = NOTE["configuration"]
    matrix = configuration["firmware_key_recovery"]
    assert matrix["x2_5_0018"]["direct_o_0xfd"] == "empty"
    assert matrix["x2_5_0019"]["direct_o_0xfd"] == "empty"
    assert matrix["x2_5_2010"]["direct_o_0xfd"] == "returns_existing_key"
    assert matrix["x2_5_2011"]["direct_o_0xfd"] == "returns_existing_key"
    assert matrix["mobi_pro_5_3008"]["direct_o_0xfd"] == "returns_existing_key"
    assert "static_analysis_only" in matrix["firmware_4_5166"]["dump_recovery"]
    assert matrix["firmware_5_0020"]["direct_o_0xfd"] == "no_lowercase_key_read"
    assert matrix["firmware_5_0020"]["write_O_0xfd"] == "uppercase_rejected"
    assert matrix["firmware_5_0020"]["generic_set_token"] is False
    assert matrix["firmware_5_0020"]["offline_activation"] == "not_established"

    mailbox = configuration["mailbox_recreation"]
    assert mailbox["creates_upload_key"] is False
    assert mailbox["activates_reset_card"] is False
    assert mailbox["effect"] == "restores_channel_to_recover_existing_key"
    spec_mailbox = SPEC["protocol_details"]["mounted_configuration"][
        "mailbox_recreation"
    ]
    assert "already exists" in spec_mailbox["effect"]
    assert "Does not create or assign an upload key" in spec_mailbox["does_not"]
    assert "activate a reset card" in spec_mailbox["does_not"]

    for relative in ("research-notes/eye-fi-cards.md", "docs/devices/eye-fi-cards.md"):
        page = (ROOT / relative).read_text(encoding="utf-8")
        assert "5.0020" in page
        assert "SetToken" in page
        assert "0xffffffff" in page
        assert "0x1234" in page
        assert "existing" in page
        assert "RamSet/eyefi-recovery" in page
