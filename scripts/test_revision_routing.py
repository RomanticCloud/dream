#!/usr/bin/env python3
"""Tests for revision routing and menus."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from strict_interactive_runner import FIXED_MENUS, main as runner_main
from volume_revision_router import apply_full_chapter_result, apply_rewrite_card_result, revalidate_after_revision, run_rewrite_card
from rule_engine import filter_tasks_for_mode, infer_execution_mode


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_chapter_revision_menu_contains_rewrite_card():
    labels = [item["label"] for item in FIXED_MENUS["chapter-revision-menu"]["options"]]
    assert "重写工作卡" in labels


def test_run_rewrite_card_creates_prompt_file():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        write(root / "wizard_state.json", json.dumps({"naming": {"selected_book_title": "测试书"}}, ensure_ascii=False))
        write(root / "chapters" / "vol01" / "ch01.md", "# 第1章\n\n## 正文\n\n张三在房间里等待来人，仔细听着门外的动静，确认线索仍在掌握之中。")

        tasks = [
            {
                "type": "field_invalid",
                "severity": "error",
                "card": "2. 情节卡",
                "field": "关键事件",
                "message": "字段不一致",
                "instruction": "让关键事件与正文一致。",
                "fix_method": "rewrite_card",
            }
        ]

        ok = run_rewrite_card(root, 1, 1, tasks)
        prompt_file = root / "chapters" / "vol01" / "001_rewrite_card_prompt.md"

        assert ok is True
        assert prompt_file.exists()
        prompt_text = prompt_file.read_text(encoding="utf-8")
        assert "工作卡重写" in prompt_text
        assert "让关键事件与正文一致。" in prompt_text


def test_runner_chapter_revision_works_without_fix_plan_file():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        write(root / "REVISION_STATE.json", json.dumps({
            "chapter": {
                "vol01_ch001": {
                    "status": "pending_rewrite_card",
                    "fix_plan": {},
                    "tasks": [{"type": "field_invalid", "severity": "error", "instruction": "补全工作卡", "fix_method": "rewrite_card"}],
                }
            },
            "volume": {},
        }, ensure_ascii=False))
        old_argv = sys.argv[:]
        try:
            sys.argv = ["strict_interactive_runner.py", "chapter-revision", str(root), "1", "1"]
            code = runner_main()
        finally:
            sys.argv = old_argv
        assert code == 0


def test_runner_volume_revision_works_without_fix_plan_file():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        write(root / "REVISION_STATE.json", json.dumps({
            "chapter": {},
            "volume": {
                "vol01": {
                    "status": "pending_polish",
                    "fix_plan": {},
                    "memory_enriched": False,
                }
            },
        }, ensure_ascii=False))
        write(root / "chapters" / "vol01" / "ch01.md", "# 第1章\n\n正文")
        old_argv = sys.argv[:]
        try:
            sys.argv = ["strict_interactive_runner.py", "volume-revision", str(root), "1"]
            code = runner_main()
        finally:
            sys.argv = old_argv
        assert code == 0


def test_normalize_volume_revision_payload_reads_tasks():
    from revision_state import normalize_volume_revision_payload

    payload = normalize_volume_revision_payload({
        "fix_plan": {},
        "tasks": [{"fix_method": "rewrite_card", "instruction": "重写工作卡"}],
        "memory_enriched": False,
    })

    assert payload["status"] == "pending_rewrite_card"
    assert payload["tasks"][0]["instruction"] == "重写工作卡"


def test_tasks_to_fix_plan_prefers_structured_tasks():
    from volume_revision_router import tasks_to_fix_plan

    fix_plan = tasks_to_fix_plan([
        {"type": "word_count_low", "severity": "error", "instruction": "整章重写", "fix_method": "regenerate"},
        {"type": "resource_format_weak", "severity": "warning", "instruction": "补强资源格式", "fix_method": "polish"},
    ])

    assert fix_plan["total_regenerate"] == 1
    assert fix_plan["total_polish"] == 1
    assert fix_plan["regenerate"][0]["details"] == "整章重写"


def test_apply_rewrite_card_result_and_revalidate_clears_pending():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        write(root / "wizard_state.json", json.dumps({"basic_specs": {"chapter_length_min": 10, "chapter_length_max": 5000, "main_genres": ["都市生活"]}}, ensure_ascii=False))
        write(root / "chapters" / "vol01" / "ch01.md", "# 第1章\n\n## 正文\n\n张三在房间里等待来人，仔细听着门外的动静，确认线索仍在掌握之中。")
        write(root / "chapters" / "vol01" / "cards" / "ch01_card.md", "## 内部工作卡\n\n### 1. 状态卡\n- 主角当前位置：房间\n")
        write(root / "REVISION_STATE.json", json.dumps({
            "chapter": {
                "vol01_ch001": {"status": "pending_rewrite_card", "fix_plan": {}, "tasks": [{"instruction": "补全工作卡", "fix_method": "rewrite_card"}]}
            },
            "volume": {}
        }, ensure_ascii=False))

        revised_cards = """## 内部工作卡

