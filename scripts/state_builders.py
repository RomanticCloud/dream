#!/usr/bin/env python3
"""Option constants and state builders for dream skill."""

from __future__ import annotations

from planning_rules import describe_target_profile, volume_label


WORD_TARGET_OPTIONS = ["30万字", "40万字", "50万字", "100万字"]

CHAPTER_LENGTH_OPTIONS = ["2000-2500字", "2500-3500字", "3500-4500字", "4500-5500字"]

GENDER_OPTIONS = ["男", "女"]

AGE_GROUP_OPTIONS = ["少年(14-17)", "青年(18-30)", "中年(31-50)"]

PERSONALITY_OPTIONS = [
    "坚毅", "腹黑", "阳光", "冷漠", "热血", "沉稳", "果断", "阴郁", "幽默", "正直"
]

CORE_DESIRE_EXAMPLES = [
    "获得力量", "改变命运", "复仇", "保护重要的人",
    "获得财富", "证明自己", "探索真相", "登临巅峰"
]

DEEPEST_FEAR_EXAMPLES = [
    "无力反击", "失去重要的人", "被背叛", "永远的失败",
    "身败名裂", "孤独终老", "陷入绝望"
]

POWER_SYSTEM_OPTIONS = [
    "体能技击", "武魂觉醒", "职业技能", "系统面板",
    "血脉传承", "功法修炼", "科技装备"
]

LEVEL_OPTIONS_BY_SYSTEM = {
    "体能技击": ["基础期→进阶期→精英期→大师期→宗师期"],
    "武魂觉醒": ["觉醒者→进阶者→掌控者→觉醒大师→觉醒宗师"],
    "职业技能": ["初级→中级→高级→专家→大师"],
    "系统面板": ["Lv1→Lv10→Lv50→Lv100→满级"],
    "血脉传承": ["觉醒→成熟→完全体→返祖→真祖"],
    "功法修炼": ["引气→筑基→金丹→元婴→飞升"],
    "科技装备": ["普通→精良→稀有→史诗→传说"]
}

BREAKTHROUGH_OPTIONS = [
    "实战胜利积累", "资源消耗", "感悟突破",
    "生死历练", "导师指导", "秘法传承"
]

LIMITATION_OPTIONS = [
    "体力限制", "资源稀缺", "境界壁障",
    "心魔干扰", "对手限制", "无明显限制"
]

PACING_OPTIONS = ["偏快（每章推进）", "偏稳（允许铺垫）", "快慢交替"]

STYLE_TONE_OPTIONS = [
    "热血燃向",
    "轻松幽默",
    "严肃写实",
    "黑暗深邃",
    "甜宠治愈",
    "悬疑推理"
]

MAIN_GENRE_OPTIONS = [
    "都市高武",
    "玄幻奇幻",
    "都市生活",
    "悬疑推理",
    "科幻未来",
    "仙侠修真",
    "历史军事"
]

SUB_GENRE_OPTIONS = [
    "重生",
    "穿越",
    "系统流",
    "升级流",
    "甜宠",
    "虐恋",
    "群像",
    "单女主"
]


def parse_word_target(label: str) -> int:
    if "万字" in label:
        return int(label.replace("万字", "")) * 10000
    return int(label)


def parse_chapter_length(label: str) -> tuple[int, int]:
    if label == "用户输入":
        return (3500, 4500)
    label = label.replace("字", "")
    parts = label.split("-")
    if len(parts) == 2:
        return (int(parts[0]), int(parts[1]))
    return (3500, 4500)


def build_basic_specs(
    word_target: str,
    chapter_length: str,
    pacing: str,
    style_tone: str,
    main_genres: list[str],
    sub_genres: list[str],
) -> dict:
    word_numeric = parse_word_target(word_target)
    chapter_min, chapter_max = parse_chapter_length(chapter_length)
    chapter_avg = (chapter_min + chapter_max) // 2

    derived = describe_target_profile(word_target, chapter_length)

    chosen_volume_label = volume_label(derived["derived_total_volumes"])
    target_volumes_numeric = (
        10 if chosen_volume_label == "10卷+" else int(chosen_volume_label.rstrip("卷"))
    )

    return {
        "target_word_count": word_target,
        "target_word_count_numeric": word_numeric,
        "chapter_length": chapter_length,
        "chapter_length_min": chapter_min,
        "chapter_length_max": chapter_max,
        "pacing": pacing,
        "style_tone": style_tone,
        "main_genres": main_genres,
        "sub_genres": sub_genres,
        "target_volumes_label": chosen_volume_label,
        "target_volumes_numeric": target_volumes_numeric,
        "chapters_per_volume": derived["derived_chapters_per_volume"],
        "derived": derived,
    }


