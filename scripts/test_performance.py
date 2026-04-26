#!/usr/bin/env python3
"""测试性能优化 - 验证实例缓存和索引缓存"""

import tempfile
from pathlib import Path
import time


def test_subagent_generator_cache():
    """测试 SubagentChapterGenerator 实例缓存"""
    from subagent_chapter_generator import SubagentChapterGenerator
    
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)
        
        # 创建测试章节
        for i in range(1, 6):
            vol_dir = project_dir / "chapters" / "vol01"
            vol_dir.mkdir(parents=True, exist_ok=True)
            ch_file = vol_dir / f"ch{i:02d}.md"
            ch_file.write_text(f"# 第{i}章 测试\n\n## 正文\n\n测试内容{i}。\n\n## 内部工作卡\n\n### 1. 状态卡\n- 地点：地点{i}", encoding="utf-8")
        
        gen = SubagentChapterGenerator(project_dir)
        
        # 准备完整的项目配置
        project_config = {
            "basic_specs": {
                "target_word_count": "10万字",
                "target_word_count_numeric": 100000,
                "chapter_length": "2000-2500字",
                "chapter_length_min": 2000,
                "chapter_length_max": 2500,
                "pacing": "偏快",
                "style_tone": "轻松幽默",
                "main_genres": ["都市生活"],
            },
            "positioning": {"narrative_style": "第三人称有限视角"},
            "naming": {"selected_book_title": "测试"},
            "protagonist": {"gender": "男"},
        }
        
        # 第一次构建 manifest（应该填充缓存）
        start = time.time()
        manifest1 = gen.build_context_manifest(1, 6, project_config)
        time1 = time.time() - start
        
        # 第二次构建 manifest（应该使用缓存）
        start = time.time()
        manifest2 = gen.build_context_manifest(1, 6, project_config)
        time2 = time.time() - start
        
        # 验证缓存有效
        assert time2 < time1, f"缓存未生效：第一次{time1:.3f}s，第二次{time2:.3f}s"
        assert len(gen._chapter_view_cache) == 5, f"缓存应该包含5章，实为{len(gen._chapter_view_cache)}"
        
        print(f"✓ SubagentChapterGenerator 缓存有效（第一次{time1:.3f}s，第二次{time2:.3f}s）")


def test_card_dispatcher_cache():
    """测试 CardDispatcher 上一章状态缓存"""
    from card_dispatcher import CardDispatcher
    
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)
        
        # 创建第1章工作卡
        vol_dir = project_dir / "chapters" / "vol01"
        vol_dir.mkdir(parents=True)
        cards_dir = vol_dir / "cards"
        cards_dir.mkdir(parents=True)
        
        prev_card = cards_dir / "ch01_card.md"
        prev_card.write_text("""## 内部工作卡

### 1. 状态卡
- 主角当前位置：办公室
- 主角当前情绪：平静

### 3. 资源卡
- 需带到下章的状态：100金币
""", encoding="utf-8")
        
        dispatcher = CardDispatcher(project_dir)
        
        # 第一次加载
        state1 = dispatcher._load_previous_state(1, 2)
        
        # 第二次加载（应该命中缓存）
        state2 = dispatcher._load_previous_state(1, 2)
        
        # 验证缓存命中
        assert len(dispatcher._previous_state_cache) == 1, "缓存应该包含1个条目"
        assert state1 == state2, "缓存结果应该一致"
        
        print("✓ CardDispatcher 状态缓存有效")


def test_chapter_index():
    """测试章节索引缓存"""
    from chapter_index import update_chapter_index, get_chapter_index
    
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)
        
        # 创建测试章节
        for vol in range(1, 3):
            for ch in range(1, 4):
                vol_dir = project_dir / "chapters" / f"vol{vol:02d}"
                vol_dir.mkdir(parents=True, exist_ok=True)
                ch_file = vol_dir / f"ch{ch:02d}.md"
                ch_file.write_text(f"# 第{ch}章", encoding="utf-8")
        
        # 第一次构建索引
        index1 = update_chapter_index(project_dir)
        
        # 第二次获取索引（应该复用缓存）
        index2 = get_chapter_index(project_dir)
        
        # 忽略时间戳比较
        assert index1["total_chapters"] == index2["total_chapters"], "总章节数应该一致"
        assert len(index1["chapters"]) == len(index2["chapters"]), "章节列表长度应该一致"
        assert index1["total_chapters"] == 6, f"应该有6章，实为{index1['total_chapters']}"
        assert 1 in index1["volumes"] or "1" in index1["volumes"], f"应该有卷1，实为{list(index1['volumes'].keys())}"
        assert 2 in index1["volumes"] or "2" in index1["volumes"], f"应该有卷2，实为{list(index1['volumes'].keys())}"
        
        print("✓ 章节索引缓存有效")


