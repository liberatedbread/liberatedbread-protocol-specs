"""Tests for the Wemo tooling: discovery parsing, control, and setup.

Prerequisites: run from the repo root. Uses only the standard library plus
pytest; the setup-encryption tests additionally need the ``openssl`` binary and
are skipped when it is unavailable.
"""

from __future__ import annotations

import base64
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

# Make scripts/ importable
_scripts_dir = Path(__file__).resolve().parent
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

import wemo_control  # noqa: E402
import wemo_discover  # noqa: E402
import wemo_setup  # noqa: E402

SETUP_XML = b"""<?xml version="1.0"?>
<root xmlns="urn:schemas-upnp-org:device-1-0">
  <device>
    <deviceType>urn:Belkin:device:controllee:1</deviceType>
    <friendlyName>Kitchen Plug</friendlyName>
    <manufacturer>Belkin International Inc.</manufacturer>
    <modelName>Socket</modelName>
    <modelNumber>1.0</modelNumber>
    <serialNumber>221517K0101769</serialNumber>
    <macAddress>94103E36AF15</macAddress>
    <UDN>uuid:Socket-1_0-221517K0101769</UDN>
    <serviceList>
      <service>
        <serviceType>urn:Belkin:service:basicevent:1</serviceType>
        <serviceId>urn:Belkin:serviceId:basicevent1</serviceId>
        <controlURL>/upnp/control/basicevent1</controlURL>
        <eventSubURL>/upnp/event/basicevent1</eventSubURL>
        <SCPDURL>/eventservice.xml</SCPDURL>
      </service>
      <service>
        <serviceType>urn:Belkin:service:WiFiSetup:1</serviceType>
        <serviceId>urn:Belkin:serviceId:WiFiSetup1</serviceId>
        <controlURL>/upnp/control/WiFiSetup1</controlURL>
        <eventSubURL>/upnp/event/WiFiSetup1</eventSubURL>
        <SCPDURL>/setupservice.xml</SCPDURL>
      </service>
    </serviceList>
  </device>
</root>
"""

SOAP_RESPONSE = b"""<?xml version="1.0"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
  <s:Body>
    <u:GetMetaInfoResponse xmlns:u="urn:Belkin:service:metainfo:1">
      <MetaInfo>221517K0101769|94103E36AF15|Wemo Mini</MetaInfo>
    </u:GetMetaInfoResponse>
  </s:Body>
</s:Envelope>
"""


# ── Discovery ────────────────────────────────────────────────────────────────


def test_parse_setup_xml_extracts_identity_and_services():
    device = wemo_discover.parse_setup_xml(SETUP_XML)
    assert device is not None
    assert device.device_type == "urn:Belkin:device:controllee:1"
    assert device.friendly_name == "Kitchen Plug"
    assert device.udn == "uuid:Socket-1_0-221517K0101769"
    assert device.serial_number == "221517K0101769"
    assert device.mac_address == "94103E36AF15"

    # Both services must survive parsing, with their control URLs intact —
    # the WiFiSetup controlURL is what the setup tool resolves at runtime.
    by_type = {s.service_type: s for s in device.services}
    assert set(by_type) == {
        "urn:Belkin:service:basicevent:1",
        "urn:Belkin:service:WiFiSetup:1",
    }
    assert by_type["urn:Belkin:service:WiFiSetup:1"].control_url == (
        "/upnp/control/WiFiSetup1"
    )
    assert by_type["urn:Belkin:service:basicevent:1"].event_sub_url == (
        "/upnp/event/basicevent1"
    )


def test_parse_setup_xml_without_namespace():
    """Some firmware serves the description without the UPnP namespace."""
    device = wemo_discover.parse_setup_xml(
        SETUP_XML.replace(b' xmlns="urn:schemas-upnp-org:device-1-0"', b"")
    )
    assert device is not None
    assert device.friendly_name == "Kitchen Plug"
    assert len(device.services) == 2


def test_parse_setup_xml_rejects_garbage():
    assert wemo_discover.parse_setup_xml(b"not xml at all") is None


def test_parse_ip_port():
    assert wemo_discover.parse_ip_port("http://192.168.1.42:49153/setup.xml") == (
        "192.168.1.42",
        49153,
    )
    assert wemo_discover.parse_ip_port("http://192.168.1.42/setup.xml") == (
        "192.168.1.42",
        80,
    )


def test_is_wemo_filters_other_upnp_responders():
    """ssdp:all makes every UPnP device on the LAN answer; only Wemo counts."""
    wemo = wemo_discover.WemoDevice(
        location_url="",
        ip="192.168.1.42",
        port=49153,
        manufacturer="Belkin International Inc.",
    )
    printer = wemo_discover.WemoDevice(
        location_url="",
        ip="192.168.1.9",
        port=80,
        manufacturer="Brother",
        device_type="urn:schemas-upnp-org:device:Printer:1",
        raw_ssdp_response="HTTP/1.1 200 OK\r\nSERVER: Linux/3.0 UPnP/1.0\r\n",
    )
    assert wemo_discover.is_wemo(wemo)
    assert not wemo_discover.is_wemo(printer)


