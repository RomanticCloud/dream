#!/usr/bin/env python3
"""
子代理章节生成模块 - 使用子代理生成章节正文
将所有前文章节完整加载到子代理的独立上下文中，从根本上解决漂移问题
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Optional

from card_names import CARRY_CARD, EMOTION_CARD, PLOT_CARD
from card_fields import (
    FIELD_CARRY_HOOK,
    FIELD_CARRY_LIMIT,
    FIELD_CARRY_MUST,
    FIELD_CARRY_PAYOFF,
    FIELD_CARRY_SETUP,
    FIELD_EMOTION_PROCESS,
    FIELD_EMOTION_START,
    FIELD_EMOTION_SUSPENSE,
    FIELD_EMOTION_TARGET,
    FIELD_PLOT_CONFLICT,
    FIELD_PLOT_EVENT,
    FIELD_PLOT_PAYOFF,
    FIELD_PLOT_SETUP,
    FIELD_PLOT_TURN,
    FIELD_RELATION_CHANGE,
    FIELD_RELATION_MAIN,
    FIELD_RESOURCE_CARRY,
    FIELD_RESOURCE_GAIN,
    FIELD_RESOURCE_LOSS,
    FIELD_RESOURCE_SETUP,
    FIELD_RESOURCE_SPEND,
    FIELD_STATUS_CHANGE,
    FIELD_STATUS_ELAPSED,
    FIELD_STATUS_EMOTION,
    FIELD_STATUS_GOAL,
    FIELD_STATUS_INJURY,
    FIELD_STATUS_LOCATION,
    FIELD_STATUS_TIMEPOINT,
)
from chapter_scan import iter_chapter_files
from common_io import (
    ProjectStateError,
    extract_bullets,
    extract_section,
    load_volume_outline,
    load_project_state,
    load_json_file,
    require_chapter_word_range,
    require_locked_protagonist_gender,
    save_json_file,
)
from path_rules import (
    chapter_card_file,
    chapter_file,
    project_running_memory_file,
    volume_memory_json,
    volume_memory_md,
)
from chapter_view import load_chapter_view, save_split_chapter
from revision_state import get_chapter_revision_status, get_chapter_revision_tasks


class SubagentChapterGenerator:
    """子代理章节生成器"""

    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        self.chapters_dir = project_dir / "chapters"
        # 实例级缓存（单章生成生命周期内有效）
        self._chapter_index_cache = None      # iter_chapter_files 结果缓存
        self._chapter_view_cache = {}          # (vol, ch) -> ChapterView 缓存
        self._manifest_cache = {}              # (vol, ch) -> manifest dict 缓存

    def _get_chapter_index(self):
        """获取章节索引（带实例缓存）"""
        if self._chapter_index_cache is None:
            self._chapter_index_cache = list(iter_chapter_files(self.project_dir))
        return self._chapter_index_cache
    
    def _get_chapter_view(self, vol, ch):
        """获取章节视图（带实例缓存）"""
        key = (vol, ch)
        if key not in self._chapter_view_cache:
            self._chapter_view_cache[key] = load_chapter_view(self.project_dir, vol, ch)
        return self._chapter_view_cache[key]
    
    def _get_manifest(self, vol, ch):
        """获取manifest（带实例缓存）"""
        key = (vol, ch)
        if key not in self._manifest_cache:
            manifest_path = self._manifest_path(vol, ch)
            if manifest_path.exists():
                self._manifest_cache[key] = json.loads(manifest_path.read_text(encoding="utf-8"))
        return self._manifest_cache.get(key)
    
    def _require_runtime_state(self) -> dict:
        state = load_project_state(self.project_dir)
        require_locked_protagonist_gender(state)
        require_chapter_word_range(state)
        return state

    def load_all_previous_chapters(
        self,
        vol_num: int,
        ch_num: int,
        lookback: int = 0,
    ) -> list[dict]:
        """加载所有前文章节

        Args:
            vol_num: 当前卷号
            ch_num: 当前章节号
            lookback: 回溯章节数（0=全部）

        Returns:
            [
                {
                    "vol": 1,
                    "ch": 1,
                    "title": "第1章 标题",
                    "content": "完整正文..."
                },
                ...
            ]
        """
        chapters: list[dict] = []

        if not self.chapters_dir.exists():
            return chapters

        # 使用缓存的章节索引
        chapter_index = self._get_chapter_index()
        for vol, ch, ch_file in chapter_index:
            if vol > vol_num:
                continue

            if vol == vol_num and ch >= ch_num:
                continue

            # 使用缓存的章节视图
            content = self._get_chapter_view(vol, ch).merged_text

            title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
            title = title_match.group(1) if title_match else f"第{ch}章"

            chapters.append({
                "vol": vol,
                "ch": ch,
                "title": title,
                "content": content,
            })

        if lookback > 0 and len(chapters) > lookback:
            chapters = chapters[-lookback:]

        return chapters

    def _get_last_chapter_num(self, vol_num: int) -> int | None:
        """获取指定卷的最后一章号"""
        vol_dir = self.project_dir / "chapters" / f"vol{vol_num:02d}"
        if not vol_dir.exists():
            return None
        chapters = [int(f.stem.replace("ch", "")) for f in vol_dir.glob("ch*.md") if f.stem.replace("ch", "").isdigit()]
        return max(chapters) if chapters else None

    def _manifest_path(self, vol_num: int, ch_num: int) -> Path:
        return self.project_dir / "context" / f"subagent_context_vol{vol_num:02d}_ch{ch_num:02d}.json"

    def _title_from_text(self, text: str, fallback: str) -> str:
        title_match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
        return title_match.group(1).strip() if title_match else fallback

    def _collect_static_context_files(self, vol_num: int) -> dict[str, list[Path]]:
        groups = {
            "project_state": [
                self.project_dir / "wizard_state.json",
                self.project_dir / ".project_config.json",
                self.project_dir / ".workflow_lock.json",
            ],
            "planning": [
                self.project_dir / "reference" / "卷纲总表.md",
                self.project_dir / "BATCH_PLAN.md",
                project_running_memory_file(self.project_dir),
                volume_memory_md(self.project_dir, vol_num),
                volume_memory_json(self.project_dir, vol_num),
            ],
            "constraints": [
                self.project_dir / "CONSTRAINT_SNAPSHOT.md",
                self.project_dir / "CHECKPOINT_LOG.md",
            ],
            "runtime_state": [
                self.project_dir / "context" / "ABILITY_STATE.json",
                self.project_dir / "context" / "RESOURCE_INVENTORY.json",
            ],
        }
        return {
            name: [path.resolve() for path in paths if path.exists()]
            for name, paths in groups.items()
        }

    def build_context_manifest(
        self,
        vol_num: int,
        ch_num: int,
        project_config: dict,
        chapter_plan: Optional[dict] = None,
        revision_tasks: Optional[list[dict]] = None,
        revision_status: Optional[str] = None,
    ) -> dict:
        require_locked_protagonist_gender(project_config)
        specs = project_config.get("basic_specs", {})
        positioning = project_config.get("positioning", {})
        naming = project_config.get("naming", {})

        book_title = naming.get("selected_book_title", naming.get("book_title", "未命名"))
        genres = specs.get("main_genres", specs.get("genres", []))
        style_tone = specs.get("style_tone", "热血")
        narrative_style = positioning.get("narrative_style", "第三人称有限视角")
        min_words, max_words = require_chapter_word_range(project_config)
        draft_target = (min_words + max_words) // 2
        pass_threshold = int(min_words * 0.85)

        manifest_id = f"subagent-read-all-v1-vol{vol_num:02d}-ch{ch_num:02d}"
        manifest_path = self._manifest_path(vol_num, ch_num)

        # 尝试增量构建：复用前一章的 manifest
        prev_manifest = self._get_manifest(vol_num, ch_num - 1) if ch_num > 1 else None
        if prev_manifest:
            # 增量构建：在前一章 manifest 基础上追加
            prev_chapters = prev_manifest.get("previous_chapters", [])
            prev_required_paths = prev_manifest.get("required_read_sequence", [])
            prev_seen_paths = set(prev_required_paths)
            
            # 获取前一章的信息
            prev_vol_num = vol_num
            prev_ch_num = ch_num - 1
            if prev_ch_num < 1:
                prev_vol_num = vol_num - 1
                prev_ch_num = self._get_last_chapter_num(prev_vol_num) or 0
            
            if prev_ch_num > 0:
                view = self._get_chapter_view(prev_vol_num, prev_ch_num)
                title = self._title_from_text(view.raw_body_file or view.merged_text, f"第{prev_ch_num}章")
                body_path = view.chapter_path.resolve()
                body_path_str = str(body_path)
                
                card_path: str | None = None
                card_source = "missing"
                if view.has_separate_card:
                    card_path = str(view.card_path.resolve())
                    card_source = "separate_file"
                elif view.has_inline_card:
                    card_path = str(view.chapter_path.resolve())
                    card_source = "inline_in_body_file"
                
                # 追加前一章的信息
                new_prev_chapters = list(prev_chapters) + [{
                    "vol": prev_vol_num,
                    "ch": prev_ch_num,
                    "title": title,
                    "body_path": body_path_str,
                    "card_path": card_path,
                    "card_source": card_source,
                }]
                
                # 追加前一章的文件路径
                new_required_paths = list(prev_required_paths)
                if body_path_str not in prev_seen_paths:
                    new_required_paths.append(body_path_str)
                if card_path and card_path not in prev_seen_paths:
                    new_required_paths.append(card_path)
                
                manifest = {
                    **prev_manifest,
                    "context_manifest_id": manifest_id,
                    "current_chapter": {
                        "vol": vol_num,
                        "ch": ch_num,
                    },
                    "output_targets": {
                        "chapter_body_file": str(chapter_file(self.project_dir, vol_num, ch_num).resolve()),
                        "chapter_cards_file": str(chapter_card_file(self.project_dir, vol_num, ch_num).resolve()),
                    },
                    "task_context": {
                        **prev_manifest.get("task_context", {}),
                        "chapter_plan": chapter_plan.get("description") if chapter_plan else None,
                        "revision_status": revision_status,
                        "revision_tasks": revision_tasks or [],
                    },
                    "previous_chapters": new_prev_chapters,
                    "required_read_sequence": new_required_paths,
                    "counts": {
                        "previous_chapters": len(new_prev_chapters),
                        "required_files": len(new_required_paths),
                    },
                }
                save_json_file(manifest_path, manifest)
                manifest["manifest_file"] = str(manifest_path)
                # 更新缓存
                self._manifest_cache[(vol_num, ch_num)] = manifest
                return manifest

        # 完整构建（回退到原有逻辑）
        static_groups = self._collect_static_context_files(vol_num)
        previous_chapters: list[dict] = []
        missing_cards: list[str] = []
        required_paths: list[str] = []
        seen_paths: set[str] = set()

        def add_required(path: Path) -> None:
            resolved = str(path.resolve())
            if resolved not in seen_paths:
                seen_paths.add(resolved)
                required_paths.append(resolved)

        for paths in static_groups.values():
            for path in paths:
                add_required(path)

        # 使用缓存的章节索引，避免重复遍历目录
        chapter_index = self._get_chapter_index()
        for prev_vol, prev_ch, _ in chapter_index:
            if prev_vol > vol_num:
                continue
            if prev_vol == vol_num and prev_ch >= ch_num:
                continue

            # 使用缓存的章节视图，避免重复读取文件
            view = self._get_chapter_view(prev_vol, prev_ch)
            title = self._title_from_text(view.raw_body_file or view.merged_text, f"第{prev_ch}章")
            body_path = view.chapter_path.resolve()
            add_required(body_path)

            card_path: str | None = None
            card_source = "missing"
            if view.has_separate_card:
                card_path = str(view.card_path.resolve())
                card_source = "separate_file"
                add_required(view.card_path)
            elif view.has_inline_card:
                card_path = str(view.chapter_path.resolve())
                card_source = "inline_in_body_file"
            else:
                missing_cards.append(f"第{prev_vol}卷第{prev_ch}章")

            previous_chapters.append({
                "vol": prev_vol,
                "ch": prev_ch,
                "title": title,
                "body_path": str(body_path),
                "card_path": card_path,
                "card_source": card_source,
            })

        if missing_cards:
            raise ProjectStateError(
                "前文工作卡缺失，无法执行 subagent-only 全前文读取链路：" + "、".join(missing_cards)
            )

        manifest_id = f"subagent-read-all-v1-vol{vol_num:02d}-ch{ch_num:02d}"
        manifest_path = self._manifest_path(vol_num, ch_num)
        manifest = {
            "manifest_version": 1,
            "context_manifest_id": manifest_id,
            "strategy": "subagent_read_all_previous",
            "project_dir": str(self.project_dir.resolve()),
            "current_chapter": {
                "vol": vol_num,
                "ch": ch_num,
            },
            "output_targets": {
                "chapter_body_file": str(chapter_file(self.project_dir, vol_num, ch_num).resolve()),
                "chapter_cards_file": str(chapter_card_file(self.project_dir, vol_num, ch_num).resolve()),
            },
            "task_context": {
                "book_title": book_title,
                "genres": genres,
                "style_tone": style_tone,
                "narrative_style": narrative_style,
                "min_words": min_words,
                "max_words": max_words,
                "draft_target": draft_target,
                "pass_threshold": pass_threshold,
                "chapter_plan": chapter_plan.get("description") if chapter_plan else None,
                "revision_status": revision_status,
                "revision_tasks": revision_tasks or [],
            },
            "required_groups": {
                name: [str(path) for path in paths]
                for name, paths in static_groups.items()
                if paths
            },
            "previous_chapters": previous_chapters,
            "required_read_sequence": required_paths,
            "counts": {
                "previous_chapters": len(previous_chapters),
                "required_files": len(required_paths),
            },
        }
        save_json_file(manifest_path, manifest)
        manifest["manifest_file"] = str(manifest_path)
        return manifest

    def build_subagent_prompt(
        self,
        previous_chapters: list[dict],
        project_config: dict,
        current_chapter_info: dict,
        chapter_plan: Optional[dict] = None,
        revision_tasks: Optional[list[dict]] = None,
        revision_status: Optional[str] = None,
    ) -> str:
        """构建子代理的提示

        Args:
            previous_chapters: 前文章节列表
            project_config: 项目配置
            current_chapter_info: 当前章节信息
            chapter_plan: 章节规划（可选）

        Returns:
            完整的子代理提示
        """
        require_locked_protagonist_gender(project_config)
        specs = project_config.get("basic_specs", {})
        positioning = project_config.get("positioning", {})
        naming = project_config.get("naming", {})

        book_title = naming.get("selected_book_title", naming.get("book_title", "未命名"))
        genres = specs.get("main_genres", specs.get("genres", []))
        style_tone = specs.get("style_tone", "热血")
        narrative_style = positioning.get("narrative_style", "第三人称有限视角")
        min_words, max_words = require_chapter_word_range(project_config)
        pass_threshold = int(min_words * 0.85)

        vol_num = current_chapter_info["vol"]
        ch_num = current_chapter_info["ch"]
        chapter_plan_description = chapter_plan.get("description") if chapter_plan else None
        continuation = self._latest_continuation_requirements(previous_chapters)
        recent_summary = self._recent_mainline_summary_from_embedded(previous_chapters)
        volume_constraints = self._render_volume_outline_constraints(vol_num, chapter_plan_description)
        continuation_constraints = self._render_continuation_constraints(continuation, recent_summary)

        if revision_tasks and not revision_status:
            fix_methods = {task.get("fix_method") for task in revision_tasks}
            if "regenerate" in fix_methods:
                revision_status = "pending_regenerate"
            elif "rewrite_card" in fix_methods:
                revision_status = "pending_rewrite_card"
            else:
                revision_status = "pending_polish"

        prompt = f"""# 章节生成任务

