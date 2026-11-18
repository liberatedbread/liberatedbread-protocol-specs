"""Independent discovery and parser vectors for the LAN protocol corrections.

The algorithms below use only the Python standard library and are transcribed
from the specifications. PyYAML is used only to load those specifications; no
repository helper, fixture module or client implementation is imported.
"""

import json
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
NAMES = (
    "weatherflow-tempest-udp",
    "bambu-lab-lan",
    "yeelight-cube-lamp",
    "divoom-pixoo",
    "tplink-kasa-smart-plug",
    "hisense-vidaa",
    "sony-bravia",
)
SPECS = {
    name: yaml.safe_load(
        (ROOT / "device-specs" / "devices" / f"{name}.yaml").read_text(
            encoding="utf-8"
        )
    )
    for name in NAMES
}


def _obs_st(message, fields):
    observations = message["obs"]
    if not isinstance(observations, list) or len(observations) != 1:
        raise ValueError("obs must contain one observation")
    values = observations[0]
    if not isinstance(values, list) or len(values) != 18:
        raise ValueError("Tempest observation must have 18 positions")
    ordered = sorted(fields, key=lambda field: field["index"])
    return {field["name"]: values[field["index"]] for field in ordered}


def _strike(values):
    if len(values) != 3:
        raise ValueError("strike event must have three positions")
    timestamp, distance, energy = values
    return {
        "timestamp": timestamp,
        "distance": None if distance in (None, 63) else distance,
        "energy": energy & ~0x01000000,
    }


def _headers(datagram):
    if isinstance(datagram, str):
        datagram = datagram.encode("ascii")
    lines = datagram.decode("ascii").split("\r\n")
    result = {}
    for line in lines[1:]:
        if not line:
            break
        name, value = line.split(":", 1)
        result[name.lower()] = value.strip()
    return lines[0], result


def _get_prop(names, results):
    if len(names) != len(results):
        raise ValueError("property/result lengths differ")
    decoded = {}
    for name, value in zip(names, results, strict=True):
        if value == "":
            decoded[name] = "" if name == "name" else None
        elif name in {"bright", "ct", "rgb", "hue", "sat", "color_mode"}:
            decoded[name] = int(value, 10)
        else:
            decoded[name] = value
    return decoded


def _speaker_volume(response):
    for entry in response["result"][0]:
        if entry.get("target") == "speaker":
            return entry["volume"]
    raise ValueError("speaker target is unavailable")


def test_weatherflow_passive_discovery_and_observation_vectors():
    spec = SPECS["weatherflow-tempest-udp"]
    methods = spec["device"]["discovery"]["methods"]
    assert len(methods) == 1
    udp = methods[0]["udp_broadcast"]
    assert methods[0]["type"] == "udp_broadcast"
    assert udp["port"] == 50222
    assert udp["passive_ok"] is True
    assert "probe_hex" not in udp
    assert udp["response_format"] == "json"
    assert udp["identity_mapping"]["stable_keys"][0]["source"] == "json:serial_number"

    rule = udp["response_match"][0]
    matcher = re.compile(rule["value"])
    for message_type in (
        "obs_st",
        "obs_air",
        "obs_sky",
        "rapid_wind",
        "evt_precip",
        "evt_strike",
        "device_status",
        "hub_status",
    ):
        assert matcher.fullmatch(message_type)
    assert not matcher.fullmatch("http")

    obs = spec["payload_formats"]["obs_st"]
    assert [field["index"] for field in obs["fields"]] == list(range(18))
    vendor_message = {"obs": json.loads(obs["example"])}
    decoded = _obs_st(vendor_message, obs["fields"])
    assert decoded["timestamp"] == 1588948614
    assert decoded["wind_avg"] == 0.22
    assert decoded["station_pressure"] == 1017.57
    assert decoded["rain_previous_minute"] == 0.0
    assert "0.000000" in obs["example"]
    assert "0.010000" not in obs["example"]
    assert decoded["report_interval"] == 1

    null_message = {"obs": [[None] * 18]}
    nulls = _obs_st(null_message, obs["fields"])
    assert set(nulls.values()) == {None}
    with pytest.raises(ValueError, match="18 positions"):
        _obs_st({"obs": [[0] * 17]}, obs["fields"])

    strike = spec["payload_formats"]["evt_strike"]
    assert _strike(json.loads(strike["example"])) == {
        "timestamp": 1493322445,
        "distance": 27,
        "energy": 3848,
    }
    assert _strike([1493322445, 63, 0x01000F08])["distance"] is None
    assert _strike([1493322445, 63, 0x01000F08])["energy"] == 3848
    assert spec["device"]["setup"]["methods"][0]["type"] == "cloud_account"
    unknowns = " ".join(spec["remaining_unknowns"])
    assert "unsolicited UDP" in unknowns
    assert "account-free station" in unknowns


