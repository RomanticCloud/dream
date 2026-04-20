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


def load_project_state(project_dir: Path) -> dict:
    state_file = project_dir / "wizard_state.json"
    if state_file.exists():
        return json.loads(state_file.read_text(encoding="utf-8"))

    config_file = project_dir / ".project_config.json"
    if config_file.exists():
        return json.loads(config_file.read_text(encoding="utf-8"))

    return {}


def save_project_state(project_dir: Path, state: dict) -> None:
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
    chapters_per_volume = 10  # 默认值
    state_file = project_dir / "wizard_state.json"
    if state_file.exists():
        state = json.loads(state_file.read_text(encoding="utf-8"))
        arch = state.get("volume_architecture", {})
        chapters_per_volume = arch.get("chapters_per_volume", 10)

    vol_num = (chapter_num - 1) // chapters_per_volume + 1
    vol_name = f"vol{vol_num:02d}"
    chapter_file = project_dir / "chapters" / vol_name / f"{chapter_num:03d}_第{chapter_num}章.md"

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
