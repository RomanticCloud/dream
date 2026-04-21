#!/usr/bin/env python3
"""时间逻辑检查器 - 检查章节的时间线、因果链、人物位置等逻辑问题"""

import re
from dataclasses import dataclass, field
from typing import Optional

from rule_engine import CheckResult


@dataclass
class TimeLogicIssue:
    type: str  # "time_contradiction" | "causal_contradiction" | "location_contradiction" | "number_error"
    severity: str  # "error", "warning"
    message: str
    location: str  # 位置描述
    suggestion: str  # 修复建议


def extract_time_words(text: str) -> dict[str, list[str]]:
    """提取时间词及其上下文

    Returns:
        {
            "三个月": ["第5行", "第29行"],
            "大半年": ["第29行"],
            ...
        }
    """
    time_patterns = [
        (r"([一二三四五六七八九十零]+)个?月", "月"),
        (r"([一二三四五六七八九十零]+)年", "年"),
        (r"([一二三四五六七八九十零]+)天", "天"),
        (r"([一二三四五六七八九十零]+)小时", "小时"),
        (r"([一二三四五六七八九十零]+)分钟", "分钟"),
        (r"(\d+)个?月", "月"),
        (r"(\d+)年", "年"),
        (r"(\d+)天", "天"),
        (r"(\d+)小时", "小时"),
    ]

    time_words = {}
    for pattern, unit in time_patterns:
        matches = re.finditer(pattern, text)
        for match in matches:
            time_phrase = match.group(0)
            line_num = text[:match.start()].count("\n") + 1
            if time_phrase not in time_words:
                time_words[time_phrase] = []
            time_words[time_phrase].append(f"第{line_num}行")

    return time_words


def check_time_consistency(body: str) -> list[TimeLogicIssue]:
    """检查时间词一致性

    规则：
    - 同一章内相同时间跨度必须一致
    - "X个月"和"X+个月"互斥（如"三个月"和"大半年"）
    - 倒计时应该每章递减
    """
    issues = []
    time_words = extract_time_words(body)

    month_pattern = re.compile(r"(\d+)个?月|大半年|小半年|几个月")
    day_pattern = re.compile(r"(\d+)天|几天|十天半个月")

    month_times = {}
    for phrase, locations in time_words.items():
        if "月" in phrase:
            month_match = month_pattern.search(phrase)
            if month_match:
                key = month_match.group(0)
                if key not in month_times:
                    month_times[key] = locations
                else:
                    month_times[key].extend(locations)

    if len(month_times) > 1:
        phrases = list(month_times.keys())
        for i in range(len(phrases)):
            for j in range(i + 1, len(phrases)):
                issues.append(TimeLogicIssue(
                    type="time_contradiction",
                    severity="error",
                    message=f"时间矛盾：'{phrases[i]}' 和 '{phrases[j]}' 不能同时出现在同一章",
                    location=", ".join(month_times[phrases[i]] + month_times[phrases[j]]),
                    suggestion=f"统一为'{phrases[0]}'，删除其他矛盾的时间描述"
                ))

    countdown_pattern = re.compile(r"(\d+):(\d+):(\d+)|剩余时间[：:](\d+)小时|倒计时[：:](\d+)")
    countdowns = []
    for match in countdown_pattern.finditer(body):
        line_num = body[:match.start()].count("\n") + 1
        if match.group(1):
            countdowns.append((int(match.group(1)), int(match.group(2)), int(match.group(3)), line_num))
        elif match.group(4):
            countdowns.append((0, 0, int(match.group(4)), line_num))

    if len(countdowns) > 1:
        for i in range(1, len(countdowns)):
            prev = countdowns[i - 1]
            curr = countdowns[i]
            prev_total = prev[0] * 3600 + prev[1] * 60 + prev[2]
            curr_total = curr[0] * 3600 + curr[1] * 60 + curr[2]
            if curr_total > prev_total:
                issues.append(TimeLogicIssue(
                    type="time_contradiction",
                    severity="warning",
                    message=f"倒计时异常：第{prev[3]}行显示{prev_total}秒，第{curr[3]}行显示{curr_total}秒，时间应该递减",
                    location=f"第{prev[3]}行、第{curr[3]}行",
                    suggestion=f"修正倒计时，确保后文时间早于等于前文"
                ))

    return issues


