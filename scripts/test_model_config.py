#!/usr/bin/env python3
"""Tests for configurable body generation model."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from body_dispatcher import BodyDispatcher
from model_config import resolve_body_model
from model_config import body_model_options
from test_quality_gates import _chapter, _state, CARD1
from continuity_ledger import rebuild_ledger


def test_project_can_select_deepseek_body_model():
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)
        _state(project_dir)
        _chapter(project_dir, 1, "# 第1章\n\n## 正文\n\n旧仓库门口，陆明收到警告。", CARD1)
        rebuild_ledger(project_dir)
        (project_dir / "dream_model_config.json").write_text(json.dumps({
            "body": {
                "provider": "deepseek",
                "model": "deepseek-v4-pro",
                "temperature": 0.7,
                "max_tokens": 5000,
            }
        }, ensure_ascii=False), encoding="utf-8")

        resolved = resolve_body_model(project_dir)
        assert resolved["provider"] == "deepseek"
        assert resolved["backend"] == "openai_compatible"
        assert resolved["api_key_env"] == "DEEPSEEK_API_KEY"
        assert resolved["base_url"] == "https://api.deepseek.com"
        assert resolved["context_window_tokens"] == 1000000

        dispatch = BodyDispatcher(project_dir).dispatch(1, 2)
        request = json.loads(Path(dispatch.request_file).read_text(encoding="utf-8"))
        assert request["model"]["provider"] == "deepseek"
        assert request["model_runner_command"].startswith("python3 scripts/model_runner.py body")


def test_kimi_model_option_exists():
    labels = {option["label"] for option in body_model_options()}
    assert "kimi/kimi-k2.6" in labels
