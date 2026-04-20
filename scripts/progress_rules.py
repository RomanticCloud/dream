#!/usr/bin/env python3
"""Unified progress calculation helpers."""

from __future__ import annotations

from pathlib import Path

from chapter_scan import latest_chapter
from common_io import load_project_state


def get_chapters_per_volume(project_dir: Path) -> int:
    state = load_project_state(project_dir)
    return state.get("volume_architecture", {}).get("chapters_per_volume", 10)


def get_current_progress(project_dir: Path) -> tuple[int, int]:
    vol_num, ch_num, _ = latest_chapter(project_dir)
    if vol_num == 0:
        return 1, 0
    return vol_num, ch_num


def is_volume_boundary(project_dir: Path) -> bool:
    current_vol, current_ch = get_current_progress(project_dir)
    return current_ch > 0 and current_ch >= get_chapters_per_volume(project_dir)


def get_next_chapter(project_dir: Path) -> tuple[int, int, str]:
    current_vol, current_ch = get_current_progress(project_dir)
    chapters_per_volume = get_chapters_per_volume(project_dir)
    if current_ch == 0:
        return 1, 1, "vol01"
    if current_ch >= chapters_per_volume:
        return current_vol + 1, 1, f"vol{current_vol + 1:02d}"
    return current_vol, current_ch + 1, f"vol{current_vol:02d}"
