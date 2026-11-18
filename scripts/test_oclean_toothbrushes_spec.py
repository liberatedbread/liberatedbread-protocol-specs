#!/usr/bin/env python3
"""Independent Oclean routing, layout and fragmented-session checks.

Every session below is invented. No upstream real-data fixture, account, cloud or
health-history record is read by this module. The codec uses only the standard
library; YAML is used solely to hold the published vectors and declarations.
"""

import calendar
from datetime import datetime
from pathlib import Path

import pytest
import yaml

SPEC = yaml.safe_load(
    (Path(__file__).parents[1] / "device-specs/devices/oclean-toothbrushes.yaml").read_text()
)
DETAILS = SPEC["protocol_details"]
VECTORS = {row["name"]: row for row in DETAILS["test_vectors"]}
MAGIC = b"*B#"


def route_for_model(model_id):
    for route_name in ("type1", "type_z1", "air1_legacy"):
        if model_id in DETAILS["model_routing"][route_name]["model_ids"]:
            return route_name
    raise ValueError(f"unsupported model ID: {model_id}")


def encode_type0_time(epoch_seconds):
    return bytes.fromhex("020e") + epoch_seconds.to_bytes(4, "big")


def encode_type1_time(year, month, day, hour, minute, second, weekday, timezone_index):
    return bytes.fromhex("0201") + bytes(
        [year - 2000, month, day, hour, minute, second, weekday, timezone_index]
    )


def timezone_index(offset_minutes):
    offsets = DETAILS["time_calibration"]["timezone_offsets_minutes"]
    return min(range(len(offsets)), key=lambda index: abs(offsets[index] - offset_minutes)) + 1


def local_datetime(year_byte, month, day, hour, minute, second):
    year = year_byte + 2000
    if year < 2015:
        raise ValueError("implausible year")
    return datetime(year, month, day, hour, minute, second)


def utc_epoch(device_datetime, timezone_quarters):
    return int(calendar.timegm(device_datetime.timetuple())) - timezone_quarters * 15 * 60


def parse_status(notification):
    if len(notification) < 6 or notification[:2] != bytes.fromhex("0303"):
        raise ValueError("short or wrong status frame")
    battery = notification[5]
    if battery > 100:
        raise ValueError("invalid battery")
    return {"battery_percent": battery}


def parse_device_settings(notification):
    if notification[:2] != bytes.fromhex("0302"):
        raise ValueError("wrong device-settings marker")
    payload = notification[2:]
    if len(payload) < 6:
        raise ValueError("short device-settings frame")
    output = {
        "battery_percent": payload[0],
        "bind_state_raw": payload[4],
        "mode_number": payload[5],
    }
    if output["battery_percent"] > 100:
        raise ValueError("invalid battery")
    if len(payload) >= 22:
        output["clock_local"] = local_datetime(*payload[16:22]).isoformat(sep=" ")
        output["timezone_index"] = payload[24] if len(payload) >= 25 else None
    if len(payload) >= 32:
        output.update(
            {
                "head_max_time_raw": int.from_bytes(payload[25:27], "big"),
                "head_used_time_raw": int.from_bytes(payload[27:29], "big"),
                "head_used_days": int.from_bytes(payload[29:31], "big"),
                "head_used_times": payload[31],
            }
        )
    return output


def parse_simple(notification):
    if notification[:2] != bytes.fromhex("0308"):
        raise ValueError("wrong 0308 marker")
    payload = notification[2:]
    if len(payload) < 18:
        raise ValueError("short simple session")
    dt = local_datetime(*payload[:6])
    timezone_quarters = int.from_bytes(payload[6:7], "big", signed=True)
    return {
        "local_datetime": dt.isoformat(sep=" "),
        "timezone_quarter_hours": timezone_quarters,
        "utc_epoch": utc_epoch(dt, timezone_quarters),
        "programme_id": payload[8],
        "brush_head_wear_raw": int.from_bytes(payload[14:16], "little"),
        "pressure_raw": int.from_bytes(payload[16:18], "little"),
    }


