#!/usr/bin/env python3
"""工作卡生成调度器 - 负责生成工作卡prompt和消费工作卡结果"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from card_names import EMOTION_CARD, PLOT_CARD
from card_fields import (
    FIELD_CARRY_HOOK,
    FIELD_CARRY_LIMIT,
    FIELD_CARRY_MUST,
    FIELD_CARRY_PAYOFF,
    FIELD_CARRY_SETUP,
    FIELD_EMOTION_PROCESS,
    FIELD_EMOTION_START,
    FIELD_EMOTION_SUSPENSE,
    FIELD_EMOTION_TARGET,
    FIELD_PLOT_CONFLICT,
    FIELD_PLOT_EVENT,
    FIELD_PLOT_PAYOFF,
    FIELD_PLOT_SETUP,
    FIELD_PLOT_TURN,
    FIELD_RELATION_CHANGE,
    FIELD_RELATION_MAIN,
    FIELD_RESOURCE_CARRY,
    FIELD_RESOURCE_GAIN,
    FIELD_RESOURCE_LOSS,
    FIELD_RESOURCE_SETUP,
    FIELD_RESOURCE_SPEND,
    FIELD_STATUS_CHANGE,
    FIELD_STATUS_ELAPSED,
    FIELD_STATUS_EMOTION,
    FIELD_STATUS_GOAL,
    FIELD_STATUS_INJURY,
    FIELD_STATUS_LOCATION,
    FIELD_STATUS_TIMEPOINT,
)
from chapter_validator import validate_chapter
from chapter_view import save_split_chapter
from common_io import save_json_file
from path_rules import chapter_file, chapter_card_file


@dataclass
class CardDispatchResult:
    """工作卡生成调度结果"""
    status: str
    prompt_file: str
    request_file: str
    body_file: str
    prompt_length: int
    mode: str = "cards_only"


@dataclass
class CardConsumeResult:
    """工作卡消费结果"""
    status: str
    vol: int
    ch: int
    chapter_file: str
    card_file: str
    issues: list[str]


class CardDispatcher:
    """工作卡生成调度器"""
    
    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        # 上一章状态缓存（实例级，避免 dispatch/consume 重复读取）
        self._previous_state_cache = {}  # (vol, ch) -> state dict
    
    def dispatch(self, vol_num: int, ch_num: int, last_errors: list[str] | None = None, retry_count: int = 0) -> CardDispatchResult:
        """生成工作卡专用prompt"""
        # 1. 读取已生成的正文
        # 支持两种命名：ch03.md（子代理直接写入）和 ch03_body.md（旧格式）
        chapter_path = chapter_file(self.project_dir, vol_num, ch_num)
        body_candidates = [
            chapter_path.parent / f"{chapter_path.stem}_body.md",
            chapter_path,  # 子代理直接写入的 ch03.md
        ]
        body_file = None
        for candidate in body_candidates:
            if candidate.exists():
                body_file = candidate
                break
        
        if not body_file:
            return CardDispatchResult(
                status="error",
                prompt_file="",
                request_file="",
                body_file="",
                prompt_length=0,
            )
        
        body_text = body_file.read_text(encoding="utf-8")
        
        # 2. 读取前文工作卡（用于状态继承）
        previous_state = self._load_previous_state(vol_num, ch_num)
        
        # 3. 生成工作卡prompt
        prompt = self._generate_card_prompt(vol_num, ch_num, body_text, previous_state, last_errors, retry_count)
        
        # 4. 保存prompt
        prompt_file = self.project_dir / "context" / f"card_prompt_vol{vol_num:02d}_ch{ch_num:02d}.md"
        prompt_file.write_text(prompt, encoding="utf-8")
        
        # 5. 生成请求文件
        request_file = self.project_dir / "context" / "latest_card_request.json"
        payload = {
            "generator": "dream/scripts/card_dispatcher.py",
            "mode": "cards_only",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "vol": vol_num,
            "ch": ch_num,
            "prompt_file": str(prompt_file),
            "body_file": str(body_file),
            "prompt_length": len(prompt),
            "retry_count": retry_count,
            "requirements": {
                "output_field": "chapter_cards",
                "required_marker": "## 内部工作卡",
                "card_headers": ["状态卡", "情节卡", "资源卡", "关系卡", "情绪弧线卡", "承上启下卡"],
            }
        }
        save_json_file(request_file, payload)
        
        return CardDispatchResult(
            status="card_prompt_ready",
            prompt_file=str(prompt_file),
            request_file=str(request_file),
            body_file=str(body_file),
            prompt_length=len(prompt),
        )
    
    def consume(self, vol_num: int, ch_num: int, raw_result: str | dict, validate: bool = True) -> CardConsumeResult:
        """消费工作卡生成结果"""
        # 解析结果
        if isinstance(raw_result, str):
            try:
                payload = json.loads(raw_result)
            except json.JSONDecodeError as exc:
                return CardConsumeResult(
                    status="parse_failed",
                    vol=vol_num,
                    ch=ch_num,
                    chapter_file="",
                    card_file="",
                    issues=[f"JSON解析失败: {exc}"]
                )
        else:
            payload = raw_result
        
        # 检查状态
        if payload.get("status") == "error":
            return CardConsumeResult(
                status="generation_failed",
                vol=vol_num,
                ch=ch_num,
                chapter_file="",
                card_file="",
                issues=[payload.get("error", "子代理返回错误状态")]
            )
        
        chapter_cards = payload.get("chapter_cards", "")
        
        # 基础校验
        issues = []
        if not chapter_cards:
            issues.append("缺少 chapter_cards")
        if not chapter_cards.lstrip().startswith("## 内部工作卡"):
            issues.append("工作卡必须以 ## 内部工作卡 开头")
        
        if issues:
            return CardConsumeResult(
                status="validation_failed",
                vol=vol_num,
                ch=ch_num,
                chapter_file="",
                card_file="",
                issues=issues
            )
        
        # 读取正文（支持两种文件命名：chXX.md 和 chXX_body.md）
        chapter_path = chapter_file(self.project_dir, vol_num, ch_num)
        body_file = chapter_path.parent / f"{chapter_path.stem}_body.md"
        if not body_file.exists():
            # 回退到 chXX.md
            body_file = chapter_path
        if not body_file.exists():
            return CardConsumeResult(
                status="body_missing",
                vol=vol_num,
                ch=ch_num,
                chapter_file="",
                card_file="",
                issues=[f"正文文件不存在: {body_file}"]
            )
        
        body_text = body_file.read_text(encoding="utf-8")
        
        # 自动填充继承字段
        previous_state = self._load_previous_state(vol_num, ch_num)
        chapter_cards = self._apply_inheritance(chapter_cards, previous_state)
        
        # 保存纯正文章节（不含工作卡）
        chapter_path = chapter_file(self.project_dir, vol_num, ch_num)
        card_path = chapter_card_file(self.project_dir, vol_num, ch_num)
        
        chapter_path.parent.mkdir(parents=True, exist_ok=True)
        card_path.parent.mkdir(parents=True, exist_ok=True)
        
        chapter_path.write_text(body_text, encoding="utf-8")
        card_path.write_text(chapter_cards, encoding="utf-8")
        
        # 执行完整校验（含跨章一致性）
        if validate:
            validation = validate_chapter(self.project_dir, vol_num, ch_num)
            if not validation.passed:
                return CardConsumeResult(
                    status="validation_failed",
                    vol=vol_num,
                    ch=ch_num,
                    chapter_file=str(chapter_path),
                    card_file=str(card_path),
                    issues=[issue.message for issue in validation.issues]
                )
        
        # 删除临时正文文件（合并后删除）
        # 只有当 body_file 和 chapter_path 不是同一文件时才删除
        if body_file.exists() and body_file.resolve() != chapter_path.resolve():
            body_file.unlink()
        
        return CardConsumeResult(
            status="chapter_ready",
            vol=vol_num,
            ch=ch_num,
            chapter_file=str(chapter_path),
            card_file=str(card_path),
            issues=[]
        )
    
    def _load_previous_state(self, vol_num: int, ch_num: int) -> dict[str, str]:
        """加载上一章的可继承字段值（带缓存）
        
        Returns:
            {字段名: 字段值, ...}
        """
        # 确定上一章
        prev_ch = ch_num - 1
        prev_vol = vol_num
        
        if prev_ch < 1:
            if vol_num > 1:
                prev_vol = vol_num - 1
                prev_ch = self._get_last_chapter_num(prev_vol) or 0
            else:
                return {}
        
        if prev_ch < 1:
            return {}
        
        cache_key = (prev_vol, prev_ch)
        
        # 检查缓存
        if cache_key in self._previous_state_cache:
            return self._previous_state_cache[cache_key]
        
        # 未命中，实际加载
        state = self._do_load_previous_state(prev_vol, prev_ch)
        self._previous_state_cache[cache_key] = state
        return state
    
    def _do_load_previous_state(self, prev_vol: int, prev_ch: int) -> dict[str, str]:
        """实际加载上一章的可继承字段值"""
        from card_parser import extract_section, extract_all_bullets
        from field_value_rules import INHERIT_MARKERS
        
        state = {}
        
        prev_card_file = chapter_card_file(self.project_dir, prev_vol, prev_ch)
        if not prev_card_file.exists():
            return state
        
        prev_text = prev_card_file.read_text(encoding="utf-8")
        
        # 提取状态卡字段
        status_section = extract_section(prev_text, "### 1. 状态卡")
        if status_section:
            bullets = extract_all_bullets(status_section)
            for bullet in bullets:
                field = bullet.get("field", "")
                value = bullet.get("value", "")
                if field and value and value not in INHERIT_MARKERS:
                    # 只继承有实际值的字段
                    state[field] = value
        
        # 提取资源卡中的"需带到下章的状态"
        resource_section = extract_section(prev_text, "### 3. 资源卡")
        if resource_section:
            bullets = extract_all_bullets(resource_section)
            for bullet in bullets:
                if bullet.get("field") == FIELD_RESOURCE_CARRY:
                    value = bullet.get("value", "")
                    if value and value not in INHERIT_MARKERS:
                        state[FIELD_RESOURCE_CARRY] = value
        
        return state
    
    def _apply_inheritance(self, chapter_cards: str, previous_state: dict[str, str]) -> str:
        """自动填充继承字段
        
        如果工作卡中某字段是继承标记或空值，且上一章有该字段的值，
        则自动用上一章的值替换。
        """
        from field_value_rules import INHERIT_MARKERS
        from card_parser import extract_section, extract_all_bullets
        
        if not previous_state:
            return chapter_cards
        
        lines = chapter_cards.splitlines()
        result_lines = []
        current_section = ""
        
        for line in lines:
            stripped = line.strip()
            
            # 跟踪当前卡片
            if stripped.startswith("### "):
                current_section = stripped
                result_lines.append(line)
                continue
            
            # 处理字段行
            if stripped.startswith("-"):
                from card_parser import split_card_line
                parts = split_card_line(stripped[1:])
                if parts:
                    field_name = parts[0].strip()
                    field_value = parts[1].strip() if len(parts) > 1 else ""
                    
                    # 检查是否需要继承
                    if field_value in INHERIT_MARKERS and field_name in previous_state:
                        # 用上一章的值替换
                        inherited_value = previous_state[field_name]
                        line = f"- {field_name}：{inherited_value}"
            
            result_lines.append(line)
        
        return "\n".join(result_lines)
    
    def _get_last_chapter_num(self, vol_num: int) -> int | None:
        """获取指定卷的最后一章号"""
        vol_dir = self.project_dir / "chapters" / f"vol{vol_num:02d}"
        if not vol_dir.exists():
            return None
        
        chapters = [int(f.stem.replace("ch", "")) for f in vol_dir.glob("ch*.md") if f.stem.replace("ch", "").isdigit()]
        return max(chapters) if chapters else None
    
    def _generate_card_prompt(self, vol_num: int, ch_num: int, body_text: str, previous_state: dict[str, str], last_errors: list[str] | None = None, retry_count: int = 0) -> str:
        """生成工作卡专用prompt"""
        
        # 计算输出路径
        from path_rules import chapter_card_file
        card_output = chapter_card_file(self.project_dir, vol_num, ch_num)
        
        retry_info = ""
        if retry_count > 0 and last_errors:
            retry_info = f"""
