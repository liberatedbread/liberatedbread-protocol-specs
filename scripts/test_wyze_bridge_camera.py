"""Checks the bounded docker-wyze-bridge spec using only its published data."""

from pathlib import Path
import re

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
SPEC_PATH = ROOT / "device-specs" / "devices" / "wyze-bridge-camera.yaml"


@pytest.fixture(scope="module")
def spec() -> dict:
    return yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))


def camera_slug(nickname: str) -> str:
    """Transcribe protocol_details.camera_slug's unmodified default."""
    separated = nickname.strip().replace(" ", "-")
    return re.sub(r"[^\-\w+]", "", separated, flags=re.ASCII).lower()


def test_exact_supported_model_allowlist(spec):
    expected = {
        "WYZEC1",
        "WYZEC1-JZ",
        "WYZE_CAKP2JFUS",
        "HL_CAM3P",
        "HL_CAM4",
        "WYZECP1_JEF",
        "HL_PAN2",
        "HL_PAN3",
        "HL_PANP",
        "WVOD1",
        "HL_WCO2",
        "WYZEDB3",
        "HL_DB2",
        "HL_CFL",
        "HL_CFL2",
    }
    actual = {variant["model"] for variant in spec["device"]["variants"]}
    assert actual == expected
    assert {
        "HL_PAN4",
        "GW_GC1",
        "GW_GC2",
        "AN_RSCW",
        "LD_CFP",
        "GW_BE1",
        "AN_RDB1",
        "ME_DB1",
    }.isdisjoint(actual)


def test_floodlight_and_shared_v3_model_mapping_is_explicit(spec):
    variants = {v["model"]: v for v in spec["device"]["variants"]}
    assert variants["WYZE_CAKP2JFUS"]["products"] == [
        "Wyze Cam v3",
        "Wyze Cam Floodlight v1",
    ]
    assert variants["HL_CFL"]["products"] == ["Wyze Cam Floodlight v1"]
    assert variants["HL_CFL2"]["products"] == ["Wyze Cam Floodlight v2 (2K)"]


@pytest.mark.parametrize(
    ("nickname", "expected"),
    [
        ("Front Porch Cam", "front-porch-cam"),
        ("  Back Yard  ", "back-yard"),
        ("Garage+East", "garage+east"),
        ("Doorbell!", "doorbell"),
    ],
)
def test_default_camera_slug(spec, nickname, expected):
    assert camera_slug(nickname) == expected
    published = spec["protocol_details"]["camera_slug"]
    assert published["default_separator"] == "-"
    assert any("Lowercase" in step for step in published["algorithm"])


def test_discovery_is_manual_bridge_host_only(spec):
    discovery = spec["device"]["discovery"]
    assert "none" in discovery
    assert "methods" not in discovery
    assert discovery["identity"]["stable_keys"] == ["bridge_host", "camera_name"]
    assert spec["camera"]["feed_host_source"] == "nvr"
    assert all(stream["served_by"] == "nvr" for stream in spec["camera"]["streams"])


def test_stream_templates_use_bridge_address_and_real_hls_path(spec):
    streams = {stream["transport"]: stream for stream in spec["camera"]["streams"]}
    assert streams["rtsp"]["url_template"] == "rtsp://{address}:8554/{camera_name}"
    assert streams["hls"]["url_template"] == (
        "http://{address}:8888/{camera_name}/stream.m3u8"
    )
    assert streams["webrtc"]["url_template"] == "http://{address}:8889/{camera_name}"
    for stream in streams.values():
        assert "{bridge_address}" not in stream["url_template"]
        assert "{device" not in stream["url_template"]


def test_tutk_modes_and_cloud_boundary(spec):
    tutk = spec["protocol_details"]["tutk_sessions"]
    assert {m["value"]: m["name"] for m in tutk["modes"]} == {
        0: "P2P",
        1: "relay",
        2: "LAN",
    }
    assert tutk["preferred_mode"] == 2
    assert tutk["cloud_account_and_api_required"] is True
    assert tutk["permanent_isolation_supported"] is False
    assert "NET_MODE=LAN" in tutk["lan_only"]
    assert "local bridge endpoints" in tutk["modes"][1]["meaning"]


def test_wb_auth_stream_auth_and_explicit_anonymous_mode(spec):
    auth = spec["protocol_details"]["bridge_authentication"]
    assert auth["default"]["WB_AUTH"] is True
    assert auth["default"]["stream_username"] == "wb"
    assert "unique WB_API key" in auth["default"]["stream_password_source"]
    assert auth["default"]["webui_username_default"] == "wbadmin"
    assert auth["custom_stream_auth"]["variable"] == "STREAM_AUTH"
    assert "@path" in auth["custom_stream_auth"]["syntax"]
    assert auth["explicitly_disabled"]["configuration"] == (
        "WB_AUTH=false with STREAM_AUTH unset"
    )
    assert "anonymous" in auth["explicitly_disabled"]["behavior"]
    for stream in spec["camera"]["streams"]:
        assert stream["auth"] != "none"


def test_reset_is_product_scoped_and_v1_has_its_own_hold(spec):
    procedures = spec["device"]["setup"]["factory_reset"]["procedures"]
    products = {
        product
        for procedure in procedures
        for product in procedure["product_names"]
    }
    assert products == {
        "Wyze Cam v1 (HD only)",
        "Wyze Cam v2",
        "Wyze Cam v3",
        "Wyze Cam Pan v1",
    }
    holds = {
        product: procedure["hold_seconds"]
        for procedure in procedures
        for product in procedure["product_names"]
    }
    assert holds == {
        "Wyze Cam v1 (HD only)": 20,
        "Wyze Cam v2": 10,
        "Wyze Cam Pan v1": 10,
        "Wyze Cam v3": 10,
    }
    v3 = next(p for p in procedures if p["product_names"] == ["Wyze Cam v3"])
    assert v3["excluded_product_names"] == ["Wyze Cam Floodlight v1"]
    assert all(p["verified"] is False and p["basis"] for p in procedures)


def test_each_reset_product_has_its_model_qsg(spec):
    manuals = {
        entry["title"]: entry
        for entry in spec["helpful_urls"]
        if entry.get("kind") == "manual"
    }
    assert set(manuals) == {
        "Wyze Cam v1 Quick Start Guide",
        "Wyze Cam v2 Quick Start Guide",
        "Wyze Cam v3 Quick Start Guide",
        "Wyze Cam Pan v1 Quick Start Guide",
    }
    assert all("specifically for" in entry["description"] for entry in manuals.values())


def test_stock_firmware_rtsp_exception_is_narrow(spec):
    notes = spec["device"]["notes"]
    assert "no first-party general-purpose local API" in notes
    assert "wyze-legacy-rtsp.yaml" in notes
    assert "must not be generalized" in notes
