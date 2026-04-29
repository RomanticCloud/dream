#!/usr/bin/env python3
"""正文生成调度器 - 负责生成正文prompt和消费正文结果"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from chapter_view import save_split_chapter
from common_io import save_json_file
from context_pack_builder import build_context_pack, context_pack_file, context_pack_markdown_file
from model_config import is_external_backend, resolve_body_model
from path_rules import chapter_file, chapter_card_file
from preflight_planner import build_preflight_plan, preflight_file, preflight_markdown_file
from subagent_chapter_generator import SubagentChapterGenerator


@dataclass
class BodyDispatchResult:
    """正文生成调度结果"""
    status: str
    prompt_file: str
    request_file: str
    manifest_file: str
    context_manifest_id: str
    prompt_length: int
    chapters_loaded: int
    required_files: int
    body_output: str
    mode: str = "body_only"


@dataclass
class BodyConsumeResult:
    """正文消费结果"""
    status: str
    vol: int
    ch: int
    body_file: str
    word_count: int
    issues: list[str]


class BodyResultError(ValueError):
    """Raised when body generation result violates execution protocol."""


class BodyDispatcher:
    """正文生成调度器"""
    
    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        self.generator = SubagentChapterGenerator(project_dir)
    
    def dispatch(self, vol_num: int, ch_num: int, context_mode: str = "fast") -> BodyDispatchResult:
        """生成正文专用prompt
        
        Args:
            vol_num: 卷号
            ch_num: 章节号
            
        Returns:
            BodyDispatchResult 包含所有生成所需的文件路径
        """
        if context_mode == "full":
            return self._dispatch_full_context(vol_num, ch_num)

        # 1. 构建轻量上下文包和预检计划（默认 fast，不再全量读取前文）
        body_model = resolve_body_model(self.project_dir)
        context_pack = build_context_pack(self.project_dir, vol_num, ch_num, mode=context_mode)
        preflight = build_preflight_plan(self.project_dir, vol_num, ch_num, context_pack)
        manifest_file = str(context_pack_file(self.project_dir, vol_num, ch_num))
        manifest_id = context_pack.get("context_id", "")

        # 2. 生成正文专用prompt
        body_prompt = self._generate_fast_body_prompt(vol_num, ch_num, context_pack, preflight)

        # 3. 保存正文专用prompt
        body_prompt_file = self.project_dir / "context" / f"body_prompt_vol{vol_num:02d}_ch{ch_num:02d}.md"
        body_prompt_file.write_text(body_prompt, encoding="utf-8")

        # 4. 生成请求文件
        request_file = self.project_dir / "context" / "latest_body_request.json"
        required_files = [
            str(context_pack_markdown_file(self.project_dir, vol_num, ch_num)),
            str(context_pack_file(self.project_dir, vol_num, ch_num)),
            str(preflight_markdown_file(self.project_dir, vol_num, ch_num)),
            str(preflight_file(self.project_dir, vol_num, ch_num)),
        ]
        payload = {
            "generator": "dream/scripts/body_dispatcher.py",
            "project_dir": str(self.project_dir),
            "mode": "body_only",
            "strategy": "compact_context",
            "context_mode": context_mode,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "vol": vol_num,
            "ch": ch_num,
            "prompt_file": str(body_prompt_file),
            "manifest_file": manifest_file,
            "context_manifest_id": manifest_id,
            "body_output": str(chapter_file(self.project_dir, vol_num, ch_num)),
            "proof_file": str(self._proof_file(vol_num, ch_num)),
            "card_output": str(chapter_card_file(self.project_dir, vol_num, ch_num)),
            "chapters_loaded": len(context_pack.get("recent_chapters", [])),
            "required_files": len(required_files),
            "required_context_files": required_files,
            "prompt_length": len(body_prompt),
            "model": body_model,
            "model_runner_command": self._model_runner_command(request_file) if is_external_backend(body_model) else "",
            "requirements": {
                "output_field": "chapter_body",
                "forbidden_marker": "## 内部工作卡",
                "required_marker": "## 正文",
                "split_files": False,
                "context_manifest_id": manifest_id,
            }
        }
        save_json_file(request_file, payload)

        return BodyDispatchResult(
            status="body_prompt_ready",
            prompt_file=str(body_prompt_file),
            request_file=str(request_file),
            manifest_file=manifest_file,
            context_manifest_id=manifest_id,
            prompt_length=len(body_prompt),
            chapters_loaded=len(context_pack.get("recent_chapters", [])),
            required_files=len(required_files),
            body_output=str(chapter_file(self.project_dir, vol_num, ch_num)),
        )

    def _model_runner_command(self, request_file: Path) -> str:
        return f"python3 scripts/model_runner.py body --request-file {request_file} --json"

    def _dispatch_full_context(self, vol_num: int, ch_num: int) -> BodyDispatchResult:
        """旧版全前文读取链路，作为严重漂移或回改时的兜底模式。"""
        from chapter_plan_loader import get_chapter_plan
        body_model = resolve_body_model(self.project_dir)
        chapter_plan = get_chapter_plan(self.project_dir, vol_num, ch_num)
        result = self.generator.dispatch_chapter_generation(vol_num, ch_num, chapter_plan=chapter_plan)
        if result.get("status") != "prompt_ready":
            return BodyDispatchResult(
                status="error",
                prompt_file="",
                request_file="",
                manifest_file="",
                context_manifest_id="",
                prompt_length=0,
                chapters_loaded=0,
                required_files=0,
                body_output="",
            )
        
        manifest_file = result.get("manifest_file", "")
        manifest_id = result.get("context_manifest_id", "")
        prompt_file = result.get("prompt_file", "")
        
        # 2. 生成正文专用prompt（从完整prompt中提取正文部分）
        body_prompt = self._generate_body_prompt(vol_num, ch_num, prompt_file, manifest_file, manifest_id)
        
        # 3. 保存正文专用prompt
        body_prompt_file = self.project_dir / "context" / f"body_prompt_vol{vol_num:02d}_ch{ch_num:02d}.md"
        body_prompt_file.write_text(body_prompt, encoding="utf-8")
        
        # 4. 生成请求文件
        request_file = self.project_dir / "context" / "latest_body_request.json"
        payload = {
            "generator": "dream/scripts/body_dispatcher.py",
            "project_dir": str(self.project_dir),
            "mode": "body_only",
            "strategy": "subagent_read_all_previous",
            "context_mode": "full",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "vol": vol_num,
            "ch": ch_num,
            "prompt_file": str(body_prompt_file),
            "manifest_file": manifest_file,
            "context_manifest_id": manifest_id,
            "body_output": str(chapter_file(self.project_dir, vol_num, ch_num)),
            "proof_file": str(self._proof_file(vol_num, ch_num)),
            "card_output": str(chapter_card_file(self.project_dir, vol_num, ch_num)),
            "chapters_loaded": result.get("chapters_loaded", 0),
            "required_files": result.get("required_files", 0),
            "prompt_length": len(body_prompt),
            "model": body_model,
            "model_runner_command": self._model_runner_command(request_file) if is_external_backend(body_model) else "",
            "requirements": {
                "output_field": "chapter_body",
                "forbidden_marker": "## 内部工作卡",
                "required_marker": "## 正文",
                "split_files": False,  # 正文阶段只生成body
            }
        }
        save_json_file(request_file, payload)
        
        return BodyDispatchResult(
            status="body_prompt_ready",
            prompt_file=str(body_prompt_file),
            request_file=str(request_file),
            manifest_file=manifest_file,
            context_manifest_id=manifest_id,
            prompt_length=len(body_prompt),
            chapters_loaded=result.get("chapters_loaded", 0),
            required_files=result.get("required_files", 0),
            body_output=str(chapter_file(self.project_dir, vol_num, ch_num)),
        )

    def _proof_file(self, vol_num: int, ch_num: int) -> Path:
        return self.project_dir / "context" / f"body_execution_proof_vol{vol_num:02d}_ch{ch_num:02d}.json"

    def _generate_fast_body_prompt(self, vol_num: int, ch_num: int, context_pack: dict, preflight: dict) -> str:
        from common_io import load_project_state, require_chapter_word_range
        state = load_project_state(self.project_dir)
        min_words, max_words = require_chapter_word_range(state)
        draft_target = (min_words + max_words) // 2
        context_md = context_pack_markdown_file(self.project_dir, vol_num, ch_num)
        context_json = context_pack_file(self.project_dir, vol_num, ch_num)
        preflight_md = preflight_markdown_file(self.project_dir, vol_num, ch_num)
        preflight_json = preflight_file(self.project_dir, vol_num, ch_num)
        output_file = chapter_file(self.project_dir, vol_num, ch_num)
        proof_file = self._proof_file(vol_num, ch_num)
        project = context_pack.get("project", {})
        return f"""# 正文生成任务（轻量上下文模式）

