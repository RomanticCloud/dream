#!/usr/bin/env python3
"""章节生成器 - 为dream技能创建章节支架和起草提示

合并功能：
- 支持创建章节支架（可选）
- 支持指定卷章号（content_generator风格）
- 支持自动检测进度（new_chapter风格）
- 使用 chapter-draft.md 模板文件生成提示
- 支持Power System检测和条件渲染
"""

import json
import re
import sys
from pathlib import Path
from datetime import datetime

from card_parser import extract_section, extract_bullets
from card_names import CARRY_CARD, EMOTION_CARD, PLOT_CARD
from card_fields import (
    FIELD_CARRY_HOOK,
    FIELD_CARRY_LIMIT,
    FIELD_CARRY_MUST,
    FIELD_CARRY_PAYOFF,
    FIELD_CARRY_SETUP,
    FIELD_EMOTION_PROCESS,
    FIELD_EMOTION_START,
    FIELD_EMOTION_SUSPENSE,
    FIELD_EMOTION_TARGET,
    FIELD_PLOT_CONFLICT,
    FIELD_PLOT_EVENT,
    FIELD_PLOT_PAYOFF,
    FIELD_PLOT_SETUP,
    FIELD_PLOT_TURN,
    FIELD_RELATION_CHANGE,
    FIELD_RELATION_MAIN,
    FIELD_RESOURCE_CARRY,
    FIELD_RESOURCE_GAIN,
    FIELD_RESOURCE_LOSS,
    FIELD_RESOURCE_SETUP,
    FIELD_RESOURCE_SPEND,
    FIELD_STATUS_CHANGE,
    FIELD_STATUS_ELAPSED,
    FIELD_STATUS_EMOTION,
    FIELD_STATUS_GOAL,
    FIELD_STATUS_INJURY,
    FIELD_STATUS_LOCATION,
    FIELD_STATUS_TIMEPOINT,
)
from chapter_scan import chapter_file_by_number
from chapter_validator import validate_chapter, print_result, fix_time_logic_and_revalidate
from common_io import (
    ProjectStateError,
    load_project_state,
    load_volume_outline,
    require_chapter_word_range,
    require_locked_protagonist_gender,
    save_json_file,
)
from narrative_context import NarrativeContext
from revision_state import get_chapter_revision_status, get_chapter_revision_tasks
from state_tracker import StateTracker
from path_rules import chapter_file, chapter_card_file, draft_prompt_file
from progress_rules import get_current_progress, get_next_chapter
from subagent_chapter_generator import SubagentChapterGenerator
from task_dispatcher import TaskChapterDispatcher, TaskResultError
from global_clock import GlobalClock

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent

POWER_GENRES = ["都市高武", "玄幻奇幻", "仙侠修真"]

STYLE_ROLE_MAPPING = {
    "热血燃向": "节奏紧凑、情绪高涨的战斗/逆袭场面，每章要有燃点",
    "轻松幽默": "轻松诙谐的日常描写，反转打脸要自然不做作",
    "严肃写实": "细腻的心理描写，克制但有力量，注重现实逻辑",
    "黑暗深邃": "人性挣扎，情感张力强，氛围压抑但有深度",
    "甜宠治愈": "温暖甜蜜的情感互动，细节要甜而不腻",
    "悬疑推理": "逻辑严密，悬念营造，线索铺设要有层次感",
}


def should_include_power_system(state: dict) -> bool:
    """判断是否需要包含power system相关约束"""
    specs = state.get("basic_specs", {})
    genres = specs.get("main_genres", specs.get("genres", []))
    return any(g in POWER_GENRES for g in genres)


def load_prompt_template() -> str:
    """加载正文生成prompt模板"""
    prompt_file = SKILL_DIR / "prompts" / "chapter-draft.md"
    if prompt_file.exists():
        return prompt_file.read_text(encoding="utf-8")
    return None


def process_conditional_blocks(template: str, include_power_system: bool) -> str:
    """处理条件化块：<!-- IF POWER_SYSTEM --> ... <!-- ELSE --> ... <!-- ENDIF -->"""
    # 处理有 ELSE 的情况
    pattern_with_else = r'<!--\s*IF\s+POWER_SYSTEM\s*-->(.*?)<!--\s*ELSE\s*-->(.*?)<!--\s*ENDIF\s*-->'
    
    def replace_with_else(match):
        power_content = match.group(1)
        else_content = match.group(2)
        if include_power_system:
            return power_content
        else:
            return else_content
    
    result = re.sub(pattern_with_else, replace_with_else, template, flags=re.DOTALL)
    
    # 处理没有 ELSE 的情况
    pattern_without_else = r'<!--\s*IF\s+POWER_SYSTEM\s*-->(.*?)<!--\s*ENDIF\s*-->'
    
    def replace_without_else(match):
        content = match.group(1)
        if include_power_system:
            return content
        else:
            return ""
    
    result = re.sub(pattern_without_else, replace_without_else, result, flags=re.DOTALL)
    
    return result


def get_style_role(style_tone: str) -> str:
    """根据文风获取角色设定"""
    return STYLE_ROLE_MAPPING.get(style_tone, "商业化长篇连载创作")


def get_genre_description(genres: list) -> str:
    """根据题材获取描述"""
    if not genres:
        return "网络小说"
    
    genre_desc = {
        "都市高武": "都市背景下的高武战斗",
        "玄幻奇幻": "玄幻世界的冒险成长",
        "都市生活": "都市中的生活故事",
        "悬疑推理": "悬疑案件的推理破解",
        "科幻未来": "科幻背景下的未来世界",
        "仙侠修真": "仙侠世界的修真成长",
        "历史军事": "历史背景下的军事斗争",
    }
    
    descriptions = [genre_desc.get(g, g) for g in genres]
    return "、".join(descriptions[:2])


