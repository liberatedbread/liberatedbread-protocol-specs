#!/usr/bin/env python3
# Copyright 2026 Pigs Can Fly Labs LLC
# SPDX-License-Identifier: Apache-2.0
"""LAN recon for a June Intelligent Oven.

Unlike the other ``*_discover.py`` scripts here, this one is expected to find
nothing. The June oven has no documented mDNS service, no SSDP announcement and
no local API: it is a pure outbound cloud client. That expectation is exactly
why the script exists — "we looked, with this command, and the oven answered on
no port" is a publishable result, and nobody has published it for any
generation.

So this reports negatives as findings rather than as errors, and every field it
emits is something a device spec can carry.

Usage::

    python scripts/june_discover.py --address 192.168.1.50
    python scripts/june_discover.py --address 192.168.1.50 --full --json
    python scripts/june_discover.py --mdns-only            # passive, no target

See ``docs/devices/june-oven-lan-recon.md`` for what to do with the output, and
for the passive-capture work that matters more than this scan does.
"""

from __future__ import annotations

import argparse
import json
import socket
from dataclasses import asdict, dataclass, field

# Ports worth trying on an Android appliance that is not supposed to be
# listening on any of them. Each is here for a stated reason; do not pad this
# list, because a long scan of a device with nothing open is just slow.
DEFAULT_PORTS: dict[int, str] = {
    22: "ssh — stock AOSP does not ship one; presence would be notable",
    23: "telnet — same",
    80: "http — a local status/setup page, if one was ever left in",
    443: "https — same over TLS",
    1900: "ssdp/upnp (tcp side) — no announcement observed, probe anyway",
    5555: "adb over tcp — reported removed in the oven's locked 'user' mode; verify rather than assume",
    8080: "http-alt — common debug/servlet port",
    8156: "THE claim — one unverified community report of this being open. This scan exists mostly for this row",
    8443: "https-alt",
    9222: "chrome devtools — the UI is Android; a webview debug port would be a large finding",
}


@dataclass
class PortResult:
    port: int
    state: str  # "open" | "closed" | "filtered"
    reason: str
    banner: str = ""


@dataclass
class ReconResult:
    address: str = ""
    hostname: str = ""
    ports: list[PortResult] = field(default_factory=list)
    mdns: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def open_ports(self) -> list[int]:
        return [p.port for p in self.ports if p.state == "open"]


