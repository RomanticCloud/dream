#!/usr/bin/env python3
"""Unified chapter body and work-card parsing helpers."""

from __future__ import annotations


BODY_MARKER = "## 正文"
CARD_MARKER = "## 内部工作卡"


def split_card_line(line: str) -> tuple[str, str] | None:
    if "：" in line:
        return line.split("：", 1)
    if ":" in line:
        return line.split(":", 1)
    return None


def extract_body(content: str) -> str:
    start = content.find(BODY_MARKER)
    if start == -1:
        return content
    start += len(BODY_MARKER)
    end = content.find(CARD_MARKER, start)
    if end == -1:
        end = len(content)
    return content[start:end].strip()


def extract_section(content: str, header: str) -> str:
    start = content.find(header)
    if start == -1:
        return ""
    start += len(header)
    rest = content[start:]
    next_header = rest.find("### ")
    if next_header != -1:
        rest = rest[:next_header]
    return rest.strip()


def extract_bullets(section: str) -> dict[str, str]:
    data: dict[str, str] = {}
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped.startswith("-"):
            continue
        parts = split_card_line(stripped[1:])
        if not parts:
            continue
        key, value = parts[0].strip(), parts[1].strip()
        if value and value not in {"（待填）", "[更新]"}:
            data[key] = value
    return data


def filled_bullet_stats(section: str) -> tuple[int, int]:
    filled = 0
    total = 0
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped.startswith("-"):
            continue
        total += 1
        parts = split_card_line(stripped[1:])
        if not parts:
            continue
        value = parts[1].strip()
        if value and value not in {"", "（待填）", "[更新]"}:
            filled += 1
    return filled, total
