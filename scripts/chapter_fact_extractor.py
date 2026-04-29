#!/usr/bin/env python3
"""Extract chapter facts from drafted prose for card generation and validation."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from body_validator import extract_body
from common_io import save_json_file
from path_rules import chapter_file


def fact_file(project_dir: Path, vol: int, ch: int) -> Path:
    return project_dir / "context" / f"chapter_facts_vol{vol:02d}_ch{ch:02d}.json"


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[。！？!?])", text)
    return [part.strip() for part in parts if part.strip()]


def _extract_title(text: str, ch: int) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return f"第{ch}章"


def _extract_key_terms(body: str) -> list[str]:
    patterns = [
        r"[A-Z]\d(?:-\d+)*",
        r"零号旧库(?:\s*[A-Z]\d(?:-\d+)*)?",
        r"第七份档案",
        r"镜子的背后",
        r"黑色灯塔",
        r"[\u4e00-\u9fa5]{2,5}录音带",
    ]
    terms: list[str] = []
    for pattern in patterns:
        terms.extend(re.findall(pattern, body))
    return list(dict.fromkeys(term.strip() for term in terms if term.strip()))[:20]


def _extract_location(sentences: list[str], fallback: str = "") -> str:
    text = "".join(sentences)
    patterns = [
        r"(零号旧库\s*[A-Z]\d(?:-\d+)*)",
        r"(地下档案馆修复室|修复室|监控室|旧库|杂物间|走廊|楼梯间|设备层)",
        r"(?:进入|回到|抵达|来到|走进|踏入)([^，。！？]{2,16})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()
    return fallback


def _extract_event(sentences: list[str]) -> str:
    useful = [s for s in sentences if any(word in s for word in ["发现", "找到", "确认", "进入", "看见", "听见", "录音", "档案"])]
    return (useful[-1] if useful else (sentences[-1] if sentences else ""))[:160]


def _detect_plan_deviation(body: str, key_terms: list[str]) -> dict:
    aliases = []
    if "B7" in body and "B7-07" in body:
        aliases.append({"from": "B7", "to": "B7-07", "type": "acceptable_enrichment"})
    if "旧库" in body and "零号旧库" in body:
        aliases.append({"from": "旧库", "to": "零号旧库", "type": "acceptable_enrichment"})
    return {
        "renamed_terms": aliases,
        "missing_required_items": [],
        "new_important_facts": key_terms[:8],
    }


def extract_facts_from_body_text(body_text: str, vol: int, ch: int) -> dict:
    body = extract_body(body_text) or body_text
    sentences = _sentences(body)
    dialogues = re.findall(r"[“\"]([^”\"]{4,120})[”\"]", body)
    time_mentions = re.findall(r"(?:第\d+天(?:清晨|早晨|上午|中午|下午|傍晚|晚上|深夜)?|\d+(?:分钟|小时|天|月|年)后|第二天|几天后|一周后|一个月后)", body)
    resource_mentions = re.findall(r"[+-]?\d+[\u4e00-\u9fa5A-Za-z]+", body)
    ending = "".join(sentences[-3:])[-500:] if sentences else body[-500:]
    opening = "".join(sentences[:3])[:500] if sentences else body[:500]
    key_terms = _extract_key_terms(body)
    location_start = _extract_location(sentences[:5])
    location_end = _extract_location(sentences[-8:], location_start)
    actual_event = _extract_event(sentences)
    actual_hook = (sentences[-1] if sentences else ending)[-180:]
    return {
        "chapter": f"vol{vol:02d}/ch{ch:02d}",
        "actual_title": _extract_title(body_text, ch),
        "actual_main_event": actual_event,
        "actual_location_start": location_start,
        "actual_location_end": location_end,
        "actual_goal": "追查第七份档案与父亲失踪真相" if "第七份档案" in body or "父亲" in body else "推进当前主线",
        "actual_state_change": actual_event,
        "actual_payoffs": [term for term in key_terms if term in body[: max(len(body) // 2, 1)]],
        "actual_new_setups": [actual_hook] if actual_hook else [],
        "actual_ending_hook": actual_hook,
        "actual_key_terms": key_terms,
        "plan_deviation": _detect_plan_deviation(body, key_terms),
        "opening_excerpt": opening,
        "ending_excerpt": ending,
        "key_dialogue": dialogues[:5],
        "time_mentions": list(dict.fromkeys(time_mentions))[:10],
        "resource_mentions": list(dict.fromkeys(resource_mentions))[:10],
        "candidate_events": sentences[:2] + sentences[-3:],
        "word_count_hint": len(re.sub(r"\s+", "", body)),
    }


def extract_facts_from_file(project_dir: Path, vol: int, ch: int) -> dict:
    path = chapter_file(project_dir, vol, ch)
    text = path.read_text(encoding="utf-8")
    facts = extract_facts_from_body_text(text, vol, ch)
    save_json_file(fact_file(project_dir, vol, ch), facts)
    return facts


def main() -> int:
    parser = argparse.ArgumentParser(description="从正文提取章节事实")
    parser.add_argument("project_dir")
    parser.add_argument("vol", type=int)
    parser.add_argument("ch", type=int)
    args = parser.parse_args()
    payload = extract_facts_from_file(Path(args.project_dir).expanduser().resolve(), args.vol, args.ch)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
