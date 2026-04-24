#!/usr/bin/env python3
"""
卷收尾回改路由器 - volume_revision_router.py
根据严重度评估结果，分流到 整章重生成 或 AI润色
"""
import json
import re
import sys
from pathlib import Path
from typing import Optional

from card_parser import CARD_MARKER, extract_body
from chapter_scan import chapter_file_by_number
from chapter_validator import validate_chapter
from common_io import ProjectStateError, load_project_state, load_volume_outline, require_chapter_word_range
from path_rules import chapter_card_file, polish_prompt_file, regen_prompt_file, rewrite_card_prompt_file
from revision_state import get_chapter_revision, get_volume_revision, mark_chapter_revision_resolved, normalize_revision_payload, normalize_volume_revision_payload, set_chapter_revision, set_volume_revision
from rule_engine import filter_tasks_for_mode, infer_execution_mode, infer_revision_status, sort_revision_tasks, group_revision_tasks
from subagent_chapter_generator import SubagentChapterGenerator


def load_state(project_dir: Path) -> dict:
    return load_project_state(project_dir)


def load_chapter_content(project_dir: Path, vol_num: int, ch_num: int) -> tuple[Optional[str], Optional[Path]]:
    ch_file = chapter_file_by_number(project_dir, vol_num, ch_num)
    if ch_file and ch_file.exists():
        return ch_file.read_text(encoding="utf-8"), ch_file
    return None, None


def load_prev_chapter_carry(project_dir: Path, vol_num: int, ch_num: int) -> dict:
    if ch_num <= 1:
        if vol_num > 1:
            prev_vol = vol_num - 1
            prev_vol_dir = project_dir / "chapters" / f"vol{prev_vol:02d}"
            if prev_vol_dir.exists():
                prev_chs = sorted(prev_vol_dir.glob("*.md"))
                if prev_chs:
                    prev_file = prev_chs[-1]
                    return extract_body(prev_file.read_text(encoding="utf-8"))
        return ""
    vol_name = f"vol{vol_num:02d}"
    prev_file = project_dir / "chapters" / vol_name / f"{ch_num-1:03d}_*.md"
    matches = list(prev_file.parent.glob(prev_file.name.replace("*", "*")))
    if matches:
        return extract_body(matches[0].read_text(encoding="utf-8"))
    return ""


def load_next_chapter_carry(project_dir: Path, vol_num: int, ch_num: int) -> str:
    vol_name = f"vol{vol_num:02d}"
    next_file = project_dir / "chapters" / vol_name / f"{ch_num+1:03d}_*.md"
    matches = list(next_file.parent.glob(next_file.name.replace("*", "*")))
    if matches:
        return extract_body(matches[0].read_text(encoding="utf-8"))
    return ""


def build_regenerate_prompt(
    project_dir: Path,
    vol_num: int,
    ch_num: int,
    original_text: str,
    failure_items: list[dict],
    state: dict
) -> str:
    min_words, max_words = require_chapter_word_range(state)

    book_title = state.get("naming", {}).get("selected_book_title", "未命名")

    vol_outline = load_volume_outline(project_dir, vol_num)

    vol_goal = vol_outline.get("卷目标", "推进故事")
    vol_hook = vol_outline.get("卷钩子", "")

    prev_body = load_prev_chapter_carry(project_dir, vol_num, ch_num)
    next_body = load_next_chapter_carry(project_dir, vol_num, ch_num)

    failure_list = "; ".join([f["name"] + ": " + f["details"] for f in failure_items])

    prompt = f"""# 第{ch_num}章 回改重生成

## 项目信息
- 书名：{book_title}
- 当前卷：第{vol_num}卷
- 目标字数：{min_words}-{max_words}字

## 本章原始信息
{original_text[:2000] if original_text else "(无原始内容)"}

## 必须保留
- 本章既定功能：{vol_goal}
- 结尾结果：（保留原章结尾）
- 伏笔回收点：{vol_hook}

## 承接信息
### 上一章结尾
{prev_body[:500] if prev_body else "(无)"}

### 下一章开头
{next_body[:500] if next_body else "(待承接)"}

## 回改约束
### 上次检查失败项
{failure_list}

### 必须修复
- 以上失败项必须在本章中得到解决
- 保证与前文连续性一致
- 确保伏笔能被正确回收

### 禁止出现
- 上次检查中发现的违禁模式必须消除
- 禁止套用AI模板化描写
- 禁止章节自指词（本章/上章/前文）

---
请根据以上约束重新生成第{ch_num}章正文，保留章节卡结构。
"""

    return prompt