def test_validation_cache():
    """测试校验结果缓存"""
    from chapter_validator import ValidationResult, ValidationIssue
    from validation_cache import get_cached_validation, save_validation_cache
    
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)
        
        # 直接测试缓存的保存和读取
        result = ValidationResult(
            passed=True,
            issues=[],
            word_count=2000,
        )
        
        # 创建虚拟章节文件
        vol_dir = project_dir / "chapters" / "vol01"
        vol_dir.mkdir(parents=True)
        ch_file = vol_dir / "ch01.md"
        ch_file.write_text("# 第1章\n\n## 正文\n\n测试内容。", encoding="utf-8")
        
        # 保存缓存
        save_validation_cache(project_dir, 1, 1, result)
        
        # 读取缓存
        cached = get_cached_validation(project_dir, 1, 1)
        assert cached is not None, "应该有缓存"
        assert cached["passed"] is True, "缓存结果应该一致"
        assert cached["word_count"] == 2000, "字数应该一致"
        
        # 修改文件后缓存应该失效
        time.sleep(0.1)
        ch_file.write_text("# 第1章\n\n## 正文\n\n修改后的内容。", encoding="utf-8")
        
        cached2 = get_cached_validation(project_dir, 1, 1)
        assert cached2 is None, "文件修改后缓存应该失效"
        
        print("✓ 校验结果缓存有效（文件修改后正确失效）")


def test_incremental_manifest():
    """测试增量 Manifest 构建"""
    from subagent_chapter_generator import SubagentChapterGenerator
    
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)
        
        # 创建测试章节（1-5章）
        for i in range(1, 6):
            vol_dir = project_dir / "chapters" / "vol01"
            vol_dir.mkdir(parents=True, exist_ok=True)
            ch_file = vol_dir / f"ch{i:02d}.md"
            ch_file.write_text(f"# 第{i}章 测试\n\n## 正文\n\n测试内容{i}。\n\n## 内部工作卡\n\n### 1. 状态卡\n- 地点：地点{i}", encoding="utf-8")
        
        # 先构建第1章 manifest（完整构建）
        gen = SubagentChapterGenerator(project_dir)
        project_config = {
            "basic_specs": {
                "target_word_count": "10万字",
                "target_word_count_numeric": 100000,
                "chapter_length": "2000-2500字",
                "chapter_length_min": 2000,
                "chapter_length_max": 2500,
                "pacing": "偏快",
                "style_tone": "轻松幽默",
                "main_genres": ["都市生活"],
            },
            "positioning": {"narrative_style": "第三人称有限视角"},
            "naming": {"selected_book_title": "测试"},
            "protagonist": {"gender": "男"},
        }
        
        manifest1 = gen.build_context_manifest(1, 1, project_config)
        assert len(manifest1["previous_chapters"]) == 0, "第1章应该没有前文"
        
        # 构建第2章 manifest（应该使用增量构建）
        start = time.time()
        manifest2 = gen.build_context_manifest(1, 2, project_config)
        time2 = time.time() - start
        
        # 构建第3章 manifest（应该使用增量构建）
        start = time.time()
        manifest3 = gen.build_context_manifest(1, 3, project_config)
        time3 = time.time() - start
        
        # 验证增量构建结果正确
        assert len(manifest2["previous_chapters"]) == 1, f"第2章应该有1个前文，实为{len(manifest2['previous_chapters'])}"
        assert manifest2["previous_chapters"][0]["ch"] == 1, "第2章的前文应该是第1章"
        
        assert len(manifest3["previous_chapters"]) == 2, f"第3章应该有2个前文，实为{len(manifest3['previous_chapters'])}"
        assert manifest3["previous_chapters"][0]["ch"] == 1, "第3章的第一个前文应该是第1章"
        assert manifest3["previous_chapters"][1]["ch"] == 2, "第3章的第二个前文应该是第2章"
        
        # 验证 required_paths 正确递增
        assert len(manifest1["required_read_sequence"]) < len(manifest2["required_read_sequence"]), "第2章的路径应该比第1章多"
        assert len(manifest2["required_read_sequence"]) < len(manifest3["required_read_sequence"]), "第3章的路径应该比第2章多"
        
        # 验证 current_chapter 更新正确
        assert manifest2["current_chapter"]["ch"] == 2, "current_chapter 应该是第2章"
        assert manifest3["current_chapter"]["ch"] == 3, "current_chapter 应该是第3章"
        
        # 验证 task_context 更新正确
        assert manifest2["task_context"]["chapter_plan"] is None, "第2章的 chapter_plan 应该为 None"
        
        print(f"✓ 增量 Manifest 构建有效（第2章{time2:.4f}s，第3章{time3:.4f}s）")
        print(f"  - 第1章: {len(manifest1['previous_chapters'])} 前文")
        print(f"  - 第2章: {len(manifest2['previous_chapters'])} 前文")
        print(f"  - 第3章: {len(manifest3['previous_chapters'])} 前文")


if __name__ == "__main__":
    print("Running performance optimization tests...\n")
    
    test_subagent_generator_cache()
    test_card_dispatcher_cache()
    test_chapter_index()
    test_validation_cache()
    test_incremental_manifest()
    
    print("\n✅ All performance tests passed!")
    print("\n优化效果：")
    print("1. SubagentChapterGenerator: 实例缓存避免重复文件读取")
    print("2. CardDispatcher: 上一章状态缓存避免重复解析")
    print("3. chapter_index: 目录扫描结果持久化缓存")
    print("4. validation_cache: 已通过章节校验结果缓存")
