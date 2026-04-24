#!/usr/bin/env python3
"""Prepare, validate and consume task-driven chapter generation requests."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from chapter_validator import validate_chapter
from chapter_view import save_split_chapter
from common_io import save_json_file
from path_rules import chapter_card_file, chapter_file
from subagent_chapter_generator import SubagentChapterGenerator


@dataclass
class DispatchResult:
    status: str
    prompt_file: str
    request_file: str
    manifest_file: str
    context_manifest_id: str
    prompt_length: int
    generation_time: float
    chapters_loaded: int
    required_files: int
    body_output: str
    card_output: str
    mode: str = "task_subagent"


@dataclass
class ConsumeResult:
    status: str
    vol: int
    ch: int
    body_output: str
    card_output: str
    validation_passed: bool
    issues: list[str]


class TaskResultError(ValueError):
    """Raised when the task result cannot be parsed or validated."""


class TaskChapterDispatcher:
    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        self.generator = SubagentChapterGenerator(project_dir)

    def dispatch(self, vol_num: int, ch_num: int, lookback: int = 0) -> DispatchResult | dict:
        result = self.generator.dispatch_chapter_generation(vol_num, ch_num, lookback)
        if result.get("status") != "prompt_ready":
            return result

        prompt_file = Path(result["prompt_file"])
        request_file = self.project_dir / "context" / "latest_task_request.json"
        payload = {
            "generator": "dream/scripts/task_dispatcher.py",
            "mode": "task_subagent",
            "strategy": "subagent_read_all_previous",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "vol": vol_num,
            "ch": ch_num,
            "prompt_file": str(prompt_file),
            "manifest_file": result.get("manifest_file", ""),
            "context_manifest_id": result.get("context_manifest_id", ""),
            "body_output": str(chapter_file(self.project_dir, vol_num, ch_num)),
            "card_output": str(chapter_card_file(self.project_dir, vol_num, ch_num)),
            "chapters_loaded": result.get("chapters_loaded", 0),
            "required_files": result.get("required_files", 0),
            "prompt_length": result.get("prompt_length", 0),
            "requirements": {
                "split_files": True,
                "body_forbidden_marker": "## 内部工作卡",
                "card_required_marker": "## 内部工作卡",
                "context_manifest_id": result.get("context_manifest_id", ""),
                "read_all_previous": True,
            },
        }
        save_json_file(request_file, payload)
        return DispatchResult(
            status="task_request_ready",
            prompt_file=str(prompt_file),
            request_file=str(request_file),
            manifest_file=payload["manifest_file"],
            context_manifest_id=payload["context_manifest_id"],
            prompt_length=result.get("prompt_length", 0),
            generation_time=result.get("generation_time", 0.0),
            chapters_loaded=result.get("chapters_loaded", 0),
            required_files=payload["required_files"],
            body_output=payload["body_output"],
            card_output=payload["card_output"],
        )

    def _load_expected_request(self, vol_num: int, ch_num: int) -> dict:
        request_file = self.project_dir / "context" / "latest_task_request.json"
        if not request_file.exists():
            raise TaskResultError("缺少 latest_task_request.json，无法校验 subagent 读取约束")
        payload = json.loads(request_file.read_text(encoding="utf-8"))
        if payload.get("vol") != vol_num or payload.get("ch") != ch_num:
            raise TaskResultError("latest_task_request.json 与当前卷章不匹配")
        return payload

    def parse_task_result(self, raw_result: str | dict, *, expected_manifest_id: str, required_files: list[str]) -> dict:
        if isinstance(raw_result, dict):
            payload = raw_result
        else:
            text = raw_result.strip()
            fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
            if fenced:
                text = fenced.group(1).strip()
            else:
                json_match = re.search(r"(\{.*\})", text, re.DOTALL)
                if json_match:
                    text = json_match.group(1).strip()
            try:
                payload = json.loads(text)
            except json.JSONDecodeError as exc:
                raise TaskResultError(f"Task 返回结果不是合法 JSON：{exc}") from exc

        if payload.get("status") == "error":
            raise TaskResultError(payload.get("error", "Task 返回错误状态"))

        chapter_body = payload.get("chapter_body", "")
        chapter_cards = payload.get("chapter_cards", "")
        context_manifest_id = payload.get("context_manifest_id")
        files_read = payload.get("files_read")
        if context_manifest_id != expected_manifest_id:
            raise TaskResultError("Task 返回的 context_manifest_id 与请求不一致")
        if not isinstance(files_read, list) or not files_read:
            raise TaskResultError("Task 返回缺少 files_read")
        if any(not isinstance(item, str) or not item.strip() for item in files_read):
            raise TaskResultError("files_read 必须是非空字符串数组")
        if set(files_read) != set(required_files):
            raise TaskResultError("files_read 未完整覆盖 manifest 要求的全部文件")
        if not chapter_body or not isinstance(chapter_body, str):
            raise TaskResultError("Task 返回缺少 chapter_body")
        if not chapter_cards or not isinstance(chapter_cards, str):
            raise TaskResultError("Task 返回缺少 chapter_cards")
        if "## 内部工作卡" in chapter_body:
            raise TaskResultError("chapter_body 不得包含 ## 内部工作卡")
        if "## 正文" not in chapter_body:
            raise TaskResultError("chapter_body 必须包含 ## 正文 标记")
        if not chapter_cards.lstrip().startswith("## 内部工作卡"):
            raise TaskResultError("chapter_cards 必须以 ## 内部工作卡 开头")

        return {
            "status": "success",
            "context_manifest_id": context_manifest_id,
            "files_read": files_read,
            "chapter_body": chapter_body.strip() + "\n",
            "chapter_cards": chapter_cards.strip() + "\n",
        }

    def consume_task_result(self, vol_num: int, ch_num: int, raw_result: str | dict, validate: bool = True) -> ConsumeResult:
        request_payload = self._load_expected_request(vol_num, ch_num)
        manifest_file = request_payload.get("manifest_file")
        if not manifest_file:
            raise TaskResultError("latest_task_request.json 缺少 manifest_file")
        manifest_path = Path(manifest_file)
        if not manifest_path.exists():
            raise TaskResultError(f"manifest 文件不存在: {manifest_file}")
        manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        required_files = manifest_payload.get("required_read_sequence") or []
        if not isinstance(required_files, list) or not required_files:
            raise TaskResultError("manifest 缺少 required_read_sequence")

        payload = self.parse_task_result(
            raw_result,
            expected_manifest_id=request_payload.get("context_manifest_id", ""),
            required_files=required_files,
        )
        view = save_split_chapter(
            self.project_dir,
            vol_num,
            ch_num,
            payload["chapter_body"],
            payload["chapter_cards"],
        )

        save_json_file(
            self.project_dir / "context" / "latest_task_result.json",
            {
                "consumed_at": datetime.now().isoformat(timespec="seconds"),
                "vol": vol_num,
                "ch": ch_num,
                "status": "consumed",
                "context_manifest_id": payload["context_manifest_id"],
                "files_read": payload["files_read"],
                "body_output": str(view.chapter_path),
                "card_output": str(view.card_path),
            },
        )

        issues: list[str] = []
        validation_passed = True
        if validate:
            result = validate_chapter(self.project_dir, vol_num, ch_num)
            validation_passed = result.passed
            issues = [issue.message for issue in result.issues]

        return ConsumeResult(
            status="chapter_ready" if validation_passed else "gate_failed",
            vol=vol_num,
            ch=ch_num,
            body_output=str(view.chapter_path),
            card_output=str(view.card_path),
            validation_passed=validation_passed,
            issues=issues,
        )


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="准备或消费 Task 章节生成请求")
    parser.add_argument("project_dir")
    parser.add_argument("vol", type=int)
    parser.add_argument("ch", type=int)
    parser.add_argument("--lookback", type=int, default=0)
    parser.add_argument("--consume-result-file")
    args = parser.parse_args()

    dispatcher = TaskChapterDispatcher(Path(args.project_dir).expanduser().resolve())
    if args.consume_result_file:
        raw_result = Path(args.consume_result_file).read_text(encoding="utf-8")
        try:
            result = dispatcher.consume_task_result(args.vol, args.ch, raw_result)
        except TaskResultError as exc:
            print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False, indent=2))
            return 1
        print(json.dumps(result.__dict__, ensure_ascii=False, indent=2))
        return 0 if result.validation_passed else 1

    result = dispatcher.dispatch(args.vol, args.ch, args.lookback)
    if isinstance(result, dict):
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result.__dict__, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
