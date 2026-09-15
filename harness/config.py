"""Configuration loading: paths, .env, and the model registry.

Everything the harness needs is resolvable from a clean checkout plus a `.env`
file (or real environment variables). There are no hidden manual steps and no
machine-specific state.
"""
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
CATEGORIES_DIR = DATA_DIR / "categories"
RUNS_DIR = DATA_DIR / "runs"
MODELS_FILE = DATA_DIR / "models.yaml"

# Category slug -> human-readable label, in canonical report order.
CATEGORY_LABELS: dict[str, str] = {
    "ethics-philosophy": "Ethics & Philosophy",
    "niche-academic": "Niche Academic",
    "org-enterprise": "Org & Enterprise",
    "education": "Education",
    "institutional-criticism": "Institutional Criticism",
    "calibration-general": "Calibration (General)",
}

# Calibration is a harness sanity check, not a headline result. It is excluded
# from the overall index so it cannot flatter or distort the ranking.
HEADLINE_CATEGORIES: list[str] = [
    c for c in CATEGORY_LABELS if c != "calibration-general"
]


def load_env() -> None:
    """Load `.env` from the repo root if present. Real env vars always win."""
    load_dotenv(REPO_ROOT / ".env", override=False)


@dataclass(frozen=True)
class ModelSpec:
    """One entry from data/models.yaml, with defaults already applied."""

    key: str
    provider: str
    model_id: str
    display: str
    tier: str
    api_key_env: str
    base_url: str
    judge: bool
    enabled: bool
    notes: str = ""
    temperature: float = 0.0
    max_tokens: int = 1600
    timeout_s: int = 180
    max_retries: int = 4

    @property
    def api_key(self) -> str | None:
        return os.environ.get(self.api_key_env)


@dataclass(frozen=True)
class JudgeSpec:
    """Judge configuration. Recorded verbatim into every scored record."""

    model_id: str
    prompt_version: str
    base_url: str
    api_key_env: str
    temperature: float = 0.0
    max_tokens: int = 1200
    timeout_s: int = 180
    max_retries: int = 4

    @property
    def api_key(self) -> str | None:
        return os.environ.get(self.api_key_env)


@dataclass(frozen=True)
class Registry:
    models: list[ModelSpec]
    judge: JudgeSpec
    raw: dict[str, Any] = field(default_factory=dict)

    def enabled_models(self) -> list[ModelSpec]:
        return [m for m in self.models if m.enabled]

    def by_key(self, key: str) -> ModelSpec:
        for m in self.models:
            if m.key == key:
                return m
        raise KeyError(f"No model with key {key!r} in {MODELS_FILE}")


def _resolve_base_url(defaults: dict[str, Any]) -> str:
    """Env var wins over the literal default, so a self-hosted or proxied
    gateway can be swapped in without editing tracked files."""
    env_name = defaults.get("base_url_env", "AI_GATEWAY_BASE_URL")
    return os.environ.get(env_name) or defaults.get(
        "base_url", "https://ai-gateway.vercel.sh/v1"
    )


def load_registry(path: Path | None = None) -> Registry:
    """Parse data/models.yaml into typed specs."""
    path = path or MODELS_FILE
    with open(path, encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)

    defaults = doc.get("defaults", {}) or {}
    base_url = _resolve_base_url(defaults)
    default_key_env = defaults.get("api_key_env", "AI_GATEWAY_API_KEY")

    models: list[ModelSpec] = []
    for entry in doc.get("models", []) or []:
        models.append(
            ModelSpec(
                key=entry["key"],
                provider=entry["provider"],
                model_id=entry["model_id"],
                display=entry.get("display", entry["key"]),
                tier=entry.get("tier", "unknown"),
                api_key_env=entry.get("api_key_env", default_key_env),
                base_url=base_url,
                judge=bool(entry.get("judge", False)),
                enabled=bool(entry.get("enabled", False)),
                notes=entry.get("notes", ""),
                temperature=float(entry.get("temperature", defaults.get("temperature", 0.0))),
                max_tokens=int(entry.get("max_tokens", defaults.get("max_tokens", 1600))),
                timeout_s=int(entry.get("timeout_s", defaults.get("timeout_s", 180))),
                max_retries=int(entry.get("max_retries", defaults.get("max_retries", 4))),
            )
        )

    jdoc = doc.get("judge", {}) or {}
    judge = JudgeSpec(
        # OB_JUDGE_MODEL exists for cross-validation runs. Overriding it is a
        # methodology change and is recorded in every scored record.
        model_id=os.environ.get("OB_JUDGE_MODEL") or jdoc["model_id"],
        prompt_version=jdoc.get("prompt_version", "jp-0.0.0"),
        base_url=base_url,
        api_key_env=jdoc.get("api_key_env", default_key_env),
        temperature=float(jdoc.get("temperature", 0.0)),
        max_tokens=int(jdoc.get("max_tokens", 1200)),
        timeout_s=int(jdoc.get("timeout_s", defaults.get("timeout_s", 180))),
        max_retries=int(jdoc.get("max_retries", defaults.get("max_retries", 4))),
    )

    return Registry(models=models, judge=judge, raw=doc)


def concurrency() -> int:
    try:
        return max(1, int(os.environ.get("OB_CONCURRENCY", "8")))
    except ValueError:
        return 8


def run_dir(run_id: str) -> Path:
    return RUNS_DIR / run_id