def parse_extended(notification):
    if notification[:2] != bytes.fromhex("0308"):
        raise ValueError("wrong 0308 marker")
    payload = notification[2:]
    if len(payload) < 2 or payload[0] != 0:
        raise ValueError("not an extended session")
    record_length = int.from_bytes(payload[:2], "big")
    if record_length < 32 or len(payload) < record_length:
        raise ValueError("truncated extended session; never fall back to simple")
    dt = local_datetime(*payload[2:8])
    timezone_quarters = int.from_bytes(payload[19:20], "big", signed=True)
    return {
        "record_length": record_length,
        "duration_total": int.from_bytes(payload[9:11], "big"),
        "valid_duration": int.from_bytes(payload[11:13], "big"),
        "score": payload[28],
        "scheme_type_raw": payload[29],
        "overcross_count": payload[31],
        "utc_epoch": utc_epoch(dt, timezone_quarters),
    }


def parse_inline(notification):
    if notification[:2] != bytes.fromhex("0307") or notification[2:5] != MAGIC:
        raise ValueError("wrong Type 1 header")
    payload = notification[2:]
    if len(payload) < 12:
        raise ValueError("short inline session")
    count = int.from_bytes(payload[3:5], "big")
    if count != 0:
        raise ValueError("nonzero count requires reassembly")
    dt = local_datetime(*payload[5:11])
    output = {
        "record_count": count,
        "local_datetime": dt.isoformat(sep=" "),
        "programme_id": payload[11],
        "score": None,
        "clear_enrichment": True,
    }
    if len(payload) >= 14:
        output["duration_reported"] = int.from_bytes(payload[12:14], "big")
    return output


def parse_record42(record):
    if len(record) != 42:
        raise ValueError("Type 1 record requires exactly 42 bytes")
    dt = local_datetime(*record[:6])
    scheduled = int.from_bytes(record[7:9], "big")
    valid = int.from_bytes(record[9:11], "big")
    if valid > 0 and (scheduled == 0 or valid <= scheduled):
        actual = valid
    elif scheduled > 0:
        actual = scheduled
    else:
        actual = None
    score = record[33] if 0 < record[33] <= 100 else None
    return {
        "local_datetime": dt.isoformat(sep=" "),
        "programme_id": record[6],
        "scheduled_duration": scheduled,
        "valid_duration": valid,
        "actual_duration": actual,
        "pressure_ratio": list(record[11:16]),
        "timezone_index": record[17],
        "gesture_array_raw": list(record[23:31]),
        "gesture_code": (record[30] & 0x0C) >> 2,
        "score": score,
        "point_raw": record[34],
    }


def parse_xx03(notification):
    if (
        len(notification) < 20
        or notification[1:3] != bytes.fromhex("0303")
        or notification[4:9] != bytes.fromhex("ffffffffff")
    ):
        raise ValueError("not an XX03 record")
    dt = local_datetime(*notification[9:15])
    return {
        "score": notification[0] if 0 < notification[0] <= 100 else None,
        "local_datetime": dt.isoformat(sep=" "),
        "programme_id": notification[15],
        "duration_reported": int.from_bytes(notification[16:18], "big"),
    }


class Reassembler:
    def __init__(self):
        self.expected = 0
        self.buffer = bytearray()
        self.records = []
        self.current = None
        self.history = []

    def _accept(self, record):
        parsed = parse_record42(record)
        timestamp = parsed["utc_epoch"] if "utc_epoch" in parsed else parsed["local_datetime"]
        if self.current is None or timestamp > self.current[0]:
            self.current = (timestamp, parsed)
        if timestamp not in {item[0] for item in self.history}:
            self.history.append((timestamp, parsed))
        self.records.append(parsed)

    def _flush(self, expected):
        complete = bytes(self.buffer[:expected])
        for offset in range(0, len(complete), 42):
            self._accept(complete[offset : offset + 42])
        self.expected = 0
        self.buffer.clear()

    def feed(self, packet):
        if self.expected:
            self.buffer.extend(packet)
            if len(self.buffer) >= self.expected:
                self._flush(self.expected)
            return
        if len(packet) >= 8 and packet[2:5] == MAGIC:
            count = int.from_bytes(packet[5:7], "big")
            if count:
                self.expected = count * 42
                self.buffer.extend(packet[7:])
                if len(self.buffer) >= self.expected:
                    self._flush(self.expected)
                return
        raise ValueError("not a fragmented Type 1 header")

    def finish(self):
        if not self.expected:
            return
        complete = len(self.buffer) // 42 * 42
        if complete:
            self._flush(complete)
        else:
            self.expected = 0
            self.buffer.clear()


