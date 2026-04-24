#!/usr/bin/env python3
"""Unified chapter/body/card view helpers for dream scripts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from card_parser import BODY_MARKER, CARD_MARKER
from path_rules import chapter_card_file, chapter_file


@dataclass
class ChapterView:
    vol_num: int
    ch_num: int
    chapter_path: Path
    card_path: Path
    raw_body_file: str
    raw_card_file: str
    body_text: str
    card_text: str
    merged_text: str
    has_body_marker: bool
    has_inline_card: bool
    has_separate_card: bool

    @property
    def is_split_valid(self) -> bool:
        return self.has_body_marker and not self.has_inline_card and self.has_separate_card


def _normalize_body_text(text: str) -> str:
    return text.rstrip() + "\n"


def _normalize_card_text(text: str) -> str:
    return text.strip() + "\n" if text.strip() else ""


def load_chapter_view(project_dir: Path, vol_num: int, ch_num: int) -> ChapterView:
    chapter_path = chapter_file(project_dir, vol_num, ch_num)
    card_path = chapter_card_file(project_dir, vol_num, ch_num)

    raw_body_file = chapter_path.read_text(encoding="utf-8") if chapter_path.exists() else ""
    raw_card_file = card_path.read_text(encoding="utf-8") if card_path.exists() else ""

    has_inline_card = CARD_MARKER in raw_body_file
    has_body_marker = BODY_MARKER in raw_body_file
    has_separate_card = bool(raw_card_file.strip()) and CARD_MARKER in raw_card_file

    body_text = raw_body_file
    card_text = raw_card_file

    if has_inline_card:
        marker_index = raw_body_file.find(CARD_MARKER)
        body_text = raw_body_file[:marker_index].rstrip() + "\n"
        if not raw_card_file.strip():
            card_text = raw_body_file[marker_index:].strip() + "\n"

    normalized_body = _normalize_body_text(body_text) if body_text else ""
    normalized_card = _normalize_card_text(card_text)
    merged_text = normalized_body.rstrip()
    if normalized_card:
        merged_text = merged_text + "\n\n" + normalized_card.strip()
    if merged_text:
        merged_text += "\n"

    return ChapterView(
        vol_num=vol_num,
        ch_num=ch_num,
        chapter_path=chapter_path,
        card_path=card_path,
        raw_body_file=raw_body_file,
        raw_card_file=raw_card_file,
        body_text=normalized_body,
        card_text=normalized_card,
        merged_text=merged_text,
        has_body_marker=has_body_marker,
        has_inline_card=has_inline_card,
        has_separate_card=has_separate_card,
    )


def save_split_chapter(project_dir: Path, vol_num: int, ch_num: int, body_text: str, card_text: str) -> ChapterView:
    view = load_chapter_view(project_dir, vol_num, ch_num)
    view.chapter_path.parent.mkdir(parents=True, exist_ok=True)
    view.card_path.parent.mkdir(parents=True, exist_ok=True)
    view.chapter_path.write_text(_normalize_body_text(body_text), encoding="utf-8")
    view.card_path.write_text(_normalize_card_text(card_text), encoding="utf-8")
    return load_chapter_view(project_dir, vol_num, ch_num)
