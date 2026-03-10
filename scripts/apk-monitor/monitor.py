#!/usr/bin/env python3
"""APK Monitoring Agent — main orchestrator.

This is the cron entry point.  It:
1. Discovers new APKs from APKPure that might be IoT Bluetooth apps.
2. Downloads them and scans for Bluetooth/BLE device patterns.
3. Checks each against the existing targets list.
4. For new BT-device APKs, launches RE agents on Claude, OpenAI, and local QWEN.
5. Saves transcripts to the configured transcripts repo.
6. Cross-checks agent results and votes on the best spec.
7. Auto-merges winners that pass the vote threshold.

Usage:
    python3 monitor.py                     # full run
    python3 monitor.py --scan-only         # only discover + scan, no RE agents
    python3 monitor.py --target <id>       # run RE agents on a specific target
    python3 monitor.py --vote <id>         # run voting on existing candidates
"""

import argparse
import csv
import json
import logging
import os
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

# Make sure sibling modules are importable
sys.path.insert(0, str(Path(__file__).parent))

from apk_discovery import discover_new_apks, load_known_packages
from bt_scanner import scan_apk, is_interesting, ScanResult
from re_agents import AgentTask, launch_all_agents
from merge_voter import cross_check_and_vote, auto_merge_winner

log = logging.getLogger("monitor")


def _load_config() -> dict:
    """Load config from config.env if present, fall back to environment."""
    config_path = Path(__file__).parent / "config.env"
    cfg: dict[str, str] = {}
    if config_path.exists():
        for line in config_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, val = line.partition("=")
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if val:  # only override if non-empty
                    cfg[key] = val
    # Environment variables take precedence
    for key in cfg:
        env_val = os.environ.get(key)
        if env_val:
            cfg[key] = env_val
    return cfg


def _detect_root() -> Path:
    """Detect the repo root directory."""
    return Path(__file__).resolve().parents[2]


