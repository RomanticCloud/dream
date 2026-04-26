#!/usr/bin/env python3
"""正文生成调度器 - 负责生成正文prompt和消费正文结果"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from chapter_view import save_split_chapter
from common_io import save_json_file
from path_rules import chapter_file, chapter_card_file
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


class BodyDispatcher:
    """正文生成调度器"""
    
    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        self.generator = SubagentChapterGenerator(project_dir)
    
    def dispatch(self, vol_num: int, ch_num: int) -> BodyDispatchResult:
        """生成正文专用prompt
        
        Args:
            vol_num: 卷号
            ch_num: 章节号
            
        Returns:
            BodyDispatchResult 包含所有生成所需的文件路径
        """
        # 1. 构建上下文manifest（复用现有逻辑）
        result = self.generator.dispatch_chapter_generation(vol_num, ch_num)
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
        body_prompt = self._generate_body_prompt(vol_num, ch_num, prompt_file, manifest_file)
        
        # 3. 保存正文专用prompt
        body_prompt_file = self.project_dir / "context" / f"body_prompt_vol{vol_num:02d}_ch{ch_num:02d}.md"
        body_prompt_file.write_text(body_prompt, encoding="utf-8")
        
        # 4. 生成请求文件
        request_file = self.project_dir / "context" / "latest_body_request.json"
        payload = {
            "generator": "dream/scripts/body_dispatcher.py",
            "mode": "body_only",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "vol": vol_num,
            "ch": ch_num,
            "prompt_file": str(body_prompt_file),
            "manifest_file": manifest_file,
            "context_manifest_id": manifest_id,
            "body_output": str(chapter_file(self.project_dir, vol_num, ch_num)),
            "card_output": str(chapter_card_file(self.project_dir, vol_num, ch_num)),
            "chapters_loaded": result.get("chapters_loaded", 0),
            "required_files": result.get("required_files", 0),
            "prompt_length": len(body_prompt),
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
    
    def _generate_body_prompt(self, vol_num: int, ch_num: int, full_prompt_file: str, manifest_file: str) -> str:
        """从完整prompt生成正文专用prompt
        
        移除工作卡生成要求，只保留正文生成相关指令
        """
        # 读取完整prompt
        full_prompt = Path(full_prompt_file).read_text(encoding="utf-8")
        
        # 提取正文相关部分
        # 策略：保留直到"## 输出要求"之前的所有内容
        # 但移除工作卡格式要求部分
        
        body_prompt = full_prompt
        
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
        
        # 添加正文专用说明
        body_prompt += """

## 正文专用说明
- 本章只需生成正文部分，不需要生成工作卡
- 工作卡将在正文通过校验后单独生成
- 确保正文内容完整、连贯、符合字数要求
"""
        
        return body_prompt