def get_locked_word_range(state: dict) -> tuple[int, int, int]:
    min_words, max_words = require_chapter_word_range(state)
    return min_words, max_words, (min_words + max_words) // 2


def ensure_writing_prerequisites(state: dict) -> None:
    require_chapter_word_range(state)
    require_locked_protagonist_gender(state)


def replace_template_variables(template: str, state: dict, vol_num: int, ch_num: int) -> str:
    """替换模板中的变量"""
    specs = state.get("basic_specs", {})
    positioning = state.get("positioning", {})
    
    min_words, max_words, _ = get_locked_word_range(state)
    
    # 计算骨架字数
    opening_min = int(min_words * 0.15)
    opening_max = int(max_words * 0.15)
    development_min = int(min_words * 0.40)
    development_max = int(max_words * 0.40)
    climax_min = int(min_words * 0.25)
    climax_max = int(max_words * 0.25)
    ending_min = int(min_words * 0.20)
    ending_max = int(max_words * 0.20)
    
    style_tone = specs.get("style_tone", "热血燃向")
    genres = specs.get("main_genres", specs.get("genres", []))
    narrative = positioning.get("narrative_style", "第三人称有限视角")
    
    variables = {
        "[文风基调]": style_tone,
        "[题材特点]": get_genre_description(genres),
        "[字数范围，根据项目配置]": f"{min_words}-{max_words}字",
        "[根据narrative_style配置]": narrative,
        "[N]": str(ch_num),
        "[章节标题]": "",  # 将在动态内容中补充
        "【开场】（500-700字）": f"【开场】（{opening_min}-{opening_max}字）",
        "【发展】（1500-1800字）": f"【发展】（{development_min}-{development_max}字）",
        "【转折/爆点】（800-1000字）": f"【转折/爆点】（{climax_min}-{climax_max}字）",
        "【收束】（600-800字）": f"【收束】（{ending_min}-{ending_max}字）",
    }
    
    result = template
    for var, value in variables.items():
        result = result.replace(var, value)
    
    return result


def load_last_chapter_carry(project_dir: Path, vol_name: str, last_ch_num: int) -> dict:
    """加载上一章的承接信息"""
    vol_num = int(vol_name.replace("vol", ""))
    last_file = chapter_file_by_number(project_dir, vol_num, last_ch_num)
    if last_file and last_file.exists():
        content = last_file.read_text(encoding="utf-8")
        carry_section = extract_section(content, CARRY_CARD)
        if carry_section:
            return extract_bullets(carry_section)

    return {}


def load_volume_memory(project_dir: Path, vol_num: int) -> dict:
    """加载卷级记忆"""
    memory_file = project_dir / "reference" / "卷沉淀" / f"vol{vol_num:02d}_state.json"
    if memory_file.exists():
        return json.loads(memory_file.read_text(encoding="utf-8"))
    return {}


def load_running_memory(state: dict) -> dict:
    """加载运行时记忆"""
    return state.get("project_running_memory", {})


def normalize_memory_items(items) -> list[str]:
    """规范化记忆项"""
    normalized: list[str] = []
    for item in items or []:
        if isinstance(item, dict):
            value = item.get("fact", "")
        else:
            value = str(item)
        value = value.strip()
        if value:
            normalized.append(value)
    return normalized


def render_memory_lines(items, limit: int = 4) -> str:
    """渲染记忆项为列表"""
    picked = normalize_memory_items(items)[:limit]
    if not picked:
        return "- （暂无）"
    return "\n".join(f"- {item}" for item in picked)


def render_revision_tasks(tasks: list[dict], limit: int = 5) -> str:
    if not tasks:
        return ""
    severity_order = {"error": 0, "warning": 1, "info": 2}
    sorted_tasks = sorted(tasks, key=lambda item: (severity_order.get(item.get("severity", "info"), 9), item.get("fix_method", "polish")))
    lines = []
    for task in sorted_tasks[:limit]:
        label = f"[{task.get('severity', 'info')}][{task.get('fix_method', 'polish')}]"
        location = " / ".join(part for part in [task.get("card", ""), task.get("field", "")] if part)
        rewrite_target = task.get("rewrite_target")
        if not rewrite_target:
            rewrite_target = {
                "regenerate": "full_chapter",
                "rewrite_card": "work_cards_only",
                "polish": "local_patch",
            }.get(task.get("fix_method", "polish"), "local_patch")
        blocking = task.get("blocking")
        if blocking is None:
            blocking = task.get("severity") == "error"
        constraints = task.get("preserve_constraints") or (
            ["工作卡必须与正文一致"] if rewrite_target == "work_cards_only" else
            ["保留本章核心事件", "保留章节结尾结果"] if rewrite_target == "full_chapter" else
            ["不改变主事件与章节结构"]
        )
        extras = []
        extras.append(f"目标={rewrite_target}")
        extras.append(f"阻塞={'是' if blocking else '否'}")
        if task.get("priority"):
            extras.append(f"优先级={task['priority']}")
        if location:
            line = f"- {label} {location}：{task.get('instruction', task.get('message', ''))}"
        else:
            line = f"- {label} {task.get('instruction', task.get('message', ''))}"
        if extras:
            line += f" ({'; '.join(extras)})"
        lines.append(line)
        if constraints:
            lines.append(f"  保留约束：{'；'.join(constraints)}")
    return "\n".join(lines)


