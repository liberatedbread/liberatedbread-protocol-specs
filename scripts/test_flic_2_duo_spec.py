#!/usr/bin/env python3
"""Independent Flic 2/Duo framing, crypto and reliable-event checks.

All keys, addresses and events are synthetic. Chaskey expected values were
cross-checked against the official SDK during specification work; this module
transcribes the algorithm using only Python's standard library.
"""

import base64
import hashlib
import hmac
import re
from pathlib import Path

import pytest
import yaml

SPEC = yaml.safe_load(
    (Path(__file__).parents[1] / "device-specs/devices/flic-2-duo.yaml").read_text()
)
DETAILS = SPEC["protocol_details"]
MASK = 0xFFFFFFFF


def decode_public_advertisement(local_name, manufacturer_payload):
    if not re.fullmatch(r"F2[0-9]{2}[A-Za-z0-9_-]{4}", local_name):
        raise ValueError("not a public Flic name")
    low = base64.urlsafe_b64decode(local_name[4:])
    if len(low) != 3 or len(manufacturer_payload) < 5 or manufacturer_payload[0] != 2:
        raise ValueError("invalid public manufacturer payload")
    top = bytes(reversed(manufacturer_payload[1:4]))
    flags = manufacturer_payload[4]
    address_octets = top + low
    if flags & 1 and address_octets[0] & 0xC0 != 0xC0:
        raise ValueError("static-random address must have top bits 11")
    address = ":".join(f"{byte:02x}" for byte in address_octets)
    return {
        "address": address,
        "firmware": int(local_name[2:4]),
        "address_type": "static random" if flags & 1 else "public",
        "connected": bool(flags & 2),
    }


def fragment(conn_id, logical, fragment_payload=8):
    if len(logical) + 1 > 129:
        raise ValueError("logical packet too large")
    if not 0 <= conn_id <= 31:
        raise ValueError("invalid logical connection ID")
    chunks = [logical[offset : offset + fragment_payload] for offset in range(0, len(logical), fragment_payload)]
    output = []
    for index, chunk in enumerate(chunks):
        header = conn_id | (0x80 if index + 1 < len(chunks) else 0)
        output.append(bytes([header]) + chunk)
    return output


def reassemble(fragments, expected_conn):
    if not fragments:
        raise ValueError("empty fragment stream")
    body = bytearray()
    for index, fragment_bytes in enumerate(fragments):
        if len(fragment_bytes) < 2:
            raise ValueError("empty fragment")
        header = fragment_bytes[0]
        if header & 0x1F != expected_conn:
            raise ValueError("packet for another logical connection")
        final = not header & 0x80
        body.extend(fragment_bytes[1:])
        if final and index != len(fragments) - 1:
            raise ValueError("bytes after final fragment")
        if index == len(fragments) - 1 and not final:
            raise ValueError("unterminated fragment stream")
    if len(body) + 1 > 129:
        raise ValueError("reassembled packet too large")
    return bytes(body)


def parse_coalesced(value, expected_conn):
    packets = []
    offset = 0
    while offset < len(value):
        header = value[offset]
        if header & 0xC0 != 0x40 or header & 0x1F != expected_conn:
            raise ValueError("not a coalesced packet for this connection")
        if offset + 2 > len(value):
            raise ValueError("missing coalesced length")
        length = value[offset + 1]
        start = offset + 2
        end = start + length
        if end > len(value):
            raise ValueError("truncated coalesced packet")
        packets.append(value[start:end])
        offset = end
    return packets


def rotl(value, count):
    return ((value << count) | (value >> (32 - count))) & MASK


def rotr(value, count):
    return ((value >> count) | (value << (32 - count))) & MASK


def words(data):
    if len(data) != 16:
        raise ValueError("a Chaskey key/block requires 16 bytes")
    return [int.from_bytes(data[offset : offset + 4], "little") for offset in range(0, 16, 4)]


def subkeys(key):
    original = words(key)

    def double(input_words):
        carry = 0x87 if input_words[3] & 0x80000000 else 0
        return [
            ((input_words[0] << 1) & MASK) ^ carry,
            ((input_words[1] << 1) & MASK) | (input_words[0] >> 31),
            ((input_words[2] << 1) & MASK) | (input_words[1] >> 31),
            ((input_words[3] << 1) & MASK) | (input_words[2] >> 31),
        ]

    first = double(original)
    return original, first, double(first)


