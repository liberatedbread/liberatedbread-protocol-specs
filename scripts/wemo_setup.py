#!/usr/bin/env python3
# Copyright 2026 Pigs Can Fly Labs LLC
# SPDX-License-Identifier: Apache-2.0
"""Provision a Belkin Wemo device onto a WiFi network without the vendor app.

Drives the WiFiSetup SOAP service a Wemo device exposes while it is in setup
mode, so a factory-reset device can be joined to a network — and an already
provisioned one can be moved to a different network — entirely locally. The
Belkin cloud is not involved at any point.

Run this while joined to the device's own setup access point (an open network
named ``Wemo.*``); the device answers on 10.22.22.1. The exception is
``resetup``, which is sent to a device still on your LAN to push it back into
setup mode.

Every subcommand is a DRY RUN by default and prints the SOAP it would send.
Pass --execute to actually talk to the device.

Usage:
    python scripts/wemo_setup.py info --execute
    python scripts/wemo_setup.py list-aps --execute
    python scripts/wemo_setup.py connect --ssid HomeNet --auth WPA2PSK \\
        --encrypt AES --channel 6 --execute
    python scripts/wemo_setup.py status --execute
    python scripts/wemo_setup.py close --execute
    python scripts/wemo_setup.py resetup --device 192.168.1.42:49153 --execute

The WiFi passphrase is read from the WEMO_WIFI_PASSWORD environment variable
or prompted for without echo. It is never printed and never logged.

Environment:
    Python 3 stdlib only, plus the `openssl` command-line tool for the
    AES-128-CBC passphrase encryption the device requires (Python's stdlib has
    no AES implementation).

Confidence: the service and action names are taken from the device's own
setup.xml service list and from pywemo. The passphrase encryption derivation
and the ApList field order follow the public wemosetup implementation and have
not been replayed against hardware in this project — raw device responses are
printed so they can be checked against docs/devices/wemo-setup.md.
"""

from __future__ import annotations

import argparse
import base64
import getpass
import os
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from typing import Optional
from urllib.error import URLError

# Sibling module: sys.path[0] is scripts/ when run as `python scripts/...`.
from wemo_control import (  # noqa: E402
    SERVICE_BASICEVENT,
    SERVICE_METAINFO,
    SERVICE_WIFI,
    build_soap_envelope,
    envelope_to_bytes,
    parse_soap_values,
    post_soap,
    soapaction_header,
)
from wemo_discover import fetch_setup_xml, parse_setup_xml  # noqa: E402

# ── Constants ────────────────────────────────────────────────────────────────

#: Address a Wemo device answers on while hosting its own setup AP.
SETUP_AP_ADDRESS = "10.22.22.1:49153"

#: Control paths for the WiFiSetup service. The spelling varies across firmware
#: generations, so setup.xml is authoritative; these are the fallbacks.
WIFI_CONTROL_PATHS = ["/upnp/control/WiFiSetup1", "/upnp/control/wifi1"]
METAINFO_CONTROL_PATH = "/upnp/control/metainfo1"
BASICEVENT_CONTROL_PATH = "/upnp/control/basicevent1"

#: NetworkStatus value reported by a device that joined successfully.
NETWORK_STATUS_CONNECTED = "1"

#: Placeholder shown instead of the encrypted passphrase in dry-run output.
PASSWORD_PLACEHOLDER = "[encrypted-passphrase-not-shown]"


class SetupError(RuntimeError):
    """A provisioning step failed in a way the user needs to act on."""


# ── Passphrase encryption ────────────────────────────────────────────────────


def build_key_data(meta_info: str) -> str:
    """Derive the OpenSSL key material from a device's MetaInfo string.

    ``MetaInfo`` is pipe-delimited; fields 0 and 1 are recombined into the
    passphrase OpenSSL derives the AES key from. Documented in
    docs/devices/wemo-setup.md; taken from the public wemosetup implementation.
    """
    fields = meta_info.split("|")
    if len(fields) < 2 or len(fields[0]) < 12:
        raise SetupError(
            "MetaInfo is not in the expected form (need at least two "
            f"pipe-delimited fields, the first at least 12 characters): got "
            f"{len(fields)} field(s)"
        )

    key_data = fields[0][0:6] + fields[1] + fields[0][6:12]
    if len(key_data) < 16:
        raise SetupError(
            f"Derived key material is {len(key_data)} characters; 16 are "
            "needed for the initialization vector"
        )
    return key_data