## 任务描述
你是一位专业的小说创作助手。请根据提供的前文章节和项目配置，生成新章节的正文内容。

## 项目配置
- 书名：{book_title}
- 题材：{', '.join(genres)}
- 文风：{style_tone}
- 叙事视角：{narrative_style}

## 当前任务
- 当前卷：第{vol_num}卷
- 当前章节：第{ch_num}章
- 字数要求：{min_words}-{max_words}字

"""

        if chapter_plan:
            prompt += f"""## 章节规划
{chapter_plan.get('description', '无特殊要求')}

"""

        prompt += f"""{volume_constraints}

{continuation_constraints}

"""

        if revision_tasks:
            severity_order = {"error": 0, "warning": 1, "info": 2}
            if revision_status == "pending_regenerate":
                prompt += "## 本轮修正模式：整章重写\n- 必须整章重写正文与工作卡，不能只做局部补丁。\n- 优先解决所有 error，再处理 warning。\n\n"
            elif revision_status == "pending_rewrite_card":
                prompt += "## 本轮修正模式：重写工作卡\n- 正文尽量保持不变，重点重写 `## 内部工作卡`。\n- 工作卡必须严格对齐现有正文。\n\n"
            elif revision_status == "pending_polish":
                prompt += "## 本轮修正模式：局部润色\n- 不改变主事件与章节结构，只修局部问题。\n- 优先修复 warning 和格式细节。\n\n"
            prompt += "## 本轮修正要求\n"
            for task in sorted(revision_tasks, key=lambda item: (severity_order.get(item.get("severity", "info"), 9), item.get("fix_method", "polish")))[:5]:
                location = " / ".join(part for part in [task.get("card", ""), task.get("field", "")] if part)
                label = f"[{task.get('severity', 'info')}][{task.get('fix_method', 'polish')}]"
                rewrite_target = task.get("rewrite_target") or {
                    "regenerate": "full_chapter",
                    "rewrite_card": "work_cards_only",
                    "polish": "local_patch",
                }.get(task.get("fix_method", "polish"), "local_patch")
                blocking = task.get("blocking")
                if blocking is None:
                    blocking = task.get("severity") == "error"
                constraints = task.get("preserve_constraints") or (
                    ["工作卡必须与正文一致"] if rewrite_target == "work_cards_only" else
                    ["保留本章核心事件", "保留章节结尾结果"] if rewrite_target == "full_chapter" else
                    ["不改变主事件与章节结构"]
                )
                extras = []
                extras.append(f"目标={rewrite_target}")
                extras.append(f"阻塞={'是' if blocking else '否'}")
                if task.get("priority"):
                    extras.append(f"优先级={task['priority']}")
                if location:
                    prompt += f"- {label} {location}：{task.get('instruction', task.get('message', ''))}"
                else:
                    prompt += f"- {label} {task.get('instruction', task.get('message', ''))}"
                if extras:
                    prompt += f" ({'; '.join(extras)})"
                prompt += "\n"
                if constraints:
                    prompt += f"  保留约束：{'；'.join(constraints)}\n"
            prompt += "\n"

        prompt += "## 前文章节（完整内容）\n\n"

        for chapter in previous_chapters:
            prompt += f"""### {chapter['title']}