def _append_to_targets_csv(targets_csv: Path, package_id: str, target_id: str,
                           device_class: str, transport: str) -> None:
    """Append a new entry to targets.csv."""
    with open(targets_csv, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([package_id, target_id, device_class, transport, "unspecified",
                         f"auto-discovered {datetime.now(timezone.utc).strftime('%Y-%m-%d')}"])


def _generate_target_id(package_id: str) -> str:
    """Generate a target_id from a package_id.

    e.g. com.example.myapp -> myapp
    Falls back to last two segments joined with hyphen.
    """
    parts = package_id.split(".")
    if len(parts) >= 3:
        return parts[-1].lower().replace("_", "-")
    return "-".join(parts[-2:]).lower().replace("_", "-")


def _save_run_log(workspace_dir: Path, log_data: dict) -> Path:
    """Save a JSON log of this run."""
    log_dir = workspace_dir / "apk-monitor" / "runs"
    log_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"run_{ts}.json"
    with open(log_path, "w") as f:
        json.dump(log_data, f, indent=2, default=str)
    return log_path


def run_full_pipeline(cfg: dict, scan_only: bool = False) -> dict:
    """Execute the full monitoring pipeline."""
    root_dir = Path(cfg.get("PROTOCOL_DOCS_ROOT", "")) or _detect_root()
    workspace_dir = Path(cfg.get("WORKSPACE_DIR", "")) or (root_dir / "workspace")
    transcripts_dir = Path(cfg.get("TRANSCRIPTS_REPO", "")) or (workspace_dir / "re-transcripts")
    targets_csv = root_dir / "targets" / "targets.csv"

    max_new = int(cfg.get("MAX_NEW_APKS_PER_RUN", "10"))
    apkeep_source = cfg.get("APKEEP_SOURCE", "apk-pure")
    min_votes = int(cfg.get("MIN_VOTES_TO_MERGE", "2"))

    run_log: dict = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "root_dir": str(root_dir),
        "discovered": [],
        "scanned": [],
        "interesting": [],
        "agents_launched": [],
        "votes": [],
    }

    # Step 1: Discover new APKs
    log.info("=== Step 1: Discovering new APKs ===")
    downloaded = discover_new_apks(root_dir, workspace_dir, max_new=max_new, apkeep_source=apkeep_source)
    run_log["discovered"] = downloaded
    log.info("Downloaded %d new APKs", len(downloaded))

    # Step 2: Scan each for Bluetooth
    log.info("=== Step 2: Scanning for Bluetooth patterns ===")
    interesting_targets: list[tuple[dict, ScanResult]] = []

    for apk_info in downloaded:
        pkg = apk_info["package_id"]
        apk_path = Path(apk_info["apk_path"])
        work_dir = workspace_dir / "apk-monitor" / "scans" / pkg

        result = scan_apk(pkg, apk_path, work_dir=work_dir)
        run_log["scanned"].append(asdict(result))

        if is_interesting(result):
            log.info("  INTERESTING: %s — %s", pkg, result.summary)
            interesting_targets.append((apk_info, result))
            run_log["interesting"].append({"package_id": pkg, "summary": result.summary})
        else:
            log.info("  skip: %s — %s", pkg, result.summary)

    if scan_only:
        log.info("=== Scan-only mode: stopping here ===")
        return run_log

    # Step 3: For each interesting target, register and launch RE agents
    log.info("=== Step 3: Launching RE agents ===")
    known_packages = load_known_packages(targets_csv)

    for apk_info, scan_result in interesting_targets:
        pkg = apk_info["package_id"]
        if pkg in known_packages:
            log.info("  Already in targets.csv, skipping: %s", pkg)
            continue

        target_id = _generate_target_id(pkg)

        # Add to targets.csv
        transport = "BLE" if scan_result.has_ble_gatt else "Bluetooth"
        _append_to_targets_csv(targets_csv, pkg, target_id, scan_result.summary[:50], transport)
        log.info("  Added to targets.csv: %s -> %s", pkg, target_id)

        # Build agent task
        task = AgentTask(
            package_id=pkg,
            target_id=target_id,
            apk_path=str(apk_info["apk_path"]),
            scan_summary=scan_result.summary,
            uuids_found=scan_result.uuids_found,
            device_class="auto-discovered",
            transport=transport,
        )

        # Find protocol hints from static analysis
        hints_path = workspace_dir / "apk-monitor" / "scans" / pkg / "jadx"
        protocol_hints = None
        rg_hints = workspace_dir / "apk-monitor" / "scans" / pkg / "summary" / "rg_protocol_hints.txt"
        if rg_hints.exists():
            protocol_hints = rg_hints

        # Launch agents
        results = launch_all_agents(
            task=task,
            root_dir=root_dir,
            transcripts_dir=transcripts_dir,
            claude_model=cfg.get("CLAUDE_MODEL", "claude-sonnet-4-20250514"),
            openai_model=cfg.get("OPENAI_MODEL", "gpt-4o"),
            local_model=cfg.get("LOCAL_MODEL", "qwen2.5-coder:32b"),
            local_base_url=cfg.get("LOCAL_MODEL_BASE_URL", "http://localhost:11434/v1"),
            local_api_key=cfg.get("LOCAL_MODEL_API_KEY", "ollama"),
            anthropic_api_key=cfg.get("ANTHROPIC_API_KEY", os.environ.get("ANTHROPIC_API_KEY", "")),
            openai_api_key=cfg.get("OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY", "")),
            protocol_hints_path=protocol_hints,
        )
        run_log["agents_launched"].append({
            "target_id": target_id,
            "results": [asdict(r) for r in results],
        })

        # Step 4: Cross-check and vote
        log.info("=== Step 4: Cross-checking and voting for %s ===", target_id)
        successful_agents = [r for r in results if r.success]
        if len(successful_agents) >= 2:
            decision = cross_check_and_vote(
                target_id=target_id,
                root_dir=root_dir,
                claude_model=cfg.get("CLAUDE_MODEL", "claude-sonnet-4-20250514"),
                openai_model=cfg.get("OPENAI_MODEL", "gpt-4o"),
                local_model=cfg.get("LOCAL_MODEL", "qwen2.5-coder:32b"),
                local_base_url=cfg.get("LOCAL_MODEL_BASE_URL", "http://localhost:11434/v1"),
                local_api_key=cfg.get("LOCAL_MODEL_API_KEY", "ollama"),
                anthropic_api_key=cfg.get("ANTHROPIC_API_KEY", os.environ.get("ANTHROPIC_API_KEY", "")),
                openai_api_key=cfg.get("OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY", "")),
            )
            decision = auto_merge_winner(decision, root_dir, min_votes=min_votes)
            run_log["votes"].append(asdict(decision))
        else:
            log.info("  Only %d successful agents — skipping vote", len(successful_agents))

    return run_log


