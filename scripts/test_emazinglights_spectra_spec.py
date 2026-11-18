def formatted_marker(company_integer, payload):
    return f"{company_integer:x}" + payload.hex()


def raw_candidate(company_integer, payload):
    return company_integer.to_bytes(2, "little") + payload


def discovery_mode(raw_advertisement_available):
    return "candidate_review" if raw_advertisement_available else "manual"


def make_command(opcode, index, payload):
    if len(payload) > 16:
        raise ValueError("payload is limited to 16 bytes")
    frame = bytearray(20)
    frame[0] = 0x55
    frame[1] = opcode
    frame[2] = index
    frame[3 : 3 + len(payload)] = payload
    frame[19] = 0
    for byte in frame[:19]:
        frame[19] ^= byte
    return bytes(frame)


def test_formatted_candidates_still_do_not_choose_a_raw_matcher():
    target = "4c4548554231"
    assert formatted_marker(0x4C45, b"HUB1") == target
    assert formatted_marker(0x004C, b"EHUB1") == target
    assert formatted_marker(0x454C, b"HUB1") != target
    for company, payload in ((0x4C45, b"HUB1"), (0x004C, b"EHUB1")):
        assert b"LEHUB1" not in raw_candidate(company, payload)
        assert discovery_mode(False) == "manual"


def test_invalid_old_company_matcher_is_not_revived():
    assert formatted_marker(0x454C, b"HUB1") == "454c48554231"
    assert formatted_marker(0x454C, b"HUB1") != "4c4548554231"


def test_independent_twenty_byte_xor_frame():
    frame = make_command(0x05, 0, bytes([1, 2, 3]))
    assert len(frame) == 20
    assert frame[:6] == bytes.fromhex("55 05 00 01 02 03")
    assert frame[6:19] == bytes(13)
    checksum = 0
    for byte in frame[:19]:
        checksum ^= byte
    assert frame[19] == checksum
