#!/usr/bin/env python3
"""
子代理章节生成模块 - 使用子代理生成章节正文
将所有前文章节完整加载到子代理的独立上下文中，从根本上解决漂移问题
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Optional

from common_io import load_project_state, load_json_file, save_json_file


class SubagentChapterGenerator:
    """子代理章节生成器"""

    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        self.chapters_dir = project_dir / "chapters"

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

        for vol_dir in sorted(self.chapters_dir.glob("vol*")):
            vol_num_match = re.search(r"vol(\d+)", vol_dir.name)
            if not vol_num_match:
                continue
            vol = int(vol_num_match.group(1))

            if vol > vol_num:
                continue

            for ch_file in sorted(vol_dir.glob("ch*.md")):
                ch_num_match = re.search(r"ch(\d+)", ch_file.name)
                if not ch_num_match:
                    continue
                ch = int(ch_num_match.group(1))

                if vol == vol_num and ch >= ch_num:
                    continue

                content = ch_file.read_text(encoding="utf-8")

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

    def build_subagent_prompt(
        self,
        previous_chapters: list[dict],
        project_config: dict,
        current_chapter_info: dict,
        chapter_plan: Optional[dict] = None,
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
        specs = project_config.get("basic_specs", {})
        positioning = project_config.get("positioning", {})
        naming = project_config.get("naming", {})

        book_title = naming.get("selected_book_title", naming.get("book_title", "未命名"))
        genres = specs.get("main_genres", specs.get("genres", []))
        style_tone = specs.get("style_tone", "热血")
        narrative_style = positioning.get("narrative_style", "第三人称有限视角")
        min_words = specs.get("chapter_length_min", specs.get("min_words", 3500))
        max_words = specs.get("chapter_length_max", specs.get("max_words", 4500))

        vol_num = current_chapter_info["vol"]
        ch_num = current_chapter_info["ch"]

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

2. **内容要求**
   - 字数：{min_words}-{max_words}字
   - 包含完整的工作卡（状态卡、情节卡、资源卡、关系卡、情绪弧线卡、承上启下卡）
   - 承接前文章节的结尾
   - 发展故事主线

3. **格式要求**
   - 使用标准章节格式：`# 第{ch_num}章 标题`
   - 正文部分
   - `## 内部工作卡` 标记
   - 六张工作卡（每张用 `### N. 卡片名` 标记）

4. **工作卡格式**

   ### 1. 状态卡
   - 主角当前位置：
   - 主角当前情绪：
   - 主角当前目标：
   - 主角当前伤势/疲劳：

   ### 2. 情节卡
   - 本章关键事件：
   - 新埋伏笔：
   - 回收伏笔：

   ### 3. 资源卡
   - 本章获得资源：
   - 本章消耗资源：

   ### 4. 关系卡
   - 主要人物：
   - 人物变化：

   ### 5. 情绪弧线卡
   - 起始情绪：
   - 变化过程：
   - 目标情绪：

   ### 6. 承上启下卡
   - 下章必须接住什么：
   - 本章留下的最强钩子是什么：

5. **禁止事项**
   - 不得出现与前文矛盾的设定
   - 不得遗忘前文埋下的伏笔
   - 不得突变人物性格或关系
   - 不得出现AI痕迹（如"小明微微一笑"、"张三若有所思"等模式化表达）

请生成完整的第{ch_num}章内容，包含标题、正文和工作卡。
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

        project_config = load_project_state(self.project_dir)

        previous_chapters = self.load_all_previous_chapters(vol_num, ch_num, lookback)

        if not previous_chapters and ch_num > 1:
            return {
                "status": "error",
                "error": f"未找到前文章节（第{ch_num}章需要前文）",
                "chapter_content": "",
                "token_usage": 0,
                "generation_time": time.time() - start_time,
                "chapters_loaded": 0,
            }

        chapter_plan = self._load_chapter_plan(vol_num, ch_num)

        prompt = self.build_subagent_prompt(
            previous_chapters=previous_chapters,
            project_config=project_config,
            current_chapter_info={"vol": vol_num, "ch": ch_num},
            chapter_plan=chapter_plan,
        )

        prompt_file = self.project_dir / "context" / "subagent_prompt.md"
        prompt_file.parent.mkdir(exist_ok=True)
        prompt_file.write_text(prompt, encoding="utf-8")

        generation_time = time.time() - start_time

        return {
            "status": "prompt_ready",
            "prompt_file": str(prompt_file),
            "generation_time": generation_time,
            "chapters_loaded": len(previous_chapters),
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