{chapter['content']}

"""

        prompt += f"""## 生成要求

1. **连续性要求**
   - 严格保持与前文的人物状态一致
   - 对话风格、语气保持自然延续
   - 场景描写风格一致
   - 时间线合理衔接
   - 必须根据上一章承接要求与最近主线推进摘要续写
   - 必须保持在同一故事线内推进，不得偏离当前卷纲

2. **内容要求**
   - 字数：{min_words}-{max_words}字
   - 包含完整的工作卡（状态卡、情节卡、资源卡、关系卡、情绪弧线卡、承上启下卡）
   - 承接前文章节的结尾
   - 发展故事主线

3. **格式要求**
   - `chapter_body` 使用标准章节格式：`# 第{ch_num}章 标题`
   - `chapter_body` 必须包含 `## 正文` 标记
   - `chapter_body` 不得包含 `## 内部工作卡`
   - `chapter_cards` 必须包含 `## 内部工作卡` 标记
   - 六张工作卡（每张用 `### N. 卡片名` 标记）

4. **工作卡格式**

   ### 1. 状态卡
   - {FIELD_STATUS_LOCATION}：
   - {FIELD_STATUS_INJURY}：
   - {FIELD_STATUS_EMOTION}：
   - {FIELD_STATUS_GOAL}：
   - {FIELD_STATUS_CHANGE}：
   - {FIELD_STATUS_ELAPSED}：
   - {FIELD_STATUS_TIMEPOINT}：

   {PLOT_CARD}
   - {FIELD_PLOT_CONFLICT}：
   - {FIELD_PLOT_EVENT}：
   - {FIELD_PLOT_TURN}：
   - {FIELD_PLOT_SETUP}：
   - {FIELD_PLOT_PAYOFF}：

   ### 3. 资源卡
   - {FIELD_RESOURCE_GAIN}：
   - {FIELD_RESOURCE_SPEND}：
   - {FIELD_RESOURCE_LOSS}：
   - {FIELD_RESOURCE_CARRY}：
   - {FIELD_RESOURCE_SETUP}：

   ### 4. 关系卡
   - {FIELD_RELATION_MAIN}：
   - {FIELD_RELATION_CHANGE}：

   {EMOTION_CARD}
   - {FIELD_EMOTION_START}：
   - {FIELD_EMOTION_PROCESS}：
   - {FIELD_EMOTION_TARGET}：
   - {FIELD_EMOTION_SUSPENSE}：

   {CARRY_CARD}
   - {FIELD_CARRY_MUST}：
   - {FIELD_CARRY_LIMIT}：
   - {FIELD_CARRY_PAYOFF}：
   - {FIELD_CARRY_SETUP}：
   - {FIELD_CARRY_HOOK}：

