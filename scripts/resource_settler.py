#!/usr/bin/env python3
"""资源结算模块 - 解析章节资源卡中的增减量指令，计算并更新库存状态

用法：
    python resource_settler.py <project_dir> [vol] [ch]
    python resource_settler.py <project_dir>  # 结算当前最新章节
"""

import json
import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from common_io import extract_section, load_json_file, save_json_file


class ResourceSettler:
    """资源结算器"""

    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        self.context_dir = project_dir / "context"
        self.context_dir.mkdir(exist_ok=True)

        self.inventory_file = self.context_dir / "RESOURCE_INVENTORY.json"
        self.ability_file = self.context_dir / "ABILITY_STATE.json"
        self.log_file = self.context_dir / "resource_change.log"

        self._setup_logging()

    def _setup_logging(self):
        """设置日志"""
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('[%(levelname)s] %(message)s'))
            self.logger.addHandler(handler)

    def parse_deltas(self, text: str) -> dict[str, int]:
        """解析文本中的增减量指令

        Args:
            text: 包含资源的文本，如 "+500灵石"、"-200金币"

        Returns:
            资源名称到增量的字典，如 {"灵石": 500, "金币": -200}

        Examples:
            "+500灵石" → {"灵石": 500}
            "-200金币 +100银两" → {"金币": -200, "银两": 100}
        """
        # 匹配 [+/-]数字[资源名]
        pattern = r'([+-])(\d+)\s*([\u4e00-\u9fa5a-zA-Z]+)'
        matches = re.findall(pattern, text)

        deltas = {}
        for sign, number, name in matches:
            value = int(sign + number)
            name = name.strip()
            if name in deltas:
                deltas[name] += value
            else:
                deltas[name] = value

        return deltas

    def load_or_create_inventory(self) -> dict:
        """加载或创建资源库存"""
        if self.inventory_file.exists():
            inventory = load_json_file(self.inventory_file)
            self.logger.info(f"加载资源库存: {self.inventory_file}")
        else:
            inventory = {}
            self.logger.info("创建新的资源库存文件")

        return inventory

    def load_or_create_ability_state(self) -> dict:
        """加载或创建能力状态"""
        if self.ability_file.exists():
            ability_state = load_json_file(self.ability_file)
            self.logger.info(f"加载能力状态: {self.ability_file}")
        else:
            ability_state = {
                "战力损耗比例": 0,
                "底牌列表": [],
                "可用底牌": []
            }
            self.logger.info("创建新的能力状态文件")

        return ability_state

    def validate_not_negative(self, inventory: dict) -> list[dict]:
        """检查库存是否有负数或其他异常

        Args:
            inventory: 资源库存字典

        Returns:
            警告列表，每项包含 resource, value, message
        """
        warnings = []

        for resource, value in inventory.items():
            if value < 0:
                warnings.append({
                    "resource": resource,
                    "value": value,
                    "message": f"{resource}为负数 ({value})，可能计算错误"
                })

            if value == 0 and resource not in ["战力损耗比例"]:
                warnings.append({
                    "resource": resource,
                    "value": value,
                    "message": f"{resource}已耗尽"
                })

        return warnings

    def load_chapter_card(self, vol: int, ch: int) -> Optional[str]:
        """加载章节卡片文本

        Args:
            vol: 卷号
            ch: 章号

        Returns:
            卡片文本，未找到返回None
        """
        chapters_dir = self.project_dir / "chapters" / f"vol{vol:02d}"
        chapter_file = chapters_dir / "cards" / f"ch{ch:02d}_card.md"

        if not chapter_file.exists():
            self.logger.error(f"卡片文件不存在: {chapter_file}")
            return None

        return chapter_file.read_text(encoding="utf-8")

    def extract_resource_deltas(self, card_text: str) -> dict[str, int]:
        """从卡片文本中提取资源增减量

        Args:
            card_text: 卡片文本

        Returns:
            资源名称到增量的字典
        """
        all_deltas = {}

        # 提取资源卡
        resource_card = extract_section(card_text, "### 3. 资源卡")
        if resource_card:
            deltas = self.parse_deltas(resource_card)
            for k, v in deltas.items():
                all_deltas[k] = all_deltas.get(k, 0) + v

        return all_deltas

    def extract_ability_updates(self, card_text: str) -> dict:
        """从卡片文本中提取能力状态更新

        Args:
            card_text: 卡片文本

        Returns:
            能力更新字典
        """
        updates = {}

        # 提取战力卡（POWER_SYSTEM项目）
        power_card = extract_section(card_text, "### 2. 战力卡")
        if power_card:
            # 解析战力损耗比例
            loss_pattern = r'战力损耗比例[：:]\s*[+-]?(\d+)%?'
            match = re.search(loss_pattern, power_card)
            if match:
                updates["战力损耗比例"] = int(match.group(1))

            # 解析底牌名称
            trump_pattern = r'使用的底牌名称[：:]\s*(.+)'
            match = re.search(trump_pattern, power_card)
            if match:
                trump_text = match.group(1).strip()
                trump_list = [t.strip() for t in trump_text.split("/") if t.strip()]
                if trump_list:
                    updates["底牌列表"] = trump_list

        return updates

    def settle_chapter(self, vol: int, ch: int) -> dict:
        """结算指定章节的资源变化

        Args:
            vol: 卷号
            ch: 章号

        Returns:
            结算结果字典
        """
        result = {
            "chapter": f"vol{vol:02d}/ch{ch:02d}",
            "success": False,
            "resource_changes": [],
            "ability_updates": [],
            "warnings": [],
            "errors": []
        }

        # 1. 加载卡片文本
        card_text = self.load_chapter_card(vol, ch)
        if not card_text:
            result["errors"].append("无法加载卡片文件")
            return result

        # 2. 解析资源增减量
        resource_deltas = self.extract_resource_deltas(card_text)
        if not resource_deltas:
            self.logger.info("本章无资源变化")
        else:
            self.logger.info(f"解析到资源变化: {resource_deltas}")

        # 3. 解析能力更新
        ability_updates = self.extract_ability_updates(card_text)
        if ability_updates:
            self.logger.info(f"解析到能力更新: {ability_updates}")

        # 4. 加载库存
        inventory = self.load_or_create_inventory()

        # 5. 计算资源变化
        for resource, delta in resource_deltas.items():
            before = inventory.get(resource, 0)
            after = before + delta
            inventory[resource] = after

            result["resource_changes"].append({
                "resource": resource,
                "delta": delta,
                "before": before,
                "after": after
            })

        # 6. 检查负数
        warnings = self.validate_not_negative(inventory)
        result["warnings"] = warnings

        # 7. 保存资源库存
        save_json_file(self.inventory_file, inventory)
        self.logger.info(f"保存资源库存: {self.inventory_file}")

        # 8. 更新能力状态
        if ability_updates:
            ability_state = self.load_or_create_ability_state()

            if "战力损耗比例" in ability_updates:
                ability_state["战力损耗比例"] = ability_updates["战力损耗比例"]

            if "底牌列表" in ability_updates:
                # 追加新底牌
                existing = set(ability_state.get("底牌列表", []))
                new = set(ability_updates["底牌列表"])
                ability_state["底牌列表"] = list(existing | new)

            save_json_file(self.ability_file, ability_state)
            result["ability_updates"] = ability_updates
            self.logger.info(f"保存能力状态: {self.ability_file}")

        # 9. 记录日志
        self._append_to_log(result)

        result["success"] = True
        return result

    def _append_to_log(self, result: dict):
        """追加变更日志"""
        log_entries = []
        if self.log_file.exists():
            try:
                log_entries = json.loads(self.log_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                log_entries = []

        timestamp = datetime.now().isoformat()
        entry = {
            "timestamp": timestamp,
            "chapter": result["chapter"],
            "resource_changes": result["resource_changes"],
            "ability_updates": result["ability_updates"],
            "warnings": result["warnings"]
        }
        log_entries.append(entry)

        # 只保留最近100条记录
        if len(log_entries) > 100:
            log_entries = log_entries[-100:]

        save_json_file(self.log_file, log_entries)

    def print_result(self, result: dict):
        """打印结算结果"""
        print(f"\n{'='*50}")
        print(f"【资源结算】{result['chapter']}")
        print(f"{'='*50}")

        if not result["success"]:
            print("❌ 结算失败")
            for error in result["errors"]:
                print(f"   - {error}")
            return

        print("✅ 结算完成")

        # 资源变化
        if result["resource_changes"]:
            print("\n📦 资源变化:")
            for change in result["resource_changes"]:
                delta = change["delta"]
                delta_str = f"+{delta}" if delta > 0 else str(delta)
                print(f"   {change['resource']}: {change['before']} → {change['after']} ({delta_str})")

        # 能力更新
        if result["ability_updates"]:
            print("\n⚔️ 能力更新:")
            for key, value in result["ability_updates"].items():
                if key == "底牌列表":
                    print(f"   {key}: {value}")
                else:
                    print(f"   {key}: {value}")

        # 警告
        if result["warnings"]:
            print("\n⚠️ 警告:")
            for warning in result["warnings"]:
                print(f"   - {warning['message']}")

        print()

    def find_latest_chapter(self) -> tuple[int, int]:
        """查找当前最新章节

        Returns:
            (vol_num, ch_num)
        """
        chapters_dir = self.project_dir / "chapters"

        if not chapters_dir.exists():
            return 1, 1

        vol_dirs = sorted(chapters_dir.glob("vol*"), key=lambda p: p.name)
        if not vol_dirs:
            return 1, 1

        latest_vol = None
        latest_ch = 0

        for vol_dir in vol_dirs:
            vol_match = re.search(r"vol(\d+)", vol_dir.name)
            if not vol_match:
                continue

            vol_num = int(vol_match.group(1))
            cards_dir = vol_dir / "cards"

            if not cards_dir.exists():
                continue

            for card_file in cards_dir.glob("ch*_card.md"):
                ch_match = re.search(r"ch(\d+)", card_file.name)
                if ch_match:
                    ch_num = int(ch_match.group(1))
                    if ch_num > latest_ch:
                        latest_ch = ch_num
                        latest_vol = vol_num

        if latest_vol is None:
            return 1, 1

        return latest_vol, latest_ch


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法: python resource_settler.py <project_dir> [vol] [ch]")
        print("       python resource_settler.py <project_dir>  # 结算当前最新章节")
        sys.exit(1)

    project_dir = Path(sys.argv[1]).expanduser().resolve()
    if not project_dir.exists():
        print(f"错误: 项目目录不存在: {project_dir}")
        sys.exit(1)

    settler = ResourceSettler(project_dir)

    # 解析参数
    if len(sys.argv) >= 4:
        vol = int(sys.argv[2])
        ch = int(sys.argv[3])
    else:
        vol, ch = settler.find_latest_chapter()
        print(f"自动检测到最新章节: vol{vol:02d}/ch{ch:02d}")

    # 执行结算
    result = settler.settle_chapter(vol, ch)
    settler.print_result(result)

    # 根据结果返回退出码
    if not result["success"]:
        sys.exit(1)
    if result["warnings"]:
        sys.exit(2)  # 有警告但不失败
    sys.exit(0)


if __name__ == "__main__":
    main()
