#!/usr/bin/env python3
"""管理分离式生成的状态持久化"""

import json
from pathlib import Path
from typing import Any

GENERATION_STATE_FILE = "context/generation_state.json"


def load_generation_state(project_dir: Path) -> dict[str, Any]:
    """加载生成状态"""
    state_file = project_dir / GENERATION_STATE_FILE
    if state_file.exists():
        return json.loads(state_file.read_text(encoding="utf-8"))
    return {}


def save_generation_state(project_dir: Path, state: dict[str, Any]) -> None:
    """保存生成状态（完全替换）"""
    state_file = project_dir / GENERATION_STATE_FILE
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def update_generation_state(project_dir: Path, updates: dict[str, Any]) -> None:
    """更新生成状态（增量合并）"""
    state = load_generation_state(project_dir)
    state.update(updates)
    save_generation_state(project_dir, state)


def cleanup_generation_state(project_dir: Path) -> None:
    """清理生成状态（章节完成后）"""
    state_file = project_dir / GENERATION_STATE_FILE
    if state_file.exists():
        state_file.unlink()


def get_generation_phase(project_dir: Path) -> str | None:
    """获取当前生成阶段"""
    state = load_generation_state(project_dir)
    return state.get("phase")


def is_body_phase(project_dir: Path) -> bool:
    """是否处于正文生成阶段"""
    phase = get_generation_phase(project_dir)
    return phase in ("body_required", "body_ready")


def is_cards_phase(project_dir: Path) -> bool:
    """是否处于工作卡生成阶段"""
    phase = get_generation_phase(project_dir)
    return phase in ("cards_required", "cards_ready")
