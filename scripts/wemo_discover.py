#!/usr/bin/env python3
# Copyright 2026 Pigs Can Fly Labs LLC
# SPDX-License-Identifier: Apache-2.0
"""Discover Belkin Wemo devices on the local LAN via SSDP (UPnP).

Sends an M-SEARCH multicast probe to 239.255.255.250:1900 and collects
responses from Wemo devices. For each discovered device, fetches and
parses the UPnP device description XML at the LOCATION URL to extract
device metadata (deviceType, friendlyName, UDN, serial, MAC, services).

Usage:
    python scripts/wemo_discover.py [--timeout SECONDS] [--json]

Environment:
    No external dependencies. Uses only Python 3 stdlib (socket, xml.etree,
    urllib, argparse, json).
"""

from __future__ import annotations

import argparse
import json
import re
import socket
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Optional
from urllib.error import URLError

# ── Constants ────────────────────────────────────────────────────────────────
SSDP_MULTICAST = "239.255.255.250"
SSDP_PORT = 1900
SSDP_MX = 2  # seconds to wait for responses

# Wemo-specific search targets for M-SEARCH ST header.
SEARCH_TARGETS = [
    "urn:Belkin:service:basicevent:1",
    "urn:Belkin:device:controllee:1",
    "urn:Belkin:device:socket:1",
    "ssdp:all",
]

# Default SOAP port for Wemo devices (probed first; then the full list).
DEFAULT_SOAP_PORT = 49153
PROBE_PORTS = [49153, 49152, 49154, 49151, 49155, 49156, 49157, 49158, 49159]

# Timeout for fetching setup.xml after discovery.
HTTP_TIMEOUT = 5  # seconds

# SSDP response patterns.
LOCATION_RE = re.compile(r"(?i)^location:\s*(.+)$", re.MULTILINE)
USN_RE = re.compile(r"(?i)^usn:\s*(.+)$", re.MULTILINE)
ST_RE = re.compile(r"(?i)^st:\s*(.+)$", re.MULTILINE)

# UPnP XML namespaces.
NS = {
    "dn": "urn:schemas-upnp-org:device-1-0",
}


@dataclass
class WemoService:
    """A UPnP service exposed by a Wemo device."""

    service_type: str
    service_id: str
    control_url: str
    event_sub_url: str
    scpd_url: str = ""


@dataclass
class WemoDevice:
    """Parsed Wemo device description from /setup.xml."""

    location_url: str
    ip: str
    port: int
    device_type: str = ""
    friendly_name: str = ""
    manufacturer: str = ""
    model_name: str = ""
    model_number: str = ""
    serial_number: str = ""
    mac_address: str = ""
    udn: str = ""
    usn: str = ""
    services: list[WemoService] = field(default_factory=list)
    raw_ssdp_response: str = ""
    fetch_error: Optional[str] = None


def build_msearch_packet(st: str, mx: int = SSDP_MX) -> bytes:
    """Build an SSDP M-SEARCH request packet for the given search target.

    Args:
        st: Search Target (ST header), e.g. ``urn:Belkin:service:basicevent:1``.
        mx: Maximum wait time in seconds for responses.

    Returns:
        Encoded M-SEARCH request as bytes.
    """
    request = (
        "M-SEARCH * HTTP/1.1\r\n"
        f"HOST: {SSDP_MULTICAST}:{SSDP_PORT}\r\n"
        'MAN: "ssdp:discover"\r\n'
        f"MX: {mx}\r\n"
        f"ST: {st}\r\n"
        "\r\n"
    )
    return request.encode("utf-8")


def send_msearch(st: str, timeout: float = 3.0) -> list[str]:
    """Send one M-SEARCH and collect all unicast responses.

    Args:
        st: Search Target to probe for.
        timeout: How long to wait for responses (in seconds).

    Returns:
        List of raw SSDP response strings (headers only, no body).
    """
    responses: list[str] = []

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
    sock.settimeout(timeout)

    try:
        packet = build_msearch_packet(st)
        sock.sendto(packet, (SSDP_MULTICAST, SSDP_PORT))

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                sock.settimeout(remaining)
                data, addr = sock.recvfrom(4096)
                responses.append(data.decode("utf-8", errors="replace"))
            except socket.timeout:
                break
    finally:
        sock.close()

    return responses


