#!/usr/bin/env python3
"""整卷提纲生成器 - 支持LLM生成"""

import json
import os
import sys
from pathlib import Path
from typing import Optional


def load_project_state(project_dir: Path) -> dict:
    """加载项目状态"""
    state_file = project_dir / "wizard_state.json"
    if state_file.exists():
        return json.loads(state_file.read_text(encoding="utf-8"))

    config_file = project_dir / ".project_config.json"
    if config_file.exists():
        return json.loads(config_file.read_text(encoding="utf-8"))

    return {}


def build_generation_prompt(state: dict) -> str:
    """构建用于LLM生成卷纲的prompt
    
    基于wizard完整设定，生成结构化的卷纲prompt
    """
    specs = state.get("basic_specs", {})
    positioning = state.get("positioning", {})
    protagonist = state.get("protagonist", {})
    world = state.get("world", {})
    factions = state.get("factions", {})
    characters = state.get("characters", {})
    arch = state.get("volume_architecture", {})
    batch = state.get("batch_plan", {})
    naming = state.get("naming", {})
    power = state.get("power_system", {})

    volume_count = arch.get("volume_count", 10)
    chapters_per_volume = arch.get("chapters_per_volume", 14)
    book_title = naming.get("selected_book_title", "未命名")
    target_words = specs.get("target_word_count", "待定")
    chapter_length = specs.get("chapter_length", "2000-2500字")
    
    # 构建设定摘要
    setting_summary = f"""
## 基础设定
- 书名：{book_title}
- 总卷数：{volume_count}卷
- 每卷章数：{chapters_per_volume}章
- 总字数：{target_words}
- 单章字数：{chapter_length}
- 文风：{specs.get('style_tone', '待定')}
- 题材：{', '.join(specs.get('main_genres', []))}
- 子题材：{', '.join(specs.get('sub_genres', []))}
- 叙事视角：{positioning.get('narrative_style', '待定')}

## 主角设定
- 姓名：{protagonist.get('name', '待定')}
- 性别：{protagonist.get('gender', '待定')}
- 年龄段：{protagonist.get('age_group', '待定')}
- 起点身份：{protagonist.get('starting_identity', '待定')}
- 起点实力/地位：{protagonist.get('starting_level', '待定')}
- 核心性格：{protagonist.get('personality', '待定')}
- 核心欲望：{protagonist.get('core_desire', '待定')}
- 深层恐惧：{protagonist.get('deepest_fear', '待定')}
- 长期目标：{protagonist.get('long_term_goal', '待定')}
- 特殊能力：{protagonist.get('ability', '待定')}

## 世界观设定
- 背景设定：{world.get('setting_type', '待定')}
- 社会结构：{world.get('society_structure', '待定')}
- 主要场景：{', '.join(world.get('main_scene', []))}
- 冒险区域：{', '.join(world.get('adventure_zone', []))}
- 主要危机：{', '.join(world.get('main_crisis', []))}
- 场景层级：{world.get('scene_layers', '待定')}

## 势力设定
- 主角势力：{factions.get('player_faction', '待定')}
- 敌对势力：{factions.get('enemy_faction', '待定')}
- 中立势力：{factions.get('neutral_faction', '待定')}

## 角色关系
- 感情线类型：{characters.get('romance_type', '待定')}
- 主要关系类型：{', '.join(characters.get('key_relationship_types', []))}
- 核心对立面：{characters.get('main_antagonist_type', '待定')}
- 反派强度曲线：{characters.get('antagonist_curve', '待定')}
- 冲突层级：{', '.join(characters.get('conflict_levels', []))}
- 关系张力来源：{', '.join(characters.get('relationship_tension', []))}

## 核心冲突
- 主要冲突：{', '.join(positioning.get('main_conflicts', []))}
- 读者钩子：{', '.join(positioning.get('reader_hooks', []))}
- 核心承诺：{positioning.get('core_promise', '待定')}
"""

    # 如果有力量体系，添加
    if power:
        setting_summary += f"""
## 力量体系
- 主要体系：{power.get('main_system', '待定')}
- 境界划分：{power.get('levels', '待定')}
- 突破条件：{power.get('breakthrough_condition', '待定')}
- 力量限制：{power.get('limitation', '待定')}
- 体系特点：{power.get('unique_trait', '待定')}
- 资源/货币：{power.get('resource_economy', '待定')}
"""

    prompt = f"""你是一位资深的小说架构师。请根据以下小说设定，生成全部 {volume_count} 卷的详细卷纲。

{setting_summary}

## 全书架构
- 全书抬升路径：{arch.get('book_escalation_path', '逐步成长')}
- 每卷交付承诺：{arch.get('delivery_matrix', '情感收获 + 成长蜕变')}
- 第一卷目标：{batch.get('first_volume_goal', '确立核心关系')}
- 第一卷钩子：{batch.get('first_volume_hook', '系统任务发布')}

## 生成要求

1. **每卷必须包含以下字段**：
   - 卷标题（有吸引力的标题，不是"第X卷"）
   - 卷定位（本卷在全书中的位置和作用，2-3句话）
   - 卷目标（具体、可衡量的叙事目标，1-2句话）
   - 抬升路径（本卷的具体故事走向，3-5句话，要具体！）
   - 核心冲突（本卷要解决的核心矛盾）
   - 关键转折（本卷中的1-2个关键转折点，具体事件）
   - 卷尾钩子（吸引读者继续读下一卷的悬念，要具体！）
   - 预估章数（{chapters_per_volume}章）

2. **质量要求**：
   - 卷与卷之间必须有明确的递进关系，不能重复
   - 抬升路径要具体，写"主角从X状态通过Y事件到达Z状态"，禁止写"故事推进，冲突升级"这类空话
   - 关键转折要指明具体事件，如"主角发现XX真相"、"主角遭遇XX背叛"
   - 卷尾钩子要具体，如"XX的秘密即将揭晓"、"XX的阴谋浮出水面"
   - 第一卷必须呼应"第一卷目标"和"第一卷钩子"
   - 全书总章节数约 {volume_count * chapters_per_volume} 章，合理分配内容密度

3. **叙事节奏**：
   - 前期（1-3卷）：铺垫、建立关系、小冲突
   - 中期（4-7卷）：冲突升级、重大转折、揭示真相
   - 后期（8-{volume_count}卷）：高潮、决战、收尾

4. **角色成长弧线**：
   - 主角必须有清晰的成长轨迹
   - 每卷结束时主角的状态要比开始时有所提升
   - 最后几卷要有终极考验

## 输出格式

严格使用以下Markdown格式，不要添加任何额外说明：

```markdown
# 卷纲总表

## 全书概览
- 总字数目标：{target_words}
- 总卷数：{volume_count}卷
- 单章字数：{chapter_length}
- 书名：{book_title}

## 全书抬升路径
[2-3句话描述全书整体故事弧线，要具体]

## 每卷交付承诺
[1句话描述每卷给读者的核心体验]

## 第1卷 · [有吸引力的卷标题]
- 卷定位：...
- 卷目标：...
- 抬升路径：...
- 核心冲突：...
- 关键转折：...
- 卷尾钩子：...
- 预估章数：{chapters_per_volume}章

## 第2卷 · [有吸引力的卷标题]
[同上格式]

[重复直到第{volume_count}卷]
```

请直接输出Markdown格式的卷纲，不要有任何前言或后缀。"""

    return prompt


