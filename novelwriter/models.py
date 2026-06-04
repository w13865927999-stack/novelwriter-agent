"""Data models used by NovelWriter Agent.

The project keeps these models dependency-light on purpose. Dataclasses are
simple to serialize, easy to extend, and do not force users to install a heavy
validation framework before they can run the CLI.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timezone
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _pick_known_fields(cls: type, data: dict[str, Any]) -> dict[str, Any]:
    names = {item.name for item in fields(cls)}
    return {key: value for key, value in data.items() if key in names}


@dataclass(slots=True)
class NovelProject:
    title: str
    slug: str
    genre: str
    target_readers: str
    target_words: int
    chapter_count: int
    words_per_chapter: int
    protagonist: str
    world_seed: str
    style: str
    pacing_reference: str = ""
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    status: str = "draft"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NovelProject":
        return cls(**_pick_known_fields(cls, data))


@dataclass(slots=True)
class CharacterCard:
    name: str
    age: str = ""
    identity: str = ""
    personality: str = ""
    goal: str = ""
    weakness: str = ""
    secret: str = ""
    relationships: dict[str, str] = field(default_factory=dict)
    arc: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ChapterRecord:
    number: int
    title: str
    summary: str = ""
    core_event: str = ""
    conflict: str = ""
    hook: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class MemoryPatch:
    summary: str = ""
    new_characters: list[dict[str, Any]] = field(default_factory=list)
    new_locations: list[dict[str, Any]] = field(default_factory=list)
    new_foreshadowing: list[dict[str, Any]] = field(default_factory=list)
    resolved_foreshadowing: list[dict[str, Any]] = field(default_factory=list)
    relationship_changes: list[dict[str, Any]] = field(default_factory=list)
    world_updates: dict[str, Any] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

