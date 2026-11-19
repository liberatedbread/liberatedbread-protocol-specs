"""Documentary Somfy Developer Mode conformance against a loopback HTTP stub."""

from __future__ import annotations

import json
import re
import threading
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
SPEC = yaml.safe_load((ROOT / "device-specs/devices/somfy-tahoma-developer-mode.yaml").read_text())
COMMANDS = SPEC["commands"]
API_ROOT = "/enduser-mobile-web/1/enduserAPI"
PIN = "2001-0000-0000"
TOKEN = "synthetic-owner-token"
DEVICE_URL = "io://2001-0000-0000/1000001"
LISTENER_ID = "00000000-0000-4000-8000-000000000002"
EXECUTION_ID = "00000000-0000-4000-8000-000000000001"


class GatewayStub(BaseHTTPRequestHandler):
    records = []

    def log_message(self, *args):
        pass

    def _record(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length else b""
        type(self).records.append({
            "method": self.command,
            "path": self.path,
            "authorization": self.headers.get("Authorization"),
            "body": json.loads(body) if body else None,
        })

    def _reply(self, value, status=200):
        data = json.dumps(value, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        self._record()
        if self.path == f"{API_ROOT}/apiVersion":
            self._reply({"protocolVersion": "2022.1.3-1"})
        elif self.path == f"{API_ROOT}/setup":
            self._reply({"devices": [{"deviceURL": DEVICE_URL, "label": "Example Shade"}]})
        elif self.path == f"{API_ROOT}/setup/devices":
            self._reply([{
                "deviceURL": DEVICE_URL,
                "label": "Example Shade",
                "controllableName": "io:VerticalExteriorAwningIOComponent",
                "states": [{"name": "core:OpenClosedState", "type": 3, "value": "closed"}],
            }])
        elif self.path.startswith(f"{API_ROOT}/setup/devices/") and self.path.endswith("/states"):
            self._reply([{"name": "core:OpenClosedState", "type": 3, "value": "open"}])
        elif self.path == f"{API_ROOT}/exec/current":
            self._reply([{"id": EXECUTION_ID, "executionSubType": "MANUAL_CONTROL"}])
        elif self.path == f"{API_ROOT}/exec/current/{EXECUTION_ID}":
            self._reply({"id": EXECUTION_ID, "executionSubType": "MANUAL_CONTROL"})
        else:
            self._reply({"error": "not found", "errorCode": "NOT_FOUND"}, 404)

    def do_POST(self):
        self._record()
        if self.path == f"{API_ROOT}/events/register":
            self._reply({"id": LISTENER_ID})
        elif self.path == f"{API_ROOT}/events/{LISTENER_ID}/fetch":
            self._reply([{
                "name": "DeviceStateChangedEvent",
                "deviceURL": DEVICE_URL,
                "deviceStates": [{"name": "core:OpenClosedState", "type": 3, "value": "open"}],
            }])
        elif self.path == f"{API_ROOT}/events/{LISTENER_ID}/unregister":
            self._reply([])
        elif self.path == f"{API_ROOT}/exec/apply":
            self._reply({"execId": EXECUTION_ID})
        else:
            self._reply({"error": "not found", "errorCode": "NOT_FOUND"}, 404)


@pytest.fixture
def gateway():
    GatewayStub.records = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), GatewayStub)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}", GatewayStub.records
    server.shutdown()
    thread.join(timeout=5)
    server.server_close()


def api_request(base_url: str, name: str, **parameters):
    """Transcribe a documentary command, not a generic mobile consumer."""
    command = COMMANDS[name]
    token = parameters.pop("token", None)
    path = command["path"]
    for key, value in parameters.items():
        if key in ("device_url", "listener_id", "execution_id"):
            value = urllib.parse.quote(str(value), safe="")
        path = path.replace("{" + key + "}", str(value))
    headers = {"Accept": "application/json"}
    for header, template in command.get("headers", {}).items():
        assert token, f"{name} requires a bearer token"
        headers[header] = template.replace("{owner_token}", token)
    body = None
    if "body" in command:
        text = command["body"]
        for key, value in parameters.items():
            text = text.replace("{" + key + "}", str(value))
        body = json.dumps(json.loads(text), separators=(",", ":")).encode()
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(base_url + path, data=body, headers=headers, method=command["method"])
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, json.load(error)


