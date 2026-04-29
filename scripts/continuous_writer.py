#!/usr/bin/env python3
"""Continuous writing dispatcher for dream."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from body_dispatcher import BodyDispatcher
from chapter_validator import validate_chapter
from common_io import ProjectStateError, load_project_state, require_chapter_word_range, require_locked_protagonist_gender
from generation_state import (
    cleanup_generation_state,
    get_generation_phase,
    load_generation_state,
    save_generation_state,
    update_generation_state,
)
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


def _body_proof_file(project_dir: Path, vol_num: int, ch_num: int) -> Path:
    return project_dir / "context" / f"body_execution_proof_vol{vol_num:02d}_ch{ch_num:02d}.json"


def _validate_body_execution_proof(project_dir: Path, vol_num: int, ch_num: int) -> list[str]:
    request_file = project_dir / "context" / "latest_body_request.json"
    proof_file = _body_proof_file(project_dir, vol_num, ch_num)
    if not request_file.exists():
        return ["缺少 latest_body_request.json，无法证明正文生成读取了上下文"]
    if not proof_file.exists():
        return [f"缺少正文执行证明文件: {proof_file}"]
    try:
        request_payload = json.loads(request_file.read_text(encoding="utf-8"))
        proof = json.loads(proof_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"正文执行证明 JSON 损坏: {exc}"]
    if request_payload.get("vol") != vol_num or request_payload.get("ch") != ch_num:
        return ["latest_body_request.json 与当前卷章不匹配"]
    if proof.get("context_manifest_id") != request_payload.get("context_manifest_id"):
        return ["正文执行证明 context_manifest_id 与请求不一致"]
    files_read = proof.get("files_read")
    if not isinstance(files_read, list) or not files_read:
        return ["正文执行证明缺少 files_read"]
    if request_payload.get("strategy") == "compact_context":
        required = request_payload.get("required_context_files") or []
    else:
        manifest_file = request_payload.get("manifest_file", "")
        if not manifest_file or not Path(manifest_file).exists():
            return ["正文请求缺少可读取的 manifest_file"]
        manifest = json.loads(Path(manifest_file).read_text(encoding="utf-8"))
        required = manifest.get("required_read_sequence") or []
    if set(files_read) != set(required):
        missing = sorted(set(required) - set(files_read))
        return ["正文执行证明 files_read 未覆盖全部必读文件" + (f": {missing[:5]}" if missing else "")]
    return []


def _archive_failed_body(project_dir: Path, body_file: Path, vol_num: int, ch_num: int, reason: str) -> str:
    archive_dir = project_dir / "context" / "failed_bodies"
    archive_dir.mkdir(parents=True, exist_ok=True)
    target = archive_dir / f"vol{vol_num:02d}_ch{ch_num:02d}_{reason}.md"
    if body_file.exists():
        target.write_text(body_file.read_text(encoding="utf-8"), encoding="utf-8")
        body_file.unlink()
    return str(target)


def _fallback_to_full_context(project_dir: Path, vol_num: int, ch_num: int, body_file: Path, issues: list[str]) -> dict:
    gen_state = load_generation_state(project_dir) or {}
    if gen_state.get("context_mode") == "full":
        return _emit("body_failed", vol=vol_num, ch=ch_num, body_file=str(body_file), issues=issues, context_mode="full")
    archived = _archive_failed_body(project_dir, body_file, vol_num, ch_num, "compact_failed")
    update_generation_state(project_dir, {
        "phase": None,
        "context_mode": "full",
        "fallback_reason": issues,
        "archived_failed_body": archived,
    })
    result = _generate_body_phase(project_dir, vol_num, ch_num, context_mode="full")
    result["fallback_from"] = "compact_context"
    result["fallback_reason"] = issues
    result["archived_failed_body"] = archived
    return result


def run(project_dir: Path, task_result_file: str | None = None, mode: str | None = None) -> dict:
    """运行连续写作调度器（子代理模式）
    
    新架构：
    1. 子代理直接写入文件（body/cards）
    2. 主会话只负责路由和状态检测
    3. body完成后自动进入cards，cards完成后返回chapter_ready
    
    Args:
        project_dir: 项目目录
        task_result_file: 子代理返回的结果文件路径（已弃用，保留兼容）
        mode: 运行模式（None=自动检测, body-only=只生成正文, card-only=只生成工作卡）
    """
    # 一次性加载所有状态信息（避免重复 I/O）
    state = load_project_state(project_dir)
    if not state:
        return _emit("missing_state", message="未找到项目状态文件")

    try:
        require_locked_protagonist_gender(state)
        require_chapter_word_range(state)
    except ProjectStateError as exc:
        return _emit("missing_state", message=f"项目配置不完整：{exc}")

    # 缓存 generation_state（避免多次读取同一文件）
    gen_state = load_generation_state(project_dir) or {}
    gen_phase = gen_state.get("phase")

    if task_result_file:
        vol = gen_state.get("current_vol")
        ch = gen_state.get("current_ch")
        if not vol or not ch:
            return _emit("gate_failed", message="缺少当前生成状态，无法消费结果文件")
        if gen_phase == "body_required":
            return _consume_body_result(project_dir, task_result_file, int(vol), int(ch))
        if gen_phase == "cards_required":
            return _consume_cards_result(project_dir, task_result_file, int(vol), int(ch))
        return _emit("gate_failed", message=f"当前阶段 {gen_phase} 不能消费结果文件")
    
    # 缓存进度信息（避免重复计算）
    current_vol, current_ch = get_current_progress(project_dir)
    next_vol, next_ch, _ = get_next_chapter(project_dir)
    chapters_per_volume = get_chapters_per_volume(project_dir)

    # 检查是否有待处理回改
    pending = get_pending_chapter_revision(project_dir)
    if pending:
        chapter_key, payload = pending
        return _emit("gate_failed", revision_key=chapter_key, revision_status=payload.get("status"))

    # 如果指定了模式，优先使用指定模式
    if mode == "body-only":
        return _generate_body_phase(project_dir, next_vol, next_ch)
    elif mode == "card-only":
        vol = gen_state.get("current_vol", 1)
        ch = gen_state.get("current_ch", 1)
        return _generate_card_phase(project_dir, vol, ch)
    
    # 自动检测模式：根据 generation_state 和文件存在性决定下一步
    if gen_phase == "body_required":
        vol = gen_state.get("current_vol", 1)
        ch = gen_state.get("current_ch", 1)
        
        # 检查正文文件是否已由子代理写入
        body_file = chapter_file(project_dir, vol, ch)
        if body_file.exists():
            proof_issues = _validate_body_execution_proof(project_dir, vol, ch)
            if proof_issues:
                return _fallback_to_full_context(project_dir, vol, ch, body_file, proof_issues)
            # 验证正文
            from body_validator import validate_body
            body_text = body_file.read_text(encoding="utf-8")
            validation = validate_body(body_text, project_dir, vol, ch)
            
            if validation.passed:
                # 正文有效，自动进入 body_ready → cards_required
                update_generation_state(project_dir, {
                    "phase": "body_ready",
                    "body_file": str(body_file),
                    "word_count": validation.word_count,
                })
                return _generate_card_phase(project_dir, vol, ch)
            else:
                # compact-context 正文失败后自动升级 full-context 重跑
                return _fallback_to_full_context(project_dir, vol, ch, body_file, [issue.message for issue in validation.issues])
        
        # 正文不存在，返回 body_required（等待子代理生成）
        return _emit(
            "body_required",
            vol=vol, ch=ch,
            prompt_file=gen_state.get("body_prompt_file", ""),
            manifest_file=gen_state.get("manifest_file", ""),
        )
    
    elif gen_phase == "body_ready":
        # 正文已就绪，进入工作卡生成阶段
        vol = gen_state.get("current_vol", 1)
        ch = gen_state.get("current_ch", 1)
        return _generate_card_phase(project_dir, vol, ch)
    
    elif gen_phase == "cards_required":
        vol = gen_state.get("current_vol", 1)
        ch = gen_state.get("current_ch", 1)
        
        # 检查工作卡文件是否已由子代理写入
        card_file = chapter_card_file(project_dir, vol, ch)
        if card_file.exists():
            # 验证完整章节
            validation = validate_chapter(project_dir, vol, ch)
            if validation.passed:
                try:
                    from continuity_ledger import update_ledger_for_chapter
                    from plan_deviation_router import accept_from_facts
                    accept_from_facts(project_dir, vol, ch)
                    update_ledger_for_chapter(project_dir, vol, ch)
                except Exception as exc:
                    return _emit(
                        "cards_failed",
                        vol=vol, ch=ch,
                        issues=[f"连续性账本更新失败: {exc}"],
                    )
                # 章节完成，清理状态
                cleanup_generation_state(project_dir)
                
                # 更新章节索引
                try:
                    from chapter_index import update_chapter_index
                    update_chapter_index(project_dir)
                except Exception as exc:
                    import logging
                    logging.warning(f"章节索引更新失败: {exc}")
                
                return _emit(
                    "chapter_ready",
                    vol=vol, ch=ch,
                    chapter_file=str(chapter_file(project_dir, vol, ch)),
                    card_file=str(card_file),
                )
            else:
                # 验证失败，返回错误
                return _emit(
                    "cards_failed",
                    vol=vol, ch=ch,
                    issues=[issue.message for issue in validation.issues],
                )
        
        # 工作卡不存在，返回 cards_required（等待子代理生成）
        return _emit(
            "cards_required",
            vol=vol, ch=ch,
            prompt_file=gen_state.get("card_prompt_file", ""),
            body_file=gen_state.get("body_file", ""),
        )
    
    # 现有逻辑（检查已完成章节、卷边界等）
    # 使用已缓存的 current_vol, current_ch, next_vol, next_ch
    
    if current_ch == 0:
        # 初始状态，直接进入第一章生成
        return _generate_body_phase(project_dir, 1, 1)
    
    if _chapter_ready(project_dir, current_vol, current_ch):
        validation = validate_chapter(project_dir, current_vol, current_ch)
        if not validation.passed:
            return _emit("gate_failed", vol=current_vol, ch=current_ch, issues=[issue.message for issue in validation.issues])

    # 使用缓存的 chapters_per_volume 检查卷边界，避免重复计算
    if current_ch > 0 and current_ch >= chapters_per_volume:
        volume_revision = get_volume_revision(project_dir, current_vol)
        if volume_revision and volume_revision.get("status") in {"pending_regenerate", "pending_rewrite_card", "pending_polish"}:
            return _emit("volume_ready", vol=current_vol, revision_status=volume_revision.get("status"))
        if volume_memory_md(project_dir, current_vol).exists():
            return _emit("draft_required", vol=next_vol, ch=next_ch, reason="next_volume")
        return _emit("batch_ready", vol=current_vol, ch=current_ch, reason="volume_boundary")

    if _chapter_ready(project_dir, next_vol, next_ch):
        validation = validate_chapter(project_dir, next_vol, next_ch)
        if validation.passed:
            return _emit("chapter_ready", vol=next_vol, ch=next_ch)
        return _emit("gate_failed", vol=next_vol, ch=next_ch, issues=[issue.message for issue in validation.issues])

    # 默认：进入正文生成阶段（新的分离式流程）
    return _generate_body_phase(project_dir, next_vol, next_ch)


def _generate_body_phase(project_dir: Path, vol_num: int, ch_num: int, context_mode: str | None = None) -> dict:
    """Phase A: 生成正文"""
    # 检查当前卷是否有章级规划
    from chapter_plan_loader import check_volume_has_outline
    if not check_volume_has_outline(project_dir, vol_num):
        # 缺少章级规划，返回需要生成的状态
        from chapter_outline_generator import generate_chapter_outline_dispatch
        return generate_chapter_outline_dispatch(project_dir, vol_num)
    
    dispatcher = BodyDispatcher(project_dir)
    if context_mode is None:
        gen_state = load_generation_state(project_dir) or {}
        context_mode = gen_state.get("context_mode") or "fast"
    result = dispatcher.dispatch(vol_num, ch_num, context_mode=context_mode)
    
    if result.status == "error":
        return _emit("body_failed", vol=vol_num, ch=ch_num, error="生成正文prompt失败")

    request_payload = {}
    try:
        request_payload = json.loads(Path(result.request_file).read_text(encoding="utf-8"))
    except Exception:
        request_payload = {}
    
    # 保存生成状态
    save_generation_state(project_dir, {
        "phase": "body_required",
        "current_vol": vol_num,
        "current_ch": ch_num,
        "context_mode": context_mode,
        "body_prompt_file": result.prompt_file,
        "manifest_file": result.manifest_file,
        "context_manifest_id": result.context_manifest_id,
    })
    
    return _emit(
        "body_required",
        vol=vol_num,
        ch=ch_num,
        prompt_file=result.prompt_file,
        request_file=result.request_file,
        manifest_file=result.manifest_file,
        context_manifest_id=result.context_manifest_id,
        body_output=result.body_output,
        project_dir=str(project_dir),
        context_mode=context_mode,
        model=request_payload.get("model", {}),
        model_runner_command=request_payload.get("model_runner_command", ""),
    )


def _consume_body_result(project_dir: Path, result_file: str, vol_num: int, ch_num: int) -> dict:
    """消费正文生成结果"""
    dispatcher = BodyDispatcher(project_dir)
    
    try:
        raw_result = Path(result_file).expanduser().resolve().read_text(encoding="utf-8")
        consumed = dispatcher.consume(vol_num, ch_num, raw_result, validate=True)
    except FileNotFoundError:
        return _emit("body_failed", vol=vol_num, ch=ch_num, error=f"结果文件不存在: {result_file}")
    except Exception as exc:
        import traceback
        return _emit("body_failed", vol=vol_num, ch=ch_num, error=str(exc), traceback=traceback.format_exc())
    
    if consumed.status == "body_ready":
        # 正文校验通过，进入工作卡生成阶段
        update_generation_state(project_dir, {
            "phase": "body_ready",
            "body_file": consumed.body_file,
            "word_count": consumed.word_count,
        })
        
        return _emit(
            "body_ready",
            vol=consumed.vol,
            ch=consumed.ch,
            body_file=consumed.body_file,
            word_count=consumed.word_count,
        )
    else:
        # 正文校验失败
        return _emit(
            "body_failed",
            vol=consumed.vol,
            ch=consumed.ch,
            body_file=consumed.body_file,
            word_count=consumed.word_count,
            issues=consumed.issues,
        )


def _generate_card_phase(project_dir: Path, vol_num: int, ch_num: int) -> dict:
    """Phase B: 生成工作卡"""
    from card_dispatcher import CardDispatcher
    from card_auto_settler import write_auto_card
    
    dispatcher = CardDispatcher(project_dir)
    card_file = chapter_card_file(project_dir, vol_num, ch_num)
    if not card_file.exists():
        try:
            write_auto_card(project_dir, vol_num, ch_num)
            validation = validate_chapter(project_dir, vol_num, ch_num)
            if validation.passed:
                try:
                    from continuity_ledger import update_ledger_for_chapter
                    from plan_deviation_router import accept_from_facts
                    accept_from_facts(project_dir, vol_num, ch_num)
                    update_ledger_for_chapter(project_dir, vol_num, ch_num)
                except Exception as exc:
                    return _emit("cards_failed", vol=vol_num, ch=ch_num, issues=[f"连续性账本更新失败: {exc}"])
                cleanup_generation_state(project_dir)
                try:
                    from chapter_index import update_chapter_index
                    update_chapter_index(project_dir)
                except Exception:
                    pass
                return _emit("chapter_ready", vol=vol_num, ch=ch_num, chapter_file=str(chapter_file(project_dir, vol_num, ch_num)), card_file=str(card_file), auto_card=True)
        except Exception:
            # Fall through to prompt-based card generation.
            pass
    
    # 检查是否有前一次失败的错误信息
    gen_state = load_generation_state(project_dir)
    last_errors = gen_state.get("last_error", [])
    retry_count = gen_state.get("card_retry_count", 0)
    
    result = dispatcher.dispatch(vol_num, ch_num, last_errors=last_errors, retry_count=retry_count)
    
    if result.status == "error":
        return _emit("cards_failed", vol=vol_num, ch=ch_num, error="生成工作卡prompt失败")
    
    # 保存生成状态
    update_generation_state(project_dir, {
        "phase": "cards_required",
        "card_prompt_file": result.prompt_file,
    })
    
    return _emit(
        "cards_required",
        vol=vol_num,
        ch=ch_num,
        prompt_file=result.prompt_file,
        request_file=result.request_file,
        body_file=result.body_file,
        retry_count=retry_count,
    )


def _consume_cards_result(project_dir: Path, result_file: str, vol_num: int, ch_num: int) -> dict:
    """消费工作卡生成结果"""
    from card_dispatcher import CardDispatcher
    
    dispatcher = CardDispatcher(project_dir)
    gen_state = load_generation_state(project_dir) or {}
    
    try:
        raw_result = Path(result_file).expanduser().resolve().read_text(encoding="utf-8")
        consumed = dispatcher.consume(vol_num, ch_num, raw_result, validate=True)
    except FileNotFoundError:
        return _emit("cards_failed", vol=vol_num, ch=ch_num, error=f"结果文件不存在: {result_file}")
    except Exception as exc:
        return _emit("cards_failed", vol=vol_num, ch=ch_num, error=str(exc))
    
    if consumed.status == "chapter_ready":
        # 章节完成，清理状态
        cleanup_generation_state(project_dir)
        
        # 更新章节索引（新章节已生成）
        try:
            from chapter_index import update_chapter_index
            update_chapter_index(project_dir)
        except Exception as exc:
            import logging
            logging.warning(f"章节索引更新失败: {exc}")
        
        return _emit(
            "chapter_ready",
            vol=consumed.vol,
            ch=consumed.ch,
            chapter_file=consumed.chapter_file,
            card_file=consumed.card_file,
        )
    else:
        # 工作卡校验失败
        retry_count = gen_state.get("card_retry_count", 0)
        retry_count += 1
        
        if retry_count <= 3:
            # 自动重试
            update_generation_state(project_dir, {
                "card_retry_count": retry_count,
                "last_error": consumed.issues,
            })
            
            # 重新生成工作卡prompt（包含错误信息）
            return _generate_card_phase(project_dir, vol_num, ch_num)
        else:
            # 3次都失败
            return _emit(
                "cards_failed",
                vol=consumed.vol,
                ch=consumed.ch,
                issues=consumed.issues,
                retry_count=retry_count,
            )


def resume(project_dir: Path) -> dict:
    return run(project_dir)


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="连续写作调度器")
    parser.add_argument("mode", choices=["run", "resume"])
    parser.add_argument("project_dir")
    parser.add_argument("--task-result-file")
    parser.add_argument("--generation-mode", dest="run_mode", choices=["body-only", "card-only", "auto"], default="auto",
                       help="运行模式：body-only=只生成正文, card-only=只生成工作卡, auto=自动检测")
    args = parser.parse_args()

    project_dir = Path(args.project_dir).expanduser().resolve()
    if args.mode == "run":
        result = run(project_dir, args.task_result_file, mode=args.run_mode)
    else:
        result = resume(project_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] not in {"missing_state", "gate_failed", "body_failed", "cards_failed"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
