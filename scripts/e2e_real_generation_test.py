#!/usr/bin/env python3
"""End-to-end real generation driver for a prepared project."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent


def _run(cmd: list[str], *, env: dict | None = None, check: bool = True) -> dict:
    result = subprocess.run(cmd, cwd=SCRIPT_DIR.parent, capture_output=True, text=True, env=env or os.environ.copy())
    if check and result.returncode != 0:
        raise RuntimeError(f"命令失败: {' '.join(cmd)}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"status": "text", "stdout": result.stdout, "stderr": result.stderr, "returncode": result.returncode}


def run_e2e(project_dir: Path, chapters: int, provider: str) -> dict:
    env = os.environ.copy()
    generated = []
    for _ in range(chapters):
        dispatch = _run([sys.executable, "scripts/continuous_writer.py", "run", str(project_dir), "--generation-mode", "auto"], env=env)
        if dispatch.get("status") == "chapter_ready":
            generated.append(dispatch)
            continue
        if dispatch.get("status") != "body_required":
            raise RuntimeError(f"期望 body_required，实际: {dispatch}")
        if dispatch.get("model_runner_command"):
            _run(dispatch["model_runner_command"].split(), env=env)
        else:
            raise RuntimeError("当前 E2E 脚本只执行外部模型 model_runner_command")
        ready = _run([sys.executable, "scripts/continuous_writer.py", "run", str(project_dir), "--generation-mode", "auto"], env=env)
        if ready.get("status") == "cards_required":
            ready = _run([sys.executable, "scripts/continuous_writer.py", "run", str(project_dir), "--generation-mode", "auto"], env=env)
        if ready.get("status") != "chapter_ready":
            raise RuntimeError(f"章节未通过: {ready}")
        generated.append(ready)
    volume = _run([sys.executable, "scripts/volume_ending_checker.py", str(project_dir), "1"], env=env, check=False)
    report = project_dir / "VOLUME_ENDING_REPORT.md"
    return {
        "status": "success" if report.exists() else "missing_report",
        "project_dir": str(project_dir),
        "provider": provider,
        "generated": generated,
        "volume_check_return": volume.get("returncode", 0),
        "report": str(report),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="真实端到端生成测试")
    parser.add_argument("--project-dir", required=True)
    parser.add_argument("--provider", default="deepseek")
    parser.add_argument("--chapters", type=int, default=3)
    args = parser.parse_args()
    try:
        payload = run_e2e(Path(args.project_dir).expanduser().resolve(), args.chapters, args.provider)
    except Exception as exc:
        payload = {"status": "error", "error": str(exc)}
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
