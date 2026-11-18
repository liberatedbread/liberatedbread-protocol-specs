"""Offline conformance checks for the stock/July June protocol documents.

The behavior below is transcribed from the YAML using only the standard
library. PyYAML and pytest only load the document and run the checks; no Project
July or Home Assistant code is imported, and no network or hardware is used.
All identifiers are synthetic documentation values.
"""

from __future__ import annotations

import ipaddress
import json
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
JULY_PATH = ROOT / "device-specs" / "devices" / "june-oven-project-july.yaml"
STOCK_PATH = ROOT / "device-specs" / "devices" / "june-oven.yaml"


@pytest.fixture(scope="module")
def july() -> dict:
    return yaml.safe_load(JULY_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def stock() -> dict:
    return yaml.safe_load(STOCK_PATH.read_text(encoding="utf-8"))


def connection_online(value):
    if value in ("online", "connected"):
        return True
    if value in ("offline", "disconnected"):
        return False
    return None


def unwrap(value):
    if isinstance(value, dict) and isinstance(value.get("data"), dict):
        return value["data"]
    return value if isinstance(value, dict) else None


def parse_plan(value):
    value = unwrap(value)
    if not isinstance(value, dict):
        return None
    food = value.get("food")
    if not isinstance(food, dict) or not isinstance(food.get("plan"), dict):
        return None
    steps = food["plan"].get("steps")
    steps = steps if isinstance(steps, list) else []
    step_state = value.get("step_state")
    index = step_state.get("step_index", 0) if isinstance(step_state, dict) else 0
    step = steps[index] if isinstance(index, int) and 0 <= index < len(steps) else {}
    return {
        "plan_id": food["plan"].get("id"),
        "name": food.get("name"),
        "session_id": value.get("session_id"),
        "presentation_type": step.get("presentation_type"),
        "target_millic": step.get("temperature_cavity"),
    }


def parse_status(payload):
    online = connection_online(payload.get("ha_connection_state"))
    if online is None:
        online = connection_online(payload.get("connection_state"))
    if online is None and isinstance(payload.get("online"), bool):
        online = payload["online"]
    device_state = None
    for key in ("device_state_data", "device_state"):
        device = unwrap(payload.get(key))
        if device and isinstance(device.get("state"), str) and device["state"]:
            device_state = device["state"]
            break
    plan = parse_plan(payload.get("cook_plan_data"))
    if plan is None:
        plan = parse_plan(payload.get("cook_plan"))
    return online, device_state, plan


def plan(name="proof", plan_id=114, session="session-a", presentation="preheat"):
    return {
        "food": {
            "name": name,
            "plan": {
                "id": plan_id,
                "steps": [{"presentation_type": presentation, "temperature_cavity": 26667}],
            },
        },
        "session_id": session,
        "step_state": {"step_index": 0},
    }


def test_full_status_example_precedence_and_wrapping(july):
    payload = json.loads(july["payload_formats"]["FullStatus"]["example"])
    online, state, current = parse_status(payload)
    assert online is False
    assert state == "idle"
    assert current["plan_id"] == 114
    assert current["name"] == "proof"
    assert current["presentation_type"] == "preheat_and_hold"


@pytest.mark.parametrize(
    ("payload", "expected_online", "expected_state", "expected_plan"),
    [
        ({"connection_state": "connected"}, True, None, None),
        ({"connection_state": "disconnected"}, False, None, None),
        ({"connection_state": "pairing", "online": True}, True, None, None),
        ({"connection_state": "pairing", "online": "true"}, None, None, None),
        (
            {
                "ha_connection_state": "unknown",
                "connection_state": "connected",
                "online": False,
                "device_state_data": {"data": None},
                "device_state": {"state": "active"},
                "cook_plan_data": None,
                "cook_plan": plan("bake", 0),
            },
            True,
            "active",
            0,
        ),
        (
            {
                "ha_connection_state": "online",
                "connection_state": "disconnected",
                "online": False,
                "device_state_data": {"state": "active"},
                "cook_plan_data": {"data": plan("roast", 8)},
                "cook_plan": plan("bake", 0),
            },
            True,
            "active",
            8,
        ),
    ],
)
def test_status_alias_fallbacks(payload, expected_online, expected_state, expected_plan):
    online, state, current = parse_status(payload)
    assert online is expected_online
    assert state == expected_state
    assert (current["plan_id"] if current else None) == expected_plan


def test_plan_parser_uses_selected_step_not_zero():
    value = plan("bake", 9)
    value["food"]["plan"]["steps"] = [
        {"presentation_type": "preheat", "temperature_cavity": 176667},
        {"presentation_type": "cook_bound", "temperature_cavity": 162778},
    ]
    value["step_state"]["step_index"] = 1
    assert parse_plan(value)["target_millic"] == 162778


def test_idle_last_cook_is_history_not_live_fields(july):
    idle = json.loads(july["payload_formats"]["LocalCookIdle"]["example"])
    state = idle.get("state", "idle")
    assert state == "idle"
    for active_key in ("mode", "target_c", "remaining_seconds", "plan"):
        assert active_key not in idle
    assert idle["last_cook"]["mode"] == "bake"
    assert idle["last_cook"]["target_c"] == 177
    assert idle["last_cook"]["eta_seconds"] == 900
    endpoint = next(e for e in july["http_endpoints"] if e["name"] == "Compact Cook Status")
    active = json.loads(endpoint["response_body"]["example"])
    assert active["state"] == "active"
    assert active["mode"] == "bake"
    assert "last_cook" not in active
    assert active["current_c"] == 175.5
    assert active["remaining_seconds"] == 540


_HOSTNAME = re.compile(
    r"(?=.{1,253}$)[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
    r"(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*"
)


def normalize_endpoint(value):
    """Transcribe protocol_details.endpoint_normalization."""
    value = value.strip()
    if not value:
        raise ValueError("missing endpoint")
    try:
        if ipaddress.ip_address(value).version == 6:
            value = f"[{value}]"
    except ValueError:
        pass
    if "://" not in value:
        value = f"https://{value}"
    parsed = urlsplit(value)
    scheme = parsed.scheme.lower()
    if scheme not in ("http", "https"):
        raise ValueError("scheme")
    if (
        parsed.username
        or parsed.password
        or parsed.path.strip("/")
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("endpoint must contain only host and optional port")
    host = parsed.hostname
    if not host:
        raise ValueError("missing host")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("bad port") from exc
    if port is not None and not 1 <= port <= 65535:
        raise ValueError("bad port")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        host = host.rstrip(".")
        if not _HOSTNAME.fullmatch(host):
            raise ValueError("bad hostname") from None
    else:
        host = f"[{address.compressed}]" if address.version == 6 else str(address)
    if (scheme == "http" and port == 80) or (scheme == "https" and port == 443):
        port = None
    return f"{scheme}://{host}" + (f":{port}" if port is not None else "")


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("june.local", "https://june.local"),
        ("June-Oven.local.", "https://june-oven.local"),
        ("192.0.2.50", "https://192.0.2.50"),
        ("https://192.0.2.50:443/", "https://192.0.2.50"),
        ("http://192.0.2.50", "http://192.0.2.50"),
        ("http://192.0.2.50:80", "http://192.0.2.50"),
        ("http://192.0.2.50:8080", "http://192.0.2.50:8080"),
        ("https://192.0.2.50:8443", "https://192.0.2.50:8443"),
        ("fe80::1", "https://[fe80::1]"),
        ("http://[FE80::0001]", "http://[fe80::1]"),
        ("[fe80::1]:8443", "https://[fe80::1]:8443"),
    ],
)
def test_endpoint_normalization(value, expected):
    assert normalize_endpoint(value) == expected
    assert normalize_endpoint(expected) == expected


