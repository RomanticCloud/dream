#!/usr/bin/env python3
"""Simple project health check script for dream projects."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REQUIRED_REFERENCE_FILES = [
    "项目定位.md",
    "核心卖点与主承诺.md",
    "世界观与设定.md",
    "角色关系表.md",
    "主角成长路线.md",
    "卷纲总表.md",
]


def check_project_config(project_dir: Path) -> tuple[list, list]:
    errors = []
    warnings = []

    config_file = project_dir / ".project_config.json"
    if not config_file.exists():
        errors.append(f"缺少配置文件: {config_file}")
    else:
        try:
            config = json.loads(config_file.read_text(encoding="utf-8"))
            if "basic_info" not in config:
                warnings.append("配置文件缺少 basic_info 字段")
            if config.get("_skill_source") != "dream":
                warnings.append(f"项目来源标记不是 dream: {config.get('_skill_source')}")
        except json.JSONDecodeError as e:
            errors.append(f"配置文件格式错误: {e}")

    lock_file = project_dir / ".workflow_lock.json"
    if not lock_file.exists():
        warnings.append("未找到工作流锁定文件")

    return errors, warnings


def check_reference_files(project_dir: Path) -> tuple[list, list]:
    errors = []
    warnings = []

    reference_dir = project_dir / "reference"
    if not reference_dir.exists():
        errors.append(f"缺少 reference 目录: {reference_dir}")
        return errors, warnings

    for filename in REQUIRED_REFERENCE_FILES:
        path = reference_dir / filename
        if not path.exists():
            errors.append(f"缺少参考文件: {filename}")
        elif path.stat().st_size < 50:
            warnings.append(f"参考文件内容过少: {filename}")

    return errors, warnings


def check_chapters(project_dir: Path) -> tuple[list, list]:
    errors = []
    warnings = []

    chapters_dir = project_dir / "chapters"
    if not chapters_dir.exists():
        warnings.append("未找到 chapters 目录")
        return errors, warnings

    chapter_files = list(chapters_dir.rglob("*.md"))
    if not chapter_files:
        warnings.append("未找到任何章节文件")

    for chapter_file in chapter_files:
        if chapter_file.stat().st_size < 100:
            warnings.append(f"章节内容过少: {chapter_file.name}")

    return errors, warnings


def validate_project(project_dir: Path) -> int:
    project_dir = project_dir.resolve()

    if not project_dir.exists():
        print(f"项目目录不存在: {project_dir}")
        return 1

    print(f"检查项目: {project_dir.name}")
    print("-" * 40)

    all_errors = []
    all_warnings = []

    errors, warnings = check_project_config(project_dir)
    all_errors.extend(errors)
    all_warnings.extend(warnings)

    errors, warnings = check_reference_files(project_dir)
    all_errors.extend(errors)
    all_warnings.extend(warnings)

    errors, warnings = check_chapters(project_dir)
    all_errors.extend(errors)
    all_warnings.extend(warnings)

    if all_errors:
        print("错误:")
        for e in all_errors:
            print(f"  ✗ {e}")

    if all_warnings:
        print("警告:")
        for w in all_warnings:
            print(f"  ⚠ {w}")

    if not all_errors and not all_warnings:
        print("✓ 项目检查通过")

    print("-" * 40)
    return 0 if not all_errors else 1


def main():
    parser = argparse.ArgumentParser(description="检查 dream 项目健康状态")
    parser.add_argument("project_dir", help="项目目录")
    args = parser.parse_args()

    project_dir = Path(args.project_dir).expanduser().resolve()
    sys.exit(validate_project(project_dir))


if __name__ == "__main__":
    main()