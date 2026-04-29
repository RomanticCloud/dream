#!/usr/bin/env python3
"""章节验证器 - 检查章节的格式、字数、工作卡和连续性"""

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from card_parser import CARD_MARKER, BODY_MARKER, extract_body, extract_section, filled_bullet_stats, split_card_line
from chapter_scan import chapter_file_by_number, latest_chapter
from check_rules import run_single_chapter_checks
from card_names import CARRY_CARD, required_card_headers
from card_fields import (
    CARRY_FIELDS,
    EMOTION_FIELDS,
    FIELD_CARRY_MUST,
    FIELD_CARRY_HOOK,
    FIELD_EMOTION_SUSPENSE,
    FIELD_POWER_AFTER_EFFECT,
    FIELD_POWER_CROSS,
    FIELD_POWER_LEVEL,
    FIELD_POWER_LOSS_RATIO,
    FIELD_POWER_NEW_TRUMP,
    FIELD_POWER_REASONABLE,
    FIELD_POWER_TARGET,
    FIELD_POWER_TRUMP_NAME,
    FIELD_EMOTION_TARGET,
    FIELD_PLOT_EVENT,
    FIELD_RELATION_MAIN,
    FIELD_RESOURCE_GAIN,
    FIELD_RESOURCE_LOSS,
    FIELD_RESOURCE_SPEND,
    FIELD_STATUS_ELAPSED,
    FIELD_STATUS_EMOTION,
    FIELD_STATUS_GOAL,
    FIELD_STATUS_LOCATION,
    FIELD_STATUS_TIMEPOINT,
    PLOT_FIELDS,
    POWER_CARD_FIELDS,
    POWER_STATUS_FIELDS,
    RELATION_FIELDS,
    RESOURCE_FIELDS,
    STATUS_FIELDS,
)
from field_value_rules import (
    ERROR_REQUIRED_FIELDS,
    INHERIT_MARKERS,
    POWER_ERROR_REQUIRED_FIELDS,
    POWER_WARNING_REQUIRED_FIELDS,
    RESOURCE_DELTA_FIELDS,
    WARNING_REQUIRED_FIELDS,
    has_resource_delta,
    is_inherit_marker,
    is_required_non_empty,
    is_valid_elapsed,
    is_valid_power_loss_ratio,
    is_valid_timepoint,
    is_yes_no,
    parse_suspense_strength,
    split_trump_names,
)
from common_io import ProjectStateError, find_chapter_path, load_project_state, require_chapter_word_range
from chapter_view import load_chapter_view
from enhanced_validator import EnhancedValidator
from revision_state import clear_chapter_revision, set_chapter_revision
from rule_engine import build_fix_plan, build_revision_tasks
from time_logic_checker import check_all_logic as check_time_logic, apply_fixes as apply_time_logic_fixes, TimeLogicIssue
from path_rules import chapter_card_file


