#!/usr/bin/env python3
"""Build compact generation context packages for chapter drafting."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from chapter_plan_loader import get_chapter_plan, format_chapter_plan_for_prompt
from chapter_view import load_chapter_view
from common_io import load_project_state, load_volume_outline, save_json_file
from continuity_ledger import ledger_file, ledger_markdown_file, load_ledger, rebuild_ledger
from plan_deviation_router import load_accepted_deviations
from path_rules import chapter_card_file, chapter_file


def context_pack_file(project_dir: Path, vol: int, ch: int) -> Path:
    return project_dir / "context" / f"generation_context_vol{vol:02d}_ch{ch:02d}.json"


def context_pack_markdown_file(project_dir: Path, vol: int, ch: int) -> Path:
    return project_dir / "context" / f"generation_context_vol{vol:02d}_ch{ch:02d}.md"


def _previous_chapter(vol: int, ch: int) -> tuple[int, int] | None:
    if ch > 1:
        return vol, ch - 1
    if vol > 1:
        return vol - 1, 9999
    return None


def _load_previous_anchor(project_dir: Path, vol: int, ch: int) -> dict[str, str]:
    if ch <= 1:
        return {}
    prev_vol, prev_ch = vol, ch - 1
    view = load_chapter_view(project_dir, prev_vol, prev_ch)
    if not view.chapter_path.exists():
        return {}
    body = view.raw_body_file or view.merged_text
    tail = body[-800:].strip()
    card = view.raw_card_file if view.has_separate_card else ""
    return {
        "chapter": f"vol{prev_vol:02d}/ch{prev_ch:02d}",
        "body_tail": tail,
        "card_path": str(chapter_card_file(project_dir, prev_vol, prev_ch)) if card else "",
        "card_text": card[-2500:] if card else "",
    }


def _load_focused_chapters(project_dir: Path, ledger: dict[str, Any], limit: int = 3) -> list[str]:
    paths: list[str] = []
    for item in ledger.get("foreshadowing", []):
        if item.get("status") != "open":
            continue
        chapter = item.get("source_chapter", "")
        if not chapter.startswith("vol") or "/ch" not in chapter:
            continue
        try:
            vol = int(chapter[3:5])
            ch = int(chapter.split("/ch", 1)[1])
        except ValueError:
            continue
        path = chapter_file(project_dir, vol, ch)
        if path.exists() and str(path) not in paths:
            paths.append(str(path))
        if len(paths) >= limit:
            break
    return paths


def build_context_pack(project_dir: Path, vol: int, ch: int, mode: str = "fast") -> dict[str, Any]:
    state = load_project_state(project_dir)
    ledger = load_ledger(project_dir)
    if not ledger.get("applied_chapters") and (project_dir / "chapters").exists():
        ledger = rebuild_ledger(project_dir)
    chapter_plan = get_chapter_plan(project_dir, vol, ch)
    chapter_plan_text = format_chapter_plan_for_prompt(chapter_plan) if chapter_plan else ""
    volume_outline = load_volume_outline(project_dir, vol)
    previous_anchor = _load_previous_anchor(project_dir, vol, ch)
    accepted_deviations = load_accepted_deviations(project_dir)
    focused_paths = _load_focused_chapters(project_dir, ledger) if mode in {"focused", "full"} else []

    context_id = f"generation-context-v2-{mode}-vol{vol:02d}-ch{ch:02d}"
    payload = {
        "context_id": context_id,
        "mode": mode,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "project_dir": str(project_dir),
        "current_chapter": {"vol": vol, "ch": ch},
        "project": {
            "book_title": state.get("naming", {}).get("selected_book_title", state.get("naming", {}).get("book_title", "未命名")),
            "genres": state.get("basic_specs", {}).get("main_genres", state.get("basic_specs", {}).get("genres", [])),
            "style_tone": state.get("basic_specs", {}).get("style_tone", ""),
            "narrative_style": state.get("positioning", {}).get("narrative_style", ""),
        },
        "chapter_plan": chapter_plan,
        "chapter_plan_text": chapter_plan_text,
        "volume_outline": volume_outline,
        "ledger": ledger,
        "previous_anchor": previous_anchor,
        "recent_chapters": ledger.get("recent_chapters", [])[-5:],
        "open_foreshadowing": [item for item in ledger.get("foreshadowing", []) if item.get("status") == "open"][-10:],
        "hard_facts": ledger.get("hard_facts", [])[-20:],
        "accepted_deviations": accepted_deviations,
        "required_context_files": [
            str(context_pack_markdown_file(project_dir, vol, ch)),
            str(ledger_file(project_dir)),
            str(ledger_markdown_file(project_dir)),
        ],
        "focused_read_files": focused_paths,
    }
    save_json_file(context_pack_file(project_dir, vol, ch), payload)
    context_pack_markdown_file(project_dir, vol, ch).write_text(render_context_markdown(payload), encoding="utf-8")
    return payload


def render_context_markdown(payload: dict[str, Any]) -> str:
    project = payload.get("project", {})
    ledger = payload.get("ledger", {})
    state = ledger.get("current_state", {})
    constraints = ledger.get("open_constraints", {})
    lines = [
        "# 生成上下文包",
        "",
        f"- context_id：{payload.get('context_id')}",
        f"- 模式：{payload.get('mode')}",
        f"- 书名：{project.get('book_title', '')}",
        f"- 题材：{'、'.join(project.get('genres') or [])}",
        f"- 文风：{project.get('style_tone', '')}",
        f"- 叙事视角：{project.get('narrative_style', '')}",
        "",
        "## 当前章规划",
        payload.get("chapter_plan_text") or "- 无",
        "",
        "## 当前卷约束",
    ]
    outline = payload.get("volume_outline") or {}
    if outline:
        lines.extend([f"- {key}：{value}" for key, value in outline.items()])
    else:
        lines.append("- 无")
    lines.extend([
        "",
        "## 权威连续性状态",
        f"- 位置：{state.get('location', '')}",
        f"- 伤势/疲劳：{state.get('injury', '')}",
        f"- 情绪：{state.get('emotion', '')}",
        f"- 目标：{state.get('goal', '')}",
        f"- 当前时间：{ledger.get('timeline', {}).get('current_timepoint', '')}",
        "",
        "## 下一章必须承接",
        f"- 必须接住：{constraints.get('must_handle', '')}",
        f"- 不能忘：{constraints.get('must_not_forget', '')}",
        f"- 需要回收：{constraints.get('need_payoff', '')}",
        f"- 最强钩子：{constraints.get('strongest_hook', '')}",
        "",
        "## 上一章结尾锚点",
        payload.get("previous_anchor", {}).get("body_tail", "无"),
        "",
        "## 最近主线",
    ])
    recent = payload.get("recent_chapters") or []
    lines.extend([f"- {item.get('chapter', '')}：{item.get('event', '')}；钩子：{item.get('hook', '')}" for item in recent] or ["- 无"])
    lines.extend(["", "## 待回收伏笔"])
    lines.extend([f"- {item.get('content', '')}（{item.get('source_chapter', '')}）" for item in payload.get("open_foreshadowing", [])] or ["- 无"])
    lines.extend(["", "## 禁止违背事实"])
    lines.extend([f"- {item}" for item in payload.get("hard_facts", [])] or ["- 无"])
    deviations = payload.get("accepted_deviations", {})
    if deviations.get("aliases") or deviations.get("facts"):
        lines.extend(["", "## 已接受正文偏移"])
        lines.extend([f"- 术语：{item.get('from')} => {item.get('to')}（{item.get('chapter', '')}）" for item in deviations.get("aliases", [])] or [])
        lines.extend([f"- 事实：{item.get('fact')}（{item.get('chapter', '')}）" for item in deviations.get("facts", [])[-8:]] or [])
    if payload.get("focused_read_files"):
        lines.extend(["", "## 需要聚焦读取的历史文件"])
        lines.extend([f"- {path}" for path in payload["focused_read_files"]])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="构建轻量生成上下文包")
    parser.add_argument("project_dir")
    parser.add_argument("vol", type=int)
    parser.add_argument("ch", type=int)
    parser.add_argument("--mode", choices=["fast", "focused", "full"], default="fast")
    args = parser.parse_args()
    payload = build_context_pack(Path(args.project_dir).expanduser().resolve(), args.vol, args.ch, args.mode)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