def render_revision_mode_guidance(status: str | None) -> str:
    if status == "pending_regenerate":
        return "## 本轮修正模式：整章重写\n- 必须整章重写正文与工作卡，不能只做局部补丁。\n- 优先解决所有 error，再处理 warning。"
    if status == "pending_rewrite_card":
        return "## 本轮修正模式：重写工作卡\n- 正文尽量保持不变，重点重写 `## 内部工作卡`。\n- 工作卡必须严格对齐现有正文，不得脱离正文另写新剧情。"
    if status == "pending_polish":
        return "## 本轮修正模式：局部润色\n- 不改变主事件与章节结构，只修局部问题。\n- 优先修复 warning 和格式细节，避免整章重写。"
    return ""


def create_chapter_scaffold(
    project_dir: Path,
    vol_num: int,
    ch_num: int,
    vol_name: str,
    state: dict
) -> Path:
    """创建章节支架文件"""
    chapters_dir = project_dir / "chapters" / vol_name
    chapters_dir.mkdir(parents=True, exist_ok=True)

    chapter_path = chapter_file(project_dir, vol_num, ch_num)
    card_path = chapter_card_file(project_dir, vol_num, ch_num)
    card_path.parent.mkdir(parents=True, exist_ok=True)
    
    specs = state.get("basic_specs", {})
    ensure_writing_prerequisites(state)
    min_words, max_words, draft_target = get_locked_word_range(state)
    pacing = specs.get("pacing", "偏快")
    
    positioning = state.get("positioning", {})
    main_conflicts = positioning.get("main_conflicts", ["成长"])
    
    world = state.get("world", {})
    main_scene = world.get("main_scene", ["都市"])[0] if isinstance(world.get("main_scene"), list) else world.get("main_scene", "都市")
    
    vol_outline = load_volume_outline(project_dir, vol_num)
    vol_goal = vol_outline.get("卷目标", "推进故事")
    
    last_vol, last_ch = get_current_progress(project_dir)
    carry = {}
    if last_vol == vol_num and last_ch > 0:
        carry = load_last_chapter_carry(project_dir, vol_name, last_ch)
    
    running_memory = load_running_memory(state)
    active_constraints = normalize_memory_items(running_memory.get("active_constraints", []))
    open_setups = normalize_memory_items(running_memory.get("open_setups", []))
    previous_volume_memory = load_volume_memory(project_dir, max(vol_num - 1, 1)) if vol_num > 1 else {}
    
    content_template = f"""# 第{ch_num}章

## 章节卡

- 本章目标：
- 本章主冲突：{main_conflicts[0] if main_conflicts else '成长'}
- 本章主爽点：
- 本章新增信息：
- 本章资源变化：
- 本章人物关系变化：
- 本章结尾钩子：
- 本章承接前文：{carry.get('下章必须接住什么', '')}
- 本章不能忘的设定：{'；'.join(active_constraints[:3]) if active_constraints else '；'.join(stable_facts[:2]) if 'stable_facts' in dir() else ''}
- 本章视角要求：{positioning.get('narrative_style', '第三人称有限视角')}
- 本章节奏模式：{pacing}
- 本章必须继承的卷沉淀：{'；'.join(active_constraints[:3]) if active_constraints else ''}
- 本章待回收伏笔：{'；'.join(open_setups[:3]) if open_setups else ''}

---

## 正文

（在此撰写正文...）

目标字数：{min_words}-{max_words}字
推荐首稿：{draft_target}字

---

"""

    card_template = f"""## 内部工作卡

### 1. 状态卡
- {FIELD_STATUS_LOCATION}：{main_scene}
- {FIELD_STATUS_INJURY}：
- {FIELD_STATUS_EMOTION}：
- {FIELD_STATUS_GOAL}：
- {FIELD_STATUS_CHANGE}：
- {FIELD_STATUS_ELAPSED}：
- {FIELD_STATUS_TIMEPOINT}：

{PLOT_CARD}
- {FIELD_PLOT_CONFLICT}：
- {FIELD_PLOT_EVENT}：
- {FIELD_PLOT_TURN}：
- {FIELD_PLOT_SETUP}：
- {FIELD_PLOT_PAYOFF}：

### 3. 资源卡
- {FIELD_RESOURCE_GAIN}：
- {FIELD_RESOURCE_SPEND}：
- {FIELD_RESOURCE_LOSS}：
- {FIELD_RESOURCE_CARRY}：
- {FIELD_RESOURCE_SETUP}：

### 4. 关系卡
- {FIELD_RELATION_MAIN}：
- {FIELD_RELATION_CHANGE}：

{EMOTION_CARD}
- {FIELD_EMOTION_START}：
- {FIELD_EMOTION_PROCESS}：
- {FIELD_EMOTION_TARGET}：
- {FIELD_EMOTION_SUSPENSE}：

{CARRY_CARD}
- {FIELD_CARRY_MUST}：{carry.get(FIELD_CARRY_MUST, '')}
- {FIELD_CARRY_LIMIT}：
- {FIELD_CARRY_PAYOFF}：
- {FIELD_CARRY_SETUP}：
- {FIELD_CARRY_HOOK}：

"""

    chapter_path.write_text(content_template, encoding="utf-8")
    card_path.write_text(card_template, encoding="utf-8")
    return chapter_path


