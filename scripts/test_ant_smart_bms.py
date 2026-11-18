"""Independent ANT legacy/2021+ frame and telemetry tests.

Only standard-library algorithms and public/synthetic fixtures are used. The
legacy and new decoders are deliberately separate; no battery or project code
is contacted or imported.
"""

from __future__ import annotations

import pytest


LEGACY_HEX = (
    "aa55aaff021e0d0a0d0b0d0b0d0b0d550d3f0d6c0d480d880d760d460db20d0b0d0b0d0b0d0b"
    "0000000000000000000000000000000000000000000000000000000000000000000000006400"
    "00000008581e020b3879530a13fbf3001a001dfffb001500000000020102000000000000000000"
    "0c0db2010d0a0d3910ffef00800000000000000b5034090f0d"
)
NEW_HEX = (
    "7ea11100009e050404160000000000000000000088010000000000000000000000001e091b091e"
    "091d091d091e0920091e098f088e0890082209eb08200920091f091e091f091e091f0921091f091d"
    "001d001d001d001e001e00e01315000a0064000101000000b4c40486f197003aede8006a000000a1"
    "f2c0030000000022090c008e080a009400080900006d006a00af02f3fa4c74e5002866ec00c35d62"
    "00ccb39200edc8aa55"
)
DEVICE_INFO_HEX = (
    "7ea1126c02203234424800000000000000000000000032344248554230302d32313130323641"
    "5796ff0b000041f2aa55"
)