## 前一次生成的问题（第 {retry_count} 次重试）
"""
            for error in last_errors:
                retry_info += f"- {error}\n"
            
            retry_info += """
## 注意
请特别注意修复以上问题，确保工作卡与正文内容严格一致。

"""
        
        # 前章结束状态（用于继承）
        previous_state_section = ""
        if previous_state:
            previous_state_section = """
## 前章结束状态（本章开始时应继承）

本章是续写，如果本章开始时以下状态未发生变化，可直接写"继承上章"或留空，系统会自动填充：

"""
            for field, value in previous_state.items():
                previous_state_section += f"- {field}：{value}\n"
            
            previous_state_section += """
### 继承规则
1. **状态卡**：如果本章开始时主角状态未变，可直接写"继承上章"或留空
2. **资源卡**：如果无新资源变化，"需带到下章的状态"可写"继承上章"或留空
3. **变化字段**：如情节卡、关系卡、情绪弧线卡，通常每章不同，请根据正文填写实际值
4. **实际值优先**：如果某字段有实际变化，请填写新值，系统会优先使用你填写的值

"""
        
        prompt = f"""# 工作卡生成任务

{retry_info}{previous_state_section}
## 任务说明
本章正文已生成完毕，请根据正文内容生成完整的工作卡。

## 本章正文（{len(body_text)} 字）

