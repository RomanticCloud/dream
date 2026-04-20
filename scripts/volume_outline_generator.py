#!/usr/bin/env python3
"""整卷提纲生成器"""

import json
import sys
from pathlib import Path


def load_project_state(project_dir: Path) -> dict:
    state_file = project_dir / "wizard_state.json"
    if state_file.exists():
        return json.loads(state_file.read_text(encoding="utf-8"))

    config_file = project_dir / ".project_config.json"
    if config_file.exists():
        return json.loads(config_file.read_text(encoding="utf-8"))

    return {}


def derive_volume_outline(state: dict) -> str:
    specs = state.get("basic_specs", {})
    positioning = state.get("positioning", {})
    world = state.get("world", {})
    arch = state.get("volume_architecture", {})
    batch = state.get("batch_plan", {})
    naming = state.get("naming", {})

    lines = ["# 卷纲总表", ""]

    lines.append("## 全书概览")
    lines.append(f"- 总字数目标：{specs.get('target_word_count', '待定')}")
    lines.append(f"- 总卷数：{arch.get('volume_count', '待定')}卷")
    lines.append(f"- 单章字数：{specs.get('chapter_length', '待定')}")
    if naming.get('selected_book_title'):
        lines.append(f"- 书名：{naming['selected_book_title']}")
    lines.append("")

    if arch.get('book_escalation_path'):
        lines.append("## 全书抬升路径")
        lines.append(f"- {arch['book_escalation_path']}")
        lines.append("")

    if arch.get('delivery_matrix'):
        lines.append("## 每卷交付承诺")
        lines.append(f"- {arch['delivery_matrix']}")
        lines.append("")

    volume_count = arch.get('volume_count', 8)
    chapters_per_volume = arch.get('chapters_per_volume', 10)

    main_conflicts = positioning.get('main_conflicts', [])
    main_conflict = main_conflicts[0] if main_conflicts else "成长"
    sub_conflict = main_conflicts[1] if len(main_conflicts) > 1 else "升级"

    escalation_path = arch.get('book_escalation_path', '逐步成长')

    first_goal = batch.get('first_volume_goal', '完成首次突破')
    first_hook = batch.get('first_volume_hook', '新挑战出现')

    setting_type = world.get('setting_type', '现代都市')
    society = world.get('society_structure', '帮派势力')

    lines.append(f"## 第1卷 · 初始阶段")
    lines.append(f"- 卷定位：故事开篇，建立主角在{setting_type}中的成长基础")
    lines.append(f"- 卷目标：{first_goal}")
    lines.append(f"- 核心冲突：{main_conflict}、{sub_conflict}")
    lines.append(f"- 卷尾钩子：{first_hook}")
    lines.append(f"- 预估章数：{chapters_per_volume}章")
    lines.append("")

    volume_goals = [
        f"在{society}中获得更大影响力，迎接新挑战",
        f"面对更强大的对手，经历重大挫折后崛起",
        f"突破困境，实力大幅提升，进入更高层次",
        f"面对核心敌人，揭开背后阴谋",
        f"最终决战，完成终极成长与蜕变",
        f"解决最终危机，实现目标",
        f"巩固地位，迎接新的开始",
        f"完善结局，交代所有悬念"
    ]

    for i in range(2, volume_count + 1):
        goal_idx = min(i - 2, len(volume_goals) - 1)
        lines.append(f"## 第{i}卷 · 阶段{i}")
        lines.append(f"- 卷定位：故事推进，冲突升级")
        lines.append(f"- 卷目标：{volume_goals[goal_idx]}")
        lines.append(f"- 核心冲突：{main_conflict}（升级版）、{sub_conflict}")
        lines.append(f"- 卷尾钩子：悬念与挑战")
        lines.append(f"- 预估章数：{chapters_per_volume}章")
        lines.append("")

    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print('用法: volume_outline_generator.py <项目目录>')
        sys.exit(1)

    project_dir = Path(sys.argv[1]).expanduser().resolve()
    if not project_dir.exists():
        print(f"项目目录不存在: {project_dir}")
        sys.exit(1)

    state = load_project_state(project_dir)
    if not state:
        print("未找到项目状态文件")
        sys.exit(1)

    outline = derive_volume_outline(state)

    ref_dir = project_dir / "reference"
    ref_dir.mkdir(exist_ok=True)
    outline_file = ref_dir / "卷纲总表.md"
    outline_file.write_text(outline, encoding="utf-8")

    print(f"卷纲已生成: {outline_file}")
    print(f"\n{outline}")


if __name__ == "__main__":
    main()