def resolve_card_file(project_dir: Path, chapter_path: Path, vol_num: int, ch_num: int) -> Path:
    candidates = [
        chapter_card_file(project_dir, vol_num, ch_num),
        chapter_path.parent / "cards" / f"{chapter_path.stem}_card.md",
        chapter_path.parent / "cards" / f"ch{ch_num:03d}_card.md",
        chapter_path.parent / "cards" / f"chapter_card_ch{ch_num:02d}.md",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


@dataclass
class ValidationIssue:
    type: str  # "error" or "warning"
    message: str


@dataclass
class ValidationResult:
    passed: bool
    issues: list[ValidationIssue] = field(default_factory=list)
    word_count: int = 0
    card_status: dict = field(default_factory=dict)
    file_path: Path | None = None
    fix_plan: dict = field(default_factory=dict)
    revision_tasks: list[dict] = field(default_factory=list)


def count_words(text: str) -> int:
    """计算中文字符数（去除空白）"""
    return len(re.sub(r"\s+", "", text))


def validate_format(content: str) -> list[ValidationIssue]:
    """验证格式"""
    issues = []

    if BODY_MARKER not in content:
        issues.append(ValidationIssue("error", '缺少 "## 正文" 标记'))

    return issues


def validate_resource_format(content: str, state: dict) -> list[ValidationIssue]:
    """验证资源卡是否为增量格式（仅 POWER_SYSTEM 项目）
    
    Args:
        content: 章节内容
        state: 项目状态
        
    Returns:
        问题列表
    """
    issues = []
    
    # 检查是否为 POWER_SYSTEM 项目
    specs = state.get("basic_specs", {})
    genres = specs.get("main_genres", [])
    
    POWER_GENRES = ["都市高武", "玄幻奇幻", "仙侠修真"]
    is_power = any(g in POWER_GENRES for g in genres)
    
    if not is_power:
        return issues
    
    # 提取资源卡
    resource_card = extract_section(content, "### 3. 资源卡")
    if not resource_card:
        return issues
    
    # 检查是否有增量格式（+XXX 或 -XXX）
    # 获取资源卡中的列表项
    lines = resource_card.splitlines()
    for line in lines:
        line = line.strip()
        if line.startswith("-") and ("获得" in line or "消耗" in line or "损失" in line):
            # 检查是否包含增量格式
            if not re.search(r'[+-]\d+', line):
                issues.append(ValidationIssue(
                    type="error",
                    message="[资源卡] POWER_SYSTEM项目必须使用增量格式（+XXX/-XXX），例如：+500灵石、-300金币"
                ))
                break
    
    return issues


def validate_word_count(content: str, min_words: int, max_words: int) -> tuple[int, list[ValidationIssue]]:
    """验证字数：字数必须在 min_words ~ max_words 范围内"""
    issues = []

    if BODY_MARKER not in content:
        return 0, issues

    body = extract_body(content)
    word_count = count_words(body)

    # 范围判断：字数必须在 min_words ~ max_words 范围内
    if word_count < min_words:
        issues.append(ValidationIssue("error", f"正文字数 {word_count} 字，低于最小值 {min_words} 字，需要重新生成"))
    elif word_count > max_words:
        issues.append(ValidationIssue("warning", f"正文字数 {word_count} 字，超过最大值 {max_words}"))

    return word_count, issues


def validate_cards(content: str, state: dict) -> tuple[dict, list[ValidationIssue]]:
    """验证工作卡"""
    issues = []
    card_status = {}

    if CARD_MARKER not in content:
        return card_status, [ValidationIssue("error", '缺少 "## 内部工作卡" 标记')]

    required_headers = required_card_headers(state)
    required_field_map = {
        "### 1. 状态卡": POWER_STATUS_FIELDS if required_headers[1] == "### 2. 战力卡" else STATUS_FIELDS,
        "### 2. 情节卡": PLOT_FIELDS,
        "### 2. 战力卡": POWER_CARD_FIELDS,
        "### 3. 资源卡": RESOURCE_FIELDS,
        "### 4. 关系卡": RELATION_FIELDS,
        "### 5. 情绪弧线卡": EMOTION_FIELDS,
        "### 6. 承上启下卡": CARRY_FIELDS,
    }

    for header in required_headers:
        header_clean = header.replace("### ", "").replace(".", "")
        card_status[header_clean] = {}

        section = extract_section(content, header)
        if not section:
            issues.append(ValidationIssue("error", f"缺少 {header}"))
            continue

        filled_count, required_fields = filled_bullet_stats(section)

        fill_rate = filled_count / max(required_fields, 1)
        card_status[header_clean] = {
            "filled": filled_count,
            "total": required_fields,
            "rate": fill_rate
        }

        if fill_rate < 0.5:
            issues.append(ValidationIssue("warning", f"{header} 填写不完整 ({filled_count}/{required_fields})"))

        bullets = extract_section(content, header)
        bullet_map = {}
        for line in bullets.splitlines():
            stripped = line.strip()
            if not stripped.startswith("-"):
                continue
            parts = split_card_line(stripped[1:])
            if not parts:
                continue
            bullet_map[parts[0].strip()] = parts[1].strip()

        expected_fields = required_field_map.get(header, [])
        missing_fields = [field for field in expected_fields if field not in bullet_map]
        if missing_fields:
            issues.append(ValidationIssue("error", f"{header} 缺少标准字段: {', '.join(missing_fields)}"))

        for field in ERROR_REQUIRED_FIELDS:
            if field in bullet_map and not is_required_non_empty(bullet_map[field], allow_inherit=True):
                issues.append(ValidationIssue("error", f"{header} 字段“{field}”不能为空"))

        for field in WARNING_REQUIRED_FIELDS:
            if field in bullet_map and not is_required_non_empty(bullet_map[field], allow_inherit=True):
                issues.append(ValidationIssue("warning", f"{header} 字段“{field}”建议填写"))

        if header == "### 2. 战力卡":
            for field in POWER_ERROR_REQUIRED_FIELDS:
                if field in bullet_map and not is_required_non_empty(bullet_map[field], allow_inherit=True):
                    issues.append(ValidationIssue("error", f"{header} 字段“{field}”不能为空"))
            for field in POWER_WARNING_REQUIRED_FIELDS:
                if field in bullet_map and not is_required_non_empty(bullet_map[field], allow_inherit=True):
                    issues.append(ValidationIssue("warning", f"{header} 字段“{field}”建议填写"))

            if FIELD_POWER_CROSS in bullet_map and bullet_map[FIELD_POWER_CROSS] and not is_yes_no(bullet_map[FIELD_POWER_CROSS]):
                issues.append(ValidationIssue("error", f"{header} 字段“{FIELD_POWER_CROSS}”只能填写“是”或“否”"))

            if FIELD_POWER_NEW_TRUMP in bullet_map and bullet_map[FIELD_POWER_NEW_TRUMP] and not is_yes_no(bullet_map[FIELD_POWER_NEW_TRUMP]):
                issues.append(ValidationIssue("error", f"{header} 字段“{FIELD_POWER_NEW_TRUMP}”只能填写“是”或“否”"))

            if FIELD_POWER_LOSS_RATIO in bullet_map and bullet_map[FIELD_POWER_LOSS_RATIO] and not is_valid_power_loss_ratio(bullet_map[FIELD_POWER_LOSS_RATIO]):
                issues.append(ValidationIssue("error", f"{header} 字段“{FIELD_POWER_LOSS_RATIO}”格式非法: {bullet_map[FIELD_POWER_LOSS_RATIO]}"))

            if FIELD_POWER_TRUMP_NAME in bullet_map and is_required_non_empty(bullet_map[FIELD_POWER_TRUMP_NAME]) and not split_trump_names(bullet_map[FIELD_POWER_TRUMP_NAME]):
                issues.append(ValidationIssue("error", f"{header} 字段“{FIELD_POWER_TRUMP_NAME}”必须包含至少一个底牌名称"))

            if bullet_map.get(FIELD_POWER_CROSS) == "是" and not is_required_non_empty(bullet_map.get(FIELD_POWER_REASONABLE, "")):
                issues.append(ValidationIssue("error", f"{header} 字段“{FIELD_POWER_REASONABLE}”在越级时必须填写"))

        if FIELD_STATUS_ELAPSED in bullet_map and bullet_map[FIELD_STATUS_ELAPSED] and not is_valid_elapsed(bullet_map[FIELD_STATUS_ELAPSED]):
            issues.append(ValidationIssue("error", f"{header} 字段“{FIELD_STATUS_ELAPSED}”格式非法: {bullet_map[FIELD_STATUS_ELAPSED]}"))

        if FIELD_STATUS_TIMEPOINT in bullet_map and bullet_map[FIELD_STATUS_TIMEPOINT] and not is_valid_timepoint(bullet_map[FIELD_STATUS_TIMEPOINT]):
            issues.append(ValidationIssue("error", f"{header} 字段“{FIELD_STATUS_TIMEPOINT}”格式非法: {bullet_map[FIELD_STATUS_TIMEPOINT]}"))

        if FIELD_EMOTION_SUSPENSE in bullet_map and bullet_map[FIELD_EMOTION_SUSPENSE]:
            if parse_suspense_strength(bullet_map[FIELD_EMOTION_SUSPENSE]) is None:
                issues.append(ValidationIssue("error", f"{header} 字段“{FIELD_EMOTION_SUSPENSE}”必须为1-10的整数"))

        for field in RESOURCE_DELTA_FIELDS:
            if field in bullet_map and is_required_non_empty(bullet_map[field], allow_inherit=True) and not has_resource_delta(bullet_map[field]):
                issues.append(ValidationIssue("warning", f"{header} 字段“{field}”建议使用 +/-数字+资源名 格式"))

    for header in required_headers:
        section = extract_section(content, header)
        if not section:
            continue

        if header == CARRY_CARD:
            lines = section.splitlines()
            has_content = any(
                split_card_line(line) and split_card_line(line)[1].strip()
                for line in lines if line.strip().startswith("-")
            )
            if not has_content:
                issues.append(ValidationIssue("warning", "承上启下卡 未填写内容"))

    return card_status, issues


def validate_continuity(content: str) -> list[ValidationIssue]:
    """验证连续性"""
    issues = []

    if CARD_MARKER not in content:
        return issues

    carry_section = extract_section(content, CARRY_CARD)

    has_carry_over = False
    for line in carry_section.splitlines():
        parts = split_card_line(line)
        if "-" in line and parts:
            value = parts[1].strip()
            if value and value not in ["", "（待填）"]:
                has_carry_over = True
                break

    if not has_carry_over:
        issues.append(ValidationIssue("warning", "承上启下卡 未填写内容，无法保证连续性"))

    return issues


def validate_chapter(
    project_dir: Path,
    vol_num: int | None = None,
    ch_num: int | None = None,
) -> ValidationResult:
    """验证章节：字数必须在 min_words ~ max_words 范围内"""
    
    # 确定卷章号
    if vol_num is None or ch_num is None:
        vol_num, ch_num, _ = latest_chapter(project_dir)
    
    # 检查缓存（已通过的校验结果可直接复用）
    try:
        from validation_cache import get_cached_validation
        cached = get_cached_validation(project_dir, vol_num, ch_num)
        if cached:
            return ValidationResult(
                passed=cached["passed"],
                issues=[ValidationIssue(i["type"], i["message"]) for i in cached["issues"]],
                word_count=cached.get("word_count", 0),
            )
    except Exception:
        pass  # 缓存读取失败不影响主流程

    state = load_project_state(project_dir)
    try:
        min_words, max_words = require_chapter_word_range(state)
    except ProjectStateError as exc:
        return ValidationResult(
            passed=False,
            issues=[ValidationIssue("error", f"项目配置不完整：{exc}")],
            file_path=None,
        )

    if vol_num is None or ch_num is None:
        vol_num, ch_num, chapter_file = latest_chapter(project_dir)
    else:
        chapter_file = chapter_file_by_number(project_dir, vol_num, ch_num)
        if not chapter_file:
            return ValidationResult(
                passed=False,
                issues=[ValidationIssue("error", f"章节文件不存在")],
                file_path=None
            )

    if not chapter_file or not chapter_file.exists():
        return ValidationResult(
            passed=False,
            issues=[ValidationIssue("error", f"章节文件不存在")],
            file_path=chapter_file
        )

    view = load_chapter_view(project_dir, vol_num, ch_num)
    raw_content = view.raw_body_file
    content = view.merged_text

    if view.has_inline_card:
        all_issues = [ValidationIssue("error", '正文文件不得包含 "## 内部工作卡" 标记，请先分离工作卡')]
    else:
        all_issues = []

    format_issues = validate_format(content)
    all_issues.extend(format_issues)

    word_count, word_issues = validate_word_count(content, min_words, max_words)
    all_issues.extend(word_issues)

    card_status, card_issues = validate_cards(content, state)
    all_issues.extend(card_issues)

    continuity_issues = validate_continuity(content)
    all_issues.extend(continuity_issues)

    # 时间逻辑检查
    body = extract_body(content)
    time_logic_issues = check_time_logic(body)
    for tli in time_logic_issues:
        all_issues.append(ValidationIssue(
            type=tli.severity,
            message=f"[时间逻辑] {tli.message}"
        ))

    # 跨章一致性检查
    if ch_num and ch_num > 1:
        prev_chapter_path = find_chapter_path(project_dir, ch_num - 1)
        if prev_chapter_path:
            enhanced_validator = EnhancedValidator(project_dir)

            carry_issues = enhanced_validator.check_carry_over_fulfilled(
                prev_chapter_path, chapter_file
            )
            for ei in carry_issues:
                all_issues.append(ValidationIssue(
                    type=ei.severity,
                    message=ei.message
                ))

            consistency_issues = enhanced_validator.validate_cross_chapter_consistency(
                chapter_file, prev_chapter_path
            )
            for ei in consistency_issues:
                all_issues.append(ValidationIssue(
                    type=ei.severity,
                    message=ei.message
                ))

    contract_issues = EnhancedValidator(project_dir).validate_generation_contract(vol_num, ch_num)
    for ei in contract_issues:
        all_issues.append(ValidationIssue(
            type=ei.severity,
            message=ei.message
        ))

    # 检查资源卡格式（仅 POWER_SYSTEM 项目）
    resource_format_issues = validate_resource_format(content, state)
    all_issues.extend(resource_format_issues)

    has_errors = any(issue.type == "error" for issue in all_issues)
    has_format_error = any(issue.type == "error" and "标记" in issue.message for issue in all_issues)
    blocking_issues = [issue for issue in all_issues if issue.type == "error"]
    revision_tasks = build_revision_tasks(blocking_issues)

    fix_plan = {}
    if not has_format_error:
        check_results = run_single_chapter_checks(ch_num, content, state)
        fix_plan = build_fix_plan(check_results, include_all=True)
        if any("低于质量门槛" in issue.message for issue in all_issues):
            fix_plan.setdefault("regenerate", []).insert(0, {
                "name": "字数门槛",
                "details": f"正文字数 {word_count} 字，低于质量门槛",
                "severity": "high",
            })
            fix_plan["total_regenerate"] = len(fix_plan["regenerate"])
        has_rewrite_card = any(task.get("fix_method") == "rewrite_card" for task in revision_tasks)
        if has_errors and fix_plan.get("total_regenerate", 0) > 0:
            set_chapter_revision(project_dir, vol_num, ch_num, "pending_regenerate", fix_plan, revision_tasks)
        elif has_errors and has_rewrite_card:
            set_chapter_revision(project_dir, vol_num, ch_num, "pending_rewrite_card", fix_plan, revision_tasks)
        elif revision_tasks:
            set_chapter_revision(project_dir, vol_num, ch_num, "pending_polish", fix_plan, revision_tasks)
        else:
            clear_chapter_revision(project_dir, vol_num, ch_num)

    result = ValidationResult(
        passed=not has_errors,
        issues=all_issues,
        word_count=word_count,
        card_status=card_status,
        file_path=chapter_file,
        fix_plan=fix_plan,
        revision_tasks=revision_tasks,
    )
    
    # 保存校验缓存（仅保存通过的校验结果）
    try:
        from validation_cache import save_validation_cache
        save_validation_cache(project_dir, vol_num, ch_num, result)
    except Exception:
        pass  # 缓存保存失败不影响主流程

    return result


def fix_time_logic_and_revalidate(
    project_dir: Path,
    vol_num: int,
    ch_num: int,
) -> tuple[bool, list[TimeLogicIssue]]:
    """自动修复时间逻辑问题并重新验证

    Returns:
        (fixed: bool, remaining_issues: list)
    """
    chapter_file = chapter_file_by_number(project_dir, vol_num, ch_num)
    if not chapter_file or not chapter_file.exists():
        return False, []

    view = load_chapter_view(project_dir, vol_num, ch_num)
    body = extract_body(view.body_text)

    issues = check_time_logic(body)
    if not issues:
        return True, []

    fixed_body = apply_time_logic_fixes(body, issues)
    fixed_content = view.body_text.replace(body, fixed_body, 1)
    chapter_file.write_text(fixed_content.rstrip() + "\n", encoding="utf-8")

    new_issues = check_time_logic(extract_body(fixed_content))
    return len(new_issues) == 0, new_issues


def print_result(result: ValidationResult):
    """打印验证结果"""
    print(f"\n{'='*50}")
    print(f"验证结果: {'✓ 通过' if result.passed else '❌ 失败'}")
    print(f"{'='*50}")

    if result.file_path:
        print(f"文件: {result.file_path.relative_to(result.file_path.parent.parent)}")

    if result.word_count > 0:
        print(f"正文字数: {result.word_count} 字")

    print(f"\n问题列表:")
    if result.issues:
        for issue in result.issues:
            icon = "❌" if issue.type == "error" else "⚠"
            print(f"  {icon} {issue.message}")
    else:
        print("  无问题")

    print("")


def main():
    import argparse
    import json
    parser = argparse.ArgumentParser(description="章节验证器")
    parser.add_argument("project_dir", nargs="?", default=".", help="项目目录")
    parser.add_argument("vol", nargs="?", type=int, help="卷号")
    parser.add_argument("ch", nargs="?", type=int, help="章节号")
    parser.add_argument("--json", "-j", action="store_true", help="JSON格式输出")
    parser.add_argument("--auto-revision", "-r", action="store_true", help="自动处理回改")
    args = parser.parse_args()

    project_dir = Path(args.project_dir).expanduser().resolve()
    if not project_dir.exists():
        print(f"项目目录不存在: {project_dir}")
        sys.exit(1)

    result = validate_chapter(project_dir, args.vol, args.ch)

    if args.json:
        import json
        output = {
            "passed": result.passed,
            "word_count": result.word_count,
            "issues": [{"type": i.type, "message": i.message} for i in result.issues],
            "revision_tasks": result.revision_tasks,
        }
        if result.fix_plan:
            output["fix_plan"] = result.fix_plan
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print_result(result)

        if result.fix_plan and result.fix_plan.get("total_regenerate", 0) > 0:
            print("\n【高严重度问题】需整章重写:")
            for item in result.fix_plan["regenerate"]:
                print(f"  - {item['name']}: {item['details']}")
        if result.fix_plan and result.fix_plan.get("total_polish", 0) > 0:
            print("\n【低严重度问题】AI润色:")
            for item in result.fix_plan["ai_polish"]:
                print(f"  - {item['name']}: {item['details']}")

    if result.fix_plan:
        fix_plan_path = project_dir / "CHAPTER_FIX_PLAN.json"
        fix_plan_path.write_text(json.dumps(result.fix_plan, ensure_ascii=False, indent=2), encoding="utf-8")

    sys.exit(0 if result.passed else 1)


if __name__ == "__main__":
    main()
