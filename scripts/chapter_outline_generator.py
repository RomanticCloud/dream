#!/usr/bin/env python3
"""章级规划生成器 - 为每卷生成各章的详细规划"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Optional

from common_io import load_json_file, load_project_state, save_json_file
from path_rules import chapter_outline_file


def load_volume_outline_text(project_dir: Path) -> str:
    """加载卷纲总表文本"""
    outline_file = project_dir / "reference" / "卷纲总表.md"
    if outline_file.exists():
        return outline_file.read_text(encoding="utf-8")
    return ""


def parse_volume_outline(outline_text: str) -> list[dict]:
    """解析卷纲总表，提取每卷信息"""
    volumes = []
    current_volume = None
    
    for line in outline_text.splitlines():
        stripped = line.strip()
        
        # 检测卷标题行: ## 第1卷 · 标题
        if stripped.startswith("## 第") and "·" in stripped:
            if current_volume:
                volumes.append(current_volume)
            
            parts = stripped.replace("## ", "").split("·", 1)
            vol_num_str = parts[0].strip()
            vol_title = parts[1].strip() if len(parts) > 1 else ""
            
            # 提取卷号数字
            vol_num = 0
            for char in vol_num_str:
                if char.isdigit():
                    vol_num = vol_num * 10 + int(char)
            
            current_volume = {
                "vol_num": vol_num,
                "title": vol_title,
                "fields": {},
                "raw_lines": []
            }
        
        # 收集卷的字段
        elif current_volume and stripped.startswith("-"):
            current_volume["raw_lines"].append(stripped)
            if "：" in stripped:
                field_name, field_value = stripped[2:].split("：", 1)
                current_volume["fields"][field_name.strip()] = field_value.strip()
    
    if current_volume:
        volumes.append(current_volume)
    
    return volumes


def build_chapter_outline_prompt(volume_info: dict, project_state: dict, project_dir: Path = None) -> str:
    """构建章级规划生成的 prompt
    
    Args:
        volume_info: 单卷信息（从卷纲总表解析）
        project_state: 项目完整状态
        project_dir: 项目目录（用于动态获取 chapters_per_volume）
        
    Returns:
        用于 LLM 生成章级规划的 prompt 文本
    """
    specs = project_state.get("basic_specs", {})
    protagonist = project_state.get("protagonist", {})
    world = project_state.get("world", {})
    factions = project_state.get("factions", {})
    characters = project_state.get("characters", {})
    positioning = project_state.get("positioning", {})
    
    vol_num = volume_info["vol_num"]
    vol_title = volume_info["title"]
    fields = volume_info["fields"]
    
    # 动态获取 chapters_per_volume，不写死
    if project_dir:
        try:
            chapters_per_volume = get_chapters_per_volume(project_dir)
        except ValueError:
            chapters_per_volume = specs.get("chapters_per_volume", 14)
    else:
        chapters_per_volume = specs.get("chapters_per_volume", 14)
    chapter_length = specs.get("chapter_length", "2000-2500字")
    style_tone = specs.get("style_tone", "轻松幽默")
    
    prompt = f"""你是一位资深的小说架构师。请根据以下小说设定和第{vol_num}卷卷纲，生成该卷全部 {chapters_per_volume} 章的详细章级规划。

## 基础设定
- 书名：{project_state.get("naming", {}).get("selected_book_title", "未命名")}
- 总卷数：{project_state.get("volume_architecture", {}).get("volume_count", 10)}卷
- 每卷章数：{chapters_per_volume}章
- 单章字数：{chapter_length}
- 文风：{style_tone}
- 题材：{", ".join(specs.get("main_genres", []))}
- 叙事视角：{positioning.get("narrative_style", "第三人称有限视角")}

## 主角设定
- 姓名：{protagonist.get("name", "待定")}
- 性别：{protagonist.get("gender", "待定")}
- 年龄段：{protagonist.get("age_group", "待定")}
- 起点身份：{protagonist.get("starting_identity", "待定")}
- 核心性格：{protagonist.get("personality", "待定")}
- 核心欲望：{protagonist.get("core_desire", "待定")}
- 深层恐惧：{protagonist.get("deepest_fear", "待定")}
- 长期目标：{protagonist.get("long_term_goal", "待定")}
- 特殊能力：{protagonist.get("ability", "待定")}

