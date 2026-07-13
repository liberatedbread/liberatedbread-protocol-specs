#!/usr/bin/env python3
# Copyright 2026 Pigs Can Fly Labs LLC
# SPDX-License-Identifier: Apache-2.0
"""Send SOAP 1.1 control commands to Belkin Wemo devices.

Generates valid SOAP envelopes and dispatches them over HTTP to Wemo
UPnP control URLs. Supports the basicevent and insight services.

By default runs in dry-run mode (prints the SOAP envelope without sending).
Use --execute to actually send commands to a device.

Usage:
    # Dry-run: show what would be sent
    python scripts/wemo_control.py on --device 192.168.1.42:49153
    python scripts/wemo_control.py off --device 192.168.1.42:49153
    python scripts/wemo_control.py state --device 192.168.1.42:49153
    python scripts/wemo_control.py insight --device 192.168.1.42:49153

    # Actually send the command
    python scripts/wemo_control.py on --device 192.168.1.42:49153 --execute

Environment:
    Uses only Python 3 stdlib (xml.etree, urllib, argparse, socket).
"""

from __future__ import annotations

import argparse
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Optional
from urllib.error import URLError

# ── UPnP SOAP constants ──────────────────────────────────────────────────────
SOAP_ENVELOPE_NS = "http://schemas.xmlsoap.org/soap/envelope/"
SOAP_ENCODING_NS = "http://schemas.xmlsoap.org/soap/encoding/"

# Wemo UPnP service URNs.
SERVICE_BASICEVENT = "urn:Belkin:service:basicevent:1"
SERVICE_INSIGHT = "urn:Belkin:service:insight:1"
SERVICE_METAINFO = "urn:Belkin:service:metainfo:1"
SERVICE_TIMESYNC = "urn:Belkin:service:timesync:1"
SERVICE_DEVICEINF = "urn:Belkin:service:deviceinf:1"
SERVICE_WIFI = "urn:Belkin:service:WiFiSetup:1"

# Default control URLs.
CONTROL_BASICEVENT = "/upnp/control/basicevent1"
CONTROL_INSIGHT = "/upnp/control/insight1"


def build_soap_envelope(
    service_type: str,
    action: str,
    body_elements: list[ET.Element],
) -> ET.Element:
    """Build a SOAP 1.1 envelope for a UPnP action.

    Args:
        service_type: The UPnP service URN (e.g. ``urn:Belkin:service:basicevent:1``).
        action: The SOAP action name (e.g. ``SetBinaryState``).
        body_elements: Child elements to place inside the action body element.

    Returns:
        An ``xml.etree.ElementTree.Element`` representing the full SOAP envelope.
    """
    ET.register_namespace("s", SOAP_ENVELOPE_NS)
    ET.register_namespace("u", service_type)

    envelope = ET.Element(f"{{{SOAP_ENVELOPE_NS}}}Envelope")
    envelope.set(
        f"{{{SOAP_ENVELOPE_NS}}}encodingStyle",
        SOAP_ENCODING_NS,
    )

    body = ET.SubElement(envelope, f"{{{SOAP_ENVELOPE_NS}}}Body")
    action_el = ET.SubElement(body, f"{{{service_type}}}{action}")

    for child in body_elements:
        action_el.append(child)

    return envelope


def envelope_to_bytes(envelope: ET.Element) -> bytes:
    """Serialize a SOAP envelope Element to UTF-8 bytes for the HTTP body.

    Strips the XML declaration for maximum compatibility with Wemo devices.
    """
    raw = ET.tostring(envelope, encoding="utf-8", xml_declaration=True)
    # Some Wemo devices don't like the XML declaration; strip it.
    return raw


def soapaction_header(service_type: str, action: str) -> str:
    """Build the SOAPACTION HTTP header value.

    Example: ``"urn:Belkin:service:basicevent:1#SetBinaryState"``
    """
    return f'"{service_type}#{action}"'


# ── Wemo command builders ────────────────────────────────────────────────────


