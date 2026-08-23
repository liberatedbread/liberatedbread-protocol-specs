#!/usr/bin/env python3
"""Shared configuration for the APK monitoring agent.

Provides ModelConfig, ResolvedPaths, and load_config() to eliminate
repeated parameter passing across modules.
"""

import os
from dataclasses import dataclass
from pathlib import Path

# ── Defaults ──────────────────────────────────────────────
# Model ids go stale as vendors retire them; each is overridable from
# config.env so a retirement is a one-line edit, not a code change.
DEFAULT_CLAUDE_MODEL = "claude-sonnet-5"
DEFAULT_OPENAI_MODEL = "gpt-5.6-terra"
DEFAULT_GEMINI_MODEL = "gemini-3.1-pro-preview"
DEFAULT_DEEPSEEK_MODEL = "deepseek-v4-pro"
DEFAULT_LOCAL_MODEL = "qwen3-coder:30b"
DEFAULT_LOCAL_BASE_URL = "http://localhost:11434/v1"
DEFAULT_LOCAL_API_KEY = "ollama"
DEFAULT_APKEEP_SOURCE = "apk-pure"
DEFAULT_MAX_NEW_APKS = 10
DEFAULT_MIN_VOTES = 2
DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
# Gemini and DeepSeek both expose OpenAI-compatible chat completions, so they
# ride the same client as OpenAI — only the base URL and key differ.
DEFAULT_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"
DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
MAX_TOKENS = 16384

# All env vars we recognize (checked even without a config file)
_KNOWN_KEYS = {
    "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY", "DEEPSEEK_API_KEY",
    "CLAUDE_MODEL", "OPENAI_MODEL", "GEMINI_MODEL", "DEEPSEEK_MODEL",
    "LOCAL_MODEL", "LOCAL_MODEL_BASE_URL", "LOCAL_MODEL_API_KEY",
    "PROTOCOL_DOCS_ROOT", "TRANSCRIPTS_REPO", "WORKSPACE_DIR",
    "APKEEP_SOURCE", "APKEEP_EMAIL", "APKEEP_AAS_TOKEN",
    "APK_SEARCH_CATEGORIES", "MAX_NEW_APKS_PER_RUN",
    "PROTOCOL_DOCS_REMOTE", "RE_BRANCH_PREFIX", "MIN_VOTES_TO_MERGE",
}


def _detect_root() -> Path:
    """Detect the repo root (two levels up from this file)."""
    return Path(__file__).resolve().parents[2]


@dataclass
class ModelConfig:
    """API keys and model identifiers for the RE agents."""
    claude_model: str = DEFAULT_CLAUDE_MODEL
    openai_model: str = DEFAULT_OPENAI_MODEL
    gemini_model: str = DEFAULT_GEMINI_MODEL
    deepseek_model: str = DEFAULT_DEEPSEEK_MODEL
    local_model: str = DEFAULT_LOCAL_MODEL
    local_base_url: str = DEFAULT_LOCAL_BASE_URL
    local_api_key: str = DEFAULT_LOCAL_API_KEY
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    gemini_api_key: str = ""
    deepseek_api_key: str = ""

    @classmethod
    def from_cfg(cls, cfg: dict) -> "ModelConfig":
        return cls(
            claude_model=cfg.get("CLAUDE_MODEL", DEFAULT_CLAUDE_MODEL),
            openai_model=cfg.get("OPENAI_MODEL", DEFAULT_OPENAI_MODEL),
            gemini_model=cfg.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL),
            deepseek_model=cfg.get("DEEPSEEK_MODEL", DEFAULT_DEEPSEEK_MODEL),
            local_model=cfg.get("LOCAL_MODEL", DEFAULT_LOCAL_MODEL),
            local_base_url=cfg.get("LOCAL_MODEL_BASE_URL", DEFAULT_LOCAL_BASE_URL),
            local_api_key=cfg.get("LOCAL_MODEL_API_KEY", DEFAULT_LOCAL_API_KEY),
            anthropic_api_key=cfg.get("ANTHROPIC_API_KEY", ""),
            openai_api_key=cfg.get("OPENAI_API_KEY", ""),
            gemini_api_key=cfg.get("GEMINI_API_KEY", ""),
            deepseek_api_key=cfg.get("DEEPSEEK_API_KEY", ""),
        )

    def agent_configs(self) -> list[tuple[str, str, str, str]]:
        """Return (agent_name, model, api_key, base_url) for each agent.

        Agents without a key are skipped by the callers, so an operator who
        only has two of the four hosted keys still gets a usable panel.
        """
        return [
            ("claude", self.claude_model, self.anthropic_api_key, ""),
            ("openai", self.openai_model, self.openai_api_key, DEFAULT_OPENAI_BASE_URL),
            ("gemini", self.gemini_model, self.gemini_api_key, DEFAULT_GEMINI_BASE_URL),
            ("deepseek", self.deepseek_model, self.deepseek_api_key, DEFAULT_DEEPSEEK_BASE_URL),
            ("local-qwen", self.local_model, self.local_api_key, self.local_base_url),
        ]


@dataclass
class ResolvedPaths:
    """Pre-resolved filesystem paths used throughout the pipeline."""
    root_dir: Path
    workspace_dir: Path
    transcripts_dir: Path
    targets_csv: Path

    @classmethod
    def from_cfg(cls, cfg: dict) -> "ResolvedPaths":
        root = Path(cfg["PROTOCOL_DOCS_ROOT"]) if cfg.get("PROTOCOL_DOCS_ROOT") else _detect_root()
        workspace = Path(cfg["WORKSPACE_DIR"]) if cfg.get("WORKSPACE_DIR") else root / "workspace"
        transcripts = Path(cfg["TRANSCRIPTS_REPO"]) if cfg.get("TRANSCRIPTS_REPO") else workspace / "re-transcripts"
        return cls(
            root_dir=root,
            workspace_dir=workspace,
            transcripts_dir=transcripts,
            targets_csv=root / "targets" / "targets.csv",
        )


def load_config(config_path: Path | None = None) -> dict:
    """Load config from a file, then overlay environment variables.

    Environment variables always take precedence over file values.
    All keys in _KNOWN_KEYS are checked in the environment even if
    no config file is present.
    """
    cfg: dict[str, str] = {}

    if config_path is None:
        config_path = Path(__file__).parent / "config.env"

    if config_path.exists():
        for line in config_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, val = line.partition("=")
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if val:
                    cfg[key] = val

    # Environment variables override file values; also check known keys
    # that may not be in the file at all.
    for key in _KNOWN_KEYS | set(cfg.keys()):
        env_val = os.environ.get(key)
        if env_val:
            cfg[key] = env_val

    return cfg