def build_polish_prompt(
    project_dir: Path,
    vol_num: int,
    ch_num: int,
    original_text: str,
    polish_items: list[dict],
    state: dict
) -> str:
    book_title = state.get("naming", {}).get("selected_book_title", "未命名")

    problem_list = "; ".join([f["name"] + ": " + f["details"] for f in polish_items])

    prompt = f"""# 第{ch_num}章 AI润色

## 项目信息
- 书名：{book_title}
- 当前卷：第{vol_num}卷

## 待润色章节
{original_text[:3000]}

## 需要润色的问题
{problem_list}

## 润色要求
- 仅对上述问题进行局部语言润色
- 不改变章节主事件、不改结局
- 不改变伏笔铺设
- 消除违禁模式但保留原意

---
请对章节进行局部润色，保留原章节结构。
"""

    return prompt


def build_rewrite_card_prompt(
    project_dir: Path,
    vol_num: int,
    ch_num: int,
    original_text: str,
    revision_tasks: list[dict],
    state: dict,
) -> str:
    book_title = state.get("naming", {}).get("selected_book_title", "未命名")
    task_lines = []
    for task in revision_tasks[:8]:
        location = " / ".join(part for part in [task.get("card", ""), task.get("field", "")] if part)
        if location:
            task_lines.append(f"- {location}: {task.get('instruction', task.get('message', ''))}")
        else:
            task_lines.append(f"- {task.get('instruction', task.get('message', ''))}")
    problem_list = "\n".join(task_lines) if task_lines else "- 无"

    prompt = f"""# 第{ch_num}章 工作卡重写

## 项目信息
- 书名：{book_title}
- 当前卷：第{vol_num}卷

## 当前章节正文（保持为准）
{original_text[:3000]}

## 本轮必须修复的工作卡问题
{problem_list}

## 执行要求
- 正文尽量保持不变，不要重写主事件
- 只重写 `## 内部工作卡`
- 工作卡必须严格对齐当前正文，不能新增正文未发生的情节
- 优先修复 error，再处理 warning

---
请仅重写本章工作卡，保留正文内容不变。
"""

    return prompt


def run_regenerate(project_dir: Path, vol_num: int, ch_num: int, regenerate_items: list[dict]):
    state = load_state(project_dir)
    original_text, ch_file = load_chapter_content(project_dir, vol_num, ch_num)

    if not original_text or not ch_file:
        print(f"未找到第{ch_num}章内容")
        return False

    prompt = build_regenerate_prompt(project_dir, vol_num, ch_num, original_text, regenerate_items, state)

    prompt_file = regen_prompt_file(project_dir, vol_num, ch_num)
    prompt_file.parent.mkdir(parents=True, exist_ok=True)
    prompt_file.write_text(prompt, encoding="utf-8")
    print(f"重生成提示已保存: {prompt_file}")
    print(f"\n请根据提示重新生成第{ch_num}章，完成后运行验证。")
    return True


def run_polish(project_dir: Path, vol_num: int, ch_num: int, polish_items: list[dict]):
    state = load_state(project_dir)
    original_text, ch_file = load_chapter_content(project_dir, vol_num, ch_num)

    if not original_text:
        print(f"未找到第{ch_num}章内容")
        return False

    prompt = build_polish_prompt(project_dir, vol_num, ch_num, original_text, polish_items, state)

    prompt_file = polish_prompt_file(project_dir, vol_num, ch_num)
    prompt_file.parent.mkdir(parents=True, exist_ok=True)
    prompt_file.write_text(prompt, encoding="utf-8")
    print(f"润色提示已保存: {prompt_file}")
    print(f"\n请根据提示进行局部润色，完成后运行验证。")
    return True


