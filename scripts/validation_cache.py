#!/usr/bin/env python3
"""校验结果缓存 - 避免重复校验已通过章节"""

from __future__ import annotations

import json
import time
from pathlib import Path
from dataclasses import asdict

CACHE_FILE = "context/validation_cache.json"


def _get_file_fingerprint(path: Path) -> str:
    """获取文件指纹（mtime + size）"""
    stat = path.stat()
    return f"{stat.st_mtime}:{stat.st_size}"


def get_cached_validation(project_dir: Path, vol: int, ch: int) -> dict | None:
    """获取缓存的校验结果
    
    Returns:
        缓存的校验结果字典，或 None（如果缓存不存在或已失效）
    """
    cache_path = project_dir / CACHE_FILE
    if not cache_path.exists():
        return None
    
    try:
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    
    key = f"vol{vol:02d}_ch{ch:02d}"
    if key not in cache:
        return None
    
    entry = cache[key]
    
    # 检查文件是否修改
    from path_rules import chapter_file
    chapter_path = chapter_file(project_dir, vol, ch)
    if not chapter_path.exists():
        return None
    
    current_fp = _get_file_fingerprint(chapter_path)
    if entry.get("fingerprint") != current_fp:
        return None  # 文件已修改，缓存失效
    
    return entry.get("result")


def save_validation_cache(project_dir: Path, vol: int, ch: int, result) -> None:
    """保存校验结果到缓存
    
    Args:
        project_dir: 项目目录
        vol: 卷号
        ch: 章号
        result: ValidationResult 对象
    """
    cache_path = project_dir / CACHE_FILE
    cache = {}
    
    if cache_path.exists():
        try:
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            cache = {}
    
    key = f"vol{vol:02d}_ch{ch:02d}"
    from path_rules import chapter_file
    chapter_path = chapter_file(project_dir, vol, ch)
    
    # 只缓存通过的校验结果
    if not result.passed:
        # 如果之前有缓存，删除它
        if key in cache:
            del cache[key]
            cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
        return
    
    cache[key] = {
        "fingerprint": _get_file_fingerprint(chapter_path),
        "timestamp": time.time(),
        "result": {
            "passed": result.passed,
            "issues": [{"type": i.type, "message": i.message} for i in result.issues],
            "word_count": result.word_count,
        }
    }
    
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def invalidate_validation_cache(project_dir: Path, vol: int, ch: int):
    """失效特定章节的缓存
    
    在章节被修改后调用
    """
    cache_path = project_dir / CACHE_FILE
    if not cache_path.exists():
        return
    
    try:
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return
    
    key = f"vol{vol:02d}_ch{ch:02d}"
    if key in cache:
        del cache[key]
        cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def clear_validation_cache(project_dir: Path):
    """清空所有校验缓存"""
    cache_path = project_dir / CACHE_FILE
    if cache_path.exists():
        cache_path.unlink()
