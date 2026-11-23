import base64


def decode_fw_container(encoded):
    payload = base64.b64decode(encoded, validate=True)
    return {"payload": payload, "further_transform": "unknown"}


def test_measured_container_sizes_with_an_invented_payload():
    payload = bytes(range(256)) * 768
    assert len(payload) == 196608
    encoded = base64.b64encode(payload)
    assert len(encoded) == 262144
    decoded = decode_fw_container(encoded)
    assert decoded["payload"] == payload
    assert len(decoded["payload"]) == 196608
    assert decoded["further_transform"] == "unknown"


def test_base64_decoding_does_not_promote_payload_to_raw_flash():
    decoded = decode_fw_container(base64.b64encode(bytes(196608)))
    assert decoded["payload"] == bytes(196608)
    assert decoded["further_transform"] != "raw_arm_image"


def test_invalid_base64_is_rejected():
    try:
        decode_fw_container(b"not base64!")
    except ValueError:
        pass
    else:
        raise AssertionError("invalid base64 must not reach the flasher")