@pytest.mark.parametrize(
    "value",
    [
        "",
        "ftp://june.local",
        "wss://june.local",
        "user:secret@june.local",
        "https://user@june.local",
        "june.local/local/status",
        "https://june.local?next=/local/status",
        "https://june.local#fragment",
        "june.local:0",
        "june.local:99999",
        "june.local:port",
        "-june.local",
        "june_local",
        "june local",
        "https://",
        "http://[fe80::1",
    ],
)
def test_endpoint_rejection(value):
    with pytest.raises(ValueError):
        normalize_endpoint(value)


def rehome_media(base, candidate):
    parsed = urlsplit(candidate)
    if not parsed.path.startswith("/media/") or ".." in parsed.path.split("/"):
        return None
    query = f"?{parsed.query}" if parsed.query else ""
    return f"{base}{parsed.path}{query}"


def test_media_rehoming_never_follows_embedded_host():
    base = normalize_endpoint("192.0.2.50")
    assert rehome_media(base, "https://api.junelife.com/media/prod/images/latest.jpg?ts=12") == (
        "https://192.0.2.50/media/prod/images/latest.jpg?ts=12"
    )
    for value in (
        "https://api.junelife.com/2/devices/register",
        "https://api.junelife.com/media/../2/devices/pairing",
        "not a url",
    ):
        assert rehome_media(base, value) is None