{body_text[:5000] if len(body_text) <= 5000 else body_text[:5000] + '...'}

## 要求
根据正文内容，生成6张工作卡：

### 1. 状态卡
记录本章开始和结束时的人物状态：
- {FIELD_STATUS_LOCATION}：
- {FIELD_STATUS_INJURY}：
- {FIELD_STATUS_EMOTION}：
- {FIELD_STATUS_GOAL}：
- {FIELD_STATUS_CHANGE}：
- {FIELD_STATUS_ELAPSED}：
- {FIELD_STATUS_TIMEPOINT}：

### 2. 情节卡
记录本章的核心事件：
- {FIELD_PLOT_CONFLICT}：
- {FIELD_PLOT_EVENT}：
- {FIELD_PLOT_TURN}：
- {FIELD_PLOT_SETUP}：
- {FIELD_PLOT_PAYOFF}：

### 3. 资源卡
记录资源变化：
- {FIELD_RESOURCE_GAIN}：
- {FIELD_RESOURCE_SPEND}：
- {FIELD_RESOURCE_LOSS}：
- {FIELD_RESOURCE_CARRY}：
- {FIELD_RESOURCE_SETUP}：

### 4. 关系卡
记录人物关系变化：
- {FIELD_RELATION_MAIN}：
- {FIELD_RELATION_CHANGE}：

