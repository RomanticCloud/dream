#!/usr/bin/env python3
"""Path helpers for dream scripts."""

from __future__ import annotations

from pathlib import Path


def volume_dir(project_dir: Path, vol_num: int) -> Path:
    return project_dir / "chapters" / f"vol{vol_num:02d}"


def chapter_file(project_dir: Path, vol_num: int, ch_num: int, title: str | None = None) -> Path:
    return volume_dir(project_dir, vol_num) / f"ch{ch_num:02d}.md"


def cards_dir(project_dir: Path, vol_num: int) -> Path:
    return volume_dir(project_dir, vol_num) / "cards"


def chapter_card_file(project_dir: Path, vol_num: int, ch_num: int) -> Path:
    return cards_dir(project_dir, vol_num) / f"ch{ch_num:02d}_card.md"


def draft_prompt_file(project_dir: Path, vol_num: int, ch_num: int) -> Path:
    return volume_dir(project_dir, vol_num) / f"{ch_num:03d}_draft_prompt.md"


def regen_prompt_file(project_dir: Path, vol_num: int, ch_num: int) -> Path:
    return volume_dir(project_dir, vol_num) / f"{ch_num:03d}_regen_prompt.md"


def polish_prompt_file(project_dir: Path, vol_num: int, ch_num: int) -> Path:
    return volume_dir(project_dir, vol_num) / f"{ch_num:03d}_polish_prompt.md"


def rewrite_card_prompt_file(project_dir: Path, vol_num: int, ch_num: int) -> Path:
    return volume_dir(project_dir, vol_num) / f"{ch_num:03d}_rewrite_card_prompt.md"


def volume_memory_dir(project_dir: Path) -> Path:
    return project_dir / "reference" / "卷沉淀"


def volume_memory_json(project_dir: Path, vol_num: int) -> Path:
    return volume_memory_dir(project_dir) / f"vol{vol_num:02d}_state.json"


def volume_memory_md(project_dir: Path, vol_num: int) -> Path:
    return volume_memory_dir(project_dir) / f"vol{vol_num:02d}_state.md"


def chapter_outline_file(project_dir: Path, vol_num: int) -> Path:
    return project_dir / "reference" / f"vol{vol_num:02d}_chapter_outline.md"


def project_running_memory_file(project_dir: Path) -> Path:
    return project_dir / "reference" / "PROJECT_RUNNING_MEMORY.md"