class OrderGenerator:
    def __init__(self):
        self.last = 0

    def next(self, now_ms):
        order = now_ms & 0x7FFFFFFF
        if order <= self.last:
            order = self.last + 1
        self.last = order
        return order


def test_order_is_strictly_increasing_through_duplicates_and_wrap(july):
    assert "0x7fffffff" in july["protocol_details"]["messaging"]["order_generation"]
    orders = OrderGenerator()
    assert orders.next(1000) == 1000
    assert orders.next(1000) == 1001
    assert orders.next(999) == 1002
    wrapped = OrderGenerator()
    assert wrapped.next(0x80000000) == 1
    assert wrapped.next(0x80000000) == 2
    near_wrap = OrderGenerator()
    assert near_wrap.next(0x7FFFFFFF) == 0x7FFFFFFF
    assert near_wrap.next(0x80000000) == 0x80000000


@dataclass
class CookSession:
    session: str
    presentation: str = "preheat"
    fired: bool = False
    holding: bool = False

    def apply_plan(self, presentation):
        previous = self.presentation
        was_holding = self.holding
        if presentation == "preheat_and_hold":
            if not was_holding:
                self.presentation = presentation
            self.holding = True
        # A stale 10015 cannot undo a later 10016 transition in this session.
        elif not self.holding:
            self.presentation = presentation
        if presentation != "preheat_and_hold" or was_holding or previous == "preheat_and_hold":
            return False
        return self._fire()

    def notification(self, notification_id):
        if notification_id != "NOTIFICATION_PREHEAT_COMPLETE":
            return False
        return self._fire()

    def _fire(self):
        if self.fired:
            return False
        self.fired = True
        return True


def test_preheat_notification_session_dedup_and_stale_plan_order():
    cook = CookSession("session-a")
    assert cook.apply_plan("preheat") is False
    assert cook.apply_plan("preheat_and_hold") is True  # 10016
    assert cook.presentation == "preheat_and_hold"
    assert cook.apply_plan("preheat") is False  # older 10015
    assert cook.presentation == "preheat_and_hold"
    assert cook.notification("NOTIFICATION_PREHEAT_COMPLETE") is False
    assert cook.notification("NOTIFICATION_COOK_COMPLETE") is False
    other = CookSession("session-b")
    assert other.notification("NOTIFICATION_PREHEAT_COMPLETE") is True
    assert other.notification("NOTIFICATION_PREHEAT_COMPLETE") is False


def test_first_seen_holding_does_not_synthesize_a_preheat_event():
    # Documented implementation rule: first-seen holding does not transition.
    freshly_seen = CookSession("session-c", presentation="preheat_and_hold", holding=True)
    assert freshly_seen.apply_plan("preheat_and_hold") is False
    assert freshly_seen.notification("NOTIFICATION_PREHEAT_COMPLETE") is True