def permutation(state):
    v0, v1, v2, v3 = state
    v2 = rotr(v2, 16)
    for _ in range(16):
        v0 = (v0 + v1) & MASK
        v1 = v0 ^ rotl(v1, 5)
        v2 = (v3 + rotr(v2, 16)) & MASK
        v3 = v2 ^ rotl(v3, 8)
        v2 = (v2 + v1) & MASK
        v0 = (v3 + rotr(v0, 16)) & MASK
        v1 = v2 ^ rotl(v1, 7)
        v3 = v0 ^ rotl(v3, 13)
    return [v0, v1, rotr(v2, 16), v3]


def chaskey(key, message):
    if not message:
        raise ValueError("empty Chaskey message")
    original, first, second = subkeys(key)
    state = original[:]

    def xor_words(left, right):
        return [(left[index] ^ right[index]) & MASK for index in range(4)]

    while len(message) > 16:
        state = xor_words(state, words(message[:16]))
        state = permutation(state)
        message = message[16:]
    if len(message) == 16:
        state = xor_words(xor_words(state, words(message)), first)
        state = permutation(state)
        state = xor_words(state, first)
    else:
        padded = message + b"\x01" + bytes(15 - len(message))
        state = xor_words(xor_words(state, words(padded)), second)
        state = permutation(state)
        state = xor_words(state, second)
    return b"".join(word.to_bytes(4, "little") for word in state)


def signature(key, direction, counter, data):
    message = counter.to_bytes(8, "little") + direction.to_bytes(8, "little") + data
    return chaskey(key, message)[:5]


def derive_full(row):
    shared = bytes.fromhex(row["shared_secret_hex"])
    sig_bits = row["sig_bits"]
    button_random = bytes.fromhex(row["button_random_hex"])
    client_random = bytes.fromhex(row["client_random_hex"])
    variant = 0x80 if row["variant"] == "Duo" else 0
    secret = hashlib.sha256(shared + bytes([sig_bits]) + button_random + client_random + bytes([variant])).digest()

    def apply(label):
        return hmac.new(secret, label, hashlib.sha256).digest()

    pairing_id = apply(b"PK")[:4]
    pairing_key = apply(b"PK")[4:20]
    token = apply(b"PT" + pairing_id + pairing_key)[:16]
    negative = apply(b"NE" + token)[:16]
    return {
        "full_verify_secret_hex": secret.hex(),
        "verifier_hex": apply(b"AT")[:16].hex(),
        "session_key_hex": apply(b"SK")[:16].hex(),
        "pairing_identifier_hex": pairing_id.hex(),
        "pairing_key_hex": pairing_key.hex(),
        "pairing_token_hex": token.hex(),
        "negative_result_hex": negative.hex(),
    }


def derive_quick(pairing_key, client_random, discriminator, button_random):
    return chaskey(pairing_key, client_random + bytes([discriminator]) + button_random)


def parse_base_event(item):
    packed = int.from_bytes(item, "little")
    encoded = (packed >> 48) & 0xF
    event_type = encoded & 3
    was_hold = False
    single = False
    double = False
    next_up_double = False
    if encoded & 8:
        event_type = 0
        was_hold = bool(encoded & 4)
        single = bool(encoded & 2) and not encoded & 1
        double = bool(encoded & 2) and bool(encoded & 1)
    elif encoded == 7:
        next_up_double = True
    return {
        "timestamp_ticks": packed & ((1 << 48) - 1),
        "type": event_type,
        "single_click": single,
        "double_click": double,
        "was_hold": was_hold,
        "next_up_will_be_double_click": next_up_double,
        "was_queued": bool((packed >> 52) & 1),
        "was_queued_last": bool((packed >> 53) & 1),
        "acknowledge": (event_type == 0 and (single or double)) or event_type == 2,
    }


class Session:
    def __init__(self, key):
        self.key = key
        self.expected = {0: 0, 1: 0}

    def verify(self, direction, counter, data, supplied_signature):
        if counter != self.expected[direction]:
            raise ValueError("replay or out-of-order packet")
        expected = signature(self.key, direction, counter, data)
        if not hmac.compare_digest(expected, supplied_signature):
            raise ValueError("invalid signature")
        self.expected[direction] += 1


