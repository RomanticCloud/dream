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
from common_io import load_project_state
from revision_state import clear_chapter_revision, set_chapter_revision
from rule_engine import build_fix_plan


REQUIRED_CARD_HEADERS = [
    "### 1. 状态卡",
    "### 2. 情节卡",
    "### 3. 资源卡",
    "### 4. 关系卡",
    "### 5. 情感弧卡",
    "### 6. 承上启下卡",
]


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


def count_words(text: str) -> int:
    """计算中文字符数（去除空白）"""
    return len(re.sub(r"\s+", "", text))


def validate_format(content: str) -> list[ValidationIssue]:
    """验证格式"""
    issues = []

    if BODY_MARKER not in content:
        issues.append(ValidationIssue("error", '缺少 "## 正文" 标记'))

    if CARD_MARKER not in content:
        issues.append(ValidationIssue("error", '缺少 "## 内部工作卡" 标记'))

    return issues


def validate_word_count(content: str, min_words: int, max_words: int, threshold_factor: float = 0.85) -> tuple[int, list[ValidationIssue]]:
    """验证字数
    threshold_factor: 通过阈值因子，默认85%（即 min_words * 0.85）
    """
    issues = []

    if BODY_MARKER not in content:
        return 0, issues

    body = extract_body(content)
    word_count = count_words(body)
    
    # 质量门阈值
    pass_threshold = int(min_words * threshold_factor)

    # 严格判断：低于pass_threshold直接失败（Reject）
    if word_count < pass_threshold:
        issues.append(ValidationIssue("error", f"正文字数 {word_count} 字，低于质量门槛 {pass_threshold} 字（{threshold_factor*100:.0f}%阈值），需要重新生成"))
    # 低于最小值但高于阈值，给警告（仍通过）
    elif word_count < min_words:
        issues.append(ValidationIssue("warning", f"正文字数 {word_count} 字，低于目标 {min_words} 字但可通过"))
    # 超过最大字，给警告
    elif word_count > max_words:
        issues.append(ValidationIssue("warning", f"正文字数 {word_count} 字，超过最大值 {max_words}"))

    return word_count, issues


def validate_cards(content: str) -> tuple[dict, list[ValidationIssue]]:
    """验证工作卡"""
    issues = []
    card_status = {}

    if CARD_MARKER not in content:
        return card_status, [ValidationIssue("error", '缺少 "## 内部工作卡" 标记')]

    for header in REQUIRED_CARD_HEADERS:
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

    for header in REQUIRED_CARD_HEADERS:
        section = extract_section(content, header)
        if not section:
            continue

        if "承接" in header:
            lines = section.splitlines()
            has_content = any(
                split_card_line(line) and split_card_line(line)[1].strip()
                for line in lines if line.strip().startswith("-")
            )
            if not has_content:
                issues.append(ValidationIssue("warning", "承上启下卡 - 承接 字段未填写"))

    return card_status, issues


def validate_continuity(content: str) -> list[ValidationIssue]:
    """验证连续性"""
    issues = []

    if CARD_MARKER not in content:
        return issues

    carry_section = extract_section(content, "### 6. 承上启下卡") or extract_section(content, "### 6.承接启下卡")

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
    threshold_factor: float = 0.85
) -> ValidationResult:
    """验证章节
    threshold_factor: 通过阈值因子，默认85%
    """

    state = load_project_state(project_dir)
    specs = state.get("basic_specs", {})
    min_words = specs.get("chapter_length_min", 3500)
    max_words = specs.get("chapter_length_max", 5500)

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

    content = chapter_file.read_text(encoding="utf-8")

    all_issues = []

    format_issues = validate_format(content)
    all_issues.extend(format_issues)

    word_count, word_issues = validate_word_count(content, min_words, max_words, threshold_factor)
    all_issues.extend(word_issues)

    card_status, card_issues = validate_cards(content)
    all_issues.extend(card_issues)

    continuity_issues = validate_continuity(content)
    all_issues.extend(continuity_issues)

    has_errors = any(issue.type == "error" for issue in all_issues)
    has_format_error = any(issue.type == "error" and "标记" in issue.message for issue in all_issues)

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
        if fix_plan.get("total_regenerate", 0) > 0:
            set_chapter_revision(project_dir, vol_num, ch_num, "pending_regenerate", fix_plan)
        elif fix_plan.get("total_polish", 0) > 0:
            set_chapter_revision(project_dir, vol_num, ch_num, "pending_polish", fix_plan)
        else:
            clear_chapter_revision(project_dir, vol_num, ch_num)

    return ValidationResult(
        passed=not has_errors,
        issues=all_issues,
        word_count=word_count,
        card_status=card_status,
        file_path=chapter_file,
        fix_plan=fix_plan
    )


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
    parser = argparse.ArgumentParser(description="章节验证器")
    parser.add_argument("project_dir", nargs="?", default=".", help="项目目录")
    parser.add_argument("vol", nargs="?", type=int, help="卷号")
    parser.add_argument("ch", nargs="?", type=int, help="章节号")
    parser.add_argument("--threshold", "-t", type=float, default=0.85, help="通过阈值因子（默认0.85）")
    parser.add_argument("--json", "-j", action="store_true", help="JSON格式输出")
    parser.add_argument("--auto-revision", "-r", action="store_true", help="自动处理回改")
    args = parser.parse_args()

    project_dir = Path(args.project_dir).expanduser().resolve()
    if not project_dir.exists():
        print(f"项目目录不存在: {project_dir}")
        sys.exit(1)

    result = validate_chapter(project_dir, args.vol, args.ch, args.threshold)

    if args.json:
        import json
        output = {
            "passed": result.passed,
            "word_count": result.word_count,
            "issues": [{"type": i.type, "message": i.message} for i in result.issues]
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