class PlanTracker:
    def __init__(self):
        self.active = False
        self.plan_id = None
        self.plan_current = False
        self.start_pending = False
        self.replaced_plan = None

    def report_plan(self, plan_id, active=True, started=False):
        if self.start_pending and not started and plan_id == self.replaced_plan:
            return False
        self.active = active
        self.plan_id = plan_id if active else None
        self.plan_current = active
        self.start_pending = False
        return True

    def start(self, acknowledgement):
        was_current = self.plan_current
        self.replaced_plan = self.plan_id if self.active and was_current else None
        self.plan_current = False
        self.start_pending = True
        if acknowledgement != "success":
            if acknowledgement is not None:
                self.start_pending = False
                self.plan_current = was_current
            return False
        self.active = True
        return True

    def command(self, code, **values):
        if code not in (11004, 11005, 11006):
            raise ValueError(code)
        if not self.active or not self.plan_current or self.plan_id is None:
            raise RuntimeError("no current plan")
        return {"plan_id": self.plan_id, **values}


def test_start_ack_precedes_plan_and_old_telemetry_cannot_win():
    tracker = PlanTracker()
    tracker.report_plan(7)
    assert tracker.start("success") is True
    for code in (11004, 11005, 11006):
        with pytest.raises(RuntimeError):
            tracker.command(code)
    assert tracker.report_plan(7) is False
    with pytest.raises(RuntimeError):
        tracker.command(11006, duration=60000)
    assert tracker.report_plan(8) is True
    assert tracker.command(11006, duration=60000) == {"plan_id": 8, "duration": 60000}
    assert tracker.command(11005, temperature_cavity=190000) == {
        "plan_id": 8,
        "temperature_cavity": 190000,
    }
    assert tracker.command(11004) == {"plan_id": 8}


def test_refused_start_restores_old_plan_but_timeout_does_not():
    tracker = PlanTracker()
    tracker.report_plan(114)
    assert tracker.start("door-open") is False
    assert tracker.command(11004) == {"plan_id": 114}
    timed_out = PlanTracker()
    timed_out.report_plan(7)
    assert timed_out.start(None) is False
    with pytest.raises(RuntimeError):
        timed_out.command(11004)


def temperature_follow_up(status, mode, plan_id, modes):
    if status == "success":
        return "changed-in-place"
    if status is None:
        return "timeout-no-restart"
    mode_rule = modes.get(mode)
    if plan_id != 0 or not mode_rule or not mode_rule["restart_eligible"]:
        return "surface-refusal-no-restart"
    return "cancel-wait-400ms-restart-then-await-new-plan"


def test_11005_only_explicit_refusal_and_only_safe_modes_restart(july):
    modes = july["protocol_details"]["cook_modes"]["modes"]
    assert temperature_follow_up("success", "bake", 0, modes) == "changed-in-place"
    assert temperature_follow_up("not-allowed", "bake", 0, modes).startswith("cancel-wait-400ms")
    assert temperature_follow_up(None, "bake", 0, modes) == "timeout-no-restart"
    for mode in ("broil", "toast", "reheat", "warm", "pizzaiolo", "grill"):
        assert temperature_follow_up("not-allowed", mode, 0, modes) == (
            "surface-refusal-no-restart"
        )
    assert temperature_follow_up("not-allowed", "proof", 114, modes) == (
        "surface-refusal-no-restart"
    )
    assert temperature_follow_up("not-allowed", "sous_vide", 0, modes) == (
        "surface-refusal-no-restart"
    )