def test_bambu_notify_and_msearch_discovery_and_mqtt_directions():
    spec = SPECS["bambu-lab-lan"]
    methods = spec["device"]["discovery"]["methods"]
    assert len(methods) == 1
    passive = methods[0]["udp_broadcast"]
    assert methods[0]["type"] == "udp_broadcast"
    assert passive["port"] == 2021
    assert passive["passive_ok"] is True
    assert "probe_hex" not in passive
    assert passive["response_format"] == "http"
    assert passive["response_match"][0]["source"] == "header:NT"
    assert passive["identity_mapping"]["stable_keys"][0]["source"] == "header:USN"
    assert passive["identity_mapping"]["display"]["source"] == (
        "header:DevName.bambu.com"
    )
    assert spec["protocol_details"]["discovery_limitations"][
        "response_match_implemented"
    ] is False

    active = spec["protocol_details"]["active_msearch"]
    assert active["status"] == "experimental_unsupported"
    expected_probe = (
        "M-SEARCH * HTTP/1.1\r\n"
        "HOST:239.255.255.250:2021\r\n"
        'MAN:"ssdp:discover"\r\n'
        "MX:1\r\n"
        "ST:urn:bambulab-com:device:3dprinter:1\r\n"
        "USER-AGENT:OS/version product/version\r\n\r\n"
    )
    assert bytes.fromhex(active["probe_hex"]).decode("ascii") == expected_probe
    assert active["multicast_group"] == "239.255.255.250"
    assert active["response_match"][0]["source"] == "header:ST"

    expected_type = "urn:bambulab-com:device:3dprinter:1"
    notify = (
        "NOTIFY * HTTP/1.1\r\n"
        f"NT:{expected_type}\r\n"
        "USN:TEST-SERIAL-000\r\n"
        "DevName.bambu.com:Test Printer\r\n\r\n"
    )
    _, headers = _headers(notify)
    assert headers.get("nt") == expected_type
    assert headers["usn"] == "TEST-SERIAL-000"
    assert headers["devname.bambu.com"] == "Test Printer"
    response = (
        "HTTP/1.1 200 OK\r\n"
        f"ST:{expected_type}\r\n"
        "USN:TEST-SERIAL-000\r\n\r\n"
    )
    _, active_headers = _headers(response)
    assert active_headers.get("st") == expected_type

    _, wrong_nt = _headers(notify.replace(expected_type, "urn:other:device:1"))
    assert wrong_nt.get("nt") != expected_type
    _, wrong_st = _headers(response.replace(expected_type, "urn:other:device:1"))
    assert wrong_st.get("st") != expected_type
    _, nt_missing = _headers("NOTIFY * HTTP/1.1\r\nUSN:TEST-SERIAL-000\r\n\r\n")
    assert nt_missing.get("nt") is None
    _, st_missing = _headers("HTTP/1.1 200 OK\r\nUSN:TEST-SERIAL-000\r\n\r\n")
    assert st_missing.get("st") is None

    topics = {entry["topic"]: entry for entry in spec["mqtt_topics"]}
    assert topics["device/{serial}/request"]["direction"] == "publish"
    assert topics["device/{serial}/report"]["direction"] == "subscribe"
    assert spec["mqtt"]["transport_security"] == "tls"


