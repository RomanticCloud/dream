#!/usr/bin/env python3
"""章节索引缓存 - 避免每次遍历目录"""

from __future__ import annotations

import json
import time
from pathlib import Path

INDEX_FILE = "context/chapter_index.json"


def _get_all_chapter_files(project_dir: Path):
    """获取所有章节文件及其mtime"""
    chapters = []
    chapters_dir = project_dir / "chapters"
    if not chapters_dir.exists():
        return chapters
    
    for vol_dir in chapters_dir.iterdir():
        if not vol_dir.is_dir() or not vol_dir.name.startswith("vol"):
            continue
        vol_num = int(vol_dir.name.replace("vol", ""))
        for ch_file in vol_dir.glob("ch*.md"):
            if "_body" in ch_file.name or "_card" in ch_file.name:
                continue
            ch_num = int(ch_file.stem.replace("ch", ""))
            stat = ch_file.stat()
            chapters.append({
                "vol": vol_num,
                "ch": ch_num,
                "path": str(ch_file),
                "mtime": stat.st_mtime,
                "size": stat.st_size,
            })
    
    return sorted(chapters, key=lambda x: (x["vol"], x["ch"]))


def update_chapter_index(project_dir: Path, force: bool = False) -> dict:
    """更新章节索引
    
    Args:
        project_dir: 项目目录
        force: 强制重建索引
    
    Returns:
        索引字典
    """
    index_path = project_dir / INDEX_FILE
    chapters_dir = project_dir / "chapters"
    
    # 检查是否需要更新
    if not force and index_path.exists():
        try:
            index = json.loads(index_path.read_text(encoding="utf-8"))
            last_modified = index.get("last_modified", 0)
            
            # 检查目录是否有新文件
            needs_update = False
            if chapters_dir.exists():
                current_mtime = max(
                    (f.stat().st_mtime for f in chapters_dir.rglob("*.md")),
                    default=0
                )
                if current_mtime > last_modified:
                    needs_update = True
            
            if not needs_update:
                return index
        except (json.JSONDecodeError, OSError):
            # 索引文件损坏，重建
            pass
    
    # 重建索引
    chapters = _get_all_chapter_files(project_dir)
    
    index = {
        "version": 1,
        "last_modified": time.time(),
        "chapters": chapters,
        "total_chapters": len(chapters),
        "volumes": {},
    }
    
    # 计算每卷章节数
    for ch in chapters:
        vol = ch["vol"]
        if vol not in index["volumes"]:
            index["volumes"][vol] = {"chapters": 0, "last_ch": 0}
        index["volumes"][vol]["chapters"] += 1
        index["volumes"][vol]["last_ch"] = max(index["volumes"][vol]["last_ch"], ch["ch"])
    
    # 保存索引
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    
    return index


def get_chapter_index(project_dir: Path) -> dict:
    """获取章节索引（自动更新）"""
    return update_chapter_index(project_dir)


def invalidate_chapter_index(project_dir: Path):
    """手动失效索引（下一章生成前调用）"""
    index_path = project_dir / INDEX_FILE
    if index_path.exists():
        index_path.unlink()


def get_last_chapter_num_from_index(project_dir: Path, vol_num: int) -> int | None:
    """从索引获取指定卷的最后一章号"""
    index = get_chapter_index(project_dir)
    vol_info = index.get("volumes", {}).get(str(vol_num))
    if vol_info:
        return vol_info.get("last_ch")
    
    # 回退：直接扫描目录
    vol_dir = project_dir / "chapters" / f"vol{vol_num:02d}"
    if not vol_dir.exists():
        return None
    
    chapters = [int(f.stem.replace("ch", "")) for f in vol_dir.glob("ch*.md") if f.stem.replace("ch", "").isdigit()]
    return max(chapters) if chapters else None
