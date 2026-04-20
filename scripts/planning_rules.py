#!/usr/bin/env python3
"""Planning rule helpers for the dream skill."""

from __future__ import annotations

import math


WORD_COUNT_MAP = {
    "30万字": 300_000,
    "40万字": 400_000,
    "50万字": 500_000,
    "100万字": 1_000_000,
}

CHAPTER_WORD_MAP = {
    "3500-4500字": (3500, 4500),
    "4500-5500字": (4500, 5500),
}

TARGET_VOLUME_OPTIONS = [3, 4, 5, 6, 8, 10]


def parse_word_target(label: str) -> int:
    if "万字" in label:
        return int(label.replace("万字", "")) * 10000
    if "万" in label:
        return int(label.replace("万", "")) * 10000
    return int(label) if label.isdigit() else 400_000


def parse_chapter_length(label: str) -> tuple[int, int]:
    return CHAPTER_WORD_MAP.get(label, (4000, 5000))


def chapter_word_average(label: str) -> int:
    low, high = parse_chapter_length(label)
    return (low + high) // 2


def derive_total_chapters(word_target_label: str, chapter_length_label: str) -> int:
    total_words = parse_word_target(word_target_label)
    avg_words = chapter_word_average(chapter_length_label)
    chapters = max(30, round(total_words / max(avg_words, 1)))
    return chapters


def _volume_penalty(total_chapters: int, volume_count: int) -> tuple[int, int]:
    chapters_per_volume = math.ceil(total_chapters / volume_count)
    if 8 <= chapters_per_volume <= 15:
        penalty = abs(chapters_per_volume - 10)
    else:
        penalty = 100 + abs(chapters_per_volume - 10)
    return penalty, chapters_per_volume


def recommend_volume_plan(total_chapters: int) -> dict:
    candidates = []
    for volume_count in TARGET_VOLUME_OPTIONS:
        penalty, chapters_per_volume = _volume_penalty(total_chapters, volume_count)
        candidates.append(
            {
                "volume_count": volume_count,
                "chapters_per_volume": chapters_per_volume,
                "penalty": penalty,
            }
        )

    candidates.sort(key=lambda item: (item["penalty"], abs(item["volume_count"] - 5)))
    best = candidates[0]
    return {
        "recommended_volume_count": best["volume_count"],
        "recommended_chapters_per_volume": best["chapters_per_volume"],
        "candidates": candidates,
    }


def volume_label(volume_count: int) -> str:
    return f"{volume_count}卷" if volume_count < 10 else "10卷+"


def describe_target_profile(word_target_label: str, chapter_length_label: str) -> dict:
    total_chapters = derive_total_chapters(word_target_label, chapter_length_label)
    recommendation = recommend_volume_plan(total_chapters)
    return {
        "target_words_numeric": parse_word_target(word_target_label),
        "chapter_words_range": parse_chapter_length(chapter_length_label),
        "chapter_words_avg": chapter_word_average(chapter_length_label),
        "target_total_chapters": total_chapters,
        "derived_total_volumes": recommendation["recommended_volume_count"],
        "derived_chapters_per_volume": recommendation[
            "recommended_chapters_per_volume"
        ],
        "volume_candidates": recommendation["candidates"],
    }