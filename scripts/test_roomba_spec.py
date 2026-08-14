# Copyright 2026 Pigs Can Fly Labs LLC
# SPDX-License-Identifier: Apache-2.0
"""Proves the iRobot Roomba spec can be driven from the spec alone.

`device-specs/devices/irobot-roomba.yaml` documents three things a client has
to get exactly right before it can talk to a robot: the UDP-5678 discovery
exchange, the password-disclosure handshake on TLS 8883, and the JSON command
envelope published to the `cmd` topic. This module transcribes the consumer's
side of all three from the YAML using nothing but the standard library, and
holds the spec to it — the sibling of `test_kasa_spec.py` (raw-socket JSON)
and `test_wemo_spec.py` (SOAP).

The password handshake gets the most attention here for a reason. Published
implementations each hardcode a *different* fixed offset into the same reply
(roombapy 7, dorita980 13 or 9 depending on how the socket delivered the
bytes), so the spec states an extraction *rule* and records those offsets only
as evidence. The test below builds a reply at every documented offset and
asserts the rule recovers the same password from all of them — if it cannot,
the rule is wrong and a client written from this document would ship a broken
credential.

None of this has been replayed against a robot. What it proves is that the
document is self-consistent and implementable, not that the protocol is
correct — for that, see koalazak/dorita980, which is where all of it came from.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SPEC_PATH = REPO_ROOT / "device-specs" / "devices" / "irobot-roomba.yaml"

# A real-shaped Roomba password: leading colon, embedded colons, mixed case.
# Chosen to break any client that splits on ':' or trims the first character.
SAMPLE_PASSWORD = ":1:1486937829:gktkDoYpWaDxCfGh"


@pytest.fixture(scope="module")
def spec() -> dict:
    return yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def protocol(spec) -> dict:
    return spec["irobot_lan_protocol"]


@pytest.fixture(scope="module")
def commands(spec) -> dict:
    return spec["commands"]


@pytest.fixture(scope="module")
def entities(spec) -> list:
    return spec["entities"]


@pytest.fixture(scope="module")
def topics(spec) -> dict:
    return {entry["topic"]: entry for entry in spec["mqtt_topics"]}


# ── Reference implementation, transcribed from the spec ──────────────────────


def blid_from_hostname(hostname: str, prefixes: tuple[str, ...]) -> str:
    """`Roomba-<blid>` / `iRobot-<blid>` -> `<blid>`, per the discovery block.

    The spec is explicit that a datagram whose hostname carries neither prefix
    is not a robot: the broadcast reaches every host on the segment, so this
    filter is the difference between finding robots and finding the LAN.
    """
    if not hostname.startswith(prefixes):
        raise ValueError(f"not an iRobot announcement: {hostname!r}")
    return hostname.split("-", 1)[1]


def extract_password(reply: bytes, response_rules: dict) -> str:
    """The password-extraction rule, transcribed from `password_extraction`.

    Drop the 2-byte header, drop remaining leading non-printable bytes, decode
    the rest as UTF-8, strip trailing NULs. Deliberately offset-free: that is
    the whole point of stating it as a rule.
    """
    header = response_rules["header_length"]
    if len(reply) < response_rules["minimum_length"]:
        raise ValueError("robot is not in password-disclosure mode")
    if reply.hex() == response_rules["unsupported_reply_hex"]:
        raise ValueError("this model cannot disclose its password locally")

    body = reply[header:]
    start = 0
    while start < len(body) and not (0x20 <= body[start] < 0x7F):
        start += 1
    return body[start:].decode("utf-8").rstrip("\x00")


def build_reply(password: str, offset: int, filler: bytes | None = None) -> bytes:
    """A disclosure reply whose password begins at `offset` of the whole reply.

    The default filler cycles through control bytes rather than repeating 0x00,
    so a rule that happens to work only against a run of NULs does not pass
    here. It is still an *assumed* filler: the spec's
    `password_extraction_notes` is explicit that nobody has confirmed what a
    real robot puts in that gap, and this function cannot know better than the
    document does.
    """
    encoded = password.encode()
    gap = offset - 2
    if filler is None:
        filler = bytes((i % 0x20) for i in range(1, gap + 1))
    assert len(filler) == gap
    payload_len = len(encoded) + gap
    reply = bytearray(b"\xf0" + bytes([payload_len & 0xFF]))
    reply.extend(filler)
    reply.extend(encoded)
    return bytes(reply)


def render(command: dict, values: dict) -> str:
    """Render a command's `arguments` into the compact JSON that goes on the wire.

    `{name}` substitutes from `values`, typed by the declared parameter — the
    spec says `time` renders as a JSON number, not a string, and a client that
    quotes it sends something the robot will not read.
    """
    parameters = command.get("parameters") or {}
    out = {}
    for key, value in command["arguments"].items():
        if isinstance(value, str) and value.startswith("{") and value.endswith("}"):
            name = value[1:-1]
            declared = parameters[name]
            supplied = values[name]
            out[key] = int(supplied) if declared["type"] == "integer" else supplied
        else:
            out[key] = value
    return json.dumps(out, separators=(",", ":"))


# ── Discovery ────────────────────────────────────────────────────────────────


def test_discovery_probe_is_the_documented_datagram(protocol):
    """The probe is nine ASCII bytes to the broadcast address on 5678."""
    discovery = protocol["discovery"]
    assert discovery["destination"] == "255.255.255.255:5678"
    assert discovery["request"]["encoding"] == "string"
    assert discovery["request"]["payload"].encode() == b"irobotmcs"


def test_the_discovery_example_parses_and_yields_a_blid(protocol):
    """The published example must survive the parse the spec describes.

    An example that does not decode into the identity the spec says it carries
    is worse than no example: it is a test vector that lies.
    """
    discovery = protocol["discovery"]
    announcement = json.loads(discovery["response"]["example"])
    blid = blid_from_hostname(announcement["hostname"], ("Roomba-", "iRobot-"))
    assert blid == "3193C60472324700"
    assert announcement["proto"] == "mqtt"


def test_every_documented_response_field_is_in_the_example(protocol):
    """The field list and the example are two statements of one payload."""
    discovery = protocol["discovery"]
    announcement = json.loads(discovery["response"]["example"])
    documented = {field["name"] for field in discovery["response"]["fields"]}
    missing = sorted(documented - set(announcement))
    assert not missing, f"documented but absent from the example: {missing}"


def test_a_non_robot_announcement_is_rejected(protocol):
    """The broadcast reaches every host; the hostname prefix is the filter."""
    with pytest.raises(ValueError):
        blid_from_hostname("printer-4f2a", ("Roomba-", "iRobot-"))


# ── Password disclosure ──────────────────────────────────────────────────────


def test_password_probe_is_the_documented_seven_bytes(protocol):
    """f0 05 ef cc 3b 29 00 — 0xf0, a length of 5, then five payload bytes."""
    request = protocol["password_disclosure"]["request"]
    probe = bytes.fromhex(request["payload_hex"])
    assert probe == b"\xf0\x05\xef\xcc\x3b\x29\x00"
    assert probe[0] == 0xF0
    assert probe[1] == len(probe) - 2, "the second byte is the payload length"


def test_the_rule_recovers_the_password_at_every_observed_offset(protocol):
    """The point of the whole block: one rule, three disagreeing clients.

    roombapy slices at 7, dorita980 at 13 or at 9 depending on how the socket
    delivered the bytes. Those are three framing assumptions about the same
    reply, so a rule that only works under one of them would send some users a
    truncated credential and no way to tell.
    """
    disclosure = protocol["password_disclosure"]
    rules = disclosure["response"]
    offsets = [entry["offset"] for entry in rules["observed_offsets"]]
    assert sorted(offsets) == [7, 9, 13], (
        "the observed offsets changed; re-check the rule against the clients"
    )
    for offset in offsets:
        reply = build_reply(SAMPLE_PASSWORD, offset)
        assert extract_password(reply, rules) == SAMPLE_PASSWORD, (
            f"extraction rule fails on a reply framed at offset {offset}"
        )


def test_the_whole_string_survives_extraction(protocol):
    """Roomba passwords start with ':' and contain ':' — nothing may be split.

    This is the failure the spec calls out in prose, asserted: an extractor
    that trims the leading colon, or splits on one, produces a credential the
    broker rejects with no clue why.
    """
    rules = protocol["password_disclosure"]["response"]
    recovered = extract_password(build_reply(SAMPLE_PASSWORD, 13), rules)
    assert recovered.startswith(":")
    assert recovered.count(":") == SAMPLE_PASSWORD.count(":")


def test_trailing_nulls_are_stripped(protocol):
    """Real replies pad; a padded password fails the broker's comparison."""
    rules = protocol["password_disclosure"]["response"]
    padded = build_reply(SAMPLE_PASSWORD, 13) + b"\x00\x00\x00"
    assert extract_password(padded, rules) == SAMPLE_PASSWORD


