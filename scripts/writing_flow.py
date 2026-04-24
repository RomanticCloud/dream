#!/usr/bin/env python3
"""写作流程管理器 - 管理连续写作流程"""

import json
import subprocess
import sys
from pathlib import Path

from card_parser import extract_body
from common_io import ProjectStateError, find_chapter_path, load_json_file, load_project_state, require_chapter_word_range, require_locked_protagonist_gender, save_json_file
from enhanced_validator import EnhancedValidator
from narrative_context import NarrativeContext
from path_rules import chapter_file, volume_memory_md
from progress_rules import get_chapters_per_volume, get_current_progress
from revision_state import get_pending_chapter_revision, get_volume_revision
from state_tracker import StateTracker


def get_target_info(state: dict) -> tuple[int, int, int]:
    specs = state.get("basic_specs", {})
    arch = state.get("volume_architecture", {})

    total_volumes = arch.get("volume_count", 8)
    chapters_per_volume = arch.get("chapters_per_volume", 10)
    total_chapters = total_volumes * chapters_per_volume

    word_min, word_max = require_chapter_word_range(state)

    return total_chapters, word_min, word_max


def show_volume_boundary_actions(project_dir: Path, state: dict, current_vol: int) -> bool:
    volume_revision = get_volume_revision(project_dir, current_vol)
    if volume_revision and volume_revision.get("status") in {"pending_regenerate", "pending_rewrite_card", "pending_polish"}:
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
    chapter_path = chapter_file(project_dir, vol_num, ch_num)

    if not chapter_path.exists():
        return {"status": "not_created", "file": None}

    content = chapter_path.read_text(encoding="utf-8")
    char_count = len(content)
    body = extract_body(content)
    body_word = len(body.replace("在此撰写正文...", "").replace("（", "").replace("）", ""))

    return {
        "status": "completed" if body_word > 100 else "in_progress",
        "char_count": char_count,
        "body_word": body_word,
        "file": chapter_path
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

    try:
        require_locked_protagonist_gender(state)
        require_chapter_word_range(state)
    except ProjectStateError as exc:
        print(f"项目配置不完整：{exc}")
        sys.exit(1)

    show_status(project_dir, state)

    dispatcher_script = Path(__file__).resolve().parent / "continuous_writer.py"
    dispatch = subprocess.run(
        [sys.executable, str(dispatcher_script), "run", str(project_dir)],
        capture_output=True,
        text=True,
        check=False,
    )
    if dispatch.stdout.strip():
        print("\n连续写作调度：")
        print(dispatch.stdout.strip())
        return

    pending_chapter = get_pending_chapter_revision(project_dir)
    if pending_chapter:
        chapter_key, payload = pending_chapter
        vol_num = int(chapter_key[3:5])
        ch_num = int(chapter_key.split("_ch", 1)[1])
        print(f"\n当前存在待处理章节回改：{chapter_key}")
        if payload.get("status") == "pending_regenerate":
            print("下一步：整章重写")
        elif payload.get("status") == "pending_rewrite_card":
            print("下一步：重写工作卡")
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

        if status["status"] == "completed" and status.get("file"):
            result = on_chapter_completed(project_dir, status["file"], current_ch)
            if result["status"] == "drift_detected":
                print(f"\n⚠ 检测到第{current_ch}章存在一致性问题：")
                for issue in result["issues"]:
                    print(f"  - {issue.message}")
                print("建议检查后继续")

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


def log_drift_issues(project_dir: Path, chapter_num: int, issues: list):
    """记录漂移问题到 drift_log.json"""
    from datetime import datetime

    drift_log_file = project_dir / "context" / "drift_log.json"

    # 加载现有日志
    if drift_log_file.exists():
        drift_log = load_json_file(drift_log_file)
    else:
        drift_log = {"entries": []}

    # 添加新条目
    drift_log["entries"].append({
        "chapter": chapter_num,
        "timestamp": datetime.now().isoformat(),
        "issues": [
            {
                "severity": issue.severity,
                "message": issue.message,
                "suggestion": issue.suggestion
            }
            for issue in issues
        ]
    })

    # 保存
    save_json_file(drift_log_file, drift_log)


def on_chapter_completed(project_dir: Path, chapter_path: Path, chapter_num: int) -> dict:
    """章节完成后的处理

    1. 提取场景锚点
    2. 生成叙事摘要
    3. 更新状态跟踪器
    4. 执行跨章一致性验证

    Returns:
        {"status": "success"} 或 {"status": "drift_detected", "issues": [...]}
    """
    try:
        # 1. 提取场景锚点
        narrative_ctx = NarrativeContext(project_dir)
        scene_anchor = narrative_ctx.extract_scene_anchor(chapter_path)
        narrative_summary = narrative_ctx.generate_narrative_summary(chapter_path)

        # 2. 保存章节上下文
        narrative_ctx.save_chapter_context(chapter_num, {
            "scene_anchor": scene_anchor,
            "narrative_summary": narrative_summary
        })

        # 3. 更新状态跟踪器
        state_tracker = StateTracker(project_dir)
        state_tracker.update_character_state(chapter_path)
        state_tracker.track_plot_threads(chapter_path)
        state_tracker.track_foreshadowing(chapter_path)
        state_tracker.update_last_chapter(chapter_num)

        # 4. 跨章一致性验证（如果有上一章）
        if chapter_num > 1:
            prev_chapter_path = find_chapter_path(project_dir, chapter_num - 1)
            if prev_chapter_path:
                validator = EnhancedValidator(project_dir)
                issues = validator.validate_cross_chapter_consistency(chapter_path, prev_chapter_path)

                if issues:
                    # 记录漂移问题
                    log_drift_issues(project_dir, chapter_num, issues)

                    # 如果有严重问题，返回警告
                    critical_issues = [i for i in issues if i.severity == "error"]
                    if critical_issues:
                        return {
                            "status": "drift_detected",
                            "issues": critical_issues,
                            "chapter_num": chapter_num
                        }

        return {"status": "success"}
    except Exception as e:
        # 记录错误但不中断写作流程
        print(f"警告: 章节完成处理时出错 (章节 {chapter_num}): {e}")
        return {"status": "success", "warning": str(e)}


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
