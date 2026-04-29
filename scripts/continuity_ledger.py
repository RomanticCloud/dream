#!/usr/bin/env python3
"""Continuity ledger for fast chapter generation.

The ledger is the authoritative compact state used by the default writing
flow. It is intentionally derived from work cards first and prose second so
that chapter generation does not need to reread every prior chapter.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from card_fields import (
    FIELD_CARRY_HOOK,
    FIELD_CARRY_LIMIT,
    FIELD_CARRY_MUST,
    FIELD_CARRY_PAYOFF,
    FIELD_CARRY_SETUP,
    FIELD_EMOTION_PROCESS,
    FIELD_EMOTION_SUSPENSE,
    FIELD_EMOTION_START,
    FIELD_EMOTION_TARGET,
    FIELD_PLOT_CONFLICT,
    FIELD_PLOT_EVENT,
    FIELD_PLOT_PAYOFF,
    FIELD_PLOT_SETUP,
    FIELD_PLOT_TURN,
    FIELD_POWER_AFTER_EFFECT,
    FIELD_POWER_LEVEL,
    FIELD_POWER_LOSS_RATIO,
    FIELD_POWER_NEW_TRUMP,
    FIELD_POWER_TARGET,
    FIELD_POWER_TRUMP_NAME,
    FIELD_RESOURCE_CARRY,
    FIELD_RESOURCE_GAIN,
    FIELD_RESOURCE_LOSS,
    FIELD_RESOURCE_SETUP,
    FIELD_RESOURCE_SPEND,
    FIELD_STATUS_CHANGE,
    FIELD_STATUS_ELAPSED,
    FIELD_STATUS_EMOTION,
    FIELD_STATUS_GOAL,
    FIELD_STATUS_INJURY,
    FIELD_STATUS_LOCATION,
    FIELD_STATUS_REALM,
    FIELD_STATUS_TIMEPOINT,
)
from card_names import CARRY_CARD, EMOTION_CARD, PLOT_CARD, POWER_CARD, RESOURCE_CARD, STATUS_CARD
from chapter_scan import iter_chapter_files
from chapter_view import load_chapter_view
from common_io import extract_body, extract_bullets, extract_section, load_json_file, save_json_file
from path_rules import chapter_card_file


LEDGER_JSON = "CONTINUITY_LEDGER.json"
LEDGER_MD = "CONTINUITY_LEDGER.md"


def ledger_file(project_dir: Path) -> Path:
    return project_dir / "context" / LEDGER_JSON


def ledger_markdown_file(project_dir: Path) -> Path:
    return project_dir / "context" / LEDGER_MD


def default_ledger() -> dict[str, Any]:
    return {
        "version": 1,
        "updated_at": None,
        "last_applied": None,
        "applied_chapters": [],
        "current_state": {
            "location": "",
            "injury": "",
            "emotion": "",
            "goal": "",
            "state_change": "",
            "realm": "",
        },
        "timeline": {
            "current_timepoint": "",
            "last_elapsed": "",
            "chapters": [],
            "warnings": [],
        },
        "resources": {
            "last_gain": "",
            "last_spend": "",
            "last_loss": "",
            "carry_state": "",
            "inventory_hint": {},
        },
        "abilities": {
            "realm": "",
            "last_opponent": "",
            "last_opponent_level": "",
            "last_loss_ratio": "",
            "trump_cards": [],
            "after_effect": "",
        },
        "characters": {},
        "relationships": [],
        "plot_threads": [],
        "foreshadowing": [],
        "hard_facts": [],
        "open_constraints": {
            "must_handle": "",
            "must_not_forget": "",
            "need_payoff": "",
            "new_setup": "",
            "strongest_hook": "",
        },
        "recent_chapters": [],
    }


def load_ledger(project_dir: Path) -> dict[str, Any]:
    payload = load_json_file(ledger_file(project_dir), default={})
    if not payload:
        return default_ledger()
    ledger = default_ledger()
    ledger.update(payload)
    for key, value in default_ledger().items():
        ledger.setdefault(key, value)
    return ledger


def save_ledger(project_dir: Path, ledger: dict[str, Any]) -> None:
    ledger["updated_at"] = datetime.now().isoformat(timespec="seconds")
    save_json_file(ledger_file(project_dir), ledger)
    ledger_markdown_file(project_dir).write_text(render_ledger_markdown(ledger), encoding="utf-8")


def _chapter_id(vol: int, ch: int) -> str:
    return f"vol{vol:02d}/ch{ch:02d}"


def _split_people(text: str) -> list[str]:
    if not text:
        return []
    for sep in ["、", "，", ",", "/"]:
        text = text.replace(sep, "、")
    return [part.strip() for part in text.split("、") if part.strip()]


def _add_foreshadowing(ledger: dict[str, Any], content: str, chapter_id: str, source: str) -> None:
    if not content or content in {"无", "-0", "暂无"}:
        return
    existing = {(item.get("content"), item.get("status")) for item in ledger["foreshadowing"]}
    item_key = (content, "open")
    if item_key in existing:
        return
    ledger["foreshadowing"].append({
        "content": content,
        "status": "open",
        "source_chapter": chapter_id,
        "source": source,
    })


def _mark_payoff(ledger: dict[str, Any], content: str, chapter_id: str) -> None:
    if not content or content in {"无", "-0", "暂无"}:
        return
    matched = False
    for item in ledger["foreshadowing"]:
        if item.get("status") != "open":
            continue
        old = item.get("content", "")
        if old and (old in content or content in old):
            item["status"] = "resolved"
            item["resolved_chapter"] = chapter_id
            matched = True
            break
    if not matched:
        ledger["foreshadowing"].append({
            "content": content,
            "status": "resolved_unmatched",
            "source_chapter": chapter_id,
            "source": "plot_payoff",
        })


def extract_chapter_ledger_delta(project_dir: Path, vol: int, ch: int) -> dict[str, Any]:
    view = load_chapter_view(project_dir, vol, ch)
    content = view.merged_text
    body = extract_body(content)
    status = extract_bullets(extract_section(content, STATUS_CARD))
    plot = extract_bullets(extract_section(content, PLOT_CARD))
    power = extract_bullets(extract_section(content, POWER_CARD))
    resource = extract_bullets(extract_section(content, RESOURCE_CARD))
    emotion = extract_bullets(extract_section(content, EMOTION_CARD))
    carry = extract_bullets(extract_section(content, CARRY_CARD))

    relation = extract_bullets(extract_section(content, "### 4. 关系卡"))
    body_tail = body[-500:].strip() if body else ""
    chapter_id = _chapter_id(vol, ch)
    return {
        "chapter_id": chapter_id,
        "vol": vol,
        "ch": ch,
        "title": _first_heading(content) or f"第{ch}章",
        "body_tail": body_tail,
        "status": status,
        "plot": plot,
        "power": power,
        "resource": resource,
        "relation": relation,
        "emotion": emotion,
        "carry": carry,
    }


def _first_heading(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def apply_chapter_delta(ledger: dict[str, Any], delta: dict[str, Any]) -> dict[str, Any]:
    chapter_id = delta["chapter_id"]
    if chapter_id in ledger.get("applied_chapters", []):
        return ledger

    status = delta.get("status", {})
    plot = delta.get("plot", {})
    power = delta.get("power", {})
    resource = delta.get("resource", {})
    relation = delta.get("relation", {})
    emotion = delta.get("emotion", {})
    carry = delta.get("carry", {})

    ledger["current_state"].update({
        "location": status.get(FIELD_STATUS_LOCATION, ledger["current_state"].get("location", "")),
        "injury": status.get(FIELD_STATUS_INJURY, ledger["current_state"].get("injury", "")),
        "emotion": status.get(FIELD_STATUS_EMOTION, ledger["current_state"].get("emotion", "")),
        "goal": status.get(FIELD_STATUS_GOAL, ledger["current_state"].get("goal", "")),
        "state_change": status.get(FIELD_STATUS_CHANGE, ""),
        "realm": status.get(FIELD_STATUS_REALM, ledger["current_state"].get("realm", "")),
    })
    ledger["timeline"].update({
        "current_timepoint": status.get(FIELD_STATUS_TIMEPOINT, ledger["timeline"].get("current_timepoint", "")),
        "last_elapsed": status.get(FIELD_STATUS_ELAPSED, ""),
    })
    ledger["timeline"].setdefault("chapters", []).append({
        "chapter": chapter_id,
        "elapsed": status.get(FIELD_STATUS_ELAPSED, ""),
        "timepoint": status.get(FIELD_STATUS_TIMEPOINT, ""),
    })

    ledger["resources"].update({
        "last_gain": resource.get(FIELD_RESOURCE_GAIN, ""),
        "last_spend": resource.get(FIELD_RESOURCE_SPEND, ""),
        "last_loss": resource.get(FIELD_RESOURCE_LOSS, ""),
        "carry_state": resource.get(FIELD_RESOURCE_CARRY, ""),
    })
    if resource.get(FIELD_RESOURCE_SETUP):
        _add_foreshadowing(ledger, resource[FIELD_RESOURCE_SETUP], chapter_id, "resource_setup")

    if power:
        trumps = _split_people(power.get(FIELD_POWER_TRUMP_NAME, ""))
        known_trumps = list(dict.fromkeys([*ledger["abilities"].get("trump_cards", []), *trumps]))
        ledger["abilities"].update({
            "realm": status.get(FIELD_STATUS_REALM, ledger["abilities"].get("realm", "")),
            "last_opponent": power.get(FIELD_POWER_TARGET, ""),
            "last_opponent_level": power.get(FIELD_POWER_LEVEL, ""),
            "last_loss_ratio": power.get(FIELD_POWER_LOSS_RATIO, ""),
            "trump_cards": known_trumps,
            "after_effect": power.get(FIELD_POWER_AFTER_EFFECT, ""),
            "last_new_trump": power.get(FIELD_POWER_NEW_TRUMP, ""),
        })

    if relation:
        people = _split_people(relation.get("主要人物", ""))
        change = relation.get("人物变化", "")
        for name in people:
            entry = ledger["characters"].setdefault(name, {"latest": {}, "history": []})
            entry["latest"] = {"chapter": chapter_id, "relation_change": change}
            entry["history"].append({"chapter": chapter_id, "relation_change": change})
        if change:
            ledger["relationships"].append({"chapter": chapter_id, "people": people, "change": change})

    plot_item = {
        "chapter": chapter_id,
        "conflict": plot.get(FIELD_PLOT_CONFLICT, ""),
        "event": plot.get(FIELD_PLOT_EVENT, ""),
        "turn": plot.get(FIELD_PLOT_TURN, ""),
        "emotion": {
            "start": emotion.get(FIELD_EMOTION_START, ""),
            "process": emotion.get(FIELD_EMOTION_PROCESS, ""),
            "target": emotion.get(FIELD_EMOTION_TARGET, ""),
            "suspense": emotion.get(FIELD_EMOTION_SUSPENSE, ""),
        },
    }
    ledger["plot_threads"].append(plot_item)
    ledger["plot_threads"] = ledger["plot_threads"][-20:]

    _add_foreshadowing(ledger, plot.get(FIELD_PLOT_SETUP, ""), chapter_id, "plot_setup")
    _mark_payoff(ledger, plot.get(FIELD_PLOT_PAYOFF, ""), chapter_id)

    ledger["open_constraints"] = {
        "must_handle": carry.get(FIELD_CARRY_MUST, ""),
        "must_not_forget": carry.get(FIELD_CARRY_LIMIT, ""),
        "need_payoff": carry.get(FIELD_CARRY_PAYOFF, ""),
        "new_setup": carry.get(FIELD_CARRY_SETUP, ""),
        "strongest_hook": carry.get(FIELD_CARRY_HOOK, ""),
    }

    hard_candidates = [
        status.get(FIELD_STATUS_CHANGE, ""),
        resource.get(FIELD_RESOURCE_CARRY, ""),
        carry.get(FIELD_CARRY_LIMIT, ""),
    ]
    for fact in hard_candidates:
        if fact and fact not in ledger["hard_facts"]:
            ledger["hard_facts"].append(fact)
    ledger["hard_facts"] = ledger["hard_facts"][-30:]

    ledger["recent_chapters"].append({
        "chapter": chapter_id,
        "title": delta.get("title", ""),
        "event": plot.get(FIELD_PLOT_EVENT, ""),
        "turn": plot.get(FIELD_PLOT_TURN, ""),
        "hook": carry.get(FIELD_CARRY_HOOK, ""),
        "ending_anchor": delta.get("body_tail", ""),
    })
    ledger["recent_chapters"] = ledger["recent_chapters"][-8:]
    ledger.setdefault("applied_chapters", []).append(chapter_id)
    ledger["last_applied"] = chapter_id
    return ledger


def update_ledger_for_chapter(project_dir: Path, vol: int, ch: int) -> dict[str, Any]:
    ledger = load_ledger(project_dir)
    delta = extract_chapter_ledger_delta(project_dir, vol, ch)
    apply_chapter_delta(ledger, delta)
    save_ledger(project_dir, ledger)
    return ledger


def rebuild_ledger(project_dir: Path) -> dict[str, Any]:
    ledger = default_ledger()
    for vol, ch, _ in iter_chapter_files(project_dir):
        card_path = chapter_card_file(project_dir, vol, ch)
        if not card_path.exists():
            continue
        delta = extract_chapter_ledger_delta(project_dir, vol, ch)
        apply_chapter_delta(ledger, delta)
    save_ledger(project_dir, ledger)
    return ledger


def render_ledger_markdown(ledger: dict[str, Any]) -> str:
    state = ledger.get("current_state", {})
    timeline = ledger.get("timeline", {})
    constraints = ledger.get("open_constraints", {})
    open_foreshadowing = [item for item in ledger.get("foreshadowing", []) if item.get("status") == "open"][-10:]
    recent = ledger.get("recent_chapters", [])[-5:]
    lines = [
        "# 连续性账本",
        "",
        f"- 更新时间：{ledger.get('updated_at') or ''}",
        f"- 最近应用章节：{ledger.get('last_applied') or ''}",
        "",
        "## 当前状态",
        f"- 位置：{state.get('location', '')}",
        f"- 伤势/疲劳：{state.get('injury', '')}",
        f"- 情绪：{state.get('emotion', '')}",
        f"- 目标：{state.get('goal', '')}",
        f"- 境界/能力：{state.get('realm', '')}",
        f"- 当前时间：{timeline.get('current_timepoint', '')}",
        "",
        "## 下一章约束",
        f"- 必须接住：{constraints.get('must_handle', '')}",
        f"- 不能忘：{constraints.get('must_not_forget', '')}",
        f"- 需要回收：{constraints.get('need_payoff', '')}",
        f"- 新伏笔：{constraints.get('new_setup', '')}",
        f"- 最强钩子：{constraints.get('strongest_hook', '')}",
        "",
        "## 待回收伏笔",
    ]
    lines.extend([f"- {item.get('content', '')}（{item.get('source_chapter', '')}）" for item in open_foreshadowing] or ["- 无"])
    lines.extend(["", "## 最近章节"])
    lines.extend([f"- {item.get('chapter', '')}：{item.get('event', '')}；钩子：{item.get('hook', '')}" for item in recent] or ["- 无"])
    lines.extend(["", "## 禁止违背事实"])
    lines.extend([f"- {item}" for item in ledger.get("hard_facts", [])[-10:]] or ["- 无"])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="连续性账本维护")
    parser.add_argument("project_dir")
    parser.add_argument("command", choices=["rebuild", "update", "show"])
    parser.add_argument("--vol", type=int)
    parser.add_argument("--ch", type=int)
    args = parser.parse_args()
    project_dir = Path(args.project_dir).expanduser().resolve()
    if args.command == "rebuild":
        payload = rebuild_ledger(project_dir)
    elif args.command == "update":
        if args.vol is None or args.ch is None:
            parser.error("update 需要 --vol 和 --ch")
        payload = update_ledger_for_chapter(project_dir, args.vol, args.ch)
    else:
        payload = load_ledger(project_dir)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