def generate_dynamic_content(
    project_dir: Path,
    vol_num: int,
    ch_num: int,
    vol_name: str,
    state: dict,
    include_power_system: bool
) -> str:
    """生成动态内容（项目信息、承接等）"""
    # 新增：加载叙事上下文
    narrative_ctx = NarrativeContext(project_dir)
    prev_context = narrative_ctx.load_previous_context(ch_num, lookback=1)

    # 新增：加载状态摘要
    state_tracker = StateTracker(project_dir)
    state_summary = state_tracker.get_state_summary(ch_num)

    specs = state.get("basic_specs", {})
    ensure_writing_prerequisites(state)
    positioning = state.get("positioning", {})
    world = state.get("world", {})
    
    min_words, max_words, draft_target = get_locked_word_range(state)
    pacing = specs.get("pacing", "偏快")
    
    main_conflicts = positioning.get("main_conflicts", [])
    core_promise = positioning.get("core_promise", "主角成长故事")
    
    setting = world.get("setting_type", "都市")
    main_scene = world.get("main_scene", ["都市"])[0] if isinstance(world.get("main_scene"), list) else world.get("main_scene", "都市")
    society = world.get("society_structure", "帮派势力")
    
    book_title = state.get("naming", {}).get("selected_book_title", state.get("naming", {}).get("book_title", "未命名"))
    
    last_vol, last_ch = get_current_progress(project_dir)
    carry = {}
    if last_vol == vol_num and last_ch > 0:
        carry = load_last_chapter_carry(project_dir, vol_name, last_ch)
    
    vol_outline = load_volume_outline(project_dir, vol_num)
    vol_goal = vol_outline.get('卷目标', '推进故事')
    previous_volume_memory = load_volume_memory(project_dir, max(vol_num - 1, 1)) if vol_num > 1 else {}
    running_memory = load_running_memory(state)
    active_constraints = normalize_memory_items(running_memory.get("active_constraints", []))
    open_setups = normalize_memory_items(running_memory.get("open_setups", []))
    stable_facts = normalize_memory_items(running_memory.get("stable_facts", previous_volume_memory.get("stable_facts", [])))
    unverified_claims = normalize_memory_items(running_memory.get("unverified_claims", previous_volume_memory.get("unverified_claims", [])))
    latest_final_state = running_memory.get("latest_final_state", {})
    conflicts = running_memory.get("conflicts", previous_volume_memory.get("conflicts", []))
    revision_status = get_chapter_revision_status(project_dir, vol_num, ch_num)
    revision_tasks = get_chapter_revision_tasks(project_dir, vol_num, ch_num)
    
    prompt = f"""## 项目信息
- 书名：{book_title}
- 题材：{', '.join(specs.get('main_genres', specs.get('genres', [])))}
- 文风：{specs.get('style_tone', '热血')}
- 叙事视角：{positioning.get('narrative_style', '第三人称有限视角')}

## 当前进度
- 当前卷：第{vol_num}卷
- 当前章节：第{ch_num}章
- 本卷目标：{vol_goal}

## 章节要求
- 字数范围：{min_words}-{max_words}字
- 目标首稿：约{draft_target}字
- 节奏要求：{pacing}

## 世界观
- 背景设定：{setting}
- 主要场景：{main_scene}
- 社会结构：{society}

## 主冲突
- 核心冲突：{main_conflicts[0] if main_conflicts else '成长'}
- 读者期待：{positioning.get('reader_hooks', ['看主角成长'])[0]}

## 主承诺
{core_promise}

"""
    
    # 项目动态沉淀
    if previous_volume_memory or active_constraints or open_setups:
        prompt += f"""## 项目动态沉淀（后文依据）

### 必须继承的稳定事实
{render_memory_lines(active_constraints or previous_volume_memory.get('next_volume_constraints', []))}

### 已验证稳定事实
{render_memory_lines(stable_facts)}

### 仅可谨慎使用的未证实信息
{render_memory_lines(unverified_claims)}

### 卷末人物状态
- 位置：{latest_final_state.get('主角当前位置', previous_volume_memory.get('final_state', {}).get('主角当前位置', ''))}
- 情绪：{latest_final_state.get('主角当前情绪', previous_volume_memory.get('final_state', {}).get('主角当前情绪', ''))}
- 目标：{latest_final_state.get('主角当前目标', previous_volume_memory.get('final_state', {}).get('主角当前目标', ''))}

### 仍待回收的卷级伏笔
{render_memory_lines(open_setups or previous_volume_memory.get('open_setups', []))}

### 禁止违背
- 不得推翻已沉淀的卷末状态、稳定关系和既定后果
- 不得把仍待回收的伏笔当作已解决事实
- 若需要改写沉淀事实，必须在正文中给出清晰因果
"""
        if conflicts:
            prompt += f"""
### 冲突提示
{render_memory_lines([f"{item.get('field', '')}: {item.get('reason', '')}" for item in conflicts])}
"""
    
    # 承接前文
    if carry.get('下章必须接住什么'):
        prompt += f"""
## 承接前文
- 必须接住：{carry['下章必须接住什么']}
"""
    if carry.get('本章留下的最强钩子是什么'):
        prompt += f"""
## 遗留悬念
- 本章留下的钩子：{carry['本章留下的最强钩子是什么']}
"""

    if revision_tasks:
        mode_guidance = render_revision_mode_guidance(revision_status)
        prompt += f"""
{mode_guidance}

## 本轮修正要求
{render_revision_tasks(revision_tasks)}
"""
    
    # 新增：场景锚点
    if prev_context:
        scene_anchor = prev_context.get("prev_1", {}).get("scene_anchor", "")
        if scene_anchor:
            prompt += f"""
## 上一章结尾场景（场景衔接锚点）
{scene_anchor}
"""

    # 新增：状态摘要
    if state_summary:
        prompt += f"""
## 当前状态摘要
{state_summary}
"""

    # 章节结构建议（动态计算字数）
    prompt += f"""
## 动态章节结构

### 开场（约{min_words//4}-{max_words//4}字）
- 场景锚定：{main_scene}中的具体场景
- 情绪基调：承接上文情绪，自然过渡

### 发展（约{min_words//2}-{max_words//2}字）
- 事件推进：具体动作 + 对话 + 心理描写
- 细节堆砌：优先动作链和即时后果

### 转折/爆点（约{min_words//4}-{max_words//4}字）
- 情绪高潮：冲突爆发或关键转折
- 感官描写：动态场景 + 内心震荡

### 收束（约{min_words//5}-{max_words//5}字）
- 即时后果：人物反应 + 状态变化
- 悬念钩子：未解危机或新发现

---

## 特别说明

### 字数验证要求
1. **统计正文字数**：只计算`## 正文`到`## 内部工作卡`之间的内容
2. **验证字数范围**：确认字数在 {min_words}-{max_words} 字范围内
3. **检查目标字数**：如果字数不足 {draft_target}，继续扩展内容
4. **检查安全下限**：如果字数低于 {int(min_words * 0.85)}，视为失败，重新生成
5. **避免水字数**：扩展时增加场景细节、内心独白、动作描写，不要堆砌无意义的描述

### 字数不足时的扩展策略（按优先级）
1. 增加场景的感官细节（视觉、听觉、触觉、嗅觉）
2. 增加角色的内心独白和思考
3. 增加动作描写的具体步骤
4. 增加环境描写和氛围营造
5. 增加对话的个性化表达

### 字数超标时的压缩策略（按优先级）
1. 删除重复的环境描写
2. 精简冗余的内心独白
3. 合并相似的场景转换
4. 减少过度的动作细节
"""
    
    return prompt


