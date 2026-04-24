#!/usr/bin/env python3
"""Tests for resource_settler power-card parsing and state persistence."""

from __future__ import annotations

import sys
import tempfile
import json
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from resource_settler import ResourceSettler


CARD_TEXT = """## 内部工作卡

### 2. 战力卡
- 本章主要交手对象：赵烈
- 对方层级：淬体四重
- 主角是否越级：是
- 越级是否合理：依靠陷阱完成反制
- 是否暴露新底牌：是
- 具体战力损耗比例：-30%
- 使用的底牌名称：燃命剑/震岳符
- 本章战斗结果的后续影响：更高层级的敌人盯上主角

### 3. 资源卡
- 获得：+1擂台积分
- 消耗：-1震岳符
- 损失：-20药粉
"""


def test_extract_ability_updates_reads_standard_power_fields():
    with tempfile.TemporaryDirectory() as td:
        settler = ResourceSettler(Path(td))
        updates = settler.extract_ability_updates(CARD_TEXT)

        assert updates["战力损耗比例"] == 30
        assert updates["底牌列表"] == ["燃命剑", "震岳符"]


def test_settle_chapter_writes_normalized_state_files_and_is_idempotent():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        card_path = root / "chapters" / "vol01" / "cards" / "ch01_card.md"
        card_path.parent.mkdir(parents=True, exist_ok=True)
        card_path.write_text(CARD_TEXT, encoding="utf-8")

        settler = ResourceSettler(root)
        first = settler.settle_chapter(1, 1)
        second = settler.settle_chapter(1, 1)

        inventory = json.loads((root / "context" / "RESOURCE_INVENTORY.json").read_text(encoding="utf-8"))
        ability = json.loads((root / "context" / "ABILITY_STATE.json").read_text(encoding="utf-8"))

        assert first["success"] is True
        assert first["skipped"] is False
        assert second["success"] is True
        assert second["skipped"] is True

        assert inventory["resources"]["擂台积分"] == 1
        assert inventory["resources"]["震岳符"] == -1
        assert inventory["resources"]["药粉"] == -20
        assert inventory["last_updated_chapter"] == "vol01/ch01"
        assert inventory["applied_chapters"] == ["vol01/ch01"]

        assert ability["战力损耗比例"] == 30
        assert ability["底牌列表"] == ["燃命剑", "震岳符"]
        assert ability["可用底牌"] == ["燃命剑", "震岳符"]
        assert ability["last_updated_chapter"] == "vol01/ch01"
        assert ability["applied_chapters"] == ["vol01/ch01"]


if __name__ == "__main__":
    import traceback

    passed = 0
    failed = 0
    for name, func in sorted(globals().items()):
        if name.startswith("test_"):
            try:
                func()
                print(f"  PASS {name}")
                passed += 1
            except Exception:
                print(f"  FAIL {name}")
                traceback.print_exc()
                failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