def test_a_short_reply_is_the_not_in_disclosure_mode_case(protocol):
    """The failure a user actually hits: they did not hold HOME long enough."""
    rules = protocol["password_disclosure"]["response"]
    for length in range(rules["minimum_length"]):
        with pytest.raises(ValueError):
            extract_password(b"\xf0" * length, rules)


def test_the_unsupported_reply_is_distinguished_from_a_password(protocol):
    """A model that cannot disclose says so; that is not a retryable failure."""
    rules = protocol["password_disclosure"]["response"]
    unsupported = bytes.fromhex(rules["unsupported_reply_hex"])
    with pytest.raises(ValueError):
        extract_password(unsupported, rules)


def test_the_extraction_rule_admits_it_is_a_hypothesis(protocol):
    """The rule is this project's synthesis and the spec must not hide that.

    Everything else in this file is transcribed from a working client. This one
    rule is not: it was derived by asking what satisfies all three published
    offsets at once, and it assumes the gap between header and credential holds
    no printable byte. That assumption is load-bearing and unverified, so the
    spec carries it as `hypothesis` — the same grade a guessed opcode gets.
    """
    rules = protocol["password_disclosure"]["response"]
    assert rules["password_extraction_verification"] == "hypothesis"
    assert "assumption" in rules["password_extraction_notes"]


