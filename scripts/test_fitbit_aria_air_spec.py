# Copyright 2026 Pigs Can Fly Labs LLC
# SPDX-License-Identifier: Apache-2.0
"""Independent vectors and honesty checks for the Fitbit Aria Air (FB203) spec.

`device-specs/devices/fitbit-aria-air.yaml` says a weigh-in is a 19-byte
indication laid out nonce | tag | ciphertext, sealed with AES-128-CCM, whose
3-byte plaintext is a flags byte and a little-endian 16-bit count. This module
reads every one of those numbers out of the YAML (field offsets, key, nonce and
tag sizes, byte order, scale factors) and nothing out of our own code or the
public implementation the spec cites, then:

* slices each synthetic message by the declared layout and opens it twice:
  with AES-CCM from `cryptography` (a dev dependency other spec tests already
  use) and with a CCM written here on top of bare AES block encryption from the
  block layouts the spec derives from RFC 3610;
* decodes the plaintext under BOTH readings the spec records and compares with
  the values the spec states, so the kilogram conflict stays visible as data;
* seals the plaintext again and reproduces the message hex;
* shows that a wrong key, a flipped bit anywhere, or a wrong length is refused.

The second half pins what the spec is allowed to claim. Nothing here was run on
a scale, so the spec must say untested, must never say confirmed, must keep the
kilogram scaling unresolved, and must keep both routes to a key unverified,
with what each costs an owner stated before what it gives. It also pins the
identifiers a client acts on (the GATT table, the identity check, the subscribe
value, the status bytes), walks the weight decision table against the two
readings it is built from, and checks that the device page states the same
bytes, rules and dates as the spec.

Owner safety is pinned too: the vendor's cut-off for the two sibling scales is
recorded as already in force, the firmware-update service asserts nothing and
offers no route, and the hardware notes stay notes. A change of phone never
leads to a reset, the capture route rehearses its log export before the pairing
is given up, and the sentences an owner or an integrator acts on (never write,
never reset because of silence, keep holding, do not bridge, do not share the
log) are each pinned by a short phrase where they stand.

The vectors are synthetic. Passing proves the document is self-consistent and
implementable; it proves nothing about real hardware.
"""

from __future__ import annotations

import copy
import re
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.ciphers.aead import AESCCM

REPO_ROOT = Path(__file__).resolve().parent.parent
SPEC_PATH = REPO_ROOT / "device-specs" / "devices" / "fitbit-aria-air.yaml"
PAGE_PATH = REPO_ROOT / "docs" / "devices" / "fitbit-aria-air.md"

SPEC_TEXT = SPEC_PATH.read_text(encoding="utf-8")
PAGE_TEXT = PAGE_PATH.read_text(encoding="utf-8")
SPEC = yaml.safe_load(SPEC_TEXT)
DEVICE = SPEC["device"]
DETAILS = SPEC["protocol_details"]
CIPHER = DETAILS["message_cipher"]
DECODING = DETAILS["weight_decoding"]
VECTORS = DETAILS["test_vectors"]

WEIGH_IN_UUID = "67b0ab2c-8323-427a-b1c9-70324bb5e228"
PROVISION_CHARACTERISTIC_UUID = "26f33a01-52a8-414b-99a2-1db75c99c032"
PROVISION_SERVICE_UUID = "26f33a00-52a8-414b-99a2-1db75c99c032"
WEIGHT_SCALE_SERVICE_UUID = "0000181d-0000-1000-8000-00805f9b34fb"
WEIGHT_MEASUREMENT_UUID = "00002a9d-0000-1000-8000-00805f9b34fb"
FIRMWARE_SERVICE_UUID = "00001530-1212-efde-1523-785feabcd123"
DEVICE_INFORMATION_SERVICE_UUID = "0000180a-0000-1000-8000-00805f9b34fb"
GENERIC_ACCESS_SERVICE_UUID = "00001800-0000-1000-8000-00805f9b34fb"
MODEL_NUMBER_UUID = "00002a24-0000-1000-8000-00805f9b34fb"
CLIENT_CONFIGURATION_DESCRIPTOR_UUID = "00002902-0000-1000-8000-00805f9b34fb"
# The stock Telink update service: named in the spec only as NOT found on the scale.
TELINK_UPDATE_SERVICE_UUID = "00010203-0405-0607-0809-0a0b0c0d1912"

# The whole GATT table the spec may declare: service -> {characteristic: name}.
# The weigh-in UUID is the one two independent parties reported; the
# provisioning UUIDs come from the public implementation; the rest are the
# Bluetooth SIG assignments for the names the public listing gives.
GATT_TABLE: dict[str, dict[str, str]] = {
    GENERIC_ACCESS_SERVICE_UUID: {},
    DEVICE_INFORMATION_SERVICE_UUID: {
        "00002a29-0000-1000-8000-00805f9b34fb": "Manufacturer Name String",
        MODEL_NUMBER_UUID: "Model Number String",
        "00002a25-0000-1000-8000-00805f9b34fb": "Serial Number String",
        "00002a27-0000-1000-8000-00805f9b34fb": "Hardware Revision String",
        "00002a26-0000-1000-8000-00805f9b34fb": "Firmware Revision String",
        "00002a28-0000-1000-8000-00805f9b34fb": "Software Revision String",
    },
    WEIGHT_SCALE_SERVICE_UUID: {
        WEIGH_IN_UUID: "Encrypted weigh-in message (vendor)",
        "00002a9e-0000-1000-8000-00805f9b34fb": "Weight Scale Feature",
    },
    PROVISION_SERVICE_UUID: {
        PROVISION_CHARACTERISTIC_UUID: "Provision status (read) and key (write)",
    },
    FIRMWARE_SERVICE_UUID: {},
}
# Named in the spec without being declared: the standard measurement the scale
# does NOT have, the descriptor a subscription writes, and the Telink update
# service the one published listing does NOT show.
MENTIONED_NOT_DECLARED = {
    WEIGHT_MEASUREMENT_UUID,
    CLIENT_CONFIGURATION_DESCRIPTOR_UUID,
    TELINK_UPDATE_SERVICE_UUID,
}
KNOWN_UUIDS = (
    set(GATT_TABLE)
    | {uuid for members in GATT_TABLE.values() for uuid in members}
    | MENTIONED_NOT_DECLARED
)
UUID_SHAPED = re.compile(
    r"(?<![0-9A-Fa-f-])[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}"
    r"(?![0-9A-Fa-f-])"
)

KEY = bytes.fromhex(VECTORS["key_hex"])


# --- what the spec declares, looked up rather than restated -----------------


def characteristics() -> dict[str, dict]:
    return {
        characteristic["uuid"]: characteristic
        for service in SPEC["services"]
        for characteristic in service.get("characteristics") or []
    }


def wire_fields() -> dict[str, dict]:
    """The format of the characteristic the cipher block says it applies to."""
    return {field["name"]: field for field in characteristics()[CIPHER["characteristic"]]["format"]}


def plaintext_fields() -> dict[str, dict]:
    """The payload format the cipher block names for the opened bytes."""
    return {
        field["name"]: field
        for field in SPEC["payload_formats"][CIPHER["plaintext_format"]]["fields"]
    }


def cut(data: bytes, field: dict) -> bytes:
    return data[field["offset"] : field["offset"] + field["length"]]


# --- transcription 1: the library's AES-CCM, fed in the spec's order --------


class NotAWeighIn(ValueError):
    """The bytes are not a message this key can vouch for."""


def open_message(key: bytes, message: bytes) -> bytes:
    """Slice by the declared layout, reorder for the library, verify, decrypt."""
    if len(key) != CIPHER["key_bytes"]:
        raise NotAWeighIn("key length")
    if len(message) != CIPHER["message_bytes"]:
        raise NotAWeighIn("message length")
    parts = {name: cut(message, field) for name, field in wire_fields().items()}
    library_input = b"".join(parts[name] for name in CIPHER["library_order"])
    assert CIPHER["associated_data_bytes"] == 0, "the spec declares no associated data"
    aead = AESCCM(key, tag_length=CIPHER["tag_bytes"])
    try:
        return aead.decrypt(parts[CIPHER["nonce_field"]], library_input, None)
    except InvalidTag as error:
        raise NotAWeighIn("tag does not verify") from error


def seal_message(key: bytes, nonce: bytes, plaintext: bytes) -> bytes:
    sealed = AESCCM(key, tag_length=CIPHER["tag_bytes"]).encrypt(nonce, plaintext, None)
    split = len(sealed) - CIPHER["tag_bytes"]
    parts = {"nonce": nonce, "ciphertext": sealed[:split], "tag": sealed[split:]}
    return b"".join(parts[name] for name in CIPHER["wire_order"])


# --- transcription 2: CCM from the derived block layouts, AES blocks only ---


def aes_block(key: bytes, block: bytes) -> bytes:
    encryptor = Cipher(algorithms.AES(key), modes.ECB()).encryptor()
    return encryptor.update(block) + encryptor.finalize()


def xor(left: bytes, right: bytes) -> bytes:
    return bytes(a ^ b for a, b in zip(left, right, strict=False))


