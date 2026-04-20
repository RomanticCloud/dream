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

from card_parser import extract_body
from chapter_scan import chapter_file_by_number
from common_io import load_project_state, load_volume_outline
from path_rules import polish_prompt_file, regen_prompt_file
from revision_state import set_chapter_revision, set_volume_revision


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
    specs = state.get("basic_specs", {})
    min_words = specs.get("chapter_length_min", 3500)
    max_words = specs.get("chapter_length_max", 5500)

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


def main():
    if len(sys.argv) < 3:
        print("用法:")
        print("  python3 volume_revision_router.py <project_dir> <vol_num> <ch_num> <fix_plan.json>")
        print("  fix_plan.json: 从 volume_ending_checker.py 获取的 get_fix_plan() 输出")
        sys.exit(1)

    project_dir = Path(sys.argv[1]).resolve()
    vol_num = int(sys.argv[2])
    ch_num = int(sys.argv[3])

    if len(sys.argv) > 4:
        fix_plan = json.loads(Path(sys.argv[4]).read_text(encoding="utf-8"))
    else:
        from volume_ending_checker import VolumeEndingChecker
        checker = VolumeEndingChecker(project_dir)
        results = checker.check(vol_num)
        fix_plan = checker.get_fix_plan()

    print_fix_plan(fix_plan)

    if fix_plan["total_regenerate"] > 0:
        if run_regenerate(project_dir, vol_num, ch_num, fix_plan["regenerate"]):
            set_chapter_revision(project_dir, vol_num, ch_num, "pending_regenerate", fix_plan)
            set_volume_revision(project_dir, vol_num, "pending_regenerate", fix_plan, memory_enriched=False)

    if fix_plan["total_polish"] > 0:
        if run_polish(project_dir, vol_num, ch_num, fix_plan["ai_polish"]):
            set_chapter_revision(project_dir, vol_num, ch_num, "pending_polish", fix_plan)
            if fix_plan["total_regenerate"] == 0:
                set_volume_revision(project_dir, vol_num, "pending_polish", fix_plan, memory_enriched=False)


if __name__ == "__main__":
    main()
