#!/usr/bin/env python3
"""叙事上下文模块 - 提取和处理章节的叙事内容
用于提供即时场景连续性
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from common_io import (
    extract_body,
    load_json_file,
    save_json_file,
)


class NarrativeContext:
    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        self.context_dir = project_dir / "context"
        self.context_dir.mkdir(exist_ok=True)

    def extract_scene_anchor(self, chapter_path: Path, word_count: int = 400) -> str:
        """提取章节最后N字作为场景锚点

        Args:
            chapter_path: 章节文件路径
            word_count: 提取的字数（默认400字）

        Returns:
            场景锚点文本
        """
        content = chapter_path.read_text(encoding="utf-8")
        body = extract_body(content)

        if len(body) <= word_count:
            # 即使返回全文，也应从完整句子开始
            first_period = body.find("。")
            if 0 < first_period < len(body) - 1:
                return body[first_period + 1:].strip()
            return body.strip()

        anchor = body[-word_count:]

        # 找到第一个句号，从完整句子开始
        first_period = anchor.find("。")
        if first_period > 0:
            anchor = anchor[first_period + 1:]

        return anchor.strip()

    def generate_narrative_summary(self, chapter_path: Path) -> dict:
        """生成章节的结构化叙事摘要

        Returns:
            {
                "scene_location": "场景位置",
                "characters_present": ["出场人物"],
                "key_dialogue": ["关键对话片段"],
                "emotion_tone": "情绪基调",
                "main_action": "主要行动",
                "ending_hook": "结尾钩子"
            }
        """
        content = chapter_path.read_text(encoding="utf-8")
        body = extract_body(content)

        characters = self._extract_characters(body)
        location = self._extract_location(body)
        dialogues = self._extract_key_dialogues(body)
        emotion = self._extract_emotion_tone(body)
        action = self._extract_main_action(body)
        hook = self._extract_ending_hook(body)

        return {
            "scene_location": location,
            "characters_present": characters,
            "key_dialogue": dialogues[:3],
            "emotion_tone": emotion,
            "main_action": action,
            "ending_hook": hook,
        }

    def _extract_characters(self, body: str) -> list:
        """从正文中提取出场人物（常见人物称呼模式）"""
        patterns = [
            r"[\u4e00-\u9fa5]{2,4}(?=说|道|问|答|想|看|走|跑)",
            r"[\u4e00-\u9fa5]{2,4}(?=：|:)",
        ]

        characters = set()
        for pattern in patterns:
            matches = re.findall(pattern, body)
            characters.update(matches)

        return list(characters)

    def _extract_location(self, body: str) -> str:
        """从正文中提取场景位置"""
        location_patterns = [
            r"(在|位于|来到|到达|前往)([\u4e00-\u9fa5]{2,10})(里|内|外|上|下|前|后|旁|边)",
            r"([\u4e00-\u9fa5]{2,10})(房间|大厅|广场|街道|城市|森林|山脉)",
        ]

        for pattern in location_patterns:
            match = re.search(pattern, body)
            if match:
                return match.group(0)

        return "未知"

    def _extract_key_dialogues(self, body: str) -> list:
        """从正文中提取关键对话（引号内容）"""
        # 中文引号
        dialogues = re.findall(r"\u201c([^\u201d]{10,100})\u201d", body)

        # 英文引号 fallback
        if not dialogues:
            dialogues = re.findall(r'"([^"]{10,100})"', body)

        return dialogues[:3]

    def _extract_emotion_tone(self, body: str) -> str:
        """从正文中提取情绪基调"""
        emotion_words = {
            "紧张": ["紧张", "焦虑", "担忧", "害怕", "恐惧"],
            "愤怒": ["愤怒", "生气", "恼火", "暴怒", "怒"],
            "悲伤": ["悲伤", "难过", "伤心", "痛苦", "哀"],
            "快乐": ["快乐", "高兴", "开心", "喜悦", "笑"],
            "平静": ["平静", "冷静", "镇定", "从容", "淡"],
        }

        emotion_counts: dict[str, int] = {}
        for emotion, words in emotion_words.items():
            count = sum(1 for word in words if word in body)
            if count > 0:
                emotion_counts[emotion] = count

        if emotion_counts:
            return max(emotion_counts, key=emotion_counts.get)

        return "未知"

    def _extract_main_action(self, body: str) -> str:
        """从正文中提取主要行动（首尾段落）"""
        paragraphs = body.split("\n\n")

        if len(paragraphs) >= 2:
            first_para = paragraphs[0].strip()
            last_para = paragraphs[-1].strip()

            if len(first_para) > 50:
                first_para = first_para[:50] + "..."
            if len(last_para) > 50:
                last_para = last_para[:50] + "..."

            return f"开头：{first_para}\n结尾：{last_para}"

        return "未知"

    def _extract_ending_hook(self, body: str) -> str:
        """从正文中提取结尾钩子（最后100字）"""
        if len(body) <= 100:
            return body.strip()

        return body[-100:].strip()

    def save_chapter_context(self, chapter_num: int, context: dict):
        """保存章节上下文到 context/chapter_context.json

        Args:
            chapter_num: 章节号
            context: 上下文数据
        """
        context_file = self.context_dir / "chapter_context.json"

        all_context = load_json_file(context_file)

        all_context[f"chapter_{chapter_num}"] = {
            "timestamp": datetime.now().isoformat(),
            **context,
        }

        save_json_file(context_file, all_context)

    def load_previous_context(self, chapter_num: int, lookback: int = 1) -> dict:
        """加载前N章的上下文

        Args:
            chapter_num: 当前章节号
            lookback: 回溯章节数（默认1章）

        Returns:
            包含前N章上下文的字典
        """
        context_file = self.context_dir / "chapter_context.json"

        if not context_file.exists():
            return {}

        all_context = load_json_file(context_file)

        result = {}
        for i in range(1, lookback + 1):
            prev_chapter = chapter_num - i
            if prev_chapter >= 1:
                key = f"chapter_{prev_chapter}"
                if key in all_context:
                    result[f"prev_{i}"] = all_context[key]

        return result
