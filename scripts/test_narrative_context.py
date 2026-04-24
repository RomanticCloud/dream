#!/usr/bin/env python3
"""Tests for narrative_context.py"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from narrative_context import NarrativeContext


SAMPLE_CHAPTER = """# 第1章

林舟走进旧城区档案馆，发现火灾档案被抽走，只剩下残缺目录页。他借着整理旧报纸的机会进入封存区，沿着灰尘的断痕找到被人翻动过的铁柜。管理员陈叔神色复杂，却还是低声提醒他昨晚有人来过。林舟没有追问，只是把注意力放回那页缺失的目录，确认这不是普通遗失，而是有人带着明确目的抽走了关键纸档。就在他准备离开时，页脚又露出了一道陌生签名，像是故意留下来的第二重指引。

陈叔说："你最好别再查下去了。"林舟沉默片刻，回答道："我已经没有退路了。"他转身走向封存区深处，脚步声在空旷的走廊里回荡。空气中有股陈旧的霉味，混合着纸张腐烂的气息。他知道，一旦翻开那个铁柜，有些事情就再也回不去了。

紧张的气氛笼罩着整个空间，林舟感到一阵焦虑涌上心头，但他强迫自己冷静下来。他深吸一口气，缓缓拉开铁柜的门。里面只有一份泛黄的文件夹，上面写着几个模糊的字。

## 内部工作卡

### 1. 状态卡
- 主角当前位置：旧城区档案馆封存区
- 主角当前伤势/疲劳：无
- 主角当前情绪：警惕而兴奋
- 主角当前目标：确认失踪档案去向
- 本章结束后的状态变化：掌握第一条直指火灾档案的线索
- 本章时间流逝：2小时
- 本章结束时时间点：第1天傍晚

### 2. 情节卡
- 核心冲突：进入封存区寻找档案
- 关键事件：发现火灾档案被抽走并获得备用钥匙
- 转折点：页脚出现陌生签名

### 3. 资源卡
- 获得：值班钥匙
- 消耗：管理员信任额度
- 损失：无
- 需带到下章的状态：值班钥匙仍可使用
- 伏笔：陌生签名与火灾档案的关系

### 4. 关系卡
- 主要人物：林舟、陈叔
- 人物变化：林舟与陈叔形成有限合作

### 5. 情绪弧线卡
- 起始情绪：谨慎
- 变化过程：怀疑转为兴奋
- 目标情绪：坚定
- 悬念强度：7

### 6. 承上启下卡
- 下章必须接住什么：继续追查签名来源
- 下章不能忘什么限制：值班钥匙仍在手里
- 需要回收的伏笔：陌生签名与火灾档案的关系
- 新埋下的伏笔：档案馆深处还藏着第二份证词
- 本章留下的最强钩子是什么：铁柜深处可能还有第二份证词
"""

SHORT_CHAPTER = """# 第1章

林舟走进档案馆。

## 内部工作卡

### 1. 状态卡
- 主角当前位置：档案馆
"""


def test_extract_scene_anchor_returns_last_n_chars():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td)
        ch = p / "001_test.md"
        ch.write_text(SAMPLE_CHAPTER, encoding="utf-8")

        ctx = NarrativeContext(p)
        anchor = ctx.extract_scene_anchor(ch, word_count=50)

        assert len(anchor) > 0
        assert "铁柜" in anchor or "文件夹" in anchor


def test_extract_scene_anchor_full_text_when_short():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td)
        ch = p / "001_test.md"
        ch.write_text(SHORT_CHAPTER, encoding="utf-8")

        ctx = NarrativeContext(p)
        anchor = ctx.extract_scene_anchor(ch, word_count=400)

        assert "林舟走进档案馆" in anchor


def test_generate_narrative_summary_keys():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td)
        ch = p / "001_test.md"
        ch.write_text(SAMPLE_CHAPTER, encoding="utf-8")

        ctx = NarrativeContext(p)
        summary = ctx.generate_narrative_summary(ch)

        assert "scene_location" in summary
        assert "characters_present" in summary
        assert "key_dialogue" in summary
        assert "emotion_tone" in summary
        assert "main_action" in summary
        assert "ending_hook" in summary
        assert len(summary["key_dialogue"]) <= 3


def test_generate_narrative_summary_detects_characters():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td)
        ch = p / "001_test.md"
        ch.write_text(SAMPLE_CHAPTER, encoding="utf-8")

        ctx = NarrativeContext(p)
        summary = ctx.generate_narrative_summary(ch)

        assert any("林舟" in c for c in summary["characters_present"])


def test_generate_narrative_summary_detects_emotion():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td)
        ch = p / "001_test.md"
        ch.write_text(SAMPLE_CHAPTER, encoding="utf-8")

        ctx = NarrativeContext(p)
        summary = ctx.generate_narrative_summary(ch)

        assert summary["emotion_tone"] == "紧张"


def test_save_and_load_chapter_context():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td)

        ctx = NarrativeContext(p)
        ctx.save_chapter_context(1, {"scene_location": "档案馆", "emotion_tone": "紧张"})

        context_file = p / "context" / "chapter_context.json"
        assert context_file.exists()

        data = json.loads(context_file.read_text(encoding="utf-8"))
        assert "chapter_1" in data
        assert data["chapter_1"]["scene_location"] == "档案馆"


def test_load_previous_context():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td)

        ctx = NarrativeContext(p)
        ctx.save_chapter_context(1, {"scene_location": "档案馆"})
        ctx.save_chapter_context(2, {"scene_location": "地下整理室"})

        prev = ctx.load_previous_context(3, lookback=2)

        assert "prev_1" in prev
        assert prev["prev_1"]["scene_location"] == "地下整理室"
        assert "prev_2" in prev
        assert prev["prev_2"]["scene_location"] == "档案馆"


def test_load_previous_context_no_file():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td)
        ctx = NarrativeContext(p)
        prev = ctx.load_previous_context(5)
        assert prev == {}


def test_extract_key_dialogues():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td)
        ch = p / "001_test.md"
        ch.write_text(SAMPLE_CHAPTER, encoding="utf-8")

        ctx = NarrativeContext(p)
        summary = ctx.generate_narrative_summary(ch)

        assert len(summary["key_dialogue"]) >= 1


def test_save_context_merges_with_existing():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td)

        ctx = NarrativeContext(p)
        ctx.save_chapter_context(1, {"emotion_tone": "谨慎"})
        ctx.save_chapter_context(1, {"emotion_tone": "紧张"})

        context_file = p / "context" / "chapter_context.json"
        data = json.loads(context_file.read_text(encoding="utf-8"))
        assert data["chapter_1"]["emotion_tone"] == "紧张"


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
