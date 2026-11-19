"""Boundary and evidence tests for the three legacy official Wyze RTSP variants."""

from pathlib import Path
import re

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
SPEC_PATH = ROOT / "device-specs" / "devices" / "wyze-legacy-rtsp.yaml"


@pytest.fixture(scope="module")
def spec() -> dict:
    return yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))


def test_exact_product_model_installed_firmware_matrix(spec):
    variants = {
        (v["product_name"], v["model"]): v["firmware"]["installed_version"]
        for v in spec["device"]["variants"]
    }
    assert variants == {
        ("Wyze Cam v2", "WYZEC1-JZ"): "4.28.4.49",
        ("Wyze Cam v3 (standalone, not Floodlight)", "WYZE_CAKP2JFUS"): "4.61.0.3",
        ("Wyze Cam Pan v1", "WYZECP1_JEF"): "4.29.4.49",
    }
    allowed_models = {model for _, model in variants}
    assert {
        "WYZEC1",
        "HL_PAN2",
        "HL_PAN3",
        "HL_CAM4",
        "HL_CFL",
        "HL_CFL2",
        "WYZEDB3",
        "WVOD1",
    }.isdisjoint(allowed_models)
    assert set(variants.values()).isdisjoint(
        {"4.28.4.50", "4.28.4.51", "4.29.4.50", "4.29.4.51", "4.61.0.1", "4.36.16.5055"}
    )


def test_official_archive_and_inner_hashes_are_complete(spec):
    expected = {
        "WYZEC1-JZ": (
            "4.28.4.49",
            "5aaa61d522ab7d0edcddcd8a67da94de12338ddb3eb1e63fc67166e3f61ba084",
            "ec1355746aab26ff581a3a12dec55c31b9c2e7259013a106d58281be170fc1c8",
            "demo.bin",
        ),
        "WYZE_CAKP2JFUS": (
            "4.61.0.1",
            "1668cfb1ca4f68b7773bcc14d5a5084771e1fbea6c757cd73e47698278f434e3",
            "5e3e31f8e709e3b682000c047b9ca29d05bc0b02a5320bfbf32de6fdacbb2715",
            "demo_wcv3.bin",
        ),
        "WYZECP1_JEF": (
            "4.29.4.49",
            "a7b3cfa8a5dd823bdb634ee50bd64e3db048358b6bbf34ff0b0c58fae82902b2",
            "ea920b3d49e9fb9ee67c0a0af54dab9ab70919875e18f5fab26beb600b2a60d4",
            "demo.bin",
        ),
    }
    for variant in spec["device"]["variants"]:
        firmware = variant["firmware"]
        version, archive_hash, inner_hash, sd_name = expected[variant["model"]]
        assert firmware["archive_package_version"] == version
        assert "package_version" not in firmware
        assert firmware["archive_sha256"] == archive_hash
        assert firmware["inner_sha256"] == inner_hash
        assert firmware["microsd_filename"] == sd_name
        assert firmware["archive_url"].startswith("https://download.wyzecam.com/firmware/rtsp/")
        for digest in (archive_hash, inner_hash):
            assert re.fullmatch(r"[0-9a-f]{64}", digest)


def test_stream_is_opaque_app_generated_full_url_not_invented(spec):
    camera = spec["camera"]
    assert len(camera["streams"]) == 1
    stream = camera["streams"][0]
    assert stream["transport"] == "rtsp"
    assert stream["url_template"] == "{stream_url}"
    assert "default_port" not in stream
    assert stream["served_by"] == "device"
    assert "app-generated" in stream["auth"]
    assert "No default_port" in stream["notes"]
    assert "/live" in stream["notes"]  # named only as something NOT to append
    assert camera["stream_discovery"]["method"] == "wyze_app_generate_full_url"
    assert "Generate URL" in camera["stream_discovery"]["id_source"]
    assert "none" in spec["device"]["discovery"]
    assert "methods" not in spec["device"]["discovery"]


def test_app_enable_route_has_per_camera_credentials_and_generate_url(spec):
    primary = spec["device"]["setup"]["methods"][0]
    assert primary["role"] == "primary"
    actions = "\n".join(step["action"] for step in primary["steps"])
    assert "Settings > Advanced Settings > RTSP" in actions
    assert "username and password unique to this camera" in actions
    assert "4-10 characters" in actions
    assert "Generate URL" in actions
    assert "including its credentials, host, port and path" in actions


