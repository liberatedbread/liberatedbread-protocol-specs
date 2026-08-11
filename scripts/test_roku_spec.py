# Copyright 2026 Pigs Can Fly Labs LLC
# SPDX-License-Identifier: Apache-2.0
"""Proves the Roku spec's control surface can be driven from the spec alone.

`device-specs/devices/roku-ecp.yaml` declares a remote as `button` entities
over HTTP commands. This module transcribes the consumer's side of that
contract — resolve a role to a command, render the command to a request —
and holds the spec to it, the same way its sibling `test_wemo_spec.py` holds
the Wemo SOAP surface honest.

Everything here reads the YAML and the standard library, nothing else. If a
button cannot be rendered into the exact request the official ECP document
publishes, the spec is underspecified and this fails.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SPEC_PATH = REPO_ROOT / "device-specs" / "devices" / "roku-ecp.yaml"

# The keypress vocabulary from the official ECP documentation (see
# device.openness.upstream_docs), spelled as the wire wants each key. The
# standard keys every device accepts, then the TV-class keys. This list is the
# test's own transcription of the doc, so a spec that drifts from the wire
# spelling fails here rather than on a television.
STANDARD_KEYS = {
    "Home",
    "Rev",
    "Fwd",
    "Play",
    "Select",
    "Left",
    "Right",
    "Down",
    "Up",
    "Back",
    "InstantReplay",
    "Info",
    "Backspace",
    "Search",
    "Enter",
    "FindRemote",
}
TV_KEYS = {
    "VolumeUp",
    "VolumeDown",
    "VolumeMute",
    "PowerOn",
    "PowerOff",
    "ChannelUp",
    "ChannelDown",
    "InputTuner",
    "InputHDMI1",
    "InputHDMI2",
    "InputHDMI3",
    "InputHDMI4",
    "InputAV1",
}

# What the official Roku app's remote exposes as buttons, as keys. The
# app-parity claim the entities block makes is exactly this set: everything on
# the app's remote surface that is a single ECP keypress. Backspace/Enter/Lit_
# are the app's keyboard, not buttons, and voice is not ECP at all.
APP_REMOTE_KEYS = (STANDARD_KEYS | TV_KEYS) - {"Backspace", "Enter"}


@pytest.fixture(scope="module")
def spec() -> dict:
    return yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def commands(spec) -> dict:
    return spec["commands"]


@pytest.fixture(scope="module")
def entities(spec) -> list:
    return spec["entities"]


@pytest.fixture(scope="module")
def endpoints(spec) -> dict:
    return {endpoint["name"]: endpoint for endpoint in spec["http_endpoints"]}


# ── Reference implementation, transcribed from the spec ──────────────────────


def render_request(command: dict) -> tuple[str, str]:
    """(method, path) for a command, per ecp_common.request_format.

    The transcription is nearly nothing, which is the point the spec makes:
    the whole request is the method and the path, with an empty body.
    """
    assert command.get("transport") == "http"
    return command["method"], command["path"]


def user_parameters(command: dict) -> list[str]:
    """Parameters the caller supplies: neither defaulted nor read back."""
    return [
        name
        for name, parameter in (command.get("parameters") or {}).items()
        if "default" not in parameter and "source" not in parameter
    ]


# ── Control: entities resolve, commands render ───────────────────────────────


def test_every_entity_binding_resolves(entities, commands):
    """A role map names a command; a name that resolves nowhere is a dead
    control drawn on screen."""
    for entity in entities:
        for role, command_name in (entity.get("commands") or {}).items():
            assert command_name in commands, (
                f"{entity['name']}: {role} binds {command_name!r}, which "
                "`commands` does not declare"
            )


def test_buttons_bind_exactly_the_press_role(entities):
    """A button is momentary: one role, `press`, and no state binding.

    The schema excuses `button` from naming a state source because a keypress
    has none; this holds the entities to the other half of that bargain — no
    state keys smuggled in, and no second role a consumer would have to
    invent semantics for.
    """
    buttons = [e for e in entities if e["platform"] == "button"]
    assert buttons, "the remote is the point of this spec"
    for entity in buttons:
        assert list(entity.get("commands") or {}) == ["press"], (
            f"{entity['name']}: a button binds exactly the `press` role"
        )
        stateful = {"state_topic", "state_endpoint", "state_command", "state_mapping"}
        assert not stateful & set(entity), f"{entity['name']}: a button has no state to read"


def test_press_commands_are_sendable_from_nothing(entities, commands):
    """`press` is a fixed role: the command must have no caller-supplied
    blanks, because a button has nothing to fill one with."""
    for entity in entities:
        for role, command_name in (entity.get("commands") or {}).items():
            if role != "press":
                continue
            blanks = user_parameters(commands[command_name])
            assert not blanks, (
                f"{entity['name']}: press binds {command_name}, which still needs {blanks}"
            )


def test_commands_render_the_documented_requests(commands):
    """Every press command renders to POST /keypress/<key> with a key the
    official vocabulary spells exactly that way."""
    for name, command in commands.items():
        method, path = render_request(command)
        assert method == "POST", f"{name}: keypresses are POSTs"
        prefix, _, key = path.rpartition("/")
        assert prefix == "/keypress", f"{name}: {path} is not a keypress"
        assert key in STANDARD_KEYS | TV_KEYS, f"{name}: {key!r} is not a documented ECP key"


def test_every_command_names_a_documented_action(commands, endpoints):
    """A command is an invocation of a catalogued endpoint; `action` is the
    join, and it must land on an endpoint that still exists."""
    for name, command in commands.items():
        action = command.get("action")
        assert action in endpoints, f"{name}: action {action!r} names no `http_endpoints` entry"
        assert endpoints[action].get("status") != "sunset", (
            f"{name}: {action} is sunset; a control must not be built on it"
        )
        assert command.get("verification"), f"{name}: does not say how well it is known"


def test_the_remote_covers_the_official_apps_buttons(entities, commands):
    """The app-parity claim, executable: every key the official app's remote
    surface sends is a button here, and nothing else is."""
    exposed = {
        render_request(commands[entity["commands"]["press"]])[1].rpartition("/")[2]
        for entity in entities
        if entity["platform"] == "button"
    }
    missing = APP_REMOTE_KEYS - exposed
    assert not missing, f"remote keys the app has and this spec does not: {sorted(missing)}"
    extra = exposed - APP_REMOTE_KEYS
    assert not extra, f"buttons for keys the app's remote does not send: {sorted(extra)}"


def test_button_names_are_unique(entities):
    """Two controls with one name are indistinguishable on screen and in a
    consumer's send-in-flight bookkeeping, which keys on the name."""
    names = [e["name"] for e in entities]
    assert len(names) == len(set(names))


def test_sunset_endpoints_stay_out_of_the_vocabulary(spec):
    """The search-browse sunset is recorded as data, so a consumer can filter
    on it instead of parsing SUNSET out of prose."""
    sunset = [
        endpoint["name"]
        for endpoint in spec["http_endpoints"]
        if endpoint.get("status") == "sunset"
    ]
    assert "Search Browse" in sunset
