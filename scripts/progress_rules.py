#!/usr/bin/env python3
"""Unified progress calculation helpers."""

from __future__ import annotations

from pathlib import Path

from chapter_scan import latest_chapter
from common_io import load_project_state


def get_chapters_per_volume(project_dir: Path) -> int:
    state = load_project_state(project_dir)
    # 尝试从 basic_specs 获取 chapters_per_volume
    if "basic_specs" in state and "chapters_per_volume" in state["basic_specs"]:
        return state["basic_specs"]["chapters_per_volume"]
    # 尝试从 volume_architecture 获取（如果它是字典）
    vol_arch = state.get("volume_architecture", {})
    if isinstance(vol_arch, dict):
        return vol_arch.get("chapters_per_volume", 10)
    # 默认值
    return 10


def get_current_progress(project_dir: Path) -> tuple[int, int]:
    """获取当前进度（使用索引缓存）"""
    try:
        from chapter_index import get_chapter_index
        index = get_chapter_index(project_dir)
        chapters = index.get("chapters", [])
        
        if not chapters:
            return 1, 0
        
        last = chapters[-1]
        return last["vol"], last["ch"]
    except Exception:
        # 回退到原有实现
        vol_num, ch_num, _ = latest_chapter(project_dir)
        if vol_num == 0:
            return 1, 0
        return vol_num, ch_num


def is_volume_boundary(project_dir: Path) -> bool:
    current_vol, current_ch = get_current_progress(project_dir)
    return current_ch > 0 and current_ch >= get_chapters_per_volume(project_dir)


def get_next_chapter(project_dir: Path) -> tuple[int, int, str]:
    """获取下一章（使用索引缓存）"""
    try:
        from chapter_index import get_chapter_index
        index = get_chapter_index(project_dir)
        chapters = index.get("chapters", [])
        chapters_per_volume = get_chapters_per_volume(project_dir)
        
        if not chapters:
            return 1, 1, "vol01"
        
        last = chapters[-1]
        current_vol, current_ch = last["vol"], last["ch"]
        
        if current_ch >= chapters_per_volume:
            return current_vol + 1, 1, f"vol{current_vol + 1:02d}"
        return current_vol, current_ch + 1, f"vol{current_vol:02d}"
    except Exception:
        # 回退到原有实现
        current_vol, current_ch = get_current_progress(project_dir)
        chapters_per_volume = get_chapters_per_volume(project_dir)
        if current_ch == 0:
            return 1, 1, "vol01"
        if current_ch >= chapters_per_volume:
            return current_vol + 1, 1, f"vol{current_vol + 1:02d}"
        return current_vol, current_ch + 1, f"vol{current_vol:02d}"
