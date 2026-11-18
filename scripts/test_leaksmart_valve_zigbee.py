"""Independent standard-library vectors for the LeakSmart Zigbee valve spec.

PyYAML only loads the document. Frame encoding, response validation, event
handling and monthly-cycle suppression are transcribed here without importing
any repository or coordinator implementation.
"""

from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
SPEC = yaml.safe_load(
    (ROOT / "device-specs" / "devices" / "leaksmart-valve-zigbee.yaml").read_text(
        encoding="utf-8"
    )
)
ZCL = SPEC["protocol_details"]["zigbee"]["zcl"]


def _hex(value):
    return bytes.fromhex(value)


def _build_request(name, request):
    example = _hex(request["example_frame_hex"])
    sequence = example[1]
    if name in {"open", "close", "get_alerts"}:
        control = 0x01
        payload = _hex(request["payload_hex"])
    elif name in {"read_onoff", "read_battery_voltage"}:
        control = 0x00
        payload = _hex(request["payload_hex"])
    elif name == "configure_onoff_reporting":
        control = 0x00
        payload = (
            bytes([0])
            + (0x0000).to_bytes(2, "little")
            + bytes([0x10])
            + (1).to_bytes(2, "little")
            + (300).to_bytes(2, "little")
        )
    elif name == "configure_battery_reporting":
        control = 0x00
        payload = (
            bytes([0])
            + (0x0020).to_bytes(2, "little")
            + bytes([0x20])
            + (3600).to_bytes(2, "little")
            + (43200).to_bytes(2, "little")
            + bytes([2])
        )
    else:
        raise AssertionError(name)
    return bytes([control, sequence, int(request["command_id"], 0)]) + payload


def _parse_read_attributes_response(frame):
    if len(frame) < 5:
        raise ValueError("truncated ZCL response")
    if frame[0] != 0x08 or frame[2] != 0x01:
        raise ValueError("not a general server Read Attributes Response")
    records = []
    position = 3
    widths = {0x10: 1, 0x20: 1}
    while position < len(frame):
        if position + 4 > len(frame):
            raise ValueError("truncated attribute record")
        attribute = int.from_bytes(frame[position : position + 2], "little")
        status = frame[position + 2]
        data_type = frame[position + 3]
        position += 4
        if status:
            raise ValueError("attribute read failed")
        expected_types = {0x0000: 0x10, 0x0020: 0x20}
        if attribute in expected_types and data_type != expected_types[attribute]:
            raise ValueError("wrong attribute type")
        if data_type not in widths:
            raise ValueError("unsupported attribute type")
        width = widths[data_type]
        if position + width > len(frame):
            raise ValueError("truncated attribute value")
        raw = frame[position : position + width]
        position += width
        records.append((attribute, data_type, raw))
    if not records:
        raise ValueError("empty response")
    return records


def _decode_single(frame, expected_attribute, expected_type):
    records = _parse_read_attributes_response(frame)
    if len(records) != 1:
        raise ValueError("expected one attribute")
    attribute, data_type, raw = records[0]
    if (attribute, data_type) != (expected_attribute, expected_type):
        raise ValueError("unexpected attribute/type")
    if expected_attribute == 0x0000:
        return {0: "closed", 1: "open"}[raw[0]]
    if expected_attribute == 0x0020:
        return "unknown" if raw[0] == 0xFF else raw[0] * 0.1
    raise ValueError("unknown decoder")


def _parse_alert_event(command, payload):
    if command not in {0, 1, 2}:
        raise ValueError("unsupported alerts command")
    if len(payload) < 2:
        raise ValueError("short alert/event payload")
    code = payload[1]
    if command in {0, 1}:
        return "clear" if code == 0 else "operation_failure"
    events = {0x80: "start", 0x81: "failure", 0x82: "not_performed", 0x83: "success"}
    if code not in events:
        raise ValueError("unknown event")
    return events[code]


def _cycle_trace(inputs):
    active = False
    obstructed = False
    readback_required = False
    emitted = []
    for kind, value in inputs:
        if kind == "event":
            event = _parse_alert_event(2, bytes([1, value]))
            if event == "start":
                active = True
                emitted.append("maintenance_started")
            elif event == "success":
                active = False
                emitted.append("maintenance_succeeded")
            elif event == "not_performed":
                active = False
                emitted.append("maintenance_warning")
            else:
                active = False
                obstructed = True
                emitted.append("safety_fault")
        elif kind == "alert":
            alert = _parse_alert_event(1, bytes([1, value]))
            if alert == "operation_failure":
                obstructed = True
                emitted.append("safety_fault")
            else:
                readback_required = obstructed
                emitted.append("readback_required" if obstructed else "clear")
        elif kind == "onoff":
            if active:
                emitted.append("suppressed")
            elif obstructed:
                emitted.append("obstructed_readback")
            else:
                emitted.append("open" if value else "closed")
        elif kind == "read_success":
            if readback_required:
                obstructed = False
                readback_required = False
                emitted.append("recovered_closed" if value == 0 else "recovered_open")
            elif not active:
                emitted.append("open" if value else "closed")
        else:
            raise AssertionError(kind)
    return active, obstructed, emitted


