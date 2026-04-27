#!/usr/bin/env python3
"""章级规划加载器 - 提供章级规划的读取和查询API"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from path_rules import chapter_outline_file


def load_chapter_outline(project_dir: Path, vol_num: int) -> Optional[str]:
    """加载指定卷的章级规划文本
    
    Args:
        project_dir: 项目目录
        vol_num: 卷号
        
    Returns:
        章级规划文本，如果不存在返回 None
    """
    outline_file = chapter_outline_file(project_dir, vol_num)
    if outline_file.exists():
        return outline_file.read_text(encoding="utf-8")
    return None


def parse_chapter_outline(outline_text: str, vol_num: int) -> list[dict]:
    """解析章级规划文本为结构化章节列表
    
    Args:
        outline_text: 章级规划文本
        vol_num: 卷号
        
    Returns:
        章节列表，每个章节包含规划字段
    """
    chapters = []
    current_chapter = None
    
    for line in outline_text.splitlines():
        stripped = line.strip()
        
        # 检测章标题行: ## 第1章 · 标题
        if stripped.startswith("## 第") and "·" in stripped:
            if current_chapter:
                chapters.append(current_chapter)
            
            parts = stripped.replace("## ", "").split("·", 1)
            ch_num_str = parts[0].strip()
            ch_title = parts[1].strip() if len(parts) > 1 else ""
            
            # 提取章号
            ch_num = 0
            for char in ch_num_str:
                if char.isdigit():
                    ch_num = ch_num * 10 + int(char)
            
            current_chapter = {
                "vol": vol_num,
                "ch": ch_num,
                "title": ch_title,
                "core_event": "",
                "character_state": "",
                "must_appear": [],
                "must_payoff": [],
                "new_setup": [],
                "suspense": 5,
                "word_target": "",
            }
        
        # 解析字段
        elif stripped.startswith("-") and current_chapter and "：" in stripped:
            # 使用 split 处理，支持 "-字段：值" 和 "- 字段：值" 两种格式
            parts = stripped[1:].split("：", 1)
            if len(parts) == 2:
                field_name = parts[0].strip()
                field_value = parts[1].strip()
            else:
                continue
            
            if field_name == "核心事件":
                current_chapter["core_event"] = field_value
            elif field_name == "角色状态":
                current_chapter["character_state"] = field_value
            elif field_name == "必须出现":
                current_chapter["must_appear"] = [s.strip() for s in field_value.split("、") if s.strip()]
            elif field_name == "必须回收":
                current_chapter["must_payoff"] = [s.strip() for s in field_value.split("、") if s.strip()]
            elif field_name == "新埋伏笔":
                current_chapter["new_setup"] = [s.strip() for s in field_value.split("、") if s.strip()]
            elif field_name == "悬念强度":
                try:
                    current_chapter["suspense"] = int(field_value)
                except ValueError:
                    current_chapter["suspense"] = 5
            elif field_name == "字数建议":
                current_chapter["word_target"] = field_value
    
    if current_chapter:
        chapters.append(current_chapter)
    
    return chapters


def load_volume_chapters(project_dir: Path, vol_num: int) -> list[dict]:
    """加载指定卷的全部章节规划
    
    Args:
        project_dir: 项目目录
        vol_num: 卷号
        
    Returns:
        章节规划列表，如果章级规划不存在返回空列表
    """
    outline_text = load_chapter_outline(project_dir, vol_num)
    if not outline_text:
        return []
    
    return parse_chapter_outline(outline_text, vol_num)


def get_chapter_plan(project_dir: Path, vol_num: int, ch_num: int) -> Optional[dict]:
    """获取指定章的规划
    
    Args:
        project_dir: 项目目录
        vol_num: 卷号
        ch_num: 章号
        
    Returns:
        单章规划字典，如果不存在返回 None
    """
    chapters = load_volume_chapters(project_dir, vol_num)
    for ch in chapters:
        if ch["ch"] == ch_num:
            return ch
    return None


def get_all_volume_plans(project_dir: Path) -> dict[int, list[dict]]:
    """获取所有卷的章级规划
    
    Args:
        project_dir: 项目目录
        
    Returns:
        {卷号: [章节规划列表]}
    """
    result = {}
    ref_dir = project_dir / "reference"
    
    if not ref_dir.exists():
        return result
    
    for file in ref_dir.glob("vol*_chapter_outline.md"):
        # 从文件名提取卷号
        vol_str = file.stem.replace("vol", "").replace("_chapter_outline", "")
        try:
            vol_num = int(vol_str)
            chapters = load_volume_chapters(project_dir, vol_num)
            if chapters:
                result[vol_num] = chapters
        except ValueError:
            continue
    
    return result


def check_volume_has_outline(project_dir: Path, vol_num: int) -> bool:
    """检查指定卷是否有有效的章级规划"""
    outline_file = chapter_outline_file(project_dir, vol_num)
    if not outline_file.exists():
        return False
    
    # 检查文件大小（空文件或过小视为无效）
    if outline_file.stat().st_size < 100:
        return False
    
    # 尝试解析，检查是否有章节
    chapters = load_volume_chapters(project_dir, vol_num)
    return len(chapters) > 0


def format_chapter_plan_for_prompt(chapter_plan: dict) -> str:
    """将章节规划格式化为prompt中的约束文本
    
    Args:
        chapter_plan: 单章规划字典
        
    Returns:
        格式化后的约束文本
    """
    if not chapter_plan:
        return ""
    
    lines = [
        f"## 当前章规划（第{chapter_plan['ch']}章 · {chapter_plan['title']}）",
        f"- 核心事件：{chapter_plan['core_event']}",
        f"- 角色状态：{chapter_plan['character_state']}",
    ]
    
    if chapter_plan.get("must_appear"):
        appear_str = "、".join(chapter_plan['must_appear'])
        lines.append(f"- 必须出现：{appear_str}")
    
    if chapter_plan.get("must_payoff"):
        payoff_str = "、".join(chapter_plan['must_payoff'])
        lines.append(f"- 必须回收：{payoff_str}")
    
    if chapter_plan.get("new_setup"):
        setup_str = "、".join(chapter_plan['new_setup'])
        lines.append(f"- 新埋伏笔：{setup_str}")
    
    lines.append(f"- 悬念强度：{chapter_plan['suspense']}")
    
    if chapter_plan.get("word_target"):
        lines.append(f"- 字数建议：{chapter_plan['word_target']}")
    
    return "\n".join(lines)


def main():
    """命令行入口，用于测试"""
    import sys
    import json
    
    if len(sys.argv) < 2:
        print("用法: chapter_plan_loader.py <项目目录> [卷号] [章号]")
        sys.exit(1)
    
    project_dir = Path(sys.argv[1]).expanduser().resolve()
    
    if not project_dir.exists():
        print(f"项目目录不存在: {project_dir}")
        sys.exit(1)
    
    if len(sys.argv) >= 4:
        try:
            vol_num = int(sys.argv[2])
            ch_num = int(sys.argv[3])
        except ValueError as e:
            print(f"参数错误: 卷号和章号必须为整数", file=sys.stderr)
            sys.exit(1)
        plan = get_chapter_plan(project_dir, vol_num, ch_num)
        if plan:
            print(json.dumps(plan, ensure_ascii=False, indent=2))
        else:
            print(f"未找到第{vol_num}卷第{ch_num}章的规划")
    elif len(sys.argv) >= 3:
        try:
            vol_num = int(sys.argv[2])
        except ValueError as e:
            print(f"参数错误: 卷号必须为整数", file=sys.stderr)
            sys.exit(1)
        chapters = load_volume_chapters(project_dir, vol_num)
        print(f"第{vol_num}卷共有 {len(chapters)} 章规划")
        for ch in chapters:
            print(f"  第{ch['ch']}章 · {ch['title']}")
    else:
        all_plans = get_all_volume_plans(project_dir)
        print(f"共找到 {len(all_plans)} 卷的章级规划")
        for vol_num, chapters in sorted(all_plans.items()):
            print(f"  第{vol_num}卷: {len(chapters)} 章")


if __name__ == "__main__":
    main()
