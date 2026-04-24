#!/usr/bin/env python3
"""Field value validation rules for dream work cards."""

from __future__ import annotations

import re

from card_fields import (
    FIELD_CARRY_HOOK,
    FIELD_CARRY_MUST,
    FIELD_EMOTION_SUSPENSE,
    FIELD_POWER_AFTER_EFFECT,
    FIELD_POWER_CROSS,
    FIELD_POWER_LEVEL,
    FIELD_POWER_LOSS_RATIO,
    FIELD_POWER_NEW_TRUMP,
    FIELD_POWER_REASONABLE,
    FIELD_POWER_TARGET,
    FIELD_POWER_TRUMP_NAME,
    FIELD_RESOURCE_GAIN,
    FIELD_RESOURCE_LOSS,
    FIELD_RESOURCE_SPEND,
    FIELD_STATUS_ELAPSED,
    FIELD_STATUS_TIMEPOINT,
)

ELAPSED_PATTERN = re.compile(r"^(?:\d+(?:\.\d+)?(?:分钟|小时|天|日|个月|月|年)|半个?月|半天)$")
TIMEPOINT_PATTERN = re.compile(r"^(?:\d{4}-\d{1,2}-\d{1,2}|第\d+天(?:清晨|早晨|上午|中午|正午|下午|傍晚|晚上|深夜)?|第\d+日(?:清晨|早晨|上午|中午|正午|下午|傍晚|晚上|深夜)?|比ch\d+晚\d+天|比ch\d+早\d+天|ch\d+之后)$")
RESOURCE_DELTA_PATTERN = re.compile(r"[+-]\d+(?:\.\d+)?\s*[\u4e00-\u9fa5A-Za-z]+")
POWER_LOSS_RATIO_PATTERN = re.compile(r"^-\d+(?:\.\d+)?%?(?:战力)?$")

SUSPENSE_MIN = 1
SUSPENSE_MAX = 10

ERROR_REQUIRED_FIELDS = [
    FIELD_STATUS_ELAPSED,
    FIELD_STATUS_TIMEPOINT,
    FIELD_CARRY_MUST,
]

WARNING_REQUIRED_FIELDS = [
    FIELD_CARRY_HOOK,
]

POWER_ERROR_REQUIRED_FIELDS = [
    FIELD_POWER_CROSS,
    FIELD_POWER_NEW_TRUMP,
    FIELD_POWER_LOSS_RATIO,
    FIELD_POWER_TRUMP_NAME,
]

POWER_WARNING_REQUIRED_FIELDS = [
    FIELD_POWER_TARGET,
    FIELD_POWER_LEVEL,
    FIELD_POWER_AFTER_EFFECT,
]

RESOURCE_DELTA_FIELDS = [
    FIELD_RESOURCE_GAIN,
    FIELD_RESOURCE_SPEND,
    FIELD_RESOURCE_LOSS,
]


def is_valid_elapsed(value: str) -> bool:
    return bool(ELAPSED_PATTERN.match(value.strip()))


def is_valid_timepoint(value: str) -> bool:
    return bool(TIMEPOINT_PATTERN.match(value.strip()))


def has_resource_delta(value: str) -> bool:
    return bool(RESOURCE_DELTA_PATTERN.search(value.strip()))


def parse_suspense_strength(value: str) -> int | None:
    text = value.strip()
    if not text.isdigit():
        return None
    score = int(text)
    if SUSPENSE_MIN <= score <= SUSPENSE_MAX:
        return score
    return None


def is_required_non_empty(value: str) -> bool:
    text = value.strip()
    return bool(text and text not in {"无", "暂无", "（待填）", "[更新]"})


def is_yes_no(value: str) -> bool:
    return value.strip() in {"是", "否"}


def is_valid_power_loss_ratio(value: str) -> bool:
    return bool(POWER_LOSS_RATIO_PATTERN.match(value.strip()))


def parse_power_loss_ratio(value: str) -> int | None:
    match = re.search(r"-(\d+(?:\.\d+)?)", value.strip())
    if not match:
        return None
    return int(float(match.group(1)))


def split_trump_names(value: str) -> list[str]:
    return [item.strip() for item in value.split("/") if item.strip()]