def test_zcl_request_frames_rebuild_from_declared_rules():
    for name, request in ZCL["requests"].items():
        assert _build_request(name, request) == _hex(request["example_frame_hex"]), name
    assert ZCL["requests"]["open"]["example_frame_hex"] == "01 21 01"
    assert ZCL["requests"]["close"]["example_frame_hex"] == "01 21 00"
    for name in ("open", "close"):
        command = ZCL["requests"][name]
        assert command["advanced"] is True
        assert command["attended"] is True
        assert command["verification"] == "reported"
        assert command["advanced_reason"]


def test_zcl_readback_voltage_units_and_invalid_sentinel():
    for example in ZCL["readback"]["examples"]:
        expected = example["expected"]
        attribute = int(expected["attribute"], 0)
        data_type = int(expected["type"], 0)
        decoded = _decode_single(_hex(example["frame_hex"]), attribute, data_type)
        if attribute == 0x0000:
            assert decoded == expected["decoded"]
        elif expected["decoded"] == "unknown":
            assert decoded == "unknown"
        else:
            assert decoded == pytest.approx(expected["decoded"])
            assert expected["scale"] == 0.1
            assert expected["unit"] == "V"
    assert _decode_single(bytes.fromhex("08 23 01 20 00 00 20 ff"), 0x20, 0x20) == "unknown"
    field = SPEC["payload_formats"]["BatteryVoltage"]["fields"][0]
    assert (field["scale"], field["unit"], field["type"]) == (0.1, "V", "uint8")


def test_malformed_readbacks_are_rejected_not_published():
    for example in ZCL["readback"]["malformed_examples"]:
        with pytest.raises(ValueError, match="."):
            _parse_read_attributes_response(_hex(example["frame_hex"]))
    with pytest.raises(ValueError, match="wrong attribute type"):
        _decode_single(bytes.fromhex("08 23 01 20 00 00 10 3c"), 0x20, 0x20)
    with pytest.raises(KeyError):
        _decode_single(bytes.fromhex("08 22 01 00 00 00 10 02"), 0x00, 0x10)


def test_alert_and_event_payloads_and_malformed_input():
    alerts = SPEC["protocol_details"]["zigbee"]["alert_events"]
    for example in alerts["alerts"]["examples"]:
        expected = "clear" if example["meaning"] == "clear alert" else "operation_failure"
        assert _parse_alert_event(int(example["command"], 0), _hex(example["payload_hex"])) == expected
    expected_events = {
        "cycle_start": "start",
        "operation_failure": "failure",
        "cycle_not_performed": "not_performed",
        "cycle_succeeded": "success",
    }
    for example in alerts["events"]["examples"]:
        assert _parse_alert_event(2, _hex(example["payload_hex"])) == expected_events[example["event"]]
    for command, payload in ((0, b"\x01"), (1, b""), (2, b"\x01\x7f"), (3, b"\x01\x00")):
        with pytest.raises(ValueError):
            _parse_alert_event(command, payload)


def test_monthly_cycle_trace_suppresses_onoff_and_latches_obstruction():
    inputs = [
        ("event", 0x80),
        ("onoff", 0),
        ("onoff", 1),
        ("event", 0x83),
        ("event", 0x81),
        ("onoff", 0),
        ("alert", 0),
        ("read_success", 0),
    ]
    active, obstructed, emitted = _cycle_trace(inputs)
    expected = [
        step["emitted"]
        for step in SPEC["protocol_details"]["zigbee"]["alert_events"]["trace_vector"][
            "steps"
        ]
    ]
    assert emitted == expected
    assert active is False
    assert obstructed is False
    assert emitted.count("suppressed") == 2
    assert "safety_fault" in emitted
    assert emitted[-1] == "recovered_closed"


def test_failure_during_cycle_is_not_a_normal_completion():
    _, obstructed, emitted = _cycle_trace([("event", 0x80), ("event", 0x81), ("onoff", 0)])
    assert obstructed is True
    assert emitted == ["maintenance_started", "safety_fault", "obstructed_readback"]
    assert "maintenance_succeeded" not in emitted


def test_no_generic_motor_or_cloud_control_surface():
    assert not SPEC.get("entities")
    assert not SPEC.get("commands")
    assert SPEC["cloud"]["required"] is False
    assert SPEC["cloud"]["hosts"] == []
    assert SPEC["device"]["testing"]["status"] == "untested"