def probe_port(address: str, port: int, timeout: float, reason: str = "") -> PortResult:
    """TCP connect-scan one port, with a best-effort banner read.

    Distinguishes closed (RST — something is there and refusing) from filtered
    (timeout — a firewall swallowed it). That difference matters: a device that
    RSTs every port is reachable and simply not listening, which is a much
    stronger negative than a device that is silently dropping.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((address, port))
    except socket.timeout:
        sock.close()
        return PortResult(port=port, state="filtered", reason=reason)
    except ConnectionRefusedError:
        sock.close()
        return PortResult(port=port, state="closed", reason=reason)
    except OSError as exc:  # unreachable host, no route, etc.
        sock.close()
        return PortResult(port=port, state="filtered", reason=f"{reason} ({exc})")

    banner = ""
    try:
        sock.settimeout(min(timeout, 2.0))
        banner = sock.recv(128).decode("utf-8", errors="replace").strip()
    except OSError:
        # Plenty of services say nothing until spoken to. Silence is not a
        # failure, and an open port with no banner is still an open port.
        pass
    finally:
        sock.close()

    return PortResult(port=port, state="open", reason=reason, banner=banner)


def resolve_hostname(address: str) -> str:
    """Reverse-DNS the target. The name the DHCP server learned is a fingerprint."""
    try:
        return socket.gethostbyaddr(address)[0]
    except OSError:
        return ""


def scan(address: str, ports: dict[int, str], timeout: float) -> ReconResult:
    result = ReconResult(address=address, hostname=resolve_hostname(address))
    for port, reason in sorted(ports.items()):
        result.ports.append(probe_port(address, port, timeout, reason))
    return result


def interpret(result: ReconResult) -> list[str]:
    """Turn the raw scan into the sentences a spec author actually needs."""
    notes: list[str] = []

    if not result.ports:
        return notes

    open_ports = result.open_ports
    filtered = sum(1 for p in result.ports if p.state == "filtered")

    if not open_ports:
        # Strong vs weak turns on whether anything TIMED OUT. A host that RSTs
        # every port is reachable and listening on nothing; one that swallows
        # even a single probe might be firewalling the interesting one. The
        # old test was `filtered == len(ports)` for the weak case, which made
        # its complement — "one closed port among nine timeouts" — read as a
        # STRONG negative the script then told the author to write into a spec.
        if filtered:
            notes.append(
                "Every port timed out. This is a weak negative — the host may be "
                "firewalled, asleep, or not the oven. Confirm the address is right "
                "and the oven is powered and awake, then re-run."
            )
        else:
            notes.append(
                "No open ports, and the host actively refused connections. This is "
                "a STRONG negative: the oven is reachable and listening on nothing. "
                "Record it in the spec as local_access.status: none_known."
            )
    else:
        notes.append(
            f"Open: {', '.join(str(p) for p in open_ports)}. This contradicts the "
            "documented 'no local surface' position and is worth writing up in "
            "detail — service, protocol, and whether it survives a reboot."
        )

    port_8156 = next((p for p in result.ports if p.port == 8156), None)
    if port_8156 is not None:
        if port_8156.state == "open":
            notes.append(
                "TCP 8156 is OPEN — this confirms the single community report that "
                "has been the only local-path lead on record. Identify the service "
                "next (nmap -sV, then a raw connect-and-listen)."
            )
        else:
            notes.append(
                f"TCP 8156 is {port_8156.state} — the community report of an open "
                "8156 is not reproduced here. One host is not the whole fleet; note "
                "the generation and firmware version alongside this result."
            )

    adb = next((p for p in result.ports if p.port == 5555), None)
    if adb is not None and adb.state == "open":
        notes.append(
            "ADB over TCP is OPEN, contradicting the report that the oven ships "
            "with ADB removed in user mode. Verify with `adb connect` before "
            "believing it — and if it holds, this is the most significant local "
            "finding available on this device."
        )

    return notes


def browse(timeout: float) -> list[dict]:
    """Passively browse mDNS for anything that looks like an oven.

    Imported lazily so the port scan — the part that matters — still runs on a
    box without the zeroconf package installed.
    """
    try:
        from _lan_discovery import browse_mdns
    except ImportError:
        return []
    # Two phases, because "browse everything" is not one query.
    # `_services._dns-sd._udp.local.` is the DNS-SD META-query: it enumerates
    # service TYPES, and its answers are type names, not instances. Handing
    # those to browse_mdns made it call get_service_info(type, name) with a
    # type where an instance name belongs, which raises inside the zeroconf
    # browser thread — so this returned [] on every LAN, including ones with
    # plenty of services, and main() printed that as a confident negative.
    try:
        from zeroconf import ZeroconfServiceTypes

        types = sorted(ZeroconfServiceTypes.find(timeout=max(timeout, 1.0)))
    except SystemExit:
        return []
    except Exception:
        # No zeroconf, or the meta-query itself failed: fall back to the
        # types an oven could plausibly answer on rather than claiming none.
        types = ["_http._tcp.local.", "_googlecast._tcp.local."]
    if not types:
        return []
    try:
        records = browse_mdns(types, timeout)
    except SystemExit:
        # _lan_discovery exits when zeroconf is missing. Recon should degrade,
        # not abort: the caller may only care about the port scan.
        return []
    return [asdict(r) for r in records]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="LAN recon for a June oven. Expect — and record — negatives."
    )
    parser.add_argument("--address", help="Oven IP address (from your DHCP lease table).")
    parser.add_argument("--timeout", type=float, default=2.0, help="Per-port timeout, seconds.")
    parser.add_argument(
        "--full",
        action="store_true",
        help="Scan all 65535 TCP ports. Slow; prefer `nmap -p- -sV` if you have it.",
    )
    parser.add_argument("--mdns", action="store_true", help="Also browse mDNS.")
    parser.add_argument(
        "--mdns-only", action="store_true", help="Browse mDNS and skip the port scan."
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON.")
    args = parser.parse_args()

    if not args.address and not args.mdns_only:
        parser.error("--address is required unless --mdns-only is given")

    result = ReconResult()
    if not args.mdns_only:
        ports = (
            {p: "full-range sweep" for p in range(1, 65536)} if args.full else DEFAULT_PORTS
        )
        result = scan(args.address, ports, args.timeout)

    if args.mdns or args.mdns_only:
        result.mdns = browse(max(args.timeout, 5.0))
        if not result.mdns:
            result.notes.append(
                "No mDNS records at all. Expected: the oven has never been observed "
                "to announce itself. A record here would be a genuine discovery."
            )

    result.notes.extend(interpret(result))

    if args.json:
        print(json.dumps(asdict(result), indent=2, default=str))
        return

    if result.address:
        print(f"address:  {result.address}")
        print(f"hostname: {result.hostname or '(no reverse DNS)'}")
        print("ports:")
        for p in result.ports:
            marker = "OPEN  " if p.state == "open" else f"{p.state:<6}"
            line = f"  {marker} {p.port:<6}"
            if p.banner:
                line += f" banner={p.banner!r}"
            if p.state == "open" or p.port in (8156, 5555):
                line += f"  # {p.reason}"
            print(line)
    for record in result.mdns:
        print(f"mdns: {record}")
    if result.notes:
        print("\nnotes:")
        for note in result.notes:
            print(f"  - {note}")


if __name__ == "__main__":
    main()
