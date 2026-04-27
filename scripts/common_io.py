#!/usr/bin/env python3
"""Common state and reference IO helpers for dream scripts.

Note: This module provides general-purpose utilities for the context optimization system.
For chapter card parsing specifically, see card_parser.py which has specialized functions
for the existing chapter format.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from chapter_scan import chapter_file_by_number


class ProjectStateError(ValueError):
    """Raised when the project state is missing required locked fields."""


def _coerce_positive_int(value, field_name: str) -> int:
    if isinstance(value, bool):
        raise ProjectStateError(f"字段 {field_name} 不能是布尔值")
    if isinstance(value, int):
        parsed = value
    elif isinstance(value, str) and value.strip().isdigit():
        parsed = int(value.strip())
    else:
        raise ProjectStateError(f"字段 {field_name} 缺失或格式非法")

    if parsed <= 0:
        raise ProjectStateError(f"字段 {field_name} 必须是正整数")
    return parsed


def require_chapter_word_range(state: dict) -> tuple[int, int]:
    """Return the locked chapter word range or raise.

    All runtime writing scripts must read the numeric locked fields instead of
    silently falling back to baked-in defaults.
    """
    specs = state.get("basic_specs")
    if not isinstance(specs, dict):
        raise ProjectStateError("项目状态缺少 basic_specs，无法确定章节字数范围")

    min_words = _coerce_positive_int(specs.get("chapter_length_min"), "basic_specs.chapter_length_min")
    max_words = _coerce_positive_int(specs.get("chapter_length_max"), "basic_specs.chapter_length_max")
    if max_words < min_words:
        raise ProjectStateError("章节字数范围非法：chapter_length_max 不能小于 chapter_length_min")

    return min_words, max_words


def require_locked_protagonist_gender(state: dict) -> str:
    """Ensure protagonist gender is explicitly locked to 男 or 女."""
    protagonist = state.get("protagonist")
    if not isinstance(protagonist, dict):
        raise ProjectStateError("项目状态缺少 protagonist，无法确认主角性别")

    gender = protagonist.get("gender")
    if gender not in {"男", "女"}:
        raise ProjectStateError("项目未锁定主角性别，请先在初始化中明确选择主角为男性或女性")

    return gender


def parse_date(text: str) -> tuple[int, int, int]:
    """解析日期文本为 (year, month, day)
    
    Args:
        text: 日期文本，如 "2024-04-21" 或 "2024年4月21日"
        
    Returns:
        (year, month, day) 元组
        
    Raises:
        ValueError: 无法解析日期
    """
    patterns = [
        (r"(\d{4})-(\d{1,2})-(\d{1,2})", (int, int, int)),
        (r"(\d{4})年(\d{1,2})月(\d{1,2})日", (int, int, int)),
        (r"(\d{4})年(\d{1,2})月", (int, int, None)),
    ]
    
    for pattern, _ in patterns:
        match = re.search(pattern, text)
        if match:
            groups = match.groups()
            year = int(groups[0])
            month = int(groups[1])
            day = int(groups[2]) if groups[2] else 1
            # 验证月/日范围
            if not (1 <= month <= 12):
                raise ValueError(f"无效的月份: {month}")
            if not (1 <= day <= 31):
                raise ValueError(f"无效的日期: {day}")
            return year, month, day
    
    raise ValueError(f"无法解析日期: {text}")


def format_time_period(hour: int) -> str:
    """根据小时返回时段描述
    
    Args:
        hour: 小时 (0-23)
        
    Returns:
        时段描述：清晨/正午/下午/傍晚/深夜
    """
    if not isinstance(hour, int) or not (0 <= hour <= 23):
        raise ValueError(f"hour 必须为 0-23 的整数，当前值: {hour}")
    if 5 <= hour < 11:
        return "清晨"
    elif 11 <= hour < 14:
        return "正午"
    elif 14 <= hour < 18:
        return "下午"
    elif 18 <= hour < 21:
        return "傍晚"
    else:
        return "深夜"


def load_project_state(project_dir: Path) -> dict:
    state_file = project_dir / "wizard_state.json"
    if state_file.exists():
        try:
            return json.loads(state_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise ValueError(f"项目状态文件损坏: {state_file}: {e}") from e

    config_file = project_dir / ".project_config.json"
    if config_file.exists():
        try:
            return json.loads(config_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise ValueError(f"项目配置文件损坏: {config_file}: {e}") from e

    return {}


def get_chapters_per_volume(project_dir: Path) -> int:
    """动态获取每卷章节数，不写死默认值

    Args:
        project_dir: 项目目录

    Returns:
        每卷章节数

    Raises:
        ValueError: 无法从项目状态确定每卷章节数
    """
    state = load_project_state(project_dir)

    # 优先从 volume_architecture 读取
    arch = state.get("volume_architecture", {})
    if isinstance(arch, dict) and "chapters_per_volume" in arch:
        return arch["chapters_per_volume"]

    # 回退到 basic_specs
    specs = state.get("basic_specs", {})
    if "chapters_per_volume" in specs:
        return specs["chapters_per_volume"]

    # 从 derived 计算结果读取
    derived = specs.get("derived", {})
    if "derived_chapters_per_volume" in derived:
        return derived["derived_chapters_per_volume"]

    # 从目标字数和章节数推算
    target_chapters = derived.get("target_total_chapters", 0)
    target_volumes = derived.get("derived_total_volumes", 0)
    if target_chapters > 0 and target_volumes > 0:
        return target_chapters // target_volumes

    # 无法确定时抛出异常
    raise ValueError(f"无法从项目状态确定 chapters_per_volume，请检查 {project_dir} 的配置")


def save_project_state(project_dir: Path, state: dict) -> None:
    project_dir.mkdir(parents=True, exist_ok=True)
    state_file = project_dir / "wizard_state.json"
    state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def load_volume_outline(project_dir: Path, volume_index: int) -> dict:
    outline_path = project_dir / "reference" / "卷纲总表.md"
    if not outline_path.exists():
        return {}

    text = outline_path.read_text(encoding="utf-8")

    pattern = rf"(^##\s+第{volume_index}卷.+?)(?=^##\s+|\Z)"
    match = re.search(pattern, text, re.M | re.S)
    if not match:
        return {}

    lines = [line.rstrip() for line in match.group(1).splitlines() if line.strip()]
    data = {"卷标题": lines[0].removeprefix("##").strip() if lines else ""}
    for line in lines[1:]:
        line = line.strip()
        if line.startswith("- ") and "：" in line:
            key, value = line[2:].split("：", 1)
            data[key.strip()] = value.strip()
    return data


def load_json_file(file_path: Path, default: dict | list | None = None):
    if not file_path.exists():
        return {} if default is None else default
    return json.loads(file_path.read_text(encoding="utf-8"))


def save_json_file(file_path: Path, payload: dict | list) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def extract_body(content: str) -> str:
    """从章节内容中提取正文部分
    
    与 card_parser.py 的 extract_body 区别：
    - card_parser: 查找"## 正文"标记
    - 本函数: 查找"## 内部工作卡"标记
    
    Args:
        content: 完整章节内容
    
    Returns:
        正文内容（不包含标题和内部工作卡）
    """
    marker = "## 内部工作卡"
    idx = content.find(marker)
    if idx != -1:
        body = content[:idx]
    else:
        body = content

    lines = body.splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    # Strip leading blank lines after title removal
    while lines and not lines[0].strip():
        lines.pop(0)
    # Strip trailing blank lines
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)


def extract_section(content: str, section_title: str) -> str:
    """从章节内容中提取指定章节
    
    与 card_parser.py 的 extract_section 区别：
    - card_parser: 查找"### "作为停止标记
    - 本函数: 使用动态 heading level 检测停止位置
    
    Args:
        content: 完整章节内容
        section_title: 章节标题，如 "### 1. 状态卡"
    
    Returns:
        章节内容（不包含标题），未找到时返回空字符串
    """
    heading_level = len(section_title) - len(section_title.lstrip("#"))
    pattern = rf"^{re.escape(section_title)}\s*$"
    match = re.search(pattern, content, re.M)
    if not match:
        return ""

    start = match.end()
    rest = content[start:]
    stop_pattern = rf"^#{{{1},{heading_level}}}\s+"
    stop_match = re.search(stop_pattern, rest, re.M)
    if stop_match:
        return rest[:stop_match.start()].strip()
    return rest.strip()


def extract_bullets(section_content: str) -> dict[str, str]:
    """从章节内容中提取要点列表
    
    与 card_parser.py 的 extract_bullets 区别：
    - card_parser: 过滤掉占位符值（"（待填）"、"[更新]"）
    - 本函数: 不过滤任何值
    
    Args:
        section_content: 章节内容
    
    Returns:
        要点字典，格式 {"要点1": "内容", "要点2": "内容"}
    """
    result: dict[str, str] = {}
    for line in section_content.splitlines():
        line = line.strip()
        m = re.match(r"^-\s+(.+?)[：:]\s*(.+)$", line)
        if m:
            result[m.group(1).strip()] = m.group(2).strip()
    return result


def find_chapter_path(project_dir: Path, chapter_num: int) -> Path | None:
    """根据章节号查找章节文件路径

    Args:
        project_dir: 项目目录
        chapter_num: 章节号（从1开始）

    Returns:
        章节文件路径，不存在时返回 None
    """
    try:
        chapters_per_volume = get_chapters_per_volume(project_dir)
    except ValueError:
        chapters_per_volume = 10  # 安全回退

    vol_num = (chapter_num - 1) // chapters_per_volume + 1
    chapter_in_volume = (chapter_num - 1) % chapters_per_volume + 1

    chapter_path = chapter_file_by_number(project_dir, vol_num, chapter_in_volume)
    if chapter_path is not None:
        return chapter_path

    vol_name = f"vol{vol_num:02d}"
    chapters_dir = project_dir / "chapters" / vol_name
    
    # 尝试多种文件命名格式
    patterns = [
        f"ch{chapter_in_volume:02d}.md",
        f"{chapter_in_volume:03d}_第{chapter_in_volume}章.md",
        f"chapter_{chapter_in_volume:02d}.md",
        f"{chapter_in_volume}.md",
    ]
    
    for pattern in patterns:
        chapter_file = chapters_dir / pattern
        if chapter_file.exists():
            return chapter_file
    
    return None


def extract_all_bullets(section_content: str) -> list[str]:
    """从章节内容中提取所有要点
    
    Args:
        section_content: 章节内容
    
    Returns:
        要点列表，不解析键值对
    """
    bullets: list[str] = []
    for line in section_content.splitlines():
        line = line.strip()
        if line.startswith("- "):
            bullets.append(line[2:].strip())
    return bullets