5. **禁止事项**
   - 不得出现与前文矛盾的设定
   - 不得遗忘前文埋下的伏笔
   - 不得突变人物性格或关系
   - 不得出现AI痕迹（如"微微一笑"、"若有所思"等模式化表达）

## 输出质量标准

1. **字数达标**：正文字数 {min_words}-{max_words}字（低于 {pass_threshold} 字直接失败）
2. **人物一致性**：与前文状态卡保持一致
3. **结构完整**：6张工作卡填写率 > 50%
4. **算数逻辑**：章节内的数字计算必须自洽
5. **章节自指**：不得出现"本章"、"本章中"等自指词汇
6. **无AI痕迹**：不得出现"微微一笑"、"若有所思"、"喃喃自语道"等模式化表达

## 输出协议（严格遵守）

只允许输出一个 JSON 对象，不允许输出解释文字，不允许使用代码块。

成功格式：
{{
  "status": "success",
  "chapter_body": "# 第{ch_num}章 标题\\n\\n## 正文\\n\\n...",
  "chapter_cards": "## 内部工作卡\\n\\n### 1. 状态卡\\n..."
}}

失败格式：
{{
  "status": "error",
  "error": "失败原因"
}}

请生成完整的第{ch_num}章内容，并按上述 JSON 协议返回。
"""

        return prompt

    def dispatch_chapter_generation(
        self,
        vol_num: int,
        ch_num: int,
        lookback: int = 0,
    ) -> dict:
        """调度章节生成

        Args:
            vol_num: 卷号
            ch_num: 章节号
            lookback: 回溯章节数（0=全部）

        Returns:
            {
                "status": "success" | "error",
                "chapter_content": "生成的章节内容",
                "token_usage": 12345,
                "generation_time": 45.6,
                "chapters_loaded": 10
            }
        """
        start_time = time.time()

        try:
            project_config = self._require_runtime_state()
        except ProjectStateError as exc:
            return {
                "status": "error",
                "error": f"项目配置不完整：{exc}",
                "chapter_content": "",
                "token_usage": 0,
                "generation_time": time.time() - start_time,
                "chapters_loaded": 0,
            }

        chapter_plan = self._load_chapter_plan(vol_num, ch_num)
        revision_status = get_chapter_revision_status(self.project_dir, vol_num, ch_num)
        revision_tasks = get_chapter_revision_tasks(self.project_dir, vol_num, ch_num)

        try:
            manifest = self.build_context_manifest(
                vol_num=vol_num,
                ch_num=ch_num,
                project_config=project_config,
                chapter_plan=chapter_plan,
                revision_tasks=revision_tasks,
                revision_status=revision_status,
            )
        except ProjectStateError as exc:
            return {
                "status": "error",
                "error": str(exc),
                "chapter_content": "",
                "token_usage": 0,
                "generation_time": time.time() - start_time,
                "chapters_loaded": 0,
            }

        chapters_loaded = manifest["counts"]["previous_chapters"]
        if chapters_loaded == 0 and ch_num > 1:
            return {
                "status": "error",
                "error": f"未找到前文章节（第{ch_num}章需要前文）",
                "chapter_content": "",
                "token_usage": 0,
                "generation_time": time.time() - start_time,
                "chapters_loaded": 0,
            }

        prompt = self.generate_file_based_prompt(
            vol_num,
            ch_num,
            manifest,
            project_config=project_config,
            revision_tasks=revision_tasks,
            revision_status=revision_status,
        )

        prompt_file = self.project_dir / "context" / "subagent_prompt.md"
        prompt_file.parent.mkdir(exist_ok=True)
        prompt_file.write_text(prompt, encoding="utf-8")

        generation_time = time.time() - start_time

        return {
            "status": "prompt_ready",
            "prompt_file": str(prompt_file),
            "manifest_file": manifest["manifest_file"],
            "context_manifest_id": manifest["context_manifest_id"],
            "generation_time": generation_time,
            "chapters_loaded": chapters_loaded,
            "required_files": manifest["counts"]["required_files"],
            "prompt_length": len(prompt),
        }

    def _load_chapter_plan(self, vol_num: int, ch_num: int) -> Optional[dict]:
        """加载章节规划

        从卷纲中提取当前章节的规划信息
        """
        outline_file = self.project_dir / "reference" / "卷纲总表.md"
        if not outline_file.exists():
            return None

        content = outline_file.read_text(encoding="utf-8")

        vol_pattern = rf"##\s+第{vol_num}卷.*?(?=##\s+第\d+卷|\Z)"
        vol_match = re.search(vol_pattern, content, re.DOTALL)

        if not vol_match:
            return None

        vol_content = vol_match.group(0)

        ch_pattern = rf"###\s+第{ch_num}章.*?(?=###\s+第\d+章|\Z)"
        ch_match = re.search(ch_pattern, vol_content, re.DOTALL)

        if not ch_match:
            return None

        return {"description": ch_match.group(0).strip()}

    def _chapter_event_summary_from_text(self, text: str) -> str:
        plot_card = extract_section(text, PLOT_CARD)
        plot_bullets = extract_bullets(plot_card)
        conflict = plot_bullets.get(FIELD_PLOT_CONFLICT, "")
        event = plot_bullets.get(FIELD_PLOT_EVENT, "")
        turn = plot_bullets.get(FIELD_PLOT_TURN, "")
        parts = [part for part in [conflict, event, turn] if part]
        if parts:
            return "；".join(parts[:3])
        lines = [line.strip() for line in text.splitlines() if line.strip() and not line.startswith("#")]
        joined = " ".join(lines)
        return joined[:80] + ("..." if len(joined) > 80 else "")

    def _latest_continuation_requirements_from_text(self, text: str) -> dict[str, str]:
        carry_card = extract_section(text, CARRY_CARD)
        status_card = extract_section(text, "### 1. 状态卡")
        carry = extract_bullets(carry_card)
        status = extract_bullets(status_card)
        return {
            "must": carry.get(FIELD_CARRY_MUST, ""),
            "limit": carry.get(FIELD_CARRY_LIMIT, ""),
            "payoff": carry.get(FIELD_CARRY_PAYOFF, ""),
            "setup": carry.get(FIELD_CARRY_SETUP, ""),
            "hook": carry.get(FIELD_CARRY_HOOK, ""),
            "location": status.get(FIELD_STATUS_LOCATION, ""),
            "emotion": status.get(FIELD_STATUS_EMOTION, ""),
            "goal": status.get(FIELD_STATUS_GOAL, ""),
        }

    def _latest_continuation_requirements(self, previous_chapters: list[dict]) -> dict[str, str]:
        if not previous_chapters:
            return {}
        latest = previous_chapters[-1]
        text = latest.get("content")
        if not text and latest.get("vol") and latest.get("ch"):
            # 使用缓存的章节视图
            text = self._get_chapter_view(latest["vol"], latest["ch"]).merged_text
        if not text:
            return {}
        return self._latest_continuation_requirements_from_text(text)

    def _recent_mainline_summary_from_embedded(self, previous_chapters: list[dict], limit: int = 3) -> list[str]:
        items: list[str] = []
        for chapter in previous_chapters[-limit:]:
            summary = self._chapter_event_summary_from_text(chapter.get("content", ""))
            items.append(f"- 第{chapter['vol']}卷第{chapter['ch']}章《{chapter['title']}》：{summary}")
        return items

    def _recent_mainline_summary_from_manifest(self, manifest: dict, limit: int = 3) -> list[str]:
        items: list[str] = []
        for chapter in manifest.get("previous_chapters", [])[-limit:]:
            # 使用缓存的章节视图，避免重复读取文件
            text = self._get_chapter_view(chapter["vol"], chapter["ch"]).merged_text
            summary = self._chapter_event_summary_from_text(text)
            items.append(f"- 第{chapter['vol']}卷第{chapter['ch']}章《{chapter['title']}》：{summary}")
        return items

    def _render_volume_outline_constraints(self, vol_num: int, chapter_plan_description: str | None) -> str:
        outline = load_volume_outline(self.project_dir, vol_num)
        lines = ["## 当前卷纲约束"]
        if outline:
            if outline.get("卷标题"):
                lines.append(f"- 当前卷：{outline['卷标题']}")
            if outline.get("卷定位"):
                lines.append(f"- 当前卷定位：{outline['卷定位']}")
            if outline.get("卷目标"):
                lines.append(f"- 当前卷目标：{outline['卷目标']}")
            if outline.get("核心冲突"):
                lines.append(f"- 当前卷核心冲突：{outline['核心冲突']}")
            if outline.get("卷尾钩子"):
                lines.append(f"- 当前卷卷尾钩子：{outline['卷尾钩子']}")
        else:
            lines.append("- 当前卷纲缺失，必须优先服从当前章节规划与前文主线。")
        if chapter_plan_description:
            lines.append("- 当前章规划：")
            for raw_line in chapter_plan_description.splitlines():
                stripped = raw_line.strip()
                if stripped:
                    lines.append(f"  {stripped}")
        lines.append("- 本章必须服务当前卷目标，不得偏离到无关故事线。")
        lines.append("- 不得提前透支下一卷核心冲突、下一卷关键揭示或下一卷卷尾钩子。")
        return "\n".join(lines)

    def _render_continuation_constraints(self, continuation: dict[str, str], recent_summary: list[str]) -> str:
        lines = [
            "## 主线续写约束",
            "- 本章必须在同一故事线内续写，不得切换到无关主线。",
            "- 如果出现支线内容，支线必须直接服务当前主线推进。",
            "- 本章必须承接上一章的目标、情绪、位置与冲突状态，不得重置剧情。",
            "- 本章主推进必须继续围绕上一章留下的最强钩子和当前卷目标展开。",
            "",
            "## 上一章承接要求",
            f"- 上一章结尾地点：{continuation.get('location') or '未提取'}",
            f"- 上一章结尾情绪：{continuation.get('emotion') or '未提取'}",
            f"- 上一章当前目标：{continuation.get('goal') or '未提取'}",
            f"- 下章必须接住什么：{continuation.get('must') or '未提取'}",
            f"- 下章不能忘什么限制：{continuation.get('limit') or '未提取'}",
            f"- 需要回收的伏笔：{continuation.get('payoff') or '未提取'}",
            f"- 新埋下的伏笔：{continuation.get('setup') or '未提取'}",
            f"- 上一章最强钩子：{continuation.get('hook') or '未提取'}",
            "",
            "## 最近主线推进摘要",
        ]
        lines.extend(recent_summary or ["- （暂无，按当前卷纲与上一章承接要求续写）"])
        return "\n".join(lines)

    def generate_file_based_prompt(
        self,
        vol_num: int,
        ch_num: int,
        manifest: dict,
        project_config: Optional[dict] = None,
        revision_tasks: Optional[list[dict]] = None,
        revision_status: Optional[str] = None,
    ) -> str:
        """生成基于 manifest 的提示（不嵌入前文内容）

        Args:
            vol_num: 当前卷号
            ch_num: 当前章节号
            manifest: 上下文 manifest

        Returns:
            固定长度的提示，要求子代理自行读取全部前文
        """
        if project_config is None:
            project_config = self._require_runtime_state()
        specs = project_config.get("basic_specs", {})
        positioning = project_config.get("positioning", {})
        naming = project_config.get("naming", {})

        book_title = naming.get("selected_book_title", naming.get("book_title", "未命名"))
        genres = specs.get("main_genres", specs.get("genres", []))
        style_tone = specs.get("style_tone", "轻松幽默")
        narrative_style = positioning.get("narrative_style", "第三人称有限视角")
        min_words, max_words = require_chapter_word_range(project_config)
        draft_target = (min_words + max_words) // 2
        pass_threshold = int(min_words * 0.85)
        if revision_status is None:
            revision_status = get_chapter_revision_status(self.project_dir, vol_num, ch_num)
        if revision_tasks is None:
            revision_tasks = get_chapter_revision_tasks(self.project_dir, vol_num, ch_num)

        content_output = str(chapter_file(self.project_dir, vol_num, ch_num))
        card_output = str(chapter_card_file(self.project_dir, vol_num, ch_num))
        manifest_path = manifest["manifest_file"]
        manifest_id = manifest["context_manifest_id"]
        chapters_loaded = manifest["counts"]["previous_chapters"]
        required_file_count = manifest["counts"]["required_files"]
        chapter_plan_description = manifest["task_context"].get("chapter_plan")
        continuation = self._latest_continuation_requirements(manifest.get("previous_chapters", []))
        recent_summary = self._recent_mainline_summary_from_manifest(manifest)
        volume_constraints = self._render_volume_outline_constraints(vol_num, chapter_plan_description)
        continuation_constraints = self._render_continuation_constraints(continuation, recent_summary)

        prompt = f"""# 章节生成任务