def gateway_hostname(txt: dict, advertised_hostname: str) -> str:
    pin = txt.get("gateway_pin", "")
    if not re.fullmatch(r"[0-9]{4}-[0-9]{4}-[0-9]{4}", pin):
        raise ValueError("invalid gateway_pin")
    if "api_version" not in txt:
        raise ValueError("missing API version")
    expected = f"gateway-{pin}.local"
    if advertised_hostname.rstrip(".").lower() != expected.lower():
        raise ValueError("gateway PIN/hostname mismatch")
    return expected


def can_fetch(last_fetch: float | None, now: float) -> bool:
    interval = SPEC["protocol_details"]["listener"]["minimum_fetch_interval_ms"] / 1000
    return last_fetch is None or now - last_fetch >= interval


def listener_recovery(status: int) -> str:
    return "register_and_resync" if status == 400 else "continue"


def test_version_devices_and_states_are_real_requests_with_correct_bearer(gateway):
    base_url, records = gateway
    status, version = api_request(base_url, "read_api_version")
    assert status == 200
    assert version == {"protocolVersion": "2022.1.3-1"}
    status, devices = api_request(base_url, "read_devices", token=TOKEN)
    assert status == 200
    assert devices[0]["deviceURL"] == DEVICE_URL
    assert devices[0]["states"][0] == {"name": "core:OpenClosedState", "type": 3, "value": "closed"}
    status, states = api_request(base_url, "read_device_states", token=TOKEN, device_url=DEVICE_URL)
    assert status == 200
    assert states[0]["value"] == "open"
    assert records[0]["authorization"] is None
    assert records[1]["authorization"] == f"Bearer {TOKEN}"
    assert records[2]["authorization"] == f"Bearer {TOKEN}"
    assert "io%3A%2F%2F2001-0000-0000%2F1000001" in records[2]["path"]


def test_listener_register_fetch_unregister_real_request_sequence(gateway):
    base_url, records = gateway
    status, registered = api_request(base_url, "register_listener", token=TOKEN)
    assert status == 200
    listener = registered["id"]
    assert listener == LISTENER_ID
    status, events = api_request(base_url, "fetch_events", token=TOKEN, listener_id=listener)
    assert status == 200
    assert events[0]["name"] == "DeviceStateChangedEvent"
    assert events[0]["deviceStates"][0]["value"] == "open"
    status, unregistered = api_request(base_url, "unregister_listener", token=TOKEN, listener_id=listener)
    assert status == 200
    assert unregistered == []
    assert [record["method"] for record in records] == ["POST", "POST", "POST"]
    assert [record["path"] for record in records] == [
        f"{API_ROOT}/events/register",
        f"{API_ROOT}/events/{LISTENER_ID}/fetch",
        f"{API_ROOT}/events/{LISTENER_ID}/unregister",
    ]
    assert all(record["authorization"] == f"Bearer {TOKEN}" for record in records)


def test_listener_rate_limit_timeout_and_invalid_id_recovery():
    listener = SPEC["protocol_details"]["listener"]
    assert listener["inactivity_timeout_seconds"] == 600
    assert listener["minimum_fetch_interval_ms"] == 1000
    assert can_fetch(None, 0) is True
    assert can_fetch(10.0, 10.5) is False
    assert can_fetch(10.0, 11.0) is True
    assert listener_recovery(400) == "register_and_resync"
    assert listener_recovery(200) == "continue"
    assert "rebuild event state from /setup" in listener["recovery"]