def run_rewrite_card(project_dir: Path, vol_num: int, ch_num: int, revision_tasks: list[dict]):
    state = load_state(project_dir)
    original_text, ch_file = load_chapter_content(project_dir, vol_num, ch_num)

    if not original_text:
        print(f"未找到第{ch_num}章内容")
        return False

    prompt = build_rewrite_card_prompt(project_dir, vol_num, ch_num, original_text, revision_tasks, state)

    prompt_file = rewrite_card_prompt_file(project_dir, vol_num, ch_num)
    prompt_file.parent.mkdir(parents=True, exist_ok=True)
    prompt_file.write_text(prompt, encoding="utf-8")
    print(f"工作卡重写提示已保存: {prompt_file}")
    print(f"\n请根据提示重写工作卡，完成后运行验证。")
    return True


def apply_full_chapter_result(project_dir: Path, vol_num: int, ch_num: int, revised_text: str) -> tuple[bool, str]:
    chapter_path = chapter_file_by_number(project_dir, vol_num, ch_num)
    if not chapter_path:
        return False, "未找到章节文件"
    if "## 正文" not in revised_text or CARD_MARKER not in revised_text:
        return False, "整章结果必须同时包含正文和内部工作卡"
    chapter_path.write_text(revised_text, encoding="utf-8")
    generator = SubagentChapterGenerator(project_dir)
    success = generator.separate_generated_chapter(chapter_path, chapter_path.parent / "cards")
    if not success:
        return False, "整章结果写回后未找到内部工作卡标记，无法分离"
    return True, "整章结果已写回"


def apply_rewrite_card_result(project_dir: Path, vol_num: int, ch_num: int, revised_cards: str) -> tuple[bool, str]:
    if not revised_cards.strip().startswith(CARD_MARKER):
        return False, "工作卡结果必须以 ## 内部工作卡 开头"
    card_path = chapter_card_file(project_dir, vol_num, ch_num)
    card_path.parent.mkdir(parents=True, exist_ok=True)
    card_path.write_text(revised_cards.strip() + "\n", encoding="utf-8")
    return True, "工作卡结果已写回"


def apply_local_patch_result(project_dir: Path, vol_num: int, ch_num: int, revised_text: str) -> tuple[bool, str]:
    if CARD_MARKER in revised_text:
        return apply_full_chapter_result(project_dir, vol_num, ch_num, revised_text)
    return apply_rewrite_card_result(project_dir, vol_num, ch_num, revised_text)


def revalidate_after_revision(project_dir: Path, vol_num: int, ch_num: int):
    result = validate_chapter(project_dir, vol_num, ch_num)
    if result.passed:
        mark_chapter_revision_resolved(project_dir, vol_num, ch_num)
    return result


def print_fix_plan(fix_plan: dict):
    print("\n" + "=" * 50)
    print("回改计划")
    print("=" * 50)

    if fix_plan["total_regenerate"] > 0:
        print(f"\n【需重写】{fix_plan['total_regenerate']}项:")
        for item in fix_plan["regenerate"]:
            print(f"  - {item['name']}: {item['details']}")

    if fix_plan["total_polish"] > 0:
        print(f"\n【需润色】{fix_plan['total_polish']}项:")
        for item in fix_plan["ai_polish"]:
            print(f"  - {item['name']}: {item['details']}")

    if fix_plan["total_regenerate"] == 0 and fix_plan["total_polish"] == 0:
        print("\n无需回改")

    print("=" * 50)


def print_revision_tasks(tasks: list[dict]):
    print("\n" + "=" * 50)
    print("结构化修正任务")
    print("=" * 50)
    if not tasks:
        print("\n无结构化任务")
        print("=" * 50)
        return
    for task in tasks:
        label = f"[{task.get('severity', 'info')}][{task.get('fix_method', 'polish')}]"
        location = " / ".join(part for part in [task.get("card", ""), task.get("field", "")] if part)
        if location:
            print(f"  - {label} {location}: {task.get('instruction', task.get('message', ''))}")
        else:
            print(f"  - {label} {task.get('instruction', task.get('message', ''))}")
    print("=" * 50)

def tasks_to_fix_plan(tasks: list[dict]) -> dict:
    grouped = group_revision_tasks(tasks)
    return {
        "regenerate": [
            {"name": task.get("type", "task"), "details": task.get("instruction", task.get("message", "")), "severity": task.get("severity", "unknown")}
            for task in grouped.get("regenerate", [])
        ],
        "ai_polish": [
            {"name": task.get("type", "task"), "details": task.get("instruction", task.get("message", "")), "severity": task.get("severity", "unknown")}
            for task in grouped.get("polish", [])
        ],
        "total_regenerate": len(grouped.get("regenerate", [])),
        "total_polish": len(grouped.get("polish", [])),
    }