def notification(name, field="notification_hex"):
    return bytes.fromhex(VECTORS[name][field])


def test_model_routing_is_exact_and_current():
    assert route_for_model("OCLEANY3M") == "type1"
    assert route_for_model("OCLEANY3MH") == "type1"
    assert route_for_model("OCLEANY3") == "type1"
    assert route_for_model("OCLEANY5") == "type_z1"
    assert route_for_model("OCLEANA1") == "air1_legacy"
    assert route_for_model("OCLEANA1d") == "air1_legacy"
    assert route_for_model("OCLEANA1e") == "type1"
    assert route_for_model("OCLEANY2") == "type1"
    assert DETAILS["model_routing"]["type0"]["model_ids"] == []
    with pytest.raises(ValueError, match="unsupported model"):
        route_for_model("OCLEAN-UNKNOWN")


def test_route_characteristics_do_not_follow_retail_name_or_old_reference():
    type1 = {row["operation"]: row for row in DETAILS["model_routing"]["type1"]["queries"]}
    z1 = {row["operation"]: row for row in DETAILS["model_routing"]["type_z1"]["queries"]}
    air1 = {row["operation"]: row for row in DETAILS["model_routing"]["air1_legacy"]["queries"]}
    assert all(row["write_characteristic"] == "fbb89" for row in type1.values())
    assert type1["sessions"]["bytes_hex"] == "0307"
    assert z1["status"]["write_characteristic"] == "fbb85"
    assert z1["sessions"]["write_characteristic"] == "fbb89"
    assert air1["status"]["write_characteristic"] == "fbb85"
    assert air1["sessions"]["write_characteristic"] == "fbb89"
    assert DETAILS["model_routing"]["type_f"]["model_ids"] == []


def test_time_calibration_vectors_and_timezone_ties():
    row = DETAILS["time_calibration"]["examples"][0]
    assert encode_type0_time(row["epoch_seconds"]).hex() == row["command_hex"]
    row = DETAILS["time_calibration"]["examples"][1]
    assert encode_type1_time(2030, 1, 4, 3, 4, 5, 5, 27).hex() == row["command_hex"]
    assert timezone_index(480) == 27
    assert timezone_index(-690) == 1
    assert timezone_index(-630) == 2


def test_status_and_current_device_settings_layouts():
    status = parse_status(notification("synthetic_status_battery"))
    assert status == VECTORS["synthetic_status_battery"]["expected"]
    settings = parse_device_settings(notification("synthetic_device_settings"))
    for field, expected in VECTORS["synthetic_device_settings"]["expected"].items():
        assert settings[field] == expected, field


def test_simple_and_extended_sessions_use_their_own_endianness():
    simple = parse_simple(notification("synthetic_simple_session"))
    for field, expected in VECTORS["synthetic_simple_session"]["expected"].items():
        assert simple[field] == expected, field
    extended = parse_extended(notification("synthetic_extended_session"))
    for field, expected in VECTORS["synthetic_extended_session"]["expected"].items():
        assert extended[field] == expected, field


def test_extended_header_never_falls_back_to_simple():
    frame = bytearray(notification("synthetic_extended_session"))
    with pytest.raises(ValueError, match="never fall back"):
        parse_extended(frame[:20])
    frame[3] = 0
    with pytest.raises(ValueError):
        parse_extended(frame)


def test_inline_zero_count_clears_stale_enrichment():
    decoded = parse_inline(notification("synthetic_type1_inline_empty_enrichment"))
    for field, expected in VECTORS["synthetic_type1_inline_empty_enrichment"]["expected"].items():
        assert decoded[field] == expected
    assert decoded["clear_enrichment"] is True
    assert decoded["score"] is None