def check_causal_chain(body: str) -> list[TimeLogicIssue]:
    """检查事件因果链

    规则：
    - "公司倒闭/老板跑路" → 不能有工资/赔偿金
    - "被裁员/被优化" → 有赔偿金
    - "跳槽" → 主动离职，不能写被裁员
    - 注意：被裁员和跳槽在不同事件中时可以的，关键是同一事件不能矛盾
    """
    issues = []

    has_company_collapse = bool(re.search(r"公司倒闭|老板跑路|破产|关门", body))
    has_layoff = bool(re.search(r"被裁员|被优化|被辞退|裁员", body))
    has_severance = bool(re.search(r"赔偿金|补偿金|补偿|n\s*个月工资", body))
    has_job_hopping = bool(re.search(r"跳槽|离职|辞职", body))
    has_salary = bool(re.search(r"月薪|工资|收入", body))

    if has_company_collapse and has_severance:
        collapse_sentences = re.findall(r"[^。]*公司倒闭[^。]*。|老板跑路[^。]*。", body)
        if collapse_sentences:
            for sentence in collapse_sentences:
                if "赔偿金" in sentence or "补偿" in sentence:
                    issues.append(TimeLogicIssue(
                        type="causal_contradiction",
                        severity="error",
                        message="因果矛盾：'公司倒闭/老板跑路'不能有'赔偿金'",
                        location=f"句子: {sentence[:50]}...",
                        suggestion="修改赔偿金来源：要么公司倒闭没钱，要么删除赔偿金描述"
                    ))

    if has_layoff and has_job_hopping:
        layoff_matches = list(re.finditer(r"被裁员|被优化|被辞退", body))
        hop_matches = list(re.finditer(r"跳槽|离职|辞职", body))

        for layoff_match in layoff_matches:
            layoff_line = body[:layoff_match.start()].count("\n") + 1
            for hop_match in hop_matches:
                hop_line = body[:hop_match.start()].count("\n") + 1
                line_diff = abs(layoff_line - hop_line)
                if line_diff <= 3:
                    issues.append(TimeLogicIssue(
                        type="causal_contradiction",
                        severity="error",
                        message="因果矛盾：'被裁员'和'跳槽'在同一段落不能同时出现",
                        location=f"第{layoff_line}行、第{hop_line}行",
                        suggestion="'跳槽'是主动行为，'被裁员'是被动行为，确保不混淆"
                    ))
                    break

    return issues


def check_character_location(body: str) -> list[TimeLogicIssue]:
    """检查人物位置变化

    规则：
    - "离开/走了" → 后续不能再出现该人物（除非重新进门）
    - 追踪每个人物的进出状态
    """
    issues = []

    character_events = {
        "王阿姨": [],
        "小蓝": [],
        "房东": [],
    }

    patterns = [
        (r"(王阿姨|房东).{0,10}(进来|进门|推门|走进来)", "enter"),
        (r"(王阿姨|房东).{0,10}(离开|走了|出门|出去)", "leave"),
        (r"(王阿姨|房东).{0,10}(还|仍然|依然)在", "still_present"),
        (r"小蓝.{0,10}(出现|现身|出现|消失)", "appear_disappear"),
        (r"小蓝.{0,10}(在|到)", "presence"),
    ]

    for char, events in character_events.items():
        char_pattern = re.compile(char)
        for match in char_pattern.finditer(body):
            line_num = body[:match.start()].count("\n") + 1
            for pattern, event_type in patterns:
                full_match = re.search(pattern, body[max(0, match.start()-50):match.end()+50])
                if full_match:
                    events.append((line_num, event_type, full_match.group(0)))

    for char, events in character_events.items():
        if not events:
            continue

        has_leave = any(e[1] == "leave" for e in events)
        has_still_present = any(e[1] == "still_present" for e in events)
        has_enter_after_leave = False

        for i, (line_num, event_type, text) in enumerate(events):
            if event_type == "leave":
                for j in range(i + 1, len(events)):
                    later_line, later_type, later_text = events[j]
                    if later_type in ["enter", "still_present", "presence"]:
                        has_enter_after_leave = True
                        issues.append(TimeLogicIssue(
                            type="location_contradiction",
                            severity="error",
                            message=f"位置矛盾：{char}在第{line_num}行'离开'，但后续又出现",
                            location=f"第{line_num}行、第{later_line}行",
                            suggestion="删除矛盾的位置描述，确保人物动线连贯"
                        ))
                        break

        if has_leave and has_still_present:
            leave_events = [e for e in events if e[1] == "leave"]
            still_events = [e for e in events if e[1] == "still_present"]
            if leave_events and still_events:
                issues.append(TimeLogicIssue(
                    type="location_contradiction",
                    severity="error",
                    message=f"位置矛盾：{char}已经'离开'，但后面写'还在'",
                    location=f"第{leave_events[0][0]}行、第{still_events[0][0]}行",
                    suggestion="删除'还在'的描述或调整离开的时机"
                ))

    return issues


