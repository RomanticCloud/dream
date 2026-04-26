#!/usr/bin/env python3
"""测试分离式章节生成流程"""

import json
import tempfile
from pathlib import Path


def test_generation_state():
    """测试状态持久化"""
    from generation_state import (
        save_generation_state,
        load_generation_state,
        update_generation_state,
        cleanup_generation_state,
        get_generation_phase,
    )
    
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)
        
        # 测试保存和加载
        state = {"phase": "body_required", "current_vol": 1, "current_ch": 1}
        save_generation_state(project_dir, state)
        loaded = load_generation_state(project_dir)
        assert loaded == state
        
        # 测试更新
        update_generation_state(project_dir, {"body_file": "test.md"})
        loaded = load_generation_state(project_dir)
        assert loaded["body_file"] == "test.md"
        
        # 测试获取阶段
        phase = get_generation_phase(project_dir)
        assert phase == "body_required"
        
        # 测试清理
        cleanup_generation_state(project_dir)
        assert not load_generation_state(project_dir)
        
        print("✓ generation_state tests passed")


def test_body_validator():
    """测试正文校验器"""
    from body_validator import validate_body, count_words, extract_body
    
    # 测试字数统计
    text = "这是一个测试文本，包含一些中文字符。"
    assert count_words(text) == 18  # 去除空白后的字符数
    
    # 测试正文提取
    content = "# 第一章 标题\n\n## 正文\n\n这是正文内容。\n\n## 内部工作卡\n\n### 1. 状态卡"
    body = extract_body(content)
    assert "这是正文内容" in body
    assert "## 内部工作卡" not in body
    
    print("✓ body_validator tests passed")


def test_dispatchers_import():
    """测试调度器导入"""
    from body_dispatcher import BodyDispatcher
    from card_dispatcher import CardDispatcher
    
    print("✓ dispatchers imported successfully")


def test_orchestrator_commands():
    """测试 orchestrator 命令"""
    import subprocess
    
    # 测试帮助信息
    result = subprocess.run(
        ["python3", "dream_orchestrator.py", "--help"],
        capture_output=True,
        text=True,
        cwd="/home/ubuntu/.opencode/skills/dream/scripts",
    )
    assert "submit-body" in result.stdout
    assert "submit-cards" in result.stdout
    
    print("✓ orchestrator commands available")


def test_continuous_writer_modes():
    """测试 continuous_writer 新模式"""
    import subprocess
    
    result = subprocess.run(
        ["python3", "continuous_writer.py", "--help"],
        capture_output=True,
        text=True,
        cwd="/home/ubuntu/.opencode/skills/dream/scripts",
    )
    assert "body-only" in result.stdout
    assert "card-only" in result.stdout
    assert "auto" in result.stdout
    
    print("✓ continuous_writer modes available")


if __name__ == "__main__":
    print("Running separation generation tests...\n")
    
    test_generation_state()
    test_body_validator()
    test_dispatchers_import()
    test_orchestrator_commands()
    test_continuous_writer_modes()
    
    print("\n✅ All tests passed!")
    print("\n分离式章节生成流程已就绪：")
    print("1. 正文生成：BodyDispatcher + BodyValidator")
    print("2. 工作卡生成：CardDispatcher + ChapterValidator（完整校验）")
    print("3. 状态管理：GenerationState")
    print("4. Orchestrator 命令：submit-body, submit-cards")
    print("5. 自动重试：工作卡失败自动重试3次")
