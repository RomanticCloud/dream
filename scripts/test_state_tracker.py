#!/usr/bin/env python3
"""Tests for state_tracker.py"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from state_tracker import StateTracker


SAMPLE_CHAPTER_1 = """# 第1章

林舟走进旧城区档案馆，发现火灾档案被抽走，只剩下残缺目录页。他借着整理旧报纸的机会进入封存区，沿着灰尘的断痕找到被人翻动过的铁柜。管理员陈叔神色复杂，却还是低声提醒他昨晚有人来过。林舟没有追问，只是把注意力放回那页缺失的目录。

陈叔说："你最好别再查下去了。"林舟沉默片刻，回答道："我已经没有退路了。"他转身走向封存区深处。

## 内部工作卡

### 1. 状态卡
- 主角当前位置：旧城区档案馆封存区
- 主角当前情绪：警惕而兴奋
- 主角当前目标：确认失踪档案去向
- 本章结束后的状态变化：掌握第一条直指火灾档案的线索

### 2. 情节卡
- 核心冲突：进入封存区寻找档案
- 关键事件：发现火灾档案被抽走并获得备用钥匙
- 转折点：页脚出现陌生签名
- 新埋伏笔：陌生签名与火灾档案的关系

### 3. 资源卡
- 获得：值班钥匙
- 消耗：管理员信任额度
- 伏笔：档案馆深处还藏着第二份证词

### 4. 关系卡
- 主要人物：林舟、陈叔
- 人物变化：林舟与陈叔形成有限合作

### 5. 情感弧卡
- 起始情绪：谨慎
- 变化过程：怀疑转为兴奋
- 目标情绪：坚定

### 6. 承上启下卡
- 承接：继续追查签名来源
- 铺垫：档案馆深处还藏着第二份证词
"""

SAMPLE_CHAPTER_2 = """# 第2章

林舟找到签名对应的登记人，发现是一个已经死亡的档案管理员。陈叔被迫透露当年有人来封存过类似档案。

陈叔说："那个人叫老张，三年前就去世了。"林舟皱起眉头，追问："他有家人吗？"

## 内部工作卡

### 1. 状态卡
- 主角当前位置：旧城区档案馆办公室
- 主角当前情绪：困惑但坚定
- 主角当前目标：找到老张的线索

### 2. 情节卡
- 核心冲突：老张已死线索中断
- 关键事件：从陈叔处获得老张家属信息
- 转折点：发现老张的笔记
- 回收伏笔：陌生签名与火灾档案的关系
- 新埋伏笔：老张的笔记中提到的月光计划

### 3. 资源卡
- 获得：老张家属地址
- 消耗：继续消耗陈叔信任

### 4. 关系卡
- 主要人物：林舟、陈叔
- 人物变化：陈叔从抗拒转为配合

### 5. 情感弧卡
- 起始情绪：兴奋
- 变化过程：兴奋转为困惑
- 目标情绪：坚定

### 6. 承上启下卡
- 承接：前往老张家调查
- 铺垫：月光计划可能与火灾有直接关联
"""

EMPTY_CHAPTER = """# 第3章

林舟走在街上。

## 内部工作卡

