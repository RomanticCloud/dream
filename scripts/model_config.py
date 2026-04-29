#!/usr/bin/env python3
"""Model configuration helpers for dream generation steps."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
DEFAULT_CONFIG_FILE = SKILL_DIR / "dream_model_config.json"
PROJECT_CONFIG_FILE = "dream_model_config.json"


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_model_config(project_dir: Path | None = None) -> dict[str, Any]:
    config: dict[str, Any] = {}
    if DEFAULT_CONFIG_FILE.exists():
        config = json.loads(DEFAULT_CONFIG_FILE.read_text(encoding="utf-8"))
    if project_dir:
        project_config = project_dir / PROJECT_CONFIG_FILE
        if project_config.exists():
            config = _deep_merge(config, json.loads(project_config.read_text(encoding="utf-8")))
    return config


def resolve_body_model(project_dir: Path) -> dict[str, Any]:
    config = load_model_config(project_dir)
    body = dict(config.get("body", {}))
    provider_name = body.get("provider") or body.get("backend") or "opencode"
    if provider_name != "opencode" and body.get("backend") == "opencode":
        # The skill default body.backend is opencode. A project-level provider
        # override such as {"provider": "deepseek"} should inherit the
        # provider backend instead of being pinned to the default backend.
        body.pop("backend", None)
    providers = config.get("providers", {})
    provider = dict(providers.get(provider_name, {}))
    resolved = _deep_merge(provider, body)
    resolved.setdefault("provider", provider_name)
    resolved.setdefault("backend", "opencode")
    resolved.setdefault("model", "current")
    resolved.setdefault("temperature", 0.8)
    resolved.setdefault("max_tokens", 6000)
    return resolved


def is_external_backend(model: dict[str, Any]) -> bool:
    return model.get("backend") in {"openai_compatible"}


def body_model_options(project_dir: Path | None = None) -> list[dict[str, str]]:
    config = load_model_config(project_dir)
    options = [
        {
            "label": "opencode/current",
            "description": "使用当前 opencode 会话模型生成正文",
        }
    ]
    for name, provider in sorted((config.get("providers") or {}).items()):
        model = provider.get("model", name)
        backend = provider.get("backend", "opencode")
        options.append({
            "label": f"{name}/{model}",
            "description": f"使用 {name} 的 {model} 生成正文（backend={backend}）",
        })
    return options


def apply_body_model_selection(project_dir: Path, label: str) -> dict[str, Any]:
    options = {option["label"] for option in body_model_options(project_dir)}
    if label not in options:
        raise ValueError(f"未知正文模型选项: {label}")
    project_config = project_dir / PROJECT_CONFIG_FILE
    payload = json.loads(project_config.read_text(encoding="utf-8")) if project_config.exists() else {}
    if label == "opencode/current":
        payload["body"] = {
            "backend": "opencode",
            "provider": "opencode",
            "model": "current",
            "temperature": payload.get("body", {}).get("temperature", 0.8),
            "max_tokens": payload.get("body", {}).get("max_tokens", 6000),
        }
    else:
        provider, model = label.split("/", 1)
        payload["body"] = {
            "provider": provider,
            "model": model,
            "temperature": payload.get("body", {}).get("temperature", 0.8),
            "max_tokens": payload.get("body", {}).get("max_tokens", 6000),
        }
    project_config.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return resolve_body_model(project_dir)