def parse_ssdp_response(raw: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Extract LOCATION, USN, and ST headers from an SSDP response.

    Returns:
        Tuple of (location_url, usn, st) — any may be None if missing.
    """
    location = None
    usn = None
    st = None

    m = LOCATION_RE.search(raw)
    if m:
        location = m.group(1).strip()

    m = USN_RE.search(raw)
    if m:
        usn = m.group(1).strip()

    m = ST_RE.search(raw)
    if m:
        st = m.group(1).strip()

    return location, usn, st


def parse_ip_port(url: str) -> tuple[str, int]:
    """Extract IP and port from a URL like http://192.168.1.42:49153/setup.xml."""
    # Strip scheme
    host_port = url
    for prefix in ("http://", "https://"):
        if host_port.startswith(prefix):
            host_port = host_port[len(prefix) :]
            break

    host, _, path = host_port.partition("/")
    if ":" in host:
        ip, port_str = host.rsplit(":", 1)
        return ip, int(port_str)
    return host, 80


def fetch_setup_xml(url: str, timeout: int = HTTP_TIMEOUT) -> Optional[bytes]:
    """Fetch the UPnP device description XML from a LOCATION URL.

    Returns:
        Raw XML bytes, or None on failure.
    """
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except (URLError, OSError) as exc:
        return None


def parse_setup_xml(xml_bytes: bytes) -> Optional[WemoDevice]:
    """Parse a UPnP device description XML document.

    Returns:
        Parsed WemoDevice, or None if parsing fails.
    """
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return None

    device_el = root.find(".//dn:device", NS)
    if device_el is None:
        device_el = root.find(".//{urn:schemas-upnp-org:device-1-0}device")

    if device_el is None:
        return None

    def _text(tag: str, default: str = "") -> str:
        el = device_el.find(f"dn:{tag}", NS)
        if el is None:
            el = device_el.find(f"{{{NS['dn']}}}{tag}")
        if el is not None and el.text:
            return el.text.strip()
        return default

    device = WemoDevice(
        location_url="",
        ip="",
        port=0,
        device_type=_text("deviceType"),
        friendly_name=_text("friendlyName"),
        manufacturer=_text("manufacturer"),
        model_name=_text("modelName"),
        model_number=_text("modelNumber"),
        serial_number=_text("serialNumber"),
        mac_address=_text("macAddress"),
        udn=_text("UDN"),
    )

    # Parse service list.
    service_list_el = device_el.find("dn:serviceList", NS)
    if service_list_el is None:
        service_list_el = device_el.find(f"{{{NS['dn']}}}serviceList")

    if service_list_el is not None:
        for svc_el in service_list_el.findall("dn:service", NS):
            if svc_el is None:
                svc_el_tag = f"{{{NS['dn']}}}service"
                svc_el_list = service_list_el.findall(svc_el_tag)
            else:
                svc_el_list = service_list_el.findall("dn:service", NS)

            # Redo this cleanly
            pass

    # Re-parse services cleanly.
    device.services = []
    if service_list_el is not None:
        for svc_el in list(service_list_el):
            tag = svc_el.tag.split("}")[-1] if "}" in svc_el.tag else svc_el.tag
            if tag != "service":
                continue

            def _svc_text(t: str) -> str:
                el2 = svc_el.find(f"dn:{t}", NS)
                if el2 is None:
                    el2 = svc_el.find(f"{{{NS['dn']}}}{t}")
                return el2.text.strip() if el2 is not None and el2.text else ""

            device.services.append(
                WemoService(
                    service_type=_svc_text("serviceType"),
                    service_id=_svc_text("serviceId"),
                    control_url=_svc_text("controlURL"),
                    event_sub_url=_svc_text("eventSubURL"),
                    scpd_url=_svc_text("SCPDURL"),
                )
            )

    return device


def discover(
    timeout: float = 3.0,
    fetch_details: bool = True,
) -> list[WemoDevice]:
    """Discover Wemo devices on the local LAN.

    Args:
        timeout: Seconds to wait for M-SEARCH responses.
        fetch_details: If True, fetch and parse /setup.xml for each device.

    Returns:
        List of discovered WemoDevice objects.
    """
    # Collect all SSDP responses (deduplicate by LOCATION).
    seen_locations: dict[str, tuple[str, str, str]] = {}

    for st in SEARCH_TARGETS:
        responses = send_msearch(st, timeout=timeout)
        for resp in responses:
            loc, usn, search_st = parse_ssdp_response(resp)
            if loc:
                # Deduplicate by location URL.
                if loc not in seen_locations:
                    seen_locations[loc] = (resp, usn or "", search_st or "")

    devices: list[WemoDevice] = []
    for loc, (raw_resp, usn, st_val) in seen_locations.items():
        ip, port = parse_ip_port(loc)
        device = WemoDevice(
            location_url=loc,
            ip=ip,
            port=port,
            usn=usn,
            raw_ssdp_response=raw_resp,
        )

        if fetch_details and loc.endswith("/setup.xml"):
            xml_data = fetch_setup_xml(loc)
            if xml_data is not None:
                parsed = parse_setup_xml(xml_data)
                if parsed is not None:
                    # Merge parsed data into discovery device.
                    device.device_type = parsed.device_type
                    device.friendly_name = parsed.friendly_name
                    device.manufacturer = parsed.manufacturer
                    device.model_name = parsed.model_name
                    device.model_number = parsed.model_number
                    device.serial_number = parsed.serial_number
                    device.mac_address = parsed.mac_address
                    device.udn = parsed.udn
                    device.services = parsed.services
                else:
                    device.fetch_error = "Failed to parse setup.xml"
            else:
                device.fetch_error = f"Failed to fetch {loc}"
        elif not fetch_details and not loc.endswith("/setup.xml"):
            # Probe known port list to find the actual setup.xml.
            device.fetch_error = "setup.xml not probed (different port may apply)"

        devices.append(device)

    return devices


def format_table(devices: list[WemoDevice]) -> str:
    """Format discovered devices as a human-readable table."""
    if not devices:
        return "No Wemo devices discovered."

    lines = []
    header = f"{'IP':<16} {'Port':<6} {'Name':<24} {'Device Type':<38} {'Serial':<18}"
    lines.append(header)
    lines.append("-" * len(header))

    for d in devices:
        # Shorten deviceType for display.
        dt = d.device_type
        if dt.startswith("urn:Belkin:device:"):
            dt = dt[len("urn:Belkin:device:") :]
        if dt.endswith(":1"):
            dt = dt[:-2]

        lines.append(
            f"{d.ip:<16} {d.port:<6} {d.friendly_name[:23]:<24} "
            f"{dt[:37]:<38} {d.serial_number[:17]:<18}"
        )

        if d.services:
            for svc in d.services:
                st_short = svc.service_type
                if st_short.startswith("urn:Belkin:service:"):
                    st_short = st_short[len("urn:Belkin:service:") :]
                if st_short.endswith(":1"):
                    st_short = st_short[:-2]
                lines.append(
                    f"        Service: {st_short:<20} CTRL={svc.control_url:<30} EVENT={svc.event_sub_url}"
                )

        if d.fetch_error:
            lines.append(f"        ⚠ {d.fetch_error}")

    return "\n".join(lines)


def format_json(devices: list[WemoDevice]) -> str:
    """Format discovered devices as JSON."""
    result = []
    for d in devices:
        entry = {
            "ip": d.ip,
            "port": d.port,
            "location_url": d.location_url,
            "device_type": d.device_type,
            "friendly_name": d.friendly_name,
            "manufacturer": d.manufacturer,
            "model_name": d.model_name,
            "model_number": d.model_number,
            "serial_number": d.serial_number,
            "mac_address": d.mac_address,
            "udn": d.udn,
            "usn": d.usn,
            "services": [
                {
                    "service_type": svc.service_type,
                    "service_id": svc.service_id,
                    "control_url": svc.control_url,
                    "event_sub_url": svc.event_sub_url,
                }
                for svc in d.services
            ],
        }
        if d.fetch_error:
            entry["fetch_error"] = d.fetch_error
        result.append(entry)
    return json.dumps(result, indent=2, ensure_ascii=False)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Discover Belkin Wemo devices via SSDP (UPnP).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                    # Discover Wemo devices, print table
  %(prog)s --timeout 5        # Wait 5s for responses
  %(prog)s --json             # Output as JSON
  %(prog)s --no-fetch         # Discover only (skip setup.xml fetch)
        """,
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=3.0,
        help="Seconds to wait for M-SEARCH responses (default: 3.0).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON instead of a table.",
    )
    parser.add_argument(
        "--no-fetch",
        action="store_true",
        help="Skip fetching /setup.xml; report SSDP responses only.",
    )

    args = parser.parse_args()

    print(f"Probing SSDP multicast on {SSDP_MULTICAST}:{SSDP_PORT}...", file=sys.stderr)
    print(
        f"Search targets: {', '.join(SEARCH_TARGETS)}", file=sys.stderr
    )
    print(f"Waiting up to {args.timeout}s per target...", file=sys.stderr)

    devices = discover(timeout=args.timeout, fetch_details=not args.no_fetch)

    print(f"Found {len(devices)} device(s).\n", file=sys.stderr)

    if args.json:
        print(format_json(devices))
    else:
        print(format_table(devices))

    return 0 if devices else 1


if __name__ == "__main__":
    raise SystemExit(main())