def build_set_binary_state(binary_state: int) -> tuple[ET.Element, str, str]:
    """Build a SetBinaryState SOAP envelope.

    Args:
        binary_state: 1 for on, 0 for off.

    Returns:
        Tuple of (envelope Element, service_type, action_name).
    """
    binary_el = ET.Element(f"{{{SERVICE_BASICEVENT}}}BinaryState")
    binary_el.text = str(binary_state)

    envelope = build_soap_envelope(
        SERVICE_BASICEVENT,
        "SetBinaryState",
        [binary_el],
    )
    return envelope, SERVICE_BASICEVENT, "SetBinaryState"


def build_get_binary_state() -> tuple[ET.Element, str, str]:
    """Build a GetBinaryState SOAP envelope.

    Returns:
        Tuple of (envelope Element, service_type, action_name).
    """
    envelope = build_soap_envelope(
        SERVICE_BASICEVENT,
        "GetBinaryState",
        [],
    )
    return envelope, SERVICE_BASICEVENT, "GetBinaryState"


def build_get_insight_params() -> tuple[ET.Element, str, str]:
    """Build a GetInsightParams SOAP envelope.

    Returns:
        Tuple of (envelope Element, service_type, action_name).
    """
    envelope = build_soap_envelope(
        SERVICE_INSIGHT,
        "GetInsightParams",
        [],
    )
    return envelope, SERVICE_INSIGHT, "GetInsightParams"


def build_get_meta_info() -> tuple[ET.Element, str, str]:
    """Build a GetMetaInfo SOAP envelope."""
    envelope = build_soap_envelope(SERVICE_METAINFO, "GetMetaInfo", [])
    return envelope, SERVICE_METAINFO, "GetMetaInfo"


def build_time_sync() -> tuple[ET.Element, str, str]:
    """Build a TimeSync SOAP envelope with current UTC timestamp."""
    utc_el = ET.Element(f"{{{SERVICE_TIMESYNC}}}UTC")
    utc_el.text = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

    envelope = build_soap_envelope(SERVICE_TIMESYNC, "TimeSync", [utc_el])
    return envelope, SERVICE_TIMESYNC, "TimeSync"


def build_get_device_information() -> tuple[ET.Element, str, str]:
    """Build a GetDeviceInformation SOAP envelope."""
    envelope = build_soap_envelope(SERVICE_DEVICEINF, "GetDeviceInformation", [])
    return envelope, SERVICE_DEVICEINF, "GetDeviceInformation"


# ── SOAP response parsing ────────────────────────────────────────────────────


def parse_soap_response(xml_bytes: bytes) -> Optional[str]:
    """Extract the first text value from a SOAP response body.

    Handles the common Wemo response pattern where the response element
    contains a single text value (e.g. BinaryState, InsightParams).
    """
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return None

    # Navigate: Envelope → Body → <action>Response → value.
    body = root.find(f"{{{SOAP_ENVELOPE_NS}}}Body")
    if body is None:
        return None

    # The response element is the first child of Body.
    children = list(body)
    if not children:
        return None

    response_el = children[0]
    # Check for direct text, or first child's text.
    if response_el.text and response_el.text.strip():
        return response_el.text.strip()

    # Check first sub-element's text.
    sub_children = list(response_el)
    if sub_children and sub_children[0].text:
        return sub_children[0].text.strip()

    return None


def parse_insight_params(raw: str) -> dict[str, str]:
    """Parse the colon-delimited InsightParams string.

    Format (from pywemo):
        state|lastchange|onfor|ontoday|ontotal|timeperiod|...
        averagepower|instantpower(mW)|energytoday|energytotal|...

    Returns a dict with named fields.
    """
    parts = raw.replace("|", ":").split(":")
    fields = [
        "state",
        "lastchange",
        "onfor_seconds",
        "ontoday_seconds",
        "ontotal_seconds",
        "timeperiod",
        "currentmw",
        "todaymw",
        "totalmw",
        "powertreshold",
        "unknown",
    ]

    result: dict[str, str] = {}
    for i, part in enumerate(parts):
        key = fields[i] if i < len(fields) else f"field_{i}"
        result[key] = part.strip()
    return result


# ── Command dispatch ─────────────────────────────────────────────────────────


