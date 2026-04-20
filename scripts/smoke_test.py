#!/usr/bin/env python3
"""Minimal smoke test for the dream skill."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent


def run(command: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(command, cwd=cwd, capture_output=True, text=True)


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def build_fixture(root: Path) -> None:
    write(root / "wizard_state.json", """{
  "basic_specs": {"chapter_length": "3500-4500字", "chapter_length_min": 3500, "chapter_length_max": 4500, "pacing": "偏快（每章推进）", "style_tone": "悬疑推理", "main_genres": ["悬疑推理"]},
  "positioning": {"narrative_style": "第三人称有限视角", "main_conflicts": ["谜题揭晓", "危机追逐"], "reader_hooks": ["看真相浮出"], "core_promise": "主角在迷雾中逼近真相"},
  "world": {"setting_type": "现代都市", "society_structure": "平衡制衡", "main_scene": ["旧城区档案馆"]},
  "volume_architecture": {"volume_count": 2, "chapters_per_volume": 2},
  "batch_plan": {"first_volume_goal": "找到失踪档案", "first_volume_hook": "第二份证词出现"},
  "naming": {"selected_book_title": "档案馆迷案"}
}""")
    write(root / "reference" / "卷纲总表.md", """# 卷纲总表

## 第1卷 · 初始阶段
- 卷定位：故事开篇，建立谜案基础
- 卷目标：找到失踪档案
- 核心冲突：谜题揭晓、危机追逐
- 卷尾钩子：第二份证词出现
- 预估章数：2章

## 第2卷 · 阶段2
- 卷定位：故事推进，冲突升级
- 卷目标：追查证词来源
- 核心冲突：谜题揭晓、危机追逐
- 卷尾钩子：真正嫌疑人现身
- 预估章数：2章
""")
    write(root / "chapters" / "vol01" / "001_第1章.md", """# 第1章

## 正文

林舟走进旧城区档案馆，发现火灾档案被抽走，只剩下残缺目录页。他借着整理旧报纸的机会进入封存区，沿着灰尘的断痕找到被人翻动过的铁柜。管理员陈叔神色复杂，却还是低声提醒他昨晚有人来过。林舟没有追问，只是把注意力放回那页缺失的目录，确认这不是普通遗失，而是有人带着明确目的抽走了关键纸档。就在他准备离开时，页脚又露出了一道陌生签名，像是故意留下来的第二重指引。

## 内部工作卡

### 1. 状态卡
- 主角当前位置：旧城区档案馆封存区
- 主角当前情绪：警惕而兴奋
- 主角当前目标：确认失踪档案去向
- 本章结束后的状态变化：掌握第一条直指火灾档案的线索

### 2. 情节卡
- 核心冲突：进入封存区寻找档案
- 关键事件：发现火灾档案被抽走并获得备用钥匙
- 转折点：页脚出现陌生签名

### 3. 资源卡
- 获得：值班钥匙
- 消耗：管理员信任额度
- 伏笔：陌生签名与火灾档案的关系

### 4. 关系卡
- 主要人物：林舟、陈叔
- 人物变化：林舟与陈叔形成有限合作

### 5. 情感弧卡
- 起始情绪：谨慎
- 变化过程：怀疑转为兴奋
- 目标情绪：坚定

### 6. 承上启下卡
- 承接：继续追查签名来源
- 铺垫：档案馆深处还藏着第二份证词
""")
    write(root / "chapters" / "vol01" / "002_第2章.md", """# 第2章

## 正文

林舟顺着陌生签名查到许衡，又在地下整理室找到第二份证词复印件。证词提到火灾发生前，最关键的一批纸档曾被提前转移，说明整场事故背后另有安排。陈叔终于承认自己当年替人开过一次门，但他从未真正见过取档人的正脸。林舟对照字迹和门禁登记，确认许衡只是被推到前台的中间人，真正的取档人另有其人，而且已经在证词背面留下了新的地址。事情暂时告一段落，但新的追查方向已经被明确锁定。

## 内部工作卡

### 1. 状态卡
- 主角当前位置：档案馆地下整理室
- 主角当前情绪：紧绷但清醒
- 主角当前目标：追查新地址与真正取档人
- 本章结束后的状态变化：锁定下一卷的调查方向

### 2. 情节卡
- 核心冲突：在时间压力下拿到第二份证词
- 关键事件：确认许衡身份并得到新地址
- 转折点：真正取档人并非许衡

