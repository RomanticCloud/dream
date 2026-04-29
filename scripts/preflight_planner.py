#!/usr/bin/env python3
"""Build deterministic preflight plans before drafting chapters."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from common_io import save_json_file
from context_pack_builder import build_context_pack, context_pack_file


def preflight_file(project_dir: Path, vol: int, ch: int) -> Path:
    return project_dir / "context" / f"preflight_vol{vol:02d}_ch{ch:02d}.json"


def preflight_markdown_file(project_dir: Path, vol: int, ch: int) -> Path:
    return project_dir / "context" / f"preflight_vol{vol:02d}_ch{ch:02d}.md"


def build_preflight_plan(project_dir: Path, vol: int, ch: int, context_pack: dict | None = None) -> dict:
    if context_pack is None:
        context_pack = build_context_pack(project_dir, vol, ch)
    ledger = context_pack.get("ledger", {})
    constraints = ledger.get("open_constraints", {})
    current_state = ledger.get("current_state", {})
    chapter_plan = context_pack.get("chapter_plan") or {}
    volume_outline = context_pack.get("volume_outline") or {}
    open_foreshadowing = context_pack.get("open_foreshadowing", [])
    plan = {
        "preflight_id": f"preflight-v1-vol{vol:02d}-ch{ch:02d}",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "context_id": context_pack.get("context_id"),
        "current_chapter": {"vol": vol, "ch": ch},
        "opening_must_continue": {
            "location": current_state.get("location", ""),
            "emotion": current_state.get("emotion", ""),
            "goal": current_state.get("goal", ""),
            "hook": constraints.get("strongest_hook", ""),
            "previous_tail": context_pack.get("previous_anchor", {}).get("body_tail", ""),
        },
        "main_progress": chapter_plan.get("core_event") or chapter_plan.get("description") or volume_outline.get("卷目标", "推进当前卷主线"),
        "must_handle": [item for item in [constraints.get("must_handle"), constraints.get("need_payoff")] if item],
        "must_not_break": [item for item in [constraints.get("must_not_forget"), *context_pack.get("hard_facts", [])] if item],
        "foreshadowing_to_consider": open_foreshadowing[-5:],
        "allowed_new_setup": chapter_plan.get("new_setup") or constraints.get("new_setup", ""),
        "ending_target": {
            "serve_volume_goal": volume_outline.get("卷目标", ""),
            "leave_next_actionable_hook": True,
            "do_not_resolve": constraints.get("must_not_forget", ""),
        },
        "blocking_items": [
            "开场必须承接上一章结尾状态，不得重置场景",
            "正文不得违背连续性账本中的禁止事实",
            "必须处理上一章承上启下卡中的 blocking 承接项",
            "工作卡必须只记录正文中实际发生的状态变化",
        ],
    }
    save_json_file(preflight_file(project_dir, vol, ch), plan)
    preflight_markdown_file(project_dir, vol, ch).write_text(render_preflight_markdown(plan), encoding="utf-8")
    return plan


def render_preflight_markdown(plan: dict) -> str:
    opening = plan.get("opening_must_continue", {})
    ending = plan.get("ending_target", {})
    lines = [
        "# 生成前预检计划",
        "",
        f"- preflight_id：{plan.get('preflight_id')}",
        f"- context_id：{plan.get('context_id')}",
        "",
        "## 开场必须承接",
        f"- 地点：{opening.get('location', '')}",
        f"- 情绪：{opening.get('emotion', '')}",
        f"- 目标：{opening.get('goal', '')}",
        f"- 钩子：{opening.get('hook', '')}",
        "",
        "## 本章主推进",
        str(plan.get("main_progress") or "推进当前主线"),
        "",
        "## 必须处理",
    ]
    lines.extend([f"- {item}" for item in plan.get("must_handle", [])] or ["- 无"])
    lines.extend(["", "## 禁止违背"])
    lines.extend([f"- {item}" for item in plan.get("must_not_break", [])] or ["- 无"])
    lines.extend(["", "## 待考虑伏笔"])
    lines.extend([f"- {item.get('content', '')}（{item.get('source_chapter', '')}）" for item in plan.get("foreshadowing_to_consider", [])] or ["- 无"])
    lines.extend(["", "## 结尾目标"])
    lines.extend([f"- 服务卷目标：{ending.get('serve_volume_goal', '')}", "- 必须留下可执行下一章钩子"])
    lines.extend(["", "## 阻塞项"])
    lines.extend([f"- {item}" for item in plan.get("blocking_items", [])])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="构建生成前预检计划")
    parser.add_argument("project_dir")
    parser.add_argument("vol", type=int)
    parser.add_argument("ch", type=int)
    args = parser.parse_args()
    project_dir = Path(args.project_dir).expanduser().resolve()
    pack = json.loads(context_pack_file(project_dir, args.vol, args.ch).read_text(encoding="utf-8")) if context_pack_file(project_dir, args.vol, args.ch).exists() else None
    payload = build_preflight_plan(project_dir, args.vol, args.ch, pack)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
