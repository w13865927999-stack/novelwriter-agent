"""Quality checks for generated chapters."""

from __future__ import annotations

import re
from collections import Counter
from typing import Any


CONFLICT_MARKERS = {
    "冲突",
    "争执",
    "威胁",
    "危机",
    "追",
    "逃",
    "杀",
    "秘密",
    "背叛",
    "代价",
    "选择",
    "发现",
    "爆炸",
    "交易",
    "审问",
    "质问",
    "封锁",
    "逼近",
    "阻止",
    "异常",
    "死亡",
    "熄灭",
    "裂开",
    "发热",
    "烫",
}

HOOK_MARKERS = {
    "突然",
    "却",
    "然而",
    "真相",
    "秘密",
    "下一刻",
    "门外",
    "电话",
    "短信",
    "声音",
    "影子",
    "血",
    "钥匙",
    "名单",
    "倒计时",
}


def _terms(text: str) -> set[str]:
    chinese = re.sub(r"[^\u4e00-\u9fff]", "", text)
    grams = {chinese[i : i + 2] for i in range(max(0, len(chinese) - 1))}
    grams.update(chinese[i : i + 3] for i in range(max(0, len(chinese) - 2)))
    words = set(re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", text))
    return {term for term in grams | words if len(term.strip()) >= 2}


def _has_repetition(text: str) -> bool:
    normalized = re.sub(r"\s+", "", text)
    phrases = [normalized[i : i + 6] for i in range(max(0, len(normalized) - 5))]
    counts = Counter(phrases)
    return any(count >= 5 for phrase, count in counts.items() if len(set(phrase)) > 2)


def heuristic_quality_scan(
    profile: dict[str, Any],
    chapter_outline: str,
    chapter_text: str,
    memory: dict[str, Any],
) -> dict[str, Any]:
    """Run lightweight checks that work even in mock/offline mode."""

    outline_terms = _terms(chapter_outline)
    chapter_terms = _terms(chapter_text)
    overlap = len(outline_terms & chapter_terms)
    outline_deviation = bool(outline_terms) and overlap / max(len(outline_terms), 1) < 0.08

    known_names = list((memory.get("characters") or {}).keys())
    protagonist = str(profile.get("protagonist", "")).strip()
    main_name_present = any(name and name in chapter_text for name in known_names)
    if not main_name_present and protagonist:
        main_name_present = protagonist in chapter_text or protagonist[-2:] in chapter_text
    character_inconsistency = bool(protagonist or known_names) and not main_name_present

    conflict_count = sum(1 for marker in CONFLICT_MARKERS if marker in chapter_text)
    missing_conflict = conflict_count < 2

    ending = chapter_text[-220:]
    missing_hook = not any(marker in ending for marker in HOOK_MARKERS) and not ending.rstrip().endswith(("？", "！", "?","!"))

    repetitive_language = _has_repetition(chapter_text)

    suggestions: list[str] = []
    if outline_deviation:
        suggestions.append("章节正文与章节大纲关键词重合较低，建议补回核心事件、冲突点或悬念点。")
    if character_inconsistency:
        suggestions.append("正文没有明显出现主角，若非特殊章节，建议强化主角行动线。")
    if missing_conflict:
        suggestions.append("章节冲突信号偏弱，建议加入更明确的阻碍、选择、追问或代价。")
    if missing_hook:
        suggestions.append("结尾钩子偏弱，建议在最后一幕加入悬念、反转或情绪推进。")
    if repetitive_language:
        suggestions.append("检测到可能的重复表达，建议删减或替换重复短语。")
    if not suggestions:
        suggestions.append("未发现明显硬伤，后续可继续检查细节节奏和对白自然度。")

    return {
        "outline_deviation": outline_deviation,
        "character_inconsistency": character_inconsistency,
        "worldbuilding_conflict": False,
        "unexplained_jump": False,
        "missing_conflict": missing_conflict,
        "missing_hook": missing_hook,
        "repetitive_language": repetitive_language,
        "style_mismatch": False,
        "suggestions": suggestions,
    }
