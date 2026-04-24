#!/usr/bin/env python3
"""Emit strict interactive Question payloads for the dream skill."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

from common_io import load_project_state
from path_rules import volume_memory_json
from progress_rules import get_chapters_per_volume, get_current_progress, is_volume_boundary
from revision_state import get_pending_chapter_revision, get_volume_revision, get_volume_revision_status

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


FIXED_MENUS = {
    "init": {
        "question": "请选择当前要进入的分支：",
        "header": "顶层分支",
        "multiple": False,
        "options": [
            {"label": "新建项目", "description": "从零开始设定并建立新的创意写作项目"},
            {"label": "继续已有项目", "description": "扫描并继续一个已存在的创意写作项目"},
            {"label": "仅规划", "description": "只产出设定和卷章规划，不初始化正式项目"},
            {"label": "退出", "description": "立即结束本次流程"},
        ],
    },
    "action-menu": {
        "question": "请选择当前项目动作：",
        "header": "项目动作",
        "multiple": False,
        "options": [
            {"label": "继续写作", "description": "持续推进正文直到完结或中止"},
            {"label": "本批检查", "description": "检查当前批次连续性与逻辑一致性"},
            {"label": "本卷收尾", "description": "推进到本卷交付与卷尾钩子"},
            {"label": "导出归档", "description": "导出当前项目归档结果"},
            {"label": "结束", "description": "结束当前工作流"},
        ],
    },
    "volume-ending": {
        "question": "本卷已完成，请选择下一步动作：",
        "header": "卷结束动作",
        "multiple": False,
        "options": [
            {"label": "卷检查", "description": "运行卷收尾检查（连续性、伏笔回收、逻辑、AI感、时间线、章节自指）"},
            {"label": "开启下一卷", "description": "继续下一卷第一章"},
            {"label": "暂停", "description": "暂停等待，稍后继续"},
        ],
    },
    "volume-passed": {
        "question": "本卷检查已通过，请选择下一步动作：",
        "header": "卷通过后动作",
        "multiple": False,
        "options": [
            {"label": "查看卷沉淀", "description": "查看本卷沉淀设定与动态约束"},
            {"label": "开启下一卷", "description": "继续下一卷第一章"},
            {"label": "暂停", "description": "暂停等待，稍后继续"},
        ],
    },
    "chapter-revision-menu": {
        "question": "当前章节存在待处理回改，请选择下一步动作：",
        "header": "章节回改动作",
        "multiple": False,
        "options": [
            {"label": "整章重写", "description": "根据高严重度问题生成整章重写提示"},
            {"label": "重写工作卡", "description": "根据字段问题重写内部工作卡并对齐正文"},
            {"label": "AI润色", "description": "根据低严重度问题生成局部润色提示"},
            {"label": "暂停", "description": "暂停等待，稍后继续"},
        ],
    },
    "volume-revision-menu": {
        "question": "当前卷存在待处理回改，请选择下一步动作：",
        "header": "卷回改动作",
        "multiple": False,
        "options": [
            {"label": "执行回改", "description": "生成整章重写或AI润色提示"},
            {"label": "查看报告", "description": "查看当前卷检查报告"},
            {"label": "暂停", "description": "暂停等待，稍后继续"},
        ],
    },
    "final-menu": {
        "question": "请选择完结后动作：",
        "header": "后处理动作",
        "multiple": False,
        "options": [
            {"label": "扩写补字数", "description": "扩写章节或卷内容以补足字数"},
            {"label": "增加番外", "description": "补充番外篇章"},
            {"label": "精修润色", "description": "精修正文语言和节奏"},
            {"label": "修改设定", "description": "调整设定并同步到项目材料"},
            {"label": "审阅导出", "description": "审阅后导出最终文本"},
            {"label": "结束", "description": "结束当前工作流"},
        ],
    },
}


def _candidate_project_dirs(base_dir: Path) -> list[Path]:
    candidates: list[Path] = []
    if base_dir.is_file():
        base_dir = base_dir.parent
    if not base_dir.exists():
        return []
    for child in sorted(base_dir.iterdir()):
        if not child.is_dir():
            continue
        if (child / "wizard_state.json").exists() or (child / ".project_config.json").exists():
            candidates.append(child)
    return candidates


def _emit_state_menu(question: str, header: str, options: list[dict], multiple: bool = False) -> int:
    print(json.dumps({
        "question": question,
        "header": header,
        "multiple": multiple,
        "options": options,
    }, ensure_ascii=False, indent=2))
    return 0


def _has_volume_memory(project_dir: Path) -> bool:
    current_vol, current_ch = get_current_progress(project_dir)
    if current_vol <= 0 or current_ch <= 0:
        return False
    memory_file = volume_memory_json(project_dir, current_vol)
    return memory_file.exists()


def _usage() -> int:
    print("用法:")
    print("  python3 scripts/strict_interactive_runner.py init")
    print("  python3 scripts/strict_interactive_runner.py action-menu [project_dir]")
    print("  python3 scripts/strict_interactive_runner.py volume-ending-check <project_dir> [vol_num]")
    print("  python3 scripts/strict_interactive_runner.py volume-revision <project_dir> [vol_num]")
    print("  python3 scripts/strict_interactive_runner.py chapter-revision <project_dir> <vol_num> <ch_num>")
    print("  python3 scripts/strict_interactive_runner.py final-menu")
    print("  python3 scripts/strict_interactive_runner.py state <wizard_state.json|project_dir> <preset-key> [limit]")
    return 1


def _get_vol_num(project_dir: Path) -> Optional[int]:
    current_vol, current_ch = get_current_progress(project_dir)
    if current_ch <= 0:
        return None
    return current_vol


def main() -> int:
    if len(sys.argv) < 2:
        return _usage()

    mode = sys.argv[1]

    if mode == "action-menu" and len(sys.argv) >= 3:
        project_dir = Path(sys.argv[2])
        pending_chapter = get_pending_chapter_revision(project_dir)
        if pending_chapter:
            print(json.dumps(FIXED_MENUS["chapter-revision-menu"], ensure_ascii=False, indent=2))
            return 0
        if is_volume_boundary(project_dir):
            current_vol = _get_vol_num(project_dir)
            if current_vol is not None:
                volume_revision = get_volume_revision(project_dir, current_vol)
                if volume_revision and volume_revision.get("status") in {"pending_regenerate", "pending_rewrite_card", "pending_polish"}:
                    print(json.dumps(FIXED_MENUS["volume-revision-menu"], ensure_ascii=False, indent=2))
                    return 0
            if _has_volume_memory(project_dir):
                print(json.dumps(FIXED_MENUS["volume-passed"], ensure_ascii=False, indent=2))
                return 0
            print(json.dumps(FIXED_MENUS["volume-ending"], ensure_ascii=False, indent=2))
            return 0

    if mode == "volume-ending-check" and len(sys.argv) >= 3:
        import subprocess
        project_dir = Path(sys.argv[2])
        vol_num = int(sys.argv[3]) if len(sys.argv) > 3 else _get_vol_num(project_dir)
        checker_script = SCRIPT_DIR / "volume_ending_checker.py"
        if checker_script.exists():
            cmd = [sys.executable, str(checker_script), str(project_dir)]
            if vol_num:
                cmd.append(str(vol_num))
            subprocess.run(cmd)
            return 0
        else:
            print(json.dumps({"error": "volume_ending_checker.py not found"}, ensure_ascii=False, indent=2))
            return 1

    if mode == "volume-revision" and len(sys.argv) >= 3:
        import subprocess
        project_dir = Path(sys.argv[2])
        vol_num = int(sys.argv[3]) if len(sys.argv) > 3 else _get_vol_num(project_dir)
        status = get_volume_revision_status(project_dir, vol_num) if vol_num else None
        fix_plan_path = project_dir / "FIX_PLAN.json"
        if not status and not fix_plan_path.exists():
            print(json.dumps({"error": "FIX_PLAN.json not found"}, ensure_ascii=False, indent=2))
            return 1
        chapter_file = project_dir / "chapters" / f"vol{vol_num:02d}"
        ch_num = 1
        if chapter_file.exists():
            ch_files = sorted(chapter_file.glob("*.md"))
            if ch_files:
                import re
                m = re.match(r"(\d+)", ch_files[0].stem)
                ch_num = int(m.group(1)) if m else 1
        router_script = SCRIPT_DIR / "volume_revision_router.py"
        if router_script.exists():
            cmd = [sys.executable, str(router_script), str(project_dir), str(vol_num), str(ch_num)]
            if fix_plan_path.exists():
                cmd.append(str(fix_plan_path))
            subprocess.run(cmd)
            return 0
        else:
            print(json.dumps({"error": "volume_revision_router.py not found"}, ensure_ascii=False, indent=2))
            return 1

    if mode == "chapter-revision" and len(sys.argv) >= 4:
        import subprocess
        project_dir = Path(sys.argv[2])
        vol_num = int(sys.argv[3])
        ch_num = int(sys.argv[4])
        pending = get_pending_chapter_revision(project_dir)
        fix_plan_path = project_dir / "CHAPTER_FIX_PLAN.json"
        if not pending and not fix_plan_path.exists():
            print(json.dumps({"error": "CHAPTER_FIX_PLAN.json not found"}, ensure_ascii=False, indent=2))
            return 1
        router_script = SCRIPT_DIR / "volume_revision_router.py"
        if router_script.exists():
            cmd = [sys.executable, str(router_script), str(project_dir), str(vol_num), str(ch_num)]
            if fix_plan_path.exists():
                cmd.append(str(fix_plan_path))
            cmd.append("--single")
            subprocess.run(cmd)
            return 0
        else:
            print(json.dumps({"error": "volume_revision_router.py not found"}, ensure_ascii=False, indent=2))
            return 1

    if mode in FIXED_MENUS:
        print(json.dumps(FIXED_MENUS[mode], ensure_ascii=False, indent=2))
        return 0

    if mode == "state":
        if len(sys.argv) < 4:
            return _usage()
        target = Path(sys.argv[2]).expanduser().resolve()
        preset_key = sys.argv[3]
        limit = int(sys.argv[4]) if len(sys.argv) > 4 and sys.argv[4].isdigit() else 4

        if preset_key == "resume-projects":
            candidates = _candidate_project_dirs(target)[:limit]
            if not candidates:
                return _emit_state_menu("未发现可继续的项目。", "继续项目", [])
            return _emit_state_menu(
                "请选择要继续的项目：",
                "继续项目",
                [{"label": candidate.name, "description": str(candidate)} for candidate in candidates],
            )

        if preset_key == "next-action":
            project_dir = target if target.is_dir() else target.parent
            pending_chapter = get_pending_chapter_revision(project_dir)
            if pending_chapter:
                return _emit_state_menu(**FIXED_MENUS["chapter-revision-menu"])
            if is_volume_boundary(project_dir):
                current_vol = _get_vol_num(project_dir)
                if current_vol is not None and _has_volume_memory(project_dir):
                    return _emit_state_menu(**FIXED_MENUS["volume-passed"])
                return _emit_state_menu(**FIXED_MENUS["volume-ending"])
            return _emit_state_menu(**FIXED_MENUS["action-menu"])

        return _emit_state_menu("该状态预设暂未实现", "状态查询", [])

    return _usage()


if __name__ == "__main__":
    raise SystemExit(main())