## 项目信息
- 书名：{project.get('book_title', '未命名')}
- 题材：{'、'.join(project.get('genres') or [])}
- 文风：{project.get('style_tone', '')}
- 叙事视角：{project.get('narrative_style', '')}
- 当前章节：第{vol_num}卷第{ch_num}章
- 字数要求：{min_words}-{max_words}字，目标约{draft_target}字

## 执行协议（严格遵守）
1. 这是 compact-context 默认链路，不需要读取全部前文章节。
2. 必须先读取以下文件，再生成正文：
   - `{context_md}`
   - `{context_json}`
   - `{preflight_md}`
   - `{preflight_json}`
3. 以 `CONTINUITY_LEDGER` 和 `preflight_plan` 为最高事实源。若摘要、正文片段、直觉判断冲突，以账本和预检计划为准。
4. 不得改写禁止违背事实，不得重置上一章结尾地点、情绪、目标和钩子。
5. 本阶段只生成正文，不生成工作卡。工作卡将在正文事实抽取后单独生成。

## 必须完成的承接
- 开场地点：{preflight.get('opening_must_continue', {}).get('location', '')}
- 开场情绪：{preflight.get('opening_must_continue', {}).get('emotion', '')}
- 开场目标：{preflight.get('opening_must_continue', {}).get('goal', '')}
- 上章钩子：{preflight.get('opening_must_continue', {}).get('hook', '')}

