#!/usr/bin/env python3
"""卷沉淀器 - 从已完成卷中提炼动态设定与后文约束。"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

from card_names import CARRY_CARD, EMOTION_CARD, PLOT_CARD, RELATION_CARD, RESOURCE_CARD, STATUS_CARD
from card_fields import (
    FIELD_CARRY_MUST,
    FIELD_CARRY_SETUP,
    FIELD_EMOTION_TARGET,
    FIELD_PLOT_EVENT,
    FIELD_RELATION_CHANGE,
    FIELD_RESOURCE_GAIN,
    FIELD_RESOURCE_SETUP,
    FIELD_RESOURCE_SPEND,
    FIELD_STATUS_CHANGE,
    FIELD_STATUS_EMOTION,
    FIELD_STATUS_GOAL,
    FIELD_STATUS_LOCATION,
)
from card_parser import CARD_MARKER, extract_body, extract_bullets, extract_section
from chapter_scan import chapter_files_in_volume
from common_io import load_project_state, load_volume_outline, save_project_state, save_json_file
from path_rules import chapter_card_file, project_running_memory_file, volume_memory_dir, volume_memory_json, volume_memory_md


def load_volume_chapters(project_dir: Path, vol_num: int) -> list[tuple[int, Path, str]]:
    chapters = []
    for ch_num, chapter_file in chapter_files_in_volume(project_dir, vol_num):
        content = chapter_file.read_text(encoding="utf-8")
        if CARD_MARKER not in content:
            card_candidates = [
                chapter_card_file(project_dir, vol_num, ch_num),
                chapter_file.parent / "cards" / f"{chapter_file.stem}_card.md",
            ]
            for candidate in card_candidates:
                if candidate.exists():
                    content = content.rstrip() + "\n\n" + candidate.read_text(encoding="utf-8")
                    break
        chapters.append((ch_num, chapter_file, content))
    return chapters


def collect_names(text: str) -> list[str]:
    patterns = [
        r"([\u4e00-\u9fff]{2,4})(?:说道|回道|问道|笑道|怒道|冷声道|沉声道|轻声道|看向|盯着|走进)",
        r"[主主]要人物[:：]\s*([^\n]+)",
    ]
    names: list[str] = []
    for pattern in patterns:
        for match in re.findall(pattern, text):
            if isinstance(match, tuple):
                match = next((item for item in match if item), "")
            for item in re.split(r"[、，,；;\s]+", match):
                item = item.strip()
                if 2 <= len(item) <= 6:
                    names.append(item)
    return names


def collect_locations(text: str) -> list[str]:
    return re.findall(r"在([\u4e00-\u9fff]{2,8})(?:中|里|内|上|下|边|前)", text)


def ranked_unique(items: list[str], top_n: int = 8) -> list[str]:
    filtered = [item.strip() for item in items if item.strip()]
    return [item for item, _ in Counter(filtered).most_common(top_n)]


def make_fact_entry(fact: str, source: str, confidence: str = "high") -> dict:
    return {"fact": fact, "source": source, "confidence": confidence}


def append_unique_fact(target: list[dict], fact: str, source: str, confidence: str = "high") -> None:
    normalized = fact.strip()
    if not normalized:
        return
    if any(item.get("fact") == normalized for item in target):
        return
    target.append(make_fact_entry(normalized, source, confidence))


def detect_conflicts(previous_memory: dict, stable_facts: list[dict], final_state: dict) -> list[dict]:
    conflicts: list[dict] = []
    previous_final = previous_memory.get("final_state", {}) if previous_memory else {}
    for key in ["主角当前位置", "主角当前情绪", "主角当前目标", "卷末状态变化"]:
        previous_value = previous_final.get(key, "").strip()
        current_value = final_state.get(key, "").strip()
        if previous_value and current_value and previous_value != current_value:
            conflicts.append({
                "field": key,
                "previous": previous_value,
                "current": current_value,
                "reason": "与上一版卷沉淀字段不一致",
            })

    previous_facts = {item.get("fact") for item in previous_memory.get("stable_facts", [])} if previous_memory else set()
    current_facts = {item.get("fact") for item in stable_facts}
    for fact in sorted(previous_facts - current_facts):
        conflicts.append({
            "field": "stable_facts",
            "previous": fact,
            "current": "",
            "reason": "旧稳定事实未在新沉淀中保留，请人工确认是否被推翻",
        })
    return conflicts


def build_volume_memory(project_dir: Path, vol_num: int) -> dict:
    chapters = load_volume_chapters(project_dir, vol_num)
    if not chapters:
        return {}

    outline = load_volume_outline(project_dir, vol_num)
    existing_memory = {}
    existing_path = volume_memory_json(project_dir, vol_num)
    if existing_path.exists():
        existing_memory = json.loads(existing_path.read_text(encoding="utf-8"))

    all_names: list[str] = []
    all_locations: list[str] = []
    resource_gained_entries: list[dict] = []
    resource_spent_entries: list[dict] = []
    stable_facts: list[dict] = []
    unverified_claims: list[dict] = []
    open_setups: list[dict] = []
    resolved_setups: list[dict] = []
    chapter_outcomes: list[dict] = []
    emotion_arcs: list[dict] = []
    relationship_changes: list[dict] = []

    final_state = {
        "主角当前位置": "",
        "主角当前情绪": "",
        "主角当前目标": "",
        "卷末状态变化": "",
    }

    for ch_num, _, content in chapters:
        source = f"vol{vol_num:02d}_ch{ch_num:03d}"
        body = extract_body(content)
        all_names.extend(collect_names(body + "\n" + content))
        all_locations.extend(collect_locations(body))

        state_card = extract_bullets(extract_section(content, STATUS_CARD))
        plot_card = extract_bullets(extract_section(content, PLOT_CARD))
        resource_card = extract_bullets(extract_section(content, RESOURCE_CARD))
        relation_card = extract_bullets(extract_section(content, RELATION_CARD))
        emotion_card = extract_bullets(extract_section(content, EMOTION_CARD))
        carry_card = extract_bullets(extract_section(content, CARRY_CARD))

        if resource_card.get(FIELD_RESOURCE_GAIN):
            append_unique_fact(resource_gained_entries, resource_card[FIELD_RESOURCE_GAIN], source)
            append_unique_fact(stable_facts, f"资源获得：{resource_card[FIELD_RESOURCE_GAIN]}", source)
        if resource_card.get(FIELD_RESOURCE_SPEND):
            append_unique_fact(resource_spent_entries, resource_card[FIELD_RESOURCE_SPEND], source)
        if resource_card.get(FIELD_RESOURCE_SETUP):
            append_unique_fact(open_setups, resource_card[FIELD_RESOURCE_SETUP], source, "medium")
        if relation_card.get(FIELD_RELATION_CHANGE):
            append_unique_fact(relationship_changes, relation_card[FIELD_RELATION_CHANGE], source)
            append_unique_fact(stable_facts, f"关系变化：{relation_card[FIELD_RELATION_CHANGE]}", source)
        if state_card.get(FIELD_STATUS_CHANGE):
            append_unique_fact(stable_facts, state_card[FIELD_STATUS_CHANGE], source)
        if plot_card.get(FIELD_PLOT_EVENT):
            chapter_outcomes.append({"chapter": ch_num, "event": plot_card[FIELD_PLOT_EVENT], "source": source})
            append_unique_fact(resolved_setups, plot_card[FIELD_PLOT_EVENT], source)
        if emotion_card.get(FIELD_EMOTION_TARGET):
            append_unique_fact(emotion_arcs, emotion_card[FIELD_EMOTION_TARGET], source, "medium")
        if carry_card.get(FIELD_CARRY_SETUP):
            append_unique_fact(open_setups, carry_card[FIELD_CARRY_SETUP], source, "medium")

        if state_card.get(FIELD_STATUS_LOCATION):
            append_unique_fact(stable_facts, f"卷内位置锚点：{state_card[FIELD_STATUS_LOCATION]}", source)
        if state_card.get(FIELD_STATUS_GOAL):
            append_unique_fact(unverified_claims, f"阶段目标：{state_card[FIELD_STATUS_GOAL]}", source, "medium")

        if ch_num == chapters[-1][0]:
            final_state["主角当前位置"] = state_card.get(FIELD_STATUS_LOCATION, "")
            final_state["主角当前情绪"] = state_card.get(FIELD_STATUS_EMOTION, "")
            final_state["主角当前目标"] = state_card.get(FIELD_STATUS_GOAL, "")
            final_state["卷末状态变化"] = state_card.get(FIELD_STATUS_CHANGE, "")

    next_volume_constraints = [
        make_fact_entry(item, f"vol{vol_num:02d}_ending", "high")
        for item in [
            final_state["主角当前位置"],
            final_state["主角当前目标"],
            final_state["卷末状态变化"],
            outline.get("卷尾钩子", ""),
        ] if item
    ]

    conflicts = detect_conflicts(existing_memory, stable_facts, final_state)

    volume_memory = {
        "volume": vol_num,
        "title": outline.get("卷标题", f"第{vol_num}卷"),
        "volume_goal": outline.get("卷目标", "推进故事"),
        "volume_hook": outline.get("卷尾钩子", outline.get("卷钩子", "")),
        "volume_position": outline.get("卷定位", ""),
        "volume_escalation": outline.get("抬升路径", ""),
        "volume_conflict": outline.get("核心冲突", ""),
        "volume_turning_points": outline.get("关键转折", ""),
        "characters": ranked_unique(all_names),
        "locations": ranked_unique(all_locations),
        "resources": {
            "gained": resource_gained_entries,
            "spent": resource_spent_entries,
        },
        "relationships": relationship_changes,
        "emotion_arcs": emotion_arcs,
        "stable_facts": stable_facts,
        "unverified_claims": unverified_claims,
        "resolved_setups": resolved_setups,
        "open_setups": open_setups,
        "final_state": final_state,
        "chapter_outcomes": chapter_outcomes[-6:],
        "next_volume_constraints": next_volume_constraints,
        "conflicts": conflicts,
    }
    return volume_memory


def _render_fact_lines(items: list[dict], prefix: str = "- ") -> list[str]:
    if not items:
        return [f"{prefix}（暂无）"]
    lines = []
    for item in items:
        source = item.get("source", "")
        confidence = item.get("confidence", "")
        suffix = f" [{source}]" if source else ""
        if confidence:
            suffix += f" ({confidence})"
        lines.append(f"{prefix}{item.get('fact', '')}{suffix}")
    return lines


def write_memory_files(project_dir: Path, volume_memory: dict) -> tuple[Path, Path, Path]:
    memory_dir = volume_memory_dir(project_dir)
    memory_dir.mkdir(parents=True, exist_ok=True)
    vol_num = volume_memory["volume"]

    json_path = volume_memory_json(project_dir, vol_num)
    md_path = volume_memory_md(project_dir, vol_num)
    project_summary_path = project_running_memory_file(project_dir)

    save_json_file(json_path, volume_memory)

    lines = [
        f"# 第{vol_num}卷 沉淀设定",
        "",
        f"- 卷标题：{volume_memory.get('title', '')}",
        f"- 卷目标：{volume_memory.get('volume_goal', '')}",
        f"- 卷尾钩子：{volume_memory.get('volume_hook', '')}",
    ]
    
    # 新增字段（如果存在）
    if volume_memory.get("volume_position"):
        lines.append(f"- 卷定位：{volume_memory['volume_position']}")
    if volume_memory.get("volume_escalation"):
        lines.append(f"- 抬升路径：{volume_memory['volume_escalation']}")
    if volume_memory.get("volume_conflict"):
        lines.append(f"- 核心冲突：{volume_memory['volume_conflict']}")
    if volume_memory.get("volume_turning_points"):
        lines.append(f"- 关键转折：{volume_memory['volume_turning_points']}")
    
    lines.extend([
        "",
        "## 卷末稳定状态",
        f"- 位置：{volume_memory['final_state'].get('主角当前位置', '')}",
        f"- 情绪：{volume_memory['final_state'].get('主角当前情绪', '')}",
        f"- 目标：{volume_memory['final_state'].get('主角当前目标', '')}",
        f"- 状态变化：{volume_memory['final_state'].get('卷末状态变化', '')}",
        "",
        "## 稳定事实",
    ])
    lines.extend(_render_fact_lines(volume_memory.get("stable_facts", [])))
    lines.append("")
    lines.append("## 未证实信息")
    lines.extend(_render_fact_lines(volume_memory.get("unverified_claims", [])))
    lines.append("")
    lines.append("## 已回收伏笔")
    lines.extend(_render_fact_lines(volume_memory.get("resolved_setups", [])))
    lines.append("")
    lines.append("## 持续伏笔")
    lines.extend(_render_fact_lines(volume_memory.get("open_setups", [])))
    lines.append("")
    lines.append("## 下卷约束")
    lines.extend(_render_fact_lines(volume_memory.get("next_volume_constraints", [])))
    lines.append("")
    lines.append("## 冲突提示")
    if volume_memory.get("conflicts"):
        for item in volume_memory["conflicts"]:
            lines.append(f"- {item['field']}：旧值={item['previous']} / 新值={item['current']} / 原因={item['reason']}")
    else:
        lines.append("- （暂无）")
    md_path.write_text("\n".join(lines), encoding="utf-8")

    project_lines = ["# 项目运行中动态记忆", ""]
    for file_path in sorted(memory_dir.glob("vol*_state.json")):
        data = json.loads(file_path.read_text(encoding="utf-8"))
        project_lines.extend([
            f"## 第{data['volume']}卷",
            f"- 卷目标：{data.get('volume_goal', '')}",
            f"- 稳定事实：{'；'.join(item.get('fact', '') for item in data.get('stable_facts', [])[:4])}",
            f"- 未证实信息：{'；'.join(item.get('fact', '') for item in data.get('unverified_claims', [])[:3])}",
            f"- 未回收伏笔：{'；'.join(item.get('fact', '') for item in data.get('open_setups', [])[:4])}",
            f"- 下卷约束：{'；'.join(item.get('fact', '') for item in data.get('next_volume_constraints', [])[:4])}",
            f"- 冲突数：{len(data.get('conflicts', []))}",
            "",
        ])
    project_summary_path.write_text("\n".join(project_lines), encoding="utf-8")

    return json_path, md_path, project_summary_path


def update_project_state(project_dir: Path, volume_memory: dict) -> None:
    state = load_project_state(project_dir)
    state.setdefault("volume_memory", {})
    state["volume_memory"][f"vol{volume_memory['volume']:02d}"] = volume_memory

    ordered = [state["volume_memory"][key] for key in sorted(state["volume_memory"].keys())]
    state["project_running_memory"] = {
        "latest_volume": volume_memory["volume"],
        "active_constraints": [item.get("fact", "") for item in volume_memory.get("next_volume_constraints", [])],
        "open_setups": [item.get("fact", "") for item in volume_memory.get("open_setups", [])],
        "latest_final_state": volume_memory.get("final_state", {}),
        "recent_volumes": ordered[-3:],
        "stable_facts": [item.get("fact", "") for item in volume_memory.get("stable_facts", [])],
        "unverified_claims": [item.get("fact", "") for item in volume_memory.get("unverified_claims", [])],
        "conflicts": volume_memory.get("conflicts", []),
    }
    save_project_state(project_dir, state)


def enrich_volume_state(project_dir: Path, vol_num: int) -> dict:
    volume_memory = build_volume_memory(project_dir, vol_num)
    if not volume_memory:
        return {}
    write_memory_files(project_dir, volume_memory)
    update_project_state(project_dir, volume_memory)
    return volume_memory


def main() -> None:
    if len(sys.argv) < 3:
        print("用法: python3 volume_state_enricher.py <project_dir> <vol_num>")
        sys.exit(1)

    project_dir = Path(sys.argv[1]).expanduser().resolve()
    vol_num = int(sys.argv[2])
    if not project_dir.exists():
        print(f"项目目录不存在: {project_dir}")
        sys.exit(1)

    volume_memory = enrich_volume_state(project_dir, vol_num)
    if not volume_memory:
        print(f"未能生成第{vol_num}卷沉淀")
        sys.exit(1)

    print(f"第{vol_num}卷沉淀完成")
    print(f"- 角色: {len(volume_memory.get('characters', []))}")
    print(f"- 稳定事实: {len(volume_memory.get('stable_facts', []))}")
    print(f"- 持续伏笔: {len(volume_memory.get('open_setups', []))}")
    print(f"- 冲突数: {len(volume_memory.get('conflicts', []))}")


if __name__ == "__main__":
    main()