## 项目信息
- 书名：{book_title}
- 题材：{', '.join(genres)}
- 文风：{style_tone}
- 叙事视角：{narrative_style}
- 当前卷：第{vol_num}卷
- 当前章节：第{ch_num}章
- 字数要求：{min_words}-{max_words}字
- 上下文策略：必须由子代理自行读取全部前文

## 执行协议（严格遵守）

1. 这是 **subagent-only** 正文生成链路。你不能依据当前 prompt 直接起草，必须先读上下文文件。
2. 第一步必须调用 `read` 读取 manifest：`{manifest_path}`
3. 第二步必须按 manifest 里的 `required_read_sequence` 顺序，逐个读取所有文件。
4. `previous_chapters` 中列出的全部前文章节正文和工作卡必须完整读取，禁止 lookback、禁止只读最近几章、禁止用摘要替代。
5. 如果 manifest 中任何必读文件无法读取，直接返回错误 JSON，不得跳过。
6. 读取完成后再生成正文和工作卡，并且只能返回 JSON。

## 本次读取规模
- context_manifest_id：`{manifest_id}`
- 必读文件数：{required_file_count}
- 必读前文章节数：{chapters_loaded}

{volume_constraints}

{continuation_constraints}

"""

        if revision_tasks:
            severity_order = {"error": 0, "warning": 1, "info": 2}
            if revision_status == "pending_regenerate":
                prompt += "## 本轮修正模式：整章重写\n- 必须整章重写正文与工作卡，不能只做局部补丁。\n- 优先解决所有 error，再处理 warning。\n\n"
            elif revision_status == "pending_rewrite_card":
                prompt += "## 本轮修正模式：重写工作卡\n- 正文尽量保持不变，重点重写 `## 内部工作卡`。\n- 工作卡必须严格对齐现有正文。\n\n"
            elif revision_status == "pending_polish":
                prompt += "## 本轮修正模式：局部润色\n- 不改变主事件与章节结构，只修局部问题。\n- 优先修复 warning 和格式细节。\n\n"
            prompt += "## 本轮修正要求\n"
            for task in sorted(revision_tasks, key=lambda item: (severity_order.get(item.get("severity", "info"), 9), item.get("fix_method", "polish")))[:5]:
                location = " / ".join(part for part in [task.get("card", ""), task.get("field", "")] if part)
                label = f"[{task.get('severity', 'info')}][{task.get('fix_method', 'polish')}]"
                rewrite_target = task.get("rewrite_target") or {
                    "regenerate": "full_chapter",
                    "rewrite_card": "work_cards_only",
                    "polish": "local_patch",
                }.get(task.get("fix_method", "polish"), "local_patch")
                blocking = task.get("blocking")
                if blocking is None:
                    blocking = task.get("severity") == "error"
                constraints = task.get("preserve_constraints") or (
                    ["工作卡必须与正文一致"] if rewrite_target == "work_cards_only" else
                    ["保留本章核心事件", "保留章节结尾结果"] if rewrite_target == "full_chapter" else
                    ["不改变主事件与章节结构"]
                )
                extras = []
                extras.append(f"目标={rewrite_target}")
                extras.append(f"阻塞={'是' if blocking else '否'}")
                if task.get("priority"):
                    extras.append(f"优先级={task['priority']}")
                if location:
                    prompt += f"- {label} {location}：{task.get('instruction', task.get('message', ''))}"
                else:
                    prompt += f"- {label} {task.get('instruction', task.get('message', ''))}"
                if extras:
                    prompt += f" ({'; '.join(extras)})"
                prompt += "\n"
                if constraints:
                    prompt += f"  保留约束：{'；'.join(constraints)}\n"
            prompt += "\n"

        prompt += f"""