def check_number_consistency(body: str) -> list[TimeLogicIssue]:
    """检查数字合理性

    规则：
    - 赔偿金 = 月薪 × 月数，需要验证
    - 金额需要说明来源
    """
    issues = []

    severance_match = re.search(r"赔偿金.*?(\d+)", body)
    salary_match = re.search(r"月薪.*?(\d+)|工资.*?(\d+)", body)

    if severance_match and salary_match:
        severance = int(severance_match.group(1))
        salary = int(salary_match.group(1) or salary_match.group(2))

        severance_match_full = re.search(r"(\d+)个?月工资|n\s*个月", body)
        if severance_match_full:
            months = int(re.search(r"\d+", severance_match_full.group(0)).group(0))
            expected_severance = salary * months
            if abs(severance - expected_severance) > 1000:
                issues.append(TimeLogicIssue(
                    type="number_error",
                    severity="warning",
                    message=f"数字矛盾：月薪{salary}元 × {months}月 = {expected_severance}元，与赔偿金{severance}元不匹配",
                    location="相关描述位置",
                    suggestion=f"修正赔偿金为{expected_severance}元，或调整月数"
                ))

    return issues


def check_all_logic(body: str) -> list[TimeLogicIssue]:
    """综合检查所有逻辑问题"""
    all_issues = []

    all_issues.extend(check_time_consistency(body))
    all_issues.extend(check_causal_chain(body))
    all_issues.extend(check_character_location(body))
    all_issues.extend(check_number_consistency(body))

    return all_issues


def apply_fixes(body: str, issues: list[TimeLogicIssue]) -> str:
    """根据检查结果自动修复问题

    修复策略：
    1. 时间矛盾：保留最早出现的时间词，删除矛盾的后文
    2. 因果矛盾：删除矛盾的一方（"赔偿金"或"跳槽"）
    3. 位置矛盾：删除矛盾的描述
    4. 数字错误：自动修正
    """
    result = body

    for issue in issues:
        if issue.type == "time_contradiction" and "大半年" in issue.message:
            result = re.sub(r"大半年", "三个月", result)

        elif issue.type == "causal_contradiction" and "赔偿金" in issue.message:
            result = re.sub(r"赔偿金[^。]*[。]?", "", result)
            result = re.sub(r"税后三万八[^。]*[。]?", "存款见底", result)

        elif issue.type == "causal_contradiction" and "跳槽" in issue.message:
            lines = result.split("\n")
            for i, line in enumerate(lines):
                if "跳槽" in line and "被" in line:
                    lines[i] = re.sub(r"跳槽.*?[，。]", "", lines[i])
            result = "\n".join(lines)

        elif issue.type == "location_contradiction" and "王阿姨" in issue.message:
            lines = result.split("\n")
            for i, line in enumerate(lines):
                if "王阿姨" in line and "还" in line and "在" in line:
                    lines[i] = re.sub(r"王阿姨.{0,20}还在", "", lines[i])
            result = "\n".join(lines)

        elif issue.type == "number_error" and "赔偿金" in issue.message:
            salary_match = re.search(r"月薪.*?(\d+)", result)
            if salary_match:
                salary = int(salary_match.group(1))
                result = re.sub(r"税后三万八", f"税后{salary * 2}元", result)

    result = re.sub(r"\n\n+", "\n", result)
    result = re.sub(r" +\n", "\n", result)
    return result


def run_time_logic_checks(chapter_num: int, body: str) -> list[CheckResult]:
    """运行时间逻辑检查，返回CheckResult列表"""
    issues = check_all_logic(body)

    results = []
    for issue in issues:
        results.append(CheckResult(
            passed=False,
            check_type=f"time_logic_{issue.type}",
            message=f"[时间逻辑] {issue.message}",
            suggestion=issue.suggestion,
            severity=issue.severity
        ))

    return results


if __name__ == "__main__":
    import sys
    from pathlib import Path

    if len(sys.argv) < 2:
        print("用法: python time_logic_checker.py <章节文件>")
        sys.exit(1)

    chapter_file = Path(sys.argv[1])
    if not chapter_file.exists():
        print(f"文件不存在: {chapter_file}")
        sys.exit(1)

    from card_parser import extract_body

    content = chapter_file.read_text(encoding="utf-8")
    body = extract_body(content)

    issues = check_all_logic(body)

    print(f"\n{'='*50}")
    print(f"时间逻辑检查结果")
    print(f"{'='*50}")

    if not issues:
        print("✅ 无问题")
    else:
        for issue in issues:
            icon = "❌" if issue.severity == "error" else "⚠"
            print(f"{icon} {issue.message}")
            print(f"   位置: {issue.location}")
            print(f"   建议: {issue.suggestion}")
            print()

    sys.exit(0 if not issues else 1)
