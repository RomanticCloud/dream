#!/usr/bin/env python3
"""Adversarial tests for compact-context quality gates."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from body_dispatcher import BodyDispatcher
from chapter_validator import validate_chapter
from continuity_ledger import rebuild_ledger


def _state(project_dir: Path) -> None:
    (project_dir / "wizard_state.json").write_text(json.dumps({
        "basic_specs": {"chapter_length_min": 80, "chapter_length_max": 2000, "main_genres": ["都市异能"], "style_tone": "热血燃向"},
        "positioning": {"narrative_style": "第三人称有限视角"},
        "protagonist": {"gender": "男"},
        "naming": {"selected_book_title": "门禁测试"},
        "volume_architecture": {"chapters_per_volume": 10},
    }, ensure_ascii=False), encoding="utf-8")


def _chapter(project_dir: Path, ch: int, body: str, card: str) -> None:
    vol_dir = project_dir / "chapters" / "vol01"
    card_dir = vol_dir / "cards"
    card_dir.mkdir(parents=True, exist_ok=True)
    (vol_dir / f"ch{ch:02d}.md").write_text(body, encoding="utf-8")
    (card_dir / f"ch{ch:02d}_card.md").write_text(card, encoding="utf-8")


CARD1 = """## 内部工作卡

### 1. 状态卡
- 主角当前位置：旧仓库门口
- 主角当前伤势/疲劳：无
- 主角当前情绪：警惕
- 主角当前目标：判断来人是否可信
- 本章结束后的状态变化：收到警告
- 本章时间流逝：1小时
- 本章结束时时间点：第1天晚上

### 2. 情节卡
- 核心冲突：识别来人可信度
- 关键事件：收到不要相信来人的警告
- 转折点：陌生号码知道提示框
- 新埋伏笔：陌生号码身份未知
- 回收伏笔：无

### 3. 资源卡
- 获得：+1警告信息
- 消耗：-1小时
- 损失：无
- 需带到下章的状态：必须判断来人是否可信
- 伏笔：陌生号码身份未知

### 4. 关系卡
- 主要人物：陆明
- 人物变化：陆明更警惕

### 5. 情绪弧线卡
- 起始情绪：困惑
- 变化过程：困惑转为警惕
- 目标情绪：警惕
- 悬念强度：8

### 6. 承上启下卡
- 下章必须接住什么：不要相信今晚来的人
- 下章不能忘什么限制：陆明尚不确定蓝色提示框来源
- 需要回收的伏笔：陌生号码身份未知
- 新埋下的伏笔：来人可能不可信
- 本章留下的最强钩子是什么：不要相信今晚来的人
"""


def _card2(event: str = "陆明直接回家睡觉") -> str:
    return f"""## 内部工作卡

### 1. 状态卡
- 主角当前位置：家中
- 主角当前伤势/疲劳：无
- 主角当前情绪：放松
- 主角当前目标：休息
- 本章结束后的状态变化：忽略警告
- 本章时间流逝：1小时
- 本章结束时时间点：第1天深夜

### 2. 情节卡
- 核心冲突：无
- 关键事件：{event}
- 转折点：无
- 新埋伏笔：无
- 回收伏笔：无

### 3. 资源卡
- 获得：无
- 消耗：-1小时
- 损失：无
- 需带到下章的状态：无
- 伏笔：无

### 4. 关系卡
- 主要人物：陆明
- 人物变化：无

### 5. 情绪弧线卡
- 起始情绪：平静
- 变化过程：平静
- 目标情绪：放松
- 悬念强度：1

### 6. 承上启下卡
- 下章必须接住什么：无
- 下章不能忘什么限制：无
- 需要回收的伏笔：无
- 新埋下的伏笔：无
- 本章留下的最强钩子是什么：无
"""


def test_body_result_requires_execution_proof():
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)
        _state(project_dir)
        _chapter(project_dir, 1, "# 第1章\n\n## 正文\n\n旧仓库门口，陆明收到警告。", CARD1)
        rebuild_ledger(project_dir)
        dispatcher = BodyDispatcher(project_dir)
        result = dispatcher.dispatch(1, 2)
        valid_body = "# 第2章\n\n## 正文\n\n" + "陆明继续站在旧仓库门口等待来人。他反复查看陌生号码发来的警告，没有立刻相信任何一方，而是把手机屏幕调暗，靠着铁门观察雨幕里的脚步声。" * 2
        payload = {"status": "success", "chapter_body": valid_body}
        consumed = dispatcher.consume(1, 2, payload)
        assert consumed.status == "validation_failed"
        assert "context_manifest_id" in consumed.issues[0] or "files_read" in consumed.issues[0]
        request = json.loads(Path(result.request_file).read_text(encoding="utf-8"))
        payload.update({"context_manifest_id": request["context_manifest_id"], "files_read": request["required_context_files"]})
        consumed = dispatcher.consume(1, 2, payload)
        assert consumed.status == "body_ready"


def test_unhandled_strong_hook_blocks_chapter():
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)
        _state(project_dir)
        _chapter(project_dir, 1, "# 第1章\n\n## 正文\n\n旧仓库门口，陆明收到警告：不要相信今晚来的人。", CARD1)
        rebuild_ledger(project_dir)
        _chapter(project_dir, 2, "# 第2章\n\n## 正文\n\n陆明回家睡了一觉，第二天醒来后决定去吃早餐。他没有再想仓库和陌生号码。", _card2())
        result = validate_chapter(project_dir, 1, 2)
        assert not result.passed
        assert any("上章要求必须接住" in issue.message for issue in result.issues)
