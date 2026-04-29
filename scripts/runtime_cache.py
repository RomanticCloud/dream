#!/usr/bin/env python3
"""Runtime cache invalidation helpers."""

from __future__ import annotations

from pathlib import Path


def invalidate_runtime_cache(project_dir: Path, vol_num: int | None = None, ch_num: int | None = None, *, include_future: bool = True) -> None:
    context_dir = project_dir / "context"
    targets = [
        context_dir / "validation_cache.json",
        context_dir / "chapter_index.json",
    ]
    for target in targets:
        if target.exists():
            target.unlink()

    if vol_num is None or ch_num is None or not context_dir.exists():
        return

    prefixes = [
        "generation_context",
        "preflight",
        "body_prompt",
        "card_prompt",
        "chapter_facts",
    ]
    for file_path in context_dir.glob("*.json"):
        _maybe_unlink_context_file(file_path, prefixes, vol_num, ch_num, include_future)
    for file_path in context_dir.glob("*.md"):
        _maybe_unlink_context_file(file_path, prefixes, vol_num, ch_num, include_future)


def _maybe_unlink_context_file(file_path: Path, prefixes: list[str], vol_num: int, ch_num: int, include_future: bool) -> None:
    name = file_path.name
    if not any(name.startswith(prefix) for prefix in prefixes):
        return
    marker = f"vol{vol_num:02d}_ch"
    if marker not in name:
        return
    try:
        current_ch = int(name.split(marker, 1)[1][:2])
    except ValueError:
        return
    if current_ch == ch_num or (include_future and current_ch > ch_num):
        file_path.unlink()