NARRATIVE_STYLE_OPTIONS = [
    "第三人称有限视角",
    "第一人称有限视角",
    "全知视角"
]

CONFLICT_OPTIONS_BY_GENRE = {
    "都市高武": ["职业晋升", "升级成长", "势力打压", "复仇翻盘"],
    "玄幻奇幻": ["探索秘境", "升级成长", "血脉觉醒", "种族战争"],
    "都市生活": ["职场竞争", "情感纠葛", "身份追寻", "生活危机"],
    "悬疑推理": ["谜题揭晓", "身份追寻", "势力博弈", "危机追逐"],
    "科幻未来": ["星际探索", "科技竞争", "末日危机", "权力争斗"],
    "仙侠修真": ["境界突破", "门派争斗", "秘境探索", "功法传承"],
    "历史军事": ["权力争斗", "战争谋略", "身份追寻", "势力博弈"],
}

READER_HOOK_OPTIONS_BY_TONE = {
    "热血燃向": ["看主角逆袭", "看成长蜕变", "看实力爆发"],
    "轻松幽默": ["看主角搞笑", "看日常轻松", "看反转打脸"],
    "严肃写实": ["看现实困境", "看人性挣扎", "看社会洞察"],
    "黑暗深邃": ["看主角黑化", "看复仇清算", "看世界崩塌"],
    "甜宠治愈": ["看甜蜜恋爱", "看温暖成长", "看治愈救赎"],
    "悬疑推理": ["看谜题揭晓", "看真相浮出", "看线索串联"],
}


def get_conflict_options(main_genres: list[str]) -> list[str]:
    options = []
    for genre in main_genres:
        if genre in CONFLICT_OPTIONS_BY_GENRE:
            options.extend(CONFLICT_OPTIONS_BY_GENRE[genre])
    return list(dict.fromkeys(options))


def get_reader_hook_options(style_tone: str) -> list[str]:
    return READER_HOOK_OPTIONS_BY_TONE.get(style_tone, ["看成长蜕变", "看主角逆袭"])


def default_positioning_values(main_genres: list[str], style_tone: str) -> dict:
    conflicts = get_conflict_options(main_genres)[:3]
    hooks = get_reader_hook_options(style_tone)[:2]
    genre_str = "、".join(main_genres) if main_genres else "都市"
    tone_desc = {
        "热血燃向": "热血成长",
        "轻松幽默": "轻松有趣",
        "严肃写实": "深刻写实",
        "黑暗深邃": "暗黑深邃",
        "甜宠治愈": "甜蜜治愈",
        "悬疑推理": "悬疑烧脑"
    }.get(style_tone, style_tone)
    return {
        "main_conflicts": conflicts,
        "reader_hooks": hooks,
        "core_promise": f"在{genre_str}背景下，主角通过{conflicts[0] if conflicts else '冒险成长'}实现{hooks[0] if hooks else '成长蜕变'}",
        "selling_point": f"{genre_str}题材，{tone_desc}风格的作品"
    }


def build_positioning(
    narrative_style: str,
    main_conflicts: list[str],
    reader_hooks: list[str],
    core_promise: str,
    selling_point: str,
) -> dict:
    return {
        "narrative_style": narrative_style,
        "main_conflicts": main_conflicts,
        "reader_hooks": reader_hooks,
        "core_promise": core_promise,
        "selling_point": selling_point,
    }


SETTING_OPTIONS = [
    "现代都市", "古代世界", "异世界", "末世废墟",
    "星际未来", "仙侠世界", "架空历史"
]

SOCIETY_OPTIONS = [
    "皇权统治", "教会/宗门主导", "贵族世家",
    "民主议会", "帮派势力", "平衡制衡", "混乱无序"
]

