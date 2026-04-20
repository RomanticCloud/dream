#!/usr/bin/env python3
"""Simple project progress dashboard for dream projects."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from datetime import datetime


def extract_chapter_number(path: Path) -> int | None:
    match = re.match(r"^(\d+)", path.stem)
    return int(match.group(1)) if match else None


def count_chinese_chars(text: str) -> int:
    return len(re.findall(r'[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]', text))


def count_words(text: str) -> int:
    return len(re.sub(r"\s+", "", text))


def analyze_chapter(path: Path) -> dict:
    content = path.read_text(encoding="utf-8")
    return {
        "file": path.name,
        "chinese_chars": count_chinese_chars(content),
        "total_words": count_words(content),
    }


def analyze_project(project_dir: Path) -> dict:
    result = {
        "project_name": project_dir.name,
        "total_chapters": 0,
        "total_chinese_chars": 0,
        "total_words": 0,
        "chapters": [],
    }

    config_file = project_dir / ".project_config.json"
    if config_file.exists():
        try:
            config = json.loads(config_file.read_text(encoding="utf-8"))
            result["project_name"] = config.get("basic_info", {}).get("project_name", project_dir.name)
            result["target_word_count"] = config.get("basic_info", {}).get("target_word_count", 0)
        except Exception:
            pass

    chapters_dir = project_dir / "chapters"
    if not chapters_dir.exists():
        return result

    for vol_dir in sorted(chapters_dir.iterdir()):
        if not vol_dir.is_dir():
            continue
        for chapter_file in sorted(vol_dir.glob("*.md")):
            info = analyze_chapter(chapter_file)
            result["chapters"].append(info)
            result["total_chapters"] += 1
            result["total_chinese_chars"] += info["chinese_chars"]
            result["total_words"] += info["total_words"]

    return result


def print_dashboard(result: dict) -> None:
    print(f"项目: {result['project_name']}")
    print("=" * 40)
    print(f"已完成章节数: {result['total_chapters']}")
    print(f"中文字符数: {result['total_chinese_chars']:,}")
    print(f"总字数: {result['total_words']:,}")

    if result.get("target_word_count"):
        progress = min(100, result["total_words"] / result["target_word_count"] * 100)
        print(f"目标字数: {result['target_word_count']:,}")
        print(f"完成进度: {progress:.1f}%")

    if result["chapters"]:
        print("-" * 40)
        print("章节列表:")
        for ch in result["chapters"][-5:]:
            print(f"  - {ch['file']}: {ch['total_words']:,} 字")


def main():
    parser = argparse.ArgumentParser(description="查看 dream 项目进度")
    parser.add_argument("project_dir", help="项目目录")
    parser.add_argument("--save", action="store_true", help="保存报告到文件")
    args = parser.parse_args()

    project_dir = Path(args.project_dir).expanduser().resolve()
    if not project_dir.exists():
        print(f"项目目录不存在: {project_dir}")
        sys.exit(1)

    result = analyze_project(project_dir)
    print_dashboard(result)

    if args.save:
        report_file = project_dir / "DASHBOARD_REPORT.md"
        content = f"""# {result['project_name']} - 项目进度报告

生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 总体进度

- 已完成章节: {result['total_chapters']} 章
- 中文字符: {result['total_chinese_chars']:,}
- 总字数: {result['total_words']:,}
"""
        if result.get("target_word_count"):
            progress = min(100, result["total_words"] / result["target_word_count"] * 100)
            content += f"- 目标字数: {result['target_word_count']:,}\n- 完成进度: {progress:.1f}%\n"

        content += "\n## 章节列表\n\n"
        for ch in result["chapters"]:
            content += f"- {ch['file']}: {ch['total_words']:,} 字\n"

        report_file.write_text(content, encoding="utf-8")
        print(f"\n报告已保存到: {report_file}")


if __name__ == "__main__":
    main()