#!/usr/bin/env python3
"""Tests for strict initialization requirements."""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from common_io import ProjectStateError
from init_wizard import validate_final_state_requirements


def test_validate_final_state_requires_locked_gender():
    state = {
        "basic_specs": {
            "chapter_length_min": 2000,
            "chapter_length_max": 2500,
        },
        "protagonist": {},
    }

    try:
        validate_final_state_requirements(state)
        raise AssertionError("expected ProjectStateError")
    except ProjectStateError as exc:
        assert "主角性别" in str(exc)


def test_validate_final_state_requires_numeric_word_range():
    state = {
        "basic_specs": {
            "chapter_length": "2000-2500字",
        },
        "protagonist": {"gender": "男"},
    }

    try:
        validate_final_state_requirements(state)
        raise AssertionError("expected ProjectStateError")
    except ProjectStateError as exc:
        assert "chapter_length_min" in str(exc)


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