## 本章主推进
{preflight.get('main_progress') or '推进当前卷主线'}

## 阻塞要求
""" + "\n".join(f"- {item}" for item in preflight.get("blocking_items", [])) + f"""

## 输出要求
- 正文只写入：`{output_file}`
- 执行证明必须写入：`{proof_file}`
- `chapter_body` 必须包含章节标题和 `## 正文` 标记
- `chapter_body` 禁止包含 `## 内部工作卡`
- 结尾必须留下下一章可执行钩子，但不能凭空解决账本中的未回收伏笔

## 输出前强制自检
1. 正文字数必须在 {min_words}-{max_words} 字之间。
2. 开头是否承接上一章结尾场景、情绪、目标。
3. 是否完成 preflight 的 must_handle。
4. 是否违背 hard_facts 或 open_constraints。
5. 是否出现与时间、资源、人物在场状态冲突的内容。

## 输出格式
只允许输出一个 JSON 对象，不允许解释文字，不允许代码块：
{{
  "status": "success",
  "context_manifest_id": "{context_pack.get('context_id')}",
  "files_read": [
    "{context_md}",
    "{context_json}",
    "{preflight_md}",
    "{preflight_json}"
  ],
  "chapter_body": "# 第{ch_num}章 标题\\n\\n## 正文\\n\\n..."
}}