def test_execution_apply_and_query_are_real_documentary_requests(gateway):
    base_url, records = gateway
    status, accepted = api_request(base_url, "cover_open", token=TOKEN, device_url=DEVICE_URL)
    assert status == 200
    execution = accepted["execId"]
    assert execution == EXECUTION_ID
    assert records[0]["body"] == {
        "label": "Attended cover open",
        "actions": [{"deviceURL": DEVICE_URL, "commands": [{"name": "open", "parameters": []}]}],
    }
    status, current = api_request(base_url, "get_execution", token=TOKEN, execution_id=execution)
    assert status == 200
    assert current["id"] == execution
    assert [record["method"] for record in records] == ["POST", "GET"]
    assert all(record["authorization"] == f"Bearer {TOKEN}" for record in records)


def test_pin_mismatch_and_txt_requirements_fail_closed():
    txt = {"gateway_pin": PIN, "api_version": "1", "fw_version": "2026.1.1"}
    assert gateway_hostname(txt, f"gateway-{PIN}.local.") == f"gateway-{PIN}.local"
    for hostname in ("gateway-2001-0000-0001.local", "other.local", f"gateway-{PIN}.local.example"):
        with pytest.raises(ValueError, match="mismatch"):
            gateway_hostname(txt, hostname)
    with pytest.raises(ValueError, match="invalid gateway_pin"):
        gateway_hostname({**txt, "gateway_pin": "not-a-pin"}, f"gateway-{PIN}.local")
    with pytest.raises(ValueError, match="missing API"):
        gateway_hostname({"gateway_pin": PIN}, f"gateway-{PIN}.local")
    discovery = SPEC["device"]["discovery"]["methods"][0]["mdns"]
    assert discovery["service_type"] == "_kizboxdev._tcp.local."
    assert discovery["service_type"] != "_kizbox._tcp.local."


def test_identify_only_tls_bearer_and_documentary_command_contract():
    assert SPEC["device"]["integration"] == "identify_only"
    assert SPEC["device"]["testing"]["status"] == "untested"
    identification = SPEC["device"]["identification"]
    assert identification["default_scheme"] == "https"
    assert identification["tls"]["verification"] == "vendor_ca"
    assert "overkiz-root-ca-2048.crt" in identification["tls"]["notes"]
    assert "never a discovered IP substitute" in identification["notes"]
    assert SPEC["protocol_details"]["api"]["request_host"].startswith("gateway-<gateway_pin>.local")
    assert "Never replace it with the mDNS IP" in SPEC["protocol_details"]["api"]["request_host"]
    tls = SPEC["protocol_details"]["tls"]
    assert tls["root_ca_url"] == "https://ca.overkiz.com/overkiz-root-ca-2048.crt"
    assert tls["root_sha256_fingerprint"].startswith("BB:FA:96:11")
    assert "Do not set CERT_NONE" in tls["rule"]

    assert "entities" not in SPEC
    assert "auth_schemes" not in SPEC
    assert not any(command["method"] == "DELETE" for command in COMMANDS.values())
    for name, command in COMMANDS.items():
        if name == "read_api_version":
            assert "headers" not in command
            assert "owner_token" not in command.get("parameters", {})
        else:
            assert command["headers"] == {"Authorization": "Bearer {owner_token}"}, name
            parameter = command["parameters"]["owner_token"]
            assert parameter == {
                "type": "string",
                "required": True,
                "source": "credential:owner_token",
            }, name
    assert COMMANDS["cover_open"]["advanced"] is True
    assert COMMANDS["cover_close"]["advanced"] is True
    assert "advanced" not in COMMANDS["cover_stop"]
    assert "cancel_execution" not in COMMANDS
    assert "cancel_all_executions" not in COMMANDS


def test_activation_exclusions_reset_and_rejoin_boundaries():
    assert SPEC["device"]["setup"]["factory_reset"]["applicable"] == "unknown"
    assert SPEC["device"]["setup"]["rejoin"]["requires_factory_reset"] is False
    assert "visible only at creation" in SPEC["device"]["setup"]["notes"]
    assert "offline" in SPEC["device"]["setup"]["notes"].lower()
    assert SPEC["device"]["pairing"]["unpair"]["supported"] is False
    variants = SPEC["device"]["variants"]
    assert any("Excluded" in variant["model"] for variant in variants)
    assert SPEC["remaining_unknowns"]
