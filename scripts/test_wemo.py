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


def test_soap_envelope_carries_action_and_arguments():
    envelope = wemo_setup.build_action(
        wemo_control.SERVICE_WIFI,
        "ConnectHomeNetwork",
        {"ssid": "HomeNet", "channel": "6"},
    )
    body = wemo_control.envelope_to_bytes(envelope).decode("utf-8")
    assert "ConnectHomeNetwork" in body
    assert ">HomeNet<" in body
    assert ">6<" in body


# ── Setup ────────────────────────────────────────────────────────────────────


def test_build_key_data_layout():
    """keydata = meta[0][0:6] + meta[1] + meta[0][6:12]."""
    key_data = wemo_setup.build_key_data("221517K0101769|94103E36AF15|Wemo Mini")
    assert key_data == "221517" + "94103E36AF15" + "K01017"
    assert len(key_data) >= 16  # enough for the 16-byte IV


def test_build_key_data_rejects_short_metainfo():
    with pytest.raises(wemo_setup.SetupError):
        wemo_setup.build_key_data("tooshort")
    with pytest.raises(wemo_setup.SetupError):
        wemo_setup.build_key_data("short|AB")


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
    key_data = wemo_setup.build_key_data("221517K0101769|94103E36AF15|Wemo Mini")
    password = "correct horse battery"

    blob = wemo_setup.encrypt_wifi_password(password, key_data)

    # Suffix is hex(len(base64)) followed by hex(len(plaintext)).
    plaintext_len_hex = f"{len(password):x}"
    assert blob.endswith(plaintext_len_hex)
    remainder = blob[: -len(plaintext_len_hex)]

    encoded = next(
        (
            remainder[:-n]
            for n in range(1, 5)
            if f"{len(remainder[:-n]):x}" == remainder[-n:]
        ),
        None,
    )
    assert encoded is not None, f"no self-consistent length suffix in {remainder!r}"

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
def test_encrypt_wifi_password_is_deterministic():
    """Same passphrase and key material must produce the same blob.

    The device derives its key from fixed metadata, so a random salt or IV
    would make the credential undecryptable on the device side.
    """
    key_data = wemo_setup.build_key_data("221517K0101769|94103E36AF15|Wemo Mini")
    first = wemo_setup.encrypt_wifi_password("hunter2", key_data)
    second = wemo_setup.encrypt_wifi_password("hunter2", key_data)
    assert first == second


def test_dry_run_never_prints_the_passphrase(capsys):
    """Redacted arguments must not reach stdout, even in dry-run output."""
    wemo_setup.call(
        device_addr="10.22.22.1:49153",
        service_type=wemo_control.SERVICE_WIFI,
        action="ConnectHomeNetwork",
        control_path="/upnp/control/WiFiSetup1",
        arguments={"ssid": "HomeNet", "password": "s3cr3t-passphrase"},
        redact={"password": wemo_setup.PASSWORD_PLACEHOLDER},
        execute=False,
    )
    out = capsys.readouterr().out
    assert "s3cr3t-passphrase" not in out
    assert wemo_setup.PASSWORD_PLACEHOLDER in out
    assert "HomeNet" in out
    assert "DRY RUN" in out
