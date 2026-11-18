"""Independent stdlib Ozobot Evo native RPC and long-RPC vectors."""

from __future__ import annotations

import struct
import zlib

ADVERTISEMENT = bytes.fromhex(
    "00 00 01 02 03 04 05 06 07 08 09 0a 0b 0c 0d 0e 0f "
    "00 00 00 00 00 04 83 02 01 00"
)
BATTERY_REQUEST = bytes.fromhex("01 00 bc 00 00 00 08 00")
BATTERY_RESPONSE = bytes.fromhex("02 00 00 08 00 00 00 50 01 20 4e 00 00")
LONG_PAYLOAD = bytes(range(25))
DISCOVERY_PATTERN = bytes(23)
DISCOVERY_MASK = bytes.fromhex("ff000000000000000000000000000000000000000000fb")


def parse_advertisement(data: bytes, require_patch: bool = False) -> dict:
    if len(data) < 25 or (require_patch and len(data) != 27):
        raise ValueError("advertisement too short or incomplete patch")
    if data[0] != 0 or data[22] not in (0, 4):
        raise ValueError("not a current Evo identity packet")
    return {
        "device_id": data[1:17].hex(),
        "product": data[22],
        "version": (data[23] & 0x7F, data[24], int.from_bytes(data[25:27], "little") if len(data) >= 27 else 0),
    }


def matches_discovery(company_id: int, data: bytes) -> bool:
    if company_id != 1003 or len(data) < len(DISCOVERY_PATTERN):
        return False
    candidate = data[: len(DISCOVERY_PATTERN)]
    return all(
        (value & mask) == (pattern & mask)
        for value, pattern, mask in zip(candidate, DISCOVERY_PATTERN, DISCOVERY_MASK, strict=True)
    )


def test_masked_discovery_accepts_only_evo_products() -> None:
    assert len(DISCOVERY_PATTERN) == len(DISCOVERY_MASK) == 23
    assert matches_discovery(1003, ADVERTISEMENT)
    evo_zero = bytearray(ADVERTISEMENT)
    evo_zero[22] = 0
    assert matches_discovery(1003, evo_zero)
    ari = bytearray(ADVERTISEMENT)
    ari[22] = 5
    assert not matches_discovery(1003, ari)
    assert not matches_discovery(1003, b"\x01" + ADVERTISEMENT[1:])
    assert not matches_discovery(1003, ADVERTISEMENT[:22])
    assert not matches_discovery(0, ADVERTISEMENT)


def request_id(counter: int) -> tuple[int, bytes]:
    if not 0 <= counter <= 0xFFFFFF:
        raise ValueError("counter outside 24 bits")
    logical = int.from_bytes(b"\x02" + counter.to_bytes(3, "big"), "big")
    return logical, logical.to_bytes(4, "little")


def memread(address: int, length: int) -> bytes:
    return struct.pack("<HIH", 1, address, length)


def parse_memread_response(data: bytes) -> dict:
    if len(data) < 5 or int.from_bytes(data[:2], "little") != 2:
        raise ValueError("not a MemRead response")
    length = int.from_bytes(data[3:5], "little")
    if len(data) != length + 5:
        raise ValueError("MemRead length mismatch")
    if data[2] != 0:
        raise ValueError("MemRead failed")
    return {"result": data[2], "data": data[5:]}


def parse_battery(data: bytes) -> dict:
    if len(data) != 8:
        raise ValueError("battery struct is eight bytes")
    voltage_raw, remaining, fields, timestamp = struct.unpack("<HBBI", data)
    return {
        "voltage_raw": voltage_raw,
        "remaining": remaining,
        "charging": bool(fields & 1),
        "timestamp_ms": timestamp,
    }


def parse_watcher_dirty(data: bytes, region_sizes: list[int]) -> list[bytes]:
    if len(data) < 3 or int.from_bytes(data[:2], "little") != 260:
        raise ValueError("not WatcherDirty")
    payload = data[3:]
    if len(payload) != sum(region_sizes):
        raise ValueError("watcher region length mismatch")
    output = []
    offset = 0
    for size in region_sizes:
        output.append(payload[offset : offset + size])
        offset += size
    return output


def teardown_watcher(watcher_id: int, configured_region_ids: list[int]) -> list[bytes]:
    operations = [
        struct.pack("<HBBHBB", 124, watcher_id, region_id, 0, 0, 3)
        for region_id in configured_region_ids
    ]
    operations.append(struct.pack("<HBBHH", 122, watcher_id, 0, 0, 0))
    return operations


def test_partial_watcher_setup_failure_clears_regions_then_disables() -> None:
    configured_region_ids = [0]
    watcher_enabled = False
    operations = teardown_watcher(0, configured_region_ids) if not watcher_enabled else []
    assert operations == [
        bytes.fromhex("7c 00 00 00 00 00 00 03"),
        bytes.fromhex("7a 00 00 00 00 00 00 00"),
    ]


