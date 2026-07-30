"""Cross-spec consistency checks for device-specs/devices/*.yaml.

schema.json says what a spec *may* contain. These tests say what our specs
*should* contain to stay comparable with one another — conventions a schema
cannot express, like "always state `verified` explicitly" or "a device that
needs provisioning must document at least one step".

The point is that someone reading their second spec should already know where
to look. Every failure here is a spec that would surprise them.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parent.parent
DEVICES_DIR = REPO_ROOT / "device-specs" / "devices"
SCHEMA_PATH = REPO_ROOT / "device-specs" / "schema.json"

SPEC_PATHS = sorted(DEVICES_DIR.glob("*.yaml"))

CONFIDENCE_VALUES = {"high", "medium", "low"}
METHOD_TYPES = {
    "none",
    "softap_http",
    "softap_soap",
    "ble_provisioning",
    "ble_direct",
    "wps",
    "smartconfig",
    "wired",
    "device_ui",
    "hub_pairing",
    "button_pairing",
    "cloud_account",
}
ACTORS = {"user", "client", "device"}
PASSPHRASE_PROTECTION = {
    "plaintext",
    "device_encrypted",
    "tls",
    "unknown",
    "not_applicable",
}
NO_PROVISIONING_TYPES = {"none", "ble_direct"}


def load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def specs() -> dict[str, dict]:
    assert SPEC_PATHS, "no device specs found"
    return {path.stem: load(path) for path in SPEC_PATHS}


def setups(specs: dict[str, dict]):
    """Yield (device_id, setup) for every spec that documents setup."""
    for device_id, spec in specs.items():
        setup = spec["device"].get("setup")
        if setup is not None:
            yield device_id, setup


def is_reference(spec: dict) -> bool:
    """True for published-protocol references rather than devices.

    A `device.type` of 'reference-*' (SAE J1979 PIDs, ISO 14229 UDS services,
    ISO 15765-2 framing) marks a file that documents a standard other specs
    cite instead of restating. There is no hardware to set up, so the setup
    conventions below do not apply. schema.json exempts these from the
    access-surface requirement for the same reason.
    """
    return spec["device"].get("type", "").startswith("reference-")


def test_every_device_documents_setup(specs):
    """Setup is not optional in practice — 'nothing to provision' is an answer.

    A missing block is indistinguishable from nobody having looked, which is
    the ambiguity this whole section exists to remove.
    """
    missing = [
        d
        for d, spec in specs.items()
        if "setup" not in spec["device"] and not is_reference(spec)
    ]
    assert not missing, f"specs without a device.setup block: {missing}"


def test_setup_blocks_have_the_same_shape(specs):
    """Same top-level keys everywhere, so readers know where to look."""
    expected = {
        "required",
        "confidence",
        "notes",
        "methods",
        "factory_reset",
        "rejoin",
        "credentials",
    }
    for device_id, setup in setups(specs):
        assert expected <= set(setup), (
            f"{device_id}: setup missing {sorted(expected - set(setup))}"
        )
        assert isinstance(setup["required"], bool), f"{device_id}: required must be bool"
        assert setup["confidence"] in CONFIDENCE_VALUES, (
            f"{device_id}: confidence {setup['confidence']!r} not in {CONFIDENCE_VALUES}"
        )


def test_every_method_states_type_description_and_verified(specs):
    """`verified` absent reads as an oversight, not as 'not yet verified'."""
    for device_id, setup in setups(specs):
        methods = setup["methods"]
        assert methods, f"{device_id}: setup.methods is empty"
        for method in methods:
            label = f"{device_id}:{method.get('type', '?')}"
            assert method["type"] in METHOD_TYPES, f"{label}: unknown method type"
            assert method.get("description"), f"{label}: needs a description"
            assert isinstance(method.get("verified"), bool), (
                f"{label}: must state `verified` explicitly"
            )


def test_verified_methods_are_high_confidence(specs):
    """A flow run against hardware cannot be low confidence."""
    for device_id, setup in setups(specs):
        for method in setup["methods"]:
            if method.get("verified"):
                assert setup["confidence"] == "high", (
                    f"{device_id}: {method['type']} is verified but the block "
                    f"claims {setup['confidence']} confidence"
                )


def test_steps_name_a_valid_actor(specs):
    """`actor` decides what a wizard can automate, so it must be meaningful."""
    for device_id, setup in setups(specs):
        step_lists = [m.get("steps", []) for m in setup["methods"]]
        step_lists += [
            p.get("steps", [])
            for p in setup["factory_reset"].get("procedures", [])
        ]
        step_lists.append(setup["rejoin"].get("steps", []))
        for steps in step_lists:
            for step in steps:
                assert step.get("action"), f"{device_id}: a step has no action"
                actor = step.get("actor")
                assert actor is None or actor in ACTORS, (
                    f"{device_id}: step actor {actor!r} not in {ACTORS}"
                )


def test_devices_that_need_provisioning_document_the_flow(specs):
    """`required: true` with no steps anywhere is a promise the spec breaks."""
    for device_id, setup in setups(specs):
        if not setup["required"]:
            continue
        total = sum(len(m.get("steps", [])) for m in setup["methods"])
        assert total > 0, (
            f"{device_id}: setup.required is true but no method documents steps"
        )


def test_no_provisioning_methods_are_consistent_with_required(specs):
    """A device whose only method is 'nothing to do' must not claim required."""
    for device_id, setup in setups(specs):
        types = {m["type"] for m in setup["methods"]}
        if types <= NO_PROVISIONING_TYPES:
            assert not setup["required"], (
                f"{device_id}: only no-provisioning methods ({sorted(types)}) "
                "but setup.required is true"
            )


def test_ble_devices_use_ble_method_types(specs):
    """A BLE-protocol device should not be described with WiFi onboarding."""
    wifi_only = {"softap_http", "softap_soap", "wps", "smartconfig", "wired"}
    for device_id, spec in specs.items():
        setup = spec["device"].get("setup")
        if not setup or spec["device"]["protocol"] != "ble":
            continue
        types = {m["type"] for m in setup["methods"]}
        assert not (types & wifi_only), (
            f"{device_id}: BLE device documents WiFi-only onboarding {types & wifi_only}"
        )


def test_factory_reset_is_described_not_just_declared(specs):
    """Reset is the entry point to every setup flow; it needs real detail.

    Not every device has one — a vehicle reached over a diagnostic connector
    does not. Those must say so with `applicable: false` and explain why,
    rather than carrying an invented procedure, which on safety-relevant
    hardware is worse than an admission of nothing to document.

    `applicable: unknown` is the third answer, for a device nobody has
    established a reset on. It may still list what to try — dropping a likely
    procedure throws away real knowledge, and it is the first thing someone
    holding the device should attempt — but every procedure under it is a
    candidate by definition, so each must say `verified: false` and cite a
    `basis`. That keeps it usable without letting it read as confirmed.
    """
    for device_id, setup in setups(specs):
        reset = setup["factory_reset"]
        assert reset.get("effect"), (
            f"{device_id}: factory_reset must say what it clears, or why there "
            "is nothing to clear"
        )

        if reset.get("applicable") is False:
            assert not reset.get("procedures"), (
                f"{device_id}: factory_reset is marked not applicable but "
                "still lists procedures"
            )
            continue

        unestablished = reset.get("applicable") == "unknown"
        if unestablished:
            assert reset.get("confidence") == "low", (
                f"{device_id}: an unestablished factory reset is low confidence"
            )
        else:
            assert reset.get("confidence") in CONFIDENCE_VALUES, (
                f"{device_id}: factory_reset needs a confidence level"
            )

        procedures = reset.get("procedures", [])
        # An established reset must show its work. An unestablished one need
        # not — sometimes there is genuinely nothing to suggest.
        if not unestablished:
            assert procedures, f"{device_id}: factory_reset needs at least one procedure"

        for procedure in procedures:
            label = f"{device_id}: reset procedure {procedure.get('name')!r}"
            assert procedure.get("name"), f"{device_id}: a reset procedure has no name"
            assert procedure.get("steps"), f"{label} has no steps"
            if unestablished:
                assert procedure.get("verified") is False, (
                    f"{label} sits under an unestablished reset, so it must say "
                    "`verified: false` — it is a candidate, not a confirmed flow"
                )
            # Any procedure that admits it is unverified owes the reader its
            # source: a vendor manual and a guess-by-analogy are both useful,
            # and they are not equally trustworthy.
            if procedure.get("verified") is False:
                assert procedure.get("basis"), (
                    f"{label} is unverified and must cite a `basis` saying where "
                    "it came from"
                )


def test_rejoin_answers_the_router_replacement_question(specs):
    """The everyday case: can this move networks without a physical reset?"""
    for device_id, setup in setups(specs):
        rejoin = setup["rejoin"]
        assert "requires_factory_reset" in rejoin, (
            f"{device_id}: rejoin must state requires_factory_reset"
        )
        assert isinstance(rejoin["requires_factory_reset"], bool)
        if "in_place_supported" in rejoin:
            assert isinstance(rejoin["in_place_supported"], bool)
            # These two are the same question asked twice; they must agree.
            if rejoin["in_place_supported"]:
                assert not rejoin["requires_factory_reset"], (
                    f"{device_id}: rejoin claims in-place support AND that a "
                    "factory reset is required"
                )


def test_credentials_declare_passphrase_handling(specs):
    """How the user's WiFi passphrase is protected is never 'unspecified'."""
    for device_id, spec in specs.items():
        setup = spec["device"].get("setup")
        if setup is None:
            continue
        credentials = setup["credentials"]
        protection = credentials.get("wifi_passphrase_protection")
        assert protection in PASSPHRASE_PROTECTION, (
            f"{device_id}: wifi_passphrase_protection {protection!r} not in "
            f"{PASSPHRASE_PROTECTION}"
        )
        # not_applicable is only honest when no passphrase crosses a link this
        # spec documents. What settles that is the method type, not the device
        # protocol: `protocol: wifi` here means "reached over IP", and plenty of
        # such devices never receive a passphrase from a client — the hue-bridge
        # is cabled, roku-ecp takes it through the TV's own on-screen UI, and
        # niu-escooter is already online when a client first meets it.
        #
        # `ble_provisioning` needs the same care in the other direction. It used
        # to be treated as proof on its own, but it covers BLE-only cases with no
        # WiFi anywhere: flashing custom firmware (xiaomi-lywsd03mmc), BLE Mesh
        # provisioning (thermopro-tempspike-bbq), lock pairing (nuki-smart-lock).
        # It only implicates a passphrase when the device has WiFi to join.
        if protection == "not_applicable":
            types = {m["type"] for m in setup["methods"]}
            hands_over_credentials = bool(
                types & {"softap_http", "softap_soap", "wps", "smartconfig"}
            ) or ("ble_provisioning" in types and spec["device"]["protocol"] == "wifi")
            assert not hands_over_credentials, (
                f"{device_id}: claims no passphrase is transferred, but "
                f"documents a credential-carrying method ({sorted(types)})"
            )