def encrypt_wifi_password(password: str, key_data: str) -> str:
    """Encrypt a WiFi passphrase the way a Wemo device expects it.

    AES-128-CBC with OpenSSL's legacy MD5 ``EVP_BytesToKey`` derivation, salt
    and IV taken from *key_data*, then base64 with the length suffix Wemo adds.

    This is obfuscation, not a security boundary: every input is derived from
    metadata the device serves unauthenticated. See docs/devices/wemo-setup.md.
    """
    openssl = shutil.which("openssl")
    if openssl is None:
        raise SetupError(
            "the `openssl` command-line tool is required for passphrase "
            "encryption but was not found on PATH"
        )

    salt = key_data[0:8].encode("utf-8")
    iv = key_data[0:16].encode("utf-8")

    proc = subprocess.run(
        [
            openssl,
            "enc",
            "-aes-128-cbc",
            "-md",
            "md5",
            "-S",
            salt.hex(),
            "-iv",
            iv.hex(),
            "-pass",
            f"pass:{key_data}",
        ],
        input=password.encode("utf-8"),
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        # stderr may echo the passphrase-derived key material; do not print it.
        raise SetupError(f"openssl exited {proc.returncode} during encryption")

    # OpenSSL 1.x writes a "Salted__" + 8-byte-salt header even when the salt
    # was supplied with -S; OpenSSL 3.x omits it. The device wants only the
    # ciphertext, so strip the header when it is actually there rather than
    # slicing 16 bytes unconditionally (which silently truncates on 3.x).
    ciphertext = proc.stdout
    if ciphertext.startswith(b"Salted__"):
        ciphertext = ciphertext[16:]
    if not ciphertext:
        raise SetupError("openssl produced no ciphertext")

    encoded = base64.b64encode(ciphertext).decode("ascii")
    return f"{encoded}{len(encoded):x}{len(password):x}"


def read_password(prompt: str = "Home network passphrase: ") -> str:
    """Read the WiFi passphrase from the environment or an unechoed prompt."""
    password = os.environ.get("WEMO_WIFI_PASSWORD")
    if password:
        return password
    return getpass.getpass(prompt)


# ── SOAP plumbing ────────────────────────────────────────────────────────────


def build_action(
    service_type: str,
    action: str,
    arguments: Optional[dict[str, str]] = None,
) -> ET.Element:
    """Build a SOAP envelope for *action* with simple string arguments."""
    elements = []
    for name, value in (arguments or {}).items():
        el = ET.Element(f"{{{service_type}}}{name}")
        el.text = value
        elements.append(el)
    return build_soap_envelope(service_type, action, elements)


def call(
    device_addr: str,
    service_type: str,
    action: str,
    control_path: str,
    arguments: Optional[dict[str, str]] = None,
    redact: Optional[dict[str, str]] = None,
    execute: bool = False,
    timeout: int = 20,
) -> dict[str, str]:
    """Print, and optionally send, one SOAP action. Returns response values.

    *redact* maps argument names to the placeholder printed in their place, so
    a passphrase blob is never written to the terminal or a log.
    """
    envelope = build_action(service_type, action, arguments)

    printable = dict(arguments or {})
    for name, placeholder in (redact or {}).items():
        if name in printable:
            printable[name] = placeholder
    display_envelope = build_action(service_type, action, printable)

    print(f"── SOAP ACTION: {action} ──")
    print(f"URL:        http://{device_addr}{control_path}")
    print(f"SOAPACTION: {soapaction_header(service_type, action)}")
    print()
    print(envelope_to_bytes(display_envelope).decode("utf-8"))
    print()

    if not execute:
        print("[DRY RUN — not sent. Use --execute to send.]")
        return {}

    try:
        body = post_soap(
            device_addr=device_addr,
            envelope=envelope,
            service_type=service_type,
            action=action,
            control_path=control_path,
            timeout=timeout,
        )
    except URLError as exc:
        raise SetupError(f"{action} failed: {exc}") from exc

    values = parse_soap_values(body)
    if not values:
        raise SetupError(
            f"{action} returned no values; raw response:\n"
            f"{body.decode('utf-8', errors='replace')}"
        )
    return values


def resolve_control_paths(device_addr: str, execute: bool) -> dict[str, str]:
    """Read setup.xml and map service types to their advertised control URLs.

    Falls back to the documented defaults when the description cannot be
    fetched (including in dry-run mode, where nothing is contacted).
    """
    defaults = {
        SERVICE_WIFI: WIFI_CONTROL_PATHS[0],
        SERVICE_METAINFO: METAINFO_CONTROL_PATH,
        SERVICE_BASICEVENT: BASICEVENT_CONTROL_PATH,
    }
    if not execute:
        return defaults

    xml_data = fetch_setup_xml(f"http://{device_addr}/setup.xml")
    if xml_data is None:
        print(
            f"warning: could not fetch http://{device_addr}/setup.xml; "
            "using default control paths",
            file=sys.stderr,
        )
        return defaults

    device = parse_setup_xml(xml_data)
    if device is None:
        print(
            "warning: could not parse setup.xml; using default control paths",
            file=sys.stderr,
        )
        return defaults

    paths = dict(defaults)
    for service in device.services:
        if service.service_type and service.control_url:
            paths[service.service_type] = service.control_url
    return paths


# ── Commands ─────────────────────────────────────────────────────────────────


def cmd_info(args: argparse.Namespace) -> int:
    """Show the device description and confirm the setup services are present."""
    if not args.execute:
        print(f"Would fetch http://{args.device}/setup.xml")
        print("[DRY RUN — not sent. Use --execute to send.]")
        return 0

    xml_data = fetch_setup_xml(f"http://{args.device}/setup.xml")
    if xml_data is None:
        raise SetupError(
            f"could not reach http://{args.device}/setup.xml — are you joined "
            "to the device's setup AP?"
        )

    device = parse_setup_xml(xml_data)
    if device is None:
        raise SetupError("setup.xml could not be parsed")

    print(f"Name:         {device.friendly_name}")
    print(f"Device type:  {device.device_type}")
    print(f"Model:        {device.model_name} {device.model_number}".rstrip())
    print(f"Serial:       {device.serial_number}")
    print(f"MAC:          {device.mac_address}")
    print(f"UDN:          {device.udn}")
    print()
    print("Services:")
    for service in device.services:
        print(f"  {service.service_type:<45} {service.control_url}")

    if not any(s.service_type == SERVICE_WIFI for s in device.services):
        print()
        print(
            "warning: this device is not advertising the WiFiSetup service. It "
            "is probably already provisioned — run `resetup` against it on the "
            "LAN, or factory reset it.",
            file=sys.stderr,
        )
    return 0


def cmd_list_aps(args: argparse.Namespace) -> int:
    """Ask the device to scan and print the networks it can see."""
    paths = resolve_control_paths(args.device, args.execute)
    values = call(
        device_addr=args.device,
        service_type=SERVICE_WIFI,
        action="GetApList",
        control_path=paths[SERVICE_WIFI],
        execute=args.execute,
        timeout=args.timeout,
    )
    if not args.execute:
        return 0

    ap_list = values.get("ApList", "")
    print("── Raw ApList ──")
    print(ap_list)
    print()
    print("── Best-effort parse ──")
    print(
        "Field order follows the public wemosetup implementation and is not "
        "verified here — check it against the raw output above before relying "
        "on the parsed columns."
    )
    print()
    print(f"{'SSID':<32} {'Channel':<8} {'Auth/Cipher':<20} Signal")
    for line in ap_list.splitlines():
        fields = [f.strip() for f in line.strip().split("|")]
        if len(fields) < 4:
            continue
        ssid = fields[0].lstrip("#")
        print(f"{ssid:<32} {fields[1]:<8} {fields[2]:<20} {fields[3]}")
    print()
    print(
        "Pass the auth mode, cipher and channel back verbatim: a device will "
        "reject a network it can see if the strings do not match its own."
    )
    return 0


def cmd_connect(args: argparse.Namespace) -> int:
    """Hand the device the home network credentials."""
    paths = resolve_control_paths(args.device, args.execute)

    if args.execute:
        meta = call(
            device_addr=args.device,
            service_type=SERVICE_METAINFO,
            action="GetMetaInfo",
            control_path=paths[SERVICE_METAINFO],
            execute=True,
            timeout=args.timeout,
        )
        meta_info = meta.get("MetaInfo", "")
        if not meta_info:
            raise SetupError("GetMetaInfo returned no MetaInfo value")
        encrypted = encrypt_wifi_password(read_password(), build_key_data(meta_info))
    else:
        print(
            "Would call GetMetaInfo, then encrypt the passphrase with the "
            "returned key material.\n"
        )
        encrypted = PASSWORD_PLACEHOLDER

    call(
        device_addr=args.device,
        service_type=SERVICE_WIFI,
        action="ConnectHomeNetwork",
        control_path=paths[SERVICE_WIFI],
        arguments={
            "ssid": args.ssid,
            "auth": args.auth,
            "password": encrypted,
            "encrypt": args.encrypt,
            "channel": str(args.channel),
        },
        redact={"password": PASSWORD_PLACEHOLDER},
        execute=args.execute,
        timeout=args.timeout,
    )

    if not args.execute:
        return 0

    print()
    print("Polling GetNetworkStatus...")
    deadline = time.monotonic() + args.wait
    status = ""
    while time.monotonic() < deadline:
        values = call(
            device_addr=args.device,
            service_type=SERVICE_WIFI,
            action="GetNetworkStatus",
            control_path=paths[SERVICE_WIFI],
            execute=True,
            timeout=args.timeout,
        )
        status = values.get("NetworkStatus", "")
        print(f"NetworkStatus: {status}")
        if status == NETWORK_STATUS_CONNECTED:
            print()
            print("Connected. Run `close` to release the device onto the network.")
            return 0
        time.sleep(2)

    raise SetupError(
        f"device did not report a connected state within {args.wait}s "
        f"(last NetworkStatus: {status or 'none'}). Common causes: wrong "
        "passphrase, a 5 GHz-only SSID, or auth/cipher values that do not "
        "match the ApList entry."
    )


def cmd_status(args: argparse.Namespace) -> int:
    """Report the device's current join status."""
    paths = resolve_control_paths(args.device, args.execute)
    values = call(
        device_addr=args.device,
        service_type=SERVICE_WIFI,
        action="GetNetworkStatus",
        control_path=paths[SERVICE_WIFI],
        execute=args.execute,
        timeout=args.timeout,
    )
    if not args.execute:
        return 0

    status = values.get("NetworkStatus", "")
    connected = status == NETWORK_STATUS_CONNECTED
    print(f"NetworkStatus: {status} ({'connected' if connected else 'not connected'})")
    return 0 if connected else 1


def cmd_close(args: argparse.Namespace) -> int:
    """Close setup mode so the device joins the configured network."""
    paths = resolve_control_paths(args.device, args.execute)
    call(
        device_addr=args.device,
        service_type=SERVICE_WIFI,
        action="CloseSetup",
        control_path=paths[SERVICE_WIFI],
        execute=args.execute,
        timeout=args.timeout,
    )
    if args.execute:
        print()
        print(
            "Setup closed. Rejoin your own network and rediscover the device:\n"
            "  python scripts/wemo_discover.py --timeout 5"
        )
    return 0


def cmd_resetup(args: argparse.Namespace) -> int:
    """Push a provisioned device back into setup mode over the LAN."""
    if args.device == SETUP_AP_ADDRESS:
        raise SetupError(
            "resetup targets a device on your LAN, not the setup AP — pass "
            "--device <ip>:<port> (find it with wemo_discover.py)"
        )

    print(
        "This clears the device's stored WiFi credentials immediately. If the\n"
        "reprovisioning that follows fails, the device will be sitting in setup\n"
        "mode, not back on the current network. Have the new SSID and\n"
        "passphrase to hand before running this with --execute.\n"
    )

    paths = resolve_control_paths(args.device, args.execute)
    call(
        device_addr=args.device,
        service_type=SERVICE_BASICEVENT,
        action="ReSetup",
        control_path=paths[SERVICE_BASICEVENT],
        execute=args.execute,
        timeout=args.timeout,
    )
    if args.execute:
        print()
        print(
            "Device should drop off the LAN and start advertising its Wemo.* "
            "setup AP within about 90 seconds."
        )
    return 0


# ── CLI ──────────────────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Provision a Belkin Wemo device onto WiFi via its local WiFiSetup "
            "SOAP service. Dry-run by default."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Typical session, joined to the device's open Wemo.* setup AP:

  %(prog)s info --execute
  %(prog)s list-aps --execute
  %(prog)s connect --ssid HomeNet --auth WPA2PSK --encrypt AES --channel 6 --execute
  %(prog)s close --execute

Moving a device that is still on your LAN to a different network:

  %(prog)s resetup --device 192.168.1.42:49153 --execute
        """,
    )
    parser.add_argument(
        "--device",
        default=SETUP_AP_ADDRESS,
        help=(
            "Device address as IP:port "
            f"(default: {SETUP_AP_ADDRESS}, the setup AP address)."
        ),
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually contact the device (default: dry-run only).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=20,
        help="Per-request HTTP timeout in seconds (default: 20).",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("info", help="Show the device description and setup services.")
    sub.add_parser("list-aps", help="Ask the device which networks it can see.")

    connect = sub.add_parser("connect", help="Send the home network credentials.")
    connect.add_argument("--ssid", required=True, help="Target network SSID.")
    connect.add_argument(
        "--auth",
        required=True,
        help="Auth mode exactly as reported by list-aps, e.g. WPA2PSK.",
    )
    connect.add_argument(
        "--encrypt",
        required=True,
        help="Cipher exactly as reported by list-aps, e.g. AES.",
    )
    connect.add_argument(
        "--channel", required=True, type=int, help="Channel from the ApList entry."
    )
    connect.add_argument(
        "--wait",
        type=int,
        default=60,
        help="Seconds to poll for a connected state (default: 60).",
    )

    sub.add_parser("status", help="Report the current NetworkStatus.")
    sub.add_parser("close", help="Close setup mode and release the device.")
    sub.add_parser(
        "resetup", help="Push a provisioned device on your LAN back into setup mode."
    )

    return parser


COMMANDS = {
    "info": cmd_info,
    "list-aps": cmd_list_aps,
    "connect": cmd_connect,
    "status": cmd_status,
    "close": cmd_close,
    "resetup": cmd_resetup,
}


def main() -> int:
    args = build_parser().parse_args()
    try:
        return COMMANDS[args.command](args)
    except SetupError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
