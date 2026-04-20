#!/usr/bin/env python3
"""写作流程管理器 - 管理连续写作流程"""

import json
import sys
from pathlib import Path

from card_parser import extract_body
from common_io import load_project_state
from path_rules import volume_memory_md
from progress_rules import get_chapters_per_volume, get_current_progress
from revision_state import get_pending_chapter_revision, get_volume_revision


def get_target_info(state: dict) -> tuple[int, int, int]:
    specs = state.get("basic_specs", {})
    arch = state.get("volume_architecture", {})

    total_volumes = arch.get("volume_count", 8)
    chapters_per_volume = arch.get("chapters_per_volume", 10)
    total_chapters = total_volumes * chapters_per_volume

    word_min = specs.get("chapter_length_min", 3500)
    word_max = specs.get("chapter_length_max", 5500)

    return total_chapters, word_min, word_max


def show_volume_boundary_actions(project_dir: Path, state: dict, current_vol: int) -> bool:
    volume_revision = get_volume_revision(project_dir, current_vol)
    if volume_revision and volume_revision.get("status") in {"pending_regenerate", "pending_polish"}:
        print(f"\n当前卷存在待处理回改：第{current_vol}卷")
        print("可选动作：")
        print(f"  1. 执行回改: python3 scripts/strict_interactive_runner.py volume-revision {project_dir} {current_vol}")
        print(f"  2. 查看报告: {project_dir / 'VOLUME_ENDING_REPORT.md'}")
        print("  3. 暂停")
        return True

    memory_file = volume_memory_md(project_dir, current_vol)
    if memory_file.exists():
        print(f"\n本卷检查已通过：第{current_vol}卷")
        print("可选动作：")
        print(f"  1. 查看卷沉淀: {memory_file}")
        print(f"  2. 开启下一卷: python3 scripts/new_chapter.py {project_dir}")
        print("  3. 暂停")
        return True

    print(f"\n本卷已完成：第{current_vol}卷")
    print("下一步建议：")
    print(f"  1. 卷检查: python3 scripts/volume_ending_checker.py {project_dir} {current_vol}")
    print("  2. 暂停")
    return True


def check_chapter_status(project_dir: Path, vol_num: int, ch_num: int) -> dict:
    vol_name = f"vol{vol_num:02d}"
    chapter_file = project_dir / "chapters" / vol_name / f"{ch_num:03d}_第{ch_num}章.md"

    if not chapter_file.exists():
        return {"status": "not_created", "file": None}

    content = chapter_file.read_text(encoding="utf-8")
    char_count = len(content)
    body = extract_body(content)
    body_word = len(body.replace("在此撰写正文...", "").replace("（", "").replace("）", ""))

    return {
        "status": "completed" if body_word > 100 else "in_progress",
        "char_count": char_count,
        "body_word": body_word,
        "file": chapter_file
    }


def show_status(project_dir: Path, state: dict):
    current_vol, current_ch = get_current_progress(project_dir)
    total_chapters, word_min, word_max = get_target_info(state)

    specs = state.get("basic_specs", {})
    book_title = state.get("naming", {}).get("selected_book_title", "未命名")

    print(f"\n{'='*50}")
    print(f"项目: {book_title}")
    print(f"{'='*50}")
    print(f"当前进度: 第{current_vol}卷 第{current_ch}章")
    print(f"目标进度: 共{total_chapters}章")
    print(f"字数要求: {word_min}-{word_max}字/章")
    print(f"{'='*50}")

    if current_ch > 0:
        status = check_chapter_status(project_dir, current_vol, current_ch)
        if status["status"] == "completed":
            print(f"✓ 第{current_ch}章已完成 ({status['body_word']}字)")
        elif status["status"] == "in_progress":
            print(f"⚠ 第{current_ch}章进行中 ({status['body_word']}字)")


def run_writing_flow(project_dir: Path):
    state = load_project_state(project_dir)
    if not state:
        print("未找到项目状态文件")
        sys.exit(1)

    show_status(project_dir, state)

    pending_chapter = get_pending_chapter_revision(project_dir)
    if pending_chapter:
        chapter_key, payload = pending_chapter
        vol_num = int(chapter_key[3:5])
        ch_num = int(chapter_key.split("_ch", 1)[1])
        print(f"\n当前存在待处理章节回改：{chapter_key}")
        if payload.get("status") == "pending_regenerate":
            print("下一步：整章重写")
        else:
            print("下一步：AI润色")
        print(f"运行: python3 scripts/strict_interactive_runner.py chapter-revision {project_dir} {vol_num} {ch_num}")
        return

    current_vol, current_ch = get_current_progress(project_dir)
    chapters_per_volume = get_chapters_per_volume(project_dir)

    if current_ch == 0:
        print("\n当前没有已完成的章节")
        next_vol = 1
        next_ch = 1
    else:
        status = check_chapter_status(project_dir, current_vol, current_ch)
        if status["status"] == "in_progress":
            print(f"\n当前章节（第{current_ch}章）尚未完成")
            print("请先完成当前章节的撰写")
            return

        if current_ch >= chapters_per_volume:
            if show_volume_boundary_actions(project_dir, state, current_vol):
                return
            next_vol = current_vol + 1
            next_ch = 1
        else:
            next_vol = current_vol
            next_ch = current_ch + 1

    print(f"\n下一步：生成第{next_vol}卷第{next_ch}章")
    print("运行: python3 scripts/new_chapter.py <项目目录>")


def main():
    if len(sys.argv) < 2:
        print("用法: writing_flow.py <项目目录>")
        print("显示当前写作进度和状态")
        sys.exit(1)

    project_dir = Path(sys.argv[1]).expanduser().resolve()
    if not project_dir.exists():
        print(f"项目目录不存在: {project_dir}")
        sys.exit(1)

    run_writing_flow(project_dir)


if __name__ == "__main__":
    main()
