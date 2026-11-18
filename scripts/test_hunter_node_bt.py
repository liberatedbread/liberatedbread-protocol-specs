"""Independent Hunter NODE-BT PIN, JSON, clock and schedule tests.

Only standard-library algorithms and synthetic values are used. No owner PIN,
address, serial or live controller is involved, and no project code is
imported.
"""

from __future__ import annotations

from datetime import datetime
import json

import pytest


MAX_RESPONSE_BYTES = 65536


def transform(packet: bytes) -> bytes:
    return bytes(value ^ 0xAC if value else 0 for value in packet)


def pin_packet(packet_type: int, result: int, challenge: int, response: int) -> bytes:
    plain = bytes([packet_type, result]) + challenge.to_bytes(2, "little") + response.to_bytes(2, "little")
    return transform(plain)


def decode_pin_packet(wire: bytes) -> tuple[int, int, int, int]:
    if len(wire) != 6:
        raise ValueError("PIN packet must be exactly six bytes")
    plain = transform(wire)
    return plain[0], plain[1], int.from_bytes(plain[2:4], "little"), int.from_bytes(plain[4:6], "little")


def json_chunks(value: dict) -> list[bytes]:
    encoded = json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return [encoded[index : index + 20] for index in range(0, len(encoded), 20)]


def parse_response(chunks) -> dict | None:
    """Accumulate through the first NUL; reject overflow/trailing/malformed data."""
    data = bytearray()
    for chunk in chunks:
        data.extend(chunk)
        if len(data) > MAX_RESPONSE_BYTES:
            raise ValueError("response exceeds 64 KiB")
        if 0 not in data:
            continue
        body, terminator, trailing = bytes(data).partition(b"\x00")
        assert terminator == b"\x00"
        if trailing:
            raise ValueError("trailing data after response NUL")
        value = json.loads(body.decode("utf-8"))
        if not isinstance(value, dict):
            raise ValueError("response must be one JSON object")
        if "Status" in value and (type(value["Status"]) is not int or value["Status"] != 0):
            raise ValueError("controller returned nonzero/malformed status")
        return value
    return None


def validate_patch(patch: dict) -> None:
    if "StartTimes" in patch and "RunTime" in patch:
        raise ValueError("combined start/runtime writes have a known controller defect")
    if "StartTimes" in patch:
        starts = patch["StartTimes"]
        if len(starts) != 8:
            raise ValueError("StartTimes must have eight entries")
        enabled = [value for value in starts if value != 65535]
        if len(enabled) != len(set(enabled)):
            raise ValueError("duplicate start execution is unverified")
        if any(value != 65535 and not 0 <= value < 1440 for value in starts):
            raise ValueError("start is not minutes after midnight")
        if starts != sorted(starts, key=lambda value: (value == 65535, value)):
            raise ValueError("enabled starts must be sorted and compacted")
    if "RunTime" in patch:
        if len(patch["RunTime"]) not in (2, 4):
            raise ValueError("preserve the controller's runtime array shape")
        if any(type(value) is not int or value < 0 for value in patch["RunTime"]):
            raise ValueError("runtimes must be nonnegative integer seconds")


def schedule_transactions(program: str, current: dict, *, starts=None, runtimes=None) -> list[dict]:
    """Plan the mandatory separate runtime/start/readback write sequence."""
    if starts is None and runtimes is None:
        raise ValueError("no schedule change requested")
    transactions = []
    if starts is not None and runtimes is not None:
        zeroed = [0] * len(current["RunTime"])
        transactions.append({program: {"RunTime": zeroed}})
    if starts is not None:
        enabled = sorted(starts)
        if len(enabled) != len(set(enabled)):
            raise ValueError("duplicate start times")
        patch = {"StartTimes": enabled + [65535] * (8 - len(enabled))}
        validate_patch(patch)
        transactions.append({program: patch})
    if runtimes is not None:
        patch = {"RunTime": runtimes}
        validate_patch(patch)
        transactions.append({program: patch})
    if len(transactions) == 2 and starts is not None and runtimes is None:
        raise AssertionError("unreachable")
    for transaction in transactions:
        validate_patch(transaction[program])
    return transactions


def expected_readback(current: dict, patch: dict) -> dict:
    """Merge only transmitted fields; unknown/original fields must survive."""
    return {**current, **patch}


def wall_seconds(year: int, month: int, day: int, hour: int, minute: int, second: int) -> int:
    """Naive local-wall-time encoding, deliberately not a UTC conversion."""
    return max(0, int((datetime(year, month, day, hour, minute, second) - datetime(1970, 1, 1)).total_seconds()))