### 1. 状态卡
- 主角当前位置：房间
- 主角当前伤势/疲劳：无
- 主角当前情绪：平静
- 主角当前目标：等待对话
- 本章结束后的状态变化：保持警惕
- 本章时间流逝：30分钟
- 本章结束时时间点：第1天晚上

### 2. 情节卡
- 核心冲突：等待对话开始
- 关键事件：张三留在房间
- 转折点：门外传来敲门声
- 新埋伏笔：敲门人身份不明
- 回收伏笔：无

### 3. 资源卡
- 获得：+1线索
- 消耗：-1耐心
- 损失：无
- 需带到下章的状态：张三继续等待
- 伏笔：敲门人身份不明

### 4. 关系卡
- 主要人物：张三
- 人物变化：暂无

### 5. 情绪弧线卡
- 起始情绪：平静
- 变化过程：平静转为紧张
- 目标情绪：警惕
- 悬念强度：6

### 6. 承上启下卡
- 下章必须接住什么：开门查看来人
- 下章不能忘什么限制：张三仍在房间内
- 需要回收的伏笔：敲门人身份不明
- 新埋下的伏笔：门外可能不止一人
- 本章留下的最强钩子是什么：敲门声越来越急
"""
        ok, _ = apply_rewrite_card_result(root, 1, 1, revised_cards)
        assert ok is True
        result = revalidate_after_revision(root, 1, 1)
        assert result.passed is True
        revision_state = json.loads((root / "REVISION_STATE.json").read_text(encoding="utf-8"))
        assert "vol01_ch001" not in revision_state["chapter"]


def test_apply_full_chapter_result_rejects_missing_markers():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        write(root / "chapters" / "vol01" / "ch01.md", "# 第1章\n\n旧内容")
        ok, message = apply_full_chapter_result(root, 1, 1, "# 第1章\n\n没有标记")
        assert ok is False
        assert "内部工作卡" in message


def test_infer_execution_mode_prefers_full_chapter():
    mode = infer_execution_mode([
        {"rewrite_target": "work_cards_only", "blocking": True, "priority": "high", "severity": "error"},
        {"rewrite_target": "full_chapter", "blocking": True, "priority": "medium", "severity": "error"},
    ])
    assert mode == "full_chapter"


def test_infer_execution_mode_prefers_work_cards_over_local_patch():
    mode = infer_execution_mode([
        {"rewrite_target": "local_patch", "blocking": False, "priority": "low", "severity": "warning"},
        {"rewrite_target": "work_cards_only", "blocking": True, "priority": "high", "severity": "error"},
    ])
    assert mode == "work_cards_only"


def test_filter_tasks_for_mode_returns_only_matching_tasks():
    tasks = [
        {"rewrite_target": "full_chapter", "instruction": "整章重写", "blocking": True, "priority": "high", "severity": "error"},
        {"rewrite_target": "local_patch", "instruction": "局部润色", "blocking": False, "priority": "low", "severity": "warning"},
    ]
    filtered = filter_tasks_for_mode(tasks, "full_chapter")
    assert len(filtered) == 1
    assert filtered[0]["instruction"] == "整章重写"


def test_infer_execution_mode_prefers_full_chapter():
    mode = infer_execution_mode([
        {"rewrite_target": "work_cards_only", "blocking": True, "priority": "high", "severity": "error"},
        {"rewrite_target": "full_chapter", "blocking": True, "priority": "medium", "severity": "error"},
    ])
    assert mode == "full_chapter"


def test_infer_execution_mode_prefers_work_cards_over_local_patch():
    mode = infer_execution_mode([
        {"rewrite_target": "local_patch", "blocking": False, "priority": "low", "severity": "warning"},
        {"rewrite_target": "work_cards_only", "blocking": True, "priority": "high", "severity": "error"},
    ])
    assert mode == "work_cards_only"


if __name__ == "__main__":
    import traceback

    passed = 0
    failed = 0
    for name, func in sorted(globals().items()):
        if name.startswith("test_"):
            try:
                func()
                print(f"  PASS {name}")
                passed += 1
            except Exception:
                print(f"  FAIL {name}")
                traceback.print_exc()
                failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
