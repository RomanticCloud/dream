#!/usr/bin/env python3
"""全局时间轴管理器 - 维护项目的全局时间线

功能：
- 记录每个章节结束时的时间节点
- 支持时间推进和对比
- 检测时间矛盾（时间倒流）

用法：
    python global_clock.py <project_dir> advance "3天" "2024-04-25"
    python global_clock.py <project_dir> status
    python global_clock.py <project_dir> init "2024-01-01"
"""

import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from common_io import load_json_file, save_json_file, extract_section, extract_bullets, parse_date


class TimeError(ValueError):
    """时间相关错误"""
    pass


class GlobalClock:
    """全局时间轴管理器"""

    CLOCK_FILE = "GLOBAL_CLOCK.json"

    UNIT_TO_DAYS = {
        "小时": 1 / 24,
        "天": 1,
        "日": 1,
        "月": 30,
        "个月": 30,
        "年": 365,
    }

    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        self.context_dir = project_dir / "context"
        self.context_dir.mkdir(exist_ok=True)
        self.clock_file = self.context_dir / self.CLOCK_FILE

    def load(self) -> dict:
        """加载时间轴"""
        if self.clock_file.exists():
            return load_json_file(self.clock_file)

        return self._create_default()

    def _create_default(self) -> dict:
        """创建默认时间轴"""
        return {
            "epoch": {
                "year": 2024,
                "month": 1,
                "day": 1,
                "description": "开篇时间点"
            },
            "current": {
                "year": 2024,
                "month": 1,
                "day": 1,
                "hour": 0,
                "description": "2024-01-01"
            },
            "chapters": [],
            "milestones": {}
        }

    def save(self, clock: dict):
        """保存时间轴"""
        save_json_file(self.clock_file, clock)

    def initialize(self, start_date: str = None) -> dict:
        """初始化时间轴

        Args:
            start_date: 起始日期，格式 YYYY-MM-DD

        Returns:
            初始化后的时间轴
        """
        clock = self._create_default()

        if start_date:
            year, month, day = self._parse_date(start_date)
            clock["epoch"] = {
                "year": year,
                "month": month,
                "day": day,
                "description": start_date
            }
            clock["current"] = {
                "year": year,
                "month": month,
                "day": day,
                "hour": 0,
                "description": start_date
            }

        self.save(clock)
        return clock

    def _parse_date(self, text: str) -> tuple[int, int, int]:
        """解析日期文本

        Returns:
            (year, month, day) 元组
        """
        try:
            return parse_date(text)
        except ValueError as e:
            raise TimeError(str(e))

    def _to_datetime(self, time_dict: dict) -> datetime:
        """将时间字典转换为datetime对象"""
        return datetime(
            time_dict["year"],
            time_dict["month"],
            time_dict["day"],
            time_dict.get("hour", 0)
        )

    def _from_datetime(self, dt: datetime, description: str = None) -> dict:
        """将datetime转换为时间字典"""
        return {
            "year": dt.year,
            "month": dt.month,
            "day": dt.day,
            "hour": dt.hour,
            "description": description or dt.strftime("%Y-%m-%d %H:%M")
        }

    def parse_elapsed(self, text: str) -> timedelta:
        """解析时间流逝文本

        Args:
            text: 时间流逝描述，如 "2小时"、"3天"、"半个月"

        Returns:
            timedelta 对象
        """
        text = text.strip()

        patterns = [
            (r"(\d+(?:\.\d+)?)\s*小时", 1 / 24),
            (r"(\d+(?:\.\d+)?)\s*天", 1),
            (r"(\d+(?:\.\d+)?)\s*月", 30),
            (r"(\d+(?:\.\d+)?)\s*个月", 30),
            (r"(\d+(?:\.\d+)?)\s*年", 365),
        ]

        for pattern, days_factor in patterns:
            match = re.search(pattern, text)
            if match:
                value = float(match.group(1))
                days = value * days_factor
                return timedelta(days=days)

        raise TimeError(f"无法解析时间流逝: {text}")

    def parse_time_point(self, text: str) -> Optional[datetime]:
        """解析时间点文本

        Args:
            text: 时间点描述，如 "2024-04-22"、"比ch02晚3天"

        Returns:
            datetime 对象，如果无法解析返回 None
        """
        text = text.strip()

        if not text:
            return None

        # 绝对日期
        if re.match(r"\d{4}-", text):
            try:
                year, month, day = self._parse_date(text)
                return datetime(year, month, day)
            except:
                pass

        # 相对引用
        if "比" in text and "晚" in text:
            return self._parse_relative_forward(text)
        if "比" in text and "早" in text:
            return self._parse_relative_backward(text)
        if "之后" in text or "之后" in text:
            return self._parse_relative_forward(text)

        return None

    def _parse_relative_forward(self, text: str) -> Optional[datetime]:
        """解析相对时间：比XX晚Y天"""
        # 比ch02晚3天
        match = re.search(r"比(\w+)\s*晚\s*(\d+)\s*天", text)
        if match:
            ref_chapter = match.group(1)
            days = int(match.group(2))
            ref_time = self.find_chapter_time(ref_chapter)
            if ref_time:
                return ref_time + timedelta(days=days)

        # ch02之后
        match = re.search(r"(\w+)\s*之后", text)
        if match:
            ref_chapter = match.group(1)
            ref_time = self.find_chapter_time(ref_chapter)
            if ref_time:
                return ref_time + timedelta(days=1)

        return None

    def _parse_relative_backward(self, text: str) -> Optional[datetime]:
        """解析相对时间：比XX早Y天"""
        match = re.search(r"比(\w+)\s*早\s*(\d+)\s*天", text)
        if match:
            ref_chapter = match.group(1)
            days = int(match.group(2))
            ref_time = self.find_chapter_time(ref_chapter)
            if ref_time:
                return ref_time - timedelta(days=days)

        return None

    def find_chapter_time(self, chapter_id: str) -> Optional[datetime]:
        """查找指定章节的时间点"""
        clock = self.load()

        # 规范化 chapter_id
        if not chapter_id.startswith("ch"):
            chapter_id = "ch" + chapter_id.zfill(2)

        for ch in clock.get("chapters", []):
            if ch["id"] == chapter_id or ch["id"].endswith(chapter_id):
                if "date" in ch:
                    try:
                        year, month, day = self._parse_date(ch["date"])
                        return datetime(year, month, day)
                    except:
                        pass

        return None

    def advance(self, elapsed: str, time_point: str, chapter_id: str) -> dict:
        """推进时间轴

        Args:
            elapsed: 时间流逝描述，如 "3天"
            time_point: 结束时时间点，如 "2024-04-22"
            chapter_id: 章节ID，如 "ch01"

        Returns:
            更新后的当前时间字典
        """
        clock = self.load()
        current_dt = self._to_datetime(clock["current"])

        # 解析时间流逝
        elapsed_delta = self.parse_elapsed(elapsed)

        # 解析时间点
        new_time_point = None

        # 尝试解析为绝对日期
        try:
            year, month, day = self._parse_date(time_point)
            new_time_point = datetime(year, month, day)
        except:
            pass

        # 尝试解析为相对引用
        if new_time_point is None:
            new_time_point = self.parse_time_point(time_point)

        # 如果都无法解析，使用 current + elapsed
        if new_time_point is None:
            new_time_point = current_dt + elapsed_delta

        # 检查时间是否倒流
        if new_time_point < current_dt:
            raise TimeError(
                f"时间倒流错误：当前时间 {current_dt.date()}，"
                f"新时间 {new_time_point.date()}，章节 {chapter_id}"
            )

        # 更新 current
        clock["current"] = self._from_datetime(new_time_point, time_point)

        # 添加章节记录
        chapter_entry = {
            "id": chapter_id,
            "elapsed": elapsed,
            "date": time_point,
            "datetime": new_time_point.isoformat()
        }

        # 更新或添加章节记录
        chapters = clock.get("chapters", [])
        for i, ch in enumerate(chapters):
            if ch["id"] == chapter_id:
                chapters[i] = chapter_entry
                break
        else:
            chapters.append(chapter_entry)

        clock["chapters"] = chapters
        self.save(clock)

        return clock["current"]

    def validate(self, elapsed: str, time_point: str, chapter_id: str) -> tuple[bool, str]:
        """验证时间是否合理

        Args:
            elapsed: 时间流逝
            time_point: 时间点
            chapter_id: 章节ID

        Returns:
            (is_valid, error_message)
        """
        clock = self.load()
        current_dt = self._to_datetime(clock["current"])

        # 检查时间点是否有效
        new_time_point = None

        try:
            year, month, day = self._parse_date(time_point)
            new_time_point = datetime(year, month, day)
        except:
            new_time_point = self.parse_time_point(time_point)

        if new_time_point is None:
            return False, f"无法解析时间点: {time_point}"

        if new_time_point < current_dt:
            return False, (
                f"时间倒流：当前 {current_dt.date()}，"
                f"新时间 {new_time_point.date()}"
            )

        return True, ""

    def advance_from_card(self, card_file: Path, vol_num: int, ch_num: int) -> dict:
        """从卡片文件读取时间信息并推进时间轴

        Args:
            card_file: 卡片文件路径
            vol_num: 卷号
            ch_num: 章号

        Returns:
            更新后的当前时间字典

        Raises:
            TimeError: 时间推进失败
        """
        if not card_file.exists():
            raise TimeError(f"卡片文件不存在: {card_file}")

        content = card_file.read_text(encoding="utf-8")

        # 从状态卡提取时间信息
        status_card = extract_section(content, "### 1. 状态卡")
        if not status_card:
            raise TimeError("卡片中未找到状态卡")

        bullets = extract_bullets(status_card)

        elapsed = bullets.get("本章时间流逝", "")
        time_point = bullets.get("本章结束时时间点", "")

        if not elapsed:
            raise TimeError("状态卡中未找到'本章时间流逝'")
        if not time_point:
            raise TimeError("状态卡中未找到'本章结束时时间点'")

        chapter_id = f"ch{ch_num:02d}"
        return self.advance(elapsed, time_point, chapter_id)

    def get_status(self) -> dict:
        """获取当前时间状态"""
        clock = self.load()
        return {
            "current": clock["current"],
            "chapter_count": len(clock.get("chapters", [])),
            "last_chapter": clock["chapters"][-1] if clock.get("chapters") else None
        }

    def print_status(self):
        """打印当前状态"""
        status = self.get_status()
        print(f"\n{'='*50}")
        print("【全局时间轴】")
        print(f"{'='*50}")
        print(f"当前时间: {status['current']['description']}")
        print(f"章节数: {status['chapter_count']}")
        if status["last_chapter"]:
            print(f"最后一章: {status['last_chapter']['id']} ({status['last_chapter']['date']})")
        print()


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法:")
        print("  python global_clock.py <project_dir> status")
        print("  python global_clock.py <project_dir> init <YYYY-MM-DD>")
        print("  python global_clock.py <project_dir> advance <elapsed> <time_point> [chapter_id]")
        print()
        print("示例:")
        print("  python global_clock.py . status")
        print("  python global_clock.py . init 2024-01-01")
        print("  python global_clock.py . advance '3天' '2024-04-25' ch03")
        sys.exit(1)

    project_dir = Path(sys.argv[1]).resolve()
    if not project_dir.exists():
        print(f"错误: 项目目录不存在: {project_dir}")
        sys.exit(1)

    clock = GlobalClock(project_dir)

    if len(sys.argv) < 3:
        clock.print_status()
        sys.exit(0)

    command = sys.argv[2]

    if command == "status":
        clock.print_status()

    elif command == "init":
        if len(sys.argv) < 4:
            print("错误: init 需要日期参数")
            sys.exit(1)
        start_date = sys.argv[3]
        result = clock.initialize(start_date)
        print(f"✅ 时间轴已初始化: {result['current']['description']}")

    elif command == "advance":
        if len(sys.argv) < 5:
            print("错误: advance 需要 elapsed 和 time_point 参数")
            sys.exit(1)
        elapsed = sys.argv[3]
        time_point = sys.argv[4]
        chapter_id = sys.argv[5] if len(sys.argv) > 5 else f"ch{(len(clock.load().get('chapters', [])) + 1):02d}"

        try:
            result = clock.advance(elapsed, time_point, chapter_id)
            print(f"✅ 时间已推进: {result['description']}")
            print(f"   章节: {chapter_id}")
            print(f"   流逝: {elapsed}")
        except TimeError as e:
            print(f"❌ 时间错误: {e}")
            sys.exit(1)

    else:
        print(f"错误: 未知命令 {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