SCENE_OPTIONS_BY_GENRE = {
    "都市高武": ["钢铁都市", "职业区", "比赛场馆", "地下禁区"],
    "玄幻奇幻": ["宗门", "遗迹", "森林", "城镇", "城堡"],
    "都市生活": ["商业区", "住宅区", "贫民区", "写字楼", "学校"],
    "悬疑推理": ["城市", "庄园", "研究所", "废弃场所", "密室"],
    "科幻未来": ["太空站", "星际城市", "赛博都市", "实验室"],
    "仙侠修真": ["宗门", "山门", "城镇", "妖域", "秘境"],
    "历史军事": ["城池", "战场", "边境", "驿站", "军营"],
}

ADVENTURE_OPTIONS = [
    "遗迹/古墓", "秘境/异空间", "危险地带",
    "地下世界", "野外山林", "城市角落"
]

CRISIS_OPTIONS = [
    "权力斗争", "资源匮乏", "外敌入侵",
    "天灾人祸", "秘密阴谋", "势力对抗", "个人仇恨"
]


def get_scene_options(main_genres: list[str]) -> list[str]:
    options = []
    for genre in main_genres:
        if genre in SCENE_OPTIONS_BY_GENRE:
            options.extend(SCENE_OPTIONS_BY_GENRE[genre])
    return list(dict.fromkeys(options)) if options else ["城镇", "野外"]


def build_world(
    setting_type: str,
    society_structure: str,
    main_scene: list[str],
    adventure_zone: list[str],
    main_crisis: list[str],
    scene_layers: str | None = None,
) -> dict:
    return {
        "setting_type": setting_type,
        "society_structure": society_structure,
        "main_scene": main_scene,
        "adventure_zone": adventure_zone,
        "main_crisis": main_crisis,
        "scene_layers": scene_layers,
    }


ROMANCE_OPTIONS = [
    "单女主", "1v1多角", "多女主/后宫", "无CP", "纯友情"
]

RELATIONSHIP_OPTIONS = [
    "师徒", "兄弟", "竞争", "仇敌", "联盟",
    "背叛", "亲人", "伙伴", "利益", "理念"
]

ANTAGONIST_OPTIONS = [
    "势力BOSS", "天才", "世家", "神秘组织",
    "宿命之敌", "系统/命运", "旧敌", "内部背叛者"
]

ANTAGONIST_CURVE_OPTIONS = [
    "始终压制", "交替领先", "前强后弱", "阶段性换血"
]

CONFLICT_LEVEL_OPTIONS = [
    "同辈竞争", "城市事件", "国家级任务",
    "世界级危机", "文明存续"
]

TENSION_OPTIONS = [
    "利益争夺", "理念冲突", "情感纠葛",
    "身份对立", "世代仇恨", "权力斗争"
]


def build_characters(
    romance_type: str,
    key_relationship_types: list[str],
    main_antagonist_type: str,
    antagonist_curve: str,
    conflict_levels: list[str],
    main_factions: str,
    relationship_tension: list[str],
) -> dict:
    return {
        "romance_type": romance_type,
        "key_relationship_types": key_relationship_types,
        "main_antagonist_type": main_antagonist_type,
        "antagonist_curve": antagonist_curve,
        "conflict_levels": conflict_levels,
        "main_factions": main_factions,
        "relationship_tension": relationship_tension,
    }


BATCH_SIZE_OPTIONS = ["8章", "10章", "12章"]

ESCALATION_PATH_BY_TONE = {
    "热血燃向": [
        "从弱小到强大的逆袭之路",
        "从底层到巅峰的奋斗之旅",
        "一路越战越强的热血征程"
    ],
    "轻松幽默": [
        "轻松搞笑的成长之路",
        "在欢笑中不断变强",
        "欢乐向的升级冒险"
    ],
    "严肃写实": [
        "在困境中艰难求进的现实之路",
        "一步一个脚印的坚实成长",
        "在压力中不断突破的奋斗史"
    ],
    "黑暗深邃": [
        "在黑暗中逐步崛起的复仇之路",
        "从深渊一步步爬向光明",
        "在绝望中寻找力量的道路"
    ],
    "甜宠治愈": [
        "相互扶持共同成长的温暖之路",
        "在爱与陪伴中不断变强",
        "甜蜜温馨的成长之旅"
    ],
    "悬疑推理": [
        "逐步揭开真相的探索之旅",
        "在迷雾中寻找答案的追查之路",
        "随着真相不断成长的解密之旅"
    ]
}