def get_formatted_time(project_dir: Path) -> str:
    """获取格式化的当前时间
    
    从 GLOBAL_CLOCK.json 读取当前时间，转换为自然语言格式
    
    Args:
        project_dir: 项目目录
        
    Returns:
        格式化的时间字符串，如 "2024年4月21日，傍晚"
    """
    clock = GlobalClock(project_dir)
    status = clock.get_status()
    current = status["current"]
    
    # 提取时间组件
    year = current["year"]
    month = current["month"]
    day = current["day"]
    hour = current.get("hour", 0)
    
    # 时段判断
    if 5 <= hour < 11:
        time_of_day = "清晨"
    elif 11 <= hour < 14:
        time_of_day = "正午"
    elif 14 <= hour < 18:
        time_of_day = "下午"
    elif 18 <= hour < 21:
        time_of_day = "傍晚"
    else:
        time_of_day = "深夜"
    
    return f"{year}年{month}月{day}日，{time_of_day}"


def generate_draft_prompt(
    project_dir: Path,
    vol_num: int,
    ch_num: int,
    vol_name: str,
    state: dict
) -> str:
    """生成完整的起草提示
    
    流程：
    1. 加载模板文件
    2. 检测是否需要Power System
    3. 处理条件块
    4. 替换变量
    5. 追加动态内容
    """
    # 加载模板
    template = load_prompt_template()
    if not template:
        print("警告：未找到模板文件 prompts/chapter-draft.md，将使用内置提示")
        # 使用简化的内置提示
        return generate_fallback_prompt(project_dir, vol_num, ch_num, vol_name, state)
    
    # 检测Power System
    include_power_system = should_include_power_system(state)
    
    # 处理条件块
    template = process_conditional_blocks(template, include_power_system)
    
    # 替换变量
    template = replace_template_variables(template, state, vol_num, ch_num)
    
    # 生成动态内容
    dynamic_content = generate_dynamic_content(
        project_dir, vol_num, ch_num, vol_name, state, include_power_system
    )
    
    # 组合：模板 + 动态内容
    # 在模板中找到合适的位置插入动态内容
    # 通常在 "## 输入信息" 或 "## 任务" 之后插入
    
    # 找到 "## 任务" 或 "## 系统级硬约束" 的位置
    insert_marker = "## 系统级硬约束"
    if insert_marker in template:
        parts = template.split(insert_marker, 1)
        full_prompt = parts[0] + dynamic_content + "\n\n" + insert_marker + parts[1]
    else:
        # 如果找不到标记，在文件末尾追加
        full_prompt = template + "\n\n" + dynamic_content
    
    # 注入时间 System Prompt（最顶部）
    try:
        formatted_time = get_formatted_time(project_dir)
        system_time_requirement = f"""【系统强制设定】
当前绝对时间为：{formatted_time}。
请确保本章的景物描写、人物作息符合此时间点。

"""
        full_prompt = system_time_requirement + full_prompt
    except Exception as e:
        # 如果时间获取失败，记录但不中断
        print(f"⚠️ 警告：无法获取当前时间: {e}")
    
    return full_prompt