def test_full_42_byte_record_fields_and_duration_choice():
    decoded = parse_record42(notification("synthetic_type1_record_42", "record_hex"))
    for field, expected in VECTORS["synthetic_type1_record_42"]["expected"].items():
        assert decoded[field] == expected, field
    changed = bytearray(notification("synthetic_type1_record_42", "record_hex"))
    changed[9:11] = (121).to_bytes(2, "big")
    assert parse_record42(changed)["actual_duration"] == 120
    changed[9:11] = bytes(2)
    assert parse_record42(changed)["actual_duration"] == 120


def test_fragmented_type1_stream_and_continuation_with_marker_prefix():
    record = notification("synthetic_type1_record_42", "record_hex")
    stream = Reassembler()
    stream.feed(bytes.fromhex("0307") + MAGIC + (1).to_bytes(2, "big") + record[:13])
    stream.feed(record[13:33])
    stream.feed(record[33:] + bytes.fromhex("0307ffff"))
    assert len(stream.records) == 1
    assert stream.records[0]["actual_duration"] == 8
    assert stream.records[0]["score"] == 91
    assert stream.expected == 0


def test_partial_final_record_is_dropped_but_complete_records_flush():
    record = notification("synthetic_type1_record_42", "record_hex")
    stream = Reassembler()
    stream.feed(bytes.fromhex("0307") + MAGIC + (2).to_bytes(2, "big") + record + record[:10])
    stream.finish()
    assert len(stream.records) == 1
    truncated = Reassembler()
    truncated.feed(bytes.fromhex("0307") + MAGIC + (1).to_bytes(2, "big") + record[:13])
    truncated.feed(record[13:33])
    truncated.finish()
    assert truncated.records == []


def test_duplicate_timestamp_does_not_clobber_or_duplicate_history():
    record = notification("synthetic_type1_record_42", "record_hex")
    stream = Reassembler()
    header = bytes.fromhex("0307") + MAGIC + (1).to_bytes(2, "big")
    stream.feed(header + record)
    changed = bytearray(record)
    changed[33] = 1
    stream.feed(header + changed)
    assert len(stream.records) == 2
    assert len(stream.history) == 1
    assert stream.current[1]["score"] == 91


def test_xx03_alternate_layout_and_fingerprint():
    decoded = parse_xx03(notification("synthetic_xx03_session"))
    for field, expected in VECTORS["synthetic_xx03_session"]["expected"].items():
        assert decoded[field] == expected, field
    with pytest.raises(ValueError, match="not an XX03"):
        parse_xx03(bytes(20))


@pytest.mark.parametrize(
    "parser,frame",
    [
        (parse_status, bytes.fromhex("0303020e"),
        ),
        (parse_simple, bytes.fromhex("03081a0100"),
        ),
        (parse_inline, bytes.fromhex("03072a42230000"),
        ),
        (parse_xx03, bytes.fromhex("58030300ffffffffff1a00020304055300b4001f"),
        ),
    ],
)
def test_malformed_and_invalid_calendar_frames_are_rejected(parser, frame):
    with pytest.raises(ValueError):
        parser(frame)


def test_invalid_status_battery_and_record_length_are_rejected():
    with pytest.raises(ValueError, match="invalid battery"):
        parse_status(bytes.fromhex("0303020e46650100"))
    with pytest.raises(ValueError, match="exactly 42"):
        parse_record42(bytes(41))


def test_air1_direct_read_fallback_contract():
    fallback = DETAILS["air1_read_fallback"]
    assert fallback["initial_delay_seconds"] == 1.5
    assert fallback["attempts"] == 6
    assert fallback["interval_seconds"] == 1
    reads = [b"", b"", notification("synthetic_status_battery")]
    battery = None
    for read in reads[: fallback["attempts"]]:
        if read:
            battery = parse_status(read)["battery_percent"]
    assert battery == 27
    assert "Do not require a CCCD" in fallback["failure_policy"]
    assert "do not subscribe to fbb89" in fallback["failure_policy"]


