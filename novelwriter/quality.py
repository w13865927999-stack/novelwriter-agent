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


def _first_meaningful_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip().lstrip("#").strip()
        if stripped:
            return stripped
    return ""


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / max(len(left | right), 1)


def _scene_markers(text: str) -> set[str]:
    markers = set(re.findall(r"[\u4e00-\u9fffA-Za-z0-9_-]{2,}(?:码头|档案馆|车站|街|楼|塔|城|巷|馆|站|港|桥|舱|区)", text))
    common = {"第七码头", "白塔", "黑市", "雾港", "旧电车站", "记忆中转站"}
    return markers | {item for item in common if item in text}


def repetition_scan(
    chapter_text: str,
    recent_chapters: list[dict[str, Any]] | None = None,
    memory: dict[str, Any] | None = None,
) -> dict[str, Any]:
    recent_chapters = recent_chapters or []
    memory = memory or {}
    issues: list[str] = []
    max_similarity = 0.0
    repeated_opening = False
    repeated_scene = False
    repeated_event = False
    repeated_clue = False

    chapter_terms = _terms(chapter_text)
    opening = _first_meaningful_line(chapter_text)[:36]
    scenes = _scene_markers(chapter_text)

    for item in recent_chapters[-3:]:
        other_text = str(item.get("content", ""))
        similarity = _jaccard(chapter_terms, _terms(other_text))
        max_similarity = max(max_similarity, similarity)
        other_opening = _first_meaningful_line(other_text)[:36]
        if opening and other_opening and opening == other_opening:
            repeated_opening = True
        if scenes and scenes & _scene_markers(other_text):
            repeated_scene = True

    for event in memory.get("occurred_events", [])[-20:]:
        event_text = event.get("event") if isinstance(event, dict) else str(event)
        if event_text and len(event_text) >= 6 and event_text in chapter_text:
            repeated_event = True
            break

    for clue in memory.get("discovered_clues", [])[-20:]:
        if isinstance(clue, dict):
            clue_text = clue.get("clue") or clue.get("description") or ""
        else:
            clue_text = str(clue)
        if clue_text and len(clue_text) >= 4 and clue_text in chapter_text:
            repeated_clue = True
            break

    if max_similarity > 0.42:
        issues.append(f"新章节与最近章节相似度偏高：{max_similarity:.2f}。")
    if repeated_opening:
        issues.append("新章节开头与最近章节重复。")
    if repeated_scene:
        issues.append("新章节可能重复使用最近章节主要场景。")
    if repeated_event:
        issues.append("新章节可能重复已发生事件。")
    if repeated_clue:
        issues.append("新章节可能重复已发现线索。")

    return {
        "repetition_warning": bool(issues),
        "similarity_to_recent": round(max_similarity, 3),
        "repeated_opening": repeated_opening,
        "repeated_scene": repeated_scene,
        "repeated_event": repeated_event,
        "repeated_clue": repeated_clue,
        "repetition_issues": issues,
    }


def heuristic_quality_scan(
    profile: dict[str, Any],
    chapter_outline: str,
    chapter_text: str,
    memory: dict[str, Any],
    recent_chapters: list[dict[str, Any]] | None = None,
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

    repetition = repetition_scan(chapter_text, recent_chapters, memory)
    suggestions.extend(repetition["repetition_issues"])
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
        **repetition,
        "suggestions": suggestions,
    }