def save_outline(project_dir: Path, outline_text: str) -> Path:
    """保存卷纲到文件
    
    Args:
        project_dir: 项目目录
        outline_text: 卷纲文本
        
    Returns:
        保存的文件路径
    """
    ref_dir = project_dir / "reference"
    ref_dir.mkdir(exist_ok=True)
    outline_file = ref_dir / "卷纲总表.md"
    outline_file.write_text(outline_text, encoding="utf-8")
    return outline_file


def generate_outline(state: dict, project_dir: Path) -> dict:
    """生成卷纲
    
    尝试直接调用LLM，如果失败则返回需要子代理的状态
    
    Returns:
        {"status": "success", "outline_file": Path} 或
        {"status": "outline_required", "prompt": str, "project_dir": str}
    """
    prompt = build_generation_prompt(state)
    
    # 尝试直接调用LLM API（如果环境中有配置）
    # 目前通过环境变量检测
    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    
    if api_key:
        try:
            outline_text = _call_llm_api(prompt, api_key)
            if outline_text:
                outline_file = save_outline(project_dir, outline_text)
                return {
                    "status": "success",
                    "outline_file": str(outline_file),
                    "message": f"卷纲已生成: {outline_file}"
                }
        except Exception as e:
            print(f"直接调用LLM失败: {e}", file=sys.stderr)
    
    # 无法直接调用，返回需要子代理的状态
    # 保存prompt到临时文件
    prompt_dir = project_dir / "context"
    prompt_dir.mkdir(exist_ok=True)
    prompt_file = prompt_dir / "outline_prompt.txt"
    prompt_file.write_text(prompt, encoding="utf-8")
    
    return {
        "status": "outline_required",
        "prompt_file": str(prompt_file),
        "project_dir": str(project_dir),
        "message": "需要调用LLM生成卷纲"
    }