def ccm_by_hand(key: bytes, nonce: bytes, plaintext: bytes) -> tuple[bytes, bytes]:
    """RFC 3610 with no associated data; returns (ciphertext, tag)."""
    derived = CIPHER["ccm_parameters_derived"]
    width = derived["length_field_bytes"]
    assert derived["counter_byte_order"] == "big"

    first = bytes([derived["b0_flags_byte"]]) + nonce + len(plaintext).to_bytes(width, "big")
    mac = aes_block(key, first)
    padded = plaintext + bytes(-len(plaintext) % 16)
    for start in range(0, len(padded), 16):
        mac = aes_block(key, xor(mac, padded[start : start + 16]))

    def counter_block(index: int) -> bytes:
        return bytes([derived["counter_block_flags_byte"]]) + nonce + index.to_bytes(width, "big")

    tag = xor(mac[: CIPHER["tag_bytes"]], aes_block(key, counter_block(0)))
    stream = b"".join(
        aes_block(key, counter_block(1 + block)) for block in range((len(plaintext) + 15) // 16)
    )
    return xor(plaintext, stream), tag


# --- the plaintext, and the two readings of it ------------------------------


def parse_plaintext(plaintext: bytes) -> tuple[int, int]:
    fields = plaintext_fields()
    if len(plaintext) != sum(field["length"] for field in fields.values()):
        raise NotAWeighIn("plaintext length")
    flags = int.from_bytes(cut(plaintext, fields[DECODING["flags_field"]]), "little")
    raw_field = fields[DECODING["raw_field"]]
    raw = int.from_bytes(cut(plaintext, raw_field), raw_field["endianness"])
    return flags, raw


def decode(reading_id: str, flags: int, raw: int, display_unit: str | None) -> tuple[str, Decimal]:
    """(unit, value) under one named reading; never a choice between them."""
    reading = next(r for r in DECODING["readings"] if r["id"] == reading_id)
    if reading["unit_selected_by"] == "flags_bit0":
        unit = reading["flags_bit0_units"][str(flags & 1)]
    elif reading["unit_selected_by"] == "owner_setting":
        assert display_unit is not None, "this reading needs the owner to state the display unit"
        unit = display_unit
    else:
        raise AssertionError(reading["unit_selected_by"])
    return unit, Decimal(raw) * Decimal(str(reading["scales"][unit]))


def every(node, key: str):
    """Every value stored under `key`, anywhere in a parsed YAML tree."""
    if isinstance(node, dict):
        for name, value in node.items():
            if name == key:
                yield value
            yield from every(value, key)
    elif isinstance(node, list):
        for item in node:
            yield from every(item, key)


def strings(node):
    """Every string value anywhere in a parsed YAML tree."""
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for value in node.values():
            yield from strings(value)
    elif isinstance(node, list):
        for item in node:
            yield from strings(item)


def decide(display_unit: str, flags: int, stored_flags: int | None = None, tag_ok: bool = True) -> dict:
    """Walk decision_table as written: guards in order, then the one matching row."""
    table = DECODING["decision_table"]
    guards = {guard["id"]: guard for guard in table["guards"]}
    assert list(guards) == ["tag_failed", "unknown_flags", "flags_changed"], "guard order is part of the rule"
    if not tag_ok:
        return guards["tag_failed"]
    if flags not in (0, 1):
        return guards["unknown_flags"]
    if stored_flags is not None and flags != stored_flags:
        return guards["flags_changed"]
    matching = [
        row
        for row in table["rows"]
        if row["display_unit"] == display_unit and row["flags_bit0"] == flags & 1
    ]
    assert len(matching) == 1, (display_unit, flags, matching)
    return matching[0]


def section(page: str, heading: str) -> str:
    """The body of one Markdown section, up to the next heading of the same or a higher level."""
    level = len(heading) - len(heading.lstrip("#"))
    start = page.index(heading + "\n") + len(heading) + 1
    following = re.search(rf"^#{{1,{level}}} ", page[start:], re.MULTILINE)
    return page[start : start + following.start()] if following else page[start:]


def table_rows(text: str) -> list[list[str]]:
    """Cells of every Markdown table row in `text`, separator rows dropped."""
    rows = []
    for line in text.splitlines():
        if line.startswith("|") and not re.fullmatch(r"[|\s:-]+", line):
            rows.append([cell.strip() for cell in line.strip().strip("|").split("|")])
    return rows


VECTOR_IDS = [vector["name"] for vector in VECTORS["vectors"]]


# --- layout ------------------------------------------------------------------


def test_the_wire_layout_is_nonce_then_tag_then_ciphertext_and_covers_19_bytes():
    fields = wire_fields()
    assert list(fields) == CIPHER["wire_order"] == ["nonce", "tag", "ciphertext"]
    assert CIPHER["library_order"] == ["ciphertext", "tag"]
    cursor = 0
    for name in CIPHER["wire_order"]:
        assert fields[name]["offset"] == cursor, f"{name} leaves a gap or overlaps"
        assert fields[name]["type"] == "bytes"
        cursor += fields[name]["length"]
    assert cursor == CIPHER["message_bytes"] == 19
    assert fields["nonce"]["length"] == CIPHER["nonce_bytes"] == 8
    assert fields["tag"]["length"] == CIPHER["tag_bytes"] == 8
    assert fields["ciphertext"]["length"] == CIPHER["plaintext_bytes"] == 3


def test_the_cipher_parameters_are_stated_as_numbers():
    assert CIPHER["algorithm"] == "AES-128-CCM"
    assert CIPHER["key_bytes"] == 16 and len(KEY) == 16
    assert CIPHER["associated_data_bytes"] == 0 and CIPHER["associated_data"] == "none"
    derived = CIPHER["ccm_parameters_derived"]
    # RFC 3610: the length field takes what the nonce leaves of the 15 bytes,
    # and both flags bytes follow from that and from the tag length.
    assert derived["length_field_bytes"] == 15 - CIPHER["nonce_bytes"] == 7
    assert derived["b0_flags_byte"] == 8 * ((CIPHER["tag_bytes"] - 2) // 2) + 6 == 0x1E
    assert derived["counter_block_flags_byte"] == derived["length_field_bytes"] - 1 == 0x06


def test_the_plaintext_is_a_flags_byte_and_a_little_endian_count():
    fields = plaintext_fields()
    assert list(fields) == ["flags", "weight_raw"]
    assert (fields["flags"]["offset"], fields["flags"]["length"]) == (0, 1)
    assert fields["flags"]["type"] == "uint8"
    raw = fields["weight_raw"]
    assert (raw["offset"], raw["length"], raw["type"]) == (1, 2, "uint16")
    assert raw["endianness"] == "little"
    assert parse_plaintext(bytes.fromhex("010200")) == (1, 2)
    assert parse_plaintext(bytes.fromhex("000001")) == (0, 256)
    example = SPEC["payload_formats"]["WeighInPlaintext"]["example"]
    assert example == VECTORS["vectors"][0]["plaintext_hex"]


# --- vectors -----------------------------------------------------------------


@pytest.mark.parametrize("vector", VECTORS["vectors"], ids=VECTOR_IDS)
def test_each_message_opens_to_its_plaintext(vector):
    message = bytes.fromhex(vector["message_hex"])
    fields = wire_fields()
    assert cut(message, fields["nonce"]).hex() == vector["nonce_hex"]
    assert cut(message, fields["tag"]).hex() == vector["tag_hex"]
    assert cut(message, fields["ciphertext"]).hex() == vector["ciphertext_hex"]

    plaintext = open_message(KEY, message)
    assert plaintext.hex() == vector["plaintext_hex"]
    assert parse_plaintext(plaintext) == (vector["flags"], vector["weight_raw"])


@pytest.mark.parametrize("vector", VECTORS["vectors"], ids=VECTOR_IDS)
def test_each_plaintext_seals_back_to_the_same_message(vector):
    nonce = bytes.fromhex(vector["nonce_hex"])
    plaintext = bytes.fromhex(vector["plaintext_hex"])
    assert seal_message(KEY, nonce, plaintext).hex() == vector["message_hex"]


@pytest.mark.parametrize("vector", VECTORS["vectors"], ids=VECTOR_IDS)
def test_ccm_built_from_aes_blocks_agrees_with_the_library(vector):
    nonce = bytes.fromhex(vector["nonce_hex"])
    ciphertext, tag = ccm_by_hand(KEY, nonce, bytes.fromhex(vector["plaintext_hex"]))
    assert ciphertext.hex() == vector["ciphertext_hex"]
    assert tag.hex() == vector["tag_hex"]


@pytest.mark.parametrize("vector", VECTORS["vectors"], ids=VECTOR_IDS)
def test_each_reading_decodes_to_the_value_the_spec_states(vector):
    flags, raw = parse_plaintext(open_message(KEY, bytes.fromhex(vector["message_hex"])))
    stated = vector["decoded"]
    assert {entry["reading"] for entry in stated} == {r["id"] for r in DECODING["readings"]}
    for entry in stated:
        unit, value = decode(entry["reading"], flags, raw, entry.get("display_unit"))
        assert unit == entry["unit"], entry
        assert value == Decimal(str(entry["value"])), entry
    values = {(entry["unit"], Decimal(str(entry["value"]))) for entry in stated}
    assert (len(values) == 1) is vector["readings_agree"]


def test_the_vectors_cover_agreement_and_conflict_and_a_fresh_nonce():
    by_name = {vector["name"]: vector for vector in VECTORS["vectors"]}
    pounds = by_name["flag_set_pounds"]
    conflict = by_name["flag_clear_kilogram_conflict"]
    repeat = by_name["same_weigh_in_fresh_nonce"]

    assert pounds["readings_agree"] is True
    assert {entry["unit"] for entry in pounds["decoded"]} == {"lb"}
    assert conflict["readings_agree"] is False
    low, high = sorted(Decimal(str(entry["value"])) for entry in conflict["decoded"])
    assert {entry["unit"] for entry in conflict["decoded"]} == {"kg"}
    assert high == 2 * low, "the two kilogram readings differ by exactly a factor of two"

    # Same plaintext, different nonce: nothing on the wire repeats.
    assert repeat["plaintext_hex"] == pounds["plaintext_hex"]
    assert repeat["nonce_hex"] != pounds["nonce_hex"]
    assert repeat["tag_hex"] != pounds["tag_hex"]
    assert repeat["ciphertext_hex"] != pounds["ciphertext_hex"]


def test_synthetic_nonces_imitate_the_reported_mirrored_pairs():
    assert CIPHER["nonce_structure_observed"]["needed_by_decoder"] is False
    for vector in VECTORS["vectors"]:
        nonce = bytes.fromhex(vector["nonce_hex"])
        assert (nonce[4], nonce[5]) == (nonce[2], nonce[1]), vector["name"]


# --- refusals ----------------------------------------------------------------


@pytest.mark.parametrize("vector", VECTORS["vectors"], ids=VECTOR_IDS)
def test_a_wrong_key_is_refused(vector):
    message = bytes.fromhex(vector["message_hex"])
    for position in range(len(KEY)):
        wrong = bytearray(KEY)
        wrong[position] ^= 0x01
        with pytest.raises(NotAWeighIn, match="tag"):
            open_message(bytes(wrong), message)
    with pytest.raises(NotAWeighIn, match="tag"):
        open_message(bytes(16), message)


@pytest.mark.parametrize("vector", VECTORS["vectors"], ids=VECTOR_IDS)
def test_a_flipped_bit_anywhere_is_refused(vector):
    message = bytes.fromhex(vector["message_hex"])
    for position in range(len(message)):
        for bit in range(8):
            damaged = bytearray(message)
            damaged[position] ^= 1 << bit
            with pytest.raises(NotAWeighIn, match="tag"):
                open_message(KEY, bytes(damaged))


def test_a_message_of_the_wrong_length_is_refused():
    message = bytes.fromhex(VECTORS["vectors"][0]["message_hex"])
    for wrong in (b"", message[:-1], message + b"\x00", message[:16]):
        with pytest.raises(NotAWeighIn, match="message length"):
            open_message(KEY, wrong)
    with pytest.raises(NotAWeighIn, match="key length"):
        open_message(KEY[:15], message)
    for wrong in (b"", b"\x01\x02", b"\x01\x02\x03\x04"):
        with pytest.raises(NotAWeighIn, match="plaintext length"):
            parse_plaintext(wrong)


def test_tag_then_ciphertext_is_not_what_a_library_expects():
    """Handing the wire bytes to the library unreordered must not decrypt."""
    message = bytes.fromhex(VECTORS["vectors"][0]["message_hex"])
    nonce, rest = message[:8], message[8:]
    with pytest.raises(InvalidTag):
        AESCCM(KEY, tag_length=8).decrypt(nonce, rest, None)


# --- the kilogram conflict stays a conflict ----------------------------------


def test_the_kilogram_scaling_is_recorded_as_an_unresolved_conflict():
    assert DECODING["resolved"] is False
    conflict = DECODING["conflict"]
    assert conflict["id"] == "C1" and conflict["resolved"] is False
    per_count = {p["reading"]: p["kilograms_per_count"] for p in conflict["positions"]}
    assert per_count == {
        "hundredths_of_displayed_unit": 0.01,
        "sig_weight_measurement_flags": 0.005,
    }

    kilograms = DECODING["unit_modes"]["kg"]
    assert kilograms["status"] == "conflict" and kilograms["conflict"] == "C1"
    # Not False: the one source with captures never says which unit its scale showed.
    assert kilograms["observed_on_hardware"] == "unknown"
    assert "not stated" in kilograms["observed_on_hardware_notes"]
    assert "scale" not in kilograms, "a single kilogram scale would be a resolution"
    assert sorted(c["scale"] for c in kilograms["candidates"]) == [0.005, 0.01]

    listed = {c["id"]: c for c in DETAILS["conflicts"]}
    assert listed["C1"]["status"] == "unresolved"


def test_pounds_is_the_only_unit_mode_with_one_answer():
    modes_ = DECODING["unit_modes"]
    assert set(modes_) == {"lb", "kg", "st"}
    assert modes_["lb"]["status"] == "reported"
    assert (modes_["lb"]["unit"], modes_["lb"]["scale"], modes_["lb"]["flags_bit0"]) == ("lb", 0.01, 1)
    assert modes_["st"]["status"] == "unknown"
    readings = {r["id"]: r for r in DECODING["readings"]}
    assert readings["hundredths_of_displayed_unit"]["scales"]["lb"] == 0.01
    assert readings["sig_weight_measurement_flags"]["scales"]["lb"] == 0.01
    assert readings["sig_weight_measurement_flags"]["flags_bit0_units"] == {"0": "kg", "1": "lb"}


def test_the_raw_count_carries_no_unit_or_scale_of_its_own():
    """A scale on the field would silently pick one side of the conflict."""
    raw = plaintext_fields()["weight_raw"]
    for key in ("unit", "scale", "unit_values", "unit_scales", "unit_source", "device_class"):
        assert key not in raw, f"weight_raw.{key} resolves a question the evidence has not"
    for field in characteristics()[WEIGH_IN_UUID]["format"]:
        for key in ("unit", "scale", "device_class"):
            assert key not in field, "ciphertext is not a weight"


# --- what the spec may claim -------------------------------------------------


def test_nothing_is_claimed_as_tested_or_confirmed():
    testing = DEVICE["testing"]
    assert testing["status"] == "untested"
    assert "detail" not in testing
    assert testing["notes"].strip()

    assert "confirmed" not in set(every(SPEC, "verification"))
    assert True not in set(every(SPEC, "verified")), "no method or procedure was run"
    assert DEVICE["setup"]["confidence"] != "high"
    assert DEVICE["pairing"]["confidence"] != "high"
    assert DEVICE["setup"]["factory_reset"]["confidence"] != "high"
    for uuid in (WEIGH_IN_UUID, PROVISION_CHARACTERISTIC_UUID):
        assert characteristics()[uuid]["verification"] == "reported"
    for block in ("message_cipher", "weight_decoding", "key_lifecycle", "subscription"):
        assert DETAILS[block]["verification"] == "reported"


def test_the_vendor_has_not_abandoned_this_model():
    assert DEVICE["manufacturer_status"] == "active"
    status = DETAILS["vendor_status"]
    assert status["affected_by_pairing_cutoff"] is False
    cutoff = status["pairing_cutoff"]
    assert not any("FB203" in model for model in cutoff["applies_to"])
    assert "not impacted" in cutoff["aria_air_statement"]
    assert status["still_sold"]["value"] is True
    lowered = SPEC_TEXT.lower()
    assert "abandoned" not in lowered and "shutdown" not in lowered


# Either way of writing each date, however a line break falls inside it.
STALE_DATE = re.compile(r"2026-11-28|\b28\s+November\b|\bNovember\s+28\b")
CURRENT_DATE = re.compile(r"2026-11-09|\b9\s+November\b|\bNovember\s+9\b")
# Wording that would tell the owner of a sibling scale there is time left.
TIME_LEFT = re.compile(
    r"time left|days? left|still time|On that date|a few days|\bdays to\b|last chance|"
    r"\bwill (?:only )?(?:happen|end|stop|take effect)\b|not yet (?:ended|in force|happened)|"
    r"can still (?:be )?(?:paired|pair|re-pair)|before it (?:ends|is too late)|"
    r"(?:before|until|by|from|ends? on|ending on) (?:2026-11-28|28 November)",
    re.IGNORECASE,
)


def test_the_cutoff_is_in_force_and_the_edited_notice_is_only_an_observation():
    """By the vendor's current English notice the sibling scales' cut-off is in the past."""
    status = DETAILS["vendor_status"]
    cutoff = status["pairing_cutoff"]
    assert cutoff["in_force"] is True
    assert cutoff["date"] == "2026-11-09" and cutoff["date"] < status["as_of"]
    assert cutoff["app_version"] == "5.12"
    assert cutoff["current_english_wording"].startswith("Starting November 9, 2026, with the release of app version 5.12")
    assert "continue to sync" in cutoff["paired_scales_statement"]
    assert cutoff["paired_scales_end_date"] == "none stated"
    assert cutoff["aria_air_statement"] == "Aria Air is not impacted by this change."
    assert "not promise" in " ".join(cutoff["aria_air_statement_caveat"].split())
    assert cutoff["source"] == "https://support.google.com/googlehealth/answer/14236805"
    assert cutoff["verification"] == "reported"

    # The other date survives only as a dated observation about the source.
    observed = cutoff["notice_edit_observed"]
    assert observed["earlier_date"] == "2026-11-28" and observed["earlier_date_is_current"] is False
    assert observed["earlier_english_wording"] == cutoff["current_english_wording"].replace(
        "November 9,", "November 28,"
    ), "nothing but the day differs between the two wordings"
    assert observed["earlier_wording_read_utc"] == "2026-11-23T05:11Z"
    reads = observed["current_wording_read_utc"]
    assert reads == sorted(reads) and reads[0] == "2026-11-23T23:07Z"
    assert observed["earlier_wording_read_utc"] < reads[0]
    # What kind of evidence the first time is, and that it is not the earliest.
    basis = " ".join(observed["current_wording_read_basis"].split())
    assert "save time" in basis and "not a logged fetch" in basis
    assert "not the earliest evidence" in basis
    earliest = observed["current_wording_earliest_saved_copy_utc"]
    assert observed["earlier_wording_read_utc"] < earliest < reads[0]
    assert "File time" in observed["current_wording_earliest_saved_copy_basis"]
    other = observed["other_language_editions"]
    assert other["languages"] == ["de", "fr", "ja"] and other["date_stated"] == observed["earlier_date"]
    assert "already ended" in " ".join(observed["not_known"].split())

    # Outside that observation no field of the cut-off block carries the old date ...
    outside = {key: value for key, value in cutoff.items() if key != "notice_edit_observed"}
    assert not any(STALE_DATE.search(text) for text in strings(outside))
    assert "2026-11-28" not in set(every(SPEC, "date"))
    # ... and no string anywhere else names it without the current date beside it.
    rest = copy.deepcopy(SPEC)
    del rest["protocol_details"]["vendor_status"]["pairing_cutoff"]["notice_edit_observed"]
    # Paragraph by paragraph: a long note that names the current date somewhere else
    # does not excuse a paragraph that names only the old one.
    paragraphs = [" ".join(part.split()) for text in strings(rest) for part in re.split(r"\n+", text)]
    mentions = [paragraph for paragraph in paragraphs if STALE_DATE.search(paragraph)]
    assert mentions, "the observed edit is mentioned where an owner will read it"
    for paragraph in mentions:
        assert CURRENT_DATE.search(paragraph), paragraph
    for text in (SPEC_TEXT, PAGE_TEXT):
        assert not TIME_LEFT.search(" ".join(text.split()))
    # Nothing about how this entry was produced leaks into what is published.
    for text in (SPEC_TEXT, PAGE_TEXT):
        assert "this session" not in text.lower()


def test_identity_is_the_name_not_a_shared_signal():
    identification = DEVICE["identification"]
    assert identification["local_names"] == ["Aria Air"]
    assert "service_uuids" not in identification, "0x181d belongs to every standard scale"
    assert "manufacturer_data" not in identification, "0x018e belongs to every Google product"
    assert "local_name_prefix" not in identification

    (method,) = DEVICE["discovery"]["methods"]
    assert method["type"] == "ble_scan"
    assert method["ble"]["local_name"] == {"match": "exact", "value": "Aria Air"}
    assert "service_uuids" not in method["ble"] and "manufacturer_data" not in method["ble"]

    advertisement = DETAILS["advertisement"]
    assert advertisement["manufacturer_data"]["company_id"] == 0x018E == 398
    assert advertisement["identity_signals"] == {
        "local_name": True,
        "manufacturer_data": False,
        "service_0x181d": False,
    }
    record = SPEC["payload_formats"]["ManufacturerData"]["fields"]
    assert [(f["name"], f["offset"], f["length"]) for f in record] == [
        ("reserved", 0, 1),
        ("awake", 1, 1),
        ("address", 2, 6),
    ]
    assert sum(f["length"] for f in record) == advertisement["manufacturer_data"]["payload_bytes"]

    # The wake signal: which field, which value, and what each value means.
    wake = advertisement["wake_signal"]
    awake_field = next(f for f in record if f["name"] == wake["field"])
    assert wake["field"] == "awake" and wake["awake_value"] == 1
    assert awake_field["values"] == {"0": "asleep", "1": "awake"}
    assert awake_field["values"][str(wake["awake_value"])] == "awake"
    assert advertisement["advertises_while_asleep"] is True
    assert advertisement["advertises_while_connected"] is False


def test_the_post_connect_identity_check_is_pinned():
    confirmation = DETAILS["identity_confirmation"]
    assert confirmation["verification"] == "reported"
    model, vendor_characteristic, standard_measurement = confirmation["checks"]
    assert model == {"characteristic": MODEL_NUMBER_UUID, "expect_utf8": "FB203"}
    assert model["expect_utf8"] == DEVICE["model"]
    assert vendor_characteristic["characteristic"] == WEIGH_IN_UUID
    assert WEIGHT_SCALE_SERVICE_UUID in vendor_characteristic["expect"]
    assert standard_measurement == {"characteristic": WEIGHT_MEASUREMENT_UUID, "expect": "absent"}
    assert MODEL_NUMBER_UUID in GATT_TABLE[DEVICE_INFORMATION_SERVICE_UUID]
    assert "FB203" in characteristics()[MODEL_NUMBER_UUID]["notes"]


def test_it_is_not_a_standard_weight_scale():
    declared = characteristics()
    assert WEIGHT_MEASUREMENT_UUID not in declared
    services = {service["uuid"]: service for service in SPEC["services"]}
    in_weight_service = {c["uuid"] for c in services[WEIGHT_SCALE_SERVICE_UUID]["characteristics"]}
    assert WEIGH_IN_UUID in in_weight_service
    assert declared[WEIGH_IN_UUID]["properties"] == ["indicate"]
    absent = [c for c in DETAILS["identity_confirmation"]["checks"] if c.get("expect") == "absent"]
    assert [c["characteristic"] for c in absent] == [WEIGHT_MEASUREMENT_UUID]


def test_the_key_gate_is_application_layer_with_no_bond():
    pairing = DEVICE["pairing"]
    assert pairing["required"] is True
    assert (pairing["security_mode"], pairing["bonding"]) == ("app_layer", "none")
    assert pairing["enter_pairing_mode"]["required"] is False
    assert pairing["exclusivity"]["single_connection"] is True
    assert pairing["exclusivity"]["recovery"].strip()

    provision = characteristics()[PROVISION_CHARACTERISTIC_UUID]
    assert provision["properties"] == ["read", "write"]
    (status,) = provision["format"]
    assert (status["offset"], status["length"], status["type"]) == (0, 1, "uint8")
    assert status["values"] == {0: "not_provisioned", 1: "provisioned"}
    lifecycle = DETAILS["key_lifecycle"]
    assert lifecycle["provision_status"]["characteristic"] == PROVISION_CHARACTERISTIC_UUID
    assert lifecycle["provision_status"]["values"] == {"0": "not_provisioned", "1": "provisioned"}
    # Each lifecycle state carries the status byte the characteristic format gives it.
    assert [(s["state"], s["status_byte"]) for s in lifecycle["states"]] == [
        ("not_provisioned", 0),
        ("provisioned", 1),
    ]
    for state in lifecycle["states"]:
        assert status["values"][state["status_byte"]] == state["state"]
    assert lifecycle["readable_back"] is False
    assert lifecycle["write_when_provisioned"]["outcome"] == "unknown"


def test_single_report_claims_and_unobserved_states_are_not_stated_as_behaviour():
    lifecycle = DETAILS["key_lifecycle"]
    # Two things the one 2026-10-26 comment says it observed carry the same grade
    # and the same caveats, as data: one report, one scale, firmware not stated,
    # relayed from an AI assistant's analysis, reproduced by nobody.
    for claim in ("own_key_provisioning", "survives_battery_removal"):
        entry = lifecycle[claim]
        assert entry["verification"] == "reported", claim
        assert (entry["reports"], entry["scales_tested"]) == (1, 1), claim
        assert entry["replicated"] is False and entry["firmware_stated"] is False, claim
        assert entry["relayed_from_ai_assistant"] is True, claim
        assert "value" not in entry, claim
    own_key_claim = lifecycle["own_key_provisioning"]
    assert own_key_claim["tool_or_repository_published"] is False
    assert "tool_or_code_published" not in own_key_claim, "the comment does carry a decode fragment"
    assert "four-line" in own_key_claim["code_in_comment"]
    assert "nothing for the key write" in own_key_claim["code_in_comment"]
    # What that comment asserts without saying how it knows stays a hypothesis.
    assert lifecycle["vendor_server_copy"]["verification"] == "hypothesis"
    assert "inference" in lifecycle["vendor_server_copy"]["basis"]
    assert "unreplicated" in DEVICE["setup"]["credentials"]["notes"]

    # No source says what a scale at status 00 sends; the spec may not either.
    assert lifecycle["unprovisioned_stream"]["outcome"] == "unknown"
    keyless = lifecycle["states"][0]
    assert keyless["status_byte"] == 0 and "not reported" in keyless["client_can"]
    effect = DEVICE["setup"]["factory_reset"]["effect"]
    assert "Not reported" in effect and "assume" in effect
    assert "void" not in effect, "that the old key is void at status 00 is an inference"
    assert "not reported" in SPEC["initialization"][0]["notes"]

    # Where the vendor app gets the key is not established, so nobody 'chooses' it here.
    (issued,) = DEVICE["setup"]["credentials"]["issued_to_client"]
    assert "not established" in issued and "chosen" not in issued

    # A shared company name is not a shared factory.
    for text in (SPEC_TEXT, PAGE_TEXT):
        lowered = " ".join(text.lower().split())
        assert "same factory" not in lowered and "factory is the same" not in lowered
        assert "factory behind" not in lowered
    assert any(line.startswith("Q13.") for line in SPEC["remaining_unknowns"])

    # The handle-to-characteristic link is the research pass's inference.
    assert "inferred" in DETAILS["subscription"]["handles_seen"]["provision_value"]


def method_steps(method: dict) -> list[dict]:
    return [step for phase in method.get("stages") or [method] for step in phase["steps"]]


def test_both_key_routes_are_unverified_and_say_what_they_cost_before_what_they_give():
    setup = DEVICE["setup"]
    assert setup["required"] is True
    assert " ".join(setup["notes"].split()).startswith("READ FIRST: a scale that already works")
    vendor, own_key = setup["methods"]
    assert (vendor["role"], own_key["role"]) == ("primary", "alternative")

    for method in (vendor, own_key):
        assert method["verified"] is False
        assert method["advanced"] is True and method["advanced_reason"].strip()
        assert "Not run by this project." in " ".join(method["basis"].split())
        # `verification` is not a declared key on a setup method; the grade of the
        # claim behind a route lives in protocol_details.key_lifecycle.
        assert "verification" not in method
        description = " ".join(method["description"].split())
        assert description.startswith("WHAT IT COSTS, BEFORE WHAT IT GIVES."), method["name"]
        first = method_steps(method)[0]
        assert first["actor"] == "user" and first["action"].lstrip().startswith("STOP AND DECIDE.")
        assert "factory-reset" in first["action"] and "pairing" in first["action"]
        # No tool recipe: the steps state GATT and ATT facts, never a program to run.
        # The own-key route names no tool at all, because its one source names none.
        # The capture route may say how its source takes the log off the phone (an
        # Android bug report made with adb): without that the route cannot be finished.
        banned = ["nrf connect", "bleak", "gatttool", "bluetoothctl", "bugreport", "extract_key", "python"]
        if method is own_key:
            banned += ["adb", "bug report"]
        for step in method_steps(method):
            lowered = " ".join(step["action"].lower().split())
            for tool in banned:
                assert not re.search(rf"\b{re.escape(tool)}\b", lowered), (tool, step["action"])

    # Route 1, as the second research round's reviewer requires it to be worded.
    assert [stage["type"] for stage in vendor["stages"]] == ["cloud_account", "ble_direct"]
    assert vendor["stages"][0]["cloud"]["local_alternative"].strip()
    costs = " ".join(vendor["description"].split())
    assert "STARTS by removing the scale from the vendor account and factory-resetting it" in costs
    assert "depends on the vendor app completing a fresh setup" in costs
    assert "public history of failing" in costs and "search-result titles" in costs
    assert "UNPAIRED WITH AN APP THAT WILL NOT RE-PAIR IT" in costs
    assert "The same key serves both, but the scale serves one client at a time" in costs
    basis = " ".join(vendor["basis"].split())
    assert "One party, one scale" in basis and "hardware H01, firmware A16" in basis
    assert "version 5.12" in basis and "Nobody else has reported the route end to end" in basis
    first_stage = vendor["stages"][0]["steps"]
    actions = [" ".join(step["action"].split()) for step in first_stage]
    remove_at = next(i for i, action in enumerate(actions) if action.startswith("Remove the scale"))
    reset_at = next(i for i, action in enumerate(actions) if action.startswith("Factory-reset"))
    add_at = next(i for i, action in enumerate(actions) if action.startswith("Add the scale"))
    assert 0 < remove_at < reset_at < add_at
    assert "ends the present pairing" in actions[remove_at]
    assert "unpaired" in first_stage[add_at]["expect"]
    assert any("history of failing" in cause for item in vendor["troubleshooting"] for cause in item["causes"])

    # The route can be finished from the file, and the owner finds out whether the
    # log can be recorded and exported BEFORE the pairing is given up.
    log_on_at = next(i for i, action in enumerate(actions) if "HCI snoop log" in action)
    dry_run_at = next(i for i, action in enumerate(actions) if action.startswith("DRY RUN, BEFORE ANYTHING IS REMOVED."))
    check_at = next(i for i, action in enumerate(actions) if "GO ON ONLY WHEN THAT WORKS." in action)
    export_at = next(i for i, action in enumerate(actions) if action.startswith("Take the Bluetooth log off the phone"))
    assert 0 < log_on_at < dry_run_at < check_at < remove_at < add_at < export_at == len(actions) - 1
    assert first_stage[dry_run_at]["actor"] == "user" and first_stage[check_at]["actor"] == "client"
    assert "do one normal weigh-in" in actions[dry_run_at]
    assert "leave the snoop log switched on" in actions[dry_run_at]
    assert "opcode 0x1d" in actions[check_at] and "19 bytes" in actions[check_at]
    assert "the pairing is still intact and nothing has been lost" in actions[check_at]
    assert "does not show" in " ".join(first_stage[check_at]["expect"].split())
    export = actions[export_at]
    assert "Never share or upload the file." in export
    assert "Android bug report" in export and "adb tool from a computer" in export
    assert "not checked on any phone by this project" in export
    capture_route = next(r for r in DETAILS["key_routes"]["routes"] if r["id"] == "capture_key_from_bluetooth_log")
    assert "a way to take an Android bug report off that phone" in capture_route["needs"]
    log_export = capture_route["log_export"]
    assert log_export["rehearse_before_removal"] is True
    assert log_export["log_path_in_report"] in export and log_export["log_path_in_report"].endswith("btsnoop_hci.log")
    assert "Not checked on any phone by this project" in log_export["basis"]
    dry_run_trouble = next(item for item in vendor["troubleshooting"] if item["symptom"].startswith("The dry run"))
    assert dry_run_trouble["causes"][0].startswith("Stop there. Nothing has been lost")
    assert vendor["troubleshooting"][0] is dry_run_trouble
    assert "guessed, without confirming" in basis and "without identifying" not in basis
    # The stage that ends the pairing says so in its own local alternative, and
    # silence after either route is never a reason to reset.
    assert "ends the vendor pairing too" in " ".join(vendor["stages"][0]["cloud"]["local_alternative"].split())
    for method in (vendor, own_key):
        silent = [
            cause
            for item in method["troubleshooting"]
            if "nothing arrive" in item["symptom"]
            for cause in item["causes"]
        ]
        assert silent and all(cause.startswith("Not a key problem, and not a reason to reset") for cause in silent), method["name"]
    for text in (SPEC_TEXT, PAGE_TEXT):
        lowered = " ".join(text.lower().split())
        assert "keeps the vendor app working" not in lowered
        assert "leaves the vendor app working" not in lowered
        assert "prudent" not in lowered, "capturing a key from a working scale is not advice this entry gives"

    # Route 2: one report, and the warnings that must travel with it.
    assert own_key["type"] == "ble_provisioning"
    assert "unreplicated" in own_key["name"]
    basis = " ".join(own_key["basis"].split())
    assert "1105" in basis and "AI assistant" in basis and "One unit" in basis
    assert "firmware and hardware revision not stated" in basis
    assert "nobody has posted a reproduction" in basis and "no tool named" in basis
    assert "no repository or capture linked" in basis and "four-line fragment" in basis
    assert "nothing for the key write" in basis and "no code or capture published" not in basis
    costs = " ".join(own_key["description"].split())
    assert "ENDS THE VENDOR PAIRING" in costs and "RECORD THE KEY BEFORE WRITING IT" in costs
    assert "If weigh-ins do not decrypt afterwards, reset again." in costs
    assert "untested on any firmware its source could name" in costs
    assert own_key["ble"]["write_characteristic"] == PROVISION_CHARACTERISTIC_UUID
    assert own_key["ble"]["read_characteristic"] == PROVISION_CHARACTERISTIC_UUID
    assert own_key["ble"]["service_uuid"] == PROVISION_SERVICE_UUID
    assert own_key["ble"]["pairing_required"] is False

    claim = DETAILS["key_lifecycle"]["own_key_provisioning"]
    assert claim["verification"] == "reported" and claim["replicated"] is False

    # The key is stored before it is written, and the write happens only after
    # the status has been read as 00.
    actions = [step["action"] for step in own_key["steps"]]
    store_at = next(i for i, action in enumerate(actions) if "BEFORE writing them" in action)
    read_at = next(i for i, action in enumerate(actions) if action.startswith("Read the provision"))
    write_at = next(i for i, action in enumerate(actions) if action.startswith("Write the 16-byte"))
    assert store_at < read_at < write_at
    assert "STOP" in own_key["steps"][read_at]["expect"]
    assert own_key["steps"][read_at]["expect"].startswith("One byte, 00.")
    write_request = own_key["steps"][write_at]["request"]
    assert write_request["service"] == PROVISION_SERVICE_UUID
    # The report used a write WITH response; a write command may be dropped silently.
    assert write_request["action"] == f"write (with response) {PROVISION_CHARACTERISTIC_UUID}"
    (key_argument,) = write_request["arguments"]
    assert key_argument["type"] == "bytes[16]"
    assert own_key["steps"][write_at + 1]["expect"] == "One byte, 01."
    for method in setup["methods"]:
        for phase in method.get("stages") or [method]:
            for step in phase["steps"]:
                assert step["actor"] in {"user", "client", "device"}, step


def test_the_reset_is_the_manuals_and_is_not_claimed_as_run():
    reset = DEVICE["setup"]["factory_reset"]
    assert reset["applicable"] is True
    (procedure,) = reset["procedures"]
    assert procedure["verified"] is False
    assert "Manual" in procedure["basis"] and "1.8" in procedure["basis"]
    assert procedure["hold_seconds"] == 10
    expects = " ".join(step.get("expect", "") for step in procedure["steps"])
    assert "otA" in expects and "clr" in expects
    assert all(step["actor"] == "user" for step in procedure["steps"])
    assert "00" in reset["effect"]

    # The consequence is stated where the reset is described, in plain words, first.
    assert reset["effect"].startswith("FOR AN OWNER: a reset ends the scale's current setup.")
    assert procedure["description"].startswith("CONSEQUENCE: this ends the scale's current setup.")
    assert "ends the pairing" in " ".join(procedure["steps"][0]["action"].split())
    # Nobody knows what the otA state is: the spec may not call it an update state,
    # and it tells nobody to stop there.
    description = " ".join(reset["description"].split())
    assert "Neither the manual nor any other public source says what that state is" in description
    assert "Do not start the hold unless a reset is intended" in description
    assert "keep holding through otA until clr, and write to nothing while otA shows" in description
    assert "do not use it as casual troubleshooting" in description
    for text in (SPEC_TEXT, PAGE_TEXT):
        lowered = " ".join(text.lower().split())
        for claim in ("firmware-update state", "update mode", "ota mode", "names an update", "looks like a firmware"):
            assert claim not in lowered, claim


def test_no_write_surface_is_offered_to_a_generic_client():
    assert DEVICE["integration"] == "identify_only"
    assert "entities" not in SPEC and "commands" not in SPEC
    assert DETAILS["entity_coverage"]["declared_entities"] == 0
    for uuid, characteristic in characteristics().items():
        assert "commands" not in characteristic, f"{uuid} declares a command"
    for step in SPEC["initialization"]:
        assert "write" not in step, "a connection never writes on its own"
    by_target = {step["characteristic"]: step for step in SPEC["initialization"]}
    assert by_target[PROVISION_CHARACTERISTIC_UUID]["read"] is True
    assert by_target[WEIGH_IN_UUID]["subscribe"] is True

    rules = " ".join(rule["rule"] for rule in DETAILS["key_lifecycle"]["client_rules"])
    assert "reads 01" in rules and FIRMWARE_SERVICE_UUID in rules
    provision_notes = " ".join(characteristics()[PROVISION_CHARACTERISTIC_UUID]["notes"].split())
    assert "NEVER write here when the status reads 01" in provision_notes
    assert "locks out the vendor app and every other client until the next reset" in provision_notes
    connect_read = " ".join(by_target[PROVISION_CHARACTERISTIC_UUID]["notes"].split())
    assert "NEVER follow this read with a write when the value is 01." in connect_read
    weigh_in_notes = " ".join(characteristics()[WEIGH_IN_UUID]["notes"].split())
    assert "never reset a scale because nothing arrived" in weigh_in_notes
    prohibited = DETAILS["prohibited_writes"]
    assert "while its status reads 01" in prohibited["provisioning_when_provisioned"]
    # The feature characteristic is four bytes, one little-endian word.
    (feature_word,) = characteristics()["00002a9e-0000-1000-8000-00805f9b34fb"]["format"]
    assert (feature_word["offset"], feature_word["length"]) == (0, 4)
    assert (feature_word["type"], feature_word["endianness"]) == ("uint32", "little")


def test_every_client_rule_is_present_with_its_reason():
    """Each rule is a sentence an integrator acts on; deleting one must fail."""
    rules = {rule["rule"]: rule["reason"] for rule in DETAILS["key_lifecycle"]["client_rules"]}
    assert list(rules) == [
        "Never write to the provision characteristic when it reads 01.",
        "Never write to the provision characteristic of a scale you do not own.",
        "Never write a key you have not already stored somewhere safe.",
        f"Never write to any attribute of service {FIRMWARE_SERVICE_UUID}.",
        "Never treat a message whose tag fails as a reading, and never retry it with a guessed key.",
        "Never log, publish or commit a key, the scale's address or the Device Information serial number.",
        "Never lead a user into a factory reset, or into removing the scale from the vendor account, "
        "without first showing what it costs.",
        "Never suggest a reset because no message arrived.",
        "Never stay connected once the weigh-in has been read.",
        "Never connect without the key unless the owner asked for that connection, "
        "and disconnect as soon as the reads are done.",
    ]
    assert all(reason.strip() for reason in rules.values())
    keyless = rules[list(rules)[-1]]
    assert "only during a weigh-in" in keyless and "takes that weigh-in away from the vendor app" in keyless


def test_changing_phone_never_leads_to_a_reset():
    """The rejoin block is where an owner with a new phone looks; it must not send them to a reset."""
    rejoin = DEVICE["setup"]["rejoin"]
    assert rejoin["requires_factory_reset"] is False and rejoin["in_place_supported"] is True
    notes = " ".join(rejoin["notes"].split())
    assert notes.startswith("CHANGING PHONE IS NOT A REASON TO RESET")
    assert "VENDOR APP ON A NEW PHONE" in notes and "LOCAL CLIENT ON A NEW HOST" in notes
    assert notes.index("VENDOR APP ON A NEW PHONE") < notes.index("LOCAL CLIENT ON A NEW HOST")
    assert "sign in to the same account on the new phone" in notes
    assert "Do not remove the scale from the account and do not reset it." in notes
    assert "Not tested by this project" in notes and "Q11" in notes and "E7" in notes
    assert "no reported way to obtain it without a reset" in notes
    assert "A reset ends the vendor pairing" in notes and "setup.factory_reset.effect" in notes
    assert "the choice that costs nothing is to go on using the vendor app" in notes
    lowered = notes.lower()
    assert "only reported way forward" not in lowered and "way forward is then a reset" not in lowered

    steps = rejoin["steps"]
    assert steps and all(step["actor"] == "user" for step in steps)
    first = " ".join(steps[0]["action"].split())
    assert "sign in to the SAME account" in first
    assert "Do not remove the scale from the account, do not add it as a new device and do not reset it" in first
    last = " ".join(steps[-1]["expect"].split())
    assert "not something this project has tested" in last
    assert "do not reset the scale and do not remove it from the account" in last
    for step in steps:
        assert "request" not in step, "a phone change writes nothing to the scale"

    # The same answer as data.
    new_phone = DETAILS["key_lifecycle"]["new_phone"]
    assert new_phone["reset_needed"] is False and new_phone["removal_from_account_needed"] is False
    assert new_phone["vendor_app"]["verification"] == "reported"
    assert "Not tested by this project" in " ".join(new_phone["vendor_app"]["basis"].split())
    assert "not established" in new_phone["vendor_app"]["key_transfer"]
    without = " ".join(new_phone["local_client"]["without_the_key"].split())
    assert "Changing phone is not a reason to reset" in without and "ends the vendor pairing" in without

    # Wherever else the spec says a reset is the only way to something, the cost is in the same string.
    for text in strings(SPEC):
        flat_text = " ".join(text.split())
        if re.search(r"only (?:reported |other reported )?way[^.]*\breset\b", flat_text):
            assert re.search(r"ends the|pairing|set up again|fresh setup", flat_text), flat_text

    # The page gives the same two answers, under their own heading.
    page = flat(section(PAGE_TEXT, "### Rebinding to a new phone or network"))
    assert page.startswith("**Changing phone is not a reason to reset.**")
    assert "Sign in to the same account on the new phone and weigh in with the app open there" in page
    assert "**Do not remove the scale from the account and do not reset it.**" in page
    assert "Not tested by this project" in page and "Q11" in page
    assert "there is no reported way to obtain it without a reset" in page
    assert "a reset ends the vendor pairing" in page
    assert "loses nothing by staying with the vendor app" in page
    options = flat(section(PAGE_TEXT, "## What an owner can do, cheapest first"))
    assert "**New phone?** Sign in to the same account on the new phone" in options
    assert "Changing phone is not a reason to reset the scale or to remove it from the account" in options


def test_the_firmware_service_asserts_no_stack_default():
    (feature,) = SPEC["features"]
    dfu = feature["dfu"]
    assert feature["type"] == "firmware_update"
    assert dfu["mechanisms"] == ["unknown"]
    assert dfu["enter"]["how"] == "unknown"
    assert dfu["recovery"]["interrupted"] == "unknown"
    assert dfu["services"] == [FIRMWARE_SERVICE_UUID]
    assert "local_names" not in dfu["dfu_mode"] and "address_offset" not in dfu["dfu_mode"]
    service = next(s for s in SPEC["services"] if s["uuid"] == FIRMWARE_SERVICE_UUID)
    assert "characteristics" not in service
    assert "DO NOT WRITE" in service["notes"]

    # Listed as present on one source's word, do-not-write, recovery none known.
    assert dfu["verification"] == "reported"
    notes = " ".join(service["notes"].split())
    assert "RECOVERY: NONE KNOWN" in notes and "one unit, firmware A16" in notes
    assert " ".join(dfu["recovery"]["notes"].split()).startswith("None known.")
    assert (dfu["image"]["signing"], dfu["image"]["source"]) == ("unknown", "unknown")
    assert "transport" not in dfu and "algorithm" not in dfu["image"] and "encrypted" not in dfu["image"]
    # The stock Telink service is a negative about one listing, not about the scale.
    assert f"{TELINK_UPDATE_SERVICE_UUID} is not present in that one published listing" in notes
    assert "nobody has checked for it while the display shows otA" in notes
    assert TELINK_UPDATE_SERVICE_UUID not in {s["uuid"] for s in SPEC["services"]}
    assert TELINK_UPDATE_SERVICE_UUID not in PAGE_TEXT
    # No Nordic default appears anywhere, and nothing says whether the channel checks anything.
    for text in (SPEC_TEXT, PAGE_TEXT):
        lowered = text.lower()
        for default in ("00001531", "00001532", "00001534", "dfutarg", "0000fe59", "8ec9000"):
            assert default not in lowered, default
        for claim in (
            "unauthenticated",
            "unsigned image",
            "unsigned firmware",
            "is unsigned",
            "is signed",
            "signed image",
            "is authenticated",
            "crc-only",
            "crc only",
        ):
            assert claim not in lowered, claim
        # A side-load is only ever named to say there is none.
        assert lowered.count("side-load") == lowered.count("no firmware side-load")
    # No write surface and no entry command exist for it.
    assert "command" not in dfu["enter"] and "endpoint" not in dfu
    assert "does not connect it to this service" in " ".join(dfu["enter"]["notes"].split())


def test_the_subscription_trap_is_data():
    subscription = DETAILS["subscription"]
    assert subscription["declared_property"] == "indicate"
    assert subscription["descriptor"] == "00002902-0000-1000-8000-00805f9b34fb"
    assert subscription["vendor_app_descriptor_value_hex"] == "0100"
    assert subscription["standards_value_hex"] == "0200"
    assert subscription["standards_value_outcome"] == "unknown"
    assert subscription["characteristic"] == WEIGH_IN_UUID

    # No host stack is claimed to work, and none is claimed to fail.
    hosts = {row["stack"]: row for row in DEVICE["host_compatibility"]}
    assert set(hosts) == {"bluez", "corebluetooth"}
    assert (hosts["bluez"]["status"], hosts["bluez"]["verification"]) == ("unknown", "reported")
    # The Apple row is an inference from platform documentation, never a report.
    apple = hosts["corebluetooth"]
    assert (apple["status"], apple["verification"]) == ("unknown", "hypothesis")
    for row in hosts.values():
        assert row["basis"].strip() and row["notes"].strip()
        assert "symptom" not in row and "workaround" not in row
    assert "proxy" in hosts["bluez"]["notes"].lower()
    unverified = " ".join(subscription["unverified_hosts"])
    assert "BlueZ" in unverified and "CoreBluetooth" in unverified and "prox" in unverified


def test_host_timings_keep_the_attended_and_unattended_values_apart():
    """0.4 s is an attended tool's retry sleep; an always-on client spaces attempts 15 s apart."""
    timings = DETAILS["connection"]["host_policy_timings"]
    assert set(timings) == {"notes", "attended_reader", "unattended_integration"}
    attended, unattended = timings["attended_reader"], timings["unattended_integration"]
    assert attended["context"].strip() and unattended["context"].strip()
    assert attended["connect_retry_interval_s"] == 0.4
    assert attended["connect_attempt_timeout_s"] == 2.5
    assert attended["keeps_trying_for_s"] == 180, "the fast retry is bounded"
    assert "connect_retry_interval_s" not in unattended
    assert unattended["timer_fallback_interval_s"] == 15
    assert unattended["timer_fallback_default"] == "disabled"
    assert unattended["pause_between_sessions_s"] == 3
    assert (
        unattended["give_up_connecting_after_s"],
        unattended["give_up_without_data_after_s"],
        unattended["disconnect_after_last_reading_s"],
        unattended["session_cap_s"],
    ) == (30, 30, 20, 120)
    assert unattended["timer_fallback_interval_s"] > 30 * attended["connect_retry_interval_s"]


def test_the_open_questions_and_experiments_are_written_down():
    unknowns = SPEC["remaining_unknowns"]
    question_ids = {f"Q{number}" for number in range(1, 23)}
    for question in question_ids:
        assert sum(line.startswith(f"{question}.") for line in unknowns) == 1, question
    assert SPEC["evidence"]["open_questions"]
    conflict_ids = {c["id"] for c in DETAILS["conflicts"]}
    assert conflict_ids == {f"C{n}" for n in range(1, 8)}

    experiments = DETAILS["owner_experiments"]["experiments"]
    experiment_ids = [e["id"] for e in experiments]
    assert experiment_ids == [f"E{n}" for n in range(1, 13)]
    assert [e["id"] for e in experiments if e["needs_vendor_app"]] == ["E7", "E11", "E12"]
    for experiment in experiments:
        assert experiment["closes"] and experiment["steps"] and experiment["cost"].strip()
        assert set(experiment["closes"]) <= question_ids | conflict_ids, experiment["id"]
        for step in experiment["steps"]:
            assert step["actor"] in {"user", "client"}, step
            assert step["action"].strip()
    # Every experiment a conflict or an open question points at exists.
    for conflict in DETAILS["conflicts"]:
        assert conflict.get("experiment", "E1") in experiment_ids, conflict["id"]
    for line in unknowns:
        for cited in re.findall(r"\bE\d+\b", line):
            assert cited in experiment_ids, line
    # The second research round's questions each name the cheapest way to settle them.
    by_question = {line.split(".", 1)[0]: line for line in unknowns if re.match(r"Q\d+\.", line)}
    for question in ("Q17", "Q22"):
        assert re.search(r"\(E\d+", by_question[question]), question
    for question in ("Q18", "Q19", "Q20", "Q21"):
        assert "Cheapest" in by_question[question], question
    # The two that need the case open and equipment attached say what that risks, right there.
    assert "never mains-powered equipment while a person is on the scale" in by_question["Q19"]
    assert "Never an erase or a write" in by_question["Q20"] and "unrecoverable" in by_question["Q20"]
    assert "lifting the module, which can destroy the board" in by_question["Q20"]
    for question in ("Q19", "Q20"):
        assert "Not an owner experiment" in by_question[question]
        # Each line is rendered on its own, so each carries the mains warning itself.
        assert "never mains-powered equipment while a person is on the scale" in by_question[question]
        assert "dead weight" in by_question[question]
        assert "attery-powered or isolated equipment" in by_question[question]
    pads = next(line for line in unknowns if "DOWN, SET, UP and UNIT" in line)
    assert "Do not bridge them" in pads
    assert "never unpair a working scale" in by_question["Q17"]
    assert any("Cheapest experiment" in line for line in SPEC["evidence"]["open_questions"])


def test_an_experiment_that_resets_the_scale_says_so_in_its_cost():
    """`cost` is the field an owner reads before starting; a reset is never 'None'."""
    by_id = {e["id"]: e for e in DETAILS["owner_experiments"]["experiments"]}
    for experiment in by_id.values():
        actions = " ".join(step["action"] for step in experiment["steps"])
        holds_the_button = bool(re.search(r"Factory-reset the scale|reset hold|otA", actions))
        assert experiment["resets_scale"] is holds_the_button, experiment["id"]
        if experiment["resets_scale"]:
            assert experiment["cost"].strip().startswith("A factory reset"), experiment["id"]
        else:
            assert "factory reset" not in experiment["cost"].lower(), experiment["id"]
    assert {e["id"] for e in by_id.values() if e["resets_scale"]} == {"E1", "E10"}
    for reset_id in ("E1", "E10"):
        assert "vendor" in by_id[reset_id]["cost"], "a reset costs the vendor pairing; say so"
    # Nothing that needs the vendor app asks an owner to unpair a working scale for it.
    e7 = " ".join(step["action"] for step in by_id["E7"]["steps"])
    assert "do not remove the scale from the account" in e7 and "Do not add the scale as a new device" in e7
    assert by_id["E11"]["steps"][0]["action"].startswith("Only when a setup is about to happen anyway")
    assert "Never remove a working scale" in " ".join(by_id["E11"]["cost"].split())
    notes = " ".join(DETAILS["owner_experiments"]["notes"].split())
    assert "No experiment here is a reason to unpair or reset a scale that works" in notes
    # The read-only listing no longer asks anyone to hold the button.
    assert all(step["actor"] == "client" for step in by_id["E6"]["steps"])
    assert by_id["E6"]["cost"].startswith("None")
    # The reset-hold observation never has the owner stop at the update stage.
    hold = " ".join(step["action"] for step in by_id["E10"]["steps"])
    assert "without releasing at otA" in hold
    assert "released" in by_id["E10"]["cost"] and "clr" in by_id["E10"]["cost"]
    # No owner experiment opens the case: the notes send those to hardware_research.
    assert "Experiments that need the case opened are not owner experiments" in notes
    assert by_id["E9"]["cost"].startswith("None") and "The case stays closed." in by_id["E9"]["cost"]
    e9 = " ".join(step["action"] for step in by_id["E9"]["steps"])
    assert "Do not open the scale for this" in e9 and "it may not survive" in e9
    for experiment in by_id.values():
        told = " ".join([experiment["cost"]] + [step["action"] for step in experiment["steps"]])
        assert not re.search(r"(?<!Do not )\bopen(?:ing)? the (?:scale|case)\b", told), experiment["id"]
    # A connection is made during a weigh-in and takes it from the vendor app:
    # every experiment that connects a local client says so in its cost.
    for connects in ("E2", "E3", "E4", "E6", "E8"):
        assert "may never reach the vendor app" in by_id[connects]["cost"], connects
    assert "no connection" in by_id["E5"]["cost"]
    assert "holding it starts the reset" in by_id["E2"]["cost"]
    # Read-only means read-only, and it is said in the step itself.
    assert by_id["E6"]["steps"][0]["action"].endswith("Enumerate and read only.")
    assert "Read only: write nothing at all, not even a subscription descriptor." in hold
    assert by_id["E10"]["steps"][-1]["action"].endswith("Write nothing.")
    assert "never write to the firmware-update service" in notes
    # The unit sweep starts in the unit the owner already uses.
    assert "already set to" in by_id["E2"]["steps"][0]["action"]
    assert by_id["E2"]["outcome"].strip()
    # The keyless stream is looked at before the key is written.
    e1 = [step["action"] for step in by_id["E1"]["steps"]]
    before_write = next(i for i, action in enumerate(e1) if "status 00" in action)
    write = next(i for i, action in enumerate(e1) if action.startswith("Write 16"))
    assert before_write < write


# --- what an owner can do, and what stays a research note --------------------


def test_the_routes_are_ordered_by_what_they_cost_the_owner():
    routes = DETAILS["key_routes"]["routes"]
    assert [route["id"] for route in routes] == [
        "leave_paired",
        "read_the_display_with_a_camera",
        "identify_without_a_key",
        "capture_key_from_bluetooth_log",
        "own_key_after_reset",
    ]
    free, costly = routes[:3], routes[3:]
    for route in free:
        assert route["is_setup_method"] is False
        assert route["pairing_impact"].startswith("none") and route["scale_risk"].startswith("none")
    # The two that end the pairing are exactly the two setup methods, and say so the same way.
    methods = {method["name"]: method for method in DEVICE["setup"]["methods"]}
    assert [route["title"] for route in costly] == list(methods)
    for route in costly:
        assert route["is_setup_method"] is True and route["verified"] is False
        assert methods[route["title"]]["verified"] is route["verified"]
        assert "factory reset" in route["starts_with"]
        assert route["pairing_impact"].startswith("Ends the")
        assert route["scale_risk"].startswith("recoverable")
        assert route["failure_state"].strip() and len(route["warnings"]) == 4
    capture, own_key = costly
    # The warnings the second round's reviewer requires, by content and in order.
    assert capture["warnings"] == [
        "The present pairing and key are lost at the first step.",
        "It depends on the vendor app completing a fresh setup.",
        "The scale serves one client at a time.",
        "The log holds the key and all the phone's other Bluetooth traffic: do not share it.",
    ]
    assert own_key["warnings"] == [
        "It ends the current vendor pairing.",
        "Record the key before writing it.",
        "If weigh-ins do not decrypt, reset again.",
        "Untested on any firmware its source could name.",
    ]
    # Reading without a key is free for the scale, not for the weigh-in it takes.
    route_notes = " ".join(DETAILS["key_routes"]["notes"].split())
    assert "The first two cost nothing at all; the third can cost the weigh-in" in route_notes
    assert "BOTH end the present vendor pairing before they give anything back" in route_notes
    identify = routes[2]
    assert identify["must_not"] == (
        f"Write to the provision characteristic or to anything under service {FIRMWARE_SERVICE_UUID}."
    )
    assert "may never reach the vendor app" in identify["pairing_impact"]
    assert identify["connect_only"].startswith("when the owner asks, and disconnect as soon as the reads are done")
    # Only what both parties report is graded as two-party.
    two_party, one_party = identify["evidence"].split(";")[:2]
    assert two_party.startswith("two parties for") and "handle" not in two_party and "prefix" not in two_party
    assert "January 2025 capture alone" in one_party and "handle" in one_party and "address prefix" in one_party
    assert capture["starts_with"] == ["remove the scale from the vendor account", "factory reset"]
    assert capture["failure_state"] == "Unpaired, with an app that will not re-pair."
    assert (capture["hardware_revision"], capture["firmware_revision"]) == ("H01", "A16")
    assert capture["vendor_app_5_12_tested"] is False
    assert "one party" in capture["evidence"] and "not reproduced end to end" in capture["evidence"]
    assert (own_key["reports"], own_key["scales_tested"]) == (1, 1)
    assert own_key["firmware_stated"] is False and own_key["reproduced"] is False
    assert "AI assistant" in own_key["evidence"]
    assert "Record the key before writing it." in own_key["warnings"]
    assert "names no tool" in own_key["needs"]

    # The baseline costs nothing and is said first, where an owner reads.
    assert "safest" in " ".join(routes[0]["basis"].split())
    notes = " ".join(DEVICE["notes"].split())
    assert "LEAVE A WORKING PAIRING ALONE" in notes
    assert "BEGIN by removing the scale from the vendor account and factory-resetting it" in notes

    # The camera-reading app: its licence, what its author tested, and its limits.
    camera = routes[1]
    assert camera["project"] == "drinkcat/SmarterScale" and camera["licence"] == "Apache-2.0"
    assert camera["project_url"] in {link["url"] for link in SPEC["helpful_urls"]}
    assert "Aria Air only" in camera["tested_by_its_author_on"]
    assert camera["limits"][:2] == ["Kilograms only.", "The position of the decimal point is assumed, not read."]
    assert "not run or reviewed by this project" in camera["evidence"]

    # What has no public basis is listed as that, never as a route.
    assert {entry["id"] for entry in DETAILS["key_routes"]["no_public_basis"]} == {
        "existing_key_without_a_reset",
        "setup_write_from_the_air",
    }
    not_covered = " ".join(SPEC["local_access"]["not_covered"])
    assert "without first ending the present vendor pairing: no route is known" in not_covered


def test_the_hardware_notes_are_notes_and_carry_their_warnings():
    research = DETAILS["hardware_research"]
    status = " ".join(research["status"].split())
    assert "Nothing in this block is a route, a setup method or a recommendation" in status
    assert "No wiring, programming or flashing procedure is given" in status
    opening = " ".join(research["before_opening_the_case"].split())
    assert "not serviceable" in opening and "nobody has published a teardown" in opening
    assert "Never connect mains-powered equipment" in opening and "dead weight" in opening

    notes = {note["id"]: note for note in research["notes"]}
    assert set(notes) == {"H1", "H2", "H3"}
    for note in notes.values():
        assert note["evidence"].strip() and note["statement"].strip()
        assert "steps" not in note and "procedure" not in note
    chip = " ".join(notes["H1"]["statement"].split())
    assert "Telink TLSR8261 on a Transtek module whose underside carries pads" in chip
    assert "Nobody has reported connecting to them." in chip
    assert "No public programmer lists this chip as tested" in chip
    assert "unrecoverable" in notes["H1"]["risk"]
    assert "inference" in notes["H2"]["evidence"] and notes["H2"]["open_question"] == "Q19"
    tap_risk = " ".join(notes["H2"]["risk"].split())
    assert tap_risk.startswith("Unknown.") and "receive-only tap is electrically passive" in tap_risk
    assert "can destroy the board" in tap_risk and "can destroy the board" in notes["H1"]["risk"]
    for note_id, field in (("H1", "risk"), ("H2", "risk"), ("H3", "consequence")):
        assert notes[note_id][field].strip(), f"{note_id} says what it would risk"
    retrofit = " ".join(notes["H3"]["consequence"].split())
    assert "ends the Fitbit function" in retrofit and "known weights" in retrofit
    assert "no instructions exist" in retrofit and "isolated from the mains" in retrofit

    hardware = DETAILS["hardware"]
    assert hardware["soc_marking"] == "TLSR8261 F512ET32"
    assert hardware["module_pads_labelled"] == ["VDD", "GND", "SWS", "RXD", "TXD"]
    assert "underside" in hardware["module_pads_location"]
    assert hardware["serviceable"] is False
    (pad_note,) = [line for line in hardware["other_photo_observations"] if "UNIT" in line]
    assert "do not bridge or drive them" in pad_note
    assert "not an established fact" in pad_note, "the back-button reading is an inference from a photograph"

    # None of it is a setup method, a feature or a command, and nothing here is a recipe:
    # no line speed, no programmer or amplifier named, no claim that the firmware can be read.
    assert {method["type"] for method in DEVICE["setup"]["methods"]} == {"cloud_account", "ble_provisioning"}
    assert [feature["type"] for feature in SPEC["features"]] == ["firmware_update"]
    for text in (SPEC_TEXT, PAGE_TEXT):
        lowered = " ".join(text.lower().split())
        assert not re.search(r"\b(?:9600|19200|38400|57600|115200|230400|921600)\b", lowered), "no baud rate is known"
        for name in ("tlsrcomprog", "tlsrtools", "tlsrpgm", "pvvx", "hx711", "ads1232", "floader"):
            assert name not in lowered, name
        for claim in ("can be dumped", "can be reflashed", "dump the firmware", "flash a patched"):
            assert claim not in lowered, claim


def test_two_party_corroboration_lists_only_what_both_parties_report():
    """The public implementation gives no handle number and no address prefix."""
    corroboration = SPEC["evidence"]["corroboration"]
    two_parties = " ".join(corroboration["two_parties"])
    for one_party_fact in ("0x0019", "handle 0x", "A4:C1:38", "address prefix"):
        assert one_party_fact not in two_parties, one_party_fact
    assert "delivery as an indication" in corroboration["two_parties"]
    capture_only = " ".join(corroboration["january_2025_capture_only"])
    assert "value handle 0x0019" in capture_only and "address prefix A4:C1:38" in capture_only
    assert "not a second observation of the prefix" in capture_only
    (prefix,) = DEVICE["identification"]["mac_prefixes"]
    assert prefix["confidence"] == "low" and "One unit, one capture." in " ".join(prefix["notes"].split())
    assert "January 2025 capture only" in DETAILS["subscription"]["handles_seen"]["weigh_in_value"]

    rows = {row[0]: row[1] for row in table_rows(section(PAGE_TEXT, "## Verification and unknowns")) if len(row) == 2}
    two_party_row = next(fact for fact, standing in rows.items() if standing.startswith("Two independent parties"))
    assert "prefix" not in two_party_row and "handle" not in two_party_row.lower()
    capture_row = next(standing for fact, standing in rows.items() if "address prefix `A4:C1:38`" in fact)
    assert capture_row.startswith("The January 2025 capture only") and "not a second observation" in capture_row


def test_the_sentences_an_owner_acts_on_are_where_an_owner_reads_them():
    """Each of these can be deleted without touching a field; each is pinned by a short phrase."""
    pairing = DEVICE["pairing"]
    notes = " ".join(pairing["notes"].split())
    assert "That is NOT a reason to go and capture the key from a scale that works" in notes
    assert "starts by removing the scale from the account and resetting it" in notes
    unpair = " ".join(pairing["unpair"]["notes"].split())
    assert "which ends the vendor pairing and leaves the scale needing a fresh setup" in unpair

    links = {link["url"]: " ".join(link["description"].split()) for link in SPEC["helpful_urls"]}
    implementation = next(text for url, text in links.items() if url.endswith("/tree/d43708a1eb6acee368bde5a06b34208c9ece88f8"))
    assert "starts by removing the scale from the vendor account and resetting it" in implementation
    assert "read device.setup before following it" in implementation
    sync_help = links["https://support.google.com/googlehealth/answer/14236618"]
    assert "try the earlier steps first" in sync_help and "Q11" in sync_help
    assert "this spec cannot say what a reinstall does to it" in sync_help
    assert "None of its Aria Air steps removes the scale itself from the account or resets it." in sync_help
    notice = links["https://support.google.com/googlehealth/answer/14236805"]
    assert "ended on 9 November 2026" in notice and "trust it over this line" in notice
    camera = links["https://github.com/drinkcat/SmarterScale"]
    assert "Not run or reviewed by this project." in camera and "proxy" not in camera
    fcc = links["https://fccid.io/XRAFB203"]
    assert "they are not instructions for opening the scale" in fcc

    # The page: the sibling-scale owner, the reset hold, the trap box, the never-do list,
    # the experiments and the reference to the implementation.
    overview = flat(section(PAGE_TEXT, "## Overview"))
    assert (
        "For a scale that takes AA cells, pairing and re-pairing have already ended by Google's current notice: "
        "one that is unpaired cannot be paired again, so leave a working one paired and do not reset it."
    ) in overview
    assert "it is not a promise about the future" in overview
    assert overview.count("pairing and re-pairing have already ended") == 2
    reset = flat(section(PAGE_TEXT, "### Factory reset"))
    assert "once you are resetting, keep holding until `clr`" in reset
    assert "Do not reset as casual troubleshooting" in reset
    trap = flat(section(PAGE_TEXT, "### Receiving a weigh-in"))
    assert "Never reset a scale because nothing arrived." in trap
    never = flat(section(PAGE_TEXT, "### What a client must never do"))
    for bullet in (
        "- Write a key it has not already stored somewhere safe, or write to a scale its user does not own.",
        "- Write anything to the firmware-update service. No recovery is known.",
        "- Lead a user into a factory reset, or into removing the scale from the vendor account, without first showing what it costs.",
        "- Suggest a reset because no message arrived.",
        "- Stay connected once the reading is in.",
        "- Connect on its own when it does not hold the key.",
        "- Log, publish or commit a key, the scale's address or its serial number.",
    ):
        assert bullet in never, bullet
    assert "Connect only when the owner asks, and disconnect as soon as the reads are done." in never
    pairing_page = flat(section(PAGE_TEXT, "## Pairing"))
    assert "A local client should disconnect as soon as it has the reading" in pairing_page
    experiments = flat(section(PAGE_TEXT, "### Experiments an owner can run"))
    assert "Never write to the firmware-update service" in experiments
    references = flat(section(PAGE_TEXT, "## References"))
    assert "Its documented way of getting the key starts by removing and resetting the scale." in references
    hardware = flat(section(PAGE_TEXT, "## Hardware"))
    assert "not an established fact" in hardware and "could act as holding the button that starts the reset" in hardware


def test_the_negative_findings_are_recorded_as_negatives():
    findings = " ".join(DETAILS["negative_findings"])
    assert "Nothing to redirect: the scale has no Wi-Fi and no route to a server" in findings
    assert f"by service {WEIGHT_SCALE_SERVICE_UUID} alone will claim this scale and then get nothing" in findings
    assert "none of those services or characteristics is reported here" in findings
    assert "not verified as one company" in findings
    assert f"{TELINK_UPDATE_SERVICE_UUID} is not present in the one published GATT listing" in findings
    assert "Not checked while the display shows otA" in findings
    assert "No weight in the advertisement" in findings and "None found" in findings
    assert "No public basis for capturing the key without a reset" in findings
    assert "NO WI-FI, SO NOTHING TO REDIRECT" in DEVICE["notes"]
    assert "cloud" not in SPEC, "a scale with no network path has no egress to list"


def test_what_was_taken_from_the_unlicensed_source_is_stated_as_facts():
    """A claim that no text was taken cannot be checked by a reader; what was taken can."""
    for text in (SPEC_TEXT, PAGE_TEXT):
        lowered = " ".join(text.lower().split())
        assert "no text" not in lowered
        assert "facts" in lowered and "own words" in lowered
    assert "NO licence file" in DEVICE["openness"]["notes"]
    review = " ".join(SPEC["evidence"]["public_implementation"].split())
    assert "shared runs of six or more words" in review


# --- hygiene -----------------------------------------------------------------


def test_only_synthetic_identifiers_appear():
    assert KEY == b"liberatedbread!!", "the only key in the file is the invented one"
    assert "synthetic" in VECTORS["provenance"].lower()
    full_mac = re.compile(r"\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b")
    for text in (SPEC_TEXT, PAGE_PATH.read_text(encoding="utf-8")):
        for address in full_mac.findall(text):
            assert address.lower().startswith("00:00:5e:00:53:"), address
        private = r"\b(?:10\.\d{1,3}|192\.168|172\.(?:1[6-9]|2\d|3[01]))\.\d{1,3}\.\d{1,3}\b"
        assert not re.search(private, text), "no LAN address belongs in a BLE-only spec"
    # 32 hex digits in a row are key-shaped: only the synthetic key may be one.
    for run in re.findall(r"\b[0-9a-f]{32}\b", SPEC_TEXT):
        assert run == VECTORS["key_hex"], run


def test_every_uuid_is_lowercase_and_full_length():
    shape = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
    seen = [service["uuid"] for service in SPEC["services"]] + list(characteristics())
    seen += [step["characteristic"] for step in SPEC["initialization"]]
    assert len(seen) == len(SPEC["services"]) + len(characteristics()) + 2
    for uuid in seen:
        assert shape.match(uuid), uuid
    assert not re.search(r"\b0x181D\b|\b0x2A9[DE]\b", SPEC_TEXT), "short UUIDs are lowercase in prose too"


# --- the identifiers a client acts on ---------------------------------------


def test_the_gatt_table_is_exactly_the_reported_one():
    declared = {
        service["uuid"]: {c["uuid"]: c["name"] for c in service.get("characteristics") or []}
        for service in SPEC["services"]
    }
    assert declared == GATT_TABLE
    assert [service["uuid"] for service in SPEC["services"]] == list(GATT_TABLE), "service order"
    for uuid, members in GATT_TABLE.items():
        service = next(s for s in SPEC["services"] if s["uuid"] == uuid)
        if not members:
            assert service["notes"].strip(), "a service with no characteristics says why"
    names = {service["uuid"]: service["name"] for service in SPEC["services"]}
    assert names[GENERIC_ACCESS_SERVICE_UUID] == "Generic Access"
    assert names[DEVICE_INFORMATION_SERVICE_UUID] == "Device Information"
    assert names[WEIGHT_SCALE_SERVICE_UUID].startswith("Weight Scale")
    assert names[PROVISION_SERVICE_UUID].startswith("Provisioning")
    assert names[FIRMWARE_SERVICE_UUID].startswith("Firmware update")
    for uuid in GATT_TABLE[DEVICE_INFORMATION_SERVICE_UUID]:
        assert characteristics()[uuid]["properties"] == ["read"]
        assert characteristics()[uuid]["verification"] == "reported"


def test_every_uuid_written_anywhere_is_one_the_table_knows():
    """One wrong hex digit in any occurrence, structured or prose, lands outside this set."""
    for name, text in (("spec", SPEC_TEXT), ("page", PAGE_TEXT)):
        found = UUID_SHAPED.findall(text)
        assert found, name
        for uuid in found:
            assert uuid == uuid.lower(), f"{name}: {uuid}"
            assert uuid in KNOWN_UUIDS, f"{name}: {uuid} is not a UUID this scale is reported to use"
    assert set(UUID_SHAPED.findall(SPEC_TEXT)) == KNOWN_UUIDS, "each known UUID is used at least once"
    # The feature characteristic the scale HAS is one hex digit from the measurement
    # characteristic it LACKS. The first is written once, where it is declared; every
    # prose mention is of the second.
    assert SPEC_TEXT.count("00002a9e-0000-1000-8000-00805f9b34fb") == 1
    assert "00002a9e-0000-1000-8000-00805f9b34fb" not in PAGE_TEXT
    assert f"Weight Measurement characteristic {WEIGHT_MEASUREMENT_UUID}" in DEVICE["notes"]
    # Anything UUID-like that the strict pattern skipped (wrong group length) is a typo.
    loose = re.findall(r"[0-9A-Fa-f]{6,}-[0-9A-Fa-f]{3,}-[0-9A-Fa-f]{3,}-[0-9A-Fa-f]{3,}-[0-9A-Fa-f]{6,}", SPEC_TEXT + PAGE_TEXT)
    assert set(loose) <= KNOWN_UUIDS


def test_every_structured_uuid_reference_points_where_it_says():
    """A known UUID in the wrong place (service for characteristic) is still wrong."""
    declared = characteristics()
    assert [step["characteristic"] for step in SPEC["initialization"]] == [PROVISION_CHARACTERISTIC_UUID, WEIGH_IN_UUID]
    assert DETAILS["subscription"]["descriptor"] == CLIENT_CONFIGURATION_DESCRIPTOR_UUID
    (intended,) = DETAILS["entity_coverage"]["intended"]
    assert intended["source_characteristic"] == WEIGH_IN_UUID
    assert intended["source_field"] == DECODING["raw_field"]
    (feature,) = SPEC["features"]
    assert feature["dfu"]["services"] == [FIRMWARE_SERVICE_UUID]

    requests = []
    for method in DEVICE["setup"]["methods"]:
        for phase in method.get("stages") or [method]:
            requests += [step["request"] for step in phase["steps"] if "request" in step]
    with_service = [request for request in requests if "service" in request]
    assert len(with_service) == 5, "one subscribe in the vendor route; two reads, a write and a subscribe in the own-key route"
    for request in with_service:
        assert request["protocol"] == "ble_gatt"
        members = GATT_TABLE[request["service"]]
        (target,) = UUID_SHAPED.findall(request["action"])
        assert target in members, f"{target} is not a characteristic of {request['service']}"
        verb = request["action"].split(" ", 1)[0]
        assert verb in {"read", "write", "subscribe"}
        wanted = {"read": "read", "write": "write", "subscribe": "indicate"}[verb]
        assert wanted in declared[target]["properties"], request["action"]
    by_verb = sorted(request["action"].split(" ", 1)[0] for request in with_service)
    assert by_verb == ["read", "read", "subscribe", "subscribe", "write"]

    # The Route 1 log search names the characteristic the key is written to.
    extract = DEVICE["setup"]["methods"][0]["stages"][1]["steps"][0]["action"]
    assert UUID_SHAPED.findall(extract) == [PROVISION_CHARACTERISTIC_UUID]
    rules = DETAILS["key_lifecycle"]["client_rules"]
    assert sum(FIRMWARE_SERVICE_UUID in rule["rule"] for rule in rules) == 1
    assert FIRMWARE_SERVICE_UUID in DETAILS["prohibited_writes"]["firmware_update"]


def test_the_cipher_names_its_characteristic_its_fields_and_its_plaintext_format():
    """A consumer walking fields can get from the characteristic to a weight without prose."""
    assert CIPHER["characteristic"] == WEIGH_IN_UUID
    wire_names = [field["name"] for field in characteristics()[WEIGH_IN_UUID]["format"]]
    assert [CIPHER["nonce_field"], CIPHER["tag_field"], CIPHER["ciphertext_field"]] == wire_names
    assert sorted(CIPHER["library_order"]) == sorted([CIPHER["ciphertext_field"], CIPHER["tag_field"]])
    assert CIPHER["plaintext_format"] == DECODING["payload_format"] == "WeighInPlaintext"
    plaintext = SPEC["payload_formats"][CIPHER["plaintext_format"]]["fields"]
    assert sum(field["length"] for field in plaintext) == CIPHER["plaintext_bytes"]
    assert {DECODING["raw_field"], DECODING["flags_field"]} == {field["name"] for field in plaintext}
    assert "encryption" not in characteristics()[WEIGH_IN_UUID], "the schema's vocabulary has no AES-CCM"


# --- the weight decision, as data --------------------------------------------


def test_the_decision_table_covers_every_case_exactly_once():
    table = DECODING["decision_table"]
    assert set(table["inputs"]) == {"display_unit", "flags", "stored_flags"}
    rows = table["rows"]
    keys = [(row["display_unit"], row["flags_bit0"]) for row in rows]
    assert sorted(keys) == sorted((unit, bit) for unit in DECODING["unit_modes"] for bit in (0, 1))
    assert len(set(keys)) == len(keys)
    actions = set(table["actions"])
    assert actions == {"publish", "owner_confirm", "refuse", "stop_and_reconfirm", "drop"}
    for row in rows:
        assert row["action"] in actions and row["why"].strip()
        assert ("unit" in row and "scale" in row) is (row["action"] == "publish")
        assert ("candidates" in row) is (row["action"] == "owner_confirm")
    assert [(g["id"], g["action"]) for g in table["guards"]] == [
        ("tag_failed", "drop"),
        ("unknown_flags", "refuse"),
        ("flags_changed", "stop_and_reconfirm"),
    ]


@pytest.mark.parametrize("display_unit", ["lb", "kg", "st"])
@pytest.mark.parametrize("flags", [0, 1])
def test_a_row_publishes_only_where_both_readings_agree(display_unit, flags):
    """Derived from `readings`, not restated: publish needs one (unit, scale) from both."""
    row = decide(display_unit, flags)
    per_reading = set()
    for reading in DECODING["readings"]:
        if reading["unit_selected_by"] == "flags_bit0":
            unit = reading["flags_bit0_units"][str(flags & 1)]
        else:
            unit = display_unit
        per_reading.add((unit, reading["scales"].get(unit)))
    settled = len(per_reading) == 1 and None not in {scale for _, scale in per_reading}

    if row["action"] == "publish":
        assert settled, "a publishing row where the readings disagree picks a side"
        assert per_reading == {(row["unit"], row["scale"])}
    else:
        assert not settled, "the readings agree here; refusing would hide a settled case"
    if row["action"] == "owner_confirm":
        assert display_unit == "kg"
        offered = {(c["unit"], c["scale"]) for c in row["candidates"]}
        assert offered == {("kg", c["scale"]) for c in DECODING["unit_modes"]["kg"]["candidates"]}
        assert row["if_none_match"] == "refuse", "nobody has shown the wire unit follows the display"
    if display_unit == "st":
        assert row["action"] == "refuse"


def test_the_guards_stop_a_stale_or_unknown_flags_byte():
    assert decide("lb", 1, tag_ok=False)["action"] == "drop"
    for flags in (2, 3, 0x80, 0xFF):
        assert decide("lb", flags)["action"] == "refuse"
        assert decide("kg", flags)["action"] == "refuse"
    # The unit button is the reset button: a changed flags byte means ask again.
    assert decide("kg", 1, stored_flags=0)["action"] == "stop_and_reconfirm"
    assert decide("lb", 0, stored_flags=1)["action"] == "stop_and_reconfirm"
    assert decide("lb", 1, stored_flags=1)["action"] == "publish"
    assert decide("lb", 0)["action"] == "refuse", "pounds with bit 0 clear is where the readings part"
    # The prose rules say the same things as the table.
    rules = " ".join(DECODING["client_rule"])
    assert "pounds and flags bit 0 clear: do not publish" in rules
    assert "neither candidate equals the display: do not publish" in rules
    assert "stop publishing and ask the owner again" in rules
    assert "Do not infer it" in rules


@pytest.mark.parametrize("vector", VECTORS["vectors"], ids=VECTOR_IDS)
def test_each_vector_takes_the_row_its_stated_decodes_imply(vector):
    flags, raw = parse_plaintext(open_message(KEY, bytes.fromhex(vector["message_hex"])))
    display_unit = next(e["display_unit"] for e in vector["decoded"] if "display_unit" in e)
    row = decide(display_unit, flags)
    if vector["readings_agree"]:
        assert row["action"] == "publish"
        published = Decimal(raw) * Decimal(str(row["scale"]))
        assert {(row["unit"], published)} == {
            (entry["unit"], Decimal(str(entry["value"]))) for entry in vector["decoded"]
        }
    else:
        assert row["action"] == "owner_confirm"
        offered = {Decimal(raw) * Decimal(str(c["scale"])) for c in row["candidates"]}
        assert offered == {Decimal(str(entry["value"])) for entry in vector["decoded"]}


# --- the device page says what the spec says ---------------------------------


def numbered_steps(text: str) -> list[str]:
    steps: list[str] = []
    for line in text.splitlines():
        if re.match(r"\d+\. ", line):
            steps.append(line)
        elif steps and line.startswith("   "):
            steps[-1] += " " + line.strip()
        elif steps and not line.strip():
            break
    return steps


def flat(text: str) -> str:
    return " ".join(text.split())


def test_the_page_header_and_overview_carry_the_spec_status():
    assert re.search(r"^\| Pairing required \| Yes\b", PAGE_TEXT, re.MULTILINE)
    assert "scripts/test_fitbit_aria_air_spec.py" in PAGE_TEXT
    status_line = next(
        line for line in PAGE_TEXT.splitlines() if line.startswith("> **Manufacturer Status**")
    )
    assert "Active" in status_line and "not part of" in status_line
    overview = flat(section(PAGE_TEXT, "## Overview"))
    cutoff = DETAILS["vendor_status"]["pairing_cutoff"]
    observed = cutoff["notice_edit_observed"]

    # The current date, in the past tense; the old one only as a dated observation.
    year, month, day = cutoff["date"].split("-")
    assert month == "11"
    assert cutoff["date"] in status_line and "ended" in status_line
    assert observed["earlier_date"] not in status_line
    assert f"ended on {int(day)} November {year} with app version {cutoff['app_version']}" in overview
    assert f'"{cutoff["aria_air_statement"].rstrip(".")}"' in overview
    assert "pairing and re-pairing have already ended" in overview
    assert "05:11 UTC on 2026-11-23" in overview and "by 23:07 UTC the same day" in overview
    assert "German, French and Japanese editions still said 28 November" in overview
    for paragraph in re.split(r"\n\s*\n", PAGE_TEXT):
        if STALE_DATE.search(flat(paragraph)):
            assert CURRENT_DATE.search(flat(paragraph)), paragraph
    # The old date is named once, inside the dated observation, and nowhere else.
    assert len(STALE_DATE.findall(flat(PAGE_TEXT))) == 2, "once for the English edit, once for the other editions"
    assert all(STALE_DATE.search(flat(p)) is None for p in re.split(r"\n\s*\n", PAGE_TEXT) if "Three AAA cells" in p)
    assert not TIME_LEFT.search(flat(PAGE_TEXT)), "nobody is told there is time left"

    # The owner-safety statement comes before anything about getting a key.
    tip = overview.index("If your Aria Air works today, the safest thing to do is nothing")
    assert tip < overview.index("Three things to know before anything else")
    assert "**begin by removing the scale from your account and factory-resetting it.**" in overview
    assert "Nothing here is a reason to unpair or reset a scale that works" in overview

    # Which Aria: an owner of a sibling scale must not read this page as theirs.
    assert "Three AAA cells" in overview and "Four AA cells" in overview and '"Aria 2"' in overview
    assert "**only**" in overview
    (sibling,) = re.findall(r"\]\((fitbit-aria[\w-]*\.md)\)", section(PAGE_TEXT, "## Overview"))
    assert (PAGE_PATH.parent / sibling).is_file(), "the sibling page link must resolve"
    hardware = flat(section(PAGE_TEXT, "## Hardware"))
    assert "FB203" in hardware and DETAILS["hardware"]["fcc_id"] in hardware
    assert "not established" in hardware, "the shared Transtek name is not a shared factory"
    for link in SPEC["helpful_urls"]:
        if link["kind"] in {"manual", "vendor_support"}:
            assert link["url"] in PAGE_TEXT, link["url"]


def test_the_page_message_tables_are_the_declared_layouts():
    layout = section(PAGE_TEXT, "### Message layout")
    rows = [row for row in table_rows(layout) if row[0].isdigit()]
    wire = characteristics()[CIPHER["characteristic"]]["format"]
    plaintext = SPEC["payload_formats"][CIPHER["plaintext_format"]]["fields"]
    assert len(rows) == len(wire) + len(plaintext)
    for row, field in zip(rows, wire + plaintext, strict=True):
        assert (int(row[0]), int(row[1])) == (field["offset"], field["length"]), row
    wire_rows, plain_rows = rows[: len(wire)], rows[len(wire) :]
    assert ["nonce" in r[2].lower() for r in wire_rows] == [True, False, False]
    assert ["tag" in r[2].lower() for r in wire_rows] == [False, True, False]
    assert ["ciphertext" in r[2].lower() for r in wire_rows] == [False, False, True]
    assert plain_rows[0][2].startswith("Flags")
    raw = next(f for f in plaintext if f["name"] == DECODING["raw_field"])
    assert f"{raw['endianness']}-endian" in plain_rows[1][2]
    assert f"{8 * raw['length']}-bit" in plain_rows[1][2] and "unsigned" in plain_rows[1][2]

    prose = flat(layout)
    assert f"always {CIPHER['message_bytes']} bytes" in prose
    assert f"**{CIPHER['algorithm']}**" in prose
    assert f"{CIPHER['key_bytes']}-byte key" in prose
    assert f"{CIPHER['nonce_bytes']}-byte nonce" in prose
    assert f"{CIPHER['tag_bytes']}-byte tag" in prose
    assert "no associated data" in prose
    assert f"The {CIPHER['plaintext_bytes']} plaintext bytes" in prose
    derived = CIPHER["ccm_parameters_derived"]
    assert f"{derived['length_field_bytes']}-byte length field" in prose
    assert f"first block flags `0x{derived['b0_flags_byte']:02x}`" in prose
    assert f"counter block flags `0x{derived['counter_block_flags_byte']:02x}`" in prose
    assert "tag comes *before* the ciphertext" in prose


def test_the_page_worked_example_is_the_spec_vectors():
    example = section(PAGE_TEXT, "### Worked example (synthetic)")
    first, second, third = VECTORS["vectors"]
    block = example.split("```text\n", 1)[1].split("```", 1)[0]
    lines = {line.split()[0]: line.split()[1:] for line in block.splitlines() if line.strip()}
    assert list(lines) == ["key", "message", "nonce", "tag", "ciphertext", "plaintext", "flags", "count"]
    assert lines["key"][0] == VECTORS["key_hex"]
    assert bytes.fromhex(lines["key"][0]).decode("ascii") == lines["key"][-1].strip('"')
    assert lines["message"] == [first["message_hex"]]
    assert lines["nonce"] == [first["nonce_hex"]]
    assert lines["tag"] == [first["tag_hex"]]
    assert lines["ciphertext"] == [first["ciphertext_hex"]]
    assert "".join(lines["plaintext"]) == first["plaintext_hex"]
    assert lines["flags"] == [f"0x{first['flags']:02x}"]
    assert lines["count"][:3] == [f"0x{first['weight_raw']:04x}", "=", str(first["weight_raw"])]
    (value,) = {Decimal(str(entry["value"])) for entry in first["decoded"]}
    (unit,) = {entry["unit"] for entry in first["decoded"]}
    assert lines["count"][4:6] == [f"{value:.2f}", unit]
    # The block itself opens under the spec's own rules.
    assert open_message(KEY, bytes.fromhex(lines["message"][0])).hex() == first["plaintext_hex"]

    after = flat(example.split("```", 2)[2])
    assert f"flags `0x{second['flags']:02x}`" in after and f"count {second['weight_raw']}" in after
    by_reading = {entry["reading"]: entry for entry in second["decoded"]}
    assert f"{Decimal(str(by_reading['sig_weight_measurement_flags']['value'])):.2f} kg under reading B" in after
    assert f"{Decimal(str(by_reading['hundredths_of_displayed_unit']['value'])):.2f} kg under reading A" in after
    assert third["plaintext_hex"] == first["plaintext_hex"] and "A third repeats the first plaintext" in after


def test_the_page_setup_and_never_do_rules_are_the_spec_rules():
    never = flat(section(PAGE_TEXT, "### What a client must never do"))
    rules = DETAILS["key_lifecycle"]["client_rules"]
    assert rules[0]["rule"] == "Never write to the provision characteristic when it reads 01."
    assert "**Write to the provision characteristic when it reads `01`.**" in never
    assert "`00`" not in never, "the never-write rule is about a scale that HAS a key"
    assert "firmware-update service" in never and "tag fails" in never

    for extra in ("factory reset", "no message arrived", "Stay connected"):
        assert extra in never, extra

    # What both routes cost is said before either route is described.
    setup = section(PAGE_TEXT, "## Initial Setup")
    cost_at = setup.index("### Before either route: what it costs")
    assert cost_at < setup.index("### Route 1:") < setup.index("### Route 2:")
    cost = flat(section(PAGE_TEXT, "### Before either route: what it costs"))
    assert "Both routes end the pairing you have" in cost
    assert "public history of failing" in cost and "search-result titles" in cost
    assert "**a scale that is unpaired and an app that will not re-pair it**" in cost

    route_two = flat(section(PAGE_TEXT, "### Route 2: reset and write your own key (one unreplicated report)"))
    guard = "continue only if it reads `00`"
    write = "write the 16 bytes with response"
    check = "read the status again and expect `01`"
    assert route_two.index(guard) < route_two.index(write) < route_two.index(check)
    assert "**before** writing them" in route_two
    assert "Experiment, not procedure" in route_two and "Nobody has repeated it" in route_two
    assert "findings an AI assistant produced" in route_two and "does not state the firmware" in route_two
    assert "**It ends the vendor pairing.**" in route_two
    assert "**Record the key before you write it**" in route_two
    assert "If weigh-ins do not decrypt afterwards, reset again." in route_two
    assert "no tool recipe exists to give" in route_two
    assert "names no tool and links no repository or capture" in route_two
    assert "four-line fragment that decodes a message, with nothing for the key write" in route_two
    assert "publishes no code" not in route_two
    for tool in ("adb", "bug report", "nrf connect", "bleak", "gatttool", "bluetoothctl"):
        assert not re.search(rf"\b{re.escape(tool)}\b", route_two.lower()), tool

    route_one_raw = section(
        PAGE_TEXT, "### Route 1: let the vendor app set the key and capture it from your phone's log"
    )
    route_one = flat(route_one_raw)
    assert f"exactly {CIPHER['key_bytes']} bytes to characteristic `{PROVISION_CHARACTERISTIC_UUID}`" in route_one
    assert "hardware `H01`, firmware `A16`" in route_one and "version 5.12" in route_one
    assert "The same key serves both, but the scale serves one client at a time" in route_one
    steps = numbered_steps(route_one_raw[route_one_raw.index("1. **Decide first.**") :])
    assert len(steps) == 8 and steps[0].startswith("1. **Decide first.**")
    remove_at = next(i for i, step in enumerate(steps) if "Remove the scale from the vendor app" in step)
    reset_at = next(i for i, step in enumerate(steps) if "Reset the scale" in step)
    dry_run_at = next(i for i, step in enumerate(steps) if "**Dry run, before anything is removed.**" in step)
    export_at = next(i for i, step in enumerate(steps) if "Take the Bluetooth log off the phone" in step)
    assert 0 < dry_run_at < remove_at < reset_at < export_at
    # "Decide first" names the two steps that end the pairing by their numbers.
    assert f"Steps {remove_at + 1} and {reset_at + 1} end the pairing you have" in steps[0]
    assert f"as in step {export_at + 1}" in steps[dry_run_at]
    assert "**Go on only when that works.**" in steps[dry_run_at]
    assert "at least one indication with a 19-byte value" in steps[dry_run_at]
    assert "leave the log switched on" in steps[dry_run_at]
    assert "the pairing is intact and nothing has been lost" in steps[dry_run_at]
    assert "**This ends the present pairing.**" in steps[remove_at]
    assert "the scale stays unpaired until one succeeds" in steps[reset_at]
    assert "never upload it" in steps[export_at] and "Android bug report" in steps[export_at]
    assert f"skip to step {export_at + 2} with no reset at all" in route_one
    capture_route = next(r for r in DETAILS["key_routes"]["routes"] if r["id"] == "capture_key_from_bluetooth_log")
    assert f"`{capture_route['log_export']['log_path_in_report']}`" in route_one
    assert "a way to take an Android bug report off it" in route_one and "`adb` tool from a computer" in route_one
    assert "This project has not checked that on any phone" in route_one
    assert "guessed, without confirming, that it was a key being set up" in route_one

    # The reset: its cost first, the manual's two stages, nothing claimed about otA
    # or about what a keyless scale sends.
    (procedure,) = DEVICE["setup"]["factory_reset"]["procedures"]
    stage = procedure["hold_seconds"] // 2
    reset = flat(section(PAGE_TEXT, "### Factory reset"))
    assert reset.startswith("**What it costs:** a reset ends the scale's current setup.")
    assert f"after {stage} seconds `otA` flashes" in reset
    assert f"after about {stage} more the display changes to `clr`" in reset
    assert "do not start the hold unless you mean to reset" in reset
    assert "neither the manual nor any other public source says what that state is" in reset
    assert "not reported by anyone" in reset and "**assume a reset scale is useless" in reset
    assert "old key is void" not in reset
    assert "One unreplicated report says the key survives a battery change" in reset
    assert "never because a local client received nothing" in reset


def test_the_page_receive_steps_are_the_spec_steps():
    receiving = section(PAGE_TEXT, "### Receiving a weigh-in")
    steps = numbered_steps(receiving)
    assert len(steps) == 6
    subscription = DETAILS["subscription"]
    vendor_value = " ".join(re.findall("..", subscription["vendor_app_descriptor_value_hex"]))
    standards_value = " ".join(re.findall("..", subscription["standards_value_hex"]))
    assert (vendor_value, standards_value) == ("01 00", "02 00")

    timings = DETAILS["connection"]["host_policy_timings"]
    attended, unattended = timings["attended_reader"], timings["unattended_integration"]
    assert f"every {attended['connect_retry_interval_s']} s" in steps[0]
    assert f"up to {attended['keeps_trying_for_s'] // 60} minutes" in steps[0]
    assert f"every {unattended['timer_fallback_interval_s']} s" in steps[0]
    assert "always-on client" in steps[0]
    wake = DETAILS["advertisement"]["wake_signal"]
    assert f"reads `{wake['awake_value']}`" in steps[0]

    assert f"Read `{PROVISION_CHARACTERISTIC_UUID}`" in steps[2]
    assert "`01` means the scale has a key" in steps[2] and "`00` means it was reset" in steps[2]
    assert f"`{WEIGH_IN_UUID}`" in steps[3] and f"writing `{vendor_value}`" in steps[3]
    assert standards_value not in steps[3]
    assert "**indications**" in steps[4] and "Confirm each one" in steps[4]

    trap = flat(receiving.split('!!! warning "The descriptor value is a trap"', 1)[1])
    assert f"stack writes `{standards_value}`" in trap
    assert f"vendor app writes `{vendor_value}`" in trap
    for host in ("BlueZ", "Apple", "ESPHome proxy"):
        assert host in trap, host
    assert "shows no session through one" in trap
    assert "untested" not in trap, "the source offers a proxy as a host; say what it does and does not show"


def test_the_page_services_table_matches_the_gatt_table():
    rows = table_rows(section(PAGE_TEXT, "### BLE Services"))[1:]
    by_uuid = {row[0].strip("`"): row for row in rows}
    assert len(by_uuid) == len(rows) == 6
    assert set(by_uuid) <= KNOWN_UUIDS
    assert by_uuid[DEVICE_INFORMATION_SERVICE_UUID][1] == "Device Information"
    assert "model `FB203`" in by_uuid[DEVICE_INFORMATION_SERVICE_UUID][2]
    assert by_uuid[WEIGHT_SCALE_SERVICE_UUID][1].startswith("Weight Scale")
    assert "(characteristic)" in by_uuid[WEIGH_IN_UUID][1]
    assert by_uuid[WEIGH_IN_UUID][2].startswith("Indicate") and "19-byte" in by_uuid[WEIGH_IN_UUID][2]
    assert by_uuid[PROVISION_SERVICE_UUID][1].startswith("Provisioning")
    assert "(characteristic)" in by_uuid[PROVISION_CHARACTERISTIC_UUID][1]
    assert "Read: `00` no key, `01` has a key" in by_uuid[PROVISION_CHARACTERISTIC_UUID][2]
    assert "16-byte key" in by_uuid[PROVISION_CHARACTERISTIC_UUID][2]
    assert "firmware update" in by_uuid[FIRMWARE_SERVICE_UUID][1].lower()
    firmware_row = by_uuid[FIRMWARE_SERVICE_UUID][2]
    assert firmware_row.startswith("**Do not write to anything in this service. Recovery: none known.**")
    assert "one published listing" in firmware_row and "no Nordic default is assumed" in firmware_row

    identification = flat(section(PAGE_TEXT, "### Identification"))
    assert f"`{WEIGHT_SCALE_SERVICE_UUID}`" in identification
    assert f"`{WEIGHT_MEASUREMENT_UUID}` is **absent**" in identification
    assert "model number reads `FB203`" in identification
    company = DETAILS["advertisement"]["manufacturer_data"]["company_id_hex"]
    assert f"`{company}`" in identification
    assert "**`Aria Air`**" in identification


def test_the_page_weight_rules_are_the_decision_table():
    conflict = section(PAGE_TEXT, "### The kilogram conflict")
    rows = table_rows(conflict)
    readings_table = [row for row in rows if len(row) == 3 and row[0] in {"Pounds", "Kilograms", "Stones"}
                      and row[1] not in {"set", "clear", "either"}]
    decision_rows = [row for row in rows if len(row) == 3 and row[1] in {"set", "clear", "either"}]
    readings = {reading["id"]: reading for reading in DECODING["readings"]}
    a, b = readings["hundredths_of_displayed_unit"], readings["sig_weight_measurement_flags"]
    by_display = {row[0]: row for row in readings_table}
    assert f"count × {a['scales']['lb']} lb" in by_display["Pounds"][1]
    assert f"count × {b['scales']['lb']} lb" in by_display["Pounds"][2]
    assert f"count × {a['scales']['kg']} kg" in by_display["Kilograms"][1]
    assert f"count × {b['scales']['kg']} kg" in by_display["Kilograms"][2]
    assert "bit 0 clear" in by_display["Kilograms"][2] and "bit 0 set" in by_display["Pounds"][2]
    assert by_display["Stones"][1:] == ["not addressed", "not addressed"]

    words = {"lb": "Pounds", "kg": "Kilograms", "st": "Stones"}
    bit_words = {1: "set", 0: "clear"}
    opening = {"publish": "Publish", "refuse": "Refuse", "owner_confirm": "Compute"}
    for row in DECODING["decision_table"]["rows"]:
        matching = [
            page_row
            for page_row in decision_rows
            if page_row[0] == words[row["display_unit"]]
            and page_row[1] in {bit_words[row["flags_bit0"]], "either"}
        ]
        assert len(matching) == 1, row
        text = matching[0][2]
        assert text.startswith(opening[row["action"]]), (row, text)
        if row["action"] == "publish":
            assert f"count × {row['scale']} {row['unit']}" in text
        if row["action"] == "owner_confirm":
            for candidate in row["candidates"]:
                assert f"count × {candidate['scale']} {candidate['unit']}" in text
            assert "If neither does, refuse" in text
    assert len(decision_rows) == 4, "pounds set, pounds clear, kilograms, stones"

    prose = flat(conflict)
    assert "**Neither source says it captured a scale set to kilograms**" in prose
    assert "Neither source shows" not in prose
    assert "never infers it from the flags byte" in prose
    assert "tag fails is dropped" in prose and "other than `0` or `1` is refused" in prose
    assert "stops publishing and asks again" in prose

    can_do = {row[0]: row[1] for row in table_rows(section(PAGE_TEXT, "## What a third-party client can and cannot do today"))}
    pounds = next(value for key, value in can_do.items() if "display in pounds" in key)
    assert "does not say which unit" in pounds and "on one unit" not in pounds


def test_the_page_lists_every_experiment_with_an_honest_cost():
    rows = table_rows(section(PAGE_TEXT, "### Experiments an owner can run"))[1:]
    experiments = DETAILS["owner_experiments"]["experiments"]
    assert [row[0] for row in rows] == [experiment["id"] for experiment in experiments]
    for row, experiment in zip(rows, experiments, strict=True):
        cost = row[3].lower()
        assert ("factory reset" in cost) is experiment["resets_scale"], experiment["id"]
        if experiment["needs_vendor_app"]:
            assert "vendor app" in cost
    by_id = {row[0]: row for row in rows}
    assert by_id["E6"][3].startswith("None")
    assert "Never release at `otA`" in by_id["E10"][1]
    assert "status still reads `00`" in by_id["E1"][1]
    assert "already set to" in by_id["E2"][1]
    assert "Apple host" in by_id["E3"][1]
    assert "second" in by_id["E7"][1].lower() and "never removed from the account" in by_id["E7"][3]
    assert by_id["E11"][1].startswith("Only when a setup is happening anyway")
    assert "Never unpair a working scale" in by_id["E11"][3]
    assert "**Do not open the scale for this**" in by_id["E9"][1] and "the case stays closed" in by_id["E9"][3]
    for row in rows:
        assert not re.search(r"(?<!not )\bopen(?:ing)? the (?:scale|case)\b", " ".join(row).lower()), row[0]
    for connects in ("E2", "E3", "E4", "E6", "E8"):
        assert "may not reach the vendor app" in by_id[connects][3], connects
    assert "no connection" in by_id["E5"][3]
    assert "holding it starts the reset" in by_id["E2"][3]
    intro = flat(section(PAGE_TEXT, "### Experiments an owner can run").split("| | Experiment", 1)[0])
    assert "**E1 and E10 reset the scale, which ends the vendor pairing**" in intro
    assert "None of these is a reason to unpair or reset a scale that works" in intro


def test_the_page_puts_the_free_options_first_and_keeps_research_as_research():
    options = table_rows(section(PAGE_TEXT, "## What an owner can do, cheapest first"))[1:]
    routes = DETAILS["key_routes"]["routes"]
    assert [row[0] for row in options] == [str(n) for n in range(1, len(routes) + 1)]
    for row, route in zip(options, routes, strict=True):
        cost = row[3]
        if route["is_setup_method"]:
            assert re.match(r"\*\*The (?:present|vendor) pairing\b", cost), (route["id"], cost)
        else:
            assert cost.startswith("Nothing"), (route["id"], cost)
    camera_row, camera = options[1], routes[1]
    assert f"]({camera['project_url']})" in camera_row[1] and camera["licence"] in camera_row[1]
    assert "on nothing else" in camera_row[4]
    about = flat(section(PAGE_TEXT, "## What an owner can do, cheapest first"))
    assert "kilograms only" in about and "assumes where the decimal point is" in about
    assert "not from an app store" in about and "This project has not run or reviewed it" in about
    assert "start with the first steps of the vendor's own [sync troubleshooting]" in about
    assert "try the earlier steps first" in about and "Q11" in about
    assert "this page cannot say what a reinstall does to it" in about
    assert "None of its Aria Air steps removes the scale itself from the account or resets it. Do neither." in about
    assert "may never reach the vendor app" in options[2][3]
    assert "Two parties for the name, service, characteristic, indication and length" in options[2][4]
    assert "The first three change nothing on the scale and leave the pairing alone" in about
    assert "the third can cost the weigh-in it connects during" in about
    assert "end the vendor pairing before they give anything back" in about

    # Negative findings, as negatives.
    negatives = flat(section(PAGE_TEXT, "### What is not a route"))
    for phrase in (
        "**Nothing to redirect.**",
        "**No shared protocol with the Transtek-named scale family.**",
        "**A matcher on the standard weight service alone** claims this scale and gets nothing",
        "is not present in the one published GATT listing",
        "nobody has checked while the display shows `otA`",
        "**No firmware side-load.**",
        "This page publishes no route through it",
        "**No key without a reset.**",
        "They are not owner experiments",
    ):
        assert phrase in negatives, phrase
    can_do = {row[0]: row[1] for row in table_rows(section(PAGE_TEXT, "## What a third-party client can and cannot do today"))}
    assert can_do["Get the key without ending the present pairing"].startswith("**No known way.**")
    assert can_do["Redirect the scale to a server of your own"].startswith("Does not apply")

    # The hardware paragraph and the last resort are statements with their risks, not steps.
    hardware = flat(section(PAGE_TEXT, "## Hardware"))
    assert "**Inside the case: research notes, not instructions.**" in hardware
    assert "Nobody has reported connecting to them" in hardware
    assert "no public programmer lists this chip as tested" in hardware
    assert "This page gives no wiring or flashing procedure" in hardware
    assert "could not be undone" in hardware and "do not bridge them" in hardware
    last = flat(section(PAGE_TEXT, "### When nothing else is left"))
    for phrase in (
        "nobody has documented on this model",
        "It ends the Fitbit function",
        "recalibration against known weights",
        "for which no instructions exist",
        "isolated from the mains",
        "not something to do to one that works",
    ):
        assert phrase in last, phrase
    assert not re.search(r"^\d+\. ", section(PAGE_TEXT, "### When nothing else is left"), re.MULTILINE)
    assert not re.search(r"^\d+\. ", section(PAGE_TEXT, "## Hardware"), re.MULTILINE)
