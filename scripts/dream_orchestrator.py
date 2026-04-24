#!/usr/bin/env python3
"""Script-controlled workflow orchestrator for the dream skill."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from state_builders import (
    WORD_TARGET_OPTIONS,
    CHAPTER_LENGTH_OPTIONS,
    POWER_SYSTEM_OPTIONS,
    BREAKTHROUGH_OPTIONS,
    LIMITATION_OPTIONS,
    PACING_OPTIONS,
    STYLE_TONE_OPTIONS,
    MAIN_GENRE_OPTIONS,
    SUB_GENRE_OPTIONS,
    NARRATIVE_STYLE_OPTIONS,
    SETTING_OPTIONS,
    SOCIETY_OPTIONS,
    ADVENTURE_OPTIONS,
    CRISIS_OPTIONS,
    ROMANCE_OPTIONS,
    RELATIONSHIP_OPTIONS,
    ANTAGONIST_OPTIONS,
    ANTAGONIST_CURVE_OPTIONS,
    CONFLICT_LEVEL_OPTIONS,
    TENSION_OPTIONS,
    BATCH_SIZE_OPTIONS,
    get_escalation_path_options,
    get_delivery_options,
    get_first_volume_goal_options,
    get_first_volume_hook_options,
    generate_book_title_options,
    get_scene_options,
    get_conflict_options,
    get_reader_hook_options,
    default_positioning_values,
    build_basic_specs,
    build_positioning,
    build_protagonist,
    build_power_system,
    build_world,
    build_factions,
    build_characters,
    build_volume_architecture,
    build_batch_plan,
    build_naming,
)
from common_io import save_project_state


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
RUNTIME_DIR = SKILL_DIR / ".runtime"

INIT_OPTIONS = [
    {"label": "新建项目", "description": "从零开始建立新的创意写作项目"},
    {"label": "继续已有项目", "description": "扫描并继续一个已存在的创意写作项目"},
    {"label": "仅规划", "description": "只做规划，不进入正式项目流程"},
    {"label": "退出", "description": "结束当前流程"},
]

ACTION_OPTIONS = [
    {"label": "继续写作", "description": "继续推进当前项目正文"},
    {"label": "本批检查", "description": "检查当前批次连续性与一致性"},
    {"label": "本卷收尾", "description": "推进本卷收尾与卷尾检查"},
    {"label": "导出归档", "description": "导出当前项目文本"},
    {"label": "结束", "description": "结束当前工作流"},
]

FINAL_OPTIONS = [
    {"label": "扩写补字数", "description": "扩写内容以补足目标字数"},
    {"label": "增加番外", "description": "新增番外内容"},
    {"label": "精修润色", "description": "精修现有正文"},
    {"label": "修改设定", "description": "调整设定并同步材料"},
    {"label": "审阅导出", "description": "审阅后导出最终文本"},
    {"label": "结束", "description": "结束当前工作流"},
]

NEW_PROJECT_REVIEW_OPTIONS = [
    {"label": "确认并进入下一阶段", "description": "锁定基础信息，后续进入项目定位"},
    {"label": "重新填写基础信息", "description": "清空当前基础信息并重新收集"},
    {"label": "退出", "description": "结束当前流程"},
]

POSITIONING_REVIEW_OPTIONS = [
    {"label": "确认并进入下一阶段", "description": "锁定项目定位，后续进入主角设定"},
    {"label": "重新填写项目定位", "description": "清空当前项目定位并重新收集"},
    {"label": "退出", "description": "结束当前流程"},
]

LOCK_MODE_OPTIONS = [
    {"label": "用户锁定", "description": "后续设定从系统推导候选中逐项选择"},
    {"label": "模型推荐", "description": "后续设定由系统推导候选并按推荐项自动锁定"},
]

PROTAGONIST_REVIEW_OPTIONS = [
    {"label": "确认并进入下一阶段", "description": "锁定主角设定，进入后续阶段"},
    {"label": "重新选择主角设定", "description": "保留候选并重新选择"},
    {"label": "退出", "description": "结束当前流程"},
]

WORLD_REVIEW_OPTIONS = [
    {"label": "确认并进入下一阶段", "description": "锁定世界观设定，进入后续阶段"},
    {"label": "重新选择世界观设定", "description": "保留候选并重新选择"},
    {"label": "退出", "description": "结束当前流程"},
]

POWER_REVIEW_OPTIONS = [
    {"label": "确认并进入下一阶段", "description": "锁定力量体系，进入世界观设定"},
    {"label": "重新选择力量体系", "description": "保留候选并重新选择"},
    {"label": "退出", "description": "结束当前流程"},
]

FACTIONS_REVIEW_OPTIONS = [
    {"label": "确认并进入下一阶段", "description": "锁定势力设定，进入角色关系"},
    {"label": "重新选择势力设定", "description": "保留候选并重新选择"},
    {"label": "退出", "description": "结束当前流程"},
]

CHARACTERS_REVIEW_OPTIONS = [
    {"label": "确认并进入下一阶段", "description": "锁定角色关系，进入卷章架构"},
    {"label": "重新选择角色关系", "description": "保留候选并重新选择"},
    {"label": "退出", "description": "结束当前流程"},
]

VOLUME_REVIEW_OPTIONS = [
    {"label": "确认并进入下一阶段", "description": "锁定卷章架构，进入命名阶段"},
    {"label": "重新选择卷章架构", "description": "保留候选并重新选择"},
    {"label": "退出", "description": "结束当前流程"},
]

NAMING_REVIEW_OPTIONS = [
    {"label": "确认完成前期设定", "description": "锁定命名并完成全部前期设定"},
    {"label": "重新选择书名", "description": "保留候选并重新选择"},
    {"label": "退出", "description": "结束当前流程"},
]

POST_SETUP_ACTION_OPTIONS = [
    {"label": "开始生成正文", "description": "落盘当前设定并进入正文生成主链"},
    {"label": "查看设定总览", "description": "查看当前已锁定的全部前期设定"},
    {"label": "结束", "description": "结束当前流程"},
]

PROTAGONIST_FIELD_SPECS = [
    ("name", "PROTAGONIST_PICK_NAME", "主角姓名", "name_candidates"),
    ("gender", "PROTAGONIST_PICK_GENDER", "主角性别", "gender_candidates"),
    ("age_group", "PROTAGONIST_PICK_AGE_GROUP", "年龄段", "age_group_candidates"),
    ("starting_identity", "PROTAGONIST_PICK_STARTING_IDENTITY", "起点身份", "starting_identity_candidates"),
    ("starting_level", "PROTAGONIST_PICK_STARTING_LEVEL", "起点实力", "starting_level_candidates"),
    ("personality", "PROTAGONIST_PICK_PERSONALITY", "核心性格", "personality_candidates"),
    ("core_desire", "PROTAGONIST_PICK_CORE_DESIRE", "核心欲望", "core_desire_candidates"),
    ("deepest_fear", "PROTAGONIST_PICK_DEEPEST_FEAR", "深层恐惧", "deepest_fear_candidates"),
    ("long_term_goal", "PROTAGONIST_PICK_LONG_TERM_GOAL", "长期目标", "long_term_goal_candidates"),
    ("ability", "PROTAGONIST_PICK_ABILITY", "特殊能力", "ability_candidates"),
]

WORLD_FIELD_SPECS = [
    ("setting_type", "WORLD_PICK_SETTING_TYPE", "背景设定", "setting_type_candidates", False, 1, 1),
    ("society_structure", "WORLD_PICK_SOCIETY_STRUCTURE", "社会结构", "society_structure_candidates", False, 1, 1),
    ("main_scene", "WORLD_PICK_MAIN_SCENE", "主要场景", "main_scene_candidates", True, 1, 2),
    ("adventure_zone", "WORLD_PICK_ADVENTURE_ZONE", "冒险区域", "adventure_zone_candidates", True, 1, 2),
    ("main_crisis", "WORLD_PICK_MAIN_CRISIS", "主要危机", "main_crisis_candidates", True, 1, 2),
    ("scene_layers", "WORLD_PICK_SCENE_LAYERS", "场景层级", "scene_layers_candidates", False, 1, 1),
]

POWER_FIELD_SPECS = [
    ("main_system", "POWER_PICK_MAIN_SYSTEM", "主要修炼体系", "main_system_candidates", False, 1, 1),
    ("levels", "POWER_PICK_LEVELS", "境界划分", "levels_candidates", False, 1, 1),
    ("breakthrough_condition", "POWER_PICK_BREAKTHROUGH", "突破条件", "breakthrough_condition_candidates", False, 1, 1),
    ("limitation", "POWER_PICK_LIMITATION", "力量限制", "limitation_candidates", False, 1, 1),
    ("unique_trait", "POWER_PICK_UNIQUE_TRAIT", "修炼体系特点", "unique_trait_candidates", False, 1, 1),
    ("resource_economy", "POWER_PICK_RESOURCE_ECONOMY", "资源/货币体系", "resource_economy_candidates", False, 1, 1),
]

FACTIONS_FIELD_SPECS = [
    ("player_faction", "FACTIONS_PICK_PLAYER", "主角势力", "player_faction_candidates", False, 1, 1),
    ("enemy_faction", "FACTIONS_PICK_ENEMY", "反派势力", "enemy_faction_candidates", False, 1, 1),
    ("neutral_faction", "FACTIONS_PICK_NEUTRAL", "中立势力", "neutral_faction_candidates", False, 1, 1),
]

CHARACTERS_FIELD_SPECS = [
    ("romance_type", "CHARACTERS_PICK_ROMANCE", "感情线", "romance_type_candidates", False, 1, 1),
    ("key_relationship_types", "CHARACTERS_PICK_RELATION_TYPES", "主要关系类型", "key_relationship_types_candidates", True, 1, 3),
    ("main_antagonist_type", "CHARACTERS_PICK_ANTAGONIST", "核心对立面", "main_antagonist_type_candidates", False, 1, 1),
    ("antagonist_curve", "CHARACTERS_PICK_ANTAGONIST_CURVE", "反派强度曲线", "antagonist_curve_candidates", False, 1, 1),
    ("conflict_levels", "CHARACTERS_PICK_CONFLICT_LEVELS", "冲突层级", "conflict_levels_candidates", True, 1, 3),
    ("main_factions", "CHARACTERS_PICK_MAIN_FACTIONS", "主要势力组合", "main_factions_candidates", False, 1, 1),
    ("relationship_tension", "CHARACTERS_PICK_RELATION_TENSION", "关系张力来源", "relationship_tension_candidates", True, 1, 2),
]

VOLUME_FIELD_SPECS = [
    ("book_escalation_path", "VOLUME_PICK_ESCALATION", "全书抬升路径", "book_escalation_path_candidates", False, 1, 1),
    ("delivery_matrix", "VOLUME_PICK_DELIVERY", "每卷交付承诺", "delivery_matrix_candidates", False, 1, 1),
    ("batch_size_label", "VOLUME_PICK_BATCH_SIZE", "每批章节数", "batch_size_label_candidates", False, 1, 1),
    ("first_volume_goal", "VOLUME_PICK_FIRST_GOAL", "首卷目标", "first_volume_goal_candidates", False, 1, 1),
    ("first_volume_hook", "VOLUME_PICK_FIRST_HOOK", "首卷钩子", "first_volume_hook_candidates", False, 1, 1),
    ("first_batch_opening_mode", "VOLUME_PICK_OPENING_MODE", "开局链", "first_batch_opening_mode_candidates", False, 1, 1),
]

NAMING_FIELD_SPECS = [
    ("selected_book_title", "NAMING_PICK_TITLE", "书名", "book_title_candidates", False, 1, 1),
]

POWER_GENRES = {"都市高武", "玄幻奇幻", "仙侠修真"}

OPENING_MODE_OPTIONS = [
    "开局受压 -> 获得机遇 -> 首次成功 -> 站稳脚跟",
    "开局平平 -> 意外机遇 -> 小试牛刀 -> 初露头角",
    "开局困境 -> 系统/导师帮助 -> 快速成长 -> 一鸣惊人",
]

STOP_WORDS = {"停止", "退出", "中止", "cancel", "stop"}


@dataclass
class SessionState:
    session_id: str
    current_node: str
    workspace: str
    history: list[dict[str, Any]]
    selected_project: str | None
    retry_count: dict[str, int]
    mode: str
    created_at: str
    updated_at: str
    new_project: dict[str, Any] = field(default_factory=dict)
    lock_mode: str | None = None
    derive_context: dict[str, Any] = field(default_factory=dict)
    derive_retry_count: dict[str, int] = field(default_factory=dict)


QUESTION_DEFS = {
    "INIT": {
        "header": "顶层分支",
        "text": "请选择当前要进入的分支：",
        "options": INIT_OPTIONS,
        "multiple": False,
    },
    "RESUME_PICK": {
        "header": "继续项目",
        "text": "请选择要继续的项目：",
        "options": [],
        "multiple": False,
    },
    "BASIC_SPECS_WORD_TARGET": {
        "header": "目标字数",
        "text": "请选择目标字数，或直接输入自定义值（如：60万字）。",
        "options": [{"label": label, "description": "标准目标字数"} for label in WORD_TARGET_OPTIONS],
        "multiple": False,
    },
    "BASIC_SPECS_CHAPTER_LENGTH": {
        "header": "单章字数",
        "text": "请选择单章字数，或直接输入自定义范围（如：2500-3500字）。",
        "options": [{"label": label, "description": "标准单章字数范围"} for label in CHAPTER_LENGTH_OPTIONS],
        "multiple": False,
    },
    "BASIC_SPECS_PACING": {
        "header": "节奏偏好",
        "text": "请选择节奏偏好：",
        "options": [{"label": label, "description": "基础信息字段"} for label in PACING_OPTIONS],
        "multiple": False,
    },
    "BASIC_SPECS_STYLE_TONE": {
        "header": "文风基调",
        "text": "请选择文风基调：",
        "options": [{"label": label, "description": "基础信息字段"} for label in STYLE_TONE_OPTIONS],
        "multiple": False,
    },
    "BASIC_SPECS_MAIN_GENRES": {
        "header": "主题材",
        "text": "请选择主要题材（1-3个）：",
        "options": [{"label": label, "description": "主要题材"} for label in MAIN_GENRE_OPTIONS],
        "multiple": True,
        "min_select": 1,
        "max_select": 3,
    },
    "BASIC_SPECS_SUB_GENRES": {
        "header": "补充元素",
        "text": "请选择补充元素（可选，可多选，也可直接回车跳过）：",
        "options": [{"label": label, "description": "补充元素"} for label in SUB_GENRE_OPTIONS],
        "multiple": True,
        "min_select": 0,
        "max_select": len(SUB_GENRE_OPTIONS),
    },
    "BASIC_SPECS_REVIEW": {
        "header": "基础信息复核",
        "text": "请确认基础信息是否锁定：",
        "options": NEW_PROJECT_REVIEW_OPTIONS,
        "multiple": False,
    },
    "POSITIONING_NARRATIVE_STYLE": {
        "header": "叙事方式",
        "text": "请选择叙事方式：",
        "options": [{"label": label, "description": "项目定位字段"} for label in NARRATIVE_STYLE_OPTIONS],
        "multiple": False,
    },
    "POSITIONING_MAIN_CONFLICTS": {
        "header": "主冲突",
        "text": "请选择主冲突（2-3个）：",
        "options": [],
        "multiple": True,
        "min_select": 2,
        "max_select": 3,
    },
    "POSITIONING_READER_HOOKS": {
        "header": "核心追读动力",
        "text": "请选择核心追读动力（2-3个）：",
        "options": [],
        "multiple": True,
        "min_select": 2,
        "max_select": 3,
    },
    "POSITIONING_REVIEW": {
        "header": "项目定位复核",
        "text": "请确认项目定位是否锁定：",
        "options": POSITIONING_REVIEW_OPTIONS,
        "multiple": False,
    },
    "LOCK_MODE_SELECT": {
        "header": "后续锁定模式",
        "text": "第二阶段已完成，请选择后续设定的锁定方式：",
        "options": LOCK_MODE_OPTIONS,
        "multiple": False,
    },
    "PROTAGONIST_REVIEW": {
        "header": "主角设定复核",
        "text": "请确认主角设定是否锁定：",
        "options": PROTAGONIST_REVIEW_OPTIONS,
        "multiple": False,
    },
    "WORLD_REVIEW": {
        "header": "世界观设定复核",
        "text": "请确认世界观设定是否锁定：",
        "options": WORLD_REVIEW_OPTIONS,
        "multiple": False,
    },
    "POWER_REVIEW": {
        "header": "力量体系复核",
        "text": "请确认力量体系是否锁定：",
        "options": POWER_REVIEW_OPTIONS,
        "multiple": False,
    },
    "FACTIONS_REVIEW": {
        "header": "势力设定复核",
        "text": "请确认势力设定是否锁定：",
        "options": FACTIONS_REVIEW_OPTIONS,
        "multiple": False,
    },
    "CHARACTERS_REVIEW": {
        "header": "角色关系复核",
        "text": "请确认角色关系是否锁定：",
        "options": CHARACTERS_REVIEW_OPTIONS,
        "multiple": False,
    },
    "VOLUME_REVIEW": {
        "header": "卷章架构复核",
        "text": "请确认卷章架构是否锁定：",
        "options": VOLUME_REVIEW_OPTIONS,
        "multiple": False,
    },
    "NAMING_REVIEW": {
        "header": "命名复核",
        "text": "请确认命名是否锁定：",
        "options": NAMING_REVIEW_OPTIONS,
        "multiple": False,
    },
    "POST_SETUP_ACTION": {
        "header": "后续动作",
        "text": "全部前期设定已完成，请选择下一步：",
        "options": POST_SETUP_ACTION_OPTIONS,
        "multiple": False,
    },
    "ACTION_MENU": {
        "header": "项目动作",
        "text": "请选择当前项目动作：",
        "options": ACTION_OPTIONS,
        "multiple": False,
    },
    "FINAL_MENU": {
        "header": "后处理动作",
        "text": "请选择完结后的下一步动作：",
        "options": FINAL_OPTIONS,
        "multiple": False,
    },
}


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def generated_project_name() -> str:
    return datetime.now().strftime("dream-%Y%m%d-%H%M%S")


def ensure_runtime_dir() -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)


def session_file(session_id: str) -> Path:
    return RUNTIME_DIR / f"session_{session_id}.json"


def save_session(state: SessionState) -> None:
    ensure_runtime_dir()
    state.updated_at = now_iso()
    session_file(state.session_id).write_text(
        json.dumps(asdict(state), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_session(session_id: str) -> SessionState:
    data = json.loads(session_file(session_id).read_text(encoding="utf-8"))
    return SessionState(**data)


def emit(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def clone_question_def(node: str) -> dict[str, Any]:
    return json.loads(json.dumps(QUESTION_DEFS[node], ensure_ascii=False))


def question_payload(
    state: SessionState,
    node: str,
    header: str,
    text: str,
    options: list[dict[str, str]],
    message: str | None = None,
    *,
    multiple: bool = False,
    input_mode: str = "choice",
    min_select: int | None = None,
    max_select: int | None = None,
) -> dict[str, Any]:
    state.current_node = node
    save_session(state)
    payload: dict[str, Any] = {
        "status": "question",
        "next_action": "ask_user",
        "session_id": state.session_id,
        "node": node,
        "question": {
            "header": header,
            "text": text,
            "options": options,
            "multiple": multiple,
            "input_mode": input_mode,
        },
    }
    if min_select is not None:
        payload["question"]["min_select"] = min_select
    if max_select is not None:
        payload["question"]["max_select"] = max_select
    if message:
        payload["message"] = message
    return payload


def ask_node(state: SessionState, node: str, message: str | None = None) -> dict[str, Any]:
    if node.startswith("PROTAGONIST_PICK_"):
        question = protagonist_pick_question(state, node)
        return question_payload(
            state,
            node,
            question["header"],
            question["text"],
            question["options"],
            message=message,
            multiple=question.get("multiple", False),
            input_mode=question.get("input_mode", "choice"),
            min_select=question.get("min_select"),
            max_select=question.get("max_select"),
        )
    if node.startswith("WORLD_PICK_"):
        question = world_pick_question(state, node)
        return question_payload(
            state,
            node,
            question["header"],
            question["text"],
            question["options"],
            message=message,
            multiple=question.get("multiple", False),
            input_mode=question.get("input_mode", "choice"),
            min_select=question.get("min_select"),
            max_select=question.get("max_select"),
        )
    if node.startswith("POWER_PICK_"):
        question = generic_pick_question(state, node, "POWER_DERIVE", POWER_FIELD_SPECS)
        return question_payload(state, node, question["header"], question["text"], question["options"], message=message, multiple=question.get("multiple", False), input_mode=question.get("input_mode", "choice"), min_select=question.get("min_select"), max_select=question.get("max_select"))
    if node.startswith("FACTIONS_PICK_"):
        question = generic_pick_question(state, node, "FACTIONS_DERIVE", FACTIONS_FIELD_SPECS)
        return question_payload(state, node, question["header"], question["text"], question["options"], message=message, multiple=question.get("multiple", False), input_mode=question.get("input_mode", "choice"), min_select=question.get("min_select"), max_select=question.get("max_select"))
    if node.startswith("CHARACTERS_PICK_"):
        question = generic_pick_question(state, node, "CHARACTERS_DERIVE", CHARACTERS_FIELD_SPECS)
        return question_payload(state, node, question["header"], question["text"], question["options"], message=message, multiple=question.get("multiple", False), input_mode=question.get("input_mode", "choice"), min_select=question.get("min_select"), max_select=question.get("max_select"))
    if node.startswith("VOLUME_PICK_"):
        question = generic_pick_question(state, node, "VOLUME_DERIVE", VOLUME_FIELD_SPECS)
        return question_payload(state, node, question["header"], question["text"], question["options"], message=message, multiple=question.get("multiple", False), input_mode=question.get("input_mode", "choice"), min_select=question.get("min_select"), max_select=question.get("max_select"))
    if node.startswith("NAMING_PICK_"):
        question = generic_pick_question(state, node, "NAMING_DERIVE", NAMING_FIELD_SPECS)
        return question_payload(state, node, question["header"], question["text"], question["options"], message=message, multiple=question.get("multiple", False), input_mode=question.get("input_mode", "choice"), min_select=question.get("min_select"), max_select=question.get("max_select"))
    question = clone_question_def(node)
    if node == "RESUME_PICK":
        workspace = Path(state.workspace)
        question["options"] = [
            {"label": candidate.name, "description": str(candidate)}
            for candidate in candidate_project_dirs(workspace)[:4]
        ]
    if node == "POSITIONING_MAIN_CONFLICTS":
        question["options"] = [
            {"label": label, "description": "根据主题材动态生成"}
            for label in positioning_conflict_options(state)
        ]
    if node == "POSITIONING_READER_HOOKS":
        question["options"] = [
            {"label": label, "description": "根据文风基调动态生成"}
            for label in positioning_hook_options(state)
        ]
    if node == "ACTION_MENU":
        project_name = Path(state.selected_project).name if state.selected_project else "当前项目"
        question["text"] = f"已选择项目 `{project_name}`，请选择下一步动作："
    if node == "BASIC_SPECS_REVIEW":
        question["text"] = build_basic_specs_review(state)
    if node == "POSITIONING_REVIEW":
        question["text"] = build_positioning_review(state)
    if node == "PROTAGONIST_REVIEW":
        question["text"] = build_protagonist_review(state)
    if node == "WORLD_REVIEW":
        question["text"] = build_world_review(state)
    if node == "POWER_REVIEW":
        question["text"] = build_power_review(state)
    if node == "FACTIONS_REVIEW":
        question["text"] = build_factions_review(state)
    if node == "CHARACTERS_REVIEW":
        question["text"] = build_characters_review(state)
    if node == "VOLUME_REVIEW":
        question["text"] = build_volume_review(state)
    if node == "NAMING_REVIEW":
        question["text"] = build_naming_review(state)
    return question_payload(
        state,
        node,
        question["header"],
        question["text"],
        question["options"],
        message=message,
        multiple=question.get("multiple", False),
        input_mode=question.get("input_mode", "choice"),
        min_select=question.get("min_select"),
        max_select=question.get("max_select"),
    )


def report_payload(state: SessionState, node: str, message: str) -> dict[str, Any]:
    state.current_node = node
    save_session(state)
    return {
        "status": "report",
        "next_action": "show_message",
        "session_id": state.session_id,
        "node": node,
        "message": message,
    }


def done_payload(state: SessionState, message: str) -> dict[str, Any]:
    state.current_node = "DONE"
    save_session(state)
    return {
        "status": "done",
        "next_action": "stop",
        "session_id": state.session_id,
        "node": "DONE",
        "message": message,
    }


def error_payload(state: SessionState | None, node: str, message: str) -> dict[str, Any]:
    return {
        "status": "error",
        "next_action": "stop",
        "session_id": state.session_id if state else None,
        "node": node,
        "message": message,
    }


def derive_payload(state: SessionState, node: str, derive: dict[str, Any], message: str | None = None) -> dict[str, Any]:
    state.current_node = node
    save_session(state)
    payload = {
        "status": "derive_options",
        "next_action": "derive_with_model",
        "session_id": state.session_id,
        "node": node,
        "derive": derive,
    }
    if message:
        payload["message"] = message
    return payload


def run_script_payload(state: SessionState, node: str, command: list[str], message: str) -> dict[str, Any]:
    state.current_node = node
    save_session(state)
    return {
        "status": "run_script",
        "next_action": "execute_script",
        "session_id": state.session_id,
        "node": node,
        "message": message,
        "script": {
            "kind": "python",
            "command": command,
        },
    }


def empty_new_project_state() -> dict[str, Any]:
    return {
        "project_name": "",
        "stage": "basic_specs",
        "basic_specs_raw": {
            "target_word_count": None,
            "chapter_length": None,
            "pacing": None,
            "style_tone": None,
            "main_genres": [],
            "sub_genres": [],
        },
        "basic_specs": None,
        "positioning_raw": {
            "narrative_style": None,
            "main_conflicts": [],
            "reader_hooks": [],
        },
        "positioning": None,
        "protagonist_raw": {
            "name": None,
            "gender": None,
            "age_group": None,
            "starting_identity": None,
            "starting_level": None,
            "personality": None,
            "core_desire": None,
            "deepest_fear": None,
            "long_term_goal": None,
            "ability": None,
        },
        "protagonist": None,
        "world_raw": {
            "setting_type": None,
            "society_structure": None,
            "main_scene": [],
            "adventure_zone": [],
            "main_crisis": [],
            "scene_layers": None,
        },
        "world": None,
        "power_raw": {
            "main_system": None,
            "levels": None,
            "breakthrough_condition": None,
            "limitation": None,
            "unique_trait": None,
            "resource_economy": None,
        },
        "power_system": None,
        "factions_raw": {
            "player_faction": None,
            "enemy_faction": None,
            "neutral_faction": None,
        },
        "factions": None,
        "characters_raw": {
            "romance_type": None,
            "key_relationship_types": [],
            "main_antagonist_type": None,
            "antagonist_curve": None,
            "conflict_levels": [],
            "main_factions": None,
            "relationship_tension": [],
        },
        "characters": None,
        "volume_raw": {
            "book_escalation_path": None,
            "delivery_matrix": None,
            "batch_size_label": None,
            "first_volume_goal": None,
            "first_volume_hook": None,
            "first_batch_opening_mode": None,
        },
        "volume_architecture": None,
        "batch_plan": None,
        "naming_raw": {
            "selected_book_title": None,
        },
        "naming": None,
        "materialized_project_dir": None,
    }


def new_session(workspace: Path) -> SessionState:
    session_id = f"dream-{uuid4().hex[:12]}"
    state = SessionState(
        session_id=session_id,
        current_node="INIT",
        workspace=str(workspace),
        history=[],
        selected_project=None,
        retry_count={},
        mode="interactive",
        created_at=now_iso(),
        updated_at=now_iso(),
        new_project=empty_new_project_state(),
    )
    save_session(state)
    return state


def normalize_answer(raw: str) -> str:
    return re.sub(r"\s+", " ", raw.strip())


def normalize_value(raw: Any) -> Any:
    if isinstance(raw, list):
        return [normalize_answer(str(item)) for item in raw if normalize_answer(str(item))]
    if not isinstance(raw, str):
        return raw
    text = raw.strip()
    if not text:
        return ""
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return normalize_answer(text)
    if isinstance(parsed, list):
        return [normalize_answer(str(item)) for item in parsed if normalize_answer(str(item))]
    if isinstance(parsed, str):
        return normalize_answer(parsed)
    return parsed


def invalid_answer(state: SessionState, node: str, message: str) -> dict[str, Any]:
    retries = state.retry_count.get(node, 0) + 1
    state.retry_count[node] = retries
    if retries >= 2:
        return error_payload(state, node, message)
    state.history.append({"node": node, "answer": None, "result": "retry"})
    return ask_node(state, node, message=message)


def candidate_project_dirs(workspace: Path) -> list[Path]:
    candidates: list[Path] = []
    if not workspace.exists():
        return candidates
    for child in sorted(workspace.iterdir()):
        if not child.is_dir():
            continue
        if (child / "wizard_state.json").exists() or (child / ".project_config.json").exists():
            candidates.append(child)
    return candidates


def parse_custom_word_target(user_input: str) -> str | None:
    match = re.search(r"(\d+)\s*万字?", user_input)
    if match:
        num = int(match.group(1))
        if num >= 10:
            return f"{num}万字"
    match = re.search(r"^(\d+)$", user_input.strip())
    if match:
        num = int(match.group(1))
        if 100000 <= num <= 5000000:
            return f"{num // 10000}万字"
    return None


def parse_custom_chapter_length(user_input: str) -> str | None:
    match = re.search(r"(\d+)\s*[-~]\s*(\d+)\s*字?", user_input)
    if match:
        low = int(match.group(1))
        high = int(match.group(2))
        if 1000 <= low <= high <= 20000:
            return f"{low}-{high}字"
    return None


def ensure_new_project(state: SessionState) -> dict[str, Any]:
    if not state.new_project:
        state.new_project = empty_new_project_state()
    return state.new_project


def build_basic_specs_review(state: SessionState) -> str:
    project = ensure_new_project(state)
    specs = project.get("basic_specs") or {}
    raw = project.get("basic_specs_raw") or {}
    derived = specs.get("derived") or {}
    sub_genres = raw.get("sub_genres") or []
    lines = [
        "请确认以下基础信息：",
        f"- 项目名称：{project.get('project_name') or '未命名项目'}",
        f"- 目标字数：{raw.get('target_word_count')}",
        f"- 单章字数：{raw.get('chapter_length')}",
        f"- 节奏偏好：{raw.get('pacing')}",
        f"- 文风基调：{raw.get('style_tone')}",
        f"- 主题材：{', '.join(raw.get('main_genres') or [])}",
        f"- 补充元素：{', '.join(sub_genres) if sub_genres else '无'}",
    ]
    if derived:
        lines.extend([
            "",
            "自动推导结果：",
            f"- 总章节数约：{derived.get('target_total_chapters')}章",
            f"- 推荐卷数：{derived.get('derived_total_volumes')}卷",
            f"- 每卷章节数约：{derived.get('derived_chapters_per_volume')}章",
        ])
    return "\n".join(lines)


def positioning_conflict_options(state: SessionState) -> list[str]:
    project = ensure_new_project(state)
    specs = project.get("basic_specs") or {}
    return get_conflict_options(specs.get("main_genres", []))


def positioning_hook_options(state: SessionState) -> list[str]:
    project = ensure_new_project(state)
    specs = project.get("basic_specs") or {}
    return get_reader_hook_options(specs.get("style_tone", "热血燃向"))


def build_positioning_review(state: SessionState) -> str:
    project = ensure_new_project(state)
    raw = project.get("positioning_raw") or {}
    positioning = project.get("positioning") or {}
    lines = [
        "请确认以下项目定位：",
        f"- 叙事方式：{raw.get('narrative_style')}",
        f"- 主冲突：{', '.join(raw.get('main_conflicts') or [])}",
        f"- 核心追读动力：{', '.join(raw.get('reader_hooks') or [])}",
        f"- 一句话主承诺：{positioning.get('core_promise')}",
        f"- 一句话卖点：{positioning.get('selling_point')}",
    ]
    return "\n".join(lines)


def protagonist_derive_spec() -> dict[str, str]:
    return {field: candidate_key for field, _node, _label, candidate_key in PROTAGONIST_FIELD_SPECS}


def protagonist_derive_request(state: SessionState) -> dict[str, Any]:
    project = ensure_new_project(state)
    return {
        "kind": "protagonist_seed",
        "inputs": {
            "project_name": project.get("project_name"),
            "basic_specs": project.get("basic_specs") or {},
            "positioning": project.get("positioning") or {},
        },
        "requirements": {
            "must_return_fields": ["recommended", "candidates", "reason"],
            "candidate_limit": 3,
            "field_map": protagonist_derive_spec(),
            "must_choose_best": True,
        },
        "schema_hint": {
            "recommended": {field: "string" for field, _node, _label, _candidate_key in PROTAGONIST_FIELD_SPECS},
            "candidates": {candidate_key: ["候选1", "候选2"] for _field, _node, _label, candidate_key in PROTAGONIST_FIELD_SPECS},
            "reason": "string",
        },
    }


def world_derive_spec() -> dict[str, str]:
    return {field: candidate_key for field, _node, _label, candidate_key, _multiple, _min_select, _max_select in WORLD_FIELD_SPECS}


def world_derive_request(state: SessionState) -> dict[str, Any]:
    project = ensure_new_project(state)
    return {
        "kind": "world_seed",
        "inputs": {
            "project_name": project.get("project_name"),
            "basic_specs": project.get("basic_specs") or {},
            "positioning": project.get("positioning") or {},
            "protagonist": project.get("protagonist") or {},
        },
        "requirements": {
            "must_return_fields": ["recommended", "candidates", "reason"],
            "candidate_limit": 3,
            "field_map": world_derive_spec(),
            "must_choose_best": True,
        },
        "schema_hint": {
            "recommended": {field: (["候选A", "候选B"] if multiple else "候选A") for field, _node, _label, _candidate_key, multiple, _min_select, _max_select in WORLD_FIELD_SPECS},
            "candidates": {candidate_key: ["候选1", "候选2"] for _field, _node, _label, candidate_key, _multiple, _min_select, _max_select in WORLD_FIELD_SPECS},
            "reason": "string",
        },
    }


def simple_derive_request(state: SessionState, kind: str, field_specs: list[tuple], inputs: dict[str, Any]) -> dict[str, Any]:
    field_map = {field: candidate_key for field, _node, _label, candidate_key, _multiple, _min_select, _max_select in field_specs}
    recommended_schema = {}
    for field, _node, _label, _candidate_key, multiple, _min_select, _max_select in field_specs:
        recommended_schema[field] = ["候选A", "候选B"] if multiple else "候选A"
    return {
        "kind": kind,
        "inputs": inputs,
        "requirements": {
            "must_return_fields": ["recommended", "candidates", "reason"],
            "candidate_limit": 3,
            "field_map": field_map,
            "must_choose_best": True,
        },
        "schema_hint": {
            "recommended": recommended_schema,
            "candidates": {candidate_key: ["候选1", "候选2"] for _field, _node, _label, candidate_key, _multiple, _min_select, _max_select in field_specs},
            "reason": "string",
        },
    }


def power_derive_request(state: SessionState) -> dict[str, Any]:
    project = ensure_new_project(state)
    inputs = {
        "basic_specs": project.get("basic_specs") or {},
        "positioning": project.get("positioning") or {},
        "protagonist": project.get("protagonist") or {},
    }
    return simple_derive_request(state, "power_seed", POWER_FIELD_SPECS, inputs)


def factions_derive_request(state: SessionState) -> dict[str, Any]:
    project = ensure_new_project(state)
    inputs = {
        "basic_specs": project.get("basic_specs") or {},
        "positioning": project.get("positioning") or {},
        "protagonist": project.get("protagonist") or {},
        "power_system": project.get("power_system") or {},
        "world": project.get("world") or {},
    }
    return simple_derive_request(state, "factions_seed", FACTIONS_FIELD_SPECS, inputs)


def characters_derive_request(state: SessionState) -> dict[str, Any]:
    project = ensure_new_project(state)
    inputs = {
        "basic_specs": project.get("basic_specs") or {},
        "positioning": project.get("positioning") or {},
        "protagonist": project.get("protagonist") or {},
        "world": project.get("world") or {},
        "factions": project.get("factions") or {},
    }
    return simple_derive_request(state, "characters_seed", CHARACTERS_FIELD_SPECS, inputs)


def volume_derive_request(state: SessionState) -> dict[str, Any]:
    project = ensure_new_project(state)
    specs = project.get("basic_specs") or {}
    positioning = project.get("positioning") or {}
    world = project.get("world") or {}
    inputs = {
        "basic_specs": specs,
        "positioning": positioning,
        "world": world,
        "constraints": {
            "volume_count": specs.get("target_volumes_numeric"),
            "chapters_per_volume": specs.get("chapters_per_volume"),
            "escalation_options": get_escalation_path_options(specs.get("style_tone", "热血燃向")),
            "delivery_options": get_delivery_options(positioning.get("main_conflicts", [])),
            "batch_size_options": BATCH_SIZE_OPTIONS,
            "first_goal_options": get_first_volume_goal_options(positioning.get("main_conflicts", [])),
            "first_hook_options": get_first_volume_hook_options(world.get("main_crisis", [])),
            "opening_mode_options": OPENING_MODE_OPTIONS,
        },
    }
    return simple_derive_request(state, "volume_seed", VOLUME_FIELD_SPECS, inputs)


def naming_derive_request(state: SessionState) -> dict[str, Any]:
    project = ensure_new_project(state)
    specs = project.get("basic_specs") or {}
    positioning = project.get("positioning") or {}
    title_candidates = generate_book_title_options(specs.get("main_genres", []), specs.get("style_tone", "热血燃向"), positioning.get("core_promise", ""))
    inputs = {
        "basic_specs": specs,
        "positioning": positioning,
        "title_candidates_seed": title_candidates,
    }
    return simple_derive_request(state, "naming_seed", NAMING_FIELD_SPECS, inputs)


def lock_mode_label(lock_mode: str | None) -> str:
    if lock_mode == "user_locked":
        return "用户锁定"
    if lock_mode == "model_recommended":
        return "模型推荐"
    return "未设置"


def continue_after_lock_mode(state: SessionState, message: str | None = None) -> dict[str, Any]:
    return derive_payload(
        state,
        "PROTAGONIST_DERIVE",
        protagonist_derive_request(state),
        message=message or f"已沿用既有锁定模式：{lock_mode_label(state.lock_mode)}。开始推导第三阶段：主角设定候选。",
    )


def continue_to_world(state: SessionState, message: str | None = None) -> dict[str, Any]:
    return derive_payload(
        state,
        "WORLD_DERIVE",
        world_derive_request(state),
        message=message or f"已沿用既有锁定模式：{lock_mode_label(state.lock_mode)}。开始推导第四阶段：世界观设定候选。",
    )


def has_power_stage(state: SessionState) -> bool:
    project = ensure_new_project(state)
    specs = project.get("basic_specs") or {}
    return bool(POWER_GENRES.intersection(set(specs.get("main_genres", []))))


def continue_after_protagonist(state: SessionState, message: str | None = None) -> dict[str, Any]:
    if has_power_stage(state):
        return derive_payload(state, "POWER_DERIVE", power_derive_request(state), message=message or f"已沿用既有锁定模式：{lock_mode_label(state.lock_mode)}。开始推导第四阶段：力量体系候选。")
    return continue_to_world(state, message=message or f"已沿用既有锁定模式：{lock_mode_label(state.lock_mode)}。跳过力量体系，开始推导第四阶段：世界观设定候选。")


def continue_to_factions(state: SessionState, message: str | None = None) -> dict[str, Any]:
    return derive_payload(state, "FACTIONS_DERIVE", factions_derive_request(state), message=message or f"已沿用既有锁定模式：{lock_mode_label(state.lock_mode)}。开始推导下一阶段：势力设定候选。")


def continue_to_characters(state: SessionState, message: str | None = None) -> dict[str, Any]:
    return derive_payload(state, "CHARACTERS_DERIVE", characters_derive_request(state), message=message or f"已沿用既有锁定模式：{lock_mode_label(state.lock_mode)}。开始推导下一阶段：角色关系候选。")


def continue_to_volume(state: SessionState, message: str | None = None) -> dict[str, Any]:
    return derive_payload(state, "VOLUME_DERIVE", volume_derive_request(state), message=message or f"已沿用既有锁定模式：{lock_mode_label(state.lock_mode)}。开始推导下一阶段：卷章架构候选。")


def continue_to_naming(state: SessionState, message: str | None = None) -> dict[str, Any]:
    return derive_payload(state, "NAMING_DERIVE", naming_derive_request(state), message=message or f"已沿用既有锁定模式：{lock_mode_label(state.lock_mode)}。开始推导最后阶段：命名候选。")


def build_protagonist_review(state: SessionState) -> str:
    project = ensure_new_project(state)
    protagonist = project.get("protagonist") or project.get("protagonist_raw") or {}
    lines = [
        "请确认以下主角设定：",
        f"- 姓名：{protagonist.get('name')}",
        f"- 性别：{protagonist.get('gender')}",
        f"- 年龄段：{protagonist.get('age_group')}",
        f"- 起点身份：{protagonist.get('starting_identity')}",
        f"- 起点实力：{protagonist.get('starting_level')}",
        f"- 核心性格：{protagonist.get('personality')}",
        f"- 核心欲望：{protagonist.get('core_desire')}",
        f"- 深层恐惧：{protagonist.get('deepest_fear')}",
        f"- 长期目标：{protagonist.get('long_term_goal')}",
        f"- 特殊能力：{protagonist.get('ability')}",
    ]
    derive = state.derive_context.get("PROTAGONIST_DERIVE") or {}
    reason = derive.get("reason")
    if reason:
        lines.extend(["", f"推荐理由：{reason}"])
    return "\n".join(lines)


def build_world_review(state: SessionState) -> str:
    project = ensure_new_project(state)
    world = project.get("world") or project.get("world_raw") or {}
    lines = [
        "请确认以下世界观设定：",
        f"- 背景设定：{world.get('setting_type')}",
        f"- 社会结构：{world.get('society_structure')}",
        f"- 主要场景：{', '.join(world.get('main_scene') or [])}",
        f"- 冒险区域：{', '.join(world.get('adventure_zone') or [])}",
        f"- 主要危机：{', '.join(world.get('main_crisis') or [])}",
        f"- 场景层级：{world.get('scene_layers') or '无'}",
    ]
    derive = state.derive_context.get("WORLD_DERIVE") or {}
    reason = derive.get("reason")
    if reason:
        lines.extend(["", f"推荐理由：{reason}"])
    return "\n".join(lines)


def build_power_review(state: SessionState) -> str:
    project = ensure_new_project(state)
    power = project.get("power_system") or project.get("power_raw") or {}
    lines = [
        "请确认以下力量体系：",
        f"- 主要修炼体系：{power.get('main_system')}",
        f"- 境界划分：{power.get('levels')}",
        f"- 突破条件：{power.get('breakthrough_condition')}",
        f"- 力量限制：{power.get('limitation')}",
        f"- 修炼体系特点：{power.get('unique_trait')}",
        f"- 资源/货币体系：{power.get('resource_economy')}",
    ]
    reason = (state.derive_context.get("POWER_DERIVE") or {}).get("reason")
    if reason:
        lines.extend(["", f"推荐理由：{reason}"])
    return "\n".join(lines)


def build_factions_review(state: SessionState) -> str:
    project = ensure_new_project(state)
    factions = project.get("factions") or project.get("factions_raw") or {}
    lines = [
        "请确认以下势力设定：",
        f"- 主角势力：{factions.get('player_faction')}",
        f"- 反派势力：{factions.get('enemy_faction')}",
        f"- 中立势力：{factions.get('neutral_faction')}",
    ]
    reason = (state.derive_context.get("FACTIONS_DERIVE") or {}).get("reason")
    if reason:
        lines.extend(["", f"推荐理由：{reason}"])
    return "\n".join(lines)


def build_characters_review(state: SessionState) -> str:
    project = ensure_new_project(state)
    chars = project.get("characters") or project.get("characters_raw") or {}
    lines = [
        "请确认以下角色关系：",
        f"- 感情线：{chars.get('romance_type')}",
        f"- 主要关系类型：{', '.join(chars.get('key_relationship_types') or [])}",
        f"- 核心对立面：{chars.get('main_antagonist_type')}",
        f"- 反派强度曲线：{chars.get('antagonist_curve')}",
        f"- 冲突层级：{', '.join(chars.get('conflict_levels') or [])}",
        f"- 主要势力组合：{chars.get('main_factions')}",
        f"- 关系张力来源：{', '.join(chars.get('relationship_tension') or [])}",
    ]
    reason = (state.derive_context.get("CHARACTERS_DERIVE") or {}).get("reason")
    if reason:
        lines.extend(["", f"推荐理由：{reason}"])
    return "\n".join(lines)


def build_volume_review(state: SessionState) -> str:
    project = ensure_new_project(state)
    raw = project.get("volume_raw") or {}
    arch = project.get("volume_architecture") or {}
    batch = project.get("batch_plan") or {}
    lines = [
        "请确认以下卷章架构：",
        f"- 卷数：{arch.get('volume_count')}",
        f"- 每卷章节数：{arch.get('chapters_per_volume')}",
        f"- 全书抬升路径：{arch.get('book_escalation_path')}",
        f"- 每卷交付承诺：{arch.get('delivery_matrix')}",
        f"- 每批章节数：{batch.get('batch_size')}章",
        f"- 首卷目标：{batch.get('first_volume_goal')}",
        f"- 首卷钩子：{batch.get('first_volume_hook')}",
        f"- 开局链：{batch.get('first_batch_opening_mode') or raw.get('first_batch_opening_mode')}",
    ]
    reason = (state.derive_context.get("VOLUME_DERIVE") or {}).get("reason")
    if reason:
        lines.extend(["", f"推荐理由：{reason}"])
    return "\n".join(lines)


def build_naming_review(state: SessionState) -> str:
    project = ensure_new_project(state)
    naming = project.get("naming") or project.get("naming_raw") or {}
    candidates = ((state.derive_context.get("NAMING_DERIVE") or {}).get("candidates") or {}).get("book_title_candidates", [])
    lines = [
        "请确认以下命名结果：",
        f"- 选定书名：{naming.get('selected_book_title')}",
        f"- 候选书名：{', '.join(candidates)}",
    ]
    reason = (state.derive_context.get("NAMING_DERIVE") or {}).get("reason")
    if reason:
        lines.extend(["", f"推荐理由：{reason}"])
    return "\n".join(lines)


def build_project_summary(state: SessionState) -> str:
    project = ensure_new_project(state)
    specs = project.get("basic_specs") or {}
    positioning = project.get("positioning") or {}
    protagonist = project.get("protagonist") or {}
    power = project.get("power_system") or {}
    world = project.get("world") or {}
    factions = project.get("factions") or {}
    characters = project.get("characters") or {}
    arch = project.get("volume_architecture") or {}
    batch = project.get("batch_plan") or {}
    naming = project.get("naming") or {}
    lines = [
        f"项目名称：{project.get('project_name')}",
        f"目标字数：{specs.get('target_word_count')}",
        f"单章字数：{specs.get('chapter_length')}",
        f"题材：{', '.join(specs.get('main_genres') or [])}",
        f"补充元素：{', '.join(specs.get('sub_genres') or []) or '无'}",
        f"叙事方式：{positioning.get('narrative_style')}",
        f"主冲突：{', '.join(positioning.get('main_conflicts') or [])}",
        f"核心追读动力：{', '.join(positioning.get('reader_hooks') or [])}",
        f"主承诺：{positioning.get('core_promise')}",
        f"卖点：{positioning.get('selling_point')}",
        f"主角：{protagonist.get('name')} / {protagonist.get('gender')} / {protagonist.get('starting_identity')}",
        f"主角目标：{protagonist.get('long_term_goal')}",
    ]
    if power:
        lines.extend([
            f"力量体系：{power.get('main_system')}",
            f"境界划分：{power.get('levels')}",
        ])
    lines.extend([
        f"世界观：{world.get('setting_type')} / {world.get('society_structure')}",
        f"主要场景：{', '.join(world.get('main_scene') or [])}",
        f"主要危机：{', '.join(world.get('main_crisis') or [])}",
        f"主角势力：{factions.get('player_faction')}",
        f"反派势力：{factions.get('enemy_faction')}",
        f"关系类型：{', '.join(characters.get('key_relationship_types') or [])}",
        f"核心对立面：{characters.get('main_antagonist_type')}",
        f"卷数：{arch.get('volume_count')} 卷，每卷约 {arch.get('chapters_per_volume')} 章",
        f"全书抬升路径：{arch.get('book_escalation_path')}",
        f"每批章节数：{batch.get('batch_size')} 章",
        f"首卷目标：{batch.get('first_volume_goal')}",
        f"首卷钩子：{batch.get('first_volume_hook')}",
        f"书名：{naming.get('selected_book_title')}",
    ])
    return "\n".join(lines)


def build_materialized_project_state(state: SessionState) -> dict[str, Any]:
    project = ensure_new_project(state)
    result = {
        "_created_at": state.created_at,
        "_project_name": project.get("project_name"),
        "_current_node": "preproduction_done",
        "basic_specs": project.get("basic_specs"),
        "positioning": project.get("positioning"),
        "protagonist": project.get("protagonist"),
        "world": project.get("world"),
        "factions": project.get("factions"),
        "characters": project.get("characters"),
        "volume_architecture": project.get("volume_architecture"),
        "batch_plan": project.get("batch_plan"),
        "naming": project.get("naming"),
    }
    if project.get("power_system"):
        result["power_system"] = project.get("power_system")
    return result


def materialize_project(state: SessionState) -> Path:
    project = ensure_new_project(state)
    existing = project.get("materialized_project_dir")
    if existing:
        return Path(existing)
    workspace = Path(state.workspace)
    project_name = project.get("project_name") or generated_project_name()
    project_dir = workspace / project_name
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "reference").mkdir(exist_ok=True)
    (project_dir / "chapters").mkdir(exist_ok=True)
    save_project_state(project_dir, build_materialized_project_state(state))
    project["materialized_project_dir"] = str(project_dir)
    save_session(state)
    return project_dir


def protagonist_pick_question(state: SessionState, node: str) -> dict[str, Any]:
    derive = state.derive_context.get("PROTAGONIST_DERIVE") or {}
    candidates = derive.get("candidates") or {}
    recommended = derive.get("recommended") or {}
    for field, field_node, label, candidate_key in PROTAGONIST_FIELD_SPECS:
        if field_node != node:
            continue
        options = [{"label": value, "description": ("推荐项" if value == recommended.get(field) else "候选项")} for value in candidates.get(candidate_key, [])]
        text = f"请选择{label}。"
        if recommended.get(field):
            text += f" 推荐：{recommended.get(field)}"
        return {
            "header": label,
            "text": text,
            "options": options,
            "multiple": False,
            "input_mode": "choice",
        }
    raise KeyError(node)


def generic_pick_question(state: SessionState, node: str, derive_node: str, field_specs: list[tuple]) -> dict[str, Any]:
    derive = state.derive_context.get(derive_node) or {}
    candidates = derive.get("candidates") or {}
    recommended = derive.get("recommended") or {}
    for field, field_node, label, candidate_key, multiple, min_select, max_select in field_specs:
        if field_node != node:
            continue
        recommended_values = recommended.get(field)
        if multiple and not isinstance(recommended_values, list):
            recommended_values = []
        if not multiple and isinstance(recommended_values, list):
            recommended_values = recommended_values[:1]
        rec_set = set(recommended_values if isinstance(recommended_values, list) else [recommended_values])
        options = [{"label": value, "description": ("推荐项" if value in rec_set else "候选项")} for value in candidates.get(candidate_key, [])]
        text = f"请选择{label}。"
        if multiple and rec_set:
            text += f" 推荐：{', '.join([v for v in candidates.get(candidate_key, []) if v in rec_set])}"
        elif not multiple and recommended.get(field):
            text += f" 推荐：{recommended.get(field)}"
        return {"header": label, "text": text, "options": options, "multiple": multiple, "input_mode": "choice", "min_select": min_select, "max_select": max_select}
    raise KeyError(node)


def world_pick_question(state: SessionState, node: str) -> dict[str, Any]:
    return generic_pick_question(state, node, "WORLD_DERIVE", WORLD_FIELD_SPECS)


def protagonist_next_node(current_node: str) -> str:
    nodes = [node for _field, node, _label, _candidate_key in PROTAGONIST_FIELD_SPECS]
    index = nodes.index(current_node)
    if index + 1 < len(nodes):
        return nodes[index + 1]
    return "PROTAGONIST_REVIEW"


def world_next_node(current_node: str) -> str:
    nodes = [node for _field, node, _label, _candidate_key, _multiple, _min_select, _max_select in WORLD_FIELD_SPECS]
    index = nodes.index(current_node)
    if index + 1 < len(nodes):
        return nodes[index + 1]
    return "WORLD_REVIEW"


def generic_next_node(current_node: str, field_specs: list[tuple], review_node: str) -> str:
    nodes = [node for _field, node, _label, _candidate_key, _multiple, _min_select, _max_select in field_specs]
    index = nodes.index(current_node)
    if index + 1 < len(nodes):
        return nodes[index + 1]
    return review_node


def protagonist_field_for_node(node: str) -> tuple[str, str]:
    for field, field_node, _label, candidate_key in PROTAGONIST_FIELD_SPECS:
        if field_node == node:
            return field, candidate_key
    raise KeyError(node)


def world_field_for_node(node: str) -> tuple[str, str, bool, int, int]:
    for field, field_node, _label, candidate_key, multiple, min_select, max_select in WORLD_FIELD_SPECS:
        if field_node == node:
            return field, candidate_key, multiple, min_select, max_select
    raise KeyError(node)


def generic_field_for_node(node: str, field_specs: list[tuple]) -> tuple[str, str, bool, int, int]:
    for field, field_node, _label, candidate_key, multiple, min_select, max_select in field_specs:
        if field_node == node:
            return field, candidate_key, multiple, min_select, max_select
    raise KeyError(node)


def validate_protagonist_derive_payload(payload: dict[str, Any]) -> tuple[bool, str]:
    recommended = payload.get("recommended")
    candidates = payload.get("candidates")
    reason = payload.get("reason")
    if not isinstance(recommended, dict):
        return False, "推导结果缺少 recommended 对象。"
    if not isinstance(candidates, dict):
        return False, "推导结果缺少 candidates 对象。"
    if not isinstance(reason, str) or not reason.strip():
        return False, "推导结果缺少非空的 reason。"
    for field, _node, _label, candidate_key in PROTAGONIST_FIELD_SPECS:
        rec_value = recommended.get(field)
        cand_values = candidates.get(candidate_key)
        if not isinstance(rec_value, str) or not normalize_answer(rec_value):
            return False, f"recommended.{field} 缺失或为空。"
        if not isinstance(cand_values, list) or not cand_values:
            return False, f"candidates.{candidate_key} 缺失或为空。"
        normalized_candidates = [normalize_answer(str(item)) for item in cand_values if normalize_answer(str(item))]
        if len(normalized_candidates) > 3:
            return False, f"candidates.{candidate_key} 超过 3 个候选。"
        if normalize_answer(rec_value) not in normalized_candidates:
            return False, f"recommended.{field} 不在 {candidate_key} 中。"
        payload["recommended"][field] = normalize_answer(rec_value)
        payload["candidates"][candidate_key] = normalized_candidates
    payload["reason"] = reason.strip()
    return True, ""


def validate_world_derive_payload(payload: dict[str, Any]) -> tuple[bool, str]:
    return validate_generic_derive_payload(payload, WORLD_FIELD_SPECS)


def validate_generic_derive_payload(payload: dict[str, Any], field_specs: list[tuple]) -> tuple[bool, str]:
    recommended = payload.get("recommended")
    candidates = payload.get("candidates")
    reason = payload.get("reason")
    if not isinstance(recommended, dict):
        return False, "推导结果缺少 recommended 对象。"
    if not isinstance(candidates, dict):
        return False, "推导结果缺少 candidates 对象。"
    if not isinstance(reason, str) or not reason.strip():
        return False, "推导结果缺少非空的 reason。"
    for field, _node, _label, candidate_key, multiple, min_select, max_select in field_specs:
        rec_value = recommended.get(field)
        cand_values = candidates.get(candidate_key)
        if not isinstance(cand_values, list) or not cand_values:
            return False, f"candidates.{candidate_key} 缺失或为空。"
        normalized_candidates = [normalize_answer(str(item)) for item in cand_values if normalize_answer(str(item))]
        if len(normalized_candidates) > 3:
            return False, f"candidates.{candidate_key} 超过 3 个候选。"
        if multiple:
            if isinstance(rec_value, str):
                normalized_rec = parse_multi_answer_text(normalize_answer(rec_value), normalized_candidates)
            elif isinstance(rec_value, list):
                normalized_rec = [normalize_answer(str(item)) for item in rec_value if normalize_answer(str(item))]
            else:
                return False, f"recommended.{field} 缺失或格式错误。"
            normalized_rec = list(dict.fromkeys(normalized_rec))
            if not normalized_rec or len(normalized_rec) < min_select or len(normalized_rec) > max_select:
                return False, f"recommended.{field} 数量不合法。"
            if any(item not in normalized_candidates for item in normalized_rec):
                return False, f"recommended.{field} 不在 {candidate_key} 中。"
            payload["recommended"][field] = normalized_rec
        else:
            if not isinstance(rec_value, str) or not normalize_answer(rec_value):
                return False, f"recommended.{field} 缺失或为空。"
            normalized_single = normalize_answer(rec_value)
            if normalized_single not in normalized_candidates:
                return False, f"recommended.{field} 不在 {candidate_key} 中。"
            payload["recommended"][field] = normalized_single
        payload["candidates"][candidate_key] = normalized_candidates
    payload["reason"] = reason.strip()
    return True, ""


def build_protagonist_from_values(values: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": values.get("name") or "",
        "gender": values.get("gender") or "",
        "age_group": values.get("age_group") or "",
        "starting_identity": values.get("starting_identity") or "",
        "starting_level": values.get("starting_level") or "",
        "personality": values.get("personality") or "",
        "core_desire": values.get("core_desire") or "",
        "deepest_fear": values.get("deepest_fear") or "",
        "long_term_goal": values.get("long_term_goal") or "",
        "ability": values.get("ability") or "",
    }


def build_world_from_values(values: dict[str, Any]) -> dict[str, Any]:
    return build_world(
        values.get("setting_type") or "",
        values.get("society_structure") or "",
        values.get("main_scene") or [],
        values.get("adventure_zone") or [],
        values.get("main_crisis") or [],
        values.get("scene_layers") or None,
    )


def build_power_from_values(values: dict[str, Any]) -> dict[str, Any]:
    return build_power_system(values.get("main_system") or "", values.get("levels") or "", values.get("breakthrough_condition") or "", values.get("limitation") or "", values.get("unique_trait") or "", values.get("resource_economy") or "")


def build_factions_from_values(values: dict[str, Any]) -> dict[str, Any]:
    return build_factions(values.get("player_faction") or "", values.get("enemy_faction") or "", values.get("neutral_faction") or "")


def build_characters_from_values(values: dict[str, Any]) -> dict[str, Any]:
    return build_characters(values.get("romance_type") or "", values.get("key_relationship_types") or [], values.get("main_antagonist_type") or "", values.get("antagonist_curve") or "", values.get("conflict_levels") or [], values.get("main_factions") or "", values.get("relationship_tension") or [])


def build_volume_from_values(state: SessionState, values: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    specs = (ensure_new_project(state).get("basic_specs") or {})
    batch_size_label = values.get("batch_size_label") or "10章"
    batch_size = int(str(batch_size_label).rstrip("章"))
    arch = build_volume_architecture(specs.get("target_volumes_numeric") or 0, specs.get("chapters_per_volume") or 0, values.get("book_escalation_path") or "", values.get("delivery_matrix") or "")
    batch = build_batch_plan(batch_size, values.get("first_volume_goal") or "", values.get("first_volume_hook") or "", values.get("first_batch_opening_mode") or "")
    return arch, batch


def build_naming_from_values(derive_context: dict[str, Any], values: dict[str, Any]) -> dict[str, Any]:
    candidates = (derive_context.get("candidates") or {}).get("book_title_candidates", [])
    return build_naming(values.get("selected_book_title") or "", candidates)


def handle_init_answer(state: SessionState, answer: str) -> dict[str, Any]:
    labels = {option["label"] for option in INIT_OPTIONS}
    if answer not in labels:
        return invalid_answer(state, "INIT", "无效分支选择，重试一次后将安全退出。")

    state.retry_count["INIT"] = 0
    state.history.append({"node": "INIT", "answer": answer})

    if answer == "退出":
        return done_payload(state, "已结束 dream 工作流。")
    if answer == "继续已有项目":
        workspace = Path(state.workspace)
        if not candidate_project_dirs(workspace):
            return ask_node(state, "INIT", message="未发现可继续的项目，请重新选择分支。")
        return ask_node(state, "RESUME_PICK")
    if answer == "新建项目":
        state.new_project = empty_new_project_state()
        state.new_project["project_name"] = generated_project_name()
        state.history.append({"node": "NEW_PROJECT_NAME", "answer": state.new_project["project_name"], "result": "auto_generated"})
        return ask_node(state, "BASIC_SPECS_WORD_TARGET", message=f"已自动生成项目名：`{state.new_project['project_name']}`")
    return report_payload(
        state,
        "PLAN_ONLY",
        "第一阶段仅接管新建项目基础信息与顶层路由。仅规划详细流程尚未迁入 orchestrator。",
    )


def handle_resume_pick_answer(state: SessionState, answer: str) -> dict[str, Any]:
    workspace = Path(state.workspace)
    candidates = candidate_project_dirs(workspace)
    mapping = {candidate.name: candidate for candidate in candidates}
    if answer not in mapping:
        return invalid_answer(state, "RESUME_PICK", "无效项目选择，重试一次后将安全退出。")

    state.retry_count["RESUME_PICK"] = 0
    state.selected_project = str(mapping[answer])
    state.history.append({"node": "RESUME_PICK", "answer": answer})
    return ask_node(state, "ACTION_MENU")


def handle_word_target_answer(state: SessionState, answer: str) -> dict[str, Any]:
    if not isinstance(answer, str) or not answer:
        return invalid_answer(state, "BASIC_SPECS_WORD_TARGET", "目标字数不能为空，重试一次后将安全退出。")
    normalized = answer if answer in WORD_TARGET_OPTIONS else parse_custom_word_target(answer)
    if not normalized:
        return invalid_answer(state, "BASIC_SPECS_WORD_TARGET", "目标字数格式无效，示例：40万字。")
    project = ensure_new_project(state)
    project["basic_specs_raw"]["target_word_count"] = normalized
    state.retry_count["BASIC_SPECS_WORD_TARGET"] = 0
    state.history.append({"node": "BASIC_SPECS_WORD_TARGET", "answer": normalized})
    return ask_node(state, "BASIC_SPECS_CHAPTER_LENGTH")


def handle_chapter_length_answer(state: SessionState, answer: str) -> dict[str, Any]:
    if not isinstance(answer, str) or not answer:
        return invalid_answer(state, "BASIC_SPECS_CHAPTER_LENGTH", "单章字数不能为空，重试一次后将安全退出。")
    normalized = answer if answer in CHAPTER_LENGTH_OPTIONS else parse_custom_chapter_length(answer)
    if not normalized:
        return invalid_answer(state, "BASIC_SPECS_CHAPTER_LENGTH", "单章字数格式无效，示例：2500-3500字。")
    project = ensure_new_project(state)
    project["basic_specs_raw"]["chapter_length"] = normalized
    state.retry_count["BASIC_SPECS_CHAPTER_LENGTH"] = 0
    state.history.append({"node": "BASIC_SPECS_CHAPTER_LENGTH", "answer": normalized})
    return ask_node(state, "BASIC_SPECS_PACING")


def handle_choice_answer(state: SessionState, node: str, answer: str, options: list[str], target_key: str, next_node: str) -> dict[str, Any]:
    if answer not in options:
        return invalid_answer(state, node, "无效选项，重试一次后将安全退出。")
    project = ensure_new_project(state)
    project["basic_specs_raw"][target_key] = answer
    state.retry_count[node] = 0
    state.history.append({"node": node, "answer": answer})
    return ask_node(state, next_node)


def validate_multi_answer(answer: Any, allowed: list[str], min_select: int, max_select: int) -> list[str] | None:
    if isinstance(answer, str):
        text = normalize_answer(answer)
        if not text:
            values = []
        elif text in allowed:
            values = [text]
        else:
            values = parse_multi_answer_text(text, allowed)
    elif isinstance(answer, list):
        values = [str(item) for item in answer if str(item)]
    else:
        return None
    values = [normalize_answer(value) for value in values if normalize_answer(value)]
    if len(values) < min_select or len(values) > max_select:
        return None
    if any(value not in allowed for value in values):
        return None
    return list(dict.fromkeys(values))


def parse_multi_answer_text(text: str, allowed: list[str]) -> list[str]:
    if not text:
        return []
    matched: list[str] = []
    for option in allowed:
        if option in text:
            matched.append(option)
    if matched:
        return list(dict.fromkeys(matched))
    parts = [part.strip() for part in re.split(r"[,，|/;；]+", text) if part.strip()]
    normalized_parts = [normalize_answer(part) for part in parts if normalize_answer(part)]
    return [part for part in normalized_parts if part in allowed]


def handle_main_genres_answer(state: SessionState, answer: Any) -> dict[str, Any]:
    values = validate_multi_answer(answer, MAIN_GENRE_OPTIONS, 1, 3)
    if not values:
        return invalid_answer(state, "BASIC_SPECS_MAIN_GENRES", "主题材必须选择 1-3 个有效选项。")
    project = ensure_new_project(state)
    project["basic_specs_raw"]["main_genres"] = values
    state.retry_count["BASIC_SPECS_MAIN_GENRES"] = 0
    state.history.append({"node": "BASIC_SPECS_MAIN_GENRES", "answer": values})
    return ask_node(state, "BASIC_SPECS_SUB_GENRES")


def handle_sub_genres_answer(state: SessionState, answer: Any) -> dict[str, Any]:
    if answer in ("", []):
        values: list[str] = []
    else:
        values = validate_multi_answer(answer, SUB_GENRE_OPTIONS, 0, len(SUB_GENRE_OPTIONS)) or []
        if answer not in ("", []) and not values:
            return invalid_answer(state, "BASIC_SPECS_SUB_GENRES", "补充元素必须是有效选项，可为空或多选。")
    project = ensure_new_project(state)
    raw = project["basic_specs_raw"]
    raw["sub_genres"] = values
    project["basic_specs"] = build_basic_specs(
        raw["target_word_count"],
        raw["chapter_length"],
        raw["pacing"],
        raw["style_tone"],
        raw["main_genres"],
        raw["sub_genres"],
    )
    state.retry_count["BASIC_SPECS_SUB_GENRES"] = 0
    state.history.append({"node": "BASIC_SPECS_SUB_GENRES", "answer": values})
    return ask_node(state, "BASIC_SPECS_REVIEW")


def handle_basic_specs_review_answer(state: SessionState, answer: str) -> dict[str, Any]:
    labels = {option["label"] for option in NEW_PROJECT_REVIEW_OPTIONS}
    if answer not in labels:
        return invalid_answer(state, "BASIC_SPECS_REVIEW", "无效复核动作，重试一次后将安全退出。")
    state.retry_count["BASIC_SPECS_REVIEW"] = 0
    state.history.append({"node": "BASIC_SPECS_REVIEW", "answer": answer})
    if answer == "退出":
        return done_payload(state, "已结束当前流程。")
    if answer == "重新填写基础信息":
        project = ensure_new_project(state)
        project["basic_specs_raw"] = empty_new_project_state()["basic_specs_raw"]
        project["basic_specs"] = None
        return ask_node(state, "BASIC_SPECS_WORD_TARGET")
    project = ensure_new_project(state)
    project["stage"] = "basic_specs_locked"
    return ask_node(state, "POSITIONING_NARRATIVE_STYLE", message="基础信息已锁定，进入第二阶段：项目定位。")


def handle_positioning_narrative_answer(state: SessionState, answer: str) -> dict[str, Any]:
    if answer not in NARRATIVE_STYLE_OPTIONS:
        return invalid_answer(state, "POSITIONING_NARRATIVE_STYLE", "叙事方式无效，重试一次后将安全退出。")
    project = ensure_new_project(state)
    project["positioning_raw"]["narrative_style"] = answer
    state.retry_count["POSITIONING_NARRATIVE_STYLE"] = 0
    state.history.append({"node": "POSITIONING_NARRATIVE_STYLE", "answer": answer})
    return ask_node(state, "POSITIONING_MAIN_CONFLICTS")


def handle_positioning_main_conflicts_answer(state: SessionState, answer: Any) -> dict[str, Any]:
    options = positioning_conflict_options(state)
    values = validate_multi_answer(answer, options, 2, 3)
    if not values:
        return invalid_answer(state, "POSITIONING_MAIN_CONFLICTS", "主冲突必须选择 2-3 个有效选项。")
    project = ensure_new_project(state)
    project["positioning_raw"]["main_conflicts"] = values
    state.retry_count["POSITIONING_MAIN_CONFLICTS"] = 0
    state.history.append({"node": "POSITIONING_MAIN_CONFLICTS", "answer": values})
    return ask_node(state, "POSITIONING_READER_HOOKS")


def handle_positioning_reader_hooks_answer(state: SessionState, answer: Any) -> dict[str, Any]:
    options = positioning_hook_options(state)
    values = validate_multi_answer(answer, options, 2, 3)
    if not values:
        return invalid_answer(state, "POSITIONING_READER_HOOKS", "核心追读动力必须选择 2-3 个有效选项。")
    project = ensure_new_project(state)
    raw = project["positioning_raw"]
    raw["reader_hooks"] = values
    specs = project.get("basic_specs") or {}
    defaults = default_positioning_values(specs.get("main_genres", []), specs.get("style_tone", "热血燃向"))
    project["positioning"] = build_positioning(
        raw["narrative_style"],
        raw["main_conflicts"],
        raw["reader_hooks"],
        defaults["core_promise"],
        defaults["selling_point"],
    )
    state.retry_count["POSITIONING_READER_HOOKS"] = 0
    state.history.append({"node": "POSITIONING_READER_HOOKS", "answer": values})
    return ask_node(state, "POSITIONING_REVIEW")


def handle_positioning_review_answer(state: SessionState, answer: str) -> dict[str, Any]:
    labels = {option["label"] for option in POSITIONING_REVIEW_OPTIONS}
    if answer not in labels:
        return invalid_answer(state, "POSITIONING_REVIEW", "无效复核动作，重试一次后将安全退出。")
    state.retry_count["POSITIONING_REVIEW"] = 0
    state.history.append({"node": "POSITIONING_REVIEW", "answer": answer})
    if answer == "退出":
        return done_payload(state, "已结束当前流程。")
    if answer == "重新填写项目定位":
        project = ensure_new_project(state)
        project["positioning_raw"] = empty_new_project_state()["positioning_raw"]
        project["positioning"] = None
        return ask_node(state, "POSITIONING_NARRATIVE_STYLE")
    project = ensure_new_project(state)
    project["stage"] = "positioning_locked"
    if state.lock_mode:
        return continue_after_lock_mode(state)
    return ask_node(state, "LOCK_MODE_SELECT", message="项目定位已锁定，请选择后续锁定模式。")


def handle_lock_mode_select_answer(state: SessionState, answer: str) -> dict[str, Any]:
    if state.lock_mode:
        if answer != lock_mode_label(state.lock_mode):
            return error_payload(state, "LOCK_MODE_SELECT", f"锁定模式已设置为{lock_mode_label(state.lock_mode)}，不能重复改写。")
        state.retry_count["LOCK_MODE_SELECT"] = 0
        state.history.append({"node": "LOCK_MODE_SELECT", "answer": answer, "result": "reuse_locked_mode"})
        return continue_after_lock_mode(state)
    labels = {option["label"] for option in LOCK_MODE_OPTIONS}
    if answer not in labels:
        return invalid_answer(state, "LOCK_MODE_SELECT", "无效锁定模式，重试一次后将安全退出。")
    state.retry_count["LOCK_MODE_SELECT"] = 0
    state.history.append({"node": "LOCK_MODE_SELECT", "answer": answer})
    state.lock_mode = "user_locked" if answer == "用户锁定" else "model_recommended"
    return continue_after_lock_mode(state, message="开始推导第三阶段：主角设定候选。")


def handle_protagonist_pick_answer(state: SessionState, node: str, answer: str) -> dict[str, Any]:
    if not isinstance(answer, str) or not answer:
        return invalid_answer(state, node, "无效选择，重试一次后将安全退出。")
    field, candidate_key = protagonist_field_for_node(node)
    derive = state.derive_context.get("PROTAGONIST_DERIVE") or {}
    allowed = (derive.get("candidates") or {}).get(candidate_key, [])
    normalized = normalize_answer(answer)
    if normalized not in allowed:
        return invalid_answer(state, node, "选择不在候选范围内，重试一次后将安全退出。")
    project = ensure_new_project(state)
    project["protagonist_raw"][field] = normalized
    state.retry_count[node] = 0
    state.history.append({"node": node, "answer": normalized})
    next_node = protagonist_next_node(node)
    if next_node == "PROTAGONIST_REVIEW":
        project["protagonist"] = build_protagonist_from_values(project["protagonist_raw"])
    return ask_node(state, next_node)


def handle_protagonist_review_answer(state: SessionState, answer: str) -> dict[str, Any]:
    labels = {option["label"] for option in PROTAGONIST_REVIEW_OPTIONS}
    if answer not in labels:
        return invalid_answer(state, "PROTAGONIST_REVIEW", "无效复核动作，重试一次后将安全退出。")
    state.retry_count["PROTAGONIST_REVIEW"] = 0
    state.history.append({"node": "PROTAGONIST_REVIEW", "answer": answer})
    if answer == "退出":
        return done_payload(state, "已结束当前流程。")
    if answer == "重新选择主角设定":
        project = ensure_new_project(state)
        project["protagonist_raw"] = empty_new_project_state()["protagonist_raw"]
        project["protagonist"] = None
        return ask_node(state, PROTAGONIST_FIELD_SPECS[0][1])
    project = ensure_new_project(state)
    project["stage"] = "protagonist_locked"
    return continue_after_protagonist(state, message="主角设定已锁定，开始推导下一阶段候选。")


def handle_world_pick_answer(state: SessionState, node: str, answer: Any) -> dict[str, Any]:
    field, candidate_key, multiple, min_select, max_select = world_field_for_node(node)
    derive = state.derive_context.get("WORLD_DERIVE") or {}
    allowed = (derive.get("candidates") or {}).get(candidate_key, [])
    if multiple:
        values = validate_multi_answer(answer, allowed, min_select, max_select)
        if not values:
            return invalid_answer(state, node, "选择不在候选范围内，或数量不合法。")
        stored_value: Any = values
    else:
        if not isinstance(answer, str) or normalize_answer(answer) not in allowed:
            return invalid_answer(state, node, "选择不在候选范围内，重试一次后将安全退出。")
        stored_value = normalize_answer(answer)
    project = ensure_new_project(state)
    project["world_raw"][field] = stored_value
    state.retry_count[node] = 0
    state.history.append({"node": node, "answer": stored_value})
    next_node = world_next_node(node)
    if next_node == "WORLD_REVIEW":
        project["world"] = build_world_from_values(project["world_raw"])
    return ask_node(state, next_node)


def handle_world_review_answer(state: SessionState, answer: str) -> dict[str, Any]:
    labels = {option["label"] for option in WORLD_REVIEW_OPTIONS}
    if answer not in labels:
        return invalid_answer(state, "WORLD_REVIEW", "无效复核动作，重试一次后将安全退出。")
    state.retry_count["WORLD_REVIEW"] = 0
    state.history.append({"node": "WORLD_REVIEW", "answer": answer})
    if answer == "退出":
        return done_payload(state, "已结束当前流程。")
    if answer == "重新选择世界观设定":
        project = ensure_new_project(state)
        project["world_raw"] = empty_new_project_state()["world_raw"]
        project["world"] = None
        return ask_node(state, WORLD_FIELD_SPECS[0][1])
    project = ensure_new_project(state)
    project["stage"] = "world_locked"
    return continue_to_factions(state, message="世界观设定已锁定，开始推导下一阶段：势力设定候选。")


def handle_generic_pick_answer(state: SessionState, node: str, answer: Any, derive_node: str, field_specs: list[tuple], raw_key: str, build_final, review_node: str):
    field, candidate_key, multiple, min_select, max_select = generic_field_for_node(node, field_specs)
    derive = state.derive_context.get(derive_node) or {}
    allowed = (derive.get("candidates") or {}).get(candidate_key, [])
    if multiple:
        values = validate_multi_answer(answer, allowed, min_select, max_select)
        if not values:
            return invalid_answer(state, node, "选择不在候选范围内，或数量不合法。")
        stored_value: Any = values
    else:
        if not isinstance(answer, str) or normalize_answer(answer) not in allowed:
            return invalid_answer(state, node, "选择不在候选范围内，重试一次后将安全退出。")
        stored_value = normalize_answer(answer)
    project = ensure_new_project(state)
    project[raw_key][field] = stored_value
    state.retry_count[node] = 0
    state.history.append({"node": node, "answer": stored_value})
    next_node = generic_next_node(node, field_specs, review_node)
    if next_node == review_node:
        build_final(state)
    return ask_node(state, next_node)


def finalize_power(state: SessionState) -> None:
    project = ensure_new_project(state)
    project["power_system"] = build_power_from_values(project["power_raw"])


def finalize_factions(state: SessionState) -> None:
    project = ensure_new_project(state)
    project["factions"] = build_factions_from_values(project["factions_raw"])


def finalize_characters(state: SessionState) -> None:
    project = ensure_new_project(state)
    project["characters"] = build_characters_from_values(project["characters_raw"])


def finalize_volume(state: SessionState) -> None:
    project = ensure_new_project(state)
    arch, batch = build_volume_from_values(state, project["volume_raw"])
    project["volume_architecture"] = arch
    project["batch_plan"] = batch


def finalize_naming(state: SessionState) -> None:
    project = ensure_new_project(state)
    project["naming"] = build_naming_from_values(state.derive_context.get("NAMING_DERIVE") or {}, project["naming_raw"])


def handle_power_review_answer(state: SessionState, answer: str) -> dict[str, Any]:
    labels = {option["label"] for option in POWER_REVIEW_OPTIONS}
    if answer not in labels:
        return invalid_answer(state, "POWER_REVIEW", "无效复核动作，重试一次后将安全退出。")
    state.retry_count["POWER_REVIEW"] = 0
    state.history.append({"node": "POWER_REVIEW", "answer": answer})
    if answer == "退出":
        return done_payload(state, "已结束当前流程。")
    if answer == "重新选择力量体系":
        project = ensure_new_project(state)
        project["power_raw"] = empty_new_project_state()["power_raw"]
        project["power_system"] = None
        return ask_node(state, POWER_FIELD_SPECS[0][1])
    ensure_new_project(state)["stage"] = "power_locked"
    return continue_to_world(state, message="力量体系已锁定，开始推导下一阶段：世界观设定候选。")


def handle_factions_review_answer(state: SessionState, answer: str) -> dict[str, Any]:
    labels = {option["label"] for option in FACTIONS_REVIEW_OPTIONS}
    if answer not in labels:
        return invalid_answer(state, "FACTIONS_REVIEW", "无效复核动作，重试一次后将安全退出。")
    state.retry_count["FACTIONS_REVIEW"] = 0
    state.history.append({"node": "FACTIONS_REVIEW", "answer": answer})
    if answer == "退出":
        return done_payload(state, "已结束当前流程。")
    if answer == "重新选择势力设定":
        project = ensure_new_project(state)
        project["factions_raw"] = empty_new_project_state()["factions_raw"]
        project["factions"] = None
        return ask_node(state, FACTIONS_FIELD_SPECS[0][1])
    ensure_new_project(state)["stage"] = "factions_locked"
    return continue_to_characters(state, message="势力设定已锁定，开始推导下一阶段：角色关系候选。")


def handle_characters_review_answer(state: SessionState, answer: str) -> dict[str, Any]:
    labels = {option["label"] for option in CHARACTERS_REVIEW_OPTIONS}
    if answer not in labels:
        return invalid_answer(state, "CHARACTERS_REVIEW", "无效复核动作，重试一次后将安全退出。")
    state.retry_count["CHARACTERS_REVIEW"] = 0
    state.history.append({"node": "CHARACTERS_REVIEW", "answer": answer})
    if answer == "退出":
        return done_payload(state, "已结束当前流程。")
    if answer == "重新选择角色关系":
        project = ensure_new_project(state)
        project["characters_raw"] = empty_new_project_state()["characters_raw"]
        project["characters"] = None
        return ask_node(state, CHARACTERS_FIELD_SPECS[0][1])
    ensure_new_project(state)["stage"] = "characters_locked"
    return continue_to_volume(state, message="角色关系已锁定，开始推导下一阶段：卷章架构候选。")


def handle_volume_review_answer(state: SessionState, answer: str) -> dict[str, Any]:
    labels = {option["label"] for option in VOLUME_REVIEW_OPTIONS}
    if answer not in labels:
        return invalid_answer(state, "VOLUME_REVIEW", "无效复核动作，重试一次后将安全退出。")
    state.retry_count["VOLUME_REVIEW"] = 0
    state.history.append({"node": "VOLUME_REVIEW", "answer": answer})
    if answer == "退出":
        return done_payload(state, "已结束当前流程。")
    if answer == "重新选择卷章架构":
        project = ensure_new_project(state)
        project["volume_raw"] = empty_new_project_state()["volume_raw"]
        project["volume_architecture"] = None
        project["batch_plan"] = None
        return ask_node(state, VOLUME_FIELD_SPECS[0][1])
    ensure_new_project(state)["stage"] = "volume_locked"
    return continue_to_naming(state, message="卷章架构已锁定，开始推导最后阶段：命名候选。")


def handle_naming_review_answer(state: SessionState, answer: str) -> dict[str, Any]:
    labels = {option["label"] for option in NAMING_REVIEW_OPTIONS}
    if answer not in labels:
        return invalid_answer(state, "NAMING_REVIEW", "无效复核动作，重试一次后将安全退出。")
    state.retry_count["NAMING_REVIEW"] = 0
    state.history.append({"node": "NAMING_REVIEW", "answer": answer})
    if answer == "退出":
        return done_payload(state, "已结束当前流程。")
    if answer == "重新选择书名":
        project = ensure_new_project(state)
        project["naming_raw"] = empty_new_project_state()["naming_raw"]
        project["naming"] = None
        return ask_node(state, NAMING_FIELD_SPECS[0][1])
    ensure_new_project(state)["stage"] = "naming_locked"
    return ask_node(state, "POST_SETUP_ACTION", message="全部前期设定已锁定完成。")


def handle_post_setup_action_answer(state: SessionState, answer: str) -> dict[str, Any]:
    labels = {option["label"] for option in POST_SETUP_ACTION_OPTIONS}
    if answer not in labels:
        return invalid_answer(state, "POST_SETUP_ACTION", "无效动作，重试一次后将安全退出。")
    state.retry_count["POST_SETUP_ACTION"] = 0
    state.history.append({"node": "POST_SETUP_ACTION", "answer": answer})
    if answer == "结束":
        return done_payload(state, "流程已结束。")
    if answer == "查看设定总览":
        return report_payload(state, "POST_SETUP_SUMMARY", build_project_summary(state))
    project_dir = materialize_project(state)
    return run_script_payload(
        state,
        "WRITING_ENTRY",
        [sys.executable, str(SCRIPT_DIR / "continuous_writer.py"), "run", str(project_dir)],
        f"已落盘项目状态到 {project_dir}，开始进入正文生成调度。",
    )


def handle_action_menu_answer(state: SessionState, answer: str) -> dict[str, Any]:
    project_dir = state.selected_project
    if not project_dir:
        return error_payload(state, "ACTION_MENU", "当前会话缺少已确认项目。")

    labels = {option["label"] for option in ACTION_OPTIONS}
    if answer not in labels:
        return invalid_answer(state, "ACTION_MENU", "无效动作选择，重试一次后将安全退出。")

    state.retry_count["ACTION_MENU"] = 0
    state.history.append({"node": "ACTION_MENU", "answer": answer})

    if answer == "结束":
        return done_payload(state, "已结束当前项目工作流。")
    if answer == "继续写作":
        return run_script_payload(
            state,
            "ACTION_MENU",
            [sys.executable, str(SCRIPT_DIR / "continuous_writer.py"), "resume", project_dir],
            "进入连续写作调度。",
        )
    if answer == "本批检查":
        return run_script_payload(
            state,
            "ACTION_MENU",
            [sys.executable, str(SCRIPT_DIR / "strict_interactive_runner.py"), "action-menu", project_dir],
            "读取当前项目动作菜单状态。",
        )
    if answer == "本卷收尾":
        return run_script_payload(
            state,
            "ACTION_MENU",
            [sys.executable, str(SCRIPT_DIR / "strict_interactive_runner.py"), "volume-ending-check", project_dir],
            "执行本卷收尾检查。",
        )
    return run_script_payload(
        state,
        "ACTION_MENU",
        [sys.executable, str(SCRIPT_DIR / "merge_export.py"), project_dir, "--format", "txt"],
        "导出当前项目文本。",
    )


def handle_final_menu_answer(state: SessionState, answer: str) -> dict[str, Any]:
    labels = {option["label"] for option in FINAL_OPTIONS}
    if answer not in labels:
        return invalid_answer(state, "FINAL_MENU", "无效后处理动作，重试一次后将安全退出。")
    state.retry_count["FINAL_MENU"] = 0
    state.history.append({"node": "FINAL_MENU", "answer": answer})
    if answer == "结束":
        return done_payload(state, "已结束后处理流程。")
    return report_payload(state, "FINAL_MENU", f"已记录后处理动作：{answer}。第一版暂未接入自动执行。")


def start(workspace: Path) -> dict[str, Any]:
    state = new_session(workspace)
    return ask_node(state, "INIT")


def answer(session_id: str, value: Any) -> dict[str, Any]:
    state = load_session(session_id)
    normalized = normalize_value(value)
    if isinstance(normalized, str) and normalized in STOP_WORDS:
        state.history.append({"node": state.current_node, "answer": normalized, "result": "stopped"})
        return done_payload(state, "用户已中止当前流程。")
    if state.current_node == "INIT":
        return handle_init_answer(state, normalized)
    if state.current_node == "RESUME_PICK":
        return handle_resume_pick_answer(state, normalized)
    if state.current_node == "BASIC_SPECS_WORD_TARGET":
        return handle_word_target_answer(state, normalized)
    if state.current_node == "BASIC_SPECS_CHAPTER_LENGTH":
        return handle_chapter_length_answer(state, normalized)
    if state.current_node == "BASIC_SPECS_PACING":
        return handle_choice_answer(state, "BASIC_SPECS_PACING", normalized, PACING_OPTIONS, "pacing", "BASIC_SPECS_STYLE_TONE")
    if state.current_node == "BASIC_SPECS_STYLE_TONE":
        return handle_choice_answer(state, "BASIC_SPECS_STYLE_TONE", normalized, STYLE_TONE_OPTIONS, "style_tone", "BASIC_SPECS_MAIN_GENRES")
    if state.current_node == "BASIC_SPECS_MAIN_GENRES":
        return handle_main_genres_answer(state, normalized)
    if state.current_node == "BASIC_SPECS_SUB_GENRES":
        return handle_sub_genres_answer(state, normalized)
    if state.current_node == "BASIC_SPECS_REVIEW":
        return handle_basic_specs_review_answer(state, normalized)
    if state.current_node == "POSITIONING_NARRATIVE_STYLE":
        return handle_positioning_narrative_answer(state, normalized)
    if state.current_node == "POSITIONING_MAIN_CONFLICTS":
        return handle_positioning_main_conflicts_answer(state, normalized)
    if state.current_node == "POSITIONING_READER_HOOKS":
        return handle_positioning_reader_hooks_answer(state, normalized)
    if state.current_node == "POSITIONING_REVIEW":
        return handle_positioning_review_answer(state, normalized)
    if state.current_node == "LOCK_MODE_SELECT":
        return handle_lock_mode_select_answer(state, normalized)
    protagonist_pick_nodes = {node for _field, node, _label, _candidate_key in PROTAGONIST_FIELD_SPECS}
    if state.current_node in protagonist_pick_nodes:
        return handle_protagonist_pick_answer(state, state.current_node, normalized)
    if state.current_node == "PROTAGONIST_REVIEW":
        return handle_protagonist_review_answer(state, normalized)
    world_pick_nodes = {node for _field, node, _label, _candidate_key, _multiple, _min_select, _max_select in WORLD_FIELD_SPECS}
    if state.current_node in world_pick_nodes:
        return handle_world_pick_answer(state, state.current_node, normalized)
    if state.current_node == "WORLD_REVIEW":
        return handle_world_review_answer(state, normalized)
    power_pick_nodes = {node for _field, node, _label, _candidate_key, _multiple, _min_select, _max_select in POWER_FIELD_SPECS}
    if state.current_node in power_pick_nodes:
        return handle_generic_pick_answer(state, state.current_node, normalized, "POWER_DERIVE", POWER_FIELD_SPECS, "power_raw", finalize_power, "POWER_REVIEW")
    if state.current_node == "POWER_REVIEW":
        return handle_power_review_answer(state, normalized)
    factions_pick_nodes = {node for _field, node, _label, _candidate_key, _multiple, _min_select, _max_select in FACTIONS_FIELD_SPECS}
    if state.current_node in factions_pick_nodes:
        return handle_generic_pick_answer(state, state.current_node, normalized, "FACTIONS_DERIVE", FACTIONS_FIELD_SPECS, "factions_raw", finalize_factions, "FACTIONS_REVIEW")
    if state.current_node == "FACTIONS_REVIEW":
        return handle_factions_review_answer(state, normalized)
    characters_pick_nodes = {node for _field, node, _label, _candidate_key, _multiple, _min_select, _max_select in CHARACTERS_FIELD_SPECS}
    if state.current_node in characters_pick_nodes:
        return handle_generic_pick_answer(state, state.current_node, normalized, "CHARACTERS_DERIVE", CHARACTERS_FIELD_SPECS, "characters_raw", finalize_characters, "CHARACTERS_REVIEW")
    if state.current_node == "CHARACTERS_REVIEW":
        return handle_characters_review_answer(state, normalized)
    volume_pick_nodes = {node for _field, node, _label, _candidate_key, _multiple, _min_select, _max_select in VOLUME_FIELD_SPECS}
    if state.current_node in volume_pick_nodes:
        return handle_generic_pick_answer(state, state.current_node, normalized, "VOLUME_DERIVE", VOLUME_FIELD_SPECS, "volume_raw", finalize_volume, "VOLUME_REVIEW")
    if state.current_node == "VOLUME_REVIEW":
        return handle_volume_review_answer(state, normalized)
    naming_pick_nodes = {node for _field, node, _label, _candidate_key, _multiple, _min_select, _max_select in NAMING_FIELD_SPECS}
    if state.current_node in naming_pick_nodes:
        return handle_generic_pick_answer(state, state.current_node, normalized, "NAMING_DERIVE", NAMING_FIELD_SPECS, "naming_raw", finalize_naming, "NAMING_REVIEW")
    if state.current_node == "NAMING_REVIEW":
        return handle_naming_review_answer(state, normalized)
    if state.current_node == "POST_SETUP_ACTION":
        return handle_post_setup_action_answer(state, normalized)
    if state.current_node == "ACTION_MENU":
        return handle_action_menu_answer(state, normalized)
    if state.current_node == "FINAL_MENU":
        return handle_final_menu_answer(state, normalized)
    return error_payload(state, state.current_node, "当前节点不接受用户回答，请先按 orchestrator 指令继续。")


def resume(session_id: str) -> dict[str, Any]:
    state = load_session(session_id)
    if state.current_node in QUESTION_DEFS:
        return ask_node(state, state.current_node)
    if state.current_node == "DONE":
        return done_payload(state, "流程已结束。")
    if state.current_node == "POST_SETUP_SUMMARY":
        return ask_node(state, "POST_SETUP_ACTION")
    return report_payload(state, state.current_node, "当前节点已进入脚本执行阶段，请按上一条 orchestrator 指令继续。")


def submit_derived(session_id: str, node: str, value: str) -> dict[str, Any]:
    state = load_session(session_id)
    if state.current_node != node:
        return error_payload(state, node, f"当前会话不在 {node} 节点。")
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return error_payload(state, node, "推导结果不是合法 JSON。")
    if node == "PROTAGONIST_DERIVE":
        ok, error_message = validate_protagonist_derive_payload(payload)
        retry_request = protagonist_derive_request(state)
    elif node == "WORLD_DERIVE":
        ok, error_message = validate_world_derive_payload(payload)
        retry_request = world_derive_request(state)
    elif node == "POWER_DERIVE":
        ok, error_message = validate_generic_derive_payload(payload, POWER_FIELD_SPECS)
        retry_request = power_derive_request(state)
    elif node == "FACTIONS_DERIVE":
        ok, error_message = validate_generic_derive_payload(payload, FACTIONS_FIELD_SPECS)
        retry_request = factions_derive_request(state)
    elif node == "CHARACTERS_DERIVE":
        ok, error_message = validate_generic_derive_payload(payload, CHARACTERS_FIELD_SPECS)
        retry_request = characters_derive_request(state)
    elif node == "VOLUME_DERIVE":
        ok, error_message = validate_generic_derive_payload(payload, VOLUME_FIELD_SPECS)
        retry_request = volume_derive_request(state)
    elif node == "NAMING_DERIVE":
        ok, error_message = validate_generic_derive_payload(payload, NAMING_FIELD_SPECS)
        retry_request = naming_derive_request(state)
    else:
        return error_payload(state, node, "当前节点暂不支持推导回传。")
    if not ok:
        retries = state.derive_retry_count.get(node, 0) + 1
        state.derive_retry_count[node] = retries
        if retries >= 2:
            return error_payload(state, node, error_message)
        return derive_payload(state, node, retry_request, message=f"推导结果校验失败：{error_message} 请按要求重新推导。")
    state.derive_retry_count[node] = 0
    state.derive_context[node] = payload
    state.history.append({"node": node, "result": "derived_submitted"})
    project = ensure_new_project(state)
    if node == "PROTAGONIST_DERIVE":
        if state.lock_mode == "model_recommended":
            project["protagonist_raw"] = payload["recommended"].copy()
            project["protagonist"] = build_protagonist_from_values(payload["recommended"])
            project["stage"] = "protagonist_locked"
            return continue_after_protagonist(state, message=f"已按模型推荐自动锁定主角设定。推荐理由：{payload['reason']}")
        project["protagonist_raw"] = empty_new_project_state()["protagonist_raw"]
        return ask_node(state, PROTAGONIST_FIELD_SPECS[0][1], message="主角设定候选已生成，请开始逐项锁定。")
    if node == "WORLD_DERIVE":
        if state.lock_mode == "model_recommended":
            project["world_raw"] = payload["recommended"].copy()
            project["world"] = build_world_from_values(payload["recommended"])
            project["stage"] = "world_locked"
            return continue_to_factions(state, message=f"已按模型推荐自动锁定世界观设定。推荐理由：{payload['reason']}")
        project["world_raw"] = empty_new_project_state()["world_raw"]
        return ask_node(state, WORLD_FIELD_SPECS[0][1], message="世界观设定候选已生成，请开始逐项锁定。")
    if node == "POWER_DERIVE":
        if state.lock_mode == "model_recommended":
            project["power_raw"] = payload["recommended"].copy()
            project["power_system"] = build_power_from_values(payload["recommended"])
            project["stage"] = "power_locked"
            return continue_to_world(state, message=f"已按模型推荐自动锁定力量体系。推荐理由：{payload['reason']}")
        project["power_raw"] = empty_new_project_state()["power_raw"]
        return ask_node(state, POWER_FIELD_SPECS[0][1], message="力量体系候选已生成，请开始逐项锁定。")
    if node == "FACTIONS_DERIVE":
        if state.lock_mode == "model_recommended":
            project["factions_raw"] = payload["recommended"].copy()
            project["factions"] = build_factions_from_values(payload["recommended"])
            project["stage"] = "factions_locked"
            return continue_to_characters(state, message=f"已按模型推荐自动锁定势力设定。推荐理由：{payload['reason']}")
        project["factions_raw"] = empty_new_project_state()["factions_raw"]
        return ask_node(state, FACTIONS_FIELD_SPECS[0][1], message="势力设定候选已生成，请开始逐项锁定。")
    if node == "CHARACTERS_DERIVE":
        if state.lock_mode == "model_recommended":
            project["characters_raw"] = payload["recommended"].copy()
            project["characters"] = build_characters_from_values(payload["recommended"])
            project["stage"] = "characters_locked"
            return continue_to_volume(state, message=f"已按模型推荐自动锁定角色关系。推荐理由：{payload['reason']}")
        project["characters_raw"] = empty_new_project_state()["characters_raw"]
        return ask_node(state, CHARACTERS_FIELD_SPECS[0][1], message="角色关系候选已生成，请开始逐项锁定。")
    if node == "VOLUME_DERIVE":
        if state.lock_mode == "model_recommended":
            project["volume_raw"] = payload["recommended"].copy()
            arch, batch = build_volume_from_values(state, payload["recommended"])
            project["volume_architecture"] = arch
            project["batch_plan"] = batch
            project["stage"] = "volume_locked"
            return continue_to_naming(state, message=f"已按模型推荐自动锁定卷章架构。推荐理由：{payload['reason']}")
        project["volume_raw"] = empty_new_project_state()["volume_raw"]
        return ask_node(state, VOLUME_FIELD_SPECS[0][1], message="卷章架构候选已生成，请开始逐项锁定。")
    if state.lock_mode == "model_recommended":
        project["naming_raw"] = payload["recommended"].copy()
        project["naming"] = build_naming_from_values(payload, payload["recommended"])
        project["stage"] = "naming_locked"
        return ask_node(state, "POST_SETUP_ACTION", message=f"已按模型推荐自动锁定命名。推荐理由：{payload['reason']}\n全部前期设定已锁定完成。")
    project["naming_raw"] = empty_new_project_state()["naming_raw"]
    return ask_node(state, NAMING_FIELD_SPECS[0][1], message="命名候选已生成，请开始锁定书名。")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="dream 工作流总控脚本")
    subparsers = parser.add_subparsers(dest="command", required=True)

    start_parser = subparsers.add_parser("start")
    start_parser.add_argument("--workspace", default=".")
    start_parser.add_argument("--json", action="store_true")

    answer_parser = subparsers.add_parser("answer")
    answer_parser.add_argument("--session", required=True)
    answer_parser.add_argument("--value", required=True)
    answer_parser.add_argument("--json", action="store_true")

    submit_parser = subparsers.add_parser("submit-derived")
    submit_parser.add_argument("--session", required=True)
    submit_parser.add_argument("--node", required=True)
    submit_parser.add_argument("--value", required=True)
    submit_parser.add_argument("--json", action="store_true")

    resume_parser = subparsers.add_parser("resume")
    resume_parser.add_argument("--session", required=True)
    resume_parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.command == "start":
            payload = start(Path(args.workspace).expanduser().resolve())
        elif args.command == "answer":
            payload = answer(args.session, args.value)
        elif args.command == "submit-derived":
            payload = submit_derived(args.session, args.node, args.value)
        else:
            payload = resume(args.session)
    except FileNotFoundError:
        payload = error_payload(None, "SESSION", "会话不存在。")
    return emit(payload)


if __name__ == "__main__":
    raise SystemExit(main())