## 输出要求
- 正文只写入：`{content_output}`
- 工作卡只写入：`{card_output}`
- 正文文件不得包含 `## 内部工作卡`

## 生成要求

1. **连续性要求**
   - 严格保持与前文的人物状态一致
   - 对话风格、语气保持自然延续
   - 场景描写风格一致
   - 时间线合理衔接
   - 必须根据上一章承接要求与最近主线推进摘要续写
   - 必须保持在同一故事线内推进，不得偏离当前卷纲

2. **内容要求**
   - 字数：{min_words}-{max_words}字
   - 包含完整的工作卡（状态卡、情节卡、资源卡、关系卡、情绪弧线卡、承上启下卡）
   - 承接前文章节的结尾
   - 发展故事主线

3. **格式要求**
   - 章节标题：`# 第{ch_num}章 标题`
   - **正文部分前必须有 `## 正文` 标记**
   - `## 内部工作卡` 标记
   - 六张工作卡（每张用 `### N. 卡片名` 标记）

4. **工作卡格式**（必须完整填写每个字段）

   ### 1. 状态卡
   - {FIELD_STATUS_LOCATION}：
   - {FIELD_STATUS_INJURY}：
   - {FIELD_STATUS_EMOTION}：
   - {FIELD_STATUS_GOAL}：
   - {FIELD_STATUS_CHANGE}：
   - {FIELD_STATUS_ELAPSED}：
   - {FIELD_STATUS_TIMEPOINT}：

   {PLOT_CARD}
   - {FIELD_PLOT_CONFLICT}：
   - {FIELD_PLOT_EVENT}：
   - {FIELD_PLOT_TURN}：
   - {FIELD_PLOT_SETUP}：
   - {FIELD_PLOT_PAYOFF}：

   ### 3. 资源卡
   - {FIELD_RESOURCE_GAIN}：
   - {FIELD_RESOURCE_SPEND}：
   - {FIELD_RESOURCE_LOSS}：
   - {FIELD_RESOURCE_CARRY}：
   - {FIELD_RESOURCE_SETUP}：

   ### 4. 关系卡
   - {FIELD_RELATION_MAIN}：
   - {FIELD_RELATION_CHANGE}：

   {EMOTION_CARD}
   - {FIELD_EMOTION_START}：
   - {FIELD_EMOTION_PROCESS}：
   - {FIELD_EMOTION_TARGET}：
   - {FIELD_EMOTION_SUSPENSE}：

   {CARRY_CARD}
   - {FIELD_CARRY_MUST}：
   - {FIELD_CARRY_LIMIT}：
   - {FIELD_CARRY_PAYOFF}：
   - {FIELD_CARRY_SETUP}：
   - {FIELD_CARRY_HOOK}：