DELIVERY_OPTIONS_BY_CONFLICT = {
    "复仇翻盘": ["战力提升 + 复仇成功", "身份地位 + 敌人覆灭", "全面提升 + 核心突破"],
    "职业晋升": ["战力提升 + 职位升迁", "资源获得 + 能力解锁", "身份地位 + 势力扩张"],
    "升级成长": ["战力提升 + 能力解锁", "境界突破 + 资源收获", "全面升级 + 传承获得"],
    "探索秘境": ["秘境收获 + 实力大增", "传承获得 + 境界提升", "宝物获取 + 能力觉醒"],
    "势力博弈": ["身份地位 + 势力扩张", "资源争夺 + 权力提升", "政治资本 + 实力增长"],
    "情感纠葛": ["情感收获 + 成长蜕变", "关系突破 + 共同进步", "爱情事业双丰收"],
    "末日危机": ["生存能力 + 危机化解", "力量觉醒 + 拯救世界", "成长蜕变 + 守护家园"],
    "权力争斗": ["权力提升 + 势力稳固", "政治资本 + 身份跃升", "全面胜利 + 格局扩张"],
    "身份追寻": ["身份确认 + 能力觉醒", "过去解密 + 力量回归", "自我认知 + 成长突破"]
}

FIRST_GOAL_BY_CONFLICT = {
    "复仇翻盘": ["完成首次复仇", "站稳复仇根基", "获得关键复仇力量"],
    "职业晋升": ["完成首次晋升", "在职场站稳脚跟", "获得重要职位"],
    "升级成长": ["完成首次突破", "获得核心能力", "建立成长根基"],
    "探索秘境": ["完成首次探索", "获得秘境宝藏", "解锁关键线索"],
    "势力博弈": ["建立首个势力", "获得重要盟友", "站稳博弈根基"],
    "情感纠葛": ["确立核心关系", "完成情感突破", "获得情感支持"],
    "末日危机": ["完成首次危机应对", "建立生存基础", "获得关键力量"],
    "权力争斗": ["获得初始权力", "站稳权力基础", "建立核心团队"],
    "identity追寻": ["获得关键线索", "确认身份方向", "完成身份突破"]
}

FIRST_HOOK_BY_CRISIS = {
    "权力斗争": ["新强敌出现", "权力格局剧变", "隐藏势力浮出"],
    "资源匮乏": ["发现新资源点", "资源争夺加剧", "资源危机爆发"],
    "外敌入侵": ["强敌兵临城下", "内应暴露", "援军到来"],
    "天灾人祸": ["新的危机出现", "隐藏真相浮出", "更大灾难预警"],
    "秘密阴谋": ["阴谋败露", "幕后黑手现身", "更大秘密曝光"],
    "势力对抗": ["势力决战开始", "联盟破裂", "新势力加入"],
    "个人仇恨": ["旧敌复仇", "仇恨升级", "隐藏仇敌出现"]
}


def get_escalation_path_options(style_tone: str) -> list[str]:
    return ESCALATION_PATH_BY_TONE.get(style_tone, ["从弱小到强大的成长之路"])


def get_delivery_options(main_conflicts: list[str]) -> list[str]:
    for conflict in main_conflicts:
        if conflict in DELIVERY_OPTIONS_BY_CONFLICT:
            return DELIVERY_OPTIONS_BY_CONFLICT[conflict]
    return ["战力提升 + 身份地位", "资源获得 + 能力解锁", "全面均衡发展"]


def get_first_volume_goal_options(main_conflicts: list[str]) -> list[str]:
    for conflict in main_conflicts:
        if conflict in FIRST_GOAL_BY_CONFLICT:
            return FIRST_GOAL_BY_CONFLICT[conflict]
    return ["完成首次突破", "站稳脚跟", "获得关键能力"]


def get_first_volume_hook_options(main_crisis: list[str]) -> list[str]:
    for crisis in main_crisis:
        if crisis in FIRST_HOOK_BY_CRISIS:
            return FIRST_HOOK_BY_CRISIS[crisis]
    return ["新强敌出现", "系统任务发布", "隐藏势力浮出"]


