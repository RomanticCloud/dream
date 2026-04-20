#!/usr/bin/env python3
"""Tests for subagent_chapter_generator.py"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from subagent_chapter_generator import SubagentChapterGenerator


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def build_project(root: Path, with_outline: bool = True) -> None:
    write(root / "wizard_state.json", json.dumps({
        "basic_specs": {
            "chapter_length_min": 3500,
            "chapter_length_max": 4500,
            "style_tone": "悬疑推理",
            "main_genres": ["悬疑推理", "都市生活"],
        },
        "positioning": {"narrative_style": "第三人称有限视角"},
        "naming": {"selected_book_title": "档案馆迷案"},
    }, ensure_ascii=False))

    write(root / "chapters" / "vol01" / "ch001.md", """# 第1章 起源

林舟走进旧城区档案馆，发现火灾档案被抽走。

## 内部工作卡

### 1. 状态卡
- 主角当前位置：档案馆
- 主角当前情绪：警惕
""")

    write(root / "chapters" / "vol01" / "ch002.md", """# 第2章 线索

林舟顺着签名查到许衡。

## 内部工作卡

### 1. 状态卡
- 主角当前位置：档案馆地下室
- 主角当前情绪：紧绷
""")

    write(root / "chapters" / "vol02" / "ch001.md", """# 第3章 真相

陈叔终于承认当年的事。

## 内部工作卡

### 1. 状态卡
- 主角当前位置：档案馆休息室
- 主角当前情绪：冷静
""")

    if with_outline:
        write(root / "reference" / "卷纲总表.md", """# 卷纲总表

## 第1卷 · 初始阶段
- 卷定位：故事开篇

### 第1章 起源
- 章节目标：建立档案馆谜案

### 第2章 线索
- 章节目标：追查签名来源

## 第2卷 · 推进阶段
- 卷定位：冲突升级

### 第1章 真相
- 章节目标：揭示部分真相
""")


def test_load_all_previous_chapters():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        build_project(root)

        gen = SubagentChapterGenerator(root)

        # Load chapters before vol2 ch2 (should get vol1 ch001, vol1 ch002, vol2 ch001)
        chapters = gen.load_all_previous_chapters(vol_num=2, ch_num=2)
        assert len(chapters) == 3
        assert chapters[0]["vol"] == 1 and chapters[0]["ch"] == 1
        assert chapters[1]["vol"] == 1 and chapters[1]["ch"] == 2
        assert chapters[2]["vol"] == 2 and chapters[2]["ch"] == 1


def test_load_all_previous_chapters_with_lookback():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        build_project(root)

        gen = SubagentChapterGenerator(root)

        # lookback=2 should only return last 2 chapters
        chapters = gen.load_all_previous_chapters(vol_num=2, ch_num=2, lookback=2)
        assert len(chapters) == 2
        assert chapters[0]["vol"] == 1 and chapters[0]["ch"] == 2
        assert chapters[1]["vol"] == 2 and chapters[1]["ch"] == 1


def test_load_all_previous_chapters_first_chapter():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        build_project(root)

        gen = SubagentChapterGenerator(root)

        # First chapter of first volume should return empty
        chapters = gen.load_all_previous_chapters(vol_num=1, ch_num=1)
        assert len(chapters) == 0


def test_load_all_previous_chapters_no_chapters_dir():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        write(root / "wizard_state.json", "{}")

        gen = SubagentChapterGenerator(root)
        chapters = gen.load_all_previous_chapters(vol_num=1, ch_num=2)
        assert chapters == []


def test_build_subagent_prompt():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        build_project(root)

        gen = SubagentChapterGenerator(root)
        chapters = gen.load_all_previous_chapters(vol_num=2, ch_num=2)
        config = json.loads((root / "wizard_state.json").read_text(encoding="utf-8"))

        prompt = gen.build_subagent_prompt(
            previous_chapters=chapters,
            project_config=config,
            current_chapter_info={"vol": 2, "ch": 2},
        )

        assert "档案馆迷案" in prompt
        assert "悬疑推理" in prompt
        assert "第2卷" in prompt
        assert "第2章" in prompt
        assert "第1章 起源" in prompt
        assert "第2章 线索" in prompt
        assert "第3章 真相" in prompt
        assert "生成要求" in prompt
        assert "连续性要求" in prompt


def test_build_subagent_prompt_with_plan():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        build_project(root)

        gen = SubagentChapterGenerator(root)
        chapters = gen.load_all_previous_chapters(vol_num=1, ch_num=2)
        config = json.loads((root / "wizard_state.json").read_text(encoding="utf-8"))

        plan = {"description": "### 第2章 线索\n- 章节目标：追查签名来源"}

        prompt = gen.build_subagent_prompt(
            previous_chapters=chapters,
            project_config=config,
            current_chapter_info={"vol": 1, "ch": 2},
            chapter_plan=plan,
        )

        assert "章节规划" in prompt
        assert "追查签名来源" in prompt


def test_dispatch_chapter_generation():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        build_project(root)

        gen = SubagentChapterGenerator(root)
        result = gen.dispatch_chapter_generation(vol_num=2, ch_num=2)

        assert result["status"] == "prompt_ready"
        assert result["chapters_loaded"] == 3
        assert result["prompt_length"] > 0
        assert result["generation_time"] >= 0

        prompt_file = Path(result["prompt_file"])
        assert prompt_file.exists()
        prompt_text = prompt_file.read_text(encoding="utf-8")
        assert "档案馆迷案" in prompt_text


def test_dispatch_chapter_generation_error_no_previous():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        write(root / "wizard_state.json", "{}")
        write(root / "chapters" / "vol01" / "ch001.md", "# 第1章\n\ncontent")

        gen = SubagentChapterGenerator(root)
        result = gen.dispatch_chapter_generation(vol_num=1, ch_num=2)

        # ch001.md matches ch(\d+) pattern => ch=1, so for vol=1 ch=2, it should find ch001
        # Wait — ch001.md matches r"ch(\d+)" giving ch=1, and we skip ch >= ch_num (2)?
        # ch=1 < ch_num=2, so it should NOT be skipped. So we should get 1 chapter loaded.
        assert result["status"] == "prompt_ready"
        assert result["chapters_loaded"] == 1


def test_dispatch_chapter_generation_error_chapter1():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        write(root / "wizard_state.json", "{}")

        gen = SubagentChapterGenerator(root)
        result = gen.dispatch_chapter_generation(vol_num=1, ch_num=1)

        assert result["status"] == "prompt_ready"
        assert result["chapters_loaded"] == 0


def test_load_chapter_plan():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        build_project(root)

        gen = SubagentChapterGenerator(root)

        plan = gen._load_chapter_plan(vol_num=1, ch_num=2)
        assert plan is not None
        assert "追查签名来源" in plan["description"]

        plan_missing = gen._load_chapter_plan(vol_num=3, ch_num=1)
        assert plan_missing is None


def test_load_chapter_plan_no_outline():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        write(root / "wizard_state.json", "{}")

        gen = SubagentChapterGenerator(root)
        plan = gen._load_chapter_plan(vol_num=1, ch_num=1)
        assert plan is None


def test_load_all_previous_chapters_multi_volume():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        build_project(root)

        # Add vol03 ch001
        write(root / "chapters" / "vol03" / "ch001.md", "# 第5章 新篇章\n\nnew content")

        gen = SubagentChapterGenerator(root)
        chapters = gen.load_all_previous_chapters(vol_num=3, ch_num=2)
        assert len(chapters) == 4
        assert chapters[-1]["vol"] == 3 and chapters[-1]["ch"] == 1


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