### 3. 资源卡
- 获得：第二份证词复印件
- 消耗：陈叔的隐瞒空间
- 伏笔：新地址背后可能藏着真正的取档人

### 4. 关系卡
- 主要人物：林舟、陈叔、许衡
- 人物变化：林舟确认陈叔可被有限信任

### 5. 情感弧卡
- 起始情绪：压迫
- 变化过程：逼近真相后的冷静
- 目标情绪：专注

### 6. 承上启下卡
- 承接：追查新地址与取档人
- 铺垫：第二卷从新地址切入真正嫌疑人
""")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="dream_smoke_") as temp_dir:
        root = Path(temp_dir)
        build_fixture(root)

        compile_result = run([sys.executable, "-m", "py_compile", *[str(path) for path in SCRIPT_DIR.glob("*.py")]], root)
        if compile_result.returncode != 0:
            print(compile_result.stderr or compile_result.stdout)
            return 1

        enrich_result = run([sys.executable, str(SCRIPT_DIR / "volume_state_enricher.py"), str(root), "1"], root)
        if enrich_result.returncode != 0:
            print(enrich_result.stderr or enrich_result.stdout)
            return 1

        flow_result = run([sys.executable, str(SCRIPT_DIR / "writing_flow.py"), str(root)], root)
        if "本卷检查已通过" not in flow_result.stdout:
            print(flow_result.stdout)
            print(flow_result.stderr)
            return 1

        menu_result = run([sys.executable, str(SCRIPT_DIR / "strict_interactive_runner.py"), "action-menu", str(root)], root)
        if "查看卷沉淀" not in menu_result.stdout:
            print(menu_result.stdout)
            return 1

        volume_check_result = run([sys.executable, str(SCRIPT_DIR / "volume_ending_checker.py"), str(root), "1"], root)
        if volume_check_result.returncode != 0:
            print(volume_check_result.stdout)
            print(volume_check_result.stderr)
            return 1

        revision_state_text = (root / "REVISION_STATE.json").read_text(encoding="utf-8")
        if '"status": "passed"' not in revision_state_text:
            print(revision_state_text)
            return 1

        volume_memory_text = (root / "reference" / "卷沉淀" / "vol01_state.json").read_text(encoding="utf-8")
        if '"stable_facts"' not in volume_memory_text or '"unverified_claims"' not in volume_memory_text or '"conflicts"' not in volume_memory_text:
            print(volume_memory_text)
            return 1

        prompt_result = run([sys.executable, str(SCRIPT_DIR / "new_chapter.py"), str(root), "--prompt-only"], root)
        if prompt_result.returncode != 0:
            print(prompt_result.stderr or prompt_result.stdout)
            return 1

        prompt_file = root / "chapters" / "vol02" / "001_draft_prompt.md"
        prompt_text = prompt_file.read_text(encoding="utf-8")
        if "项目动态沉淀（后文依据）" not in prompt_text or "追查新地址与真正取档人" not in prompt_text or "已验证稳定事实" not in prompt_text or "仅可谨慎使用的未证实信息" not in prompt_text:
            print(prompt_text)
            return 1

        menu_after_pass = run([sys.executable, str(SCRIPT_DIR / "strict_interactive_runner.py"), "action-menu", str(root)], root)
        if "查看卷沉淀" not in menu_after_pass.stdout:
            print(menu_after_pass.stdout)
            return 1

        scaffold_result = run([sys.executable, str(SCRIPT_DIR / "new_chapter.py"), str(root)], root)
        if scaffold_result.returncode != 0:
            print(scaffold_result.stdout)
            print(scaffold_result.stderr)
            return 1

        chapter_issue_result = run([sys.executable, str(SCRIPT_DIR / "chapter_validator.py"), str(root), "2", "1", "--threshold", "0.85", "--json"], root)
        if chapter_issue_result.returncode == 0:
            print(chapter_issue_result.stdout)
            return 1

        revision_after_issue = (root / "REVISION_STATE.json").read_text(encoding="utf-8")
        if 'pending_regenerate' not in revision_after_issue and 'pending_polish' not in revision_after_issue:
            print(revision_after_issue)
            return 1

        menu_after_issue = run([sys.executable, str(SCRIPT_DIR / "strict_interactive_runner.py"), "action-menu", str(root)], root)
        if "整章重写" not in menu_after_issue.stdout and "AI润色" not in menu_after_issue.stdout:
            print(menu_after_issue.stdout)
            return 1

        print("dream smoke test passed")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
