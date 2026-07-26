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
# REQUEST IDs only. ATSH sets the header we transmit with, so a response ID such as
# 0x7E8 would put our requests on the ECU's own arbitration ID and simply look dead.
# 0x7E0 and 0x7E1 are the first two physically addressed ECUs on standard OBD-II.
DEFAULT_ECUS = ["0x7E0", "0x7E1"]

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
        # Spaces ON (ATS1) deliberately: separated bytes are unambiguous to parse. The
        # parser also handles the compact form, since some adapters ignore this.
        self.command("ATS1")
        info["voltage"] = self.command("ATRV")
        info["protocol_set"] = self.command(f"ATSP{protocol}")
        info["protocol"] = self.command("ATDP")
        return info


def parse_response(reply: str) -> list[list[int]]:
    """Turn an adapter reply into a list of byte sequences, one per response line.

    Handles both adapter output styles, because whether spaces appear depends on the
    adapter's ATS setting and not every adapter honours ours:

        spaced   "7E8 06 62 F1 90 01"   (optional 3-digit CAN header when ATH1)
        compact  "7E80662F19001"        (same reply with spaces off)
    """
    frames = []
    for line in reply.splitlines():
        line = line.strip()
        if not line or line in {"OK", "SEARCHING..."}:
            continue
        if any(marker in line for marker in ("NO DATA", "ERROR", "UNABLE", "?", "STOPPED")):
            continue
        # An ISO-TP multi-line reply prefixes each line with a frame index ("0:", "1:").
        if ":" in line:
            line = line.split(":", 1)[1].strip()
        byte_values = _line_to_bytes(line)
        if byte_values:
            frames.append(byte_values)
    return frames


def _line_to_bytes(line: str) -> list[int]:
    """Decode one response line to bytes, spaced or compact."""
    tokens = line.split()
    if len(tokens) > 1:
        # Spaced: two-character tokens are payload bytes. A three-character token is
        # the 11-bit CAN header (present under ATH1) and is not payload.
        return [int(tok, 16) for tok in tokens if len(tok) == 2 and _is_hex(tok)]

    compact = tokens[0] if tokens else ""
    if not compact or not _is_hex(compact):
        return []
    if len(compact) % 2:
        # Odd length means either a leading 3-digit CAN header or a bare multi-frame
        # total-length line ("014"). Dropping three characters resolves the first and
        # empties the second, which is the right outcome for both.
        compact = compact[3:]
        if not compact or len(compact) % 2:
            return []
    return [int(compact[i : i + 2], 16) for i in range(0, len(compact), 2)]


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


def response_id_for(request_id: str) -> str | None:
    """Paired response ID for a standard OBD-II physical request ID (0x7E0 -> 0x7E8).

    Returns None outside that range, where the pairing is manufacturer-defined and
    guessing would filter out the very replies we are looking for.
    """
    value = int(request_id, 16)
    if 0x7E0 <= value <= 0x7E7:
        return f"0x{value + 8:03X}"
    return None


def probe_ecu(elm: Elm327, ecu_request_id: str, extended: bool) -> dict[str, object]:
    """Basic liveness probe of one ECU address. Read-only.

    `ecu_request_id` is a REQUEST id: it becomes the ATSH transmit header.
    """
    elm.command(f"ATSH {ecu_request_id[2:]}")
    response_id = response_id_for(ecu_request_id)
    if response_id:
        elm.command(f"ATCRA {response_id[2:]}")
    else:
        elm.command("ATCRA")  # clear any previous filter
    out: dict[str, object] = {"request_id": ecu_request_id, "response_id": response_id}

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
            sweep_response_id = response_id_for(ecus[0])
            elm.command(f"ATCRA {sweep_response_id[2:]}" if sweep_response_id else "ATCRA")
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
