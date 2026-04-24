#!/usr/bin/env python3
"""State-driven project initialization wizard for the dream skill."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from planning_rules import describe_target_profile, volume_label
from state_builders import (
    WORD_TARGET_OPTIONS,
    CHAPTER_LENGTH_OPTIONS,
    PACING_OPTIONS,
    STYLE_TONE_OPTIONS,
    MAIN_GENRE_OPTIONS,
    SUB_GENRE_OPTIONS,
    NARRATIVE_STYLE_OPTIONS,
    SETTING_OPTIONS,
    SOCIETY_OPTIONS,
    ADVENTURE_OPTIONS,
    CRISIS_OPTIONS,
    ROMANCE_OPTIONS,
    RELATIONSHIP_OPTIONS,
    ANTAGONIST_OPTIONS,
    ANTAGONIST_CURVE_OPTIONS,
    CONFLICT_LEVEL_OPTIONS,
    TENSION_OPTIONS,
    BATCH_SIZE_OPTIONS,
    GENDER_OPTIONS,
    AGE_GROUP_OPTIONS,
    PERSONALITY_OPTIONS,
    CORE_DESIRE_EXAMPLES,
    DEEPEST_FEAR_EXAMPLES,
    POWER_SYSTEM_OPTIONS,
    BREAKTHROUGH_OPTIONS,
    LIMITATION_OPTIONS,
    get_conflict_options,
    get_reader_hook_options,
    get_scene_options,
    get_escalation_path_options,
    get_delivery_options,
    get_first_volume_goal_options,
    get_first_volume_hook_options,
    generate_book_title_options,
    default_positioning_values,
    build_basic_specs,
    build_positioning,
    build_world,
    build_characters,
    build_volume_architecture,
    build_batch_plan,
    build_naming,
    build_protagonist,
    build_power_system,
    build_factions,
)
from common_io import ProjectStateError, require_chapter_word_range, require_locked_protagonist_gender

STATE_FILENAME = "wizard_state.json"
POWER_GENRES = {"都市高武", "玄幻奇幻", "仙侠修真"}


def validate_final_state_requirements(state: dict) -> None:
    """Fail fast when required locked fields are missing before initialization completes."""
    require_chapter_word_range(state)
    require_locked_protagonist_gender(state)


def persist_wizard_state(base_dir: Path, state: dict) -> None:
    state_file = base_dir / STATE_FILENAME
    state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def input_with_default(
    prompt: str,
    default: str = "",
    state_value: str | None = None,
) -> str:
    current = state_value if state_value not in (None, "") else default
    if current:
        try:
            value = input(f"{prompt} [{current}]: ").strip()
        except EOFError:
            return current
        return value or current
    try:
        return input(f"{prompt}: ").strip()
    except EOFError:
        return ""


def input_choice(
    prompt: str,
    options: list[str],
    default: str | None = None,
    state_value: str | None = None,
    allow_custom: bool = False,
    custom_hint: str = "",
) -> str:
    print(f"\n{prompt}")
    current = state_value if state_value in options else default
    for index, option in enumerate(options, start=1):
        marker = " (当前)" if option == current else ""
        print(f"  {index}. {option}{marker}")
    if allow_custom:
        print(f"  0. {custom_hint}")
    while True:
        try:
            choice = input("选择编号 [直接回车保持当前]: ").strip()
        except EOFError:
            return current or options[0]
        if not choice and current:
            return current
        if choice.isdigit():
            if 0 <= int(choice) <= len(options):
                if int(choice) == 0 and allow_custom:
                    custom_input = input("请输入自定义值: ").strip()
                    if custom_input:
                        return custom_input
                    print("未输入有效值，请重试")
                    continue
                elif int(choice) > 0:
                    return options[int(choice) - 1]
        print("无效选择，请重试")


def input_multi_choice(
    prompt: str,
    options: list[str],
    max_select: int | None = None,
    state_values: list[str] | None = None,
) -> list[str]:
    print(f"\n{prompt}")
    print("(输入多个编号，用空格分隔；直接回车结束选择)")
    current_values = state_values or []
    for index, option in enumerate(options, start=1):
        marker = " ✓" if option in current_values else ""
        print(f"  {index}. {option}{marker}")
    while True:
        try:
            raw = input("选择编号: ").strip()
        except EOFError:
            return current_values or []
        if not raw:
            return current_values
        values = []
        ok = True
        for item in raw.split():
            if item.isdigit() and 1 <= int(item) <= len(options):
                values.append(options[int(item) - 1])
            else:
                ok = False
                break
        if not ok:
            print("无效输入，请重试")
            continue
        if max_select and len(values) > max_select:
            print(f"最多选择 {max_select} 个，请重试")
            continue
        return values


def parse_custom_word_target(user_input: str) -> str | None:
    match = re.search(r"(\d+)\s*万字?", user_input)
    if match:
        num = int(match.group(1))
        if num >= 10:
            return f"{num}万字"
    match = re.search(r"^(\d+)$", user_input.strip())
    if match:
        num = int(match.group(1))
        if 100000 <= num <= 5000000:
            return f"{num // 10000}万字"
    return None


def parse_custom_chapter_length(user_input: str) -> str | None:
    match = re.search(r"(\d+)\s*[-~]\s*(\d+)\s*字?", user_input)
    if match:
        low = int(match.group(1))
        high = int(match.group(2))
        if 1000 <= low <= high <= 20000:
            return f"{low}-{high}字"
    return None


def step_basic_specs(state: dict) -> dict:
    saved = state.get("basic_specs", {})
    print("\n=== 步骤 1：基本规格与体裁 ===")

    word_target = input_choice(
        "目标字数",
        WORD_TARGET_OPTIONS,
        "40万字",
        saved.get("target_word_count"),
        allow_custom=True,
        custom_hint="用户输入（如：50万字）",
    )
    if word_target not in WORD_TARGET_OPTIONS:
        parsed = parse_custom_word_target(word_target)
        if parsed:
            word_target = parsed
        else:
            print("格式无效，已使用默认值 40万字")
            word_target = "40万字"

    chapter_length = input_choice(
        "单章字数",
        CHAPTER_LENGTH_OPTIONS,
        "3500-4500字",
        saved.get("chapter_length"),
        allow_custom=True,
        custom_hint="用户输入（如：2500-3500字）",
    )
    if chapter_length not in CHAPTER_LENGTH_OPTIONS:
        parsed = parse_custom_chapter_length(chapter_length)
        if parsed:
            chapter_length = parsed
        else:
            print("格式无效，已使用默认值 3500-4500字")
            chapter_length = "3500-4500字"

    pacing = input_choice(
        "节奏偏好",
        PACING_OPTIONS,
        "偏快（每章推进）",
        saved.get("pacing"),
    )

    style_tone = input_choice(
        "文风基调",
        STYLE_TONE_OPTIONS,
        "热血燃向",
        saved.get("style_tone"),
    )

    main_genres = input_multi_choice(
        "选择主要题材（1-3个）",
        MAIN_GENRE_OPTIONS,
        max_select=3,
        state_values=saved.get("main_genres", []),
    )
    if not main_genres:
        main_genres = ["都市高武"]

    sub_genres = input_multi_choice(
        "补充元素（可选）",
        SUB_GENRE_OPTIONS,
        state_values=saved.get("sub_genres", []),
    )

    derived = describe_target_profile(word_target, chapter_length)
    print(f"\n自动推导：总章节数约 {derived['target_total_chapters']} 章，"
          f"推荐 {volume_label(derived['derived_total_volumes'])}，"
          f"每卷约 {derived['derived_chapters_per_volume']} 章")

    state["basic_specs"] = build_basic_specs(
        word_target,
        chapter_length,
        pacing,
        style_tone,
        main_genres,
        sub_genres,
    )
    state["_current_node"] = "basic_specs"
    state["_completed_nodes"] = state.get("_completed_nodes", []) + ["basic_specs"]

    return state


def step_positioning(state: dict) -> dict:
    saved = state.get("positioning", {})
    specs = state.get("basic_specs", {})
    main_genres = specs.get("main_genres", ["都市高武"])
    style_tone = specs.get("style_tone", "热血燃向")

    print("\n=== 步骤 2：项目定位与读者承诺 ===")

    narrative_style = input_choice(
        "叙事方式",
        NARRATIVE_STYLE_OPTIONS,
        "第三人称有限视角",
        saved.get("narrative_style"),
    )

    conflict_options = get_conflict_options(main_genres)
    print(f"\n可选主冲突: {', '.join(conflict_options)}")
    main_conflicts = input_multi_choice(
        "选择主冲突（2-3个）",
        conflict_options,
        max_select=3,
        state_values=saved.get("main_conflicts", []),
    )
    if not main_conflicts:
        main_conflicts = conflict_options[:2]

    hook_options = get_reader_hook_options(style_tone)
    print(f"\n可选核心追读动力: {', '.join(hook_options)}")
    reader_hooks = input_multi_choice(
        "选择核心追读动力（2-3个）",
        hook_options,
        max_select=3,
        state_values=saved.get("reader_hooks", []),
    )
    if not reader_hooks:
        reader_hooks = hook_options[:2]

    defaults = default_positioning_values(main_genres, style_tone)
    core_promise = input_with_default(
        "一句话主承诺",
        defaults["core_promise"],
        saved.get("core_promise"),
    )
    selling_point = input_with_default(
        "一句话卖点",
        defaults["selling_point"],
        saved.get("selling_point"),
    )

    state["positioning"] = build_positioning(
        narrative_style,
        main_conflicts,
        reader_hooks,
        core_promise,
        selling_point,
    )
    state["_current_node"] = "positioning"
    state["_completed_nodes"] = state.get("_completed_nodes", []) + ["positioning"]

    return state


def step_protagonist(state: dict) -> dict:
    saved = state.get("protagonist", {})

    print("\n=== 步骤 3：主角设定 ===")

    name = input_with_default(
        "主角姓名",
        "林泽",
        saved.get("name"),
    )

    gender = input_choice(
        "性别",
        GENDER_OPTIONS,
        "男",
        saved.get("gender"),
    )

    age_group = input_choice(
        "年龄段",
        AGE_GROUP_OPTIONS,
        "青年(18-30)",
        saved.get("age_group"),
    )

    starting_identity = input_with_default(
        "起点身份",
        "培训中心学员",
        saved.get("starting_identity"),
    )

    starting_level = input_with_default(
        "起点实力",
        "基础中期",
        saved.get("starting_level"),
    )

    personality = input_choice(
        "核心性格",
        PERSONALITY_OPTIONS[:5],
        "坚毅",
        saved.get("personality"),
    )

    print(f"\n可选核心欲望: {', '.join(CORE_DESIRE_EXAMPLES[:4])}")
    core_desire = input_with_default(
        "核心欲望",
        "获得力量，改变命运",
        saved.get("core_desire"),
    )

    print(f"\n可选深层恐惧: {', '.join(DEEPEST_FEAR_EXAMPLES[:4])}")
    deepest_fear = input_with_default(
        "深层恐惧",
        "无力反击",
        saved.get("deepest_fear"),
    )

    long_term_goal = input_with_default(
        "长期目标",
        "获得足够的力量和地位",
        saved.get("long_term_goal"),
    )

    ability = input_with_default(
        "特殊能力/金手指（可选）",
        "超强的体能素质",
        saved.get("ability"),
    )

    state["protagonist"] = build_protagonist(
        name, gender, age_group, starting_identity, starting_level,
        personality, core_desire, deepest_fear, long_term_goal, ability
    )
    state["_current_node"] = "protagonist"
    state["_completed_nodes"] = state.get("_completed_nodes", []) + ["protagonist"]

    return state


def step_power_system(state: dict) -> dict:
    saved = state.get("power_system", {})

    print("\n=== 步骤 4：力量体系 ===")

    main_system = input_choice(
        "主要修炼体系",
        POWER_SYSTEM_OPTIONS,
        "体能技击",
        saved.get("main_system"),
    )

    levels = input_with_default(
        "境界划分",
        "基础期→进阶期→精英期→大师期",
        saved.get("levels"),
    )

    breakthrough = input_choice(
        "突破条件",
        BREAKTHROUGH_OPTIONS,
        "实战胜利积累",
        saved.get("breakthrough_condition"),
    )

    limitation = input_choice(
        "力量限制/代价",
        LIMITATION_OPTIONS,
        "无明显限制",
        saved.get("limitation"),
    )

    unique_trait = input_with_default(
        "修炼体系特点（可选）",
        "无",
        saved.get("unique_trait"),
    )

    resource_economy = input_with_default(
        "资源/货币体系（可选）",
        "无",
        saved.get("resource_economy"),
    )

    state["power_system"] = build_power_system(
        main_system, levels, breakthrough, limitation, unique_trait, resource_economy
    )
    state["_current_node"] = "power_system"
    state["_completed_nodes"] = state.get("_completed_nodes", []) + ["power_system"]

    return state


def step_world(state: dict) -> dict:
    saved = state.get("world", {})
    specs = state.get("basic_specs", {})
    main_genres = specs.get("main_genres", [])

    print("\n=== 步骤 5：世界观设定 ===")

    setting_type = input_choice(
        "背景设定",
        SETTING_OPTIONS,
        "现代都市",
        saved.get("setting_type"),
    )

    society_structure = input_choice(
        "社会结构",
        SOCIETY_OPTIONS,
        "帮派势力",
        saved.get("society_structure"),
    )

    scene_options = get_scene_options(main_genres)
    print(f"\n可选主要场景: {', '.join(scene_options)}")
    main_scene = input_multi_choice(
        "主要场景（1-2个）",
        scene_options,
        max_select=2,
        state_values=saved.get("main_scene", []),
    )
    if not main_scene:
        main_scene = scene_options[:1]

    print(f"\n可选冒险区域: {', '.join(ADVENTURE_OPTIONS)}")
    adventure_zone = input_multi_choice(
        "冒险区域（1-2个）",
        ADVENTURE_OPTIONS,
        max_select=2,
        state_values=saved.get("adventure_zone", []),
    )
    if not adventure_zone:
        adventure_zone = ADVENTURE_OPTIONS[:1]

    print(f"\n可选主要危机: {', '.join(CRISIS_OPTIONS)}")
    main_crisis = input_multi_choice(
        "主要危机（1-2个）",
        CRISIS_OPTIONS,
        max_select=2,
        state_values=saved.get("main_crisis", []),
    )
    if not main_crisis:
        main_crisis = CRISIS_OPTIONS[:1]

    scene_layers = input_with_default(
        "场景层级（可选，如：表层-中层-深层）",
        "表层-中层-深层",
        saved.get("scene_layers"),
    )
    if scene_layers == "表层-中层-深层":
        scene_layers = None

    state["world"] = build_world(
        setting_type,
        society_structure,
        main_scene,
        adventure_zone,
        main_crisis,
        scene_layers,
    )
    state["_current_node"] = "world"
    state["_completed_nodes"] = state.get("_completed_nodes", []) + ["world"]

    return state


def step_factions(state: dict) -> dict:
    saved = state.get("factions", {})

    print("\n=== 步骤 5：势力设定 ===")

    player_faction = input_with_default(
        "主角势力",
        "猎杀小队",
        saved.get("player_faction"),
    )

    enemy_faction = input_with_default(
        "反派势力",
        "其他帮派势力",
        saved.get("enemy_faction"),
    )

    neutral_faction = input_with_default(
        "中立势力",
        "培训中心",
        saved.get("neutral_faction"),
    )

    state["factions"] = build_factions(
        player_faction, enemy_faction, neutral_faction
    )
    state["_current_node"] = "factions"
    state["_completed_nodes"] = state.get("_completed_nodes", []) + ["factions"]

    return state


def step_characters(state: dict) -> dict:
    saved = state.get("characters", {})

    print("\n=== 步骤 6：角色关系 ===")

    romance_type = input_choice(
        "感情线",
        ROMANCE_OPTIONS,
        "单女主",
        saved.get("romance_type"),
    )

    print(f"\n可选关系类型: {', '.join(RELATIONSHIP_OPTIONS)}")
    key_relationship_types = input_multi_choice(
        "主要关系类型（1-3个）",
        RELATIONSHIP_OPTIONS,
        max_select=3,
        state_values=saved.get("key_relationship_types", []),
    )
    if not key_relationship_types:
        key_relationship_types = ["兄弟", "竞争"]

    main_antagonist_type = input_choice(
        "核心对立面",
        ANTAGONIST_OPTIONS,
        "势力BOSS",
        saved.get("main_antagonist_type"),
    )

    antagonist_curve = input_choice(
        "反派强度曲线",
        ANTAGONIST_CURVE_OPTIONS,
        "交替领先",
        saved.get("antagonist_curve"),
    )

    print(f"\n可选冲突层级: {', '.join(CONFLICT_LEVEL_OPTIONS)}")
    conflict_levels = input_multi_choice(
        "冲突层级（1-3个）",
        CONFLICT_LEVEL_OPTIONS,
        max_select=3,
        state_values=saved.get("conflict_levels", []),
    )
    if not conflict_levels:
        conflict_levels = ["同辈竞争", "城市事件"]

    main_factions = input_with_default(
        "主要势力（用逗号分隔）",
        "主角势力,反派组织,中立联盟",
        saved.get("main_factions"),
    )

    print(f"\n可选关系张力来源: {', '.join(TENSION_OPTIONS)}")
    relationship_tension = input_multi_choice(
        "关系张力来源（1-2个）",
        TENSION_OPTIONS,
        max_select=2,
        state_values=saved.get("relationship_tension", []),
    )
    if not relationship_tension:
        relationship_tension = ["利益争夺", "理念冲突"]

    state["characters"] = build_characters(
        romance_type,
        key_relationship_types,
        main_antagonist_type,
        antagonist_curve,
        conflict_levels,
        main_factions,
        relationship_tension,
    )
    state["_current_node"] = "characters"
    state["_completed_nodes"] = state.get("_completed_nodes", []) + ["characters"]

    return state


def step_volume_architecture(state: dict) -> dict:
    saved_arch = state.get("volume_architecture", {})
    saved_batch = state.get("batch_plan", {})
    specs = state["basic_specs"]
    positioning = state.get("positioning", {})
    world = state.get("world", {})

    volume_count = specs["target_volumes_numeric"]
    chapters_per_volume = specs["chapters_per_volume"]

    print("\n=== 步骤 7：卷章架构 ===")
    print(f"确认卷数: {volume_count} 卷")
    print(f"确认每卷章节数: {chapters_per_volume} 章")

    style_tone = specs.get("style_tone", "热血燃向")
    escalation_options = get_escalation_path_options(style_tone)
    book_escalation_path = input_choice(
        "全书抬升路径",
        escalation_options,
        escalation_options[0],
        saved_arch.get("book_escalation_path"),
    )

    main_conflicts = positioning.get("main_conflicts", ["升级成长"])
    delivery_options = get_delivery_options(main_conflicts)
    delivery_matrix = input_choice(
        "每卷交付承诺",
        delivery_options,
        delivery_options[0],
        saved_arch.get("delivery_matrix"),
    )

    batch_size_label = input_choice(
        "每批章节数",
        BATCH_SIZE_OPTIONS,
        "10章",
        saved_batch.get("batch_size_label"),
    )
    batch_size = int(batch_size_label.rstrip("章"))

    goal_options = get_first_volume_goal_options(main_conflicts)
    first_volume_goal = input_choice(
        "首卷目标",
        goal_options,
        goal_options[0],
        saved_batch.get("first_volume_goal"),
    )

    main_crisis = world.get("main_crisis", ["权力斗争"])
    hook_options = get_first_volume_hook_options(main_crisis)
    first_volume_hook = input_choice(
        "首卷钩子",
        hook_options,
        hook_options[0],
        saved_batch.get("first_volume_hook"),
    )

    opening_modes = [
        "开局受压 -> 获得机遇 -> 首次成功 -> 站稳脚跟",
        "开局平平 -> 意外机遇 -> 小试牛刀 -> 初露头角",
        "开局困境 -> 系统/导师帮助 -> 快速成长 -> 一鸣惊人"
    ]
    first_batch_opening_mode = input_choice(
        "开局链",
        opening_modes,
        opening_modes[0],
        saved_batch.get("first_batch_opening_mode"),
    )

    state["volume_architecture"] = build_volume_architecture(
        volume_count,
        chapters_per_volume,
        book_escalation_path,
        delivery_matrix,
    )
    state["batch_plan"] = build_batch_plan(
        batch_size,
        first_volume_goal,
        first_volume_hook,
        first_batch_opening_mode,
    )
    state["_current_node"] = "volume_architecture"
    state["_completed_nodes"] = state.get("_completed_nodes", []) + ["volume_architecture", "batch_plan"]

    return state


def step_naming(state: dict) -> dict:
    saved = state.get("naming", {})
    specs = state["basic_specs"]
    positioning = state.get("positioning", {})

    main_genres = specs.get("main_genres", ["都市高武"])
    style_tone = specs.get("style_tone", "热血燃向")
    core_promise = positioning.get("core_promise", "")

    print("\n=== 步骤 8：命名与最终审阅 ===")

    candidates = generate_book_title_options(main_genres, style_tone, core_promise)
    print(f"书名候选: {', '.join(candidates)}")

    book_title = input_choice(
        "选择书名",
        candidates,
        candidates[0],
        saved.get("selected_book_title"),
    )

    state["naming"] = build_naming(book_title, candidates)
    state["_current_node"] = "naming"
    state["_completed_nodes"] = state.get("_completed_nodes", []) + ["naming"]

    return state


def init_wizard(project_name: str, base_dir: Path, initial_state: dict | None = None) -> dict:
    state = initial_state or {
        "_created_at": datetime.now().isoformat(),
        "_project_name": project_name,
        "_current_node": "init",
    }
    state.setdefault("_project_name", project_name)

    step_basic_specs(state)
    persist_wizard_state(base_dir, state)
    step_positioning(state)
    persist_wizard_state(base_dir, state)
    step_protagonist(state)
    persist_wizard_state(base_dir, state)
    if POWER_GENRES.intersection(set(state.get("basic_specs", {}).get("main_genres", []))):
        step_power_system(state)
        persist_wizard_state(base_dir, state)
    step_world(state)
    persist_wizard_state(base_dir, state)
    step_factions(state)
    persist_wizard_state(base_dir, state)
    step_characters(state)
    persist_wizard_state(base_dir, state)
    step_volume_architecture(state)
    persist_wizard_state(base_dir, state)
    step_naming(state)
    persist_wizard_state(base_dir, state)

    print("\n=== 基本规格已锁定 ===")
    specs = state["basic_specs"]
    print(f"  目标字数: {specs['target_word_count']}")
    print(f"  单章字数: {specs['chapter_length']}")
    print(f"  节奏偏好: {specs['pacing']}")
    print(f"  文风基调: {specs['style_tone']}")
    print(f"  主题材: {', '.join(specs['main_genres'])}")
    if specs['sub_genres']:
        print(f"  补充元素: {', '.join(specs['sub_genres'])}")
    print(f"  预计: {specs['target_volumes_label']}，每卷 {specs['chapters_per_volume']} 章")

    print("\n=== 项目定位已锁定 ===")
    pos = state["positioning"]
    print(f"  叙事方式: {pos['narrative_style']}")
    print(f"  主冲突: {', '.join(pos['main_conflicts'])}")
    print(f"  核心追读动力: {', '.join(pos['reader_hooks'])}")
    print(f"  主承诺: {pos['core_promise']}")
    print(f"  卖点: {pos['selling_point']}")

    if "protagonist" in state:
        print("\n=== 主角设定已锁定 ===")
        prot = state["protagonist"]
        print(f"  姓名: {prot['name']}")
        print(f"  性别: {prot['gender']}")
        print(f"  年龄段: {prot['age_group']}")
        print(f"  起点身份: {prot['starting_identity']}")
        print(f"  起点实力: {prot['starting_level']}")
        print(f"  核心性格: {prot['personality']}")
        print(f"  核心欲望: {prot['core_desire']}")
        print(f"  深层恐惧: {prot['deepest_fear']}")
        print(f"  长期目标: {prot['long_term_goal']}")
        if prot.get('ability'):
            print(f"  特殊能力: {prot['ability']}")

    if "power_system" in state:
        print("\n=== 力量体系已锁定 ===")
        pw = state["power_system"]
        print(f"  修炼体系: {pw['main_system']}")
        print(f"  境界划分: {pw['levels']}")
        print(f"  突破条件: {pw['breakthrough_condition']}")
        print(f"  力量限制: {pw['limitation']}")
        if pw.get('unique_trait'):
            print(f"  体系特点: {pw['unique_trait']}")

    print("\n=== 世界观设定已锁定 ===")
    world = state["world"]
    print(f"  背景设定: {world['setting_type']}")
    print(f"  社会结构: {world['society_structure']}")
    print(f"  主要场景: {', '.join(world['main_scene'])}")
    print(f"  冒险区域: {', '.join(world['adventure_zone'])}")
    print(f"  主要危机: {', '.join(world['main_crisis'])}")
    if world.get('scene_layers'):
        print(f"  场景层级: {world['scene_layers']}")

    if "factions" in state:
        print("\n=== 势力设定已锁定 ===")
        fac = state["factions"]
        print(f"  主角势力: {fac['player_faction']}")
        print(f"  反派势力: {fac['enemy_faction']}")
        print(f"  中立势力: {fac['neutral_faction']}")

    print("\n=== 角色关系已锁定 ===")
    chars = state["characters"]
    print(f"  感情线: {chars['romance_type']}")
    print(f"  主要关系: {', '.join(chars['key_relationship_types'])}")
    print(f"  核心对立面: {chars['main_antagonist_type']}")
    print(f"  反派曲线: {chars['antagonist_curve']}")
    print(f"  冲突层级: {', '.join(chars['conflict_levels'])}")
    print(f"  主要势力: {chars['main_factions']}")
    print(f"  关系张力: {', '.join(chars['relationship_tension'])}")

    print("\n=== 卷章架构已锁定 ===")
    arch = state["volume_architecture"]
    print(f"  卷数: {arch['volume_count']} 卷")
    print(f"  每卷章节数: {arch['chapters_per_volume']} 章")
    print(f"  全书抬升路径: {arch['book_escalation_path']}")
    print(f"  每卷交付承诺: {arch['delivery_matrix']}")
    batch = state["batch_plan"]
    print(f"  每批章节数: {batch['batch_size']} 章")
    print(f"  首卷目标: {batch['first_volume_goal']}")
    print(f"  首卷钩子: {batch['first_volume_hook']}")
    print(f"  开局链: {batch['first_batch_opening_mode']}")

    print("\n=== 命名与最终审阅已锁定 ===")
    naming = state["naming"]
    print(f"  书名: {naming['selected_book_title']}")
    print(f"  候选: {', '.join(naming['book_title_candidates'])}")

    return state


def main():
    if len(sys.argv) < 2:
        print('用法: init_wizard.py "项目名"')
        sys.exit(1)

    project_name = sys.argv[1].strip()
    if not project_name:
        print("项目名不能为空")
        sys.exit(1)

    base_dir = Path.cwd()
    existing_state = base_dir / STATE_FILENAME
    initial_state = json.loads(existing_state.read_text(encoding="utf-8")) if existing_state.exists() else None
    state = init_wizard(project_name, base_dir, initial_state)

    try:
        validate_final_state_requirements(state)
    except ProjectStateError as exc:
        print(f"初始化失败：{exc}")
        sys.exit(1)

    print(f"\n状态已保存到: {base_dir / STATE_FILENAME}")


if __name__ == "__main__":
    main()
