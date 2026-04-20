#!/usr/bin/env python3
"""Scan current directory and first-level subdirectories for dream projects."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from dataclasses import dataclass


@dataclass
class ProjectInfo:
    name: str
    path: Path
    stage_label: str
    summary: str


def find_dream_projects(root: Path) -> list[ProjectInfo]:
    projects = []
    root = root.resolve()

    for subdir in [root] + list(root.iterdir()):
        if not subdir.is_dir():
            continue
        if subdir.name.startswith("."):
            continue

        config_file = subdir / ".project_config.json"
        if not config_file.exists():
            continue

        try:
            config = json.loads(config_file.read_text(encoding="utf-8"))
            skill_source = config.get("_skill_source", "")
            if skill_source != "dream":
                continue

            project_name = config.get("basic_info", {}).get("project_name", subdir.name)
            stage = config.get("_workflow_stage", "unknown")
            summary = config.get("basic_info", {}).get("summary", "未设置摘要")

            projects.append(ProjectInfo(
                name=project_name,
                path=subdir,
                stage_label=stage,
                summary=summary
            ))
        except (json.JSONDecodeError, KeyError):
            continue

    projects.sort(key=lambda p: p.path.stat().st_mtime, reverse=True)
    return projects


def print_flow_list(projects: list, numbered: bool = False) -> None:
    if not projects:
        print("未在当前目录及其一级子目录中发现 dream 项目。")
        return
    for index, project in enumerate(projects, start=1):
        prefix = f"{index}. " if numbered else ""
        print(f"{prefix}{project.name} · {project.stage_label} · {project.summary}")


def print_table(projects: list, root: Path) -> None:
    if not projects:
        print(f"未在 {root} 及其一级子目录中发现 dream 项目。")
        return
    print(f"在 {root} 及其一级子目录中发现 {len(projects)} 个 dream 项目：")
    for index, project in enumerate(projects, start=1):
        location = project.path.relative_to(root) if project.path != root else Path(".")
        print(f"{index}. {project.name}")
        print(f"   路径: {location}")
        print(f"   阶段: {project.stage_label}")
        print(f"   摘要: {project.summary}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="扫描当前目录及一级子目录中的 dream 项目并汇总阶段"
    )
    parser.add_argument("root", nargs="?", default=".", help="扫描根目录，默认当前目录")
    parser.add_argument(
        "--flow-list",
        action="store_true",
        help="输出 flow 列表格式（项目名 · 阶段标签 · 阶段摘要）",
    )
    parser.add_argument(
        "--numbered-flow-list", action="store_true", help="输出带编号的 flow 列表格式"
    )
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    projects = find_dream_projects(root)

    if args.numbered_flow_list:
        print_flow_list(projects, numbered=True)
    elif args.flow_list:
        print_flow_list(projects, numbered=False)
    else:
        print_table(projects, root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
