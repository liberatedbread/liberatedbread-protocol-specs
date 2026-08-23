"""Tests for re_agents.py — response extraction and prompt building."""

import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from re_agents import (
    AgentTask,
    _build_user_prompt,
    _extract_protocol_doc,
    _extract_spec_yaml,
    _output_limit_field,
)


class TestOutputLimitField:
    def test_gpt5_family_needs_max_completion_tokens(self):
        assert _output_limit_field("gpt-5.6-terra") == "max_completion_tokens"
        assert _output_limit_field("gpt-5.6-sol") == "max_completion_tokens"

    def test_o_series_needs_max_completion_tokens(self):
        assert _output_limit_field("o3-mini") == "max_completion_tokens"

    def test_other_providers_keep_max_tokens(self):
        assert _output_limit_field("gemini-3.1-pro-preview") == "max_tokens"
        assert _output_limit_field("deepseek-v4-pro") == "max_tokens"
        assert _output_limit_field("qwen3-coder:30b") == "max_tokens"


class TestExtractSpecYaml:
    def test_extracts_fenced_yaml(self):
        response = '### SPEC_YAML\n```yaml\ndevice: test\n```\n'
        assert _extract_spec_yaml(response) == "device: test"

    def test_extracts_yaml_without_header(self):
        response = 'Some text\n```yaml\ndevice: fallback\n```\n'
        assert _extract_spec_yaml(response) == "device: fallback"

    def test_empty_response(self):
        assert _extract_spec_yaml("") == ""

    def test_no_yaml_block(self):
        assert _extract_spec_yaml("Just text, no code blocks.") == ""


class TestExtractProtocolDoc:
    def test_extracts_fenced_markdown(self):
        response = '### PROTOCOL_DOC\n```markdown\n# Protocol\nDetails here.\n```\n'
        assert _extract_protocol_doc(response) == "# Protocol\nDetails here."

    def test_empty_response(self):
        assert _extract_protocol_doc("") == ""

    def test_no_doc_block(self):
        assert _extract_protocol_doc("Just text, no code blocks.") == ""


class TestBuildUserPrompt:
    def test_includes_target_info(self):
        task = AgentTask(
            package_id="com.test.app",
            target_id="test-app",
            apk_path="/test.apk",
            scan_summary="BLE detected",
        )
        prompt = _build_user_prompt(task)
        assert "com.test.app" in prompt
        assert "test-app" in prompt
        assert "BLE detected" in prompt

    def test_includes_uuids(self):
        task = AgentTask(
            package_id="com.test.app",
            target_id="test-app",
            apk_path="/test.apk",
            scan_summary="BLE",
            uuids_found=["12345678-1234-5678-9abc-def012345678"],
        )
        prompt = _build_user_prompt(task)
        assert "12345678-1234-5678-9abc-def012345678" in prompt

    def test_flutter_note_when_flutter(self):
        task = AgentTask(
            package_id="com.test.app",
            target_id="test-app",
            apk_path="/test.apk",
            scan_summary="BLE",
            is_flutter=True,
        )
        prompt = _build_user_prompt(task)
        assert "Flutter App Note" in prompt
        assert "flutter_blue_plus" in prompt

    def test_no_flutter_note_when_not_flutter(self):
        task = AgentTask(
            package_id="com.test.app",
            target_id="test-app",
            apk_path="/test.apk",
            scan_summary="BLE",
            is_flutter=False,
        )
        prompt = _build_user_prompt(task)
        assert "Flutter App Note" not in prompt