def test_type_f_and_destructive_operations_are_not_executable():
    type_f = next(service for service in SPEC["services"] if service["uuid"] == "0000aaaa-0000-1000-8000-00805f9b34fb")
    assert all("commands" not in char for char in type_f["characteristics"])
    for service in SPEC["services"]:
        for char in service["characteristics"]:
            for command in char.get("commands", {}).values():
                assert command.get("value") not in ([0x09, 0xED, 0xEF], [0xF9, 0xED, 0xEF], [0x02, 0x0F])


def test_vectors_are_synthetic_and_reassembly_has_no_record_length_word():
    assert DETAILS["session_reassembly"]["record_length_field_present"] is False
    assert DETAILS["session_reassembly"]["record_bytes"] == 42
    for row in VECTORS.values():
        assert "invented" in row["evidence"].lower() or "synthetic" in row["evidence"].lower()
    assert SPEC["device"]["testing"]["status"] == "untested"


def sync_events(model_id):
    steps = DETAILS["sync_lifecycle"]["order"]
    dis_step = steps[0]
    for characteristic in dis_step["characteristics"]:
        yield "read", characteristic
    route = route_for_model(model_id)
    yield "route", route
    for step in steps[1:]:
        if step["action"] == "write":
            yield "write", step["operation"], route
        else:
            yield step["action"], step["operation"], route


def test_dis_read_and_route_selection_is_first_lifecycle_operation():
    lifecycle = DETAILS["sync_lifecycle"]
    steps = lifecycle["order"]
    assert lifecycle["first_command_related_operation"] == "read_dis_and_select_route"
    assert lifecycle["reconfirm_route_before_every_write"] is True
    assert steps[0]["operation"] == lifecycle["first_command_related_operation"]
    assert steps[0]["action"] == "read"
    assert steps[0]["characteristics"] == [
        "00002a24-0000-1000-8000-00805f9b34fb",
        "00002a27-0000-1000-8000-00805f9b34fb",
        "00002a28-0000-1000-8000-00805f9b34fb",
    ]
    assert steps[1]["operation"] == "calibrate_time"
    assert steps[1]["action"] == "write"
    operations = [step["operation"] for step in steps]
    assert operations.index("calibrate_time") < operations.index("subscribe") < operations.index("query")


@pytest.mark.parametrize(
    ("model_id", "route"),
    [("OCLEANY3M", "type1"), ("OCLEANY5", "type_z1"), ("OCLEANA1", "air1_legacy")],
)
def test_no_write_precedes_known_model_id(model_id, route):
    events = list(sync_events(model_id))
    assert events[:4] == [
        ("read", "00002a24-0000-1000-8000-00805f9b34fb"),
        ("read", "00002a27-0000-1000-8000-00805f9b34fb"),
        ("read", "00002a28-0000-1000-8000-00805f9b34fb"),
        ("route", route),
    ]
    assert all(index > 3 for index, event in enumerate(events) if event[0] == "write")
    assert events[4] == ("write", "calibrate_time", route)
    operations = [event[1] for event in events]
    assert operations.index("calibrate_time") < operations.index("subscribe") < operations.index("query")


def test_unknown_model_stops_after_dis_reads_without_a_write():
    events = []
    with pytest.raises(ValueError, match="unsupported model"):
        for event in sync_events("OCLEAN-UNKNOWN"):
            events.append(event)
    assert events == [
        ("read", "00002a24-0000-1000-8000-00805f9b34fb"),
        ("read", "00002a27-0000-1000-8000-00805f9b34fb"),
        ("read", "00002a28-0000-1000-8000-00805f9b34fb"),
    ]
    assert all(event[0] != "write" for event in events)


def test_identify_only_has_no_generic_model_routed_executable_writes():
    assert SPEC["device"]["integration"] == "identify_only"
    for service in SPEC["services"]:
        for characteristic in service["characteristics"]:
            assert "commands" not in characteristic
    assert "protocol_details" in SPEC
