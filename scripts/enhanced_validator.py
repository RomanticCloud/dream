#!/usr/bin/env python3
"""增强的章节验证器 - 添加跨章一致性检查，防止漂移累积"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from common_io import extract_body, extract_section, extract_bullets
from narrative_context import NarrativeContext
from state_tracker import StateTracker


@dataclass
class ValidationIssue:
    severity: str  # "error", "warning", "info"
    message: str
    suggestion: Optional[str] = None


class EnhancedValidator:
    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        self.narrative_context = NarrativeContext(project_dir)
        self.state_tracker = StateTracker(project_dir)

    def validate_cross_chapter_consistency(
        self, current_chapter_path: Path, previous_chapter_path: Path
    ) -> list[ValidationIssue]:
        """验证跨章一致性

        检查项：
        1. 人物状态是否一致
        2. 场景位置是否合理衔接
        3. 时间线是否合理
        """
        issues = []

        try:
            current_content = current_chapter_path.read_text(encoding="utf-8")
            previous_content = previous_chapter_path.read_text(encoding="utf-8")
        except FileNotFoundError as e:
            issues.append(ValidationIssue(
                severity="error",
                message=f"章节文件不存在: {e}",
                suggestion="请检查章节文件路径是否正确"
            ))
            return issues
        except Exception as e:
            issues.append(ValidationIssue(
                severity="error",
                message=f"读取章节文件失败: {e}",
                suggestion="请检查文件权限和编码"
            ))
            return issues

        # 1. 检查人物状态一致性
        char_issues = self._check_character_consistency(
            current_content, previous_content
        )
        issues.extend(char_issues)

        # 2. 检查场景位置衔接
        location_issues = self._check_location_continuity(
            current_content, previous_content
        )
        issues.extend(location_issues)

        # 3. 检查时间线合理性
        timeline_issues = self._check_timeline合理性(
            current_content, previous_content
        )
        issues.extend(timeline_issues)

        return issues

    def _check_character_consistency(
        self, current_content: str, previous_content: str
    ) -> list[ValidationIssue]:
        """检查人物状态一致性"""
        issues = []

        # 从状态卡提取人物信息
        current_status = extract_section(current_content, "### 1. 状态卡")
        previous_status = extract_section(previous_content, "### 1. 状态卡")

        current_bullets = extract_bullets(current_status)
        previous_bullets = extract_bullets(previous_status)

        # 检查主角状态变化是否合理
        if "主角当前情绪" in current_bullets and "主角当前情绪" in previous_bullets:
            current_emotion = current_bullets["主角当前情绪"]
            previous_emotion = previous_bullets["主角当前情绪"]

            # 简化检查：情绪不能突变（例如从快乐直接到愤怒）
            emotion_transitions = {
                "快乐": ["平静", "紧张", "担忧"],
                "愤怒": ["平静", "紧张", "担忧"],
                "悲伤": ["平静", "担忧"],
                "紧张": ["快乐", "愤怒", "悲伤", "平静"],
            }

            if previous_emotion in emotion_transitions:
                valid_transitions = emotion_transitions[previous_emotion]
                if (
                    current_emotion not in valid_transitions
                    and current_emotion != previous_emotion
                ):
                    issues.append(
                        ValidationIssue(
                            severity="warning",
                            message=f"人物情绪变化可能不合理：从 {previous_emotion} 到 {current_emotion}",
                            suggestion="请确保情绪变化有合理的铺垫",
                        )
                    )

        return issues

    def _check_location_continuity(
        self, current_content: str, previous_content: str
    ) -> list[ValidationIssue]:
        """检查场景位置衔接"""
        issues = []

        # 从状态卡提取位置信息
        current_status = extract_section(current_content, "### 1. 状态卡")
        previous_status = extract_section(previous_content, "### 1. 状态卡")

        current_bullets = extract_bullets(current_status)
        previous_bullets = extract_bullets(previous_status)

        # 检查位置变化
        if "主角当前位置" in current_bullets and "主角当前位置" in previous_bullets:
            current_location = current_bullets["主角当前位置"]
            previous_location = previous_bullets["主角当前位置"]

            # 如果位置发生变化，检查承接卡是否有说明
            if current_location != previous_location:
                carry_card = extract_section(current_content, "### 6. 承上启下卡")
                carry_bullets = extract_bullets(carry_card)

                if (
                    "场景转换" not in carry_bullets
                    and "位置变化" not in carry_bullets
                ):
                    issues.append(
                        ValidationIssue(
                            severity="info",
                            message=f"位置从 {previous_location} 变为 {current_location}，但承接卡未说明",
                            suggestion="建议在承接卡中说明位置变化",
                        )
                    )

        return issues

    def _check_timeline合理性(
        self, current_content: str, previous_content: str
    ) -> list[ValidationIssue]:
        """检查时间线合理性"""
        issues = []

        # 简化实现：检查是否有关于时间的描述
        time_keywords = ["第二天", "几天后", "一周后", "一个月后", "一年后"]

        current_body = extract_body(current_content)

        # 检查是否有时间跳跃
        for keyword in time_keywords:
            if keyword in current_body:
                # 检查承接卡是否有说明
                carry_card = extract_section(current_content, "### 6. 承上启下卡")
                carry_bullets = extract_bullets(carry_card)

                if "时间跳跃" not in carry_bullets:
                    issues.append(
                        ValidationIssue(
                            severity="info",
                            message=f"检测到时间跳跃（{keyword}），建议在承接卡中说明",
                            suggestion="建议在承接卡中说明时间变化",
                        )
                    )

        return issues

    def check_carry_over_fulfilled(
        self, previous_chapter_path: Path, current_chapter_path: Path
    ) -> list[ValidationIssue]:
        """检查上一章的承接要求是否被满足

        从上一章的承接卡提取"下章必须接住什么"
        检查当前章是否处理了这些要求
        """
        issues = []

        try:
            # 加载上一章的承接卡
            previous_content = previous_chapter_path.read_text(encoding="utf-8")
            carry_card = extract_section(previous_content, "### 6. 承上启下卡")
            carry_bullets = extract_bullets(carry_card)

            # 获取必须接住的内容
            must_handle = carry_bullets.get("下章必须接住什么", "")

            if not must_handle:
                return issues  # 没有明确要求，跳过

            # 检查当前章是否处理了这些要求
            current_content = current_chapter_path.read_text(encoding="utf-8")
            current_body = extract_body(current_content)

            # 简化检查：检查关键词是否在当前章中出现
            keywords = must_handle.split()
            found_keywords = [kw for kw in keywords if kw in current_body]

            if len(found_keywords) < len(keywords) * 0.5:  # 至少50%的关键词要出现
                issues.append(
                    ValidationIssue(
                        severity="warning",
                        message=f"上一章要求处理的内容可能未在本章充分体现：{must_handle}",
                        suggestion="请确保本章处理了上一章承接卡中要求的内容",
                    )
                )
        except FileNotFoundError as e:
            issues.append(ValidationIssue(
                severity="error",
                message=f"章节文件不存在: {e}",
                suggestion="请检查章节文件路径是否正确"
            ))
        except Exception as e:
            issues.append(ValidationIssue(
                severity="error",
                message=f"读取章节文件失败: {e}",
                suggestion="请检查文件权限和编码"
            ))

        return issues

    def detect_drift_patterns(self, state_history: list[dict]) -> list[ValidationIssue]:
        """检测漂移模式

        分析状态历史，检测：
        1. 人物性格漂移
        2. 能力体系漂移
        3. 世界观设定漂移
        """
        issues = []

        if len(state_history) < 3:
            return issues  # 需要至少3章数据才能检测模式

        # 1. 检测人物性格漂移
        char_drift = self._detect_character_drift(state_history)
        issues.extend(char_drift)

        # 2. 检测世界观漂移
        world_drift = self._detect_world_drift(state_history)
        issues.extend(world_drift)

        return issues

    def _detect_character_drift(self, state_history: list[dict]) -> list[ValidationIssue]:
        """检测人物性格漂移"""
        issues = []

        # 简化实现：检查人物情绪变化模式
        for chapter_data in state_history[-5:]:  # 检查最近5章
            if "narrative_summary" in chapter_data:
                summary = chapter_data["narrative_summary"]
                if isinstance(summary, dict) and "emotion_tone" in summary:
                    emotion = summary["emotion_tone"]
                    # 这里可以添加更复杂的漂移检测逻辑
                    pass

        return issues

    def _detect_world_drift(self, state_history: list[dict]) -> list[ValidationIssue]:
        """检测世界观漂移"""
        issues = []

        # 简化实现：检查设定关键词的一致性
        # 这里可以添加更复杂的检测逻辑

        return issues