def run_target_only(cfg: dict, target_id: str) -> dict:
    """Run RE agents on a specific existing target."""
    root_dir = Path(cfg.get("PROTOCOL_DOCS_ROOT", "")) or _detect_root()
    workspace_dir = Path(cfg.get("WORKSPACE_DIR", "")) or (root_dir / "workspace")
    transcripts_dir = Path(cfg.get("TRANSCRIPTS_REPO", "")) or (workspace_dir / "re-transcripts")
    targets_csv = root_dir / "targets" / "targets.csv"

    # Find the target in CSV
    pkg = ""
    transport = "BLE"
    device_class = "unknown"
    with open(targets_csv, newline="") as f:
        for row in csv.DictReader(f):
            if row.get("target_id") == target_id:
                pkg = row["package_id"]
                transport = row.get("transport", "BLE")
                device_class = row.get("device_class", "unknown")
                break

    if not pkg:
        log.error("Target %s not found in targets.csv", target_id)
        return {"error": f"target {target_id} not found"}

    # Find APK
    apk_candidates = list((workspace_dir / "apks").rglob(f"*{pkg}*.apk"))
    if not apk_candidates:
        apk_candidates = list((workspace_dir / "apks").rglob("*.apk"))
    apk_path = str(apk_candidates[0]) if apk_candidates else ""

    task = AgentTask(
        package_id=pkg,
        target_id=target_id,
        apk_path=apk_path,
        scan_summary=f"Manual run for existing target {target_id}",
        device_class=device_class,
        transport=transport,
    )

    results = launch_all_agents(
        task=task,
        root_dir=root_dir,
        transcripts_dir=transcripts_dir,
        claude_model=cfg.get("CLAUDE_MODEL", "claude-sonnet-4-20250514"),
        openai_model=cfg.get("OPENAI_MODEL", "gpt-4o"),
        local_model=cfg.get("LOCAL_MODEL", "qwen2.5-coder:32b"),
        local_base_url=cfg.get("LOCAL_MODEL_BASE_URL", "http://localhost:11434/v1"),
        local_api_key=cfg.get("LOCAL_MODEL_API_KEY", "ollama"),
        anthropic_api_key=cfg.get("ANTHROPIC_API_KEY", os.environ.get("ANTHROPIC_API_KEY", "")),
        openai_api_key=cfg.get("OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY", "")),
    )

    return {"target_id": target_id, "results": [asdict(r) for r in results]}


def run_vote_only(cfg: dict, target_id: str) -> dict:
    """Run cross-check voting on existing candidate specs."""
    root_dir = Path(cfg.get("PROTOCOL_DOCS_ROOT", "")) or _detect_root()

    decision = cross_check_and_vote(
        target_id=target_id,
        root_dir=root_dir,
        claude_model=cfg.get("CLAUDE_MODEL", "claude-sonnet-4-20250514"),
        openai_model=cfg.get("OPENAI_MODEL", "gpt-4o"),
        local_model=cfg.get("LOCAL_MODEL", "qwen2.5-coder:32b"),
        local_base_url=cfg.get("LOCAL_MODEL_BASE_URL", "http://localhost:11434/v1"),
        local_api_key=cfg.get("LOCAL_MODEL_API_KEY", "ollama"),
        anthropic_api_key=cfg.get("ANTHROPIC_API_KEY", os.environ.get("ANTHROPIC_API_KEY", "")),
        openai_api_key=cfg.get("OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY", "")),
    )
    decision = auto_merge_winner(decision, root_dir, min_votes=int(cfg.get("MIN_VOTES_TO_MERGE", "2")))
    return asdict(decision)


def main():
    parser = argparse.ArgumentParser(
        description="APK Monitoring Agent: discover, scan, reverse-engineer, vote, merge.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
        Examples:
          python3 monitor.py                  # full pipeline
          python3 monitor.py --scan-only      # discover + scan only
          python3 monitor.py --target pax-vape  # RE agents on specific target
          python3 monitor.py --vote pax-vape    # vote on existing candidates
        """),
    )
    parser.add_argument("--scan-only", action="store_true", help="Only discover and scan, skip RE agents")
    parser.add_argument("--target", type=str, help="Run RE agents on a specific target_id")
    parser.add_argument("--vote", type=str, help="Run voting on existing candidates for a target_id")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        handlers=[
            logging.StreamHandler(),
        ],
    )

    cfg = _load_config()
    root_dir = Path(cfg.get("PROTOCOL_DOCS_ROOT", "")) or _detect_root()
    workspace_dir = Path(cfg.get("WORKSPACE_DIR", "")) or (root_dir / "workspace")

    if args.target:
        result = run_target_only(cfg, args.target)
    elif args.vote:
        result = run_vote_only(cfg, args.vote)
    else:
        result = run_full_pipeline(cfg, scan_only=args.scan_only)

    log_path = _save_run_log(workspace_dir, result)
    log.info("Run log saved to: %s", log_path)
    print(json.dumps(result, indent=2, default=str))


# Needed for argparse epilog
import textwrap

if __name__ == "__main__":
    main()
