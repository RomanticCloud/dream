#!/usr/bin/env python3
"""测试继承机制"""

import tempfile
from pathlib import Path


def test_body_validator_no_subjective_warnings():
    """测试正文校验不返回主观 warning"""
    from body_validator import validate_body
    
    # 包含多个AI痕迹的正文（只包含正文，不含工作卡）
    body_text = """# 第1章 测试

## 正文

小明微微一笑，看了看窗外。
他不由得想起了昨天的事情。
张三若有所思地点了点头。
小明微微一笑，表示同意。
张三若有所思，没有说话。

"这是一个测试对话。"小明说。
"""
    
    # 测试质量报告会记录AI痕迹，但不作为warning
    
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)
        result = validate_body(body_text, project_dir, 1, 1)
        
        # 应该通过（没有硬性错误）
        assert result.passed, f"应该通过，但有错误: {result.issues}"
        
        # 不应该有 subjective warning
        warnings = [i for i in result.issues if i.type == "warning"]
        assert len(warnings) == 0, f"不应该有warning，但有: {warnings}"
        
        # 但应该有 quality_report
        assert result.quality_report, "应该有质量报告"
        assert "ai_traces" in result.quality_report.get("metrics", {}), "质量报告应包含AI痕迹统计"
        
        print("✓ 主观标准已降级为info，不返回warning")


def test_field_inheritance():
    """测试工作卡字段继承"""
    from card_dispatcher import CardDispatcher
    from card_parser import extract_section, extract_all_bullets
    
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)
        
        # 创建第1章的工作卡（作为前一章）
        vol_dir = project_dir / "chapters" / "vol01"
        vol_dir.mkdir(parents=True)
        cards_dir = vol_dir / "cards"
        cards_dir.mkdir(parents=True)
        
        prev_card = cards_dir / "ch01_card.md"
        prev_card.write_text("""## 内部工作卡

### 1. 状态卡
- 主角当前位置：办公室
- 主角当前伤势/疲劳：健康
- 主角当前情绪：平静
- 主角当前目标：完成报告

### 3. 资源卡
- 需带到下章的状态：100金币
""", encoding="utf-8")
        
        dispatcher = CardDispatcher(project_dir)
        
        # 测试 _load_previous_state
        state = dispatcher._load_previous_state(1, 2)
        
        assert "主角当前位置" in state, "应继承位置"
        assert state["主角当前位置"] == "办公室", f"位置应为办公室，实为: {state.get('主角当前位置')}"
        assert "主角当前情绪" in state, "应继承情绪"
        assert state["主角当前情绪"] == "平静"
        assert "需带到下章的状态" in state, "应继承资源"
        assert state["需带到下章的状态"] == "100金币"
        
        print("✓ 字段继承加载正确")


def test_apply_inheritance():
    """测试自动填充继承字段"""
    from card_dispatcher import CardDispatcher
    
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)
        dispatcher = CardDispatcher(project_dir)
        
        previous_state = {
            "主角当前位置": "办公室",
            "主角当前情绪": "平静",
        }
        
        # 测试各种继承标记
        test_cases = [
            ("- 主角当前位置：继承上章", "- 主角当前位置：办公室"),
            ("- 主角当前位置：", "- 主角当前位置：办公室"),  # 空值
            ("- 主角当前位置：同上", "- 主角当前位置：办公室"),
            ("- 主角当前位置：会议室", "- 主角当前位置：会议室"),  # 实际值不变
            ("- 主角当前情绪：N/A", "- 主角当前情绪：平静"),
        ]
        
        for input_line, expected_line in test_cases:
            cards = f"## 内部工作卡\n\n### 1. 状态卡\n{input_line}\n"
            result = dispatcher._apply_inheritance(cards, previous_state)
            assert expected_line in result, f"输入: {input_line}\n期望包含: {expected_line}\n实际: {result}"
        
        print("✓ 自动继承填充正确")


def test_card_prompt_with_inheritance():
    """测试prompt包含继承信息"""
    from card_dispatcher import CardDispatcher
    
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)
        
        # 创建前一章工作卡
        vol_dir = project_dir / "chapters" / "vol01"
        vol_dir.mkdir(parents=True)
        cards_dir = vol_dir / "cards"
        cards_dir.mkdir(parents=True)
        
        prev_card = cards_dir / "ch01_card.md"
        prev_card.write_text("""## 内部工作卡

### 1. 状态卡
- 主角当前位置：办公室
- 主角当前情绪：平静
""", encoding="utf-8")
        
        # 创建正文
        body_file = vol_dir / "ch02_body.md"
        body_file.write_text("# 第2章 测试\n\n## 正文\n\n测试内容。", encoding="utf-8")
        
        # 创建context目录
        (project_dir / "context").mkdir(exist_ok=True)
        
        dispatcher = CardDispatcher(project_dir)
        result = dispatcher.dispatch(1, 2)
        
        assert result.status == "card_prompt_ready"
        
        prompt = Path(result.prompt_file).read_text(encoding="utf-8")
        
        # 检查prompt包含继承信息
        assert "前章结束状态" in prompt, "prompt应包含前章结束状态"
        assert "办公室" in prompt, "prompt应包含前一章位置"
        assert "继承上章" in prompt, "prompt应说明可继承"
        assert "实际值优先" in prompt, "prompt应说明实际值优先"
        
        print("✓ Prompt包含继承说明")


if __name__ == "__main__":
    print("Running inheritance tests...\n")
    
    test_body_validator_no_subjective_warnings()
    test_field_inheritance()
    test_apply_inheritance()
    test_card_prompt_with_inheritance()
    
    print("\n✅ All inheritance tests passed!")
    print("\n优化点已实现：")
    print("1. 正文校验：主观标准降级为info，不返回warning")
    print("2. 工作卡继承：自动从上一章填充字段值")
    print("3. 继承标记：支持'继承上章'/空值/N/A/同上")
    print("4. 实际值优先：子代理填写的值优先于继承值")
    print("5. Prompt指导：明确说明哪些字段可继承")