def _call_llm_api(prompt: str, api_key: str) -> Optional[str]:
    """调用LLM API生成卷纲
    
    这是一个占位实现，实际使用时需要接入具体的API
    """
    # TODO: 实现具体的LLM调用
    # 目前返回None，强制使用子代理模式
    return None


def parse_generated_outline(outline_text: str) -> dict:
    """解析生成的卷纲文本
    
    将Markdown格式的卷纲解析为结构化数据
    """
    volumes = []
    current_volume = None
    
    for line in outline_text.splitlines():
        stripped = line.strip()
        
        # 检测卷标题行
        if stripped.startswith("## 第") and "·" in stripped:
            if current_volume:
                volumes.append(current_volume)
            
            # 解析卷号和标题
            parts = stripped.replace("## ", "").split("·", 1)
            vol_num_str = parts[0].strip()
            vol_title = parts[1].strip() if len(parts) > 1 else ""
            
            # 提取数字
            vol_num = 0
            for char in vol_num_str:
                if char.isdigit():
                    vol_num = vol_num * 10 + int(char)
            
            current_volume = {
                "vol_num": vol_num,
                "title": vol_title,
                "fields": {}
            }
        
        # 检测字段行
        elif stripped.startswith("- ") and current_volume:
            if "：" in stripped:
                field_name, field_value = stripped[2:].split("：", 1)
                current_volume["fields"][field_name.strip()] = field_value.strip()
    
    # 添加最后一个卷
    if current_volume:
        volumes.append(current_volume)
    
    return {
        "volumes": volumes,
        "raw_text": outline_text
    }


def validate_outline(outline_text: str, expected_volumes: int) -> tuple[bool, list[str]]:
    """验证卷纲质量
    
    Returns:
        (是否有效, 问题列表)
    """
    issues = []
    
    # 检查基本结构
    if "# 卷纲总表" not in outline_text:
        issues.append("缺少'# 卷纲总表'标题")
    
    # 检查卷数
    volume_headers = [line for line in outline_text.splitlines() if line.strip().startswith("## 第")]
    actual_volumes = len(volume_headers)
    
    if actual_volumes != expected_volumes:
        issues.append(f"卷数不匹配: 期望{expected_volumes}卷, 实际{actual_volumes}卷")
    
    # 检查每卷是否有必需字段
    required_fields = ["卷定位", "卷目标", "抬升路径", "核心冲突", "关键转折", "卷尾钩子"]
    
    for vol_header in volume_headers:
        vol_num = vol_header.split("·")[0].strip()
        for field in required_fields:
            if f"- {field}：" not in outline_text:
                issues.append(f"{vol_num} 缺少'{field}'字段")
    
    # 检查是否有模板化内容
    template_phrases = [
        "故事推进，冲突升级",
        "悬念与挑战",
        "阶段",
        "待定",
        "...",
    ]
    
    for phrase in template_phrases:
        if phrase in outline_text:
            issues.append(f"发现模板化内容: '{phrase}'")
    
    is_valid = len(issues) == 0
    return is_valid, issues


def main():
    """命令行入口"""
    if len(sys.argv) < 2:
        print('用法: volume_outline_generator.py <项目目录> [--save <outline_file>]')
        sys.exit(1)
    
    project_dir = Path(sys.argv[1]).expanduser().resolve()
    if not project_dir.exists():
        print(f"项目目录不存在: {project_dir}")
        sys.exit(1)
    
    state = load_project_state(project_dir)
    if not state:
        print("未找到项目状态文件")
        sys.exit(1)
    
    # 检查是否有 --save 参数（用于保存子代理生成的结果）
    if "--save" in sys.argv:
        save_idx = sys.argv.index("--save")
        if save_idx + 1 < len(sys.argv):
            outline_file = Path(sys.argv[save_idx + 1])
            if outline_file.exists():
                outline_text = outline_file.read_text(encoding="utf-8")
                saved_path = save_outline(project_dir, outline_text)
                
                # 验证
                arch = state.get("volume_architecture", {})
                expected = arch.get("volume_count", 10)
                is_valid, issues = validate_outline(outline_text, expected)
                
                result = {
                    "status": "success" if is_valid else "warning",
                    "outline_file": str(saved_path),
                    "validation": {
                        "valid": is_valid,
                        "issues": issues
                    }
                }
                print(json.dumps(result, ensure_ascii=False, indent=2))
                sys.exit(0 if is_valid else 1)
    
    # 正常生成流程
    result = generate_outline(state, project_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
