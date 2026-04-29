#!/usr/bin/env python3
"""Run configured external models for dream generation.

Currently supports OpenAI-compatible chat completions. This script never stores
API keys in project files; it reads the configured environment variable.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from common_io import save_json_file
from model_config import is_external_backend, resolve_body_model


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _extract_json(text: str) -> dict:
    stripped = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", stripped, re.DOTALL)
    if fenced:
        stripped = fenced.group(1).strip()
    else:
        match = re.search(r"(\{.*\})", stripped, re.DOTALL)
        if match:
            stripped = match.group(1).strip()
    return json.loads(stripped)


def _append_jsonl(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _post_openai_compatible(model_config: dict, prompt: str) -> str:
    base_url = str(model_config.get("base_url", "")).rstrip("/")
    if not base_url:
        raise ValueError("模型配置缺少 base_url")
    api_key_env = model_config.get("api_key_env")
    if not api_key_env:
        raise ValueError("模型配置缺少 api_key_env")
    api_key = os.environ.get(str(api_key_env))
    if not api_key:
        raise ValueError(f"环境变量 {api_key_env} 未设置，无法调用外部模型")

    payload = {
        "model": model_config.get("model"),
        "messages": [
            {"role": "system", "content": "你是严格遵循 JSON 输出协议的中文长篇小说正文生成器。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": model_config.get("temperature", 0.8),
        "max_tokens": model_config.get("max_tokens", 6000),
        "response_format": {"type": "json_object"},
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=int(model_config.get("timeout", 180))) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"模型 API 请求失败: HTTP {exc.code}: {detail}") from exc
    return response_payload["choices"][0]["message"]["content"]


def run_body(request_file: Path) -> dict:
    request = _load_json(request_file)
    project_dir = Path(request.get("project_dir") or request_file.parent.parent).resolve()
    model_config = resolve_body_model(project_dir)
    if not is_external_backend(model_config):
        raise ValueError("当前正文模型配置不是外部 API backend，无需 model_runner 执行")
    prompt_file = Path(request["prompt_file"])
    prompt = prompt_file.read_text(encoding="utf-8")
    raw_file = project_dir / "context" / "latest_model_raw_response.txt"
    payload = None
    content = ""
    errors: list[str] = []
    started = time.time()
    max_attempts = int(model_config.get("retries", 3))
    for attempt in range(1, max_attempts + 1):
        try:
            content = _post_openai_compatible(model_config, prompt)
            raw_file.parent.mkdir(parents=True, exist_ok=True)
            raw_file.write_text(content, encoding="utf-8")
            payload = _extract_json(content)
            break
        except Exception as exc:
            errors.append(f"attempt {attempt}: {exc}")
            if attempt < max_attempts:
                time.sleep(min(2 ** (attempt - 1), 8))
    if payload is None:
        _append_jsonl(project_dir / "context" / "model_call_log.jsonl", {
            "status": "error",
            "provider": model_config.get("provider"),
            "model": model_config.get("model"),
            "duration_seconds": round(time.time() - started, 3),
            "prompt_chars": len(prompt),
            "response_chars": len(content),
            "raw_response": str(raw_file),
            "errors": errors,
        })
        raise RuntimeError("外部模型调用失败: " + " | ".join(errors[-3:]))
    if payload.get("status") != "success":
        raise RuntimeError(payload.get("error", "模型返回失败状态"))
    body = payload.get("chapter_body", "")
    if not body or "## 正文" not in body or "## 内部工作卡" in body:
        raise ValueError("模型返回的 chapter_body 格式不合格")
    if payload.get("context_manifest_id") != request.get("context_manifest_id"):
        raise ValueError("模型返回 context_manifest_id 与请求不一致")
    required_files = request.get("required_context_files") or []
    if not required_files and request.get("manifest_file"):
        manifest = _load_json(Path(request["manifest_file"]))
        required_files = manifest.get("required_read_sequence") or []
    files_read = payload.get("files_read")
    if set(files_read or []) != set(required_files):
        raise ValueError("模型返回 files_read 未覆盖必读上下文")

    body_output = Path(request["body_output"])
    body_output.parent.mkdir(parents=True, exist_ok=True)
    body_output.write_text(body.rstrip() + "\n", encoding="utf-8")
    proof_file = Path(request["proof_file"])
    save_json_file(proof_file, {
        "status": "success",
        "context_manifest_id": payload.get("context_manifest_id"),
        "files_read": files_read,
        "body_file": str(body_output),
        "model": {
            "provider": model_config.get("provider"),
            "backend": model_config.get("backend"),
            "model": model_config.get("model"),
        },
    })
    result_file = project_dir / "context" / "latest_model_body_result.json"
    metrics = {
        "status": "success",
        "provider": model_config.get("provider"),
        "model": model_config.get("model"),
        "duration_seconds": round(time.time() - started, 3),
        "prompt_chars": len(prompt),
        "response_chars": len(content),
        "output_chars": len(body),
        "raw_response": str(raw_file),
        "attempts": len(errors) + 1,
    }
    _append_jsonl(project_dir / "context" / "model_call_log.jsonl", metrics)
    save_json_file(project_dir / "context" / "generation_metrics.json", metrics)
    save_json_file(result_file, {
        "status": "success",
        "body_output": str(body_output),
        "proof_file": str(proof_file),
        "result_file": str(result_file),
        "model": {
            "provider": model_config.get("provider"),
            "backend": model_config.get("backend"),
            "model": model_config.get("model"),
        },
        "metrics": metrics,
    })
    return _load_json(result_file)


def main() -> int:
    parser = argparse.ArgumentParser(description="按配置调用外部模型")
    subparsers = parser.add_subparsers(dest="command", required=True)
    body_parser = subparsers.add_parser("body")
    body_parser.add_argument("--request-file", required=True)
    body_parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "body":
            payload = run_body(Path(args.request_file).expanduser().resolve())
        else:
            raise ValueError(f"未知命令: {args.command}")
    except Exception as exc:
        payload = {"status": "error", "error": str(exc)}
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