def test_a_printable_byte_in_the_gap_defeats_the_rule(protocol):
    """The known failure mode, asserted rather than left as a warning.

    If a firmware puts a printable byte between the header and the credential,
    the rule returns it glued to the front of the password and the only symptom
    is a login the broker refuses. Pinning it here means the day someone
    captures a real reply, this test says exactly what to re-check.
    """
    rules = protocol["password_disclosure"]["response"]
    gap = b"\x01\x02\x03\x04\x05\x06\x07\x08\x09\x41\x0b"  # 0x41 == 'A'
    reply = build_reply(SAMPLE_PASSWORD, 13, filler=gap)
    recovered = extract_password(reply, rules)
    assert recovered != SAMPLE_PASSWORD
    assert recovered.startswith("A"), (
        "the documented failure mode changed shape; re-read "
        "password_extraction_notes against it"
    )


def test_the_tls_cipher_limitation_is_stated(protocol):
    """A client on a modern TLS stack cannot reach some robots at all.

    Stated in the spec because the symptom (handshake failure) is
    indistinguishable from an unreachable robot, and a client that reports the
    wrong one sends the user hunting for a network fault that is not there.
    """
    tls = protocol["password_disclosure"]["tls"]
    assert "AES128-SHA256" in tls["cipher_note"]
    assert "self-signed" in tls["certificate"]


# ── Commands ─────────────────────────────────────────────────────────────────


def test_every_command_renders_its_published_example(commands):
    """`example_body` is what a consumer diffs against when the robot says no.

    Rendering the arguments must reproduce it byte for byte, including `time`
    as a JSON number — a quoted timestamp is the exact bug this catches.
    """
    for name, command in commands.items():
        expected = command["example_body"]
        # The epoch in every published example, read back out of the example
        # itself so the two cannot drift apart.
        epoch = json.loads(expected)["time"]
        assert render(command, {"time": epoch}) == expected, (
            f"command {name!r} does not render its own example_body"
        )


def test_the_time_argument_is_a_number_not_a_string(commands):
    """The robot rejects payloads whose clock it cannot read."""
    for name, command in commands.items():
        rendered = json.loads(command["example_body"])
        assert isinstance(rendered["time"], int), (
            f"command {name!r} renders `time` as {type(rendered['time'])}"
        )
        assert command["parameters"]["time"]["type"] == "integer"


