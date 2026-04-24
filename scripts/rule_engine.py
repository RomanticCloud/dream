#!/usr/bin/env python3
"""Shared result models and helpers for chapter/volume checks."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re


@dataclass
class CheckResult:
    name: str
    passed: bool
    details: str
    suggestion: str
    severity: str = "none"
    scope: str = "none"
    fix_method: str = "none"


@dataclass
class RevisionTask:
    type: str
    severity: str
    card: str = ""
    field: str = ""
    message: str = ""
    instruction: str = ""
    fix_method: str = "polish"
    scope: str = "field"
    rewrite_target: str = "local_patch"
    preserve_constraints: list[str] | None = None
    blocking: bool = False
    priority: str = "medium"


CARD_FIELD_PATTERN = re.compile(r"^(?P<card>###\s*\d+\.\s*[^\s]+)\s+字段“(?P<field>[^”]+)”(?P<detail>.+)$")
MISSING_CARD_PATTERN = re.compile(r"^缺少\s+(?P<card>###\s*\d+\.\s*.+)$")


def _normalize_card_name(card_header: str) -> str:
    return card_header.replace("###", "").strip()


def _issue_to_task(issue) -> RevisionTask:
    message = issue.message
    severity = issue.type

    if '缺少 "## 正文" 标记' in message or '缺少 "## 内部工作卡" 标记' in message:
        return RevisionTask("format_missing", severity, message=message, instruction="补全缺失的章节结构标记，确保正文和内部工作卡标记存在。", fix_method="regenerate", scope="chapter", rewrite_target="full_chapter", preserve_constraints=["保留本章核心事件", "保留章节结尾结果"], blocking=True, priority="high")

    match = MISSING_CARD_PATTERN.match(message)
    if match:
        card = _normalize_card_name(match.group("card"))
        return RevisionTask("field_missing", severity, card=card, message=message, instruction=f"补全{card}及其标准字段。", fix_method="rewrite_card", scope="card", rewrite_target="work_cards_only", preserve_constraints=["工作卡必须与正文一致", "不得新增正文未发生情节"], blocking=True, priority="high")

    match = CARD_FIELD_PATTERN.match(message)
    if match:
        card = _normalize_card_name(match.group("card"))
        field = match.group("field")
        detail = match.group("detail")
        if "缺少标准字段" in detail:
            task_type = "field_missing"
            instruction = f"在{card}中补上标准字段“{field}”。"
            fix_method = "rewrite_card"
        elif "不能为空" in detail:
            task_type = "field_empty"
            instruction = f"为{card}的“{field}”补充明确内容，不能留空。"
            fix_method = "rewrite_card"
        elif "在越级时必须填写" in detail:
            task_type = "field_empty"
            instruction = f"补全{card}的“{field}”，在越级时必须给出明确说明。"
            fix_method = "rewrite_card"
        elif "格式非法" in detail or "只能填写" in detail or "必须为1-10的整数" in detail or "必须包含至少一个底牌名称" in detail:
            task_type = "power_card_invalid" if "战力卡" in card else "field_invalid"
            instruction = f"修正{card}的“{field}”为合法格式。"
            fix_method = "rewrite_card"
        elif "建议使用 +/-数字+资源名 格式" in detail:
            task_type = "resource_format_weak"
            instruction = f"将{card}的“{field}”改为 +/-数字+资源名 的格式。"
            fix_method = "polish"
        else:
            task_type = "field_invalid"
            instruction = f"检查并修正{card}的“{field}”。"
            fix_method = "rewrite_card"
        rewrite_target = "work_cards_only" if fix_method == "rewrite_card" else "local_patch"
        scope = "field" if field else "card"
        preserve_constraints = ["工作卡必须与正文一致"] if rewrite_target == "work_cards_only" else ["不改变主事件与章节结构"]
        blocking = severity == "error"
        priority = "high" if severity == "error" else "low"
        return RevisionTask(task_type, severity, card=card, field=field, message=message, instruction=instruction, fix_method=fix_method, scope=scope, rewrite_target=rewrite_target, preserve_constraints=preserve_constraints, blocking=blocking, priority=priority)

    if "正文字数" in message and "低于质量门槛" in message:
        return RevisionTask("word_count_low", severity, message=message, instruction="整章重写并提升正文字数到质量门槛以上。", fix_method="regenerate", scope="chapter", rewrite_target="full_chapter", preserve_constraints=["保留本章核心事件", "保留章节结尾结果"], blocking=True, priority="high")
    if "正文字数" in message and "超过最大值" in message:
        return RevisionTask("word_count_high", severity, message=message, instruction="压缩重复描写与冗余内容，控制章节长度。", fix_method="polish", scope="chapter", rewrite_target="local_patch", preserve_constraints=["保留本章核心事件", "保留章节结尾结果"], blocking=False, priority="medium")
    if "承上启下卡" in message:
        return RevisionTask("continuity_missing", severity, card="6. 承上启下卡", field="下章必须接住什么", message=message, instruction="补充承上启下卡中的承接与钩子信息，确保下一章可继续。", fix_method="rewrite_card", scope="card", rewrite_target="work_cards_only", preserve_constraints=["工作卡必须与正文一致", "保留正文主事件"], blocking=severity == "error", priority="high" if severity == "error" else "medium")
    if "资源卡" in message:
        return RevisionTask("resource_format_weak", severity, card="3. 资源卡", message=message, instruction="按标准格式补强资源卡字段值。", fix_method="polish", scope="field", rewrite_target="local_patch", preserve_constraints=["不改变资源事件本身"], blocking=False, priority="low")

    return RevisionTask("field_invalid", severity, message=message, instruction="根据提示修正本章内容。", fix_method="polish" if severity == "warning" else "rewrite_card", scope="field", rewrite_target="local_patch" if severity == "warning" else "work_cards_only", preserve_constraints=["工作卡必须与正文一致"] if severity != "warning" else ["不改变主事件与章节结构"], blocking=severity == "error", priority="high" if severity == "error" else "low")


def build_revision_tasks(issues: list) -> list[dict]:
    tasks = [_issue_to_task(issue) for issue in issues]
    return [asdict(task) for task in tasks]


def build_revision_tasks_from_check_results(results: list[CheckResult]) -> list[dict]:
    tasks: list[dict] = []
    for result in results:
        if result.passed or result.fix_method == "none":
            continue
        if result.fix_method == "regenerate":
            task_type = "word_count_low" if "字数" in result.name else "continuity_missing"
            instruction = result.suggestion or f"重写并修复：{result.name}"
            fix_method = "regenerate"
        elif result.fix_method == "ai_polish":
            task_type = "polish_issue"
            instruction = result.suggestion or f"润色并修复：{result.name}"
            fix_method = "polish"
        else:
            task_type = "field_invalid"
            instruction = result.suggestion or f"修复：{result.name}"
            fix_method = "rewrite_card"
        tasks.append(asdict(RevisionTask(
            type=task_type,
            severity="error" if not result.passed else "warning",
            card=result.name,
            message=result.details,
            instruction=instruction,
            fix_method=fix_method,
            scope="chapter",
            rewrite_target="full_chapter" if fix_method == "regenerate" else "local_patch",
            preserve_constraints=["保留卷级既定结果", "保留已有主事件"],
            blocking=not result.passed,
            priority="high" if not result.passed else "medium",
        )))
    return tasks


def group_revision_tasks(tasks: list[dict]) -> dict[str, list[dict]]:
    grouped = {"regenerate": [], "rewrite_card": [], "polish": []}
    for task in tasks:
        method = task.get("fix_method", "polish")
        if method not in grouped:
            grouped[method] = []
        grouped[method].append(task)
    return grouped


def sort_revision_tasks(tasks: list[dict]) -> list[dict]:
    priority_order = {"high": 0, "medium": 1, "low": 2}
    severity_order = {"error": 0, "warning": 1, "info": 2}
    return sorted(
        tasks,
        key=lambda task: (
            0 if task.get("blocking") else 1,
            priority_order.get(task.get("priority", "medium"), 9),
            severity_order.get(task.get("severity", "info"), 9),
        ),
    )


def infer_execution_mode(tasks: list[dict]) -> str:
    rewrite_targets = {task.get("rewrite_target") for task in tasks}
    if "full_chapter" in rewrite_targets:
        return "full_chapter"
    if "work_cards_only" in rewrite_targets:
        return "work_cards_only"
    return "local_patch"


def filter_tasks_for_mode(tasks: list[dict], mode: str) -> list[dict]:
    sorted_tasks = sort_revision_tasks(tasks)
    if mode == "full_chapter":
        return [task for task in sorted_tasks if task.get("rewrite_target") == "full_chapter"] or sorted_tasks
    if mode == "work_cards_only":
        return [task for task in sorted_tasks if task.get("rewrite_target") == "work_cards_only"] or sorted_tasks
    return [task for task in sorted_tasks if task.get("rewrite_target") == "local_patch"] or sorted_tasks


def sort_revision_tasks(tasks: list[dict]) -> list[dict]:
    priority_order = {"high": 0, "medium": 1, "low": 2}
    severity_order = {"error": 0, "warning": 1, "info": 2}
    return sorted(
        tasks,
        key=lambda task: (
            0 if task.get("blocking") else 1,
            priority_order.get(task.get("priority", "medium"), 9),
            severity_order.get(task.get("severity", "info"), 9),
        ),
    )


def infer_execution_mode(tasks: list[dict]) -> str:
    rewrite_targets = {task.get("rewrite_target") for task in tasks}
    if "full_chapter" in rewrite_targets:
        return "full_chapter"
    if "work_cards_only" in rewrite_targets:
        return "work_cards_only"
    return "local_patch"


def filter_tasks_for_mode(tasks: list[dict], mode: str) -> list[dict]:
    sorted_tasks = sort_revision_tasks(tasks)
    if mode == "full_chapter":
        return [task for task in sorted_tasks if task.get("rewrite_target") == "full_chapter"] or sorted_tasks
    if mode == "work_cards_only":
        return [task for task in sorted_tasks if task.get("rewrite_target") == "work_cards_only"] or sorted_tasks
    return [task for task in sorted_tasks if task.get("rewrite_target") == "local_patch"] or sorted_tasks


def infer_revision_status(tasks: list[dict], fix_plan: dict | None = None) -> str:
    methods = {task.get("fix_method") for task in tasks}
    if "regenerate" in methods:
        return "pending_regenerate"
    if "rewrite_card" in methods:
        return "pending_rewrite_card"
    if "polish" in methods:
        return "pending_polish"

    fix_plan = fix_plan or {}
    if fix_plan.get("total_regenerate", 0) > 0:
        return "pending_regenerate"
    if fix_plan.get("total_polish", 0) > 0:
        return "pending_polish"
    return "passed"


def build_fix_plan(results: list[CheckResult], include_all: bool = False) -> dict:
    regenerate_items = [result for result in results if result.fix_method == "regenerate"]
    polish_items = [result for result in results if result.fix_method == "ai_polish"]

    payload = {
        "regenerate": [{"name": r.name, "details": r.details, "severity": r.severity} for r in regenerate_items],
        "ai_polish": [{"name": r.name, "details": r.details, "severity": r.severity} for r in polish_items],
        "total_regenerate": len(regenerate_items),
        "total_polish": len(polish_items),
    }
    if include_all:
        payload["all_results"] = [asdict(result) for result in results]
    return payload


def passed_count(results: list[CheckResult]) -> int:
    return sum(1 for result in results if result.passed)
