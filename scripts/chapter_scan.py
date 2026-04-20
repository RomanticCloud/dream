#!/usr/bin/env python3
"""Unified chapter scanning helpers."""

from __future__ import annotations

import re
from pathlib import Path


def is_non_chapter_markdown(file_path: Path) -> bool:
    stem = file_path.stem.lower()
    return any(token in stem for token in ["draft_prompt", "regen_prompt", "polish_prompt", "prompt", "提示"])


def parse_chapter_number(file_path: Path) -> int | None:
    match = re.match(r"^(\d+)", file_path.stem)
    if not match:
        return None
    return int(match.group(1))


def iter_chapter_files(project_dir: Path) -> list[tuple[int, int, Path]]:
    chapters_dir = project_dir / "chapters"
    if not chapters_dir.exists():
        return []

    results: list[tuple[int, int, Path]] = []
    for vol_dir in sorted(chapters_dir.iterdir()):
        if not vol_dir.is_dir() or not vol_dir.name.startswith("vol"):
            continue
        vol_num = int(vol_dir.name[3:])
        for file_path in sorted(vol_dir.glob("*.md")):
            if is_non_chapter_markdown(file_path):
                continue
            ch_num = parse_chapter_number(file_path)
            if ch_num is None:
                continue
            results.append((vol_num, ch_num, file_path))
    return results


def latest_chapter(project_dir: Path) -> tuple[int, int, Path | None]:
    chapters = iter_chapter_files(project_dir)
    if not chapters:
        return 0, 0, None
    vol_num, ch_num, file_path = max(chapters, key=lambda item: (item[0], item[1]))
    return vol_num, ch_num, file_path


def chapter_files_in_volume(project_dir: Path, vol_num: int) -> list[tuple[int, Path]]:
    return [
        (chapter_num, file_path)
        for volume_num, chapter_num, file_path in iter_chapter_files(project_dir)
        if volume_num == vol_num
    ]


def chapter_file_by_number(project_dir: Path, vol_num: int, ch_num: int) -> Path | None:
    for volume_num, chapter_num, file_path in iter_chapter_files(project_dir):
        if volume_num == vol_num and chapter_num == ch_num:
            return file_path
    return None
