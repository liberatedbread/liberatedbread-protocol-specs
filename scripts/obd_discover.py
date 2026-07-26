#!/usr/bin/env python3
# Copyright 2026 Pigs Can Fly Labs LLC
# SPDX-License-Identifier: Apache-2.0
"""Read-only OBD-II / UDS reconnaissance over an ELM327-class serial adapter.

Maps what a vehicle's diagnostic bus will answer *without writing anything*: which
transport it speaks, which ECU addresses respond, and which ReadDataByIdentifier (0x22)
DIDs return data. That last sweep is how you locate values such as an odometer or a
service-due distance before anyone works out how to change them.

Only services that read are ever sent: 0x22 (ReadDataByIdentifier), 0x09 (vehicle info)
and 0x10 0x03 (enter extended session, when --extended is given). Nothing in here writes
a value, starts a routine or resets an ECU, and the sweep deliberately refuses to touch
RoutineControl (0x31) — "start routine" identifiers execute whatever they name, so they
are only ever invoked from a captured, understood trace.

SAFETY: vehicles are safety-critical. Run this on a vehicle you own, stationary, on a
stand or with the parking brake set, engine off and ignition on. Never while anyone is
riding or driving it.

Usage::

    python scripts/obd_discover.py --port /dev/rfcomm0
    python scripts/obd_discover.py --port /dev/ttyUSB0 --scan-dids 0xF180-0xF1FF
    python scripts/obd_discover.py --port /dev/rfcomm0 --ecu 0x7E0 --extended --json

Requires ``pyserial``. Pair a Bluetooth adapter first, e.g.::

    sudo rfcomm bind 0 <adapter-mac> 1
"""

from __future__ import annotations

import argparse
import json
import sys
import time

try:
    import serial  # type: ignore
except ImportError:  # pragma: no cover - dependency is optional for docs builds
    serial = None

# ELM327 protocol 6 = ISO 15765-4 CAN, 11-bit ID, 500 kbit/s: the usual OBD-II variant
# and the one Triumph's later ECUs use.
DEFAULT_PROTOCOL = "6"
DEFAULT_ECUS = ["0x7E0", "0x7E8"]

# UDS negative response codes worth naming; the first three are what a DID sweep sees.
NRC = {
    0x11: "serviceNotSupported",
    0x12: "subFunctionNotSupported",
    0x13: "incorrectMessageLengthOrInvalidFormat",
    0x22: "conditionsNotCorrect",
    0x31: "requestOutOfRange",
    0x33: "securityAccessDenied",
    0x35: "invalidKey",
    0x78: "responsePending",
    0x7E: "subFunctionNotSupportedInActiveSession",
    0x7F: "serviceNotSupportedInActiveSession",
}


class Elm327:
    """Minimal ELM327/STN command wrapper.

    Deliberately thin: this is a reconnaissance tool, so the raw adapter dialogue stays
    visible (``--verbose``) rather than being hidden behind an abstraction.
    """

    def __init__(self, port: str, baudrate: int, timeout: float, verbose: bool = False):
        if serial is None:
            raise SystemExit("pyserial is required: pip install pyserial")
        self.ser = serial.Serial(port, baudrate=baudrate, timeout=timeout)
        self.verbose = verbose

    def close(self) -> None:
        self.ser.close()

    def command(self, cmd: str, delay: float = 0.1) -> str:
        """Send one command, return the adapter's reply with the '>' prompt stripped."""
        self.ser.reset_input_buffer()
        self.ser.write((cmd + "\r").encode("ascii"))
        time.sleep(delay)
        raw = b""
        deadline = time.time() + self.ser.timeout
        while time.time() < deadline:
            chunk = self.ser.read(self.ser.in_waiting or 1)
            if not chunk:
                break
            raw += chunk
            if b">" in raw:
                break
        reply = raw.decode("ascii", errors="replace").replace(">", "").strip()
        if self.verbose:
            print(f"  >> {cmd}\n  << {reply!r}", file=sys.stderr)
        return reply

    def init(self, protocol: str) -> dict[str, str]:
        """Reset the adapter and select a protocol. Returns adapter identity info."""
        info = {}
        info["adapter"] = self.command("ATZ", delay=1.0)
        self.command("ATE0")
        self.command("ATL0")
        self.command("ATS0")
        info["voltage"] = self.command("ATRV")
        info["protocol_set"] = self.command(f"ATSP{protocol}")
        info["protocol"] = self.command("ATDP")
        return info


def parse_response(reply: str) -> list[list[int]]:
    """Turn an adapter reply into a list of byte sequences, one per response line."""
    frames = []
    for line in reply.splitlines():
        line = line.strip()
        if not line or line in {"OK", "SEARCHING..."}:
            continue
        if any(marker in line for marker in ("NO DATA", "ERROR", "UNABLE", "?", "STOPPED")):
            continue
        tokens = line.replace(":", " ").split()
        byte_values = [int(tok, 16) for tok in tokens if len(tok) == 2 and _is_hex(tok)]
        if byte_values:
            frames.append(byte_values)
    return frames


def _is_hex(token: str) -> bool:
    try:
        int(token, 16)
    except ValueError:
        return False
    return True