def long_execute(data: bytes) -> bytes:
    return struct.pack("<HHI", 126, len(data), zlib.crc32(data))


def verify_long_response(response: bytes, staged: bytes) -> bytes:
    if len(response) != 9 or int.from_bytes(response[:2], "little") != 127:
        raise ValueError("bad long-RPC response")
    if response[2] != 0:
        raise ValueError("long RPC failed")
    length = int.from_bytes(response[3:5], "little")
    crc = int.from_bytes(response[5:9], "little")
    if len(staged) != length or zlib.crc32(staged) != crc:
        raise ValueError("long-RPC length/CRC mismatch")
    return staged


def test_advertisement_identity_and_version() -> None:
    parsed = parse_advertisement(ADVERTISEMENT, require_patch=True)
    assert parsed == {
        "device_id": "000102030405060708090a0b0c0d0e0f",
        "product": 4,
        "version": (3, 2, 1),
    }
    for invalid in (ADVERTISEMENT[:24], ADVERTISEMENT[:26], b"\x01" + ADVERTISEMENT[1:]):
        try:
            parse_advertisement(invalid, require_patch=True)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid advertisement accepted")
    ari = bytearray(ADVERTISEMENT)
    ari[22] = 5
    try:
        parse_advertisement(ari)
    except ValueError:
        pass
    else:
        raise AssertionError("Ari accepted as Evo")


def test_request_id_endianness_and_counter_bounds() -> None:
    assert request_id(1) == (0x02000001, bytes.fromhex("01 00 00 02"))
    assert request_id(2) == (0x02000002, bytes.fromhex("02 00 00 02"))
    assert request_id(0xFFFFFF)[1] == b"\xff\xff\xff\x02"
    try:
        request_id(0x1000000)
    except ValueError:
        pass
    else:
        raise AssertionError("counter overflow accepted")


def test_memread_battery_vector_and_malformed_responses() -> None:
    assert BATTERY_REQUEST == memread(0xBC, 8)
    response = parse_memread_response(BATTERY_RESPONSE)
    assert parse_battery(response["data"]) == {
        "voltage_raw": 0,
        "remaining": 80,
        "charging": True,
        "timestamp_ms": 20000,
    }
    for malformed in (BATTERY_RESPONSE[:-1], BATTERY_RESPONSE + b"\x00", b"\x01\x00" + BATTERY_RESPONSE[2:]):
        try:
            parse_memread_response(malformed)
        except ValueError:
            pass
        else:
            raise AssertionError("bad MemRead response accepted")


def test_watcher_setup_teardown_and_region_slicing() -> None:
    assert struct.pack("<HBBHBB", 124, 0, 0, 0xBC, 8, 0) == bytes.fromhex(
        "7c 00 00 00 bc 00 08 00"
    )
    assert struct.pack("<HBBHH", 122, 0, 3, 40, 0) == bytes.fromhex(
        "7a 00 00 03 28 00 00 00"
    )
    assert struct.pack("<HBBHH", 122, 0, 0, 0, 0) == bytes.fromhex(
        "7a 00 00 00 00 00 00 00"
    )
    dirty = bytes.fromhex("04 01 00 00 00 00 50 01 20 4e 00 00 07")
    assert parse_watcher_dirty(dirty, [1, 8, 1]) == [b"\x00", BATTERY_RESPONSE[5:], b"\x07"]
    try:
        parse_watcher_dirty(dirty, [2, 8, 1])
    except ValueError:
        pass
    else:
        raise AssertionError("bad watcher region sizes accepted")


def test_long_rpc_chunks_crc_and_response_validation() -> None:
    assert long_execute(LONG_PAYLOAD) == bytes.fromhex("7e 00 19 00 0c d4 80 d8")
    request_chunks = [LONG_PAYLOAD[i : i + 12] for i in range(0, len(LONG_PAYLOAD), 12)]
    response_chunks = [LONG_PAYLOAD[i : i + 15] for i in range(0, len(LONG_PAYLOAD), 15)]
    assert list(map(len, request_chunks)) == [12, 12, 1]
    assert list(map(len, response_chunks)) == [15, 10]
    assert b"".join(request_chunks) == LONG_PAYLOAD
    response = struct.pack("<HBHI", 127, 0, len(LONG_PAYLOAD), zlib.crc32(LONG_PAYLOAD))
    assert verify_long_response(response, LONG_PAYLOAD) == LONG_PAYLOAD
    for bad in (LONG_PAYLOAD[:-1], LONG_PAYLOAD + b"\x00", bytes(LONG_PAYLOAD[:-1] + b"\xff")):
        try:
            verify_long_response(response, bad)
        except ValueError:
            pass
        else:
            raise AssertionError("bad long-RPC staging accepted")


def test_only_stop_all_is_encoded_no_motion_command() -> None:
    assert struct.pack("<HI", 120, 0) == bytes.fromhex("78 00 00 00 00 00")
