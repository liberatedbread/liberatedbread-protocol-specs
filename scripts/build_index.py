#!/usr/bin/env python3
"""Build a machine-consumable JSON API from device-spec YAML files.

Discovers all ``device-specs/devices/*.yaml`` files, validates each against
``device-specs/schema.json`` (JSON Schema draft 2020-12), and emits:

* ``site/api/v1/devices/<id>.json`` — the YAML spec normalized to JSON
* ``site/api/v1/manifest.json`` — a registry index with checksums, timestamps, URLs

Usage::

    python scripts/build_index.py          # generate site/api/v1/*
    python scripts/build_index.py --check  # validate only, no output

The generated JSON is deterministic: devices are sorted alphabetically by id
and JSON keys are sorted.  The ``updated_at`` timestamp is extracted from
``git log -1 --format=%aI`` for each YAML file; if the repo is not a git
checkout the current UTC time is used as a fallback.
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import jsonschema
import yaml


REPO_ROOT = Path(__file__).resolve().parent.parent
SPECS_DIR = REPO_ROOT / "device-specs" / "devices"
SCHEMA_PATH = REPO_ROOT / "device-specs" / "schema.json"
API_DIR = REPO_ROOT / "site" / "api" / "v1"
MANIFEST_PATH = API_DIR / "manifest.json"


def load_schema() -> Dict[str, Any]:
    """Load the JSON Schema and return it as a dict."""
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


def discover_specs() -> List[Path]:
    """Return sorted list of YAML spec files under SPECS_DIR."""
    return sorted(glob.glob(str(SPECS_DIR / "*.yaml")))


def load_yaml(path: Path) -> Dict[str, Any]:
    """Load a YAML file and return its contents as a dict."""
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Expected a YAML mapping in {path}, got {type(data).__name__}")
    return data


def validate_spec(spec: Dict[str, Any], schema: Dict[str, Any], path: Path) -> None:
    """Validate *spec* against *schema*; raise on failure."""
    validator_cls = jsonschema.validators.validator_for(schema)
    validator_cls.check_schema(schema)
    errors = list(validator_cls(schema).iter_errors(spec))
    if errors:
        lines = [f"Validation failed for {path.relative_to(REPO_ROOT)}:"]
        for err in errors:
            lines.append(f"  {err.json_path}: {err.message}")
        raise jsonschema.ValidationError("\n".join(lines))


def git_last_modified(path: Path, fallback: str) -> str:
    """Return ISO-8601 timestamp of the last git commit touching *path*.

    Falls back to *fallback* when ``git log`` fails (e.g. no git repo).
    """
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%aI", "--", str(path)],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return fallback


def json_dumps(obj: Any) -> str:
    """Serialize *obj* to deterministic, pretty-printed JSON."""
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False)


def compute_checksum(json_str: str) -> str:
    """Return ``sha256:<hexdigest>`` of *json_str*."""
    return f"sha256:{hashlib.sha256(json_str.encode('utf-8')).hexdigest()}"


def spec_id(path: Path) -> str:
    """Return the device id (filename stem) for *path*."""
    return Path(path).stem


def _normalize_for_json(obj: Any) -> Any:
    """Recursively convert Python objects to JSON-safe equivalents.

    In particular, YAML integer dict keys become Python ``int`` keys, but
    JSON only supports string keys.  We convert them so that
    ``json.dumps`` is lossless on round-trip through ``json.loads``.
    """
    if isinstance(obj, dict):
        return {
            str(k) if isinstance(k, int) else k: _normalize_for_json(v)
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_normalize_for_json(v) for v in obj]
    if isinstance(obj, tuple):
        return [_normalize_for_json(v) for v in obj]
    return obj


def build_per_device_json(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize *spec* dict for the per-device JSON endpoint."""
    return _normalize_for_json(spec)


def build_manifest(
    spec_paths: List[Path],
    schema: Dict[str, Any],
    generated_at: str,
) -> Dict[str, Any]:
    """Build the manifest JSON from all validated specs."""
    device_entries: List[Dict[str, Any]] = []
    device_count = 0

    for path in spec_paths:
        spec = load_yaml(path)
        validate_spec(spec, schema, path)
        device_count += 1

        sid = spec_id(path)
        url = f"/api/v1/devices/{sid}.json"
        per_device_path = API_DIR / "devices" / f"{sid}.json"

        # Compute per-device JSON first so we can checksum it
        per_device_data = build_per_device_json(spec)
        per_device_json = json_dumps(per_device_data)

        updated_at = git_last_modified(path, generated_at)

        device_entries.append({
            "id": sid,
            "name": spec.get("device", {}).get("name", sid),
            "manufacturer": spec.get("device", {}).get("manufacturer", ""),
            "protocol": spec.get("device", {}).get("protocol", ""),
            "status": spec.get("device", {}).get("manufacturer_status", ""),
            "updated_at": updated_at,
            "url": url,
            "checksum": compute_checksum(per_device_json),
        })

    schema_id = schema.get("$id", "")
    return {
        "api_version": "1",
        "generated_at": generated_at,
        "schema": schema_id,
        "device_count": device_count,
        "devices": device_entries,
    }


def write_output(manifest: Dict[str, Any], spec_paths: List[Path], schema: Dict[str, Any]) -> None:
    """Write manifest.json and per-device JSON files to disk."""
    API_DIR.mkdir(parents=True, exist_ok=True)
    devices_dir = API_DIR / "devices"
    devices_dir.mkdir(parents=True, exist_ok=True)

    for path in spec_paths:
        spec = load_yaml(path)
        validate_spec(spec, schema, path)
        sid = spec_id(path)
        per_device_data = build_per_device_json(spec)
        per_device_json = json_dumps(per_device_data)
        out_path = devices_dir / f"{sid}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(per_device_json)
            f.write("\n")

    manifest_json = json_dumps(manifest)
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        f.write(manifest_json)
        f.write("\n")


def run(generated_at: str | None = None, check_only: bool = False) -> int:
    """Discover, validate, and index all device specs.

    Returns 0 on success, non-zero on failure.
    """
    if generated_at is None:
        generated_at = datetime.now(timezone.utc).isoformat()

    schema = load_schema()
    spec_paths = discover_specs()

    if not spec_paths:
        print("No device specs found in", str(SPECS_DIR), file=sys.stderr)
        return 1

    # Validate all specs first
    errors = []
    for path in spec_paths:
        try:
            spec = load_yaml(path)
            validate_spec(spec, schema, path)
        except (yaml.YAMLError, ValueError, jsonschema.ValidationError) as exc:
            errors.append(str(exc))

    if errors:
        for err in errors:
            print(err, file=sys.stderr)
        return 1

    if check_only:
        print(f"✓ {len(spec_paths)} device specs validated successfully")
        return 0

    # Build manifest and write output
    manifest = build_manifest(spec_paths, schema, generated_at)
    write_output(manifest, spec_paths, schema)

    print(f"✓ Manifest: {MANIFEST_PATH} ({manifest['device_count']} devices)")
    for entry in manifest["devices"]:
        dev_path = API_DIR / "devices" / f"{entry['id']}.json"
        print(f"  {entry['id']}: {dev_path}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build JSON API from device-spec YAML files.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate all specs without writing output files.",
    )
    args = parser.parse_args()
    sys.exit(run(check_only=args.check))


if __name__ == "__main__":
    main()