def crc_modbus(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc & 0xFFFF


def new_command(function: int, address: int, declared_length: int, data: bytes = b"") -> bytes:
    """Length is a requested read size OR actual auth size, independent of data."""
    frame = bytes([0x7E, 0xA1, function]) + address.to_bytes(2, "little") + bytes([declared_length]) + data
    return frame + crc_modbus(frame[1:]).to_bytes(2, "little") + b"\xaa\x55"


def parse_new_frame(data: bytes, *, expected_function: int | None = 0x11):
    if len(data) < 10 or not data.startswith(b"\x7e\xa1"):
        raise ValueError("invalid 2021+ header")
    declared_total = data[5] + 10
    if len(data) < declared_total:
        raise ValueError("incomplete 2021+ frame")
    function = data[2]
    if expected_function is not None and function != expected_function:
        raise ValueError("unexpected function")
    if len(data) != declared_total and function != 0x12:
        raise ValueError("length quirk is allowed only for device info")
    declared = data[:declared_total]
    if crc_modbus(declared[1:-4]) != int.from_bytes(declared[-4:-2], "little"):
        raise ValueError("invalid 2021+ CRC")
    if function == 0x12:
        if not data.endswith(b"\xaa\x55"):
            raise ValueError("device-info final trailer is missing")
        trailing = data[declared_total - 2 : -2] if len(data) > declared_total else b""
    else:
        if not declared.endswith(b"\xaa\x55"):
            raise ValueError("invalid 2021+ trailer")
        trailing = b""
    return {
        "function": function,
        "address": int.from_bytes(data[3:5], "little"),
        "data": declared[6:-4],
        "trailing": trailing,
    }


def parse_new_stream(chunks) -> list[dict]:
    buffer = bytearray()
    frames = []
    for chunk in chunks:
        buffer.extend(chunk)
        while buffer:
            start = buffer.find(b"\x7e\xa1")
            if start < 0:
                buffer[:] = b"\x7e" if buffer[-1:] == b"\x7e" else b""
                break
            if start:
                del buffer[:start]
            if len(buffer) < 6:
                break
            total = buffer[5] + 10
            if len(buffer) < total:
                break
            candidate_end = total
            if buffer[2] == 0x12 and buffer[total - 4 : total - 2] != b"\xaa\x55":
                final = buffer.find(b"\xaa\x55", total - 2)
                if final < 0:
                    break
                candidate_end = final + 2
            candidate = bytes(buffer[:candidate_end])
            try:
                frame = parse_new_frame(candidate, expected_function=None)
            except ValueError:
                del buffer[0]
                continue
            frames.append(frame)
            del buffer[:candidate_end]
    return frames


def decode_legacy(data: bytes) -> dict:
    if len(data) != 140 or not data.startswith(b"\xaa\x55\xaa\xff"):
        raise ValueError("legacy status is exactly 140 bytes with AA 55 AA FF")
    if sum(data[4:-2]) & 0xFFFF != int.from_bytes(data[-2:], "big"):
        raise ValueError("legacy additive checksum mismatch")
    cells = data[123]
    if cells > 32:
        raise ValueError("cell count exceeds reserved legacy array")
    cycle_charge = int.from_bytes(data[79:83], "big") / 1_000_000
    design_capacity = int.from_bytes(data[75:79], "big") / 1_000_000
    if not design_capacity and data[74]:
        design_capacity = int(round(cycle_charge / data[74] * 100, -1))
    return {
        "pack_voltage": int.from_bytes(data[4:6], "big") * 0.1,
        "cell_voltages": [int.from_bytes(data[6 + 2 * index : 8 + 2 * index], "big") * 0.001 for index in range(cells)],
        "current": int.from_bytes(data[70:74], "big", signed=True) * -0.1,
        "soc": data[74],
        "design_capacity": design_capacity,
        "cycle_charge": cycle_charge,
        "runtime": int.from_bytes(data[87:91], "big"),
        "temperatures": [int.from_bytes(data[91 + 2 * index : 93 + 2 * index], "big", signed=True) for index in range(4)],
        "charge_on": data[103] == 1,
        "discharge_on": data[104] == 1,
        "balancing": bool(data[105] & 4),
        "cell_count": cells,
    }


def parse_legacy_stream(chunks) -> list[dict]:
    buffer = bytearray()
    frames = []
    for chunk in chunks:
        buffer.extend(chunk)
        while buffer:
            start = buffer.find(b"\xaa\x55\xaa\xff")
            if start < 0:
                retained = b""
                for size in (3, 2, 1):
                    if buffer[-size:] == b"\xaa\x55\xaa\xff"[:size]:
                        retained = bytes(buffer[-size:])
                        break
                buffer[:] = retained
                break
            if start:
                del buffer[:start]
            if len(buffer) < 140:
                break
            candidate = bytes(buffer[:140])
            try:
                frames.append(decode_legacy(candidate))
            except ValueError:
                del buffer[0]
                continue
            del buffer[:140]
    return frames


def decode_new_status(frame: bytes) -> dict:
    parsed = parse_new_frame(frame)
    data = parsed["data"]
    temp_count = min(data[2], 6)
    cell_count = min(data[3], 32)
    # data starts at frame offset 6, so frame offset 8/9 are indices 2/3 here.
    cells_offset = 28
    shift = 2 * (cell_count + temp_count)
    if cells_offset + 2 * cell_count + 2 * (temp_count + 2) > len(data):
        raise ValueError("dynamic cell/temperature ranges exceed frame")
    cells = [
        int.from_bytes(data[cells_offset + 2 * index : cells_offset + 2 * index + 2], "little") * 0.001
        for index in range(cell_count)
    ]
    temp_offset = cells_offset + 2 * cell_count
    temperatures = [
        int.from_bytes(data[temp_offset + 2 * index : temp_offset + 2 * index + 2], "little", signed=True)
        for index in range(temp_count + 2)
    ]

    def unsigned(relative_offset: int, width: int) -> int:
        offset = relative_offset + shift
        if offset + width > len(data):
            raise ValueError("dynamic scalar offset exceeds frame")
        return int.from_bytes(data[offset : offset + width], "little")

    def signed(relative_offset: int, width: int) -> int:
        offset = relative_offset + shift
        if offset + width > len(data):
            raise ValueError("dynamic scalar offset exceeds frame")
        return int.from_bytes(data[offset : offset + width], "little", signed=True)

    return {
        "cell_count": cell_count,
        "temp_count": temp_count,
        "cell_voltages": cells,
        "temperatures": temperatures,
        "pack_voltage": unsigned(32, 2) * 0.01,
        "current": signed(34, 2) * 0.1,
        "soc": unsigned(36, 2),
        "soh": unsigned(38, 2),
        "charge_on": unsigned(40, 1) == 1,
        "discharge_on": unsigned(41, 1) == 1,
        "balancing": bool(unsigned(42, 1) & 4),
        "design_capacity": unsigned(44, 4) / 1_000_000,
        "cycle_charge": unsigned(48, 4) / 1_000_000,
        "power": signed(56, 4),
        "delta_cell_voltage": unsigned(76, 2) * 0.001,
    }


def test_crc_and_request_vectors_including_read_length_asymmetry():
    assert crc_modbus(b"123456789") == 0x4B37
    assert new_command(1, 0, 0xBE) == bytes.fromhex("7e a1 01 00 00 be 18 55 aa 55")
    assert new_command(2, 0x026C, 0x20) == bytes.fromhex("7e a1 02 6c 02 20 58 c4 aa 55")
    assert new_command(1, 0, 0xF5) == bytes.fromhex("7e a1 01 00 00 f5 58 62 aa 55")
    assert len(new_command(1, 0, 0xBE)) == 10  # requested reply size is not request payload
    auth = new_command(0x23, 0x6A01, 8, b"12345678")
    assert auth == bytes.fromhex("7e a1 23 01 6a 08 31 32 33 34 35 36 37 38 d9 ee aa 55")
    assert len(auth) == 18


def test_complete_legacy_fixture_and_checksum():
    data = bytes.fromhex(LEGACY_HEX)
    assert len(data) == 140
    assert sum(data[4:-2]) & 0xFFFF == 0x0F0D
    result = decode_legacy(data)
    assert result["pack_voltage"] == 54.2
    assert result["current"] == 0.0
    assert result["soc"] == 100
    assert result["design_capacity"] == 140
    assert result["cycle_charge"] == pytest.approx(139.992578)
    assert result["runtime"] == 169081843
    assert result["cell_count"] == 16
    assert result["cell_voltages"][0] == 3.338
    assert result["cell_voltages"][-1] == 3.339
    assert result["temperatures"] == [26, 29, -5, 21]
    assert result["charge_on"] is False
    assert result["discharge_on"] is True
    assert result["balancing"] is False


def test_complete_new_dynamic_fixture():
    data = bytes.fromhex(NEW_HEX)
    assert len(data) == 168
    result = decode_new_status(data)
    assert result["cell_count"] == 22
    assert result["temp_count"] == 4
    assert result["pack_voltage"] == 50.88
    assert result["current"] == pytest.approx(2.1)
    assert result["soc"] == 10
    assert result["soh"] == 100
    assert result["design_capacity"] == 80
    assert result["cycle_charge"] == pytest.approx(9.957766)
    assert result["power"] == 106
    assert result["delta_cell_voltage"] == 0.148
    assert result["cell_voltages"][0] == 2.334
    assert result["cell_voltages"][-1] == 2.335
    assert result["temperatures"] == [29, 29, 29, 29, 30, 30]
    assert result["charge_on"] is True
    assert result["discharge_on"] is True
    assert result["balancing"] is False


def test_generation_specific_current_signs():
    legacy = bytes.fromhex(LEGACY_HEX)
    changed = bytearray(legacy)
    changed[70:74] = (80).to_bytes(4, "big", signed=True)
    changed[-2:] = (sum(changed[4:-2]) & 0xFFFF).to_bytes(2, "big")
    assert decode_legacy(bytes(changed))["current"] == -8.0
    assert decode_new_status(bytes.fromhex(NEW_HEX))["current"] == 2.1


def test_second_synthetic_dynamic_layout_has_different_offsets():
    # Use the public fixture only as an encoding template; shrink to two cells
    # and one probe, then rebuild data and CRC from documented fields.
    data = bytearray(84)
    data[2], data[3] = 1, 2
    data[28:32] = (3300).to_bytes(2, "little") + (3310).to_bytes(2, "little")
    data[32:34] = (25).to_bytes(2, "little", signed=True)
    data[34:36] = (30).to_bytes(2, "little", signed=True)
    data[36:38] = (31).to_bytes(2, "little", signed=True)
    data[38:40] = (1234).to_bytes(2, "little")
    data[40:42] = (-21).to_bytes(2, "little", signed=True)
    data[42:44] = (88).to_bytes(2, "little")
    data[44:46] = (99).to_bytes(2, "little")
    data[46] = data[47] = 1
    data[48] = 4
    data[50:54] = (50_000_000).to_bytes(4, "little")
    data[54:58] = (25_000_000).to_bytes(4, "little")
    data[62:66] = (-25).to_bytes(4, "little", signed=True)
    data[82:84] = (10).to_bytes(2, "little")
    frame = new_command(0x11, 0, len(data), data)
    result = decode_new_status(frame)
    assert result["cell_voltages"] == pytest.approx([3.3, 3.31])
    assert result["temperatures"] == [25, 30, 31]
    assert result["pack_voltage"] == 12.34
    assert result["current"] == -2.1
    assert result["soc"] == 88
    assert result["soh"] == 99
    assert result["design_capacity"] == 50
    assert result["cycle_charge"] == 25
    assert result["power"] == -25
    assert result["delta_cell_voltage"] == 0.01


def test_split_and_coalesced_frames_for_both_generations():
    legacy = bytes.fromhex(LEGACY_HEX)
    new = bytes.fromhex(NEW_HEX)
    assert len(parse_legacy_stream([legacy + legacy])) == 2
    assert len(parse_legacy_stream([bytes([value]) for value in legacy])) == 1
    assert len(parse_new_stream([new + new])) == 2
    assert len(parse_new_stream([bytes([value]) for value in new])) == 1
    broken = bytearray(new)
    broken[-3] ^= 1
    assert len(parse_new_stream([b"noise" + bytes(broken) + new])) == 1
    assert parse_new_stream([new[:-1]]) == []


def test_two_byte_length_form_is_not_generalized():
    new = bytes.fromhex(NEW_HEX)
    longer = new[:5] + b"\x00" + new[5:]
    with pytest.raises(ValueError):
        parse_new_frame(longer)
    with pytest.raises(ValueError):
        decode_legacy(new)


def test_real_device_info_fixture_declared_crc_final_trailer_and_trailing_bytes():
    data = bytes.fromhex(DEVICE_INFO_HEX)
    assert len(data) == 48
    assert data[5] + 10 == 42
    assert data[38:40] == bytes.fromhex("57 96")
    assert data[40:42] == bytes.fromhex("ff 0b")
    assert data[-2:] == b"\xaa\x55"
    parsed = parse_new_frame(data, expected_function=0x12)
    assert parsed["data"] == data[6:38]
    assert parsed["data"][:16].rstrip(b"\x00") == b"24BH"
    assert parsed["data"][16:32].rstrip(b"\x00") == b"24BHUB00-211026A"
    assert parsed["trailing"] == bytes.fromhex("ff 0b 00 00 41 f2")
    with pytest.raises(ValueError, match="unexpected function"):
        parse_new_frame(data)
    bad_trailer = bytearray(data)
    bad_trailer[-1] ^= 1
    with pytest.raises(ValueError, match="final trailer"):
        parse_new_frame(bytes(bad_trailer), expected_function=0x12)
    bad_crc = bytearray(data)
    bad_crc[38] ^= 1
    with pytest.raises(ValueError, match="CRC"):
        parse_new_frame(bytes(bad_crc), expected_function=0x12)


def test_real_device_info_fixture_fragmented_and_coalesced_stream():
    data = bytes.fromhex(DEVICE_INFO_HEX)
    status = bytes.fromhex(NEW_HEX)
    assert len(parse_new_stream([data])) == 1
    assert len(parse_new_stream([bytes([value]) for value in data])) == 1
    assert len(parse_new_stream([data + data])) == 2
    combined = parse_new_stream([data + status])
    assert [frame["function"] for frame in combined] == [0x12, 0x11]
    assert combined[0]["trailing"] == bytes.fromhex("ff 0b 00 00 41 f2")
    assert parse_new_stream([data[:-1]]) == []