5. **禁止事项**
   - 不得出现与前文矛盾的设定
   - 不得遗忘前文埋下的伏笔
   - 不得突变人物性格或关系
   - 不得出现AI痕迹（如"小明微微一笑"、"张三若有所思"等模式化表达）

## 输出格式

只允许输出一个 JSON 对象，不允许输出解释文字，不允许使用代码块。

成功格式：
{{
  "status": "success",
  "context_manifest_id": "{manifest_id}",
  "files_read": [
    "manifest.required_read_sequence 里的绝对路径1",
    "manifest.required_read_sequence 里的绝对路径2"
  ],
  "chapter_body": "# 第{ch_num}章 标题\\n\\n## 正文\\n\\n...",
  "chapter_cards": "## 内部工作卡\\n\\n### 1. 状态卡\\n..."
}}

失败格式：
{{
  "status": "error",
  "context_manifest_id": "{manifest_id}",
  "error": "失败原因"
}}

约束：
- `context_manifest_id` 必须与 manifest 完全一致：`{manifest_id}`
- `files_read` 必须完整回填 manifest 里的 `required_read_sequence`，不能缺项
- `chapter_body` 只对应正文文件：`{content_output}`
- `chapter_cards` 只对应工作卡文件：`{card_output}`
- `chapter_body` 禁止出现 `## 内部工作卡`
- `chapter_cards` 必须以 `## 内部工作卡` 开始

