"""Read, write, and update long-form novel memory."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def default_memory(project: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "novel_info": {
            "title": project.get("title", ""),
            "genre": project.get("genre", ""),
            "target_readers": project.get("target_readers", ""),
            "target_words": project.get("target_words", 0),
            "chapter_count": project.get("chapter_count", 0),
            "words_per_chapter": project.get("words_per_chapter", 0),
            "style": project.get("style", ""),
            "pacing_reference": project.get("pacing_reference", ""),
            "logline": "",
            "synopsis": "",
            "core_conflict": "",
            "main_plot": "",
            "subplots": [],
        },
        "current_chapter": 0,
        "characters": {},
        "world": {
            "rules": [],
            "timeline": [],
            "locations": [],
            "factions": [],
            "systems": [],
            "taboos": [],
        },
        "plot": {
            "events": [],
            "open_foreshadowing": [],
            "resolved_foreshadowing": [],
        },
        "chapter_summaries": {},
        "relationship_changes": [],
        "style_notes": [],
        "quality_issues": [],
    }


def load_memory(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_memory(path: Path, memory: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(memory, ensure_ascii=False, indent=2), encoding="utf-8")


def _key(item: Any) -> str:
    if isinstance(item, dict):
        return str(item.get("id") or item.get("name") or item.get("description") or item)
    return str(item)


def _append_unique(items: list[Any], new_items: list[Any]) -> None:
    existing = {_key(item) for item in items}
    for item in new_items:
        marker = _key(item)
        if marker not in existing:
            items.append(item)
            existing.add(marker)


def _remove_by_key(items: list[Any], remove_items: list[Any]) -> None:
    remove_keys = {_key(item) for item in remove_items}
    items[:] = [item for item in items if _key(item) not in remove_keys]


def apply_character_cards(memory: dict[str, Any], characters_payload: dict[str, Any]) -> dict[str, Any]:
    characters = characters_payload.get("characters", [])
    for card in characters:
        if not isinstance(card, dict) or not card.get("name"):
            continue
        memory.setdefault("characters", {})[card["name"]] = card
    return memory


def apply_worldbuilding_seed(memory: dict[str, Any], world_payload: dict[str, Any]) -> dict[str, Any]:
    world = memory.setdefault("world", {})
    for key in ("rules", "timeline", "locations", "factions", "systems", "taboos"):
        value = world_payload.get(key, [])
        if isinstance(value, list):
            _append_unique(world.setdefault(key, []), value)
    return memory


def apply_chapter_update(
    memory: dict[str, Any],
    chapter_number: int,
    update: dict[str, Any],
) -> dict[str, Any]:
    """Merge chapter output into memory.json without discarding prior facts."""

    memory["current_chapter"] = max(int(memory.get("current_chapter", 0)), chapter_number)

    summary = update.get("summary") or update.get("chapter_summary")
    if summary:
        memory.setdefault("chapter_summaries", {})[str(chapter_number)] = summary

    for character in update.get("new_characters", []) or []:
        if isinstance(character, dict) and character.get("name"):
            memory.setdefault("characters", {})[character["name"]] = character

    world = memory.setdefault("world", {})
    for location in update.get("new_locations", []) or []:
        _append_unique(world.setdefault("locations", []), [location])

    world_updates = update.get("world_updates") or {}
    if isinstance(world_updates, dict):
        for key in ("rules", "timeline", "locations", "factions", "systems", "taboos"):
            values = world_updates.get(key, [])
            if isinstance(values, list):
                _append_unique(world.setdefault(key, []), values)

    plot = memory.setdefault("plot", {})
    _append_unique(plot.setdefault("events", []), update.get("events", []) or [])
    _append_unique(
        plot.setdefault("open_foreshadowing", []),
        update.get("new_foreshadowing", []) or [],
    )
    resolved = update.get("resolved_foreshadowing", []) or []
    _append_unique(plot.setdefault("resolved_foreshadowing", []), resolved)
    _remove_by_key(plot.setdefault("open_foreshadowing", []), resolved)

    relationships = update.get("relationship_changes", []) or []
    for change in relationships:
        if isinstance(change, dict):
            change.setdefault("chapter", chapter_number)
    _append_unique(memory.setdefault("relationship_changes", []), relationships)

    quality_notes = update.get("quality_notes", []) or []
    _append_unique(memory.setdefault("quality_issues", []), quality_notes)
    return memory