class BitReader:
    def __init__(self, data):
        self.data = data
        self.bit_position = 0

    def remaining_bytes(self):
        return len(self.data) - (self.bit_position + 7) // 8

    def read(self, width):
        if self.bit_position + width > len(self.data) * 8:
            raise ValueError("truncated Duo event bitstream")
        value = 0
        for offset in range(width):
            position = self.bit_position + offset
            value |= ((self.data[position // 8] >> (position % 8)) & 1) << offset
        self.bit_position += width
        return value


def signed_byte(value):
    return value - 256 if value >= 128 else value


def decode_duo_events(data, state):
    reader = BitReader(data)
    counts = list(state["event_count"])
    last_timestamp = state["last_timestamp_ms"]
    end_of_queue = state["end_of_queue_marker"]
    got_count = [False, False]
    events = []
    acknowledge = False
    while reader.remaining_bytes() > 1:
        button = reader.read(1)
        if not got_count[button]:
            delta = reader.read(1)
            if delta == 1 and reader.read(1) == 1:
                width = (2, 4, 8, 32)[reader.read(2)]
                delta = reader.read(width)
            delta += 1
            counts[button] += delta
            got_count[button] = True
        else:
            counts[button] += 1
        width = (8, 10, 13, 16, 24, 32, 40, 48)[reader.read(3)]
        last_timestamp += reader.read(width)
        was_queued = False
        last_queued = False
        if not end_of_queue:
            if reader.read(1) == 0:
                was_queued = True
            else:
                end_of_queue = True
                if reader.read(1) == 0:
                    was_queued = True
                    last_queued = True
        event_type = reader.read(3)
        double_hold = reader.read(1) if event_type == 4 else False
        next_up_double = reader.read(1) if event_type == 7 else False
        gesture = None
        if event_type <= 4 or event_type == 6:
            if reader.read(1) and reader.read(1):
                gesture = ("left", "right", "up", "down")[reader.read(2)]
        acceleration = [signed_byte(reader.read(8)) for _ in range(3)]
        if event_type <= 5 and counts[button] % 2 == 0:
            counts[button] += 1
        single = event_type in {1, 2}
        double = event_type in {3, 4}
        was_hold = event_type == 2 or (event_type == 4 and double_hold)
        acknowledge |= single or double or event_type == 6
        events.append(
            {
                "button": button,
                "event_count": counts[button],
                "timestamp_ms": last_timestamp,
                "type": event_type,
                "single_click": single,
                "double_click": double,
                "was_hold": was_hold,
                "next_up_will_be_double_click": bool(next_up_double),
                "was_queued": was_queued,
                "was_queued_last": last_queued,
                "gesture": gesture,
                "acceleration_raw": acceleration,
            }
        )
    return {
        "event_count": counts,
        "last_timestamp_ms": last_timestamp,
        "end_of_queue_marker": end_of_queue,
        "events": events,
        "acknowledge": acknowledge,
    }


def decode_push_twist(data):
    if len(data) < 6 or data[0] != 33:
        raise ValueError("invalid push-twist frame")
    raw = int.from_bytes(data[2:6], "little", signed=True)
    return raw * 360 / 65536


def test_public_advertisement_reconstructs_synthetic_address():
    row = DETAILS["public_advertising"]["test_vector"]
    decoded = decode_public_advertisement(row["local_name"], bytes.fromhex(row["manufacturer_payload_hex"]))
    assert decoded == {
        "address": row["address"],
        "firmware": row["firmware"],
        "address_type": row["address_type"],
        "connected": row["connected"],
    }


def test_fragmentation_and_reassembly_across_boundaries():
    logical = bytes(range(1, 100))
    for size in (1, 7, 20, 98, 99):
        fragments = fragment(7, logical, size)
        assert reassemble(fragments, 7) == logical
        assert all(fragment_bytes[0] & 0x80 for fragment_bytes in fragments[:-1])
        assert not fragments[-1][0] & 0x80
    broken = fragment(7, logical, 7)
    with pytest.raises(ValueError, match="unterminated"):
        reassemble(broken[:-1] + [broken[-2]], 7)
    with pytest.raises(ValueError, match="another logical"):
        reassemble(fragments, 8)


def test_oversized_and_coalesced_packet_rules():
    with pytest.raises(ValueError, match="too large"):
        fragment(1, bytes(129))
    first, second = b"\x14\x00\x04", b"\x0e"
    value = bytes([0x43, len(first)]) + first + bytes([0x43, len(second)]) + second
    assert parse_coalesced(value, 3) == [first, second]
    with pytest.raises(ValueError, match="truncated"):
        parse_coalesced(value[:-1], 3)


def test_chaskey_subkeys_and_official_synthetic_vectors():
    declarations = DETAILS["packet_signatures"]
    subkey_vector = declarations["test_vectors"][0]
    original, first, second = subkeys(bytes.fromhex(subkey_vector["key_hex"]))
    assert original == [0x03020100, 0x07060504, 0x0B0A0908, 0x0F0E0D0C]
    assert first == [int(value, 16) for value in subkey_vector["subkey1_words_le_hex"]]
    assert second == [int(value, 16) for value in subkey_vector["subkey2_words_le_hex"]]
    for row in declarations["test_vectors"][1:]:
        key = bytes.fromhex(row["key_hex"])
        data = bytes.fromhex(row["message_data_hex"])
        assert signature(key, row["direction"], row["counter"], data).hex() == row["expected_signature_hex"]


def test_chaskey_rejects_empty_message():
    with pytest.raises(ValueError, match="empty"):
        chaskey(bytes(16), b"")


def test_full_verify_derivation_and_really_unpaired_proofs():
    for row in DETAILS["full_verify"]["test_vectors"]:
        derived = derive_full(row)
        for field in (
            "full_verify_secret_hex",
            "verifier_hex",
            "session_key_hex",
            "pairing_identifier_hex",
            "pairing_key_hex",
            "pairing_token_hex",
            "negative_result_hex",
        ):
            assert derived[field] == row[field], f"{row['variant']}:{field}"
        assert derived["session_key_hex"] != DETAILS["quick_verify"]["test_vectors"]["base_session_key_hex"]


def test_quick_verify_base_and_duo_discriminators():
    row = DETAILS["quick_verify"]["test_vectors"]
    key = bytes.fromhex(row["pairing_key_hex"])
    client = bytes.fromhex(row["random_client_hex"])
    button = bytes.fromhex(row["random_button_hex"])
    assert derive_quick(key, client, 0, button).hex() == row["base_session_key_hex"]
    assert derive_quick(key, client, 0x40, button).hex() == row["duo_session_key_hex"]
    assert derive_quick(key, client, 0, button) != derive_quick(key, client, 0x40, button)


def test_signed_session_accepts_sequence_and_rejects_replay_and_bad_direction():
    key = bytes.fromhex("000102030405060708090a0b0c0d0e0f")
    session = Session(key)
    data = bytes.fromhex("606162636465666768696a6b6c6d6e6f70")
    session.verify(1, 0, data, signature(key, 1, 0, data))
    with pytest.raises(ValueError, match="replay"):
        session.verify(1, 0, data, signature(key, 1, 0, data))
    session.verify(0, 0, data, signature(key, 0, 0, data))
    with pytest.raises(ValueError, match="invalid signature"):
        session.verify(0, 1, data, signature(key, 1, 1, data))
    with pytest.raises(ValueError, match="invalid signature"):
        session.verify(0, 1, data, bytes(5))


def test_reliable_base_event_and_acknowledgement():
    row = DETAILS["reliable_events"]["test_vector"]
    event = parse_base_event(bytes.fromhex(row["item_hex"]))
    for field, expected in row["expected"].items():
        assert event[field] == expected, field
    assert event["acknowledge"] is True
    acknowledgement = bytes([row["acknowledgement_opcode"]]) + row["acknowledgement_event_count"].to_bytes(4, "little")
    assert acknowledgement == bytes.fromhex("1003000000")


def test_duo_down_and_single_click_bitstreams_with_state_and_ack():
    down_row, single_row = DETAILS["duo_events"]["synthetic_vectors"]
    down = decode_duo_events(bytes.fromhex(down_row["events_data_hex"]), down_row["initial"])
    assert down["event_count"] == down_row["expected"]["event_count"]
    assert down["last_timestamp_ms"] == down_row["expected"]["timestamp_ms"]
    assert down["acknowledge"] is down_row["expected"]["acknowledge"]
    assert len(down["events"]) == 1
    assert down["events"][0]["type"] == down_row["expected"]["type"]
    assert down["events"][0]["acceleration_raw"] == down_row["expected"]["acceleration_raw"]

    single = decode_duo_events(bytes.fromhex(single_row["events_data_hex"]), down)
    assert single["event_count"] == single_row["expected"]["event_count"]
    assert single["last_timestamp_ms"] == single_row["expected"]["timestamp_ms"]
    assert single["acknowledge"] is single_row["expected"]["acknowledge"]
    event = single["events"][0]
    assert event["single_click"] is single_row["expected"]["single_click"]
    assert event["acceleration_raw"] == single_row["expected"]["acceleration_raw"]
    acknowledgement = bytes([36]) + b"".join(count.to_bytes(4, "little") for count in single["event_count"])
    assert acknowledgement == bytes.fromhex("240300000000000000")


def test_duo_malformed_bitstreams_and_trailing_padding():
    row = DETAILS["duo_events"]["synthetic_vectors"][0]
    data = bytes.fromhex(row["events_data_hex"])
    with pytest.raises(ValueError, match="truncated"):
        decode_duo_events(data[:-1], row["initial"])
    padded = decode_duo_events(data + b"\x00", row["initial"])
    assert len(padded["events"]) == 1
    with pytest.raises(ValueError, match="truncated"):
        decode_duo_events(data[:2], row["initial"])


def test_battery_voltage_and_push_twist_scaling():
    battery = int.from_bytes(bytes.fromhex("0004"), "little") * 3.6 / 1024
    assert battery == pytest.approx(3.6)
    assert decode_push_twist(bytes.fromhex("210100400000")) == pytest.approx(90)
    assert decode_push_twist(bytes.fromhex("21010080ffff")) == pytest.approx(-180)


def test_no_legacy_or_hub_surface_is_declared():
    assert {variant["model"] for variant in SPEC["device"]["variants"]} == {"Flic 2", "Flic Duo"}
    assert len(SPEC["services"]) == 1
    assert SPEC["device"]["testing"]["status"] == "untested"
    assert SPEC["device"]["integration"] == "identify_only"
    assert {tuple(feature.get("variants", [])) for feature in SPEC["features"]} == {("Flic 2",), ("Flic Duo",)}


def reconcile_base_event_counts(packet_event_count, items):
    if not items:
        raise ValueError("event notification has no items")
    events = [parse_base_event(item) for item in items]
    counts = [None] * len(items)
    ec = packet_event_count
    counts[-1] = ec
    for index in range(len(items) - 2, -1, -1):
        m4 = ec % 4
        event_type = events[index]["type"]
        if m4 in {0, 2}:
            ec -= 1
        elif m4 == 1:
            ec -= 1 if event_type == 2 else 2
        else:
            ec -= 1 if event_type == 3 else 2
        counts[index] = ec
    return counts


def test_static_random_advertisement_has_required_top_bits():
    row = DETAILS["public_advertising"]["test_vector"]
    assert row["address"] == "c2:00:00:76:42:06"
    assert row["manufacturer_payload_hex"] == "020000c201"
    first_octet = int(row["address"].split(":", 1)[0], 16)
    assert first_octet & 0xC0 == 0xC0
    decoded = decode_public_advertisement(row["local_name"], bytes.fromhex(row["manufacturer_payload_hex"]))
    assert decoded["address_type"] == "static random"
    with pytest.raises(ValueError, match="top bits 11"):
        decode_public_advertisement(row["local_name"], bytes.fromhex("0200000201"))


def test_base_multi_item_reverse_reconciliation_with_skipped_hold_and_timeout():
    row = DETAILS["reliable_events"]["multi_item_test_vector"]
    items = [bytes.fromhex(value) for value in row["items_hex"]]
    events = [parse_base_event(item) for item in items]
    assert [event["type"] for event in events] == row["expected"]["types"]

    counts = reconcile_base_event_counts(row["event_count"], items)
    assert counts == row["expected"]["event_counts"]
    assert set(range(counts[0], counts[-1] + 1)) - set(counts) == {4, 6}
    for count in row["expected"]["skipped_timeout_counts"]:
        assert count not in counts
        assert count % 4 == 0
    for count in row["expected"]["skipped_hold_counts"]:
        assert count not in counts
        assert count % 4 == 2

    qualifying_counts = [count for count, event in zip(counts, events, strict=True) if event["acknowledge"]]
    assert qualifying_counts == [3, 7, 8]
    assert any(event["acknowledge"] for event in events) is row["expected"]["acknowledge"]
    acknowledgement = bytes([row["acknowledgement_opcode"]]) + row["acknowledgement_event_count"].to_bytes(4, "little")
    assert acknowledgement == bytes.fromhex("100a000000")
    assert row["acknowledgement_event_count"] == counts[-1] == row["event_count"]
    assert row["acknowledgement_event_count"] != qualifying_counts[-1]
    assert len(DETAILS["reliable_events"]["reverse_reconciliation"]["rules"]) == 5


def test_identification_has_no_bare_f2_prefix_and_regex_needs_full_grammar():
    identification = SPEC["device"]["identification"]
    assert "local_name_prefixes" not in identification
    assert "local_name_prefix" not in identification
    needle = SPEC["device"]["discovery"]["methods"][0]["ble"]["local_name"]["value"]
    assert re.fullmatch(needle, "F207dkIG")
    for name in ("F2", "F2-Remote", "F2 Lamp", "F207dkI"):
        assert not re.fullmatch(needle, name), name