def main():
    if len(sys.argv) < 3:
        print("用法:")
        print("  python3 volume_revision_router.py <project_dir> <vol_num> <ch_num> <fix_plan.json>")
        print("  fix_plan.json: 从 volume_ending_checker.py 获取的 get_fix_plan() 输出")
        sys.exit(1)

    project_dir = Path(sys.argv[1]).resolve()
    vol_num = int(sys.argv[2])
    ch_num = int(sys.argv[3])

    single_mode = "--single" in sys.argv

    if len(sys.argv) > 4 and not sys.argv[4].startswith("--"):
        fix_plan = json.loads(Path(sys.argv[4]).read_text(encoding="utf-8"))
    else:
        from volume_ending_checker import VolumeEndingChecker
        checker = VolumeEndingChecker(project_dir)
        if single_mode:
            fix_plan = checker.get_single_fix_plan(vol_num, ch_num)
        else:
            checker.check(vol_num)
            fix_plan = checker.get_fix_plan()

    revision_payload = normalize_revision_payload(get_chapter_revision(project_dir, vol_num, ch_num))
    volume_payload = normalize_volume_revision_payload(get_volume_revision(project_dir, vol_num))
    revision_tasks = revision_payload.get("tasks", []) or volume_payload.get("tasks", [])
    revision_status = infer_revision_status(revision_tasks, fix_plan)
    grouped_tasks = group_revision_tasks(revision_tasks)
    execution_mode = infer_execution_mode(revision_tasks) if revision_tasks else (
        "full_chapter" if fix_plan.get("total_regenerate", 0) > 0 else "local_patch"
    )
    if revision_tasks:
        task_fix_plan = tasks_to_fix_plan(revision_tasks)
        if task_fix_plan["total_regenerate"] or task_fix_plan["total_polish"]:
            fix_plan = task_fix_plan

    if revision_tasks:
        print_revision_tasks(revision_tasks)
        print(f"\n【自动执行目标】{execution_mode}")
    else:
        print_fix_plan(fix_plan)

    if execution_mode == "work_cards_only" or revision_status == "pending_rewrite_card":
        rewrite_tasks = filter_tasks_for_mode(revision_tasks, "work_cards_only")
        if run_rewrite_card(project_dir, vol_num, ch_num, rewrite_tasks):
            set_chapter_revision(project_dir, vol_num, ch_num, "pending_rewrite_card", fix_plan, revision_tasks)
            set_volume_revision(project_dir, vol_num, "pending_rewrite_card", fix_plan, memory_enriched=False, tasks=revision_tasks)
        return

    if execution_mode == "full_chapter" or grouped_tasks.get("regenerate") or fix_plan["total_regenerate"] > 0:
        regenerate_items = filter_tasks_for_mode(revision_tasks, "full_chapter") if revision_tasks else (grouped_tasks.get("regenerate") or fix_plan["regenerate"])
        if run_regenerate(project_dir, vol_num, ch_num, regenerate_items):
            set_chapter_revision(project_dir, vol_num, ch_num, "pending_regenerate", fix_plan, revision_tasks)
            set_volume_revision(project_dir, vol_num, "pending_regenerate", fix_plan, memory_enriched=False, tasks=revision_tasks)
        return

    if execution_mode == "local_patch" or grouped_tasks.get("polish") or fix_plan["total_polish"] > 0:
        polish_items = filter_tasks_for_mode(revision_tasks, "local_patch") if revision_tasks else (grouped_tasks.get("polish") or fix_plan["ai_polish"])
        if run_polish(project_dir, vol_num, ch_num, polish_items):
            set_chapter_revision(project_dir, vol_num, ch_num, "pending_polish", fix_plan, revision_tasks)
            if not (grouped_tasks.get("regenerate") or fix_plan["total_regenerate"] > 0):
                set_volume_revision(project_dir, vol_num, "pending_polish", fix_plan, memory_enriched=False, tasks=revision_tasks)


if __name__ == "__main__":
    main()
