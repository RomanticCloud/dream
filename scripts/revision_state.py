#!/usr/bin/env python3
"""Revision state helpers for chapter and volume repair workflow."""

from __future__ import annotations

from pathlib import Path

from common_io import load_json_file, save_json_file


def revision_state_file(project_dir: Path) -> Path:
    return project_dir / "REVISION_STATE.json"


def load_revision_state(project_dir: Path) -> dict:
    return load_json_file(revision_state_file(project_dir), default={"chapter": {}, "volume": {}})


def save_revision_state(project_dir: Path, state: dict) -> None:
    save_json_file(revision_state_file(project_dir), state)


def chapter_key(vol_num: int, ch_num: int) -> str:
    return f"vol{vol_num:02d}_ch{ch_num:03d}"


def volume_key(vol_num: int) -> str:
    return f"vol{vol_num:02d}"


def set_chapter_revision(project_dir: Path, vol_num: int, ch_num: int, status: str, fix_plan: dict | None = None) -> dict:
    state = load_revision_state(project_dir)
    state.setdefault("chapter", {})[chapter_key(vol_num, ch_num)] = {
        "status": status,
        "fix_plan": fix_plan or {},
    }
    save_revision_state(project_dir, state)
    return state


def clear_chapter_revision(project_dir: Path, vol_num: int, ch_num: int) -> dict:
    state = load_revision_state(project_dir)
    state.setdefault("chapter", {}).pop(chapter_key(vol_num, ch_num), None)
    save_revision_state(project_dir, state)
    return state


def set_volume_revision(project_dir: Path, vol_num: int, status: str, fix_plan: dict | None = None, memory_enriched: bool = False) -> dict:
    state = load_revision_state(project_dir)
    state.setdefault("volume", {})[volume_key(vol_num)] = {
        "status": status,
        "fix_plan": fix_plan or {},
        "memory_enriched": memory_enriched,
    }
    save_revision_state(project_dir, state)
    return state


def update_volume_memory_state(project_dir: Path, vol_num: int, memory_enriched: bool = True) -> dict:
    state = load_revision_state(project_dir)
    payload = state.setdefault("volume", {}).setdefault(volume_key(vol_num), {"status": "passed", "fix_plan": {}, "memory_enriched": False})
    payload["memory_enriched"] = memory_enriched
    if payload.get("status") == "pending":
        payload["status"] = "passed"
    save_revision_state(project_dir, state)
    return state


def get_pending_chapter_revision(project_dir: Path) -> tuple[str, dict] | None:
    state = load_revision_state(project_dir)
    for key, payload in sorted(state.get("chapter", {}).items()):
        if payload.get("status") in {"pending_regenerate", "pending_polish"}:
            return key, payload
    return None


def get_volume_revision(project_dir: Path, vol_num: int) -> dict | None:
    state = load_revision_state(project_dir)
    return state.get("volume", {}).get(volume_key(vol_num))


def get_chapter_revision(project_dir: Path, vol_num: int, ch_num: int) -> dict | None:
    state = load_revision_state(project_dir)
    return state.get("chapter", {}).get(chapter_key(vol_num, ch_num))
