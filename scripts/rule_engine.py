#!/usr/bin/env python3
"""Shared result models and helpers for chapter/volume checks."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class CheckResult:
    name: str
    passed: bool
    details: str
    suggestion: str
    severity: str = "none"
    scope: str = "none"
    fix_method: str = "none"


def build_fix_plan(results: list[CheckResult], include_all: bool = False) -> dict:
    regenerate_items = [result for result in results if result.fix_method == "regenerate"]
    polish_items = [result for result in results if result.fix_method == "ai_polish"]

    payload = {
        "regenerate": [{"name": r.name, "details": r.details, "severity": r.severity} for r in regenerate_items],
        "ai_polish": [{"name": r.name, "details": r.details, "severity": r.severity} for r in polish_items],
        "total_regenerate": len(regenerate_items),
        "total_polish": len(polish_items),
    }
    if include_all:
        payload["all_results"] = [asdict(result) for result in results]
    return payload


def passed_count(results: list[CheckResult]) -> int:
    return sum(1 for result in results if result.passed)
