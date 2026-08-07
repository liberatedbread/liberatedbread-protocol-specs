#!/usr/bin/env python3
# Copyright 2026 Pigs Can Fly Labs LLC
# SPDX-License-Identifier: Apache-2.0
"""Tests for scripts/june_discover.py.

The interesting logic here is interpretation, not I/O: this script's job is to
turn a scan of a device that listens on nothing into sentences a spec author can
use, and to tell a strong negative (refused) apart from a weak one (timed out).
"""

import socket
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import june_discover  # noqa: E402


def _result(*ports: tuple[int, str]) -> june_discover.ReconResult:
    return june_discover.ReconResult(
        address="192.0.2.10",
        ports=[june_discover.PortResult(port=p, state=s, reason="") for p, s in ports],
    )


def test_all_refused_is_a_strong_negative():
    notes = june_discover.interpret(_result((80, "closed"), (443, "closed")))
    joined = " ".join(notes)
    assert "STRONG negative" in joined
    assert "none_known" in joined


def test_all_timed_out_is_only_a_weak_negative():
    notes = june_discover.interpret(_result((80, "filtered"), (443, "filtered")))
    joined = " ".join(notes)
    assert "weak negative" in joined
    assert "STRONG negative" not in joined


def test_port_8156_open_is_called_out():
    notes = june_discover.interpret(_result((8156, "open")))
    joined = " ".join(notes)
    assert "8156 is OPEN" in joined


def test_port_8156_closed_is_reported_without_overclaiming():
    notes = june_discover.interpret(_result((8156, "closed"), (80, "closed")))
    joined = " ".join(notes)
    # A single unit not answering does not disprove the community report.
    assert "not reproduced" in joined
    assert "One host is not the whole fleet" in joined


def test_open_adb_is_flagged_against_the_documented_claim():
    notes = june_discover.interpret(_result((5555, "open")))
    joined = " ".join(notes)
    assert "ADB over TCP is OPEN" in joined
    assert "contradicting" in joined


def test_open_ports_property():
    result = _result((80, "closed"), (8156, "open"), (443, "filtered"))
    assert result.open_ports == [8156]


def test_empty_scan_produces_no_notes():
    assert june_discover.interpret(june_discover.ReconResult()) == []


def test_probe_port_detects_an_open_port_and_reads_a_banner():
    """A real loopback listener, so the socket path itself is covered."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]

    def serve() -> None:
        conn, _ = server.accept()
        conn.sendall(b"JUNE-TEST\r\n")
        conn.close()

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()

    result = june_discover.probe_port("127.0.0.1", port, timeout=3.0)
    thread.join(timeout=5)
    server.close()

    assert result.state == "open"
    assert result.banner == "JUNE-TEST"


def test_probe_port_reports_a_refused_port_as_closed():
    """Bind and immediately close, so the port is reachable but unserved."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()

    result = june_discover.probe_port("127.0.0.1", port, timeout=3.0)
    assert result.state == "closed"


def test_default_ports_cover_the_leads_that_motivated_the_script():
    assert 8156 in june_discover.DEFAULT_PORTS
    assert 5555 in june_discover.DEFAULT_PORTS
