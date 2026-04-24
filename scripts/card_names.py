#!/usr/bin/env python3
"""Canonical work-card headers for dream runtime code."""

STATUS_CARD = "### 1. 状态卡"
PLOT_CARD = "### 2. 情节卡"
POWER_CARD = "### 2. 战力卡"
RESOURCE_CARD = "### 3. 资源卡"
RELATION_CARD = "### 4. 关系卡"
EMOTION_CARD = "### 5. 情绪弧线卡"
CARRY_CARD = "### 6. 承上启下卡"

STANDARD_CARD_HEADERS = [
    STATUS_CARD,
    PLOT_CARD,
    RESOURCE_CARD,
    RELATION_CARD,
    EMOTION_CARD,
    CARRY_CARD,
]

POWER_CARD_HEADERS = [
    STATUS_CARD,
    POWER_CARD,
    RESOURCE_CARD,
    RELATION_CARD,
    EMOTION_CARD,
    CARRY_CARD,
]

POWER_GENRES = {"都市高武", "玄幻奇幻", "仙侠修真"}


def is_power_project(state: dict) -> bool:
    specs = state.get("basic_specs", {})
    genres = specs.get("main_genres", specs.get("genres", []))
    return any(genre in POWER_GENRES for genre in genres)


def required_card_headers(state: dict) -> list[str]:
    return POWER_CARD_HEADERS if is_power_project(state) else STANDARD_CARD_HEADERS