def test_airfry_mode_alias_and_temperature_rules(july):
    modes_block = july["protocol_details"]["cook_modes"]
    assert modes_block["legacy_aliases"] == {"air-fry": "airfry"}
    assert "air-fry" not in modes_block["modes"]
    assert modes_block["modes"]["airfry"] == {
        "kind": "variable",
        "phone_min_f": 300,
        "phone_max_f": 450,
        "default_f": 400,
        "restart_eligible": True,
    }
    assert modes_block["modes"]["proof"]["min_f"] == 80
    assert modes_block["modes"]["proof"]["max_f"] == 110
    assert modes_block["modes"]["dehydrate"]["default_f"] == 135
    assert modes_block["modes"]["grill"]["plans"] == [
        {"plan_index": 0, "label": "High", "temperature_f": 450},
        {"plan_index": 1, "label": "Medium", "temperature_f": 400},
        {"plan_index": 2, "label": "Low", "temperature_f": 275},
    ]
    for name in ("broil", "toast", "reheat", "warm", "pizzaiolo", "grill"):
        assert modes_block["modes"][name]["restart_eligible"] is False


def test_discovery_requires_server_fingerprint_not_shared_mdns(july):
    gate = july["protocol_details"]["discovery"]["status_gate"]
    assert gate["required_json"] == {"server": "june-local"}
    assert "mdns_service_type" not in july["device"]["identification"]
    assert july["device"]["discovery"]["methods"][0]["mdns"]["service_type"] == (
        "_http._tcp.local."
    )
    ports = {(entry["scheme"], entry["port"]) for entry in gate["accepted_transports"]}
    assert ports == {("https", 443), ("http", 80)}
    for payload, accepted in (
        ({"server": "june-local"}, True),
        ({"server": "other"}, False),
        ({}, False),
    ):
        assert (payload.get("server") == "june-local") is accepted


def test_signed_frame_byte_preservation_and_stock_vectors_unchanged(july, stock):
    raw = july["payload_formats"]["SignedFrameRelay"]["example"]
    parsed = json.loads(raw)
    forwarded = raw  # Relay parses a copy for routing, then sends original bytes.
    assert forwarded == raw
    assert parsed["message_code"] == 11004
    assert parsed["data"]["plan_id"] == 114
    assert parsed["device_id"] == "companion-example"
    assert parsed["target"]["id"] == "oven-example"
    for key in ("envelope", "signature"):
        assert july["protocol_details"]["messaging"][key] == stock["protocol_details"]["messaging"][key]
    for key in ("protocol", "group", "hash", "identity", "password", "salt", "seal"):
        assert july["protocol_details"]["pairing"][key] == stock["protocol_details"]["pairing"][key]
    vector_urls = [
        entry["url"]
        for entry in stock["helpful_urls"]
        if "printing-press-library" in entry["url"]
    ]
    assert vector_urls == ["https://github.com/mvanhorn/printing-press-library"]
    assert any(
        "printing-press-library" in entry["url"]
        for entry in july["helpful_urls"]
    )


def test_stock_no_local_claims_are_firmware_scoped(stock):
    notes = stock["device"]["notes"]
    assert "STOCK FIRMWARE" in notes
    assert "june-oven-project-july.yaml" in notes
    assert "stock hardware" not in stock["local_access"]["summary"]
    assert "ACTUAL food.plan.id" in stock["protocol_details"]["messaging"]["outgoing_codes"][11004]
    assert "timeout is not refusal" in stock["protocol_details"]["messaging"]["outgoing_codes"][11005]


def test_update_reset_and_camera_safety_are_explicit(july):
    updates = july["protocol_details"]["updates"]
    assert updates["installer"].startswith("Use 0.9.1 only")
    assert "pre-0.9.1" in updates["stable_channel_warning"]
    assert "not kernel" in updates["wireless_scope"]
    assert updates["verification"] == "reported"
    assert july["device"]["testing"]["status"] == "untested"
    gate = july["protocol_details"]["camera_viewer_gate"]
    assert "15 seconds" in gate["stream"]
    assert "seconds=120" in gate["still_polling"]
    assert "every 100 s" in gate["still_polling"]
    assert "stock capture service owns the camera" in gate["ownership"]
