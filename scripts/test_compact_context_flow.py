#!/usr/bin/env python3
"""Tests for compact-context generation flow."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from body_dispatcher import BodyDispatcher
from context_pack_builder import build_context_pack
from continuity_ledger import rebuild_ledger
from preflight_planner import build_preflight_plan


def _write_state(project_dir: Path) -> None:
    (project_dir / "wizard_state.json").write_text(json.dumps({
        "basic_specs": {
            "chapter_length_min": 800,
            "chapter_length_max": 1200,
            "main_genres": ["都市异能"],
            "style_tone": "热血燃向",
        },
        "positioning": {"narrative_style": "第三人称有限视角"},
        "protagonist": {"gender": "男"},
        "naming": {"selected_book_title": "测试之书"},
        "volume_architecture": {"chapters_per_volume": 10},
    }, ensure_ascii=False), encoding="utf-8")


def _write_chapter(project_dir: Path) -> None:
    vol_dir = project_dir / "chapters" / "vol01"
    card_dir = vol_dir / "cards"
    card_dir.mkdir(parents=True)
    (vol_dir / "ch01.md").write_text("""# 第1章 开端

## 正文

陆明站在旧仓库门口，雨水顺着铁皮棚往下砸。他刚刚确认蓝色提示框不是幻觉，手机却突然震动，陌生号码只发来一句话：不要相信今晚来的人。
""", encoding="utf-8")
    (card_dir / "ch01_card.md").write_text("""## 内部工作卡

### 1. 状态卡
- 主角当前位置：旧仓库门口
- 主角当前伤势/疲劳：轻微疲惫
- 主角当前情绪：警惕
- 主角当前目标：弄清蓝色提示框来源
- 本章结束后的状态变化：收到陌生警告
- 本章时间流逝：30分钟
- 本章结束时时间点：第1天晚上

### 2. 情节卡
- 核心冲突：确认异常提示是否真实
- 关键事件：陆明收到陌生警告
- 转折点：警告指向即将出现的人
- 新埋伏笔：陌生号码知道蓝色提示框
- 回收伏笔：无

### 3. 资源卡
- 获得：+1警告信息
- 消耗：-30分钟
- 损失：无
- 需带到下章的状态：陆明必须判断来人可信度
- 伏笔：陌生号码身份未知

### 4. 关系卡
- 主要人物：陆明
- 人物变化：陆明对外界更警惕

### 5. 情绪弧线卡
- 起始情绪：困惑
- 变化过程：困惑转为警惕
- 目标情绪：警惕
- 悬念强度：7

### 6. 承上启下卡
- 下章必须接住什么：陌生号码警告和即将出现的人
- 下章不能忘什么限制：陆明尚不确定蓝色提示框来源
- 需要回收的伏笔：陌生号码知道蓝色提示框
- 新埋下的伏笔：来人可能不可信
- 本章留下的最强钩子是什么：不要相信今晚来的人
""", encoding="utf-8")


def test_rebuild_context_preflight_and_body_dispatch():
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)
        _write_state(project_dir)
        _write_chapter(project_dir)

        ledger = rebuild_ledger(project_dir)
        assert ledger["open_constraints"]["must_handle"]

        pack = build_context_pack(project_dir, 1, 2)
        assert pack["context_id"].startswith("generation-context-v2-fast")
        assert pack["ledger"]["current_state"]["location"] == "旧仓库门口"

        preflight = build_preflight_plan(project_dir, 1, 2, pack)
        assert "陌生号码" in "".join(preflight["must_handle"])

        dispatch = BodyDispatcher(project_dir).dispatch(1, 2)
        assert dispatch.status == "body_prompt_ready"
        assert dispatch.chapters_loaded == 1
        prompt = Path(dispatch.prompt_file).read_text(encoding="utf-8")
        assert "compact-context" in prompt
        assert "不需要读取全部前文章节" in prompt