def test_every_command_publishes_to_a_declared_topic(commands, topics):
    """A command whose topic is not in `mqtt_topics` reaches nothing."""
    for name, command in commands.items():
        assert command["transport"] == "mqtt"
        topic = command["path"]
        assert topic in topics, f"command {name!r} publishes to undeclared {topic!r}"
        assert topics[topic]["direction"] == "publish", (
            f"command {name!r} publishes to {topic!r}, declared as "
            f"{topics[topic]['direction']}"
        )


def test_the_envelope_is_the_same_shape_for_every_command(commands):
    """One envelope, one parser. A command that varies it is a special case
    the consumer has to learn about from prose rather than from the spec."""
    for name, command in commands.items():
        assert list(command["arguments"]) == ["command", "time", "initiator"], (
            f"command {name!r} has a different envelope shape"
        )
        assert command["arguments"]["initiator"] == "localApp"
        assert command["arguments"]["command"] == name or name == "clean"


# ── Entities ─────────────────────────────────────────────────────────────────


def test_every_button_binds_a_real_command(entities, commands):
    """A role map that resolves nowhere is a dead control drawn on screen."""
    buttons = [e for e in entities if e["platform"] == "button"]
    assert buttons, "the mission controls are the point of this spec"
    for entity in buttons:
        assert set(entity["commands"]) == {"press"}
        target = entity["commands"]["press"]
        assert target in commands, (
            f"{entity['name']}: press binds {target!r}, which is undeclared"
        )


def test_every_stateful_entity_reads_a_declared_field(entities, topics):
    """A sensor's dotted path must name a field the topic says it carries.

    The two halves are written in different blocks and nothing but this
    connects them: a typo in the path yields an entity that renders forever as
    'unknown', which reads as a broken robot rather than a broken spec.
    """
    stateful = [e for e in entities if "state_topic" in e]
    assert stateful, "battery and mission state are the readings that matter"
    for entity in stateful:
        topic = topics[entity["state_topic"]]
        declared = {field["name"] for field in topic["payload_format"]["fields"]}
        path = entity["state_mapping"]["value"]
        assert path in declared, (
            f"{entity['name']}: state path {path!r} is not a documented field "
            f"of {entity['state_topic']!r}"
        )


def test_buttons_carry_no_state_binding(entities):
    """Statelessness is the honest description of a keypress.

    schema.json enforces this; restated here because the Roomba is exactly the
    device someone would be tempted to model as a switch, and the reason not to
    is worth having written down: `clean` has no readable inverse, and the
    robot's actual state is a phase string with eight values.
    """
    state_keys = {"state_topic", "state_command", "state_path", "state_mapping"}
    for entity in entities:
        if entity["platform"] != "button":
            continue
        assert not (state_keys & set(entity)), (
            f"{entity['name']}: a button must not bind state"
        )


# ── The honest-limits blocks ─────────────────────────────────────────────────


def test_the_cloud_block_records_what_blocking_it_costs(spec):
    """The hosts list is what a firewall guide is built from, and the
    failure_mode is what stops a reader from blocking the wrong thing."""
    cloud = spec["cloud"]
    assert cloud["required"] is False
    assert cloud["hosts"], "a blocklist needs hosts"
    assert "firmware" in cloud["failure_mode"]
    for endpoint in cloud["endpoints"]:
        assert endpoint["verification"] == "reported", (
            "nothing here was captured by this project"
        )


def test_the_dud_generation_is_declared_as_a_variant(spec):
    """The 2025 models have no local broker; a spec that omits that reads as
    coverage it does not have."""
    variants = spec["device"]["variants"]
    duds = [v for v in variants if "105" in v["model"]]
    assert duds, "the V4 generation must be named"
    assert any("8883" in c for c in duds[0]["characteristics"])


def test_dorita980_is_credited_as_the_source(spec):
    """The protocol is koalazak's work, and the spec says so in the two places
    a machine reads: the openness block and the first helpful_urls entry."""
    openness = spec["device"]["openness"]
    assert openness["source_code"] == "https://github.com/koalazak/dorita980"
    assert openness["license"] == "MIT"
    assert openness["reverse_engineered"] is True
    first = spec["helpful_urls"][0]
    assert "dorita980" in first["url"]
