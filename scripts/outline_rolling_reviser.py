#!/usr/bin/env python3
"""卷纲滚动修订器

在每一卷完成后，基于实际写作内容检测与卷纲的偏差，
并生成后续卷的修订建议。

使用方式:
    python3 outline_rolling_reviser.py <项目目录> <已完成卷号>
"""

import json
import sys
from pathlib import Path
from typing import Optional

from card_names import CARRY_CARD, PLOT_CARD
from card_parser import extract_bullets, extract_section
from chapter_scan import chapter_files_in_volume
from common_io import load_project_state, load_volume_outline


def extract_actual_events(project_dir: Path, vol_num: int) -> dict:
    """从已完成卷的工作卡中提取实际发生的关键事件
    
    Returns:
        {
            "key_events": [关键事件列表],
            "turning_points": [转折点列表],
            "character_arc": [主角成长轨迹],
            "final_state": {最终状态},
        }
    """
    events = []
    turning_points = []
    character_changes = []
    final_state = {}
    
    for ch_num, chapter_file in chapter_files_in_volume(project_dir, vol_num):
        # 尝试读取工作卡
        card_file = chapter_file.parent / "cards" / f"{chapter_file.stem}_card.md"
        if not card_file.exists():
            # 尝试内联工作卡
            content = chapter_file.read_text(encoding="utf-8")
            card_text = content
        else:
            card_text = card_file.read_text(encoding="utf-8")
        
        # 提取情节卡
        plot_section = extract_section(card_text, PLOT_CARD)
        if plot_section:
            plot_bullets = extract_bullets(plot_section)
            
            # 关键事件
            if plot_bullets.get("关键事件"):
                events.append({
                    "chapter": ch_num,
                    "event": plot_bullets["关键事件"],
                })
            
            # 转折点
            if plot_bullets.get("转折点"):
                turning_points.append({
                    "chapter": ch_num,
                    "turning": plot_bullets["转折点"],
                })
        
        # 提取状态变化（最后一章）
        carry_section = extract_section(card_text, CARRY_CARD)
        if carry_section:
            carry_bullets = extract_bullets(carry_section)
            if carry_bullets.get("本章留下的最强钩子是什么"):
                final_state["hook"] = carry_bullets["本章留下的最强钩子是什么"]
    
    return {
        "key_events": events,
        "turning_points": turning_points,
        "final_state": final_state,
    }


def detect_major_deviation(outline: dict, actual: dict) -> tuple[bool, list[str], float]:
    """检测重大偏差
    
    Returns:
        (是否有重大偏差, 偏差描述列表, 偏差度0-1)
    """
    deviations = []
    deviation_score = 0.0
    max_score = 0.0
    
    # 1. 检查关键转折是否发生
    outline_turning = outline.get("关键转折", "")
    actual_turning = [t["turning"] for t in actual["turning_points"]]
    
    if outline_turning:
        max_score += 0.3
        # 简单检查：卷纲中的转折点是否在实际中出现
        turning_keywords = set(outline_turning.replace("。", "").replace("，", "").split())
        actual_turning_text = " ".join(actual_turning)
        matched = sum(1 for kw in turning_keywords if kw in actual_turning_text)
        
        if turning_keywords:
            match_rate = matched / len(turning_keywords)
            if match_rate < 0.3:  # 匹配率低于30%视为重大偏差
                deviations.append(
                    f"关键转折偏离：卷纲计划'{outline_turning[:50]}...'，"
                    f"实际发生'{actual_turning_text[:50]}...'"
                )
                deviation_score += 0.3
    
    # 2. 检查抬升路径是否一致
    outline_escalation = outline.get("抬升路径", "")
    actual_events_text = " ".join([e["event"] for e in actual["key_events"]])
    
    if outline_escalation:
        max_score += 0.4
        # 检查抬升路径中的关键词是否在实际事件中出现
        escalation_keywords = set(
            outline_escalation.replace("。", "").replace("，", "").split()
        )
        matched = sum(1 for kw in escalation_keywords if kw in actual_events_text)
        
        if escalation_keywords:
            match_rate = matched / len(escalation_keywords)
            if match_rate < 0.3:
                deviations.append(
                    f"抬升路径偏离：卷纲计划'{outline_escalation[:50]}...'，"
                    f"实际走向'{actual_events_text[:50]}...'"
                )
                deviation_score += 0.4
    
    # 3. 检查卷尾钩子是否一致
    outline_hook = outline.get("卷尾钩子", "")
    actual_hook = actual["final_state"].get("hook", "")
    
    if outline_hook and actual_hook:
        max_score += 0.3
        # 简单比较：是否包含相同的核心悬念词
        hook_keywords = set(outline_hook.replace("。", "").replace("，", "").split())
        matched = sum(1 for kw in hook_keywords if kw in actual_hook)
        
        if hook_keywords:
            match_rate = matched / len(hook_keywords)
            if match_rate < 0.3:
                deviations.append(
                    f"卷尾钩子偏离：卷纲计划'{outline_hook[:50]}...'，"
                    f"实际钩子'{actual_hook[:50]}...'"
                )
                deviation_score += 0.3
    
    # 计算偏差度
    if max_score > 0:
        deviation_degree = deviation_score / max_score
    else:
        deviation_degree = 0.0
    
    has_major_deviation = deviation_degree > 0.5  # 偏差度>50%视为重大偏差
    
    return has_major_deviation, deviations, deviation_degree


