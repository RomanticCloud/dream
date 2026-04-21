#!/usr/bin/env python3
"""状态跟踪模块 - 跟踪人物状态、事件线程、伏笔
用于提供中期一致性保障
"""

from __future__ import annotations

import re
from pathlib import Path

from common_io import (
    extract_body,
    extract_section,
    extract_bullets,
    extract_all_bullets,
    load_json_file,
    save_json_file,
)
from global_clock import GlobalClock


class StateTracker:
    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        self.context_dir = project_dir / "context"
        self.context_dir.mkdir(exist_ok=True)
        self.state_file = self.context_dir / "state_tracker.json"
        self.global_clock = GlobalClock(project_dir)
        self._load_state()

    def _load_state(self):
        """加载状态文件"""
        if self.state_file.exists():
            self.state = load_json_file(self.state_file)
        else:
            self.state = {
                "characters": {},
                "plot_threads": [],
                "foreshadowing": [],
                "last_updated_chapter": 0,
            }
            self._save_state()

    def _save_state(self):
        """保存状态文件"""
        save_json_file(self.state_file, self.state)

    def update_character_state(self, chapter_path: Path):
        """更新人物状态

        从工作卡和正文中提取：
        - 当前位置
        - 情绪状态
        - 当前目标
        - 与其他人物的关系变化
        """
        chapter_name = chapter_path.name
        
        # 幂等性保护：检查是否已处理过此章节
        for char_data in self.state["characters"].values():
            if char_data["states"] and char_data["states"][-1]["chapter"] == chapter_name:
                # 已处理过此章节，跳过
                return
        
        content = chapter_path.read_text(encoding="utf-8")
        body = extract_body(content)

        # 从状态卡提取
        status_card = extract_section(content, "### 1. 状态卡")
        status_bullets = extract_bullets(status_card)

        # 从关系卡提取
        relationship_card = extract_section(content, "### 4. 关系卡")
        relationship_bullets = extract_bullets(relationship_card)

        # 从正文中提取人物信息
        characters_in_chapter = self._extract_characters_from_body(body)

        # 从状态卡中补充主角信息
        main_location = status_bullets.get("主角当前位置", "未知")
        main_emotion = status_bullets.get("主角当前情绪", "未知")
        main_goal = status_bullets.get("主角当前目标", "未知")

        # 确定主角名称（从关系卡或状态卡中提取第一个出现的人物）
        main_char = None
        if relationship_bullets:
            main_chars_text = relationship_bullets.get("主要人物", "")
            if main_chars_text:
                main_char = main_chars_text.split("、")[0].strip()

        if main_char and main_char in characters_in_chapter:
            characters_in_chapter[main_char]["location"] = main_location
            characters_in_chapter[main_char]["emotion"] = main_emotion
            characters_in_chapter[main_char]["goal"] = main_goal

        # 从关系卡中提取关系变化
        relationship_change = relationship_bullets.get("人物变化", "")
        if relationship_change:
            for char_name in characters_in_chapter:
                characters_in_chapter[char_name]["relationship_changes"].append(
                    relationship_change
                )

        for char_name, char_info in characters_in_chapter.items():
            if char_name not in self.state["characters"]:
                self.state["characters"][char_name] = {
                    "first_appearance": chapter_path.name,
                    "states": [],
                }

            # 添加新状态
            self.state["characters"][char_name]["states"].append(
                {
                    "chapter": chapter_path.name,
                    "location": char_info.get("location", "未知"),
                    "emotion": char_info.get("emotion", "未知"),
                    "goal": char_info.get("goal", "未知"),
                    "relationship_changes": char_info.get("relationship_changes", []),
                }
            )

        self._save_state()

    def _extract_characters_from_body(self, body: str) -> dict:
        """从正文中提取人物信息

        简化实现：提取人物名称和基本信息
        """
        characters = {}

        # 提取对话中的人物（使用 lookahead 避免包含动作动词）
        dialogue_pattern = r"([\u4e00-\u9fa5]{2,4})(?=[说|道|问|答|想|看|走|跑|：|:])"
        matches = re.findall(dialogue_pattern, body)

        # 过滤掉常见非人物词
        non_character_words = {"他", "她", "它", "这", "那", "什么", "怎么", "为什么", "哪里", "谁"}
        for name in set(matches):
            if name not in non_character_words and len(name) >= 2:
                characters[name] = {
                    "location": "未知",
                    "emotion": "未知",
                    "goal": "未知",
                    "relationship_changes": [],
                }

        return characters

    def track_plot_threads(self, chapter_path: Path):
        """跟踪事件线程

        维护三个列表：
        - 已发生的重要事件
        - 进行中的事件线程
        - 待解决的冲突/问题
        """
        content = chapter_path.read_text(encoding="utf-8")

        # 从情节卡提取
        plot_card = extract_section(content, "### 2. 情节卡")
        plot_bullets = extract_all_bullets(plot_card)

        # 从承接卡提取待解决问题
        carry_card = extract_section(content, "### 6. 承上启下卡")
        carry_bullets = extract_all_bullets(carry_card)

        # 更新事件线程
        chapter_events = {
            "chapter": chapter_path.name,
            "events": plot_bullets,
            "unresolved_conflicts": carry_bullets,
        }

        self.state["plot_threads"].append(chapter_events)

        # 只保留最近10章的事件线程
        if len(self.state["plot_threads"]) > 10:
            self.state["plot_threads"] = self.state["plot_threads"][-10:]

        self._save_state()

    def track_foreshadowing(self, chapter_path: Path):
        """跟踪伏笔

        维护：
        - 已埋下的伏笔
        - 待回收的伏笔
        - 已回收的伏笔
        """
        content = chapter_path.read_text(encoding="utf-8")

        # 从情节卡提取伏笔信息
        plot_card = extract_section(content, "### 2. 情节卡")
        plot_bullets = extract_bullets(plot_card)

        # 检查是否有新伏笔
        new_foreshadowing = plot_bullets.get("新埋伏笔", "")
        if new_foreshadowing:
            self.state["foreshadowing"].append(
                {
                    "planted_chapter": chapter_path.name,
                    "content": new_foreshadowing,
                    "status": "planted",  # planted, pending, resolved
                    "resolved_chapter": None,
                }
            )

        # 检查是否有伏笔回收
        resolved_foreshadowing = plot_bullets.get("回收伏笔", "")
        if resolved_foreshadowing:
            # 标记对应的伏笔为已回收
            for foreshadow in self.state["foreshadowing"]:
                if foreshadow["status"] == "planted" and self._is_similar_foreshadowing(
                    foreshadow["content"], resolved_foreshadowing
                ):
                    foreshadow["status"] = "resolved"
                    foreshadow["resolved_chapter"] = chapter_path.name
                    break

        # 从资源卡提取伏笔
        resource_card = extract_section(content, "### 3. 资源卡")
        resource_bullets = extract_bullets(resource_card)
        resource_foreshadowing = resource_bullets.get("伏笔", "")
        if resource_foreshadowing and resource_foreshadowing != new_foreshadowing:
            self.state["foreshadowing"].append(
                {
                    "planted_chapter": chapter_path.name,
                    "content": resource_foreshadowing,
                    "status": "planted",
                    "resolved_chapter": None,
                }
            )

        self._save_state()

    def _is_similar_foreshadowing(self, text1: str, text2: str) -> bool:
        """检查两个伏笔是否相似

        简化实现：检查关键词重叠
        """
        # 提取关键词（简化：取前10个字符）
        key1 = text1[:10] if len(text1) > 10 else text1
        key2 = text2[:10] if len(text2) > 10 else text2

        return key1 in text2 or key2 in text1

    def get_state_summary(self, chapter_num: int) -> str:
        """获取指定章节前的状态摘要

        用于生成下一章时提供上下文
        """
        summary_parts = []

        # 1. 人物状态摘要
        if self.state["characters"]:
            summary_parts.append("## 人物当前状态")
            for char_name, char_data in self.state["characters"].items():
                if char_data["states"]:
                    latest_state = char_data["states"][-1]
                    summary_parts.append(
                        f"- {char_name}: {latest_state['location']}, "
                        f"{latest_state['emotion']}, 目标: {latest_state['goal']}"
                    )

        # 2. 最近的事件线程
        recent_threads = self.state["plot_threads"][-3:]  # 最近3章
        if recent_threads:
            summary_parts.append("\n## 最近事件")
            for thread in recent_threads:
                if thread.get("events"):
                    for event in thread["events"][:2]:  # 每章最多2个事件
                        summary_parts.append(f"- {event}")

        # 3. 待回收的伏笔
        pending_foreshadowing = [
            f for f in self.state["foreshadowing"] if f["status"] == "planted"
        ]
        if pending_foreshadowing:
            summary_parts.append("\n## 待回收的伏笔")
            for foreshadow in pending_foreshadowing[-5:]:  # 最近5个
                summary_parts.append(
                    f"- {foreshadow['content']} (埋于{foreshadow['planted_chapter']})"
                )

        # 添加时间轴摘要
        time_summary = self.get_time_summary()
        if time_summary:
            summary_parts.insert(0, f"## 当前时间: {time_summary}\n")

        return "\n".join(summary_parts)

    def update_last_chapter(self, chapter_num: int):
        """更新最后处理的章节号"""
        self.state["last_updated_chapter"] = chapter_num
        self._save_state()

    def update_global_time(self, chapter_path: Path, chapter_num: int) -> dict:
        """更新全局时间轴

        从状态卡中提取时间流逝和时间点，推进全局时钟

        Args:
            chapter_path: 章节文件路径
            chapter_num: 章节号

        Returns:
            更新后的当前时间字典
        """
        content = chapter_path.read_text(encoding="utf-8")

        # 从状态卡提取时间信息
        status_card = extract_section(content, "### 1. 状态卡")
        status_bullets = extract_bullets(status_card)

        elapsed = status_bullets.get("本章时间流逝", "")
        time_point = status_bullets.get("本章结束时时间点", "")

        if not elapsed or not time_point:
            # 没有时间信息，跳过
            return self.global_clock.get_status()["current"]

        chapter_id = f"ch{chapter_num:02d}"

        try:
            result = self.global_clock.advance(elapsed, time_point, chapter_id)
            return result
        except Exception as e:
            # 时间推进失败，记录但不中断
            print(f"⚠️ 时间推进失败: {e}")
            return self.global_clock.get_status()["current"]

    def get_time_summary(self) -> str:
        """获取时间轴摘要"""
        status = self.global_clock.get_status()
        current = status["current"]

        summary = f"当前时间: {current['description']}"
        if status["last_chapter"]:
            summary += f" (更新于 {status['last_chapter']['id']})"

        return summary