# ── Control ──────────────────────────────────────────────────────────────────


def test_parse_insight_params_field_alignment():
    """wifipower sits between timeperiod and currentpower_mw.

    Regression test: an earlier field list omitted wifipower, which shifted
    every power reading one column to the left.
    """
    raw = "8|1700000000|100|200|300|1209600|8000|18500|1200|9900|8000"
    parsed = wemo_control.parse_insight_params(raw)

    assert parsed["state"] == "8"
    assert parsed["timeperiod"] == "1209600"
    assert parsed["wifipower"] == "8000"
    assert parsed["currentpower_mw"] == "18500"
    assert parsed["powerthreshold"] == "8000"


def test_parse_insight_params_keeps_extra_fields():
    raw = "|".join(["0"] * len(wemo_control.INSIGHT_PARAM_FIELDS) + ["42"])
    parsed = wemo_control.parse_insight_params(raw)
    assert parsed[f"field_{len(wemo_control.INSIGHT_PARAM_FIELDS)}"] == "42"


def test_parse_soap_values_returns_every_named_child():
    values = wemo_control.parse_soap_values(SOAP_RESPONSE)
    assert values == {"MetaInfo": "221517K0101769|94103E36AF15|Wemo Mini"}


def test_parse_soap_values_on_garbage():
    assert wemo_control.parse_soap_values(b"<not-soap/>") == {}


def test_soap_body_matches_the_reference_wire_format():
    """The namespace goes on the action element, arguments are unqualified.

    ElementTree hoists namespace declarations to the root, which is equivalent
    XML but not what Wemo firmware normally receives; these devices run crude
    parsers, so the wire format is pinned to what pywemo and ouimeaux send.
    """
    body = wemo_control.build_soap_body(
        wemo_control.SERVICE_WIFI,
        "ConnectHomeNetwork",
        {"ssid": "HomeNet", "channel": "6"},
    ).decode("utf-8")

    assert '<u:ConnectHomeNetwork xmlns:u="urn:Belkin:service:WiFiSetup:1">' in body
    assert "<ssid>HomeNet</ssid>" in body
    assert "<channel>6</channel>" in body
    assert "u:ssid" not in body
    assert body.startswith('<?xml version="1.0" encoding="utf-8"?>')


def test_soap_body_escapes_argument_values():
    """An SSID containing & must not produce a malformed document."""
    body = wemo_control.build_soap_body(
        wemo_control.SERVICE_WIFI, "ConnectHomeNetwork", {"ssid": "Ben & Jerry"}
    )
    assert b"<ssid>Ben &amp; Jerry</ssid>" in body
    # Must still parse.
    import xml.etree.ElementTree as ET

    ET.fromstring(body)


# ── Setup ────────────────────────────────────────────────────────────────────

META_INFO = "94103E36AF15|221517K0101769|Wemo_WW|WeMo_US_2.00.11408|Wemo.Mini.4A2|Socket"


def test_meta_info_field_order():
    """Field 0 is the MAC and field 1 the serial — not the other way round.

    Getting this backwards silently produces a valid-looking but undecryptable
    passphrase, so it is worth pinning.
    """
    meta = wemo_setup.MetaInfo.parse(META_INFO)
    assert meta.mac == "94103E36AF15"
    assert meta.serial_number == "221517K0101769"
    assert meta.firmware_version == "WeMo_US_2.00.11408"
    assert meta.access_point_ssid == "Wemo.Mini.4A2"


def test_meta_info_rejects_short_string():
    with pytest.raises(wemo_setup.SetupError):
        wemo_setup.MetaInfo.parse("94103E36AF15|221517K0101769")


def test_build_key_data_variants():
    """The three key layouts, as implemented by pywemo."""
    meta = wemo_setup.MetaInfo.parse(META_INFO)
    mac, serial = meta.mac, meta.serial_number

    assert wemo_setup.build_key_data(meta, 1) == mac[:6] + serial + mac[6:12]
    assert wemo_setup.build_key_data(meta, 2) == (
        mac[:6] + serial + mac[6:12] + wemo_setup.METHOD2_KEY_SUFFIX
    )
    assert wemo_setup.build_key_data(meta, 3) == (
        mac[:3]
        + mac[9:12]
        + serial
        + wemo_setup.METHOD3_KEY_EXTRA
        + mac[6:9]
        + mac[3:6]
    )


def test_build_key_data_rejects_unknown_method():
    meta = wemo_setup.MetaInfo.parse(META_INFO)
    with pytest.raises(wemo_setup.SetupError):
        wemo_setup.build_key_data(meta, 4)


def test_detect_encryption_method():
    """rtos without iot selects method 2, which omits the length suffix."""

    def device(**extras):
        return wemo_discover.WemoDevice(
            location_url="", ip="10.22.22.1", port=49153, config_extras=extras
        )

    assert wemo_setup.detect_encryption_method(device()) == (1, True)
    assert wemo_setup.detect_encryption_method(device(rtos="1")) == (2, False)
    assert wemo_setup.detect_encryption_method(device(rtos="1", iot="1")) == (1, True)
    assert wemo_setup.detect_encryption_method(device(iot="1")) == (1, True)


