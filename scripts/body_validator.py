#!/usr/bin/env python3
"""正文校验器 - 检查正文内容的字数、格式、连续性和质量"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from common_io import load_project_state, require_chapter_word_range
from path_rules import chapter_file


# 章节标记
BODY_MARKER = "## 正文"
CARD_MARKER = "## 内部工作卡"


@dataclass
class BodyValidationIssue:
    """正文校验问题"""
    type: str  # "error" or "warning"
    message: str


@dataclass
class BodyValidationResult:
    """正文校验结果"""
    passed: bool
    issues: list[BodyValidationIssue] = field(default_factory=list)
    word_count: int = 0
    quality_report: dict = field(default_factory=dict)


def count_words(text: str) -> int:
    """计算中文字符数（去除空白）"""
    return len(re.sub(r"\s+", "", text))


def extract_body(content: str) -> str:
    """提取正文内容（## 正文 到 ## 内部工作卡 之间）"""
    body_match = re.search(rf'{re.escape(BODY_MARKER)}(.*?)(?:{re.escape(CARD_MARKER)}|$)', content, re.DOTALL)
    if body_match:
        return body_match.group(1).strip()
    return ""


def validate_body(body_text: str, project_dir: Path, vol_num: int, ch_num: int) -> BodyValidationResult:
    """校验正文内容
    
    只返回硬性标准（error/warning），主观质量指标记录到 quality_report
    """
    issues: list[BodyValidationIssue] = []
    
    # 1. 格式校验（硬性标准）
    format_issues = _validate_format(body_text)
    issues.extend(format_issues)
    
    # 2. 字数校验（硬性标准）
    body_content = extract_body(body_text)
    word_count = count_words(body_content)
    
    try:
        state = load_project_state(project_dir)
        min_words, max_words = require_chapter_word_range(state)
        
        if word_count < min_words:
            issues.append(BodyValidationIssue(
                "error", 
                f"正文字数 {word_count} 字，低于最小值 {min_words} 字"
            ))
        elif word_count > max_words:
            issues.append(BodyValidationIssue(
                "warning",
                f"正文字数 {word_count} 字，超过最大值 {max_words} 字"
            ))
    except Exception:
        pass  # 如果无法读取配置，跳过字数校验
    
    # 3. 生成质量报告（主观标准，不返回为 issues）
    quality_report = _generate_quality_report(body_text, word_count)
    
    # 判断结果（只看 error，warning 不影响通过）
    passed = not any(issue.type == "error" for issue in issues)
    
    return BodyValidationResult(
        passed=passed,
        issues=issues,
        word_count=word_count,
        quality_report=quality_report
    )


def _validate_format(content: str) -> list[BodyValidationIssue]:
    """验证格式（硬性标准）"""
    issues = []
    
    if BODY_MARKER not in content:
        issues.append(BodyValidationIssue("error", f'缺少 "{BODY_MARKER}" 标记'))
    
    if CARD_MARKER in content:
        issues.append(BodyValidationIssue("error", f'正文不得包含 "{CARD_MARKER}" 标记'))
    
    return issues


def _generate_quality_report(content: str, word_count: int) -> dict:
    """生成内容质量报告（主观标准，仅供参考）
    
    这些指标不影响校验结果，只作为参考信息保存
    """
    body = extract_body(content)
    report = {
        "word_count": word_count,
        "metrics": {}
    }
    
    # 1. AI痕迹检测
    ai_patterns = {
        "微微一笑": r'微微一笑',
        "若有所思": r'若有所思',
        "点了点头": r'点了点头',
        "不由得": r'不由得',
        "下意识": r'下意识',
    }
    ai_traces = {}
    for name, pattern in ai_patterns.items():
        matches = re.findall(pattern, body)
        if matches:
            ai_traces[name] = len(matches)
    if ai_traces:
        report["metrics"]["ai_traces"] = ai_traces
    
    # 2. 段落长度分析
    paragraphs = [p.strip() for p in body.split('\n\n') if p.strip()]
    if paragraphs:
        long_paragraphs = [p for p in paragraphs if count_words(p) > 500]
        report["metrics"]["paragraphs"] = {
            "total": len(paragraphs),
            "long_count": len(long_paragraphs),
            "long_ratio": round(len(long_paragraphs) / len(paragraphs), 2),
            "avg_length": round(sum(count_words(p) for p in paragraphs) / len(paragraphs), 0),
        }
    
    # 3. 对话比例
    dialogues = re.findall(r'["""][^"""]*["""]', body)
    if dialogues:
        dialogue_words = sum(count_words(d) for d in dialogues)
        report["metrics"]["dialogue"] = {
            "dialogue_count": len(dialogues),
            "dialogue_words": dialogue_words,
            "dialogue_ratio": round(dialogue_words / max(word_count, 1), 2),
        }
    
    # 4. 时间跳跃统计
    time_jumps = re.findall(r'(?:第二天|几天后|一周后|一个月后|一年后)', body)
    if time_jumps:
        report["metrics"]["time_jumps"] = {
            "count": len(time_jumps),
            "indicators": list(set(time_jumps)),
        }
    
    # 5. 场景切换统计
    scene_changes = re.findall(r'(?:与此同时|另一边|回到|转而|随后)', body)
    if scene_changes:
        report["metrics"]["scene_changes"] = {
            "count": len(scene_changes),
            "indicators": list(set(scene_changes)),
        }
    
    return report


def save_quality_report(project_dir: Path, vol: int, ch: int, report: dict) -> None:
    """保存质量报告到文件"""
    report_file = project_dir / "context" / "quality_reports" / f"vol{vol:02d}_ch{ch:02d}.json"
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def validate_body_file(body_file: Path, project_dir: Path, vol_num: int, ch_num: int) -> BodyValidationResult:
    """从文件校验正文"""
    if not body_file.exists():
        return BodyValidationResult(
            passed=False,
            issues=[BodyValidationIssue("error", f"正文文件不存在: {body_file}")]
        )
    
    body_text = body_file.read_text(encoding="utf-8")
    result = validate_body(body_text, project_dir, vol_num, ch_num)
    
    # 保存质量报告
    if result.quality_report:
        save_quality_report(project_dir, vol_num, ch_num, result.quality_report)
    
    return result