def build_volume_architecture(
    volume_count: int,
    chapters_per_volume: int,
    book_escalation_path: str,
    delivery_matrix: str,
) -> dict:
    return {
        "volume_count": volume_count,
        "chapters_per_volume": chapters_per_volume,
        "book_escalation_path": book_escalation_path,
        "delivery_matrix": delivery_matrix,
    }


def build_batch_plan(
    batch_size: int,
    first_volume_goal: str,
    first_volume_hook: str,
    first_batch_opening_mode: str,
) -> dict:
    return {
        "batch_size": batch_size,
        "first_volume_goal": first_volume_goal,
        "first_volume_hook": first_volume_hook,
        "first_batch_opening_mode": first_batch_opening_mode,
    }


TITLE_KEYWORDS_BY_TONE = {
    "热血燃向": ["逆袭", "崛起", "腾飞", "觉醒", "巅峰", "王者"],
    "轻松幽默": ["欢乐", "逗王", "搞笑", "日常", "逗趣"],
    "严肃写实": ["底层", "挣扎", "现实", "奋斗", "人生"],
    "黑暗深邃": ["深渊", "黑暗", "陨落", "绝境", "凋零"],
    "甜宠治愈": ["暖心", "爱恋", "甜蜜", "守护", "治愈"],
    "悬疑推理": ["谜案", "追凶", "真相", "解密", "追踪"]
}

TITLE_KEYWORDS_BY_GENRE = {
    "都市高武": ["都市", "城市", "都市之"],
    "玄幻奇幻": ["异界", "大陆", "传奇", "幻域"],
    "都市生活": ["生活", "日常", "人生"],
    "悬疑推理": ["探案", "真相", "谜团"],
    "科幻未来": ["星际", "未来", "太空", "赛博"],
    "仙侠修真": ["仙途", "修真", "大道", "飞升"],
    "历史军事": ["王朝", "战国", "枭雄", "烽烟"]
}


def generate_book_title_options(main_genres: list[str], style_tone: str, core_promise: str = "") -> list[str]:
    titles = []
    tone_keywords = TITLE_KEYWORDS_BY_TONE.get(style_tone, ["成长"])
    genre_keywords = TITLE_KEYWORDS_BY_GENRE.get(main_genres[0] if main_genres else "都市高武", ["都市"])

    for tone_kw in tone_keywords[:3]:
        for genre_kw in genre_keywords[:2]:
            titles.append(f"{genre_kw}{tone_kw}")
            titles.append(f"{tone_kw}{genre_kw}")

    titles = list(dict.fromkeys(titles))[:6]
    if not titles:
        titles = ["未命名项目"]
    return titles


def build_naming(selected_book_title: str, book_title_candidates: list[str]) -> dict:
    return {
        "selected_book_title": selected_book_title,
        "book_title_candidates": book_title_candidates,
    }


def build_protagonist(
    name: str,
    gender: str,
    age_group: str,
    starting_identity: str,
    starting_level: str,
    personality: str,
    core_desire: str,
    deepest_fear: str,
    long_term_goal: str,
    ability: str | None = None,
) -> dict:
    return {
        "name": name,
        "gender": gender,
        "age_group": age_group,
        "starting_identity": starting_identity,
        "starting_level": starting_level,
        "personality": personality,
        "core_desire": core_desire,
        "deepest_fear": deepest_fear,
        "long_term_goal": long_term_goal,
        "ability": ability or "",
    }


def build_power_system(
    main_system: str,
    levels: str,
    breakthrough_condition: str,
    limitation: str,
    unique_trait: str | None = None,
    resource_economy: str | None = None,
) -> dict:
    return {
        "main_system": main_system,
        "levels": levels,
        "breakthrough_condition": breakthrough_condition,
        "limitation": limitation,
        "unique_trait": unique_trait or "",
        "resource_economy": resource_economy or "",
    }


def build_factions(
    player_faction: str,
    enemy_faction: str,
    neutral_faction: str,
) -> dict:
    return {
        "player_faction": player_faction,
        "enemy_faction": enemy_faction,
        "neutral_faction": neutral_faction,
    }