def test_parse_ap_list_skips_header_and_splits_auth():
    """SSID is column 0, channel column 1, and AUTH/CIPHER is the LAST column."""
    ap_list = (
        "3\n"
        "HomeNet|6|WPA2PSK|blah|WPA2PSK/AES,\n"
        "OpenGuest|11|OPEN|blah|OPEN/NONE,\n"
        "NewFangled|1|SAE|blah|Unknown,\n"
    )
    aps = wemo_setup.parse_ap_list(ap_list)

    assert [ap.ssid for ap in aps] == ["HomeNet", "OpenGuest", "NewFangled"]

    home = aps[0]
    assert (home.channel, home.auth_mode, home.encryption) == ("6", "WPA2PSK", "AES")
    assert home.supported

    assert aps[1].encryption == "NONE" and aps[1].supported
    # WPA3 and anything else the device cannot express comes back as Unknown.
    assert aps[2].auth_mode == "Unknown" and not aps[2].supported


def test_parse_ap_list_ignores_junk_lines():
    assert wemo_setup.parse_ap_list("") == []
    assert wemo_setup.parse_ap_list("1\n\n   \ngarbage-no-pipe\n") == []


requires_openssl = pytest.mark.skipif(
    shutil.which("openssl") is None, reason="openssl binary not available"
)


@requires_openssl
def test_encrypt_wifi_password_round_trips():
    """The blob decrypts back to the passphrase with the documented parameters.

    This pins the derivation (salt/IV/key material) and the header handling:
    OpenSSL 1.x emits a "Salted__" prefix even when -S is given, OpenSSL 3.x
    does not, and slicing 16 bytes unconditionally corrupts the output on 3.x.
    """
    meta = wemo_setup.MetaInfo.parse(META_INFO)
    key_data = wemo_setup.build_key_data(meta, 1)
    password = "correct horse battery"

    encoded = wemo_setup.encrypt_wifi_password(password, key_data, add_lengths=False)

    proc = subprocess.run(
        [
            shutil.which("openssl"),
            "enc",
            "-d",
            "-aes-128-cbc",
            "-md",
            "md5",
            "-S",
            key_data[0:8].encode("utf-8").hex(),
            "-iv",
            key_data[0:16].encode("utf-8").hex(),
            "-pass",
            f"pass:{key_data}",
        ],
        input=base64.b64decode(encoded),
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr.decode("utf-8", errors="replace")
    assert proc.stdout.decode("utf-8") == password


@requires_openssl
def test_encrypt_wifi_password_length_suffix_is_zero_padded():
    """Wemo expects exactly four hex digits: xxyy, both zero-padded.

    Regression test: emitting a single digit for a length below 16 produces a
    blob the device silently rejects.
    """
    meta = wemo_setup.MetaInfo.parse(META_INFO)
    key_data = wemo_setup.build_key_data(meta, 1)
    password = "8charact"  # length 8 -> "08", not "8"

    bare = wemo_setup.encrypt_wifi_password(password, key_data, add_lengths=False)
    suffixed = wemo_setup.encrypt_wifi_password(password, key_data, add_lengths=True)

    assert suffixed == f"{bare}{len(bare):02x}08"
    assert len(suffixed) == len(bare) + 4


@requires_openssl
def test_encrypt_wifi_password_is_deterministic():
    """Same passphrase and key material must produce the same blob.

    The device derives its key from fixed metadata, so a random salt or IV
    would make the credential undecryptable on the device side.
    """
    meta = wemo_setup.MetaInfo.parse(META_INFO)
    key_data = wemo_setup.build_key_data(meta, 1)
    first = wemo_setup.encrypt_wifi_password("hunter2!", key_data, True)
    second = wemo_setup.encrypt_wifi_password("hunter2!", key_data, True)
    assert first == second


@requires_openssl
def test_encrypt_wifi_password_rejects_overlong_password():
    meta = wemo_setup.MetaInfo.parse(META_INFO)
    key_data = wemo_setup.build_key_data(meta, 1)
    with pytest.raises(wemo_setup.SetupError):
        wemo_setup.encrypt_wifi_password("x" * 256, key_data, add_lengths=True)


def test_dry_run_never_prints_the_passphrase(capsys):
    """Redacted arguments must not reach stdout, even in dry-run output."""
    client = wemo_setup.Client("10.22.22.1", execute=False)
    client.call(
        wemo_control.SERVICE_WIFI,
        "ConnectHomeNetwork",
        arguments={"ssid": "HomeNet", "password": "s3cr3t-passphrase"},
        redact={"password": wemo_setup.PASSWORD_PLACEHOLDER},
    )
    out = capsys.readouterr().out
    assert "s3cr3t-passphrase" not in out
    assert wemo_setup.PASSWORD_PLACEHOLDER in out
    assert "HomeNet" in out
    assert "DRY RUN" in out


def test_reset_codes_match_the_app_wording():
    assert wemo_setup.RESET_CODES["data"][0] == 1
    assert wemo_setup.RESET_CODES["factory"][0] == 2
    assert wemo_setup.RESET_CODES["wifi"][0] == 5
