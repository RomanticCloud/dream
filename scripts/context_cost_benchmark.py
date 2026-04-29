#!/usr/bin/env python3
"""Compare compact-context request size with legacy full-context request size."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from body_dispatcher import BodyDispatcher


def benchmark(project_dir: Path, vol: int, ch: int) -> dict:
    dispatcher = BodyDispatcher(project_dir)
    compact = dispatcher.dispatch(vol, ch, context_mode="fast")
    full = dispatcher.dispatch(vol, ch, context_mode="full")
    compact_prompt = Path(compact.prompt_file).read_text(encoding="utf-8") if compact.prompt_file else ""
    full_prompt = Path(full.prompt_file).read_text(encoding="utf-8") if full.prompt_file else ""
    compact_request = json.loads(Path(compact.request_file).read_text(encoding="utf-8")) if compact.request_file else {}
    full_request = json.loads(Path(full.request_file).read_text(encoding="utf-8")) if full.request_file else {}
    return {
        "vol": vol,
        "ch": ch,
        "compact": {
            "prompt_chars": len(compact_prompt),
            "required_files": compact_request.get("required_files", compact.required_files),
            "strategy": compact_request.get("strategy"),
        },
        "full": {
            "prompt_chars": len(full_prompt),
            "required_files": full_request.get("required_files", full.required_files),
            "strategy": full_request.get("strategy"),
        },
        "prompt_char_ratio": round(len(compact_prompt) / max(len(full_prompt), 1), 4),
        "required_file_ratio": round((compact_request.get("required_files", compact.required_files) or 0) / max((full_request.get("required_files", full.required_files) or 1), 1), 4),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="compact/full 上下文成本基准")
    parser.add_argument("project_dir")
    parser.add_argument("vol", type=int)
    parser.add_argument("ch", type=int)
    args = parser.parse_args()
    print(json.dumps(benchmark(Path(args.project_dir).expanduser().resolve(), args.vol, args.ch), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
