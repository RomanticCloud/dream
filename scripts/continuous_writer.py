#!/usr/bin/env python3
"""Continuous writing dispatcher for dream."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from chapter_validator import validate_chapter
from common_io import ProjectStateError, load_project_state, require_chapter_word_range, require_locked_protagonist_gender
from path_rules import chapter_card_file, chapter_file, volume_memory_md
from progress_rules import get_chapters_per_volume, get_current_progress, get_next_chapter, is_volume_boundary
from revision_state import get_pending_chapter_revision, get_volume_revision
from task_dispatcher import TaskChapterDispatcher, TaskResultError


def _chapter_ready(project_dir: Path, vol_num: int, ch_num: int) -> bool:
    body_file = chapter_file(project_dir, vol_num, ch_num)
    card_file = chapter_card_file(project_dir, vol_num, ch_num)
    return body_file.exists() and card_file.exists()


def _emit(status: str, **extra) -> dict:
    payload = {"status": status}
    payload.update(extra)
    return payload


def run(project_dir: Path, task_result_file: str | None = None) -> dict:
    state = load_project_state(project_dir)
    if not state:
        return _emit("missing_state", message="未找到项目状态文件")

    try:
        require_locked_protagonist_gender(state)
        require_chapter_word_range(state)
    except ProjectStateError as exc:
        return _emit("missing_state", message=f"项目配置不完整：{exc}")

    pending = get_pending_chapter_revision(project_dir)
    if pending:
        chapter_key, payload = pending
        return _emit("gate_failed", revision_key=chapter_key, revision_status=payload.get("status"))

    current_vol, current_ch = get_current_progress(project_dir)

    if task_result_file:
        next_vol, next_ch, _ = get_next_chapter(project_dir)
        dispatcher = TaskChapterDispatcher(project_dir)
        try:
            raw_result = Path(task_result_file).expanduser().resolve().read_text(encoding="utf-8")
            consumed = dispatcher.consume_task_result(next_vol, next_ch, raw_result, validate=True)
        except FileNotFoundError:
            return _emit("gate_failed", error=f"Task 结果文件不存在: {task_result_file}")
        except TaskResultError as exc:
            return _emit("gate_failed", error=str(exc))
        return _emit(
            consumed.status,
            vol=consumed.vol,
            ch=consumed.ch,
            body_output=consumed.body_output,
            card_output=consumed.card_output,
            issues=consumed.issues,
        )
    if current_ch > 0 and _chapter_ready(project_dir, current_vol, current_ch):
        validation = validate_chapter(project_dir, current_vol, current_ch)
        if not validation.passed:
            return _emit("gate_failed", vol=current_vol, ch=current_ch, issues=[issue.message for issue in validation.issues])

    if current_ch > 0 and is_volume_boundary(project_dir):
        volume_revision = get_volume_revision(project_dir, current_vol)
        if volume_revision and volume_revision.get("status") in {"pending_regenerate", "pending_rewrite_card", "pending_polish"}:
            return _emit("volume_ready", vol=current_vol, revision_status=volume_revision.get("status"))
        if volume_memory_md(project_dir, current_vol).exists():
            next_vol, next_ch, _ = get_next_chapter(project_dir)
            return _emit("draft_required", vol=next_vol, ch=next_ch, reason="next_volume")
        return _emit("batch_ready", vol=current_vol, ch=current_ch, reason="volume_boundary")

    next_vol, next_ch, _ = get_next_chapter(project_dir)
    if _chapter_ready(project_dir, next_vol, next_ch):
        validation = validate_chapter(project_dir, next_vol, next_ch)
        if validation.passed:
            return _emit("chapter_ready", vol=next_vol, ch=next_ch)
        return _emit("gate_failed", vol=next_vol, ch=next_ch, issues=[issue.message for issue in validation.issues])

    dispatcher = TaskChapterDispatcher(project_dir)
    result = dispatcher.dispatch(next_vol, next_ch)
    if isinstance(result, dict):
        return _emit("draft_required", vol=next_vol, ch=next_ch, error=result.get("error", "生成请求失败"))
    return _emit(
        "draft_required",
        vol=next_vol,
        ch=next_ch,
        prompt_file=result.prompt_file,
        request_file=result.request_file,
        manifest_file=result.manifest_file,
        context_manifest_id=result.context_manifest_id,
        body_output=result.body_output,
        card_output=result.card_output,
    )


def resume(project_dir: Path) -> dict:
    return run(project_dir)


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="连续写作调度器")
    parser.add_argument("mode", choices=["run", "resume"])
    parser.add_argument("project_dir")
    parser.add_argument("--task-result-file")
    args = parser.parse_args()

    project_dir = Path(args.project_dir).expanduser().resolve()
    if args.mode == "run":
        result = run(project_dir, args.task_result_file)
    else:
        result = resume(project_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] not in {"missing_state", "gate_failed"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
