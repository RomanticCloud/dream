#!/usr/bin/env python3
"""Tests for planning_rules chapter and volume derivation."""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from planning_rules import describe_target_profile


def test_describe_target_profile_for_short_chapter_ranges():
    cases = [
        ("40万字", "2000-2500字", 178, 10, 18, (2000, 2500)),
        ("40万字", "2500-3500字", 133, 10, 14, (2500, 3500)),
        ("40万字", "3500-4500字", 100, 10, 10, (3500, 4500)),
        ("40万字", "4500-5500字", 80, 8, 10, (4500, 5500)),
    ]

    for word_target, chapter_length, total_chapters, total_volumes, chapters_per_volume, chapter_range in cases:
        profile = describe_target_profile(word_target, chapter_length)
        assert profile["target_total_chapters"] == total_chapters
        assert profile["derived_total_volumes"] == total_volumes
        assert profile["derived_chapters_per_volume"] == chapters_per_volume
        assert tuple(profile["chapter_words_range"]) == chapter_range


if __name__ == "__main__":
    import traceback

    passed = 0
    failed = 0
    for name, func in sorted(globals().items()):
        if name.startswith("test_"):
            try:
                func()
                print(f"  PASS {name}")
                passed += 1
            except Exception:
                print(f"  FAIL {name}")
                traceback.print_exc()
                failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