def test_cloud_only_onboarding_records_whether_a_local_path_exists(specs):
    """The whole point of flagging cloud_account is the recoverability answer."""
    for device_id, setup in setups(specs):
        for method in setup["methods"]:
            if method["type"] != "cloud_account":
                continue
            cloud = method.get("cloud", {})
            assert cloud.get("local_alternative"), (
                f"{device_id}: cloud_account onboarding must state whether any "
                "local alternative exists — 'none known' is a valid answer"
            )


def test_empty_local_name_prefix_is_never_used(specs):
    """An empty prefix matches every BLE device when used as a scan filter."""
    for device_id, spec in specs.items():
        identification = spec["device"].get("identification", {})
        assert identification.get("local_name_prefix", "x") != "", (
            f"{device_id}: local_name_prefix is empty — omit the key instead"
        )


# --------------------------------------------------------------------------
# Schema guards for candidate reset procedures.
#
# The rules below are enforced by schema.json, not by the loops above, so they
# hold for specs nobody has written yet. They are tested by mutation: take a
# real spec, break one rule, and require the schema to notice. Without this a
# future schema edit could drop a guard and every existing spec would still
# validate, because none of them break the rule today.
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def validator() -> Draft202012Validator:
    return Draft202012Validator(json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))


@pytest.fixture(scope="module")
def candidate_reset_spec() -> dict:
    """A real spec whose factory_reset is unestablished with a candidate."""
    return load(DEVICES_DIR / "govee-h6001-bulb.yaml")


def test_candidate_reset_spec_is_valid_to_begin_with(validator, candidate_reset_spec):
    """Guards the mutation tests: they prove nothing if the base is invalid."""
    assert not list(validator.iter_errors(candidate_reset_spec))


def test_unverified_reset_procedure_must_cite_a_basis(validator, candidate_reset_spec):
    """'Try this' is only useful if the reader can weigh where it came from."""
    spec = copy.deepcopy(candidate_reset_spec)
    spec["device"]["setup"]["factory_reset"]["procedures"][0].pop("basis")
    assert list(validator.iter_errors(spec)), (
        "schema accepted an unverified reset procedure with no basis"
    )


def test_unestablished_reset_cannot_hold_a_verified_procedure(
    validator, candidate_reset_spec
):
    """The whole point of `applicable: unknown` is that nothing under it is confirmed."""
    spec = copy.deepcopy(candidate_reset_spec)
    spec["device"]["setup"]["factory_reset"]["procedures"][0]["verified"] = True
    assert list(validator.iter_errors(spec)), (
        "schema accepted a verified procedure under an unestablished reset"
    )
