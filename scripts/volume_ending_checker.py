#!/usr/bin/env python3
"""卷收尾检查器 - 使用统一规则引擎执行检查。"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

from chapter_scan import chapter_file_by_number, chapter_files_in_volume, latest_chapter
from card_parser import CARD_MARKER
from check_rules import run_single_chapter_checks, run_volume_checks
from common_io import load_project_state
from path_rules import chapter_card_file
from revision_state import set_volume_revision, update_volume_memory_state
from rule_engine import CheckResult, build_fix_plan, build_revision_tasks_from_check_results, infer_revision_status, passed_count
from volume_state_enricher import enrich_volume_state


class VolumeEndingChecker:
    def __init__(self, project_dir: Path):
        self.project_dir = Path(project_dir).resolve()
        self.results: list[CheckResult] = []

    def _load_state(self) -> dict:
        return load_project_state(self.project_dir)

    def _load_chapters(self, vol_num: int) -> list[tuple[int, str]]:
        chapters = []
        for chapter_num, file_path in chapter_files_in_volume(self.project_dir, vol_num):
            content = file_path.read_text(encoding="utf-8")
            if CARD_MARKER not in content:
                card_candidates = [
                    chapter_card_file(self.project_dir, vol_num, chapter_num),
                    file_path.parent / "cards" / f"{file_path.stem}_card.md",
                ]
                for candidate in card_candidates:
                    if candidate.exists():
                        content = content.rstrip() + "\n\n" + candidate.read_text(encoding="utf-8")
                        break
            chapters.append((chapter_num, content))
        return chapters

    def check(self, vol_num: Optional[int] = None) -> list[CheckResult]:
        if vol_num is None:
            current_vol, current_ch, _ = latest_chapter(self.project_dir)
            if current_ch <= 0:
                print("无卷目录", file=sys.stderr)
                return []
            vol_num = current_vol

        chapters = self._load_chapters(vol_num)
        if not chapters:
            print(f"卷{vol_num}无章节", file=sys.stderr)
            return []

        self.results = run_volume_checks(chapters, self._load_state())
        return self.results

    def check_single_chapter(self, vol_num: int, ch_num: int) -> list[CheckResult]:
        chapter_file = chapter_file_by_number(self.project_dir, vol_num, ch_num)
        if not chapter_file:
            return []
        content = chapter_file.read_text(encoding="utf-8")
        if CARD_MARKER not in content:
            card_candidates = [
                chapter_card_file(self.project_dir, vol_num, ch_num),
                chapter_file.parent / "cards" / f"{chapter_file.stem}_card.md",
            ]
            for candidate in card_candidates:
                if candidate.exists():
                    content = content.rstrip() + "\n\n" + candidate.read_text(encoding="utf-8")
                    break
        self.results = run_single_chapter_checks(ch_num, content, self._load_state())
        return self.results

    def get_fix_plan(self) -> dict:
        return build_fix_plan(self.results)

    def get_single_fix_plan(self, vol_num: int, ch_num: int) -> dict:
        results = self.check_single_chapter(vol_num, ch_num)
        return build_fix_plan(results, include_all=True)

    def generate_report(self) -> str:
        if not self.results:
            return "# 卷收尾检查报告\n\n无检查结果\n"

        passed = passed_count(self.results)
        total = len(self.results)
        lines = [
            "# 卷收尾检查报告",
            "",
            f"**通过率**: {passed}/{total} ({passed * 100 // total}%)",
            "",
        ]
        for result in self.results:
            status = "✅" if result.passed else "❌"
            fix_tag = ""
            if result.fix_method == "regenerate":
                fix_tag = " **[需重写]**"
            elif result.fix_method == "ai_polish":
                fix_tag = " **[需润色]**"
            lines.extend([
                f"## {status} {result.name}{fix_tag}",
                f"**详情**: {result.details}",
                f"**严重度**: {result.severity}" if result.severity != "none" else "",
                f"**影响范围**: {result.scope}" if result.scope != "none" else "",
                f"**修复方式**: {result.fix_method}" if result.fix_method != "none" else "",
                f"**建议**: {result.suggestion}",
                "",
            ])
        return "\n".join(lines)


def print_report(results: list[CheckResult]) -> None:
    if not results:
        print("无检查结果")
        return

    passed = passed_count(results)
    total = len(results)

    print("=" * 50)
    print("卷收尾检查")
    print("=" * 50)
    print(f"\n通过率: {passed}/{total} ({passed * 100 // total}%)")

    for result in results:
        status = "✅" if result.passed else "❌"
        print(f"\n{status} {result.name}")
        print(f"   详情: {result.details}")
        print(f"   建议: {result.suggestion}")

    print("=" * 50)


def main() -> None:
    if len(sys.argv) < 2:
        print("用法: python3 volume_ending_checker.py <project_dir> [vol_num]")
        sys.exit(1)

    project_dir = Path(sys.argv[1]).resolve()
    vol_num = int(sys.argv[2]) if len(sys.argv) > 2 else None

    checker = VolumeEndingChecker(project_dir)
    results = checker.check(vol_num)
    if not results:
        print("无检查结果")
        sys.exit(0)

    print_report(results)

    report_path = project_dir / "VOLUME_ENDING_REPORT.md"
    report_path.write_text(checker.generate_report(), encoding="utf-8")
    print(f"\n报告已保存: {report_path}")

    fix_plan = checker.get_fix_plan()
    volume_tasks = build_revision_tasks_from_check_results(results)
    fix_plan_path = project_dir / "FIX_PLAN.json"
    fix_plan_path.write_text(json.dumps(fix_plan, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"回改计划已保存: {fix_plan_path}")

    if any(not result.passed for result in results):
        if vol_num is None:
            current_vol, current_ch, _ = latest_chapter(project_dir)
            target_vol = current_vol if current_ch > 0 else 0
        else:
            target_vol = vol_num
        if target_vol:
            status = infer_revision_status(volume_tasks, fix_plan)
            set_volume_revision(project_dir, target_vol, status, fix_plan, memory_enriched=False, tasks=volume_tasks)
        sys.exit(1)

    target_vol = vol_num
    if target_vol is None:
        current_vol, current_ch, _ = latest_chapter(project_dir)
        if current_ch > 0:
            target_vol = current_vol

    if target_vol is not None:
        set_volume_revision(project_dir, int(target_vol), "passed", fix_plan, memory_enriched=False, tasks=[])
        volume_memory = enrich_volume_state(project_dir, int(target_vol))
        if volume_memory:
            update_volume_memory_state(project_dir, int(target_vol), memory_enriched=True)
            print(f"卷沉淀已更新: 第{int(target_vol)}卷")
            print(f"动态约束数: {len(volume_memory.get('next_volume_constraints', []))}")


if __name__ == "__main__":
    main()
