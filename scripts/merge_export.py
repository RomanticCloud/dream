#!/usr/bin/env python3
"""Merge and export chapter files for dream projects."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


CARD_MARKER = "## 内部工作卡"


def natural_sort_key(path: Path):
    parts = re.split(r"(\d+)", path.name)
    return [int(p) if p.isdigit() else p.lower() for p in parts]


def strip_markdown(text: str) -> str:
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    text = re.sub(r"!\[.*?\]\(.*?\)", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"^\s{0,3}#{1,6}\s?", "", text, flags=re.M)
    for token in ("**", "__", "~~", "`"):
        text = text.replace(token, "")
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


def remove_internal_cards(text: str) -> str:
    if CARD_MARKER in text:
        return text.split(CARD_MARKER, 1)[0].rstrip() + "\n"
    return text


def collect_volume_dirs(project_root: Path, volume: str | None):
    chapters_root = project_root / "chapters"
    if not chapters_root.exists():
        raise FileNotFoundError(f"未找到 chapters 目录: {chapters_root}")

    vol_dirs = [p for p in chapters_root.iterdir() if p.is_dir() and p.name.startswith("vol")]
    vol_dirs = sorted(vol_dirs, key=natural_sort_key)

    if volume:
        vol_dirs = [p for p in vol_dirs if p.name == volume]
        if not vol_dirs:
            raise FileNotFoundError(f"未找到指定卷目录: {volume}")

    return vol_dirs


def collect_chapter_files(project_root: Path, volume: str | None):
    files = []
    for vol_dir in collect_volume_dirs(project_root, volume):
        md_files = [p for p in vol_dir.iterdir() if p.is_file() and p.suffix.lower() == ".md"]
        files.append((vol_dir.name, sorted(md_files, key=natural_sort_key)))
    return files


def build_markdown_output(collected, include_cards: bool, with_volume_title: bool):
    parts = []
    for vol_name, files in collected:
        if with_volume_title:
            parts.append(f"# {vol_name}\n")
        for file_path in files:
            text = file_path.read_text(encoding="utf-8")
            if not include_cards:
                text = remove_internal_cards(text)
            text = text.strip()
            if not text:
                continue
            parts.append(text)
    return "\n\n".join(parts).strip() + "\n"


def build_txt_output(collected, include_cards: bool, with_volume_title: bool):
    parts = []
    for vol_name, files in collected:
        if with_volume_title:
            parts.append(vol_name)
        for file_path in files:
            text = file_path.read_text(encoding="utf-8")
            if not include_cards:
                text = remove_internal_cards(text)
            text = strip_markdown(text)
            if not text.strip():
                continue
            parts.append(f"{file_path.stem}\n\n{text}")
    return "\n\n".join(parts).strip() + "\n"


def default_output_path(project_root: Path, export_format: str, volume: str | None):
    suffix = "md" if export_format == "md" else "txt"
    if volume:
        return project_root / "export" / f"{project_root.name}-{volume}-合并版.{suffix}"
    return project_root / "export" / f"{project_root.name}-合并版.{suffix}"


def parse_args():
    parser = argparse.ArgumentParser(description="合并导出章节正文")
    parser.add_argument("project_dir", help="项目目录")
    parser.add_argument("output", nargs="?", help="输出文件路径（可选）")
    parser.add_argument("--volume", help="只导出指定卷，如 vol01")
    parser.add_argument("--format", choices=["txt", "md"], default="txt", help="导出格式，默认 txt")
    parser.add_argument("--include-cards", action="store_true", help="导出时保留内部工作卡")
    parser.add_argument("--with-volume-title", action="store_true", help="导出时加入卷标题")
    return parser.parse_args()


def main():
    args = parse_args()
    project_root = Path(args.project_dir).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve() if args.output else default_output_path(project_root, args.format, args.volume)

    collected = collect_chapter_files(project_root, args.volume)
    file_count = sum(len(files) for _, files in collected)
    if file_count == 0:
        print("未找到可合并的章节文件")
        sys.exit(2)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if args.format == "md":
        content = build_markdown_output(collected, include_cards=args.include_cards, with_volume_title=args.with_volume_title)
    else:
        content = build_txt_output(collected, include_cards=args.include_cards, with_volume_title=args.with_volume_title)

    output_path.write_text(content, encoding="utf-8")
    print(f"已导出合并文件: {output_path}")
    print(f"导出格式: {args.format}")
    print(f"是否保留内部工作卡: {'是' if args.include_cards else '否'}")
    print(f"共合并章节文件: {file_count}")
    if args.volume:
        print(f"导出范围: {args.volume}")


if __name__ == "__main__":
    main()