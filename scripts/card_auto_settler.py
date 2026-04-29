#!/usr/bin/env python3
"""Deterministic work-card settlement from extracted chapter facts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from chapter_fact_extractor import extract_facts_from_file
from common_io import save_json_file
from continuity_ledger import load_ledger
from path_rules import chapter_card_file


def generate_card_text(project_dir: Path, vol: int, ch: int) -> str:
    facts = extract_facts_from_file(project_dir, vol, ch)
    ledger = load_ledger(project_dir)
    state = ledger.get("current_state", {})
    constraints = ledger.get("open_constraints", {})
    location = facts.get("actual_location_end") or facts.get("actual_location_start") or state.get("location") or "当前场景"
    goal = facts.get("actual_goal") or state.get("goal") or "推进当前主线"
    event = facts.get("actual_main_event") or "推进当前主线"
    hook = facts.get("actual_ending_hook") or constraints.get("strongest_hook") or "下一步行动尚未完成"
    key_terms = facts.get("actual_key_terms", [])
    payoff = "、".join(facts.get("actual_payoffs", [])[:3]) or constraints.get("need_payoff") or "无"
    setup = "、".join(key_terms[-3:]) or hook
    elapsed = "1小时"
    timepoint = _next_timepoint(ch)
    return f"""## 内部工作卡

### 1. 状态卡
- 主角当前位置：{location}
- 主角当前伤势/疲劳：{state.get('injury') or '疲惫但可行动'}
- 主角当前情绪：警惕
- 主角当前目标：{goal}
- 本章结束后的状态变化：{facts.get('actual_state_change') or event}
- 本章时间流逝：{elapsed}
- 本章结束时时间点：{timepoint}

### 2. 情节卡
- 核心冲突：{goal}
- 关键事件：{event}
- 转折点：{hook}
- 新埋伏笔：{setup}
- 回收伏笔：{payoff}

### 3. 资源卡
- 获得：+1线索
- 消耗：-1小时
- 损失：无
- 需带到下章的状态：{hook}
- 伏笔：{setup}

### 4. 关系卡
- 主要人物：{_guess_people(facts)}
- 人物变化：主角对核心谜团的认知推进

### 5. 情绪弧线卡
- 起始情绪：警惕
- 变化过程：警惕转为确认，再转为继续追查
- 目标情绪：决意
- 悬念强度：8

### 6. 承上启下卡
- 下章必须接住什么：{hook}
- 下章不能忘什么限制：{facts.get('ending_excerpt') or hook}
- 需要回收的伏笔：{setup}
- 新埋下的伏笔：{setup}
- 本章留下的最强钩子是什么：{hook}
"""


def _next_timepoint(ch: int) -> str:
    mapping = {1: "第1天深夜", 2: "第2天早晨", 3: "第2天上午", 4: "第2天下午"}
    return mapping.get(ch, f"第{max(1, ch)}天上午")


def _guess_people(facts: dict) -> str:
    text = " ".join([facts.get("opening_excerpt", ""), facts.get("ending_excerpt", "")])
    people = []
    for name in ["沈砚", "林婉清", "沈鹤鸣", "沈泊远", "陈叔"]:
        if name in text:
            people.append(name)
    return "、".join(people or ["沈砚"])


def write_auto_card(project_dir: Path, vol: int, ch: int) -> Path:
    card_path = chapter_card_file(project_dir, vol, ch)
    card_path.parent.mkdir(parents=True, exist_ok=True)
    card_path.write_text(generate_card_text(project_dir, vol, ch), encoding="utf-8")
    return card_path


def main() -> int:
    parser = argparse.ArgumentParser(description="从正文事实自动生成工作卡")
    parser.add_argument("project_dir")
    parser.add_argument("vol", type=int)
    parser.add_argument("ch", type=int)
    args = parser.parse_args()
    path = write_auto_card(Path(args.project_dir).expanduser().resolve(), args.vol, args.ch)
    print(json.dumps({"status": "success", "card_file": str(path)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