def generate_fallback_prompt(
    project_dir: Path,
    vol_num: int,
    ch_num: int,
    vol_name: str,
    state: dict
) -> str:
    """当模板文件不存在时的备用提示生成"""
    min_words, max_words, _ = get_locked_word_range(state)
    
    include_power_system = should_include_power_system(state)
    dynamic_content = generate_dynamic_content(
        project_dir, vol_num, ch_num, vol_name, state, include_power_system
    )
    
    return f"""# 第{ch_num}章 起草提示

{dynamic_content}

## 写作要求

### 系统级硬约束
- **单次输出**: {min_words}-{max_words}字
- **单文件粒度**: 单次只写一个完整章节文件
- **完成判定**: 只有当本章正文字数落入项目配置区间、且 `## 内部工作卡` 与 6 张卡全部完整时，本章才算完成
- **视角**: 第三人称有限视角，主角独占90%以上篇幅
- **节奏**: 保持推进，每章必须有可感知进展
- **场景**: 具体场景描写，有画面感
- **动作**: 清晰的动作描写
- **情绪**: 有情绪压力或情绪释放，必须呈现完整的情绪弧光
- **钩子**: 结尾必须有继续追读的悬念

### 专业级创作约束
- **连续写作原则**: 写完本章后必须为下一章留下可执行承上启下卡
- **慢节奏叙事原则**: 10章推进1步剧情，每章内部用感官填满每个瞬间
- **场景颗粒度**: 每个瞬间用至少一个感官通道（视觉/听觉/触觉/嗅觉/内心）描写
- **情绪过山车**: 每章必须有情感波动，不能平铺直叙
- **悬念植入**: 结尾必须留钩子（危机/反转/新信息三选一）
- **爆点位置**: 主爽点通常放在章节 2/3 处，前后有充分铺垫和余波

### 禁止事项
- [ ] 无控制的视角乱跳（非主角视角不超过10%）
- [ ] 大段设定说明直接压停剧情
- [ ] 配角只承担"震惊主角"的功能
- [ ] 一章多个同级爽点互相打架
- [ ] 用重复震惊反应替代推进
- [ ] 写成设定说明书
- [ ] 平铺直叙，缺少情绪起伏
- [ ] 高频词汇重复："心中充满了"、"喃喃自语道"、"深吸一口气"每章≤2次
- [ ] 相似段落重复：同一信息在多处重复描述
- [ ] 对话信息倾倒：单次连续对话≤3句，信息要分场景揭示
- [ ] 模式化情感描写：禁止"他喃喃自语道"、"他的心中充满了..."等套路
- [ ] 内容重复：前文已提及的背景、设定不再说明
- [ ] 抽象情感概括：如"他感到非常害怕"改为具体动作和感官描写
"""


def validate_chapter_interactive(
    project_dir: Path,
    vol_num: int,
    ch_num: int,
    max_retries: int = 3,
    auto_fix: bool = False
) -> bool:
    """验证章节，失败时自动修复或询问是否重生成

    Args:
        project_dir: 项目目录
        vol_num: 卷号
        ch_num: 章节号
        max_retries: 最大重试次数
        auto_fix: 是否自动修复时间逻辑问题

    Returns:
        True if validation passed, False if user gave up
    """
    for attempt in range(1, max_retries + 1):
        print(f"\n{'='*50}")
        print(f"第 {attempt}/{max_retries} 次验证")
        print(f"{'='*50}")

        result = validate_chapter(project_dir, vol_num, ch_num)
        print_result(result)

        if result.passed:
            print(f"✅ 第{attempt}次尝试通过")
            
            # 验证通过后，立即推进时间轴
            print(f"\n【时间轴推进】")
            try:
                from global_clock import GlobalClock
                clock = GlobalClock(project_dir)
                card_file = chapter_card_file(project_dir, vol_num, ch_num)
                if card_file.exists():
                    clock.advance_from_card(card_file, vol_num, ch_num)
                    print(f"✅ 时间轴已推进")
                    
                    # 记录里程碑
                    try:
                        content = card_file.read_text(encoding="utf-8")
                        plot_card = extract_section(content, PLOT_CARD)
                        if plot_card:
                            events = re.findall(r'[\d]+\.\s*(.+?)(?=\n|$)', plot_card)
                            if events:
                                milestone_event = events[0].strip()
                                clock.add_milestone(milestone_event, f"ch{ch_num:02d}")
                                print(f"✅ 里程碑已记录: {milestone_event[:50]}...")
                    except Exception as e:
                        print(f"⚠️ 里程碑记录失败: {e}")
                else:
                    print(f"⚠️ 卡片文件不存在，跳过时间轴推进")
            except Exception as e:
                print(f"❌ 时间轴推进失败: {e}")
                print("由于时间轴推进失败，阻止继续")
                return False
            
            return True

        # 自动修复时间逻辑问题
        if auto_fix:
            print(f"\n【自动修复】尝试修复时间逻辑问题...")
            fixed, remaining_issues = fix_time_logic_and_revalidate(project_dir, vol_num, ch_num)
            if fixed:
                print(f"✅ 时间逻辑问题已修复")
                result2 = validate_chapter(project_dir, vol_num, ch_num)
                if result2.passed:
                    print_result(result2)
                    print(f"✅ 修复后验证通过")
                    return True
            elif remaining_issues:
                print(f"⚠ 仍有问题需要处理:")
                for issue in remaining_issues:
                    print(f"  - {issue.message}")

        # 打印高严重度问题
        if result.fix_plan and not result.revision_tasks:
            if result.fix_plan.get("total_regenerate", 0) > 0:
                print("\n【高严重度问题】需整章重写:")
                for item in result.fix_plan["regenerate"]:
                    print(f"  - {item['name']}: {item['details']}")
            if result.fix_plan.get("total_polish", 0) > 0:
                print("\n【低严重度问题】AI润色:")
                for item in result.fix_plan["ai_polish"]:
                    print(f"  - {item['name']}: {item['details']}")
        if result.revision_tasks:
            print("\n【结构化修正任务】")
            for task in result.revision_tasks[:5]:
                label = f"[{task.get('severity', 'info')}][{task.get('fix_method', 'polish')}]"
                location = " / ".join(part for part in [task.get("card", ""), task.get("field", "")] if part)
                print(f"  - {label} {location}: {task.get('instruction', task.get('message', ''))}".rstrip())
            targets = {task.get("rewrite_target") for task in result.revision_tasks}
            auto_target = "full_chapter" if "full_chapter" in targets else "work_cards_only" if "work_cards_only" in targets else "local_patch"
            print(f"\n【自动执行目标】{auto_target}")

        # 询问用户
        if attempt < max_retries:
            print(f"\n❌ 第{attempt}次验证失败")
            try:
                choice = input("是否重生成? (y/n/c=continue anyway): ").strip().lower()
            except EOFError:
                choice = 'n'
                print("(输入不可用，默认选择n)")

            if choice == 'n':
                print("用户放弃")
                return False
            elif choice == 'c':
                print("用户选择继续")
                return False
            # y: 继续循环重生成
        else:
            print(f"\n❌ 达到最大重试次数({max_retries})")
            return False

    return False