同时必须将同一个 JSON 对象写入 `{proof_file}`。如果无法写入证明文件，返回 error，不得只写正文。
"""
    
    def consume(self, vol_num: int, ch_num: int, raw_result: str | dict, validate: bool = True) -> BodyConsumeResult:
        """消费正文生成结果
        
        Args:
            vol_num: 卷号
            ch_num: 章节号
            raw_result: 子代理返回的JSON字符串或字典
            validate: 是否执行校验
            
        Returns:
            BodyConsumeResult
        """
        # 解析结果
        if isinstance(raw_result, str):
            try:
                payload = json.loads(raw_result)
            except json.JSONDecodeError as exc:
                return BodyConsumeResult(
                    status="parse_failed",
                    vol=vol_num,
                    ch=ch_num,
                    body_file="",
                    word_count=0,
                    issues=[f"JSON解析失败: {exc}"]
                )
        else:
            payload = raw_result
        
        # 检查状态
        if payload.get("status") == "error":
            return BodyConsumeResult(
                status="generation_failed",
                vol=vol_num,
                ch=ch_num,
                body_file="",
                word_count=0,
                issues=[payload.get("error", "子代理返回错误状态")]
            )

        try:
            self._validate_execution_proof(vol_num, ch_num, payload)
        except BodyResultError as exc:
            return BodyConsumeResult(
                status="validation_failed",
                vol=vol_num,
                ch=ch_num,
                body_file="",
                word_count=0,
                issues=[str(exc)]
            )

        chapter_body = payload.get("chapter_body", "")
        
        # 基础校验
        issues = []
        if not chapter_body:
            issues.append("缺少 chapter_body")
        if "## 内部工作卡" in chapter_body:
            issues.append("正文不得包含 ## 内部工作卡")
        if "## 正文" not in chapter_body:
            issues.append("正文必须包含 ## 正文 标记")
        
        if issues:
            return BodyConsumeResult(
                status="validation_failed",
                vol=vol_num,
                ch=ch_num,
                body_file="",
                word_count=0,
                issues=issues
            )
        
        # 保存正文到临时文件
        body_file = self.project_dir / "chapters" / f"vol{vol_num:02d}" / f"ch{ch_num:02d}_body.md"
        body_file.parent.mkdir(parents=True, exist_ok=True)
        body_file.write_text(chapter_body, encoding="utf-8")
        save_json_file(self._proof_file(vol_num, ch_num), {
            "status": "success",
            "context_manifest_id": payload.get("context_manifest_id"),
            "files_read": payload.get("files_read"),
            "body_file": str(body_file),
        })
        
        # 字数统计
        from body_validator import count_words, extract_body
        word_count = count_words(extract_body(chapter_body))
        
        # 执行完整正文校验
        if validate:
            from body_validator import validate_body
            validation = validate_body(chapter_body, self.project_dir, vol_num, ch_num)
            if not validation.passed:
                return BodyConsumeResult(
                    status="validation_failed",
                    vol=vol_num,
                    ch=ch_num,
                    body_file=str(body_file),
                    word_count=word_count,
                    issues=[issue.message for issue in validation.issues]
                )
        
        return BodyConsumeResult(
            status="body_ready",
            vol=vol_num,
            ch=ch_num,
            body_file=str(body_file),
            word_count=word_count,
            issues=[]
        )

    def _load_expected_request(self, vol_num: int, ch_num: int) -> dict:
        request_file = self.project_dir / "context" / "latest_body_request.json"
        if not request_file.exists():
            raise BodyResultError("缺少 latest_body_request.json，无法校验正文生成执行证明")
        payload = json.loads(request_file.read_text(encoding="utf-8"))
        if payload.get("vol") != vol_num or payload.get("ch") != ch_num:
            raise BodyResultError("latest_body_request.json 与当前卷章不匹配")
        return payload

    def _validate_execution_proof(self, vol_num: int, ch_num: int, payload: dict) -> None:
        request_payload = self._load_expected_request(vol_num, ch_num)
        expected_manifest_id = request_payload.get("context_manifest_id", "")
        if payload.get("context_manifest_id") != expected_manifest_id:
            raise BodyResultError("正文结果 context_manifest_id 与请求不一致")
        files_read = payload.get("files_read")
        if not isinstance(files_read, list) or not files_read:
            raise BodyResultError("正文结果缺少 files_read，无法证明已读取上下文")
        if any(not isinstance(item, str) or not item.strip() for item in files_read):
            raise BodyResultError("files_read 必须是非空字符串数组")
        if request_payload.get("strategy") == "compact_context":
            required_files = request_payload.get("required_context_files") or []
        else:
            manifest_file = request_payload.get("manifest_file", "")
            if not manifest_file:
                raise BodyResultError("正文请求缺少 manifest_file")
            manifest_path = Path(manifest_file)
            if not manifest_path.exists():
                raise BodyResultError(f"manifest 文件不存在: {manifest_file}")
            manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            required_files = manifest_payload.get("required_read_sequence") or []
        if not required_files:
            raise BodyResultError("正文请求缺少必读文件列表")
        if set(files_read) != set(required_files):
            missing = sorted(set(required_files) - set(files_read))
            raise BodyResultError("files_read 未完整覆盖正文请求要求的全部文件" + (f"，缺少: {missing[:5]}" if missing else ""))
    
    def _generate_body_prompt(self, vol_num: int, ch_num: int, full_prompt_file: str, manifest_file: str, manifest_id: str = "") -> str:
        """从完整prompt生成正文专用prompt
        
        移除工作卡生成要求，只保留正文生成相关指令
        """
        # 加载项目状态获取字数范围
        from common_io import load_project_state
        state = load_project_state(self.project_dir)
        specs = state.get("basic_specs", {}) if state else {}
        min_words = specs.get("chapter_length_min", 2000)
        max_words = specs.get("chapter_length_max", 2500)
        
        # 读取完整prompt
        full_prompt = Path(full_prompt_file).read_text(encoding="utf-8")
        
        # 加载当前章规划
        from chapter_plan_loader import get_chapter_plan, format_chapter_plan_for_prompt
        chapter_plan = get_chapter_plan(self.project_dir, vol_num, ch_num)
        chapter_plan_text = format_chapter_plan_for_prompt(chapter_plan) if chapter_plan else ""
        
        # 提取正文相关部分
        # 策略：保留直到"## 输出要求"之前的所有内容
        # 但移除工作卡格式要求部分
        
        body_prompt = full_prompt
        
        # 在"当前卷纲约束"之后插入章级规划约束
        if chapter_plan_text:
            # 找到合适的位置插入章级规划
            volume_constraints_marker = "## 当前卷纲约束"
            if volume_constraints_marker in body_prompt:
                # 在卷纲约束后插入章规划
                insert_pos = body_prompt.find(volume_constraints_marker)
                # 找到卷纲约束部分的结束（下一个 ## 标题）
                next_section = body_prompt.find("\n## ", insert_pos + len(volume_constraints_marker))
                if next_section > 0:
                    body_prompt = (
                        body_prompt[:next_section] + 
                        "\n\n" + chapter_plan_text + "\n" +
                        body_prompt[next_section:]
                    )
                else:
                    body_prompt += "\n\n" + chapter_plan_text + "\n"
            else:
                # 如果找不到标记，在prompt开头附近插入
                body_prompt = chapter_plan_text + "\n\n" + body_prompt
        
        # 移除工作卡格式详细说明（从"4. **工作卡格式**"到"5. **禁止事项**"之间）
        import re
        
        # 移除工作卡格式段
        body_prompt = re.sub(
            r'4\. \*\*工作卡格式.*?## 输出格式',
            '## 输出格式',
            body_prompt,
            flags=re.DOTALL
        )
        
        # 修改输出要求：只返回 chapter_body
        body_prompt = body_prompt.replace(
            '"chapter_body": "...",\n  "chapter_cards": "..."',
            '"chapter_body": "..."'
        )
        
        # 修改内容要求：移除"包含完整的工作卡"
        body_prompt = body_prompt.replace(
            '- 包含完整的工作卡（状态卡、情节卡、资源卡、关系卡、情绪弧线卡、承上启下卡）\n',
            ''
        )
        
        # 修改格式要求：移除工作卡相关
        body_prompt = body_prompt.replace(
            '- `## 内部工作卡` 标记\n- 六张工作卡（每张用 `### N. 卡片名` 标记）\n',
            ''
        )
        
        # 修改约束：移除 chapter_cards 相关
        body_prompt = body_prompt.replace(
            '- `chapter_cards` 只对应工作卡文件：...\n',
            ''
        )
        body_prompt = body_prompt.replace(
            '- `chapter_cards` 必须以 `## 内部工作卡` 开始\n',
            ''
        )
        
        # 修改输出格式说明
        body_prompt = body_prompt.replace(
            '"chapter_body" 只对应正文文件',
            '"chapter_body" 为完整正文内容'
        )
        
        # 添加正文专用说明和自检要求
        body_prompt += """

