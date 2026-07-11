"""Tests for scripts/build_index.py.

Prerequisites: run from the repo root, with pyyaml + jsonschema installed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Make scripts/ importable
_scripts_dir = Path(__file__).resolve().parent
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

import build_index


def test_discover_specs():
    """Glob finds the expected YAML files under device-specs/devices/."""
    paths = build_index.discover_specs()
    assert len(paths) > 0, "Expected at least one device spec"
    stems = {build_index.spec_id(Path(p)) for p in paths}
    # The 4 device specs that exist on main as of this commit
    expected = {"admore-light-bar", "chef-iq-sense", "frigidaire-window-ac", "frigidaire-portable-ac"}
    assert stems == expected, f"Expected {sorted(expected)}, got {sorted(stems)}"


def test_load_yaml():
    """load_yaml returns a dict from a real spec."""
    paths = build_index.discover_specs()
    chef = [p for p in paths if "chef-iq-sense" in str(p)][0]
    spec = build_index.load_yaml(Path(chef))
    assert isinstance(spec, dict)
    assert "device" in spec
    assert spec["device"]["name"] == "CHEF iQ Sense"


def test_validate_all_specs_pass():
    """Every device spec in devices/ validates against schema.json."""
    schema = build_index.load_schema()
    paths = build_index.discover_specs()
    for path in paths:
        spec = build_index.load_yaml(Path(path))
        build_index.validate_spec(spec, schema, Path(path))


def test_manifest_structure(monkeypatch):
    """Manifest has the documented keys and valid device entries."""
    import datetime

    schema = build_index.load_schema()
    paths = build_index.discover_specs()

    generated_at = "2026-01-01T00:00:00+00:00"
    # Force git fallback so updated_at is deterministic
    monkeypatch.setattr(build_index, "git_last_modified", lambda p, fb: generated_at)

    manifest = build_index.build_manifest(paths, schema, generated_at)

    assert manifest["api_version"] == "1"
    assert manifest["generated_at"] == generated_at
    assert "https://opengreeniot.pigscanfly.ca/device-spec.schema.json" in manifest["schema"]
    assert manifest["device_count"] == len(paths)
    assert len(manifest["devices"]) == len(paths)

    for entry in manifest["devices"]:
        assert "id" in entry
        assert "name" in entry
        assert "manufacturer" in entry
        assert "protocol" in entry
        assert "status" in entry
        assert "updated_at" in entry
        assert entry["updated_at"] == generated_at  # forced fallback
        assert entry["url"].startswith("/api/v1/devices/")
        assert entry["url"].endswith(f"/{entry['id']}.json")
        assert entry["checksum"].startswith("sha256:")

    # Devices are sorted alphabetically
    ids = [e["id"] for e in manifest["devices"]]
    assert ids == sorted(ids), f"devices not sorted: {ids}"


def test_deterministic_output():
    """Two runs produce the same manifest and per-device JSON."""
    import datetime

    schema = build_index.load_schema()
    paths = build_index.discover_specs()
    generated_at = "2026-01-01T00:00:00+00:00"

    # Use the original git_last_modified; the test spec files are committed,
    # so git will return the same timestamp each run.  That makes the manifest
    # deterministic across runs of this test.
    m1 = build_index.build_manifest(paths, schema, generated_at)
    m2 = build_index.build_manifest(paths, schema, generated_at)

    assert build_index.json_dumps(m1) == build_index.json_dumps(m2)


def test_per_device_json():
    """Per-device JSON is valid JSON with expected structure."""
    schema = build_index.load_schema()
    paths = build_index.discover_specs()

    for path in paths:
        spec = build_index.load_yaml(Path(path))
        per_device = build_index.build_per_device_json(spec)
        json_str = build_index.json_dumps(per_device)
        # Round-trip
        assert json.loads(json_str) == per_device
        assert "device" in per_device
        # Must have at least one of services, http_endpoints, mqtt_topics
        assert any(
            k in per_device for k in ("services", "http_endpoints", "mqtt_topics")
        ), f"{build_index.spec_id(path)} missing transport"
