"""Core orchestration for NovelWriter Agent."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .config import AppConfig
from .llm import LLMClient
from .memory import apply_chapter_update, apply_character_cards, apply_worldbuilding_seed
from .models import NovelProject
from .prompts import (
    SYSTEM_PROMPT,
    chapter_generation_prompt,
    characters_prompt,
    continue_chapter_prompt,
    core_setting_prompt,
    memory_update_prompt,
    outline_prompt,
    polish_chapter_prompt,
    quality_check_prompt,
    rewrite_chapter_prompt,
    worldbuilding_prompt,
)
from .quality import heuristic_quality_scan
from .storage import Storage


class NovelWriterAgent:
    """High-level API used by the CLI and future integrations."""

    def __init__(self, config: AppConfig | None = None):
        self.config = config or AppConfig.load()
        self.storage = Storage(self.config.novels_dir)
        self.llm = LLMClient(self.config)

    def create_project(self, answers: dict[str, Any]) -> tuple[str, Path]:
        title = str(answers.get("title") or "未命名小说").strip()
        slug = str(answers.get("slug") or "").strip() or self.storage.make_slug(title)
        project = NovelProject(
            title=title,
            slug=slug,
            genre=str(answers.get("genre") or "").strip(),
            target_readers=str(answers.get("target_readers") or "").strip(),
            target_words=int(answers.get("target_words") or 100000),
            chapter_count=int(answers.get("chapter_count") or 30),
            words_per_chapter=int(answers.get("words_per_chapter") or 3000),
            protagonist=str(answers.get("protagonist") or "").strip(),
            world_seed=str(answers.get("world_seed") or "").strip(),
            style=str(answers.get("style") or "").strip(),
            pacing_reference=str(answers.get("pacing_reference") or "").strip(),
        )
        path = self.storage.create_project(project)
        return project.slug, path

    def list_projects(self) -> list[dict[str, Any]]:
        return self.storage.list_projects()

    def select_project(self, slug: str) -> None:
        self.storage.select_project(slug)

    def active_project(self) -> str | None:
        return self.storage.active_project()

    def generate_core_setting(self, slug: str) -> dict[str, Any]:
        profile = self._profile(slug)
        response = self.llm.generate(core_setting_prompt(profile), SYSTEM_PROMPT)
        payload = self._json_or_default(response, {})
        if not payload:
            payload = {
                "logline": "",
                "synopsis": response.strip(),
                "core_conflict": "",
                "main_plot": "",
                "subplots": [],
                "selling_points": [],
                "release_copy": "",
            }
        markdown = self._format_setting(profile, payload)
        path = self.storage.write_project_text(slug, "setting.md", markdown)

        memory = self.storage.load_project_memory(slug)
        memory.setdefault("novel_info", {}).update(payload)
        self.storage.save_project_memory(slug, memory)
        self.storage.append_log(slug, "generate-setting", self._log_payload("核心设定", response, payload))
        return {"path": path, "data": payload}

    def generate_characters(self, slug: str) -> dict[str, Any]:
        profile = self._profile(slug)
        setting = self.storage.read_project_text(slug, "setting.md")
        response = self.llm.generate(characters_prompt(profile, setting), SYSTEM_PROMPT)
        payload = self._json_or_default(response, {"characters": []})
        path = self.storage.save_project_json(slug, "characters.json", payload)

        memory = self.storage.load_project_memory(slug)
        apply_character_cards(memory, payload)
        self.storage.save_project_memory(slug, memory)
        self.storage.append_log(slug, "generate-characters", self._log_payload("人物卡", response, payload))
        return {"path": path, "data": payload}

    def generate_worldbuilding(self, slug: str) -> dict[str, Any]:
        profile = self._profile(slug)
        setting = self.storage.read_project_text(slug, "setting.md")
        characters = self.storage.load_project_json(slug, "characters.json")
        response = self.llm.generate(worldbuilding_prompt(profile, setting, characters), SYSTEM_PROMPT)
        path = self.storage.write_project_text(slug, "worldbuilding.md", response.strip() + "\n")

        memory = self.storage.load_project_memory(slug)
        apply_worldbuilding_seed(memory, self._world_seed_from_markdown(response))
        self.storage.save_project_memory(slug, memory)
        self.storage.append_log(slug, "generate-worldbuilding", response)
        return {"path": path, "data": response}

    def generate_outline(self, slug: str) -> dict[str, Any]:
        profile = self._profile(slug)
        setting = self.storage.read_project_text(slug, "setting.md")
        worldbuilding = self.storage.read_project_text(slug, "worldbuilding.md")
        characters = self.storage.load_project_json(slug, "characters.json")
        response = self.llm.generate(outline_prompt(profile, setting, worldbuilding, characters), SYSTEM_PROMPT)
        path = self.storage.write_project_text(slug, "outline.md", response.strip() + "\n")
        self.storage.append_log(slug, "generate-outline", response)
        return {"path": path, "data": response}

    def generate_chapter(self, slug: str, chapter_number: int) -> dict[str, Any]:
        context = self._chapter_context(slug, chapter_number)
        prompt = chapter_generation_prompt(**context)
        response = self.llm.generate(prompt, SYSTEM_PROMPT)
        payload = self._json_or_default(response, {})
        if not payload:
            payload = {
                "chapter_title": f"第{chapter_number}章",
                "chapter_markdown": response.strip(),
                "summary": "",
            }

        chapter_text = payload.get("chapter_markdown") or response.strip()
        chapter_path = self.storage.save_chapter(slug, chapter_number, chapter_text)
        memory = self.storage.load_project_memory(slug)
        apply_chapter_update(memory, chapter_number, payload)
        self.storage.save_project_memory(slug, memory)

        quality = heuristic_quality_scan(context["profile"], context["chapter_outline"], chapter_text, memory)
        self.storage.append_log(slug, f"chapter-{chapter_number:03d}-generation", self._log_payload("章节生成", response, payload))
        self.storage.append_log(slug, f"chapter-{chapter_number:03d}-quality", json.dumps(quality, ensure_ascii=False, indent=2))
        return {"path": chapter_path, "data": payload, "quality": quality}

    def generate_next_chapter(self, slug: str) -> dict[str, Any]:
        project = self.storage.load_metadata(slug)
        memory = self.storage.load_project_memory(slug)
        next_number = int(memory.get("current_chapter", 0)) + 1
        if next_number > project.chapter_count:
            raise ValueError(f"已达到章节上限：{project.chapter_count}")
        return self.generate_chapter(slug, next_number)

    def continue_chapter(self, slug: str, chapter_number: int) -> dict[str, Any]:
        profile = self._profile(slug)
        chapter_text = self.storage.read_chapter(slug, chapter_number)
        memory = self.storage.load_project_memory(slug)
        prompt = continue_chapter_prompt(profile, chapter_number, chapter_text, memory)
        response = self.llm.generate(prompt, SYSTEM_PROMPT)
        payload = self._json_or_default(response, {})
        appended = payload.get("appended_markdown") or response.strip()
        path = self.storage.append_chapter(slug, chapter_number, appended)
        apply_chapter_update(memory, chapter_number, payload)
        self.storage.save_project_memory(slug, memory)
        self.storage.append_log(slug, f"chapter-{chapter_number:03d}-continue", self._log_payload("续写", response, payload))
        return {"path": path, "data": payload}

    def rewrite_chapter(self, slug: str, chapter_number: int, instruction: str) -> dict[str, Any]:
        profile = self._profile(slug)
        chapter_text = self.storage.read_chapter(slug, chapter_number)
        memory = self.storage.load_project_memory(slug)
        prompt = rewrite_chapter_prompt(profile, chapter_number, chapter_text, instruction, memory)
        response = self.llm.generate(prompt, SYSTEM_PROMPT)
        payload = self._json_or_default(response, {})
        rewritten = payload.get("chapter_markdown") or response.strip()
        path = self.storage.save_chapter(slug, chapter_number, rewritten)
        apply_chapter_update(memory, chapter_number, payload)
        self.storage.save_project_memory(slug, memory)
        self.storage.append_log(slug, f"chapter-{chapter_number:03d}-rewrite", self._log_payload("重写", response, payload))
        return {"path": path, "data": payload}

    def polish_chapter(self, slug: str, chapter_number: int, instruction: str) -> dict[str, Any]:
        profile = self._profile(slug)
        chapter_text = self.storage.read_chapter(slug, chapter_number)
        response = self.llm.generate(polish_chapter_prompt(profile, chapter_number, chapter_text, instruction), SYSTEM_PROMPT)
        path = self.storage.save_chapter(slug, chapter_number, response.strip())
        self.storage.append_log(slug, f"chapter-{chapter_number:03d}-polish", response)
        return {"path": path, "data": {"chapter_markdown": response.strip()}}

    def update_memory_from_chapter(self, slug: str, chapter_number: int) -> dict[str, Any]:
        profile = self._profile(slug)
        chapter_text = self.storage.read_chapter(slug, chapter_number)
        memory = self.storage.load_project_memory(slug)
        response = self.llm.generate(memory_update_prompt(profile, chapter_number, chapter_text, memory), SYSTEM_PROMPT)
        payload = self._json_or_default(response, {})
        apply_chapter_update(memory, chapter_number, payload)
        self.storage.save_project_memory(slug, memory)
        self.storage.append_log(slug, f"chapter-{chapter_number:03d}-memory-update", self._log_payload("记忆更新", response, payload))
        return {"path": self.storage.require_project(slug) / "memory.json", "data": payload}

    def check_chapter(self, slug: str, chapter_number: int) -> dict[str, Any]:
        context = self._chapter_context(slug, chapter_number)
        chapter_text = self.storage.read_chapter(slug, chapter_number)
        heuristic = heuristic_quality_scan(context["profile"], context["chapter_outline"], chapter_text, context["memory"])
        response = self.llm.generate(
            quality_check_prompt(
                context["profile"],
                chapter_number,
                context["chapter_outline"],
                chapter_text,
                context["memory"],
            ),
            SYSTEM_PROMPT,
            temperature=0.2,
        )
        llm_report = self._json_or_default(response, {})
        report = {"heuristic": heuristic, "llm": llm_report or {"raw": response.strip()}}
        self.storage.append_log(slug, f"chapter-{chapter_number:03d}-quality-check", json.dumps(report, ensure_ascii=False, indent=2))
        return report

    def export_novel(self, slug: str) -> Path:
        return self.storage.export_project(slug)

    def _profile(self, slug: str) -> dict[str, Any]:
        return self.storage.load_metadata(slug).to_dict()

    def _chapter_context(self, slug: str, chapter_number: int) -> dict[str, Any]:
        profile = self._profile(slug)
        setting = self.storage.read_project_text(slug, "setting.md")
        worldbuilding = self.storage.read_project_text(slug, "worldbuilding.md")
        characters = self.storage.load_project_json(slug, "characters.json")
        outline = self.storage.read_project_text(slug, "outline.md")
        memory = self.storage.load_project_memory(slug)
        previous_summary = memory.get("chapter_summaries", {}).get(str(chapter_number - 1), "")
        return {
            "profile": profile,
            "setting": setting,
            "worldbuilding": worldbuilding,
            "characters": characters,
            "outline": outline,
            "chapter_outline": self.extract_chapter_outline(outline, chapter_number),
            "memory": memory,
            "previous_summary": previous_summary,
            "chapter_number": chapter_number,
        }

    @staticmethod
    def extract_chapter_outline(outline: str, chapter_number: int) -> str:
        pattern = rf"(^|\n)##\s*第\s*{chapter_number}\s*章[^\n]*\n(?P<body>.*?)(?=\n##\s*第\s*\d+\s*章|\Z)"
        match = re.search(pattern, outline, flags=re.S)
        if match:
            header_start = match.start()
            next_start = match.end("body")
            return outline[header_start:next_start].strip()
        return f"第{chapter_number}章：大纲中未找到该章节，请围绕主线推进并保持记忆一致。"

    @staticmethod
    def _json_or_default(text: str, default: Any) -> Any:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.I).strip()
            cleaned = re.sub(r"```$", "", cleaned).strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(cleaned[start : end + 1])
                except json.JSONDecodeError:
                    return default
        return default

    @staticmethod
    def _format_setting(profile: dict[str, Any], payload: dict[str, Any]) -> str:
        subplots = "\n".join(f"- {item}" for item in payload.get("subplots", []))
        selling_points = "\n".join(f"- {item}" for item in payload.get("selling_points", []))
        return (
            f"# {profile.get('title', '')} 核心设定\n\n"
            f"## 一句话卖点\n{payload.get('logline', '')}\n\n"
            f"## 故事简介\n{payload.get('synopsis', '')}\n\n"
            f"## 核心冲突\n{payload.get('core_conflict', '')}\n\n"
            f"## 主线剧情\n{payload.get('main_plot', '')}\n\n"
            f"## 支线剧情\n{subplots}\n\n"
            f"## 卖点\n{selling_points}\n\n"
            f"## 发布文案\n{payload.get('release_copy', '')}\n"
        )

    @staticmethod
    def _world_seed_from_markdown(markdown: str) -> dict[str, Any]:
        """Extract a small structured seed from generated worldbuilding markdown."""

        result = {"rules": [], "timeline": [], "locations": [], "factions": [], "systems": [], "taboos": []}
        section_map = {
            "时间线": "timeline",
            "地点": "locations",
            "势力": "factions",
            "能力体系或科技体系": "systems",
            "禁忌、限制和代价": "taboos",
            "世界观一致性规则": "rules",
        }
        current_key = ""
        for line in markdown.splitlines():
            header = line.strip().lstrip("#").strip()
            if header in section_map:
                current_key = section_map[header]
                continue
            if current_key and line.strip().startswith("-"):
                result[current_key].append(line.strip()[1:].strip())
        return result

    @staticmethod
    def _log_payload(title: str, raw: str, payload: Any) -> str:
        return (
            f"# {title}\n\n"
            "## Parsed\n\n"
            f"```json\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n```\n\n"
            "## Raw\n\n"
            f"```text\n{raw}\n```\n"
        )