def test_yeelight_typed_string_results_and_reverse_tcp_contract():
    spec = SPECS["yeelight-cube-lamp"]
    command = spec["commands"]["get_prop"]
    returned = {entry["name"]: entry for entry in command["returns"]}
    assert {entry["type"] for entry in returned.values()} == {"string"}

    vendor = _get_prop(["power", "not_exist", "bright"], ["on", "", "100"])
    assert vendor == {"power": "on", "not_exist": None, "bright": 100}
    properties = json.loads(command["body"])["params"]
    synthetic = _get_prop(
        properties,
        ["on", "80", "4000", "16711680", "240", "100", "1", "Cube"],
    )
    assert synthetic["bright"] == 80
    assert synthetic["rgb"] == 0xFF0000
    assert synthetic["color_mode"] == 1
    empty_name = _get_prop(["name"], [""])
    assert empty_name == {"name": ""}
    with pytest.raises(ValueError, match="lengths differ"):
        _get_prop(["power", "bright"], ["on"])

    music = spec["commands"]["set_music_on"]
    assert "TCP listener" in music["description"]
    assert "not UDP" in music["description"]
    assert music["parameters"]["port"]["description"].startswith(
        "Client TCP-listener port"
    )
    request = json.loads(music["example_body"])
    assert request["params"][0] == 1
    assert request["params"][1] == "192.168.1.50"
    assert "reverse-TCP" in spec["protocol_details"]["yeelight_lan_protocol"]["transport"]
    assert "silence is not an off reading" in spec["entities"][0]["notes"]


def test_divoom_post_json_examples_and_token_scope():
    spec = SPECS["divoom-pixoo"]
    expected = {
        "get_all_conf": ("Channel/GetAllConf", {}),
        "screen_on": ("Channel/OnOffScreen", {"OnOff": 1}),
        "screen_off": ("Channel/OnOffScreen", {"OnOff": 0}),
        "set_brightness": ("Channel/SetBrightness", {"Brightness": 100}),
    }
    for name, (wire_command, extra) in expected.items():
        command = spec["commands"][name]
        assert command["method"] == "POST"
        assert command["path"] == "/post"
        assert command["headers"]["Content-Type"] == "application/json"
        body = json.loads(command["example_body"])
        assert body == {"Command": wire_command, **extra}
    assert "get_on_off" not in spec["commands"]

    endpoints = {entry["name"]: entry for entry in spec["http_endpoints"]}
    assert endpoints["post_api"]["request_body"]["content_type"] == "application/json"
    assert endpoints["divoom_api"]["request_body"]["content_type"] == (
        "application/json"
    )
    setup = " ".join(yaml.safe_dump(spec["device"]["setup"]).split())
    assert "port-80 `/post` commands need no cloud login" in setup
    assert "separate app channel on port 9000" in setup
    assert "DeviceToken" in setup
    assert "required for all local HTTP commands" not in setup


def test_kasa_rejoin_and_hisense_product_specific_discovery():
    rejoin = SPECS["tplink-kasa-smart-plug"]["device"]["setup"]["rejoin"]
    assert rejoin["in_place_supported"] is True
    assert rejoin["requires_factory_reset"] is False
    assert "netif.set_stainfo" in rejoin["notes"]
    assert "kasa wifi join" in rejoin["notes"]
    assert "remains `reported`" in rejoin["notes"]

    hisense = SPECS["hisense-vidaa"]
    methods = hisense["device"]["discovery"]["methods"]
    assert all(method["type"] != "mdns" for method in methods)
    assert hisense["device"]["identification"]["ssdp_match"][0] == {
        "field": "manufacturer",
        "match": "exact",
        "value": "Hisense",
        "description": hisense["device"]["identification"]["ssdp_match"][0][
            "description"
        ],
    }


def test_sony_json_state_reads_and_speaker_target_selection():
    spec = SPECS["sony-bravia"]
    for name in ("get_power_status", "get_volume_information", "get_playing_content_info"):
        command = spec["commands"][name]
        body = json.loads(command["body"])
        assert command["method"] == "POST"
        assert command["headers"]["Content-Type"] == "application/json"
        assert command["auth"] == ["psk", "pin_cookie"]
        assert isinstance(body["params"], list)
        assert body["version"] == "1.0"

    volume = next(entity for entity in spec["entities"] if entity["name"] == "Volume")
    assert "state_path" not in volume
    assert "not guaranteed to be the speaker" in volume["notes"]
    response = {
        "result": [[
            {"target": "headphone", "volume": 80},
            {"target": "speaker", "volume": 25},
        ]]
    }
    assert _speaker_volume(response) == 25
    with pytest.raises(ValueError, match="speaker target"):
        _speaker_volume({"result": [[{"target": "headphone", "volume": 80}]]})