## 字数控制（严格遵守）
- 正文字数统计范围：从 `## 正文` 到 `## 内部工作卡` 之间的内容
- **目标中间值：{draft_target}字**
- **允许范围：{min_words}-{max_words}字**
- **低于质量门槛 {pass_threshold} 字：必须整章重写，不允许尾部补字**
- **超过最大字数：必须压缩重复反应、重复解释和冗余心理描写后重新检查**

## 质量标准

1. **字数达标**：正文字数必须在{min_words}-{max_words}之间（低于{pass_threshold}字直接失败并重生成）
2. **人物一致性**：与前文状态卡保持一致
3. **结构完整**：6张工作卡每张的每个字段都必须填写完整
4. **算数逻辑**：章节内的数字计算必须自洽
5. **章节自指**：不得出现"本章"、"本章中"等自指词汇
6. **无AI痕迹**：不得出现"微微一笑"、"若有所思"、"喃喃自语道"等模式化表达

## 生成后自检（必须执行）

生成章节后、输出前，必须进行以下自检：

1. **时间词一致性检查**：
   - 同一时间跨度必须一致（如"三个月"不能变成"大半年"）
   - 倒计时必须每章递减

2. **因果链检查**：
   - "公司倒闭/老板跑路" → 不能有"赔偿金"
   - "被裁员" → 有赔偿金
   - "跳槽" → 主动离职，不能写被裁员

3. **人物位置检查**：
   - "离开/走了" → 后续不能再出现该人物
   - 检测到矛盾立即修正后再输出

4. **数字合理性检查**：
   - 赔偿金 = 月薪 × 月数
   - 金额来源必须可追溯

发现问题立即修正，再输出最终版本。
"""

        return prompt

    def separate_generated_chapter(
        self,
        chapter_file: Path,
        cards_dir: Path,
    ) -> bool:
        """自动分离生成的章节内容

        Args:
            chapter_file: 章节文件路径（包含混合内容）
            cards_dir: 工作卡保存目录

        Returns:
            bool: 分离是否成功
        """
        if not chapter_file.exists():
            return False

        # 读取章节内容
        content = chapter_file.read_text(encoding="utf-8")

        # 查找工作卡标记
        marker = "## 内部工作卡"
        idx = content.find(marker)

        if idx == -1:
            return False

        # 分离内容
        chapter_content = content[:idx].strip()
        cards = content[idx:].strip()

        # 确保工作卡目录存在
        cards_dir.mkdir(exist_ok=True)
        vol_num = int(chapter_file.parent.name.replace("vol", ""))
        ch_num = int(chapter_file.stem.replace("ch", ""))
        save_split_chapter(self.project_dir, vol_num, ch_num, chapter_content, cards)

        return True

    def verify_separation(
        self,
        vol_num: int,
        ch_num: int,
    ) -> dict:
        """验证章节分离是否成功

        Returns:
            {
                "content_exists": True/False,
                "cards_exists": True/False,
                "content_has_marker": True/False,
                "cards_valid": True/False,
                "separated": True/False
            }
        """
        # 使用缓存的章节视图
        view = self._get_chapter_view(vol_num, ch_num)

        result = {
            "content_exists": view.chapter_path.exists(),
            "cards_exists": view.card_path.exists(),
            "content_has_marker": view.has_inline_card,
            "cards_valid": view.has_separate_card,
            "separated": view.is_split_valid,
        }

        return result

    def auto_separate_after_generation(
        self,
        vol_num: int,
        ch_num: int,
    ) -> dict:
        """生成后自动分离章节内容

        Args:
            vol_num: 卷号
            ch_num: 章节号

        Returns:
            {
                "status": "success" | "already_separated" | "failed",
                "message": "状态描述"
            }
        """
        chapter_path = chapter_file(self.project_dir, vol_num, ch_num)
        cards_dir = chapter_path.parent / "cards"

        # 先验证当前状态
        verification = self.verify_separation(vol_num, ch_num)

        if verification["separated"]:
            return {
                "status": "already_separated",
                "message": "章节已分离，无需处理",
            }

        if not verification["content_exists"]:
            return {
                "status": "failed",
                "message": f"章节文件不存在: {chapter_path}",
            }

        # 尝试自动分离
        success = self.separate_generated_chapter(chapter_path, cards_dir)

        if success:
            # 再次验证
            verification = self.verify_separation(vol_num, ch_num)
            if verification["separated"]:
                return {
                    "status": "success",
                    "message": "自动分离成功",
                }
            else:
                return {
                    "status": "failed",
                    "message": "分离后验证失败",
                }
        else:
            return {
                "status": "failed",
                "message": "未找到'## 内部工作卡'标记，无法分离",
            }