## 第{vol_num}卷卷纲
- 卷标题：{vol_title}
- 卷定位：{fields.get("卷定位", "")}
- 卷目标：{fields.get("卷目标", "")}
- 抬升路径：{fields.get("抬升路径", "")}
- 核心冲突：{fields.get("核心冲突", "")}
- 关键转折：{fields.get("关键转折", "")}
- 卷尾钩子：{fields.get("卷尾钩子", "")}

## 生成要求

1. **每章必须包含以下字段**：
   - 章标题（有吸引力的标题）
   - 核心事件（本章要发生的1-2个关键事件，具体！）
   - 角色状态（本章开始时主角的关键状态）
   - 必须出现（本章必须出场的人物清单）
   - 必须回收（本章必须回收的前文伏笔）
   - 新埋伏笔（本章新埋下的伏笔，为后续章节服务）
   - 悬念强度（1-10的整数，本章结尾的悬念等级）
   - 字数建议（建议字数范围，考虑本章在卷中的位置）

2. **质量要求**：
   - 章与章之间必须有明确的递进关系，不能重复
   - 核心事件要具体，禁止写"故事推进"、"冲突升级"这类空话
   - 每章结尾必须有一个小钩子或悬念，驱动读者读下一章
   - 伏笔回收要指明具体伏笔内容
   - 新埋伏笔要为后续章节服务，不能悬空
   - 最后两章要服务卷尾钩子，做好向下一卷的过渡

3. **叙事节奏**：
   - 前3章：铺垫、建立氛围、引入小冲突
   - 中间章（4-10）：冲突升级、推进主线、角色成长
   - 后4章（11-14）：高潮、卷目标达成、卷尾钩子抛出

4. **角色成长**：
   - 主角每章都要有微小的成长或变化
   - 关系线（如欢喜冤家）要逐步推进，不能原地踏步
   - 能力/地位的提升要有合理的铺垫

## 输出格式

严格使用以下Markdown格式，不要添加任何额外说明：

```markdown
# 第{vol_num}卷章级规划 · {vol_title}

## 第1章 · [有吸引力的章标题]
- 核心事件：...
- 角色状态：...
- 必须出现：...
- 必须回收：...
- 新埋伏笔：...
- 悬念强度：...
- 字数建议：...

## 第2章 · [有吸引力的章标题]
[同上格式]

[重复直到第{chapters_per_volume}章]
```

请直接输出Markdown格式的章级规划，不要有任何前言或后缀。"""

    return prompt


def save_chapter_outline_prompt(project_dir: Path, vol_num: int, prompt_text: str) -> Path:
    """保存章级规划生成prompt到context目录"""
    context_dir = project_dir / "context"
    context_dir.mkdir(exist_ok=True)
    prompt_file = context_dir / f"chapter_outline_prompt_vol{vol_num:02d}.txt"
    prompt_file.write_text(prompt_text, encoding="utf-8")
    return prompt_file


def save_chapter_outline(project_dir: Path, vol_num: int, outline_text: str) -> Path:
    """保存生成的章级规划到reference目录"""
    ref_dir = project_dir / "reference"
    ref_dir.mkdir(exist_ok=True)
    outline_file = chapter_outline_file(project_dir, vol_num)
    outline_file.write_text(outline_text, encoding="utf-8")
    return outline_file


def parse_chapter_outline(outline_text: str, vol_num: int) -> list[dict]:
    """解析章级规划文本为结构化数据
    
    Returns:
        [
            {
                "vol": 1,
                "ch": 1,
                "title": "章标题",
                "core_event": "核心事件",
                "character_state": "角色状态",
                "must_appear": ["人物1", "人物2"],
                "must_payoff": ["伏笔1"],
                "new_setup": ["新伏笔1"],
                "suspense": 5,
                "word_target": "2200",
            },
            ...
        ]
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
            field_name, field_value = stripped[2:].split("：", 1)
            field_name = field_name.strip()
            field_value = field_value.strip()
            
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