def test_pin_transform_and_login_vectors():
    assert transform(bytes.fromhex("01 00 ac ff")) == bytes.fromhex("ad 00 00 53")
    assert pin_packet(1, 0, 0, 0).hex() == "ad0000000000"
    assert pin_packet(2, 0, 0x1234, 0).hex() == "ae0098be0000"
    assert pin_packet(3, 0, 0x1234, 0x1234).hex() == "af0098be98be"
    assert pin_packet(3, 0, 0x1234, 1234 ^ 0x1234).hex() == "af0098be4aba"
    assert decode_pin_packet(bytes.fromhex("af0098be4aba")) == (3, 0, 0x1234, 0x16E6)
    assert pin_packet(4, 0, 0, 0).hex() == "a80000000000"
    with pytest.raises(ValueError):
        decode_pin_packet(b"\x00" * 5)


def test_compact_json_20_byte_fragmentation():
    command = {"Manual": {"StationNumber": 1, "RunTime": 60}}
    chunks = json_chunks(command)
    assert all(len(chunk) <= 20 for chunk in chunks)
    assert b"".join(chunks) == b'{"Manual":{"StationNumber":1,"RunTime":60}}'
    assert not b"".join(chunks).endswith(b"\x00")
    unicode_command = {"Station_1": {"Name": "Ångström"}}
    assert b"".join(json_chunks(unicode_command)) == json.dumps(
        unicode_command, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def test_split_and_coalesced_response_handling():
    response = b'{"State":{"ControllerState":0}}\x00'
    assert parse_response([response]) == {"State": {"ControllerState": 0}}
    fragments = [response[:4], response[4:11], response[11:-2], response[-2:]]
    assert parse_response(fragments) == {"State": {"ControllerState": 0}}
    assert parse_response([response[:-1]]) is None
    assert parse_response([b'{"Status":0}\x00']) == {"Status": 0}


def test_malformed_and_ambiguous_responses_fail_visibly():
    with pytest.raises(ValueError, match="trailing"):
        parse_response([b'{"Status":0}\x00{"Status":0}\x00'])
    with pytest.raises(ValueError, match="nonzero"):
        parse_response([b'{"Status":2}\x00'])
    with pytest.raises(ValueError, match="object"):
        parse_response([b"[0]\x00"])
    with pytest.raises(json.JSONDecodeError):
        parse_response([b"{not json}\x00"])
    with pytest.raises(ValueError, match="64 KiB"):
        parse_response([b"x" * (MAX_RESPONSE_BYTES + 1)])


def test_combined_schedule_write_is_rejected_and_replacement_is_separate():
    with pytest.raises(ValueError, match="combined"):
        validate_patch({"StartTimes": [360] + [65535] * 7, "RunTime": [60, 0]})
    current = {
        "Name": "Example",
        "ScheduleType": 0,
        "ScheduleDays": 127,
        "UnknownFutureField": {"preserve": True},
        "StartTimes": [65535] * 8,
        "RunTime": [0, 0],
    }
    plan = schedule_transactions("Program_A", current, starts=[810, 360], runtimes=[180, 60])
    assert plan == [
        {"Program_A": {"RunTime": [0, 0]}},
        {"Program_A": {"StartTimes": [360, 810] + [65535] * 6}},
        {"Program_A": {"RunTime": [180, 60]}},
    ]
    assert all(not {"StartTimes", "RunTime"} <= set(transaction["Program_A"]) for transaction in plan)
    merged = expected_readback(current, plan[-1]["Program_A"])
    assert merged["UnknownFutureField"] == {"preserve": True}
    assert merged["StartTimes"] == [65535] * 8
    # The start-time transaction is independently merged/read back as well.
    assert expected_readback(current, plan[1]["Program_A"])["StartTimes"] == [360, 810] + [65535] * 6


def test_start_sentinel_duplicates_and_shapes():
    with pytest.raises(ValueError, match="duplicate"):
        schedule_transactions("Program_B", {"RunTime": [0, 0]}, starts=[360, 360])
    with pytest.raises(ValueError, match="eight"):
        validate_patch({"StartTimes": [360]})
    with pytest.raises(ValueError, match="shape"):
        validate_patch({"RunTime": [1, 2, 3]})
    assert schedule_transactions("Program_B", {"RunTime": [0, 0]}, runtimes=[30, 0]) == [
        {"Program_B": {"RunTime": [30, 0]}}
    ]


def test_naive_wall_clock_encoding_is_not_unix_utc():
    assert wall_seconds(2026, 9, 8, 19, 21, 0) == 1788895260
    # The actual instant at UTC+2 has a different Unix timestamp.
    assert wall_seconds(2026, 9, 8, 17, 21, 0) == 1788888060
    assert wall_seconds(1969, 12, 31, 23, 59, 59) == 0