def generate_revision_prompt(
    project_dir: Path,
    vol_num: int,
    deviations: list[str],
    actual_events: dict,
) -> str:
    """生成用于修订后续卷纲的 prompt
    
    此 prompt 可以发送给 LLM 生成修订后的卷纲
    """
    state = load_project_state(project_dir)
    outline = load_volume_outline(project_dir, vol_num)
    
    # 读取后续卷的卷纲
    outline_path = project_dir / "reference" / "卷纲总表.md"
    all_outlines = {}
    if outline_path.exists():
        text = outline_path.read_text(encoding="utf-8")
        # 简单解析后续卷
        for i in range(vol_num + 1, 20):  # 最多20卷
            pattern = rf"(?:^##\s+第{i}卷.+?)(?=^##\s+|\Z)"
            import re
            match = re.search(pattern, text, re.M | re.S)
            if match:
                all_outlines[i] = match.group(0)
    
    # 构建 prompt
    prompt = f"""你是一位资深的小说架构师。当前项目的第{vol_num}卷已经完成，但实际写作与卷纲存在偏差，需要修订后续卷的卷纲。

## 当前卷（第{vol_num}卷）的卷纲
- 卷定位：{outline.get('卷定位', '未设定')}
- 卷目标：{outline.get('卷目标', '未设定')}
- 抬升路径：{outline.get('抬升路径', '未设定')}
- 关键转折：{outline.get('关键转折', '未设定')}
- 卷尾钩子：{outline.get('卷尾钩子', '未设定')}

## 实际写作内容
"""
    
    for event in actual_events["key_events"]:
        prompt += f"- 第{event['chapter']}章：{event['event']}\n"
    
    prompt += f"\n## 检测到的偏差\n"
    for dev in deviations:
        prompt += f"- {dev}\n"
    
    if all_outlines:
        prompt += f"\n## 需要修订的后续卷纲\n"
        for vol, text in all_outlines.items():
            prompt += f"\n{text[:500]}...\n"
    
    prompt += f"""
## 修订要求
1. 基于第{vol_num}卷的实际走向，重新规划后续卷的内容
2. 保持全书总卷数和每卷章数不变
3. 确保卷与卷之间的递进关系仍然合理
4. 修订后的卷纲要具体，不能写空话
5. 只输出修订后的卷纲，格式与原始卷纲一致

请直接输出修订后的卷纲（从第{vol_num + 1}卷开始）。
"""
    
    return prompt


def main():
    if len(sys.argv) < 3:
        print("用法: outline_rolling_reviser.py <项目目录> <已完成卷号>")
        sys.exit(1)
    
    project_dir = Path(sys.argv[1]).expanduser().resolve()
    vol_num = int(sys.argv[2])
    
    if not project_dir.exists():
        print(f"项目目录不存在: {project_dir}")
        sys.exit(1)
    
    # 提取实际事件
    actual = extract_actual_events(project_dir, vol_num)
    
    # 加载卷纲
    outline = load_volume_outline(project_dir, vol_num)
    
    if not outline:
        print(f"第{vol_num}卷卷纲不存在，跳过检测")
        sys.exit(0)
    
    # 检测偏差
    has_deviation, deviations, degree = detect_major_deviation(outline, actual)
    
    result = {
        "volume": vol_num,
        "has_major_deviation": has_deviation,
        "deviation_degree": round(degree, 2),
        "deviations": deviations,
    }
    
    if has_deviation:
        # 生成修订 prompt
        revision_prompt = generate_revision_prompt(project_dir, vol_num, deviations, actual)
        prompt_file = project_dir / "context" / f"outline_revision_vol{vol_num}.txt"
        prompt_file.parent.mkdir(exist_ok=True)
        prompt_file.write_text(revision_prompt, encoding="utf-8")
        
        result["revision_prompt_file"] = str(prompt_file)
        result["message"] = f"检测到重大偏差（偏差度{degree:.0%}），建议修订后续卷纲"
    else:
        result["message"] = f"偏差度{degree:.0%}，在可接受范围内，无需修订"
    
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