def send_soap(
    device_addr: str,
    envelope: ET.Element,
    service_type: str,
    action: str,
    control_path: str,
    dry_run: bool = True,
    timeout: int = 10,
) -> None:
    """Send a SOAP command to a Wemo device (or dry-run print it).

    Args:
        device_addr: IP:port of the device, e.g. ``192.168.1.42:49153``.
        envelope: SOAP envelope XML Element.
        service_type: UPnP service URN.
        action: SOAP action name.
        control_path: Control URL path on the device.
        dry_run: If True, print the envelope instead of sending.
        timeout: HTTP timeout in seconds.
    """
    soapaction = soapaction_header(service_type, action)
    body_bytes = envelope_to_bytes(envelope)

    url = f"http://{device_addr}{control_path}"

    print(f"── SOAP ACTION: {action} ──")
    print(f"URL:      {url}")
    print(f"SOAPACTION: {soapaction}")
    print()
    print(body_bytes.decode("utf-8"))

    if dry_run:
        print()
        print("[DRY RUN — not sent. Use --execute to send.]")
        return

    print()
    print("[SENDING...]")

    req = urllib.request.Request(
        url,
        data=body_bytes,
        headers={
            "Content-Type": 'text/xml; charset="utf-8"',
            "SOAPACTION": soapaction,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp_body = resp.read()
            print(f"HTTP {resp.status}")
            print()
            print(resp_body.decode("utf-8", errors="replace"))
            print()

            # Try to parse the result.
            result = parse_soap_response(resp_body)
            if result:
                print(f"RESULT: {result}")

                if action == "GetInsightParams":
                    insight = parse_insight_params(result)
                    print("── InsightParams parsed ──")
                    for k, v in insight.items():
                        print(f"  {k}: {v}")
    except URLError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)


# ── CLI ──────────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Send SOAP 1.1 control commands to Belkin Wemo devices.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s on --device 192.168.1.42:49153       # Dry-run: show SetBinaryState(1)
  %(prog)s off --device 192.168.1.42:49153      # Dry-run: show SetBinaryState(0)
  %(prog)s state --device 192.168.1.42:49153    # Dry-run: show GetBinaryState
  %(prog)s insight --device 192.168.1.42:49153  # Dry-run: show GetInsightParams
  %(prog)s info --device 192.168.1.42:49153     # Dry-run: show GetDeviceInformation
  %(prog)s on --device 192.168.1.42:49153 --execute  # Actually send
        """,
    )
    parser.add_argument(
        "command",
        choices=["on", "off", "state", "insight", "metainfo", "info", "timesync"],
        help="Command to send.",
    )
    parser.add_argument(
        "--device",
        required=True,
        help="Device address as IP:port (e.g. 192.168.1.42:49153).",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually send the command (default: dry-run only).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=10,
        help="HTTP timeout in seconds (default: 10).",
    )

    args = parser.parse_args()

    # Determine control path.
    if args.command == "insight":
        control_path = CONTROL_INSIGHT
    elif args.command in ("metainfo",):
        control_path = "/upnp/control/metainfo1"
    elif args.command in ("timesync",):
        control_path = "/upnp/control/timesync1"
    elif args.command in ("info",):
        control_path = "/upnp/control/deviceinf1"
    else:
        control_path = CONTROL_BASICEVENT

    # Build the SOAP envelope.
    if args.command == "on":
        envelope, svc_type, action = build_set_binary_state(1)
    elif args.command == "off":
        envelope, svc_type, action = build_set_binary_state(0)
    elif args.command == "state":
        envelope, svc_type, action = build_get_binary_state()
    elif args.command == "insight":
        envelope, svc_type, action = build_get_insight_params()
    elif args.command == "metainfo":
        envelope, svc_type, action = build_get_meta_info()
    elif args.command == "timesync":
        envelope, svc_type, action = build_time_sync()
    elif args.command == "info":
        envelope, svc_type, action = build_get_device_information()
    else:
        print(f"Unknown command: {args.command}", file=sys.stderr)
        return 1

    send_soap(
        device_addr=args.device,
        envelope=envelope,
        service_type=svc_type,
        action=action,
        control_path=control_path,
        dry_run=not args.execute,
        timeout=args.timeout,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