def validate_chapter_outline(outline_text: str, expected_chapters: int) -> tuple[bool, list[str]]:
    """验证章级规划质量
    
    Returns:
        (是否有效, 问题列表)
    """
    issues = []
    
    # 检查基本结构
    if f"# 第" not in outline_text or "卷章级规划" not in outline_text:
        issues.append("缺少卷章级规划标题")
    
    # 检查章数
    chapter_headers = [line for line in outline_text.splitlines() if line.strip().startswith("## 第")]
    actual_chapters = len(chapter_headers)
    
    if actual_chapters != expected_chapters:
        issues.append(f"章数不匹配: 期望{expected_chapters}章, 实际{actual_chapters}章")
    
    # 检查每章是否有必需字段
    required_fields = ["核心事件", "角色状态", "必须出现", "悬念强度"]
    
    lines = outline_text.splitlines()
    for i, ch_header in enumerate(chapter_headers):
        ch_num = ch_header.split("·")[0].strip() if "·" in ch_header else ch_header
        # 提取当前章的文本（从当前章标题到下一个章标题或文件末尾）
        ch_start = lines.index(ch_header) if ch_header in lines else -1
        if ch_start == -1:
            continue
        ch_end = len(lines)
        for j in range(ch_start + 1, len(lines)):
            if lines[j].strip().startswith("## 第"):
                ch_end = j
                break
        ch_text = "\n".join(lines[ch_start:ch_end])
        
        for field in required_fields:
            if f"- {field}：" not in ch_text:
                issues.append(f"{ch_num} 缺少'{field}'字段")
    
    # 检查是否有模板化内容
    template_phrases = [
        "故事推进",
        "冲突升级",
        "悬念与挑战",
        "待定",
    ]
    
    for phrase in template_phrases:
        if phrase in outline_text:
            issues.append(f"发现模板化内容: '{phrase}'")
    
    is_valid = len(issues) == 0
    return is_valid, issues


def check_chapter_outline_exists(project_dir: Path, vol_num: int) -> bool:
    """检查指定卷的章级规划是否存在且有效"""
    outline_file = chapter_outline_file(project_dir, vol_num)
    return outline_file.exists() and outline_file.stat().st_size > 100


def generate_chapter_outline_dispatch(project_dir: Path, vol_num: int) -> dict:
    """发起章级规划生成请求
    
    Returns:
        {"status": "chapter_outline_required", "prompt_file": str, "project_dir": str, "vol": int}
    """
    state = load_project_state(project_dir)
    if not state:
        return {"status": "error", "message": "未找到项目状态文件"}
    
    # 加载卷纲
    outline_text = load_volume_outline_text(project_dir)
    if not outline_text:
        return {"status": "error", "message": "未找到卷纲总表"}
    
    volumes = parse_volume_outline(outline_text)
    target_volume = None
    for v in volumes:
        if v["vol_num"] == vol_num:
            target_volume = v
            break
    
    if not target_volume:
        return {"status": "error", "message": f"卷纲总表中未找到第{vol_num}卷"}
    
    # 构建prompt
    prompt = build_chapter_outline_prompt(target_volume, state, project_dir)
    prompt_file = save_chapter_outline_prompt(project_dir, vol_num, prompt)
    
    return {
        "status": "chapter_outline_required",
        "prompt_file": str(prompt_file),
        "project_dir": str(project_dir),
        "vol": vol_num,
        "message": f"需要调用LLM生成第{vol_num}卷章级规划"
    }


def main():
    """命令行入口"""
    if len(sys.argv) < 3:
        print('用法: chapter_outline_generator.py <项目目录> <卷号> [--save <outline_file>]')
        sys.exit(1)
    
    project_dir = Path(sys.argv[1]).expanduser().resolve()
    vol_num = int(sys.argv[2])
    
    if not project_dir.exists():
        print(f"项目目录不存在: {project_dir}")
        sys.exit(1)
    
    # 检查是否有 --save 参数（用于保存子代理生成的结果）
    if "--save" in sys.argv:
        save_idx = sys.argv.index("--save")
        if save_idx + 1 < len(sys.argv):
            outline_file = Path(sys.argv[save_idx + 1])
            if outline_file.exists():
                outline_text = outline_file.read_text(encoding="utf-8")
                
                state = load_project_state(project_dir)
                try:
                    expected = get_chapters_per_volume(project_dir)
                except ValueError:
                    expected = state.get("basic_specs", {}).get("chapters_per_volume", 14)
                
                is_valid, issues = validate_chapter_outline(outline_text, expected)
                
                if is_valid:
                    saved_path = save_chapter_outline(project_dir, vol_num, outline_text)
                    result = {
                        "status": "success",
                        "outline_file": str(saved_path),
                        "chapters": len(parse_chapter_outline(outline_text, vol_num))
                    }
                    print(json.dumps(result, ensure_ascii=False, indent=2))
                    sys.exit(0)
                else:
                    print(json.dumps({
                        "status": "validation_failed",
                        "issues": issues
                    }, ensure_ascii=False, indent=2))
                    sys.exit(1)
    
    # 正常生成流程
    result = generate_chapter_outline_dispatch(project_dir, vol_num)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
