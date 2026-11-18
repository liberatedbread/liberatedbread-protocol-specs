"""Independent Twinkly RC4, provisioning, JSON and realtime UDP vectors."""

import base64
import hashlib
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC = yaml.safe_load(
    (ROOT / "device-specs/devices/twinkly-lights.yaml").read_text(encoding="utf-8")
)
DETAILS = SPEC["protocol_details"]


def rc4(key, data):
    state = list(range(256))
    j = 0
    for i in range(256):
        j = (j + state[i] + key[i % len(key)]) & 0xFF
        state[i], state[j] = state[j], state[i]
    i = j = 0
    output = bytearray()
    for value in data:
        i = (i + 1) & 0xFF
        j = (j + state[i]) & 0xFF
        state[i], state[j] = state[j], state[i]
        output.append(value ^ state[(state[i] + state[j]) & 0xFF])
    return bytes(output)


def repeated_mac(vector, length):
    mac = bytes.fromhex(vector["mac"].replace(":", " "))
    return (mac * ((length + len(mac) - 1) // len(mac)))[:length]


def json_body(command, **values):
    text = command["body"]
    for name, value in values.items():
        text = text.replace("{" + name + "}", str(value))
    return json.loads(text)


def test_challenge_response_matches_synthetic_spec_vector():
    vector = DETAILS["challenge_verification"]["synthetic_vector"]
    secret = b"evenmoresecret!!"
    key = bytes(
        a ^ b
        for a, b in zip(repeated_mac(vector, 16), secret, strict=True)
    )
    ciphertext = rc4(key, bytes.fromhex(vector["challenge_hex"]))
    assert hashlib.sha1(ciphertext).hexdigest() == vector["expected_sha1"]


def test_provisioning_encryption_matches_legacy_and_current_vectors():
    provisioning = DETAILS["wifi_provisioning"]
    vector = provisioning["synthetic_vector"]
    plaintext = vector["plaintext"].encode().ljust(vector["padded_bytes"], b"\0")
    for section, key, expected in (
        (
            provisioning["legacy_through_2_4_22"],
            provisioning["legacy_through_2_4_22"]["key_schedule_ascii"].encode(),
            vector["legacy_base64"],
        ),
        (
            provisioning["schedule_from_2_4_25"],
            bytes.fromhex(
                provisioning["schedule_from_2_4_25"]["key_schedule_hex"]
            ),
            vector["current_base64"],
        ),
    ):
        derived = bytes(
            a ^ b
            for a, b in zip(repeated_mac(vector, len(key)), key, strict=True)
        )
        assert base64.b64encode(rc4(derived, plaintext)).decode() == expected
        assert section["key_schedule_bytes"] == len(key)


def test_realtime_v2_and_v3_headers_and_fragmentation():
    realtime = DETAILS["realtime"]
    token = bytes(range(1, 9))
    body = bytes(2250)
    v2 = realtime["versions"]["v2"]
    datagram_v2 = bytes([2]) + token + b"\0" + body
    assert datagram_v2[: v2["header_bytes_before_body"]] == bytes(
        [2, 1, 2, 3, 4, 5, 6, 7, 8, 0]
    )

    v3 = realtime["versions"]["v3"]
    maximum = v3["maximum_fragment_body_bytes"]
    fragments = [body[offset : offset + maximum] for offset in range(0, len(body), maximum)]
    assert [len(fragment) for fragment in fragments] == [900, 900, 450]
    for index, fragment in enumerate(fragments):
        datagram = bytes([3]) + token + b"\0\0" + bytes([index]) + fragment
        assert datagram[0] == 3
        assert datagram[9:11] == b"\0\0"
        assert datagram[v3["fragment_number_offset"]] == index
        assert len(datagram) == v3["header_bytes_before_body"] + len(fragment)
        assert datagram[v3["header_bytes_before_body"] :] == fragment
    assert realtime["pixel_channel_order"] == {
        "rgb": ["red", "green", "blue"],
        "rgbw": ["white", "red", "green", "blue"],
    }


def test_color_and_effect_commands_are_bound_without_requiring_a_movie():
    commands = SPEC["commands"]
    assert json_body(commands["turn_on"]) == {"mode": "color"}
    assert json_body(commands["set_color"], red=1, green=2, blue=3) == {
        "red": 1,
        "green": 2,
        "blue": 3,
    }
    assert commands["set_color"]["path"] == "/xled/v1/led/color"
    assert json_body(commands["set_effect"], effect_id=0) == {
        "mode": "effect",
        "effect_id": 0,
    }
    entity = SPEC["entities"][0]
    assert entity["commands"]["set_color"] == "set_color"
    assert entity["commands"]["set_effect"] == "set_effect"
    assert SPEC["device"]["setup"]["credentials"][
        "wifi_passphrase_protection"
    ] == "device_encrypted"


def test_station_provisioning_complete_json_and_authentication_contract():
    vector = DETAILS["wifi_provisioning"]["synthetic_vector"]
    legacy = SPEC["commands"]["provision_station_legacy"]
    assert json_body(
        legacy,
        ssid="synthetic-ssid",
        encpassword=vector["legacy_base64"],
    ) == {
        "mode": 1,
        "station": {
            "ssid": "synthetic-ssid",
            "encpassword": vector["legacy_base64"],
            "dhcp": 1,
        },
    }
    current = SPEC["commands"]["provision_station_current"]
    assert json_body(
        current,
        encssid=vector["current_base64"],
        encpassword=vector["current_base64"],
    ) == {
        "mode": 1,
        "station": {
            "encssid": vector["current_base64"],
            "encpassword": vector["current_base64"],
            "dhcp": 1,
        },
    }
    for command in (legacy, current):
        assert command["path"] == "/xled/v1/network/status"
        assert command["headers"] == {"X-Auth-Token": "<session-token>"}
        assert command["advanced"] is True
    assert DETAILS["wifi_provisioning"]["endpoint"] == "/xled/v1/network/status"
    assert "login and /verify" in DETAILS["wifi_provisioning"]["authentication"]
    assert "2.4.23–2.4.29" in DETAILS["wifi_provisioning"]["transition_unresolved"]
