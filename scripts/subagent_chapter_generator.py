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
   - 不得出现AI痕迹（如"微微一笑"、"若有所思"等模式化表达）

## 输出质量标准

1. **字数达标**：正文字数 3500-4500字（低于 2975 字直接失败）
2. **人物一致性**：与前文状态卡保持一致
3. **结构完整**：6张工作卡填写率 > 50%
4. **算数逻辑**：章节内的数字计算必须自洽
5. **章节自指**：不得出现"本章"、"本章中"等自指词汇
6. **无AI痕迹**：不得出现"微微一笑"、"若有所思"、"喃喃自语道"等模式化表达

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

    def generate_file_based_prompt(
        self,
        vol_num: int,
        ch_num: int,
    ) -> str:
        """生成基于文件路径的提示（不嵌入内容）

        Args:
            vol_num: 当前卷号
            ch_num: 当前章节号

        Returns:
            固定长度的提示，包含文件路径列表
        """
        # 加载项目配置
        project_config = load_project_state(self.project_dir)
        specs = project_config.get("basic_specs", {})
        positioning = project_config.get("positioning", {})
        naming = project_config.get("naming", {})

        book_title = naming.get("selected_book_title", naming.get("book_title", "未命名"))
        genres = specs.get("main_genres", specs.get("genres", []))
        style_tone = specs.get("style_tone", "轻松幽默")
        narrative_style = positioning.get("narrative_style", "第三人称有限视角")
        min_words = specs.get("chapter_length_min", specs.get("min_words", 3500))
        max_words = specs.get("chapter_length_max", specs.get("max_words", 4500))

        # 构建前文章节文件路径
        content_files = []
        card_files = []

        for i in range(1, ch_num):
            content_files.append(f"chapters/vol{vol_num:02d}/ch{i:02d}.md")
            card_files.append(f"chapters/vol{vol_num:02d}/cards/ch{i:02d}_card.md")

        # 生成文件路径列表
        project_path = str(self.project_dir)
        content_files_list = "\n".join(
            f"- {project_path}/{f}" for f in content_files
        )
        card_files_list = "\n".join(
            f"- {project_path}/{f}" for f in card_files
        )

        # 输出路径
        content_output = f"{project_path}/chapters/vol{vol_num:02d}/ch{ch_num:02d}.md"
        card_output = f"{project_path}/chapters/vol{vol_num:02d}/cards/ch{ch_num:02d}_card.md"

        # 生成提示
        prompt = f"""# 章节生成任务

## 项目信息
- 书名：{book_title}
- 题材：{', '.join(genres)}
- 文风：{style_tone}
- 叙事视角：{narrative_style}
- 当前卷：第{vol_num}卷
- 当前章节：第{ch_num}章
- 字数要求：{min_words}-{max_words}字

## 需要读取的文件

### 前文章节正文
请读取以下正文文件：
{content_files_list}

### 前文章节工作卡
请读取以下工作卡文件（包含状态、情节、资源、关系等信息）：
{card_files_list}

## 生成要求

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
   - 章节标题：`# 第{ch_num}章 标题`
   - **正文部分前必须有 `## 正文` 标记**
   - `## 内部工作卡` 标记
   - 六张工作卡（每张用 `### N. 卡片名` 标记）

4. **工作卡格式**（必须完整填写每个字段）

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

## 输出格式

请生成完整的第{ch_num}章内容，并分离输出：

1. **正文**保存到：`{content_output}`
   - 正文必须包含 `## 正文` 标记
2. **工作卡**保存到：`{card_output}`

注意：工作卡必须使用 `## 内部工作卡` 标记开始。

## 字数控制（严格遵守）
- 正文字数统计范围：从 `## 正文` 到 `## 内部工作卡` 之间的内容
- **目标中间值：4000字**
- **允许范围：3500-4500字**
- **超出5000字（即4500+500）：必须压缩章节内容后重新检查**
- **低于3000字（即3500-500）：必须扩展增加对话和细节**

## 质量标准

1. **字数达标**：正文字数必须在3500-4500之间（超出5000字或低于3000字需重新生成）
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

        # 保存正文
        chapter_file.write_text(chapter_content, encoding="utf-8")

        # 保存工作卡
        card_file = cards_dir / f"{chapter_file.stem}_card.md"
        card_file.write_text(cards, encoding="utf-8")

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
        chapter_file = self.project_dir / "chapters" / f"vol{vol_num:02d}" / f"ch{ch_num:02d}.md"
        card_file = self.project_dir / "chapters" / f"vol{vol_num:02d}" / "cards" / f"ch{ch_num:02d}_card.md"

        result = {
            "content_exists": chapter_file.exists(),
            "cards_exists": card_file.exists(),
            "content_has_marker": False,
            "cards_valid": False,
            "separated": False,
        }

        # 检查正文是否不包含工作卡标记
        if result["content_exists"]:
            content = chapter_file.read_text(encoding="utf-8")
            result["content_has_marker"] = "## 内部工作卡" in content

        # 检查工作卡是否有效
        if result["cards_exists"]:
            cards = card_file.read_text(encoding="utf-8")
            result["cards_valid"] = "## 内部工作卡" in cards

        # 判断是否已分离
        result["separated"] = (
            result["content_exists"]
            and result["cards_exists"]
            and not result["content_has_marker"]
            and result["cards_valid"]
        )

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
        chapter_file = self.project_dir / "chapters" / f"vol{vol_num:02d}" / f"ch{ch_num:02d}.md"
        cards_dir = self.project_dir / "chapters" / f"vol{vol_num:02d}" / "cards"

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
                "message": f"章节文件不存在: {chapter_file}",
            }

        # 尝试自动分离
        success = self.separate_generated_chapter(chapter_file, cards_dir)

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
