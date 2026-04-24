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
from task_dispatcher import TaskChapterDispatcher, TaskResultError
from chapter_view import load_chapter_view


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def build_task_payload(root: Path, chapter_body: str, chapter_cards: str) -> dict:
    request = json.loads((root / "context" / "latest_task_request.json").read_text(encoding="utf-8"))
    manifest = json.loads(Path(request["manifest_file"]).read_text(encoding="utf-8"))
    return {
        "status": "success",
        "context_manifest_id": request["context_manifest_id"],
        "files_read": manifest["required_read_sequence"],
        "chapter_body": chapter_body,
        "chapter_cards": chapter_cards,
    }


def build_project(root: Path, with_outline: bool = True) -> None:
    write(root / "wizard_state.json", json.dumps({
        "basic_specs": {
            "chapter_length_min": 3500,
            "chapter_length_max": 4500,
            "style_tone": "悬疑推理",
            "main_genres": ["悬疑推理", "都市生活"],
        },
        "protagonist": {"gender": "男"},
        "positioning": {"narrative_style": "第三人称有限视角"},
        "naming": {"selected_book_title": "档案馆迷案"},
    }, ensure_ascii=False))

    write(root / "chapters" / "vol01" / "ch01.md", """# 第1章 起源

## 正文

林舟走进旧城区档案馆，发现火灾档案被抽走。
""")
    write(root / "chapters" / "vol01" / "cards" / "ch01_card.md", """## 内部工作卡

### 1. 状态卡
- 主角当前位置：档案馆
- 主角当前伤势/疲劳：无
- 主角当前情绪：警惕
- 主角当前目标：追查档案
- 本章结束后的状态变化：拿到第一条线索
- 本章时间流逝：1小时
- 本章结束时时间点：第1天傍晚

### 2. 情节卡
- 核心冲突：追查失踪档案
- 关键事件：发现火灾档案被抽走
- 转折点：确认档案被人为拿走
- 新埋伏笔：档案馆里还有别的知情人
- 回收伏笔：无

### 3. 资源卡
- 获得：+1线索
- 消耗：-1体力
- 损失：无
- 需带到下章的状态：线索尚未核验
- 伏笔：档案馆里还有别的知情人

### 4. 关系卡
- 主要人物：林舟
- 人物变化：暂无

### 5. 情绪弧线卡
- 起始情绪：警惕
- 变化过程：警惕转为专注
- 目标情绪：专注
- 悬念强度：6

### 6. 承上启下卡
- 下章必须接住什么：继续追查签名来源
- 下章不能忘什么限制：线索仍未核验
- 需要回收的伏笔：档案馆里还有别的知情人
- 新埋下的伏笔：签名背后另有其人
- 本章留下的最强钩子是什么：有人在暗中删除记录
""")

    write(root / "chapters" / "vol01" / "ch02.md", """# 第2章 线索

## 正文

林舟顺着签名查到许衡。
""")
    write(root / "chapters" / "vol01" / "cards" / "ch02_card.md", """## 内部工作卡

### 1. 状态卡
- 主角当前位置：档案馆地下室
- 主角当前伤势/疲劳：轻微疲劳
- 主角当前情绪：紧绷
- 主角当前目标：追查签名来源
- 本章结束后的状态变化：锁定许衡
- 本章时间流逝：1小时
- 本章结束时时间点：第1天晚上

### 2. 情节卡
- 核心冲突：锁定签名来源
- 关键事件：追查到许衡
- 转折点：发现许衡只是中间人
- 新埋伏笔：真正取档人仍未现身
- 回收伏笔：签名背后另有其人

### 3. 资源卡
- 获得：+1新地址
- 消耗：-1人情
- 损失：无
- 需带到下章的状态：新地址待追查
- 伏笔：真正取档人仍未现身

### 4. 关系卡
- 主要人物：林舟、许衡
- 人物变化：林舟确认许衡并非核心人物

### 5. 情绪弧线卡
- 起始情绪：紧绷
- 变化过程：紧绷转为冷静
- 目标情绪：冷静
- 悬念强度：7

### 6. 承上启下卡
- 下章必须接住什么：继续追查真正取档人
- 下章不能忘什么限制：许衡提供的信息有限
- 需要回收的伏笔：真正取档人仍未现身
- 新埋下的伏笔：第二份证词即将出现
- 本章留下的最强钩子是什么：新地址可能通向更深的秘密
""")

    write(root / "chapters" / "vol02" / "ch01.md", """# 第3章 真相

## 正文

陈叔终于承认当年的事。
""")
    write(root / "chapters" / "vol02" / "cards" / "ch01_card.md", """## 内部工作卡

### 1. 状态卡
- 主角当前位置：档案馆休息室
- 主角当前伤势/疲劳：无
- 主角当前情绪：冷静
- 主角当前目标：逼近真相
- 本章结束后的状态变化：获得关键证词
- 本章时间流逝：2小时
- 本章结束时时间点：第2天清晨

### 2. 情节卡
- 核心冲突：逼近真相
- 关键事件：陈叔承认当年的事
- 转折点：第二份证词出现
- 新埋伏笔：更高层级的人物现身
- 回收伏笔：第二份证词即将出现

### 3. 资源卡
- 获得：+1关键证词
- 消耗：-1陈叔信任
- 损失：无
- 需带到下章的状态：关键证词在手
- 伏笔：更高层级的人物现身

### 4. 关系卡
- 主要人物：林舟、陈叔
- 人物变化：陈叔从隐瞒转为坦白

### 5. 情绪弧线卡
- 起始情绪：压抑
- 变化过程：压抑转为冷静
- 目标情绪：冷静
- 悬念强度：8

### 6. 承上启下卡
- 下章必须接住什么：追查关键证词背后的势力
- 下章不能忘什么限制：证词仍不完整
- 需要回收的伏笔：更高层级的人物现身
- 新埋下的伏笔：证词背面留下新地址
- 本章留下的最强钩子是什么：新地址直指真正嫌疑人
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
        assert "3500-4500字" in prompt
        assert "低于 2975 字直接失败" in prompt
        assert "当前卷纲约束" in prompt
        assert "主线续写约束" in prompt
        assert "上一章承接要求" in prompt
        assert "最近主线推进摘要" in prompt
        assert "主角当前伤势/疲劳" in prompt
        assert "需带到下章的状态" in prompt
        assert "下章不能忘什么限制" in prompt


def test_build_subagent_prompt_uses_custom_word_range():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        build_project(root)
        payload = json.loads((root / "wizard_state.json").read_text(encoding="utf-8"))
        payload["basic_specs"]["chapter_length_min"] = 2000
        payload["basic_specs"]["chapter_length_max"] = 2500
        write(root / "wizard_state.json", json.dumps(payload, ensure_ascii=False))

        gen = SubagentChapterGenerator(root)
        chapters = gen.load_all_previous_chapters(vol_num=1, ch_num=2)
        prompt = gen.build_subagent_prompt(
            previous_chapters=chapters,
            project_config=payload,
            current_chapter_info={"vol": 1, "ch": 2},
        )

        assert "2000-2500字" in prompt
        assert "低于 1700 字直接失败" in prompt


def test_build_subagent_prompt_uses_mid_short_word_range():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        build_project(root)
        payload = json.loads((root / "wizard_state.json").read_text(encoding="utf-8"))
        payload["basic_specs"]["chapter_length_min"] = 2500
        payload["basic_specs"]["chapter_length_max"] = 3500
        write(root / "wizard_state.json", json.dumps(payload, ensure_ascii=False))

        gen = SubagentChapterGenerator(root)
        chapters = gen.load_all_previous_chapters(vol_num=1, ch_num=2)
        prompt = gen.build_subagent_prompt(
            previous_chapters=chapters,
            project_config=payload,
            current_chapter_info={"vol": 1, "ch": 2},
        )

        assert "2500-3500字" in prompt
        assert "低于 2125 字直接失败" in prompt


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
        assert "当前卷纲约束" in prompt
        assert "当前卷目标" in prompt


def test_build_subagent_prompt_with_revision_tasks():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        build_project(root)
        write(root / "REVISION_STATE.json", json.dumps({
            "chapter": {
                "vol01_ch002": {
                    "status": "pending_rewrite_card",
                    "fix_plan": {},
                    "tasks": [
                        {
                            "type": "field_invalid",
                            "severity": "error",
                            "card": "2. 情节卡",
                            "field": "关键事件",
                            "message": "字段非法",
                            "instruction": "补全关键事件并与正文一致。",
                            "fix_method": "rewrite_card"
                        }
                    ]
                }
            },
            "volume": {}
        }, ensure_ascii=False))

        gen = SubagentChapterGenerator(root)
        chapters = gen.load_all_previous_chapters(vol_num=1, ch_num=2)
        config = json.loads((root / "wizard_state.json").read_text(encoding="utf-8"))

        prompt = gen.build_subagent_prompt(
            previous_chapters=chapters,
            project_config=config,
            current_chapter_info={"vol": 1, "ch": 2},
            revision_tasks=json.loads((root / "REVISION_STATE.json").read_text(encoding="utf-8"))["chapter"]["vol01_ch002"]["tasks"],
        )

        assert "本轮修正要求" in prompt
        assert "补全关键事件并与正文一致。" in prompt
        assert "rewrite_card" in prompt
        assert "本轮修正模式：重写工作卡" in prompt
        assert "目标=work_cards_only" in prompt
        assert "阻塞=是" in prompt
        assert "保留约束：" in prompt


def test_dispatch_chapter_generation():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        build_project(root)

        gen = SubagentChapterGenerator(root)
        result = gen.dispatch_chapter_generation(vol_num=2, ch_num=2)

        assert result["status"] == "prompt_ready"
        assert result["chapters_loaded"] == 3
        assert result["required_files"] >= 6
        assert result["prompt_length"] > 0
        assert result["generation_time"] >= 0

        prompt_file = Path(result["prompt_file"])
        manifest_file = Path(result["manifest_file"])
        assert prompt_file.exists()
        assert manifest_file.exists()
        prompt_text = prompt_file.read_text(encoding="utf-8")
        assert "档案馆迷案" in prompt_text
        assert str(manifest_file) in prompt_text
        assert "required_read_sequence" in prompt_text
        manifest_payload = json.loads(manifest_file.read_text(encoding="utf-8"))
        assert manifest_payload["counts"]["previous_chapters"] == 3
        assert manifest_payload["strategy"] == "subagent_read_all_previous"


def test_chapter_view_uses_split_files():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        build_project(root)

        view = load_chapter_view(root, 1, 1)
        assert view.has_body_marker is True
        assert view.has_inline_card is False
        assert view.has_separate_card is True
        assert view.is_split_valid is True
        assert "## 内部工作卡" not in view.body_text
        assert "## 内部工作卡" in view.card_text


def test_task_dispatcher_writes_request_file():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        build_project(root)

        dispatcher = TaskChapterDispatcher(root)
        result = dispatcher.dispatch(2, 2)

        assert result.status == "task_request_ready"
        assert Path(result.prompt_file).exists()
        assert Path(result.request_file).exists()
        assert Path(result.manifest_file).exists()
        payload = json.loads(Path(result.request_file).read_text(encoding="utf-8"))
        assert payload["mode"] == "task_subagent"
        assert payload["strategy"] == "subagent_read_all_previous"
        assert payload["requirements"]["split_files"] is True
        assert payload["requirements"]["read_all_previous"] is True
        assert payload["context_manifest_id"] == result.context_manifest_id


def test_task_dispatcher_consumes_valid_task_result():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        build_project(root)
        payload_state = json.loads((root / "wizard_state.json").read_text(encoding="utf-8"))
        payload_state["basic_specs"]["chapter_length_min"] = 10
        payload_state["basic_specs"]["chapter_length_max"] = 5000
        write(root / "wizard_state.json", json.dumps(payload_state, ensure_ascii=False))

        dispatcher = TaskChapterDispatcher(root)
        dispatcher.dispatch(2, 2)
        payload = build_task_payload(
            root,
            "# 第2章 新线索\n\n## 正文\n\n林舟在雨夜里确认了第二个地址。\n",
            "## 内部工作卡\n\n### 1. 状态卡\n- 主角当前位置：旧城区\n- 主角当前伤势/疲劳：轻微疲劳\n- 主角当前情绪：紧绷\n- 主角当前目标：确认第二个地址\n- 本章结束后的状态变化：锁定新目标\n- 本章时间流逝：1小时\n- 本章结束时时间点：第2天深夜\n\n### 2. 情节卡\n- 核心冲突：追查新地址\n- 关键事件：确认第二个地址\n- 转折点：发现地址被监视\n- 新埋伏笔：监视者身份未知\n- 回收伏笔：新地址可能通向更深的秘密\n\n### 3. 资源卡\n- 获得：+1新地址\n- 消耗：-1体力\n- 损失：无\n- 需带到下章的状态：地址已确认\n- 伏笔：监视者身份未知\n\n### 4. 关系卡\n- 主要人物：林舟\n- 人物变化：暂无\n\n### 5. 情绪弧线卡\n- 起始情绪：谨慎\n- 变化过程：谨慎转为紧绷\n- 目标情绪：警惕\n- 悬念强度：6\n\n### 6. 承上启下卡\n- 下章必须接住什么：追查监视者\n- 下章不能忘什么限制：地址只确认其一\n- 需要回收的伏笔：监视者身份未知\n- 新埋下的伏笔：监视者留下了符号\n- 本章留下的最强钩子是什么：有人先一步到过现场\n",
        )

        result = dispatcher.consume_task_result(2, 2, payload)
        assert result.status == "chapter_ready"
        assert result.validation_passed is True
        view = load_chapter_view(root, 2, 2)
        assert "## 内部工作卡" not in view.body_text
        assert view.card_text.startswith("## 内部工作卡")


def test_task_dispatcher_rejects_inline_card_in_body():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        build_project(root)

        dispatcher = TaskChapterDispatcher(root)
        dispatcher.dispatch(2, 2)
        payload = build_task_payload(
            root,
            "# 第2章\n\n## 正文\n\n正文\n\n## 内部工作卡\n",
            "## 内部工作卡\n\n### 1. 状态卡\n- 主角当前位置：旧城区\n",
        )
        try:
            dispatcher.consume_task_result(2, 2, payload)
            raise AssertionError("expected TaskResultError")
        except TaskResultError as exc:
            assert "chapter_body" in str(exc)


def test_task_dispatcher_rejects_incomplete_files_read():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        build_project(root)

        dispatcher = TaskChapterDispatcher(root)
        dispatch = dispatcher.dispatch(2, 2)
        request = json.loads(Path(dispatch.request_file).read_text(encoding="utf-8"))
        payload = {
            "status": "success",
            "context_manifest_id": request["context_manifest_id"],
            "files_read": [],
            "chapter_body": "# 第2章\n\n## 正文\n\n正文\n",
            "chapter_cards": "## 内部工作卡\n\n### 1. 状态卡\n- 主角当前位置：旧城区\n",
        }

        try:
            dispatcher.consume_task_result(2, 2, payload)
            raise AssertionError("expected TaskResultError")
        except TaskResultError as exc:
            assert "files_read" in str(exc)


def test_dispatch_chapter_generation_includes_revision_tasks():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        build_project(root)
        write(root / "REVISION_STATE.json", json.dumps({
            "chapter": {
                "vol02_ch002": {
                    "status": "pending_polish",
                    "fix_plan": {},
                    "tasks": [
                        {
                            "type": "resource_format_weak",
                            "severity": "warning",
                            "card": "3. 资源卡",
                            "field": "获得",
                            "message": "建议使用 +/- 数字格式",
                            "instruction": "将获得字段改为 +1资源 这类格式。",
                            "fix_method": "polish"
                        }
                    ]
                }
            },
            "volume": {}
        }, ensure_ascii=False))

        gen = SubagentChapterGenerator(root)
        result = gen.dispatch_chapter_generation(vol_num=2, ch_num=2)
        prompt_text = Path(result["prompt_file"]).read_text(encoding="utf-8")

        assert "本轮修正要求" in prompt_text
        assert "将获得字段改为 +1资源 这类格式。" in prompt_text
        assert "本轮修正模式：局部润色" in prompt_text
        assert "目标=local_patch" in prompt_text


def test_dispatch_chapter_generation_includes_regenerate_mode():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        build_project(root)
        write(root / "REVISION_STATE.json", json.dumps({
            "chapter": {
                "vol02_ch002": {
                    "status": "pending_regenerate",
                    "fix_plan": {},
                    "tasks": [
                        {
                            "type": "word_count_low",
                            "severity": "error",
                            "card": "",
                            "field": "",
                            "message": "字数过低",
                            "instruction": "整章重写并提升正文字数到质量门槛以上。",
                            "fix_method": "regenerate"
                        }
                    ]
                }
            },
            "volume": {}
        }, ensure_ascii=False))

        gen = SubagentChapterGenerator(root)
        result = gen.dispatch_chapter_generation(vol_num=2, ch_num=2)
        prompt_text = Path(result["prompt_file"]).read_text(encoding="utf-8")

        assert "本轮修正模式：整章重写" in prompt_text
        assert "整章重写并提升正文字数到质量门槛以上。" in prompt_text
        assert "目标=full_chapter" in prompt_text


def test_dispatch_chapter_generation_error_no_previous():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        write(root / "wizard_state.json", "{}")
        write(root / "chapters" / "vol01" / "ch001.md", "# 第1章\n\ncontent")

        gen = SubagentChapterGenerator(root)
        result = gen.dispatch_chapter_generation(vol_num=1, ch_num=2)

        assert result["status"] == "error"
        assert "主角性别" in result["error"]


def test_dispatch_chapter_generation_error_chapter1():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        write(root / "wizard_state.json", "{}")

        gen = SubagentChapterGenerator(root)
        result = gen.dispatch_chapter_generation(vol_num=1, ch_num=1)

        assert result["status"] == "error"
        assert "主角性别" in result["error"]


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
        write(root / "chapters" / "vol03" / "ch01.md", "# 第5章 新篇章\n\nnew content")
        
        gen = SubagentChapterGenerator(root)
        chapters = gen.load_all_previous_chapters(vol_num=3, ch_num=2)
        assert len(chapters) == 4
        assert chapters[-1]["vol"] == 3 and chapters[-1]["ch"] == 1


def test_load_all_previous_chapters_legacy_filename():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        write(root / "wizard_state.json", "{}")
        write(root / "chapters" / "vol01" / "001_第1章.md", "# 第1章\n\n旧格式正文")

        gen = SubagentChapterGenerator(root)
        chapters = gen.load_all_previous_chapters(vol_num=1, ch_num=2)

        assert len(chapters) == 1
        assert chapters[0]["ch"] == 1


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