### 5. 情绪弧线卡
记录情绪变化：
- {FIELD_EMOTION_START}：
- {FIELD_EMOTION_PROCESS}：
- {FIELD_EMOTION_TARGET}：
- {FIELD_EMOTION_SUSPENSE}：

### 6. 承上启下卡
记录与前后章的衔接：
- {FIELD_CARRY_MUST}：
- {FIELD_CARRY_LIMIT}：
- {FIELD_CARRY_PAYOFF}：
- {FIELD_CARRY_SETUP}：
- {FIELD_CARRY_HOOK}：

## 格式要求
- 必须以 `## 内部工作卡` 开头
- 每张卡用 `### N. 卡片名` 标记
- 字段用 `- 字段名：值` 格式
- 可继承字段（状态卡大部分、资源卡"需带到下章的状态"）如无变化可写"继承上章"或留空
- 变化字段（情节卡、情绪卡等）必须填写实际值

## 输出前强制自检（必须执行）

生成完成后、输出前，必须进行以下格式检查：

1. **时间字段格式**：
   - 时间流逝：`^\d+(分钟|小时|天|月)$`  （正确："3小时"；错误："约3小时"）
   - 时间点：`^第\d+天(清晨|早晨|上午|中午|下午|傍晚|晚上|深夜)$`  （正确："第1天下午"；错误："工作日下午"）

2. **资源字段格式**（强制使用 +/-数字+资源名）：
   - 正确："+1沟通技巧"、"+200元现金"、"-1道具"
   - 错误："沟通技巧提升"、"现金奖励"、"得到了200元"
   - 无消耗/损失时写"-0"或"无"

3. **悬念强度**：
   - 必须是1-10的纯整数  （正确："5"；错误："中等"、"5分"）

4. **标记检查**：
   - `## 内部工作卡` 必须存在且在最前面
   - 6张卡片（1-6）全部存在

5. **内容一致性**：
   - 工作卡内容必须与正文一致
   - 不得出现正文中没有的事件或人物

发现问题立即修正，再输出最终版本。

## 输出协议
只允许输出一个 JSON 对象：
{{
  "status": "success",
  "chapter_cards": "## 内部工作卡\n\n### 1. 状态卡\n..."
}}

注意：直接写入文件 `{card_output}`，不要等待主会话确认。
"""
        return prompt