def classify(frames: list[list[int]], service: int) -> dict[str, object]:
    """Classify a response as positive, negative (with NRC name), or empty.

    Adapters differ in whether they strip the ISO-TP PCI byte and the CAN header, so the
    service byte is looked for in the first two positions rather than only the first.
    """
    for data in frames:
        for offset in (0, 1):
            if len(data) <= offset:
                continue
            if data[offset] == service + 0x40:
                payload = data[offset:]
                return {"result": "positive", "data": " ".join(f"{b:02X}" for b in payload)}
            if data[offset] == 0x7F and len(data) >= offset + 3:
                nrc = data[offset + 2]
                return {
                    "result": "negative",
                    "nrc": f"0x{nrc:02X}",
                    "nrc_name": NRC.get(nrc, "unknown"),
                }
    return {"result": "no_response"}


def probe_ecu(elm: Elm327, ecu_request_id: str, extended: bool) -> dict[str, object]:
    """Basic liveness probe of one ECU address. Read-only."""
    elm.command(f"ATSH {ecu_request_id[2:]}")
    out: dict[str, object] = {"request_id": ecu_request_id}

    vin = parse_response(elm.command("0902", delay=0.5))
    out["vin_request"] = classify(vin, 0x09)

    did_f190 = parse_response(elm.command("22F190", delay=0.3))
    out["did_F190"] = classify(did_f190, 0x22)

    if extended:
        session = parse_response(elm.command("1003", delay=0.3))
        out["extended_session"] = classify(session, 0x10)
    return out


def sweep_dids(
    elm: Elm327, start: int, end: int, delay: float, verbose: bool
) -> list[dict[str, object]]:
    """Walk 22 <DID> across a range and record everything that answers.

    Read-only by construction: service 0x22 cannot modify ECU state. Negative responses
    are recorded too — a `securityAccessDenied` on a DID is itself a finding, because it
    says the identifier exists.
    """
    hits = []
    for did in range(start, end + 1):
        reply = elm.command(f"22{did:04X}", delay=delay)
        verdict = classify(parse_response(reply), 0x22)
        if verdict["result"] == "no_response":
            continue
        if verdict["result"] == "negative" and verdict.get("nrc") == "0x31":
            # requestOutOfRange: the identifier simply does not exist. Not a finding.
            continue
        entry = {"did": f"0x{did:04X}", **verdict}
        hits.append(entry)
        if verbose:
            print(f"  hit {entry}", file=sys.stderr)
    return hits


def parse_range(text: str) -> tuple[int, int]:
    """Parse '0xF180-0xF1FF' or a single '0xF190' into an inclusive range."""
    if "-" in text:
        low, high = text.split("-", 1)
        return int(low, 16), int(high, 16)
    value = int(text, 16)
    return value, value


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Read-only OBD-II/UDS reconnaissance over an ELM327-class adapter.",
        epilog="Stationary, owned vehicle only. This tool never writes.",
    )
    parser.add_argument("--port", required=True, help="Serial port, e.g. /dev/rfcomm0")
    parser.add_argument("--baud", type=int, default=115200, help="Serial baud rate")
    parser.add_argument("--timeout", type=float, default=2.0, help="Serial read timeout (s)")
    parser.add_argument(
        "--protocol",
        default=DEFAULT_PROTOCOL,
        help="ELM327 protocol number (default 6 = ISO 15765-4, 11-bit, 500 kbit/s)",
    )
    parser.add_argument(
        "--ecu",
        action="append",
        default=None,
        help="Request CAN ID to probe, repeatable (default: 0x7E0, 0x7E8)",
    )
    parser.add_argument(
        "--extended",
        action="store_true",
        help="Also try entering the extended diagnostic session (10 03) on each ECU",
    )
    parser.add_argument(
        "--scan-dids",
        metavar="RANGE",
        help="Sweep ReadDataByIdentifier over a hex range, e.g. 0xF180-0xF1FF",
    )
    parser.add_argument(
        "--scan-delay", type=float, default=0.15, help="Delay between sweep requests (s)"
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON")
    parser.add_argument("--verbose", action="store_true", help="Echo the adapter dialogue")
    args = parser.parse_args()

    elm = Elm327(args.port, args.baud, args.timeout, args.verbose)
    report: dict[str, object] = {}
    try:
        report["adapter"] = elm.init(args.protocol)
        ecus = args.ecu or DEFAULT_ECUS
        report["ecus"] = [probe_ecu(elm, ecu, args.extended) for ecu in ecus]

        if args.scan_dids:
            start, end = parse_range(args.scan_dids)
            elm.command(f"ATSH {ecus[0][2:]}")
            report["did_sweep"] = {
                "request_id": ecus[0],
                "range": args.scan_dids,
                "hits": sweep_dids(elm, start, end, args.scan_delay, args.verbose),
            }
    finally:
        elm.close()

    if args.json:
        print(json.dumps(report, indent=2))
        return

    adapter = report["adapter"]
    print(f"Adapter: {adapter['adapter']}")
    print(f"Voltage: {adapter['voltage']}   Protocol: {adapter['protocol']}")
    for ecu in report["ecus"]:
        print(f"\nECU {ecu['request_id']}")
        for key, value in ecu.items():
            if key == "request_id":
                continue
            print(f"  {key}: {value}")
    sweep = report.get("did_sweep")
    if sweep:
        print(f"\nDID sweep {sweep['range']} on {sweep['request_id']}: {len(sweep['hits'])} hits")
        for hit in sweep["hits"]:
            print(f"  {hit}")


if __name__ == "__main__":
    main()
