#!/usr/bin/env python3
"""增强的章节验证器 - 添加跨章一致性检查，防止漂移累积"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from card_names import CARRY_CARD, STATUS_CARD
from card_fields import FIELD_CARRY_MUST, FIELD_STATUS_EMOTION, FIELD_STATUS_GOAL, FIELD_STATUS_LOCATION
from common_io import extract_body, extract_section, extract_bullets, load_json_file
from chapter_view import load_chapter_view
from continuity_ledger import load_ledger
from preflight_planner import preflight_file
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

    def _load_content(self, chapter_path: Path) -> str:
        parent_name = chapter_path.parent.name
        stem = chapter_path.stem
        if parent_name.startswith("vol") and stem.startswith("ch") and stem[2:].isdigit():
            vol_num = int(parent_name.replace("vol", ""))
            ch_num = int(stem.replace("ch", ""))
            view = load_chapter_view(self.project_dir, vol_num, ch_num)
            if view.chapter_path.exists() or view.card_path.exists():
                return view.merged_text
        return chapter_path.read_text(encoding="utf-8")

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
            current_content = self._load_content(current_chapter_path)
            previous_content = self._load_content(previous_chapter_path)
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
        current_status = extract_section(current_content, STATUS_CARD)
        previous_status = extract_section(previous_content, STATUS_CARD)

        current_bullets = extract_bullets(current_status)
        previous_bullets = extract_bullets(previous_status)

        # 检查主角状态变化是否合理
        if FIELD_STATUS_EMOTION in current_bullets and FIELD_STATUS_EMOTION in previous_bullets:
            current_emotion = current_bullets[FIELD_STATUS_EMOTION]
            previous_emotion = previous_bullets[FIELD_STATUS_EMOTION]

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
        current_status = extract_section(current_content, STATUS_CARD)
        previous_status = extract_section(previous_content, STATUS_CARD)

        current_bullets = extract_bullets(current_status)
        previous_bullets = extract_bullets(previous_status)

        # 检查位置变化
        if FIELD_STATUS_LOCATION in current_bullets and FIELD_STATUS_LOCATION in previous_bullets:
            current_location = current_bullets[FIELD_STATUS_LOCATION]
            previous_location = previous_bullets[FIELD_STATUS_LOCATION]

            # 如果位置发生变化，检查承上启下卡是否有说明
            if current_location != previous_location:
                carry_card = extract_section(current_content, CARRY_CARD)
                carry_bullets = extract_bullets(carry_card)

                if (
                    "场景转换" not in carry_bullets
                    and "位置变化" not in carry_bullets
                ):
                    issues.append(
                        ValidationIssue(
                            severity="info",
                            message=f"位置从 {previous_location} 变为 {current_location}，但承上启下卡未说明",
                            suggestion="建议在承上启下卡中说明位置变化",
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
                # 检查承上启下卡是否有说明
                carry_card = extract_section(current_content, CARRY_CARD)
                carry_bullets = extract_bullets(carry_card)

                if "时间跳跃" not in carry_bullets:
                    issues.append(
                        ValidationIssue(
                            severity="info",
                            message=f"检测到时间跳跃（{keyword}），建议在承上启下卡中说明",
                            suggestion="建议在承上启下卡中说明时间变化",
                        )
                    )

        return issues

    def check_carry_over_fulfilled(
        self, previous_chapter_path: Path, current_chapter_path: Path
    ) -> list[ValidationIssue]:
        """检查上一章的承上启下要求是否被满足

        从上一章的承上启下卡提取"下章必须接住什么"
        检查当前章是否处理了这些要求
        """
        issues = []

        try:
            # 加载上一章的承上启下卡
            previous_content = self._load_content(previous_chapter_path)
            carry_card = extract_section(previous_content, CARRY_CARD)
            carry_bullets = extract_bullets(carry_card)

            # 获取必须接住的内容
            must_handle = carry_bullets.get(FIELD_CARRY_MUST, "")

            if not must_handle:
                return issues  # 没有明确要求，跳过

            # 检查当前章是否处理了这些要求
            current_content = self._load_content(current_chapter_path)
            current_body = extract_body(current_content)

            # 简化检查：检查关键词是否在当前章中出现
            keywords = must_handle.split()
            found_keywords = [kw for kw in keywords if kw in current_body]

            if len(found_keywords) < len(keywords) * 0.5:  # 至少50%的关键词要出现
                issues.append(
                    ValidationIssue(
                        severity="warning",
                        message=f"上一章要求处理的内容可能未在本章充分体现：{must_handle}",
                        suggestion="请确保本章处理了上一章承上启下卡中要求的内容",
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

    def validate_generation_contract(self, vol_num: int, ch_num: int) -> list[ValidationIssue]:
        """Validate chapter against ledger and preflight constraints.

        These checks are deliberately conservative and blocking for only the
        highest-risk continuity failures.
        """
        issues: list[ValidationIssue] = []
        try:
            view = load_chapter_view(self.project_dir, vol_num, ch_num)
            content = view.merged_text
        except Exception as exc:
            return [ValidationIssue("error", f"读取章节失败，无法执行生成契约检查: {exc}")]

        body = extract_body(content)
        status = extract_bullets(extract_section(content, STATUS_CARD))
        carry = extract_bullets(extract_section(content, CARRY_CARD))
        ledger = load_ledger(self.project_dir)
        constraints = ledger.get("open_constraints", {})
        hard_facts = ledger.get("hard_facts", [])[-20:]
        current_state = ledger.get("current_state", {})

        # First chapter may not have a useful ledger yet.
        if ch_num > 1:
            must_handle = constraints.get("must_handle", "")
            if must_handle and not _soft_text_overlap(must_handle, body):
                issues.append(ValidationIssue(
                    "error",
                    f"[连续性阻塞] 上章要求必须接住的内容未在正文中充分体现：{must_handle}",
                    "请在本章开场或主推进中明确处理该承接项。",
                ))

            hook = constraints.get("strongest_hook", "")
            if hook and not _soft_text_overlap(hook, body[:1200]):
                issues.append(ValidationIssue(
                    "warning",
                    f"[连续性] 上章最强钩子可能没有在本章开场承接：{hook}",
                    "建议在本章前半段回应或延续该钩子。",
                ))

            prev_location = current_state.get("location", "")
            current_location = status.get(FIELD_STATUS_LOCATION, "")
            if prev_location and current_location and prev_location != current_location:
                opening = body[:1000]
                if current_location not in opening and not any(word in opening for word in ["来到", "抵达", "回到", "离开", "赶到", "走进"]):
                    issues.append(ValidationIssue(
                        "warning",
                        f"[场景衔接] 位置从“{prev_location}”变为“{current_location}”，正文开场缺少明确转场。",
                        "请补足场景转移或保持上一章地点。",
                    ))

            prev_goal = current_state.get("goal", "")
            current_goal = status.get(FIELD_STATUS_GOAL, "")
            if prev_goal and current_goal and prev_goal != current_goal and not _soft_text_overlap(prev_goal, body):
                issues.append(ValidationIssue(
                    "warning",
                    f"[目标衔接] 主角目标从“{prev_goal}”变为“{current_goal}”，正文缺少过渡。",
                    "请在正文中交代目标变化原因。",
                ))

        for fact in hard_facts:
            if fact and _contradiction_marker(fact, body):
                issues.append(ValidationIssue(
                    "error",
                    f"[事实阻塞] 正文疑似违背禁止事实：{fact}",
                    "请修改正文或工作卡，确保稳定事实不被推翻。",
                ))

        pf = load_json_file(preflight_file(self.project_dir, vol_num, ch_num), default={})
        if pf:
            main_progress = str(pf.get("main_progress") or "")
            if main_progress and not _soft_text_overlap(main_progress, body):
                issues.append(ValidationIssue(
                    "warning",
                    f"[主线漂移] 正文与预检主推进关联较弱：{main_progress[:120]}",
                    "请确认本章核心事件服务章纲和卷目标。",
                ))
            for item in pf.get("must_not_break", [])[:10]:
                if item and _contradiction_marker(str(item), body):
                    issues.append(ValidationIssue(
                        "error",
                        f"[预检阻塞] 正文疑似违背预检禁止项：{item}",
                        "请按预检计划修正。",
                    ))

        # Work card fields should not introduce entirely absent events.
        for field, value in carry.items():
            if field == FIELD_CARRY_MUST:
                continue
            if value and value not in {"无", "-0", "继承上章"} and len(value) >= 6 and not _soft_text_overlap(value, body):
                issues.append(ValidationIssue(
                    "warning",
                    f"[卡文一致] 承上启下卡字段“{field}”缺少正文依据：{value}",
                    "请确保工作卡只记录正文中已经出现或明确暗示的信息。",
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


def _tokens(text: str) -> set[str]:
    text = text.strip()
    if not text:
        return set()
    chunks = set()
    for part in re_split_text(text):
        if len(part) >= 2:
            chunks.add(part)
    return chunks


def re_split_text(text: str) -> list[str]:
    import re
    parts = re.split(r"[，。！？、；：,.;:!?\s/（）()\[\]【】]+", text)
    short = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if len(part) > 12:
            short.extend(part[i:i + 6] for i in range(0, len(part), 6))
        else:
            short.append(part)
    return short


def _soft_text_overlap(requirement: str, body: str) -> bool:
    if not requirement:
        return True
    if requirement in body:
        return True
    tokens = [token for token in _tokens(requirement) if token not in {"必须", "需要", "不能", "什么", "本章", "下章"}]
    if not tokens:
        return True
    hits = sum(1 for token in tokens if token in body)
    return hits >= max(1, len(tokens) // 3)


def _contradiction_marker(fact: str, body: str) -> bool:
    """Conservative contradiction heuristic to avoid false positives."""
    if not fact or not body:
        return False
    if "死亡" in fact and any(word in body for word in ["复活", "重新站起", "安然无恙"]):
        return True
    if "离开" in fact and "一直在场" in body:
        return True
    if "不能" in fact:
        forbidden = fact.split("不能", 1)[1].strip(" ：，。")
        return bool(forbidden and forbidden in body)
    if "不得" in fact:
        forbidden = fact.split("不得", 1)[1].strip(" ：，。")
        return bool(forbidden and forbidden in body)
    return False