## 正文专用说明
- 本章只需生成正文部分，不需要生成工作卡
- 工作卡将在正文通过校验后单独生成
- 确保正文内容完整、连贯、符合字数要求

## 输出前强制自检（必须执行）

生成完成后、输出前，必须进行以下自检：

1. **字数检查**：
   - 正文字数必须在 {min_words}-{max_words} 字范围内
   - 字数统计范围：`## 正文` 到文件末尾之间的纯文本（去除markdown标记）

2. **格式检查**：
   - `## 正文` 标记必须存在
   - `## 内部工作卡` 不得出现在正文中
   - 章节标题格式：`# 第X章 标题`

3. **内容质量检查**：
   - 不得出现"本章"、"本章中"等自指词汇
   - 不得出现"微微一笑"、"若有所思"、"喃喃自语道"等模式化表达
   - 对话要口语化，符合角色身份
   - 场景切换要有过渡

4. **时间一致性检查**：
   - 时间线必须合理衔接上一章
   - 不得与前文的时间描述矛盾

发现问题立即修正，再输出最终版本。

## 输出格式

只允许输出一个 JSON 对象：

```json
{{
  "status": "success",
  "context_manifest_id": "{context_manifest_id}",
  "files_read": [
    "manifest.required_read_sequence 里的绝对路径1",
    "manifest.required_read_sequence 里的绝对路径2"
  ],
  "chapter_body": "# 第{ch_num}章 标题\\n\\n## 正文\\n\\n..."
}}
```

注意：直接写入文件 `{body_output}`，不要等待主会话确认。
同时必须将同一个 JSON 对象写入执行证明文件 `{proof_file}`，否则调度器会判定未按流程读取上下文并拒绝继续。
""".format(
            min_words=min_words,
            max_words=max_words,
            context_manifest_id=manifest_id or manifest_file,
            ch_num=ch_num,
            body_output=chapter_file(self.project_dir, vol_num, ch_num),
            proof_file=self._proof_file(vol_num, ch_num)
        )
        
        return body_prompt