### 1. 状态卡
- 主角当前位置：街上
"""


def test_init_creates_state_file():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td)
        tracker = StateTracker(p)

        assert tracker.state_file.exists()
        assert tracker.state["characters"] == {}
        assert tracker.state["plot_threads"] == []
        assert tracker.state["foreshadowing"] == []
        assert tracker.state["last_updated_chapter"] == 0


def test_init_loads_existing_state():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td)
        ctx_dir = p / "context"
        ctx_dir.mkdir()
        state_file = ctx_dir / "state_tracker.json"
        state_file.write_text(
            json.dumps({"characters": {"林舟": {"states": []}}, "plot_threads": [], "foreshadowing": [], "last_updated_chapter": 5}),
            encoding="utf-8",
        )

        tracker = StateTracker(p)
        assert "林舟" in tracker.state["characters"]
        assert tracker.state["last_updated_chapter"] == 5


def test_update_character_state_extracts_characters():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td)
        ch = p / "001_test.md"
        ch.write_text(SAMPLE_CHAPTER_1, encoding="utf-8")

        tracker = StateTracker(p)
        tracker.update_character_state(ch)

        chars = tracker.state["characters"]
        assert "林舟" in chars
        # 陈叔说 匹配3字模式，陈叔 单独不在对话模式中
        assert "陈叔说" in chars


def test_update_character_state_sets_main_char_details():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td)
        ch = p / "001_test.md"
        ch.write_text(SAMPLE_CHAPTER_1, encoding="utf-8")

        tracker = StateTracker(p)
        tracker.update_character_state(ch)

        linzhou = tracker.state["characters"]["林舟"]
        latest = linzhou["states"][-1]
        assert latest["location"] == "旧城区档案馆封存区"
        assert latest["emotion"] == "警惕而兴奋"
        assert latest["goal"] == "确认失踪档案去向"


def test_update_character_state_appends_relationship_changes():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td)
        ch = p / "001_test.md"
        ch.write_text(SAMPLE_CHAPTER_1, encoding="utf-8")

        tracker = StateTracker(p)
        tracker.update_character_state(ch)

        linzhou = tracker.state["characters"]["林舟"]
        latest = linzhou["states"][-1]
        assert any("有限合作" in c for c in latest["relationship_changes"])


def test_track_plot_threads():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td)
        ch = p / "001_test.md"
        ch.write_text(SAMPLE_CHAPTER_1, encoding="utf-8")

        tracker = StateTracker(p)
        tracker.track_plot_threads(ch)

        threads = tracker.state["plot_threads"]
        assert len(threads) == 1
        assert threads[0]["chapter"] == "001_test.md"
        assert len(threads[0]["events"]) > 0
        assert len(threads[0]["unresolved_conflicts"]) > 0


def test_track_plot_threads_caps_at_10():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td)
        tracker = StateTracker(p)

        for i in range(12):
            ch = p / f"{i:03d}_test.md"
            ch.write_text(SAMPLE_CHAPTER_1, encoding="utf-8")
            tracker.track_plot_threads(ch)

        assert len(tracker.state["plot_threads"]) == 10


def test_track_foreshadowing_plants():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td)
        ch = p / "001_test.md"
        ch.write_text(SAMPLE_CHAPTER_1, encoding="utf-8")

        tracker = StateTracker(p)
        tracker.track_foreshadowing(ch)

        foreshadowing = tracker.state["foreshadowing"]
        assert len(foreshadowing) >= 1
        planted = [f for f in foreshadowing if f["status"] == "planted"]
        assert len(planted) >= 1


def test_track_foreshadowing_resolves():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td)
        ch1 = p / "001_test.md"
        ch1.write_text(SAMPLE_CHAPTER_1, encoding="utf-8")
        ch2 = p / "002_test.md"
        ch2.write_text(SAMPLE_CHAPTER_2, encoding="utf-8")

        tracker = StateTracker(p)
        tracker.track_foreshadowing(ch1)
        tracker.track_foreshadowing(ch2)

        foreshadowing = tracker.state["foreshadowing"]
        resolved = [f for f in foreshadowing if f["status"] == "resolved"]
        assert len(resolved) >= 1
        assert resolved[0]["resolved_chapter"] == "002_test.md"


def test_get_state_summary_with_data():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td)
        ch1 = p / "001_test.md"
        ch1.write_text(SAMPLE_CHAPTER_1, encoding="utf-8")
        ch2 = p / "002_test.md"
        ch2.write_text(SAMPLE_CHAPTER_2, encoding="utf-8")

        tracker = StateTracker(p)
        tracker.update_character_state(ch1)
        tracker.update_character_state(ch2)
        tracker.track_plot_threads(ch1)
        tracker.track_plot_threads(ch2)
        tracker.track_foreshadowing(ch1)
        tracker.track_foreshadowing(ch2)

        summary = tracker.get_state_summary(3)

        assert "人物当前状态" in summary
        assert "林舟" in summary
        assert "最近事件" in summary


def test_get_state_summary_empty():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td)
        tracker = StateTracker(p)
        summary = tracker.get_state_summary(1)
        assert summary == ""


def test_update_last_chapter():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td)
        tracker = StateTracker(p)
        tracker.update_last_chapter(5)
        assert tracker.state["last_updated_chapter"] == 5

        # reload
        tracker2 = StateTracker(p)
        assert tracker2.state["last_updated_chapter"] == 5


def test_is_similar_foreshadowing():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td)
        tracker = StateTracker(p)

        assert tracker._is_similar_foreshadowing("陌生签名与火灾", "陌生签名与火灾档案的关系")
        assert not tracker._is_similar_foreshadowing("完全无关的文本", "另一个无关的文本")


def test_state_persists_across_reloads():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td)
        ch = p / "001_test.md"
        ch.write_text(SAMPLE_CHAPTER_1, encoding="utf-8")

        tracker1 = StateTracker(p)
        tracker1.update_character_state(ch)
        tracker1.track_plot_threads(ch)

        tracker2 = StateTracker(p)
        assert "林舟" in tracker2.state["characters"]
        assert len(tracker2.state["plot_threads"]) == 1


def test_update_character_state_empty_cards():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td)
        ch = p / "003_test.md"
        ch.write_text(EMPTY_CHAPTER, encoding="utf-8")

        tracker = StateTracker(p)
        tracker.update_character_state(ch)
        # Should not crash, just no characters extracted from dialogue
        # since there's no dialogue pattern in the body


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
