#!/usr/bin/env python3
"""上下文优化集成测试"""

from __future__ import annotations

import sys
import tempfile
import traceback
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from narrative_context import NarrativeContext
from state_tracker import StateTracker
from enhanced_validator import EnhancedValidator


def test_narrative_context():
    """测试叙事上下文模块"""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)

        chapter_dir = project_dir / "chapters" / "vol1"
        chapter_dir.mkdir(parents=True)

        test_chapter = chapter_dir / "ch01.md"
        test_chapter.write_text(
            """# 第1章 测试章节

这是测试章节的正文内容。
张三走进了房间，看到李四坐在那里。
"你好，"张三说。
李四抬起头，"你好，有什么事吗？"

## 内部工作卡

### 1. 状态卡
- 主角当前位置: 房间内
- 主角当前情绪: 平静
- 主角当前目标: 找李四谈话

### 2. 情节卡
- 本章关键事件: 张三找到李四

### 3. 资源卡
- 无

### 4. 关系卡
- 张三与李四: 同事

### 5. 情绪弧线卡
- 开始: 平静
- 结束: 平静

### 6. 承上启下卡
- 下章必须接住什么: 张三与李四的对话
- 本章留下的最强钩子: 李四似乎有心事
""",
            encoding="utf-8",
        )

        ctx = NarrativeContext(project_dir)
        anchor = ctx.extract_scene_anchor(test_chapter)

        assert len(anchor) > 0, "场景锚点不能为空"
        assert "张三" in anchor or "李四" in anchor, "场景锚点应包含人物"


def test_state_tracker():
    """测试状态跟踪模块"""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)

        chapter_dir = project_dir / "chapters" / "vol1"
        chapter_dir.mkdir(parents=True)

        test_chapter = chapter_dir / "ch01.md"
        test_chapter.write_text(
            """# 第1章 测试章节

张三走进了房间。

## 内部工作卡

### 1. 状态卡
- 主角当前位置: 房间内
- 主角当前情绪: 平静

### 2. 情节卡
- 本章关键事件: 张三进入房间

### 6. 承上启下卡
- 下章必须接住什么: 无
""",
            encoding="utf-8",
        )

        tracker = StateTracker(project_dir)
        tracker.update_character_state(test_chapter)
        tracker.track_plot_threads(test_chapter)

        assert len(tracker.state["characters"]) > 0, "应有人物状态"
        assert len(tracker.state["plot_threads"]) > 0, "应有事件线程"


def test_enhanced_validator():
    """测试增强验证器"""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)

        chapter_dir = project_dir / "chapters" / "vol1"
        chapter_dir.mkdir(parents=True)

        ch01 = chapter_dir / "ch01.md"
        ch01.write_text(
            """# 第1章

张三在房间里。

## 内部工作卡

### 1. 状态卡
- 主角当前位置: 房间内
- 主角当前情绪: 平静

### 6. 承上启下卡
- 下章必须接住什么: 无
""",
            encoding="utf-8",
        )

        ch02 = chapter_dir / "ch02.md"
        ch02.write_text(
            """# 第2章

张三走出房间。

## 内部工作卡

### 1. 状态卡
- 主角当前位置: 房间外
- 主角当前情绪: 平静

### 6. 承上启下卡
- 下章必须接住什么: 无
""",
            encoding="utf-8",
        )

        validator = EnhancedValidator(project_dir)
        issues = validator.validate_cross_chapter_consistency(ch02, ch01)

        assert isinstance(issues, list), "验证结果应为列表"


if __name__ == "__main__":
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
