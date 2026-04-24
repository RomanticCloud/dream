#!/usr/bin/env python3
"""Tests for strict menus and continuous writer dispatcher."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from continuous_writer import run as run_continuous_writer
from strict_interactive_runner import FIXED_MENUS


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def build_project(root: Path) -> None:
    write(root / "wizard_state.json", json.dumps({
        "basic_specs": {
            "chapter_length_min": 10,
            "chapter_length_max": 2500,
            "main_genres": ["都市生活"],
            "chapters_per_volume": 10,
        },
        "protagonist": {"gender": "男"},
        "positioning": {"narrative_style": "第三人称有限视角"},
        "naming": {"selected_book_title": "测试项目"},
    }, ensure_ascii=False))


def test_init_menu_supports_resume_and_plan_only():
    labels = [item["label"] for item in FIXED_MENUS["init"]["options"]]
    assert labels == ["新建项目", "继续已有项目", "仅规划", "退出"]


def test_continuous_writer_returns_draft_required_with_request_files():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        build_project(root)
        result = run_continuous_writer(root)
        assert result["status"] == "draft_required"
        assert result["vol"] == 1
        assert result["ch"] == 1
        assert Path(result["prompt_file"]).exists()
        assert Path(result["request_file"]).exists()
        assert Path(result["manifest_file"]).exists()


def test_continuous_writer_consumes_task_result_file():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        build_project(root)
        draft = run_continuous_writer(root)
        assert draft["status"] == "draft_required"
        request = json.loads(Path(draft["request_file"]).read_text(encoding="utf-8"))
        manifest = json.loads(Path(draft["manifest_file"]).read_text(encoding="utf-8"))
        result_file = root / "task_result.json"
        result_file.write_text(json.dumps({
            "status": "success",
            "context_manifest_id": request["context_manifest_id"],
            "files_read": manifest["required_read_sequence"],
            "chapter_body": "# 第1章 开场\n\n## 正文\n\n陆既明第一次真正说了不。\n",
            "chapter_cards": "## 内部工作卡\n\n### 1. 状态卡\n- 主角当前位置：会议室\n- 主角当前伤势/疲劳：无\n- 主角当前情绪：紧绷\n- 主角当前目标：顶住甩锅\n- 本章结束后的状态变化：成功顶回去\n- 本章时间流逝：1小时\n- 本章结束时时间点：第1天上午\n\n### 2. 情节卡\n- 核心冲突：顶住甩锅\n- 关键事件：当众反击\n- 转折点：上司改变态度\n- 新埋伏笔：系统开始加载\n- 回收伏笔：无\n\n### 3. 资源卡\n- 获得：+1主动权\n- 消耗：-1体力\n- 损失：无\n- 需带到下章的状态：系统即将正式提示\n- 伏笔：系统开始加载\n\n### 4. 关系卡\n- 主要人物：陆既明、高远\n- 人物变化：矛盾升级\n\n### 5. 情绪弧线卡\n- 起始情绪：压抑\n- 变化过程：压抑转为决绝\n- 目标情绪：警惕\n- 悬念强度：6\n\n### 6. 承上启下卡\n- 下章必须接住什么：系统正式发出提示\n- 下章不能忘什么限制：处境未稳\n- 需要回收的伏笔：系统开始加载\n- 新埋下的伏笔：沈知夏会继续观察主角\n- 本章留下的最强钩子是什么：蓝字即将完整出现\n"
        }, ensure_ascii=False), encoding="utf-8")

        result = run_continuous_writer(root, str(result_file))
        assert result["status"] == "chapter_ready"
        assert Path(result["body_output"]).exists()
        assert Path(result["card_output"]).exists()


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
