#!/usr/bin/env python3
"""Shared chapter and volume content checks."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Optional

from card_parser import extract_body, extract_section, extract_bullets
from rule_engine import CheckResult


INVALID_SPEAKERS = {
    "如果", "没有人", "有人", "虽然", "但是", "因为", "所以",
    "只见", "突然", "然后", "于是", "不过", "只是", "既然",
    "尽管", "果然", "原来", "难道", "岂非", "除非", "岂料",
    "谁知", "谁料", "岂知", "不料", "不想", "说道", "问道",
    "笑道", "怒道", "答道", "解释道", "回答道", "淡淡道",
    "缓缓道", "轻声道", "沉声道", "冷声道", "他", "她", "它",
}


def _collect_character_names(body: str) -> set[str]:
    names: set[str] = set()

    patterns = [
        r"([\u4e00-\u9fff]{2,4})(?:说道|回道|问道|笑道|怒道|冷声道|淡淡道|沉声道|轻声)",
        r"([\u4e00-\u9fff]{2,4})(?:看向|盯着|走进|望向|拦住|拦住|喊住)",
        r"([\u4e00-\u9fff]{2,6})(?:哥|叔|姐|弟|爷|婆|医|馆|长|司|总|主)",
        r"(?:线人|证人|神秘人|黑人|白人|某人)",
    ]
    for pattern in patterns:
        names.update(re.findall(pattern, body))

    prefix_patterns = [
        r"(?:管理员|馆长|队长|组长|局长|校长|市长|省长|总裁|董事|医生|护士|警官)[的]?([\u4e00-\u9fff]{2,4})",
        r"([\u4e00-\u9fff]{2,4})(?:管理员|馆长|队长|组长|局长|校长|市长|省长|总裁|董事)",
    ]
    for pattern in prefix_patterns:
        names.update(re.findall(pattern, body))

    names = {name for name in names if 2 <= len(name) <= 6 and name not in INVALID_SPEAKERS}
    return names


def _collect_locations(body: str) -> set[str]:
    locations: set[str] = set()
    patterns = [
        r"在([\u4e00-\u9fff]{2,8})(?:中|里|内|上|下|边|前)",
        r"来到([\u4e00-\u9fff]{2,8})(?:中|里|内|上|边)",
        r"进入([\u4e00-\u9fff]{2,8})(?:中|里|内)",
        r"返回([\u4e00-\u9fff]{2,8})(?:中|里|内)",
    ]
    for pattern in patterns:
        locations.update(re.findall(pattern, body))
    return locations


def _track_character_frequency(chapter_bodies: list[tuple[int, str]]) -> dict[str, list[int]]:
    char_freq: dict[str, list[int]] = defaultdict(list)
    for chapter_num, body in chapter_bodies:
        names = _collect_character_names(body)
        for name in names:
            char_freq[name].append(chapter_num)
    return dict(char_freq)


def _detect_character_gaps(chapter_bodies: list[tuple[int, str]]) -> list[dict]:
    char_freq = _track_character_frequency(chapter_bodies)
    issues: list[dict] = []

    if len(chapter_bodies) < 3:
        return issues

    chapter_nums = [ch[0] for ch in chapter_bodies]
    min_ch, max_ch = min(chapter_nums), max(chapter_nums)

    for char, appearances in char_freq.items():
        if len(appearances) < 2:
            continue

        sorted_apps = sorted(set(appearances))
        for i in range(1, len(sorted_apps)):
            gap = sorted_apps[i] - sorted_apps[i - 1]
            if gap > 2:
                issues.append({
                    "character": char,
                    "gap_start": sorted_apps[i - 1],
                    "gap_end": sorted_apps[i],
                    "gap_size": gap,
                    "issue": f"角色'{char}'在第{sorted_apps[i-1]}至{sorted_apps[i]}章之间未出现",
                })
    return issues


def _detect_location_inconsistency(chapter_bodies: list[tuple[int, str]]) -> list[dict]:
    issues: list[dict] = []
    prev_locations: Optional[str] = None

    for chapter_num, body in chapter_bodies:
        current_locations = _collect_locations(body)
        if not current_locations:
            continue

        main_loc = next(iter(current_locations))
        if prev_locations and prev_locations != main_loc:
            if not any(loc in main_loc or main_loc in loc for loc in prev_locations):
                issues.append({
                    "chapter": chapter_num,
                    "previous": prev_locations,
                    "current": main_loc,
                    "issue": f"地点跳跃：第{chapter_num}章从'{prev_locations}'跳到'{main_loc}'",
                })
        prev_locations = main_loc

    return issues


def _check_continuity(chapter_bodies: list[tuple[int, str]], mode: str) -> CheckResult:
    if mode == "volume" and len(chapter_bodies) < 2:
        return CheckResult("连续性", False, "章节不足", "需要至少2章才能检查连续性")

    characters: set[str] = set()
    locations: set[str] = set()
    for _, body in chapter_bodies:
        characters.update(_collect_character_names(body))
        locations.update(_collect_locations(body))

    char_count = len(characters)
    loc_count = len(locations)

    issues: list[str] = []
    if mode == "volume":
        char_gaps = _detect_character_gaps(chapter_bodies)
        if char_gaps:
            for gap in char_gaps[:3]:
                issues.append(gap["issue"])

        loc_issues = _detect_location_inconsistency(chapter_bodies)
        if loc_issues:
            for loc_issue in loc_issues[:2]:
                issues.append(loc_issue["issue"])

    if mode == "single":
        if char_count >= 2 and loc_count >= 1:
            return CheckResult("连续性", True, f"角色{char_count}，场景{loc_count}", "当前章信息自洽")
        return CheckResult("连续性", True, f"角色{char_count}，场景{loc_count}", "信息偏少，建议补足锚点", "low", "small", "ai_polish")

    if issues:
        issue_summary = "; ".join(issues)
        if len(issues) == 1:
            return CheckResult("连续性", True, issue_summary, "检测到轻微不一致", "low", "small", "ai_polish")
        return CheckResult("连续性", False, issue_summary, "角色/地点一致性发现问题", "medium", "medium", "regenerate")

    if char_count >= 3 and loc_count >= 2:
        return CheckResult("连续性", True, f"发现{char_count}个角色名，{loc_count}个场景名", "角色和场景保持一致")
    if char_count < 2 or loc_count < 1:
        return CheckResult("连续性", False, f"角色{char_count}，场景{loc_count}，数据不足", "需要更多角色和场景锚点", "high", "medium", "regenerate")
    return CheckResult("连续性", True, f"角色{char_count}，场景{loc_count}", "信息自洽", "low", "small", "ai_polish")


def _extract_setups_from_cards(chapters: list[tuple[int, str]]) -> tuple[list[dict], list[dict]]:
    open_setups: list[dict] = []
    resolved_setups: list[dict] = []

    for chapter_num, content in chapters:
        source = f"ch{chapter_num:03d}"

        resource_card = extract_bullets(extract_section(content, "### 3. 资源卡"))
        if resource_card.get("伏笔"):
            open_setups.append({
                "id": f"{source}_setup",
                "content": resource_card["伏笔"],
                "source": source,
                "chapter": chapter_num,
            })

        plot_card = extract_bullets(extract_section(content, "### 2. 情节卡"))
        if plot_card.get("关键事件"):
            resolved_setups.append({
                "id": f"{source}_resolved",
                "content": plot_card["关键事件"],
                "source": source,
                "chapter": chapter_num,
            })

        carry_card = extract_bullets(extract_section(content, "### 6. 承上启下卡"))
        if carry_card.get("铺垫"):
            open_setups.append({
                "id": f"{source}_setup_carry",
                "content": carry_card["铺垫"],
                "source": source,
                "chapter": chapter_num,
            })

    return open_setups, resolved_setups


def _match_payoff_pairs(open_setups: list[dict], resolved_setups: list[dict]) -> tuple[int, int, list[dict]]:
    matched = 0
    unmatched: list[dict] = []

    for open_item in open_setups:
        is_matched = False
        open_content = open_item["content"].lower()

        for resolved_item in resolved_setups:
            resolved_content = resolved_item["content"].lower()

            if any(char in resolved_content for char in open_content[:4]):
                is_matched = True
                break

        if is_matched:
            matched += 1

    unmatched_count = len(open_setups) - matched
    for open_item in open_setups[matched:]:
        unmatched.append(open_item)

    return matched, unmatched_count, unmatched


def _check_payoff(chapter_bodies: list[tuple[int, str]], mode: str, chapters: Optional[list[tuple[int, str]]] = None) -> CheckResult:
    setup_keywords = ["伏笔", "悬念", "谜题", "疑问", "隐患", "危机", "神秘", "秘密", "奇怪", "异常", "可疑"]
    payoff_keywords = ["原来", "真相", "揭开", "揭晓", "暴露", "解决", "化解", "消灭", "击败", "明白", "知晓"]

    setup_count = 0
    payoff_count = 0
    for _, body in chapter_bodies:
        lowered = body.lower()
        setup_count += sum(lowered.count(keyword) for keyword in setup_keywords)
        payoff_count += sum(lowered.count(keyword) for keyword in payoff_keywords)

    setup_details = ""
    if chapters and mode == "volume":
        open_setups, resolved_setups = _extract_setups_from_cards(chapters)
        if open_setups or resolved_setups:
            matched, unmatched_count, unmatched = _match_payoff_pairs(open_setups, resolved_setups)

            card_setup_count = len(open_setups)
            card_resolved_count = len(resolved_setups)

            setup_details = f"，卡片提取伏笔{card_setup_count}个，回收{card_resolved_count}个"

            if unmatched and card_setup_count > card_resolved_count * 2:
                unresolved_sample = [u["content"][:20] for u in unmatched[:3]]
                return CheckResult(
                    "伏笔回收", True,
                    f"正文伏笔{setup_count}次，回收{payoff_count}次；卡片未回收{unmatched_count}个伏笔",
                    f"部分伏笔留作下卷铺垫: {'; '.join(unresolved_sample)}",
                    "low", "small", "ai_polish"
                )

    if setup_count == 0 and not setup_details:
        return CheckResult("伏笔回收", True, "未检测到伏笔标记", "可根据需要决定是否添加")

    payoff_rate = payoff_count / max(setup_count, 1)
    if mode == "single":
        if payoff_rate >= 0.3:
            return CheckResult("伏笔回收", True, f"伏笔{setup_count}，回收{payoff_count}", "单章内推进正常")
        return CheckResult("伏笔回收", True, f"伏笔{setup_count}，回收不足", "作为单章问题影响有限", "low", "small", "ai_polish")

    if payoff_count >= setup_count * 0.5:
        return CheckResult("伏笔回收", True, f"伏笔 {setup_count} 次，回收 {payoff_count} 次{setup_details}", "伏笔回收良好")
    if setup_count >= 5 and payoff_rate < 0.3:
        return CheckResult("伏笔回收", False, f"伏笔{setup_count}次，回收{payoff_count}次，回收率不足30%", "主伏笔未回收", "high", "large", "regenerate")
    if payoff_rate < 0.5:
        return CheckResult("伏笔回收", True, f"伏笔{setup_count}次，回收{payoff_count}次，影响范围小", "部分伏笔未回收", "low", "small", "ai_polish")
    return CheckResult("伏笔回收", False, f"伏笔 {setup_count} 次，回收 {payoff_count} 次，回收率不足", "建议增加伏笔回收情节")


def _check_logic(chapter_bodies: list[tuple[int, str]], mode: str) -> CheckResult:
    issue_count = 0
    issue_details: list[str] = []
    for chapter_num, body in chapter_bodies:
        cause_count = len(re.findall(r"(因为|由于|所以|因此|于是|结果)", body))
        limit = 15 if mode == "single" else 10
        if cause_count > limit:
            issue_count += 1
            issue_details.append(f"第{chapter_num}章因果链{cause_count}处")

    if not issue_details:
        return CheckResult("逻辑性", True, "因果链结构正常", "因果关系清晰")
    if mode == "single":
        return CheckResult("逻辑性", False, "; ".join(issue_details), "因果链过于密集", "high", "medium", "regenerate")
    return CheckResult("逻辑性", True, "; ".join(issue_details), "因果链结构合理")


def _check_ai_texture(chapter_bodies: list[tuple[int, str]]) -> CheckResult:
    shock_patterns = [
        "众人色变", "全场哗然", "倒吸一口凉气", "倒吸凉气", "难以置信",
        "目瞪口呆", "脸色大变", "心中震撼", "全场震惊", "脸色铁青", "面如死灰",
    ]
    explain_patterns = [
        "原来如此", "也就是说", "这意味着", "果然", "没想到", "也就是说,",
    ]
    showoff_patterns = [
        "你也配", "一拳镇压", "无人能挡", "全场失声", "这就是差距",
        "蝼蚁", "不知死活", "找死", "不自量力", "差距", "秒杀",
    ]
    ai_markers = [
        "嘴角勾起", "眼中闪过", "心中暗道", "瞳孔收缩", "瞳孔微微收缩",
        "瞳孔骤然收缩", "脸色微微一变", "嘴角浮现", "冷笑一声", "缓缓站起",
    ]

    all_patterns = shock_patterns + explain_patterns + showoff_patterns + ai_markers

    total_hits = 0
    total_chars = 0
    category_hits = {"shock": 0, "explain": 0, "showoff": 0, "ai_marker": 0}

    for _, body in chapter_bodies:
        total_chars += len(body)
        for pat in shock_patterns:
            category_hits["shock"] += body.count(pat)
        for pat in explain_patterns:
            category_hits["explain"] += body.count(pat)
        for pat in showoff_patterns:
            category_hits["showoff"] += body.count(pat)
        for pat in ai_markers:
            category_hits["ai_marker"] += body.count(pat)

    total_hits = sum(category_hits.values())

    if total_chars == 0:
        return CheckResult("AI感", False, "正文内容为空", "无内容可检查")

    density = total_hits / max(total_chars / 1000, 1)

    issues: list[str] = []
    if category_hits["shock"] >= 3:
        density_shock = category_hits["shock"] / max(total_chars / 1000, 1)
        if density_shock > 2:
            issues.append(f"震惊反应{density_shock:.1f}/千字")
    if category_hits["explain"] >= 3:
        density_explain = category_hits["explain"] / max(total_chars / 1000, 1)
        if density_explain > 2:
            issues.append(f"解释连接{density_explain:.1f}/千字")
    if category_hits["showoff"] >= 2:
        density_showoff = category_hits["showoff"] / max(total_chars / 1000, 1)
        if density_showoff > 1.5:
            issues.append(f"装逼模板{density_showoff:.1f}/千字")

    if density > 5:
        return CheckResult("AI感", False, f"AI痕迹密度 {density:.1f}/千字，高密度" + (f"（{'; '.join(issues)}）" if issues else ""), "模板化表达贯穿全章", "high", "large", "regenerate")
    if density > 3 or issues:
        issue_str = f"（{'; '.join(issues)}）" if issues else ""
        return CheckResult("AI感", False, f"AI痕迹密度 {density:.1f}/千字{issue_str}", "少量模板词", "low", "small", "ai_polish")
    return CheckResult("AI感", True, f"AI痕迹密度 {density:.1f}/千字，正常范围", "质感正常")


def _check_timeline(chapter_bodies: list[tuple[int, str]], mode: str) -> CheckResult:
    time_pattern = r"(次日|第二天|隔天|三天后|五天后|一周后|一个月后|半年后|一年后)"
    jumps = []
    for chapter_num, body in chapter_bodies:
        matches = re.findall(time_pattern, body)
        if matches:
            jumps.append((chapter_num, matches[0]))

    if len(jumps) < 2:
        return CheckResult("时间线错乱", True, "时间跳转标记少", "无明显时间线问题")

    for current, following in zip(jumps, jumps[1:]):
        curr_ch, curr_word = current
        next_ch, next_word = following
        if curr_ch < next_ch:
            continue
        return CheckResult("时间线错乱", False, f"第{curr_ch}章'{curr_word}'，第{next_ch}章'{next_word}'，时间倒退", "关键事件时间颠倒", "high", "large", "regenerate")
    return CheckResult("时间线错乱", True, "时间线正常", "时间顺序合理")


def _check_meta_refs(chapter_bodies: list[tuple[int, str]]) -> CheckResult:
    patterns = [r"本章", r"上章", r"上一章", r"下一章", r"前文", r"后文", r"前几章", r"后几章", r"该章"]
    found: list[str] = []
    for chapter_num, body in chapter_bodies:
        for pattern in patterns:
            if re.search(pattern, body):
                found.append(f"{pattern}:第{chapter_num}章")
    if not found:
        return CheckResult("章节自指", True, "无章节自指词", "正文自然承接")
    return CheckResult("章节自指", False, f"发现自指词: {', '.join(found[:5])}", "偶发自指词", "low", "small", "ai_polish")


def _check_pacing(chapter_bodies: list[tuple[int, str]], mode: str) -> CheckResult:
    issues: list[dict] = []

    for chapter_num, body in chapter_bodies:
        body_len = len(body)

        dialogue_count = len(re.findall(r'[""「』（]', body))
        dialogue_ratio = dialogue_count / max(body_len / 100, 1)

        action_count = len(re.findall(r"(走进|跑进|冲出|停下|转身|抬起|握紧|推开|关上门)", body))
        action_ratio = action_count / max(body_len / 500, 1)

        conflict_markers = len(re.findall(r"(但是|然而|可是|不料|意外|突然|紧接着)", body))
        conflict_density = conflict_markers / max(body_len / 500, 1)

        if body_len > 500:
            if dialogue_ratio > 5:
                issues.append({"chapter": chapter_num, "issue": f"对话过多，密度{dialogue_ratio:.1f}/百字", "severity": "low"})
            elif conflict_density < 0.3:
                issues.append({"chapter": chapter_num, "issue": "冲突推进不足", "severity": "low"})

    if not issues:
        return CheckResult("节奏", True, "节奏推进正常", "冲突和对话比例合理")

    issue_summary = "; ".join(i["issue"] + f"[第{i['chapter']}章]" for i in issues[:3])
    return CheckResult("节奏", True, issue_summary, "部分章节节奏偏慢", "low", "small", "ai_polish")


def _check_emotional_arc(chapters: list[tuple[int, str]], mode: str) -> CheckResult:
    if mode == "single":
        return CheckResult("情绪弧", True, "单章不检查情绪弧", "单章视角有限")

    emotion_pairs: list[dict] = []

    for chapter_num, content in chapters:
        emotion_card = extract_bullets(extract_section(content, "### 5. 情感弧卡"))
        if emotion_card.get("起始情绪") and emotion_card.get("目标情绪"):
            emotion_pairs.append({
                "chapter": chapter_num,
                "start": emotion_card["起始情绪"],
                "target": emotion_card["目标情绪"],
            })

    if len(emotion_pairs) < 2:
        return CheckResult("情绪弧", True, "数据不足", "需要至少2章情感弧数据")

    state_card = extract_bullets(extract_section(chapters[-1][1], "### 1. 状态卡"))
    final_emotion = state_card.get("主角当前情绪", "")

    if final_emotion:
        first_start = emotion_pairs[0]["start"]
        last_target = emotion_pairs[-1]["target"]

        if first_start == final_emotion or last_target == final_emotion:
            return CheckResult("情绪弧", True, f"起始{first_start}→终点{final_emotion}", "情绪弧完整")

        return CheckResult(
            "情绪弧", True,
            f"起始{first_start}→目标{last_target}→终点{final_emotion}",
            "情绪变化路径正常"
        )

    return CheckResult("情绪弧", True, f"共{len(emotion_pairs)}个情感弧", "数据足够")


def _check_goal_progression(chapters: list[tuple[int, str]], mode: str) -> CheckResult:
    goals: list[dict] = []

    for chapter_num, content in chapters:
        state_card = extract_bullets(extract_section(content, "### 1. 状态卡"))
        if state_card.get("主角当前目标"):
            goals.append({
                "chapter": chapter_num,
                "goal": state_card["主角当前目标"],
            })

    if len(goals) < 2:
        return CheckResult("目标追踪", True, "数据不足", "需要多章节目标数据")

    unique_goals = len(set(g["goal"] for g in goals))
    total_goals = len(goals)

    if unique_goals == total_goals and total_goals >= 3:
        return CheckResult(
            "目标追踪", False,
            f"目标变更{unique_goals}次，过于频繁",
            "主角目标频繁更换，缺乏聚焦",
            "medium", "medium", "ai_polish"
        )

    return CheckResult(
        "目标追踪", True,
        f"共{total_goals}个目标，其中{unique_goals}个不同",
        "目标追踪稳定"
    )


def _check_timeline_cross_chapter(chapters: list[tuple[int, str]], mode: str) -> CheckResult:
    time_map = {
        "次日": 1, "第二天": 1, "翌日": 1, "隔天": 1,
        "三天后": 3, "三日后": 3,
        "五天后": 5, "五日后": 5,
        "一周后": 7, "七天后": 7, "七日后": 7,
        "半月后": 15, "半个月后": 15,
        "一个月后": 30, "一月后": 30,
        "半年后": 180,
        "一年后": 365,
    }

    time_jumps: list[dict] = []

    for i in range(len(chapters) - 1):
        curr_num, curr_content = chapters[i]
        next_num, next_content = chapters[i + 1]

        curr_body = extract_body(curr_content)
        next_body = extract_body(next_content)

        curr_end = curr_body[-500:] if len(curr_body) >= 500 else curr_body
        next_start = next_body[:500]

        curr_days, curr_word = None, None
        next_days, next_word = None, None

        for word, days in time_map.items():
            if curr_word is None and word in curr_end:
                curr_days, curr_word = days, word
            if next_word is None and word in next_start:
                next_days, next_word = days, word

        if curr_word and next_word:
            if curr_days > next_days:
                has_backtrack = any(
                    w in next_start[:200] for w in ["回溯", "回忆", "闪回", "之前", "三天前"]
                )
                if not has_backtrack:
                    time_jumps.append({
                        "prev_ch": curr_num,
                        "next_ch": next_num,
                        "prev_time": curr_word,
                        "next_time": next_word,
                        "issue": f"时间倒溯：第{curr_num}章'{curr_word}'→第{next_num}章'{next_word}'",
                    })

    if not time_jumps:
        return CheckResult("时间连续性", True, "跨章时间线正常", "无时间倒溯问题")

    issue_summary = "; ".join(j["issue"] for j in time_jumps[:3])
    return CheckResult(
        "时间连续性", False,
        issue_summary,
        "检测到时间倒溯且无回溯提示",
        "medium", "medium", "ai_polish"
    )


def _prepare_chapter_bodies(chapters: list[tuple[int, str]]) -> list[tuple[int, str]]:
    return [(chapter_num, extract_body(content)) for chapter_num, content in chapters]


def run_volume_checks(chapters: list[tuple[int, str]], state: dict) -> list[CheckResult]:
    chapter_bodies = _prepare_chapter_bodies(chapters)
    return [
        _check_continuity(chapter_bodies, "volume"),
        _check_payoff(chapter_bodies, "volume", chapters),
        _check_logic(chapter_bodies, "volume"),
        _check_ai_texture(chapter_bodies),
        _check_timeline(chapter_bodies, "volume"),
        _check_meta_refs(chapter_bodies),
        _check_pacing(chapter_bodies, "volume"),
        _check_emotional_arc(chapters, "volume"),
        _check_goal_progression(chapters, "volume"),
        _check_timeline_cross_chapter(chapters, "volume"),
    ]


def run_single_chapter_checks(chapter_num: int, content: str, state: dict) -> list[CheckResult]:
    chapters = [(chapter_num, content)]
    chapter_bodies = _prepare_chapter_bodies(chapters)
    return [
        _check_continuity(chapter_bodies, "single"),
        _check_payoff(chapter_bodies, "single", chapters),
        _check_logic(chapter_bodies, "single"),
        _check_ai_texture(chapter_bodies),
        _check_timeline(chapter_bodies, "single"),
        _check_meta_refs(chapter_bodies),
    ]
