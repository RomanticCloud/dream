#!/usr/bin/env python3
"""Common state and reference IO helpers for dream scripts."""

from __future__ import annotations

import json
from pathlib import Path


def load_project_state(project_dir: Path) -> dict:
    state_file = project_dir / "wizard_state.json"
    if state_file.exists():
        return json.loads(state_file.read_text(encoding="utf-8"))

    config_file = project_dir / ".project_config.json"
    if config_file.exists():
        return json.loads(config_file.read_text(encoding="utf-8"))

    return {}


def save_project_state(project_dir: Path, state: dict) -> None:
    state_file = project_dir / "wizard_state.json"
    state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def load_volume_outline(project_dir: Path, volume_index: int) -> dict:
    outline_path = project_dir / "reference" / "卷纲总表.md"
    if not outline_path.exists():
        return {}

    text = outline_path.read_text(encoding="utf-8")
    import re

    pattern = rf"(^##\s+第{volume_index}卷.+?)(?=^##\s+|\Z)"
    match = re.search(pattern, text, re.M | re.S)
    if not match:
        return {}

    lines = [line.rstrip() for line in match.group(1).splitlines() if line.strip()]
    data = {"卷标题": lines[0].removeprefix("##").strip() if lines else ""}
    for line in lines[1:]:
        line = line.strip()
        if line.startswith("- ") and "：" in line:
            key, value = line[2:].split("：", 1)
            data[key.strip()] = value.strip()
    return data


def load_json_file(file_path: Path, default: dict | list | None = None):
    if not file_path.exists():
        return {} if default is None else default
    return json.loads(file_path.read_text(encoding="utf-8"))


def save_json_file(file_path: Path, payload: dict | list) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
