#!/usr/bin/env python3
"""Accept safe plan deviations and persist aliases for later context."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from chapter_fact_extractor import extract_facts_from_file, fact_file
from common_io import load_json_file, save_json_file


DEVIATION_FILE = "context/accepted_deviations.json"


def accepted_deviation_file(project_dir: Path) -> Path:
    return project_dir / DEVIATION_FILE


def load_accepted_deviations(project_dir: Path) -> dict:
    return load_json_file(accepted_deviation_file(project_dir), default={"aliases": [], "facts": []})


def accept_from_facts(project_dir: Path, vol: int, ch: int) -> dict:
    facts_path = fact_file(project_dir, vol, ch)
    facts = load_json_file(facts_path, default={}) if facts_path.exists() else extract_facts_from_file(project_dir, vol, ch)
    payload = load_accepted_deviations(project_dir)
    aliases = payload.setdefault("aliases", [])
    facts_log = payload.setdefault("facts", [])
    existing_aliases = {(item.get("from"), item.get("to")) for item in aliases}
    for alias in facts.get("plan_deviation", {}).get("renamed_terms", []):
        key = (alias.get("from"), alias.get("to"))
        if key not in existing_aliases:
            aliases.append({**alias, "chapter": f"vol{vol:02d}/ch{ch:02d}"})
    existing_facts = {item.get("fact") for item in facts_log}
    for fact in facts.get("plan_deviation", {}).get("new_important_facts", [])[:5]:
        if fact and fact not in existing_facts:
            facts_log.append({"chapter": f"vol{vol:02d}/ch{ch:02d}", "fact": fact, "type": "accepted_deviation"})
    save_json_file(accepted_deviation_file(project_dir), payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="吸收正文合理偏移")
    parser.add_argument("project_dir")
    parser.add_argument("vol", type=int)
    parser.add_argument("ch", type=int)
    args = parser.parse_args()
    print(json.dumps(accept_from_facts(Path(args.project_dir).expanduser().resolve(), args.vol, args.ch), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
