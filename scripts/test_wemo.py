"""Tests for the Wemo discovery and control helpers.

Prerequisites: run from the repo root. Standard library plus pytest.

The provisioning protocol is tested in ``test_wemo_spec.py``, against the
spec rather than against an implementation — we deliberately do not ship a
provisioning client, since pywemo already does that job and is tested against
far more hardware than we have.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make scripts/ importable
_scripts_dir = Path(__file__).resolve().parent
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

import wemo_control  # noqa: E402
import wemo_discover  # noqa: E402

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
