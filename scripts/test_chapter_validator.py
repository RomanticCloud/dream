#!/usr/bin/env python3
"""Tests for chapter_validator field value checks."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from chapter_validator import validate_chapter


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def build_project(root: Path, chapter_body: str) -> Path:
    write(root / "wizard_state.json", json.dumps({
        "basic_specs": {
            "chapter_length_min": 10,
            "chapter_length_max": 5000,
            "main_genres": ["都市生活"],
        }
    }, ensure_ascii=False))
    chapter_path = root / "chapters" / "vol01" / "ch01.md"
    if "## 内部工作卡" in chapter_body:
        body, cards = chapter_body.split("## 内部工作卡", 1)
        write(chapter_path, body.rstrip() + "\n")
        write(root / "chapters" / "vol01" / "cards" / "ch01_card.md", "## 内部工作卡" + cards)
    else:
        write(chapter_path, chapter_body)
    return chapter_path


def build_power_project(root: Path, chapter_body: str) -> Path:
    write(root / "wizard_state.json", json.dumps({
        "basic_specs": {
            "chapter_length_min": 10,
            "chapter_length_max": 5000,
            "main_genres": ["都市高武"],
        }
    }, ensure_ascii=False))
    chapter_path = root / "chapters" / "vol01" / "ch01.md"
    if "## 内部工作卡" in chapter_body:
        body, cards = chapter_body.split("## 内部工作卡", 1)
        write(chapter_path, body.rstrip() + "\n")
        write(root / "chapters" / "vol01" / "cards" / "ch01_card.md", "## 内部工作卡" + cards)
    else:
        write(chapter_path, chapter_body)
    return chapter_path


VALID_CHAPTER = """# 第1章

## 正文

张三走进档案室，确认线索还在。

## 内部工作卡

### 1. 状态卡
- 主角当前位置：档案室
- 主角当前伤势/疲劳：无
- 主角当前情绪：紧张
- 主角当前目标：确认线索
- 本章结束后的状态变化：掌握了新线索
- 本章时间流逝：2小时
- 本章结束时时间点：第1天傍晚

### 2. 情节卡
- 核心冲突：必须尽快找到线索
- 关键事件：成功找到线索
- 转折点：线索指向更深层问题
- 新埋伏笔：幕后人另有安排
- 回收伏笔：无

### 3. 资源卡
- 获得：+1线索
- 消耗：-1人情
- 损失：无
- 需带到下章的状态：线索仍需保密
- 伏笔：幕后人另有安排

### 4. 关系卡
- 主要人物：张三、李四
- 人物变化：张三开始怀疑李四

### 5. 情绪弧线卡
- 起始情绪：谨慎
- 变化过程：谨慎转为紧张
- 目标情绪：专注
- 悬念强度：7

### 6. 承上启下卡
- 下章必须接住什么：追查幕后人
- 下章不能忘什么限制：线索仍需保密
- 需要回收的伏笔：幕后人另有安排
- 新埋下的伏笔：档案室还有第二层暗格
- 本章留下的最强钩子是什么：第二层暗格里还有别的文件
"""


VALID_POWER_CHAPTER = """# 第1章

## 正文

林舟在擂台上正面迎战高一级对手，最终险胜。

## 内部工作卡

### 1. 状态卡
- 主角当前境界：淬体三重
- 主角当前位置：擂台
- 主角当前伤势/疲劳：轻伤
- 主角当前情绪：紧绷
- 主角当前目标：赢下擂台赛
- 本章结束后的状态变化：赢下擂台赛并暴露一张底牌
- 本章时间流逝：30分钟
- 本章结束时时间点：第1天傍晚

### 2. 战力卡
- 本章主要交手对象：赵烈
- 对方层级：淬体四重
- 主角是否越级：是
- 越级是否合理：依靠提前布置的陷阱与底牌完成反制
- 是否暴露新底牌：是
- 具体战力损耗比例：-30%
- 使用的底牌名称：燃命剑/震岳符
- 本章战斗结果的后续影响：赵烈所属势力开始注意主角

### 3. 资源卡
- 获得：+1擂台积分
- 消耗：-1震岳符
- 损失：-20药粉
- 需带到下章的状态：主角轻伤未愈
- 伏笔：赵烈背后还有更强的师兄

### 4. 关系卡
- 主要人物：林舟、赵烈
- 人物变化：赵烈对林舟由轻视转为忌惮

### 5. 情绪弧线卡
- 起始情绪：压抑
- 变化过程：压抑转为决绝
- 目标情绪：警惕
- 悬念强度：8