def test_installed_version_selection_is_distinct_from_archive_download(spec):
    scope = spec["protocol_details"]["legacy_rtsp_scope"]
    assert "firmware.installed_version" in scope["selection_rule"]
    assert "4.61.0.3" in scope["selection_rule"]
    assert "firmware.archive_package_version" in scope["archive_rule"]
    assert "4.61.0.1" in scope["archive_rule"]
    primary = spec["device"]["setup"]["methods"][0]
    primary_actions = "\n".join(step["action"] for step in primary["steps"])
    assert "firmware.installed_version" in primary_actions
    post_flash = spec["device"]["setup"]["methods"][1]["stages"][1]
    post_flash_actions = "\n".join(step["action"] for step in post_flash["steps"])
    assert "installed_version" in post_flash_actions
    assert "4.61.0.3" in post_flash_actions
    assert "4.61.0.1 archive_package_version" in post_flash_actions
    beta = next(
        doc
        for doc in spec["device"]["openness"]["upstream_docs"]
        if doc["title"] == "Official standalone Cam v3 RTSP beta announcement"
    )
    assert "4.61.0.1" in beta["covers"]
    assert "4.61.0.3" in beta["covers"]


def test_microsd_route_is_advanced_alternative_with_rendered_warnings(spec):
    alternative = spec["device"]["setup"]["methods"][1]
    assert alternative["role"] == "alternative"
    assert alternative["advanced"] is True
    rendered_method = alternative["description"]
    for warning in (
        "Later features are lost",
        "AI/Cam Plus functions may be unstable",
        "ongoing branch maintenance is not committed",
        "interrupted-flash recovery is unknown",
    ):
        assert warning in rendered_method
    assert [stage["type"] for stage in alternative["stages"]] == [
        "none",
        "cloud_account",
    ]
    flash_stage = alternative["stages"][0]
    assert "AI/Cam Plus functions may be" in flash_stage["description"]
    assert "interrupted-flash recovery is unknown" in flash_stage["description"]
    flash_actions = "\n".join(step["action"] for step in flash_stage["steps"])
    assert "archive_package_version" in flash_actions
    assert "archive_sha256" in flash_actions
    assert "inner_sha256" in flash_actions
    assert "demo_wcv3.bin" in flash_actions
    assert "remove the microSD card" in flash_actions


def test_feature_loss_and_maintenance_scope_is_explicit(spec):
    local = spec["local_access"]
    assert local["status"] == "firmware_replacement"
    assert any("Features added after" in item for item in local["not_covered"])
    assert any("maintenance" in item for item in local["not_covered"])
    feature = spec["features"][0]
    assert feature["type"] == "firmware_update"
    assert feature["dfu"]["mechanisms"] == ["custom"]
    assert feature["dfu"]["verification"] == "reported"
    assert feature["dfu"]["recovery"]["interrupted"] == "unknown"


def test_reset_is_reused_only_for_matching_products(spec):
    procedures = spec["device"]["setup"]["factory_reset"]["procedures"]
    products = {
        product
        for procedure in procedures
        for product in procedure["product_names"]
    }
    assert products == {
        "Wyze Cam v2",
        "Wyze Cam Pan v1",
        "Wyze Cam v3 (standalone, not Floodlight)",
    }
    assert all(procedure["hold_seconds"] == 10 for procedure in procedures)
    assert all(procedure["verified"] is False for procedure in procedures)
    assert all(procedure["basis"] for procedure in procedures)
    assert "WYZEC1" not in {
        model for procedure in procedures for model in procedure["applies_to"]
    }


def test_official_article_firmware_sources_and_evidence_are_linked(spec):
    links = {entry["url"]: entry for entry in spec["helpful_urls"]}
    assert "https://support.wyze.com/hc/en-us/articles/360026245231-Wyze-Cam-RTSP" in links
    assert "https://support.wyze.com/hc/en-us/articles/360031490871-How-to-flash-your-Wyze-Cam-firmware-manually" in links
    official_archives = [
        entry for entry in spec["helpful_urls"] if entry["title"].startswith("Official") and "archive" in entry["title"]
    ]
    assert len(official_archives) == 3
    assert all("SHA-256" in entry["description"] for entry in official_archives)
    artifacts = [a for a in spec["evidence"]["artifacts"] if a["type"] == "firmware_image"]
    assert len(artifacts) == 3
    assert all("No firmware retained" in a["description"] for a in artifacts)
    assert spec["device"]["testing"]["status"] == "untested"


def test_per_model_qsgs_exclude_cam_v1(spec):
    manuals = [entry for entry in spec["helpful_urls"] if entry.get("kind") == "manual"]
    assert {entry["title"] for entry in manuals} == {
        "Wyze Cam v2 Quick Start Guide",
        "Wyze Cam v3 Quick Start Guide",
        "Wyze Cam Pan v1 Quick Start Guide",
    }
    assert all("specifically for" in entry["description"] for entry in manuals)