def generate_chapter_with_subagent(
    project_dir: Path,
    vol_num: int,
    ch_num: int,
    lookback: int = 0
) -> dict:
    """准备 Task/子代理章节生成请求。

    Args:
        project_dir: 项目目录
        vol_num: 卷号
        ch_num: 章节号
        lookback: 回溯章节数（0=全部，不使用）

    Returns:
        {
            "status": "task_request_ready" | "error",
            "prompt_file": "提示文件路径",
            "prompt_length": 500,
            "request_file": "任务请求文件路径"
        }
    """
    dispatcher = TaskChapterDispatcher(project_dir)
    result = dispatcher.dispatch(vol_num, ch_num, lookback)
    if isinstance(result, dict):
        return result

    save_json_file(project_dir / "context" / "latest_generation_manifest.json", result.__dict__)
    return result.__dict__


def main():
    """主函数 - 支持多种参数风格

    用法:
        new_chapter.py <项目目录> [--auto|--prompt-only|--subagent|--separate]
        new_chapter.py <项目目录> [vol] [ch]

    示例:
        new_chapter.py .                          # 自动检测下一章
        new_chapter.py . --auto                   # 默认子代理链路 + 自动验证说明
        new_chapter.py . --prompt-only            # 仅生成子代理提示
        new_chapter.py . --subagent               # 兼容参数，行为同默认
        new_chapter.py . --subagent --lookback 5  # 子代理模式，回溯5章
        new_chapter.py . --subagent --auto-validate  # 子代理模式+自动验证
        new_chapter.py . --subagent --auto-validate --max-retries 5  # 最多重试5次
        new_chapter.py . --separate               # 自动分离章节
        new_chapter.py . 1 5                      # 生成第1卷第5章
    """
    # 检查帮助参数
    if "--help" in sys.argv or "-h" in sys.argv:
        print('用法: new_chapter.py <项目目录> [选项]')
        print('')
        print('选项:')
        print('  --auto              默认子代理模式 + 自动验证说明')
        print('  --prompt-only       仅生成子代理提示，不创建支架')
        print('  --subagent          兼容参数，正文生成默认即走子代理模式')
        print('  --separate          自动分离章节内容和工作卡')
        print('  --lookback N        兼容参数；subagent 主链路始终读取全部前文')
        print('  --auto-validate     生成后自动验证章节质量')
        print('  --max-retries N     验证失败最大重试次数（默认3）')
        print('  [vol] [ch]          指定卷和章（如: 1 5 表示第1卷第5章）')
        print('')
        print('示例:')
        print('  new_chapter.py .')
        print('  new_chapter.py . --auto')
        print('  new_chapter.py . --subagent')
        print('  new_chapter.py . --subagent --auto-validate')
        print('  new_chapter.py . --separate')
        print('  new_chapter.py . 1 5')
        sys.exit(0)

    if len(sys.argv) < 2:
        print('用法: new_chapter.py <项目目录> [选项]')
        print('')
        print('选项:')
        print('  --auto              默认子代理模式 + 自动验证说明')
        print('  --prompt-only       仅生成子代理提示，不创建支架')
        print('  --subagent          兼容参数，正文生成默认即走子代理模式')
        print('  --separate          自动分离章节内容和工作卡')
        print('  --lookback N        兼容参数；subagent 主链路始终读取全部前文')
        print('  --auto-validate     生成后自动验证章节质量')
        print('  --max-retries N     验证失败最大重试次数（默认3）')
        print('  [vol] [ch]          指定卷和章（如: 1 5 表示第1卷第5章）')
        print('')
        print('示例:')
        print('  new_chapter.py .')
        print('  new_chapter.py . --auto')
        print('  new_chapter.py . --subagent')
        print('  new_chapter.py . --subagent --auto-validate')
        print('  new_chapter.py . --separate')
        print('  new_chapter.py . 1 5')
        sys.exit(1)

    project_dir = Path(sys.argv[1]).expanduser().resolve()
    if not project_dir.exists():
        print(f"项目目录不存在: {project_dir}")
        sys.exit(1)

    # 检测项目配置，如果没有则启动初始化向导
    state = load_project_state(project_dir)
    if not state or not state.get("basic_specs"):
        print(f"\n{'='*60}")
        print("【项目初始化】")
        print(f"{'='*60}")
        print("未检测到项目配置，启动初始化向导...\n")
        
        import subprocess
        result = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "init_wizard.py"), str(project_dir)],
            capture_output=False
        )
        if result.returncode != 0:
            print("❌ 初始化失败")
            sys.exit(1)
        print("\n✅ 初始化完成，请重新运行命令")
        sys.exit(0)

    try:
        ensure_writing_prerequisites(state)
    except ProjectStateError as exc:
        print(f"项目配置不完整：{exc}")
        sys.exit(1)

    # 解析参数
    subagent_mode = True
    separate_mode = False
    lookback = 0
    auto_mode = False
    prompt_only = False
    auto_validate = False
    consume_result_file = None
    max_retries = 3
    vol_num = None
    ch_num = None

    args_iter = iter(enumerate(sys.argv[2:], start=2))
    for i, arg in args_iter:
        if arg == "--auto":
            auto_mode = True
        elif arg == "--prompt-only":
            prompt_only = True
        elif arg == "--subagent":
            subagent_mode = True
        elif arg == "--separate":
            separate_mode = True
        elif arg == "--lookback":
            try:
                _, next_val = next(args_iter)
                lookback = int(next_val)
            except (StopIteration, ValueError):
                print("错误：--lookback 需要一个整数参数")
                sys.exit(1)
        elif arg == "--auto-validate":
            auto_validate = True
        elif arg == "--consume-task-result-file":
            try:
                _, next_val = next(args_iter)
                consume_result_file = next_val
            except StopIteration:
                print("错误：--consume-task-result-file 需要一个文件路径参数")
                sys.exit(1)
        elif arg == "--max-retries":
            try:
                _, next_val = next(args_iter)
                max_retries = int(next_val)
            except (StopIteration, ValueError):
                print("错误：--max-retries 需要一个整数参数")
                sys.exit(1)
        elif arg.isdigit() and vol_num is None:
            vol_num = int(arg)
        elif arg.isdigit() and vol_num is not None and ch_num is None:
            ch_num = int(arg)

    # 确定卷和章
    if vol_num is None:
        # 子代理模式也需要先获取进度
        temp_state = load_project_state(project_dir)
        if not temp_state:
            print("未找到项目状态文件")
            sys.exit(1)
        vol_num, ch_num, vol_name = get_next_chapter(project_dir)
    else:
        if ch_num is None:
            ch_num = 1
        vol_name = f"vol{vol_num:02d}"

    if consume_result_file:
        dispatcher = TaskChapterDispatcher(project_dir)
        try:
            raw_result = Path(consume_result_file).expanduser().resolve().read_text(encoding="utf-8")
            consume = dispatcher.consume_task_result(vol_num, ch_num, raw_result, validate=True)
        except FileNotFoundError:
            print(f"Task 结果文件不存在: {consume_result_file}")
            sys.exit(1)
        except TaskResultError as exc:
            print(f"Task 结果不合法: {exc}")
            sys.exit(1)

        print(f"\n{'='*60}")
        print(f"Task 结果消费：第{vol_num}卷第{ch_num}章")
        print(f"{'='*60}\n")
        print(f"正文文件: {consume.body_output}")
        print(f"工作卡文件: {consume.card_output}")
        if consume.validation_passed:
            print("✅ 章节验证通过")
            sys.exit(0)
        print("❌ 章节验证失败")
        for issue in consume.issues[:10]:
            print(f"  - {issue}")
        sys.exit(1)

    # 子代理模式（默认主链路）
    if subagent_mode:
        print(f"\n{'='*60}")
        print(f"子代理主链路：生成第{vol_num}卷第{ch_num}章")
        print(f"{'='*60}\n")

        if lookback != 0:
            print(f"提示：subagent 主链路已强制切换为读取全部前文，已忽略 --lookback {lookback}")

        if not prompt_only:
            chapter_path = create_chapter_scaffold(project_dir, vol_num, ch_num, vol_name, state)
            print(f"章节支架已创建: {chapter_path}")
            print(f"工作卡支架已创建: {chapter_card_file(project_dir, vol_num, ch_num)}")

        result = generate_chapter_with_subagent(
            project_dir,
            vol_num,
            ch_num,
            lookback
        )

        if result["status"] == "task_request_ready":
            print(f"✅ Task 章节生成请求已准备就绪")
            print(f"   - 提示文件: {result['prompt_file']}")
            print(f"   - 请求文件: {result['request_file']}")
            print(f"   - 上下文 manifest: {result['manifest_file']}")
            print(f"   - context_manifest_id: {result['context_manifest_id']}")
            print(f"   - 提示长度: {result['prompt_length']} 字符")
            print(f"   - 已装载前文章节: {result['chapters_loaded']} 章")
            print(f"   - 必读文件总数: {result['required_files']} 个")
            print(f"   - 生成耗时: {result['generation_time']:.2f} 秒")
            print(f"\n后续执行约束:")
            print(f"1. 使用 Task/子代理先读取提示文件: {result['prompt_file']}")
            print(f"2. 子代理必须先读取 manifest: {result['manifest_file']}，再按 required_read_sequence 读取全部前文")
            print(f"3. Task 必须返回严格 JSON，并带上 context_manifest_id 与 files_read")
            print(f"4. 生成完成后运行: python3 scripts/new_chapter.py {project_dir} {vol_num} {ch_num} --consume-task-result-file <task_result.json>")
            print(f"5. 正文只写入: {result['body_output']}")
            print(f"6. 工作卡只写入: {result['card_output']}")
            print(f"7. 正文文件禁止出现 `## 内部工作卡`")

            if auto_validate:
                print(f"\n{'='*60}")
                print(f"【自动验证模式】")
                print(f"{'='*60}")
                print("当前仅在 Task 产出正文与工作卡后再执行验证。")
                print("生成完成后运行：python3 scripts/chapter_validator.py <项目目录> {} {}".format(vol_num, ch_num))
        else:
            print(f"❌ 错误: {result.get('error', '未知错误')}")

        return

    # 自动分离模式
    if separate_mode:
        print(f"\n{'='*60}")
        print(f"自动分离模式：分离第{vol_num}卷第{ch_num}章")
        print(f"{'='*60}\n")

        generator = SubagentChapterGenerator(project_dir)
        result = generator.auto_separate_after_generation(vol_num, ch_num)

        if result["status"] == "success":
            print(f"✅ {result['message']}")
            content_file = chapter_file(project_dir, vol_num, ch_num)
            card_file = chapter_card_file(project_dir, vol_num, ch_num)
            print(f"   - 正文文件: {content_file}")
            print(f"   - 工作卡文件: {card_file}")
        elif result["status"] == "already_separated":
            print(f"✅ {result['message']}")
        else:
            print(f"❌ {result['message']}")

        return

    return


if __name__ == "__main__":
    main()