### 6. 承上启下卡
- 下章必须接住什么：处理伤势并应对赵烈背后的势力
- 下章不能忘什么限制：燃命剑短时间内不可再用
- 需要回收的伏笔：赵烈背后还有更强的师兄
- 新埋下的伏笔：观众席上还有人在暗中记录战斗
- 本章留下的最强钩子是什么：更高境界的对手已经盯上主角
"""


def test_validate_chapter_accepts_valid_field_values():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        build_project(root, VALID_CHAPTER)
        result = validate_chapter(root, 1, 1)
        assert result.passed


def test_validate_chapter_rejects_invalid_suspense_strength():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        build_project(root, VALID_CHAPTER.replace("- 悬念强度：7", "- 悬念强度：11"))
        result = validate_chapter(root, 1, 1)
        assert not result.passed
        assert any("悬念强度" in issue.message for issue in result.issues)
        assert any(task["type"] == "field_invalid" and task["field"] == "悬念强度" for task in result.revision_tasks)


def test_validate_chapter_warns_on_non_delta_resource_value():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        build_project(root, VALID_CHAPTER.replace("- 获得：+1线索", "- 获得：线索一条"))
        result = validate_chapter(root, 1, 1)
        assert result.passed
        assert any(issue.type == "warning" and "获得" in issue.message for issue in result.issues)
        assert any(task["type"] == "resource_format_weak" and task["field"] == "获得" for task in result.revision_tasks)


def test_validate_chapter_requires_carry_over_field():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        build_project(root, VALID_CHAPTER.replace("- 下章必须接住什么：追查幕后人", "- 下章必须接住什么："))
        result = validate_chapter(root, 1, 1)
        assert not result.passed
        assert any("下章必须接住什么" in issue.message for issue in result.issues)
        assert any(task["type"] == "field_empty" and task["field"] == "下章必须接住什么" for task in result.revision_tasks)


def test_validate_power_chapter_accepts_valid_combat_fields():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        build_power_project(root, VALID_POWER_CHAPTER)
        result = validate_chapter(root, 1, 1)
        assert result.passed


def test_validate_power_chapter_rejects_invalid_yes_no():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        body = VALID_POWER_CHAPTER.replace("- 主角是否越级：是", "- 主角是否越级：可能")
        build_power_project(root, body)
        result = validate_chapter(root, 1, 1)
        assert not result.passed
        assert any("主角是否越级" in issue.message for issue in result.issues)
        assert any(task["type"] == "power_card_invalid" and task["field"] == "主角是否越级" for task in result.revision_tasks)


def test_validate_power_chapter_rejects_invalid_loss_ratio():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        body = VALID_POWER_CHAPTER.replace("- 具体战力损耗比例：-30%", "- 具体战力损耗比例：三成")
        build_power_project(root, body)
        result = validate_chapter(root, 1, 1)
        assert not result.passed
        assert any("具体战力损耗比例" in issue.message for issue in result.issues)
        assert any(task["type"] == "power_card_invalid" and task["field"] == "具体战力损耗比例" for task in result.revision_tasks)


def test_validate_power_chapter_requires_reason_when_crossing():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        body = VALID_POWER_CHAPTER.replace(
            "- 越级是否合理：依靠提前布置的陷阱与底牌完成反制",
            "- 越级是否合理：",
        )
        build_power_project(root, body)
        result = validate_chapter(root, 1, 1)
        assert not result.passed
        assert any("越级是否合理" in issue.message for issue in result.issues)
        assert any(task["type"] == "field_empty" and task["field"] == "越级是否合理" for task in result.revision_tasks)


def test_validate_chapter_builds_structured_revision_tasks():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        body = VALID_CHAPTER.replace("## 正文", "## 错误正文", 1)
        build_project(root, body)
        result = validate_chapter(root, 1, 1)

        assert not result.passed
        assert result.revision_tasks
        task = result.revision_tasks[0]
        assert "type" in task
        assert "severity" in task
        assert "message" in task
        assert "instruction" in task
        assert "fix_method" in task
        assert "scope" in task
        assert "rewrite_target" in task
        assert "preserve_constraints" in task
        assert "blocking" in task
        assert "priority" in task


def test_validate_chapter_fails_when_word_range_missing():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        write(root / "wizard_state.json", json.dumps({"basic_specs": {"main_genres": ["都市生活"]}}, ensure_ascii=False))
        write(root / "chapters" / "vol01" / "ch01.md", "# 第1章\n\n## 正文\n\n张三确认线索还在。")
        result = validate_chapter(root, 1, 1)

        assert not result.passed
        assert any("chapter_length_min" in issue.message for issue in result.issues)


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
