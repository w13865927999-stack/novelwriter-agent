"""Core orchestration for NovelWriter Agent."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .config import AppConfig
from .llm import LLMClient
from .memory import apply_chapter_update, apply_character_cards, apply_worldbuilding_seed, remove_chapter_memory
from .models import NovelProject
from .prompts import (
    SYSTEM_PROMPT,
    chapter_generation_prompt,
    chapter_plan_prompt,
    characters_prompt,
    continue_chapter_prompt,
    core_setting_prompt,
    memory_update_prompt,
    outline_prompt,
    polish_chapter_prompt,
    quality_check_prompt,
    reference_analysis_prompt,
    rewrite_chapter_prompt,
    worldbuilding_prompt,
)
from .quality import heuristic_quality_scan
from .storage import Storage


MEMORY_FIELD_NAMES = {
    "memory_update",
    "summary",
    "chapter_summary",
    "new_characters",
    "new_locations",
    "new_foreshadowing",
    "resolved_foreshadowing",
    "relationship_changes",
    "world_updates",
    "events",
    "occurred_events",
    "discovered_clues",
    "new_clues",
    "current_plot_position",
    "forbidden_repetition_notes",
    "quality_notes",
}


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

    def ensure_generation_ready(self, slug: str) -> None:
        missing: list[str] = []
        if "尚未生成" in self.storage.read_project_text(slug, "setting.md"):
            missing.append("设定")
        characters = self.storage.load_project_json(slug, "characters.json")
        if not characters.get("characters"):
            missing.append("人物")
        if "尚未生成" in self.storage.read_project_text(slug, "worldbuilding.md"):
            missing.append("世界观")
        if "尚未生成" in self.storage.read_project_text(slug, "outline.md"):
            missing.append("大纲")
        if missing:
            raise ValueError("请先点击“一键初始化”，或按顺序生成前置资料：" + "、".join(missing))

    def generate_chapter_plan(self, slug: str, chapter_number: int) -> dict[str, Any]:
        context = self._chapter_context(slug, chapter_number)
        response = self.llm.generate(
            chapter_plan_prompt(
                context["profile"],
                context["outline"],
                context["chapter_outline"],
                context["memory"],
                context["previous_summary"],
                chapter_number,
                context["reference_analysis"],
            ),
            SYSTEM_PROMPT,
        )
        plan = self._json_or_default(response, {})
        if not plan:
            plan = {
                "chapter_goal": f"推进第 {chapter_number} 章剧情。",
                "new_event": "产生一个新事件。",
                "conflict": "制造新的阻碍和选择。",
                "clues": [],
                "foreshadowing": [],
                "ending_hook": "留下新钩子。",
                "avoid_repetition": [],
            }
        self.storage.append_log(slug, f"chapter-{chapter_number:03d}-plan", self._log_payload("章节计划", response, plan))
        return plan

    def generate_chapter(self, slug: str, chapter_number: int) -> dict[str, Any]:
        self.ensure_generation_ready(slug)
        context = self._chapter_context(slug, chapter_number)
        context["chapter_plan"] = self.generate_chapter_plan(slug, chapter_number)
        prompt = chapter_generation_prompt(**context)
        response = self.llm.generate(prompt, SYSTEM_PROMPT)
        parsed = self._split_chapter_response(response, chapter_number)
        payload = parsed["payload"]
        chapter_text = parsed["chapter_text"]
        memory_update = parsed["memory_update"]

        memory_before_save = self.storage.load_project_memory(slug)
        recent_chapters = self._recent_chapters(slug, chapter_number)
        quality = heuristic_quality_scan(context["profile"], context["chapter_outline"], chapter_text, memory_before_save, recent_chapters)
        if quality.get("repetition_warning"):
            retry_prompt = (
                prompt
                + "\n\nREWRITE_TO_AVOID_REPETITION:\n"
                + "\n".join(quality.get("repetition_issues", []))
                + "\n请完全避开上述重复问题，重写本章正文和记忆更新。"
            )
            retry_response = self.llm.generate(retry_prompt, SYSTEM_PROMPT)
            retry_parsed = self._split_chapter_response(retry_response, chapter_number)
            retry_text = retry_parsed["chapter_text"]
            retry_quality = heuristic_quality_scan(
                context["profile"],
                context["chapter_outline"],
                retry_text,
                memory_before_save,
                recent_chapters,
            )
            if not retry_quality.get("repetition_warning") or retry_quality.get("similarity_to_recent", 1) <= quality.get("similarity_to_recent", 1):
                response = retry_response
                payload = retry_parsed["payload"]
                chapter_text = retry_text
                memory_update = retry_parsed["memory_update"]
                quality = retry_quality

        chapter_path = self.storage.save_chapter(slug, chapter_number, chapter_text)
        memory = self.storage.load_project_memory(slug)
        apply_chapter_update(memory, chapter_number, memory_update)
        self.storage.save_project_memory(slug, memory)

        self.storage.append_log(slug, f"chapter-{chapter_number:03d}-generation", self._log_payload("章节生成", response, payload))
        self.storage.append_log(slug, f"chapter-{chapter_number:03d}-quality", json.dumps(quality, ensure_ascii=False, indent=2))
        return {"path": chapter_path, "data": payload, "memory_update": memory_update, "quality": quality}

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
        parsed = self._split_chapter_response(response, chapter_number, text_keys=("appended_text", "appended_markdown", "chapter_text", "chapter_markdown"))
        payload = parsed["payload"]
        appended = parsed["chapter_text"]
        path = self.storage.append_chapter(slug, chapter_number, appended)
        apply_chapter_update(memory, chapter_number, parsed["memory_update"])
        self.storage.save_project_memory(slug, memory)
        self.storage.append_log(slug, f"chapter-{chapter_number:03d}-continue", self._log_payload("续写", response, payload))
        return {"path": path, "data": payload, "memory_update": parsed["memory_update"]}

    def rewrite_chapter(self, slug: str, chapter_number: int, instruction: str) -> dict[str, Any]:
        profile = self._profile(slug)
        chapter_text = self.storage.read_chapter(slug, chapter_number)
        memory = self.storage.load_project_memory(slug)
        prompt = rewrite_chapter_prompt(profile, chapter_number, chapter_text, instruction, memory)
        response = self.llm.generate(prompt, SYSTEM_PROMPT)
        parsed = self._split_chapter_response(response, chapter_number)
        payload = parsed["payload"]
        rewritten = parsed["chapter_text"]
        path = self.storage.save_chapter(slug, chapter_number, rewritten)
        apply_chapter_update(memory, chapter_number, parsed["memory_update"])
        self.storage.save_project_memory(slug, memory)
        self.storage.append_log(slug, f"chapter-{chapter_number:03d}-rewrite", self._log_payload("重写", response, payload))
        return {"path": path, "data": payload, "memory_update": parsed["memory_update"]}

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

    def save_edited_chapter(self, slug: str, chapter_number: int, content: str) -> dict[str, Any]:
        chapter_path = self.storage.save_chapter(slug, chapter_number, content)
        memory_result = self.update_memory_from_chapter(slug, chapter_number)
        memory_result["chapter_path"] = chapter_path
        return memory_result

    def delete_chapter(self, slug: str, chapter_number: int) -> Path:
        path = self.storage.delete_chapter(slug, chapter_number)
        memory = self.storage.load_project_memory(slug)
        remove_chapter_memory(memory, chapter_number)
        self.storage.save_project_memory(slug, memory)
        self.storage.append_log(slug, f"chapter-{chapter_number:03d}-delete", f"Deleted chapter {chapter_number}: {path}")
        return path

    def save_reference_text(self, slug: str, reference_text: str, reference_note: str = "") -> Path:
        project_path = self.storage.require_project(slug)
        reference_dir = project_path / "references"
        reference_dir.mkdir(parents=True, exist_ok=True)
        path = reference_dir / "reference_text.md"
        content = (
            "# 参考文本\n\n"
            "## 使用说明\n"
            f"{reference_note.strip()}\n\n"
            "## 文本\n"
            f"{reference_text.strip()}\n"
        )
        self.storage.write_text(path, content)
        return path

    def analyze_reference_text(self, slug: str, reference_text: str, reference_note: str = "") -> dict[str, Any]:
        profile = self._profile(slug)
        reference_path = self.save_reference_text(slug, reference_text, reference_note)
        response = self.llm.generate(reference_analysis_prompt(profile, reference_text, reference_note), SYSTEM_PROMPT)
        analysis_path = self.storage.write_project_text(slug, "reference_analysis.md", response.strip() + "\n")
        self.storage.append_log(slug, "reference-analysis", response)
        return {"reference_path": reference_path, "analysis_path": analysis_path, "analysis": response}

    def check_chapter(self, slug: str, chapter_number: int) -> dict[str, Any]:
        context = self._chapter_context(slug, chapter_number)
        chapter_text = self.storage.read_chapter(slug, chapter_number)
        heuristic = heuristic_quality_scan(
            context["profile"],
            context["chapter_outline"],
            chapter_text,
            context["memory"],
            self._recent_chapters(slug, chapter_number),
        )
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
        reference_analysis = self.storage.read_project_text(slug, "reference_analysis.md")
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
            "reference_analysis": reference_analysis,
        }

    def _recent_chapters(self, slug: str, chapter_number: int, limit: int = 3) -> list[dict[str, Any]]:
        recent: list[dict[str, Any]] = []
        for number in range(max(1, chapter_number - limit), chapter_number):
            try:
                recent.append({"number": number, "content": self.storage.read_chapter(slug, number)})
            except FileNotFoundError:
                continue
        return recent

    def _split_chapter_response(
        self,
        response: str,
        chapter_number: int,
        text_keys: tuple[str, ...] = ("chapter_text", "chapter_markdown", "chapter_content", "appended_text", "appended_markdown"),
    ) -> dict[str, Any]:
        """Separate model output into pure chapter text and background memory JSON.

        Real models sometimes return JSON as a string, escaped Markdown, or a
        Markdown section followed by a memory object. This method is deliberately
        defensive: only the sanitized novel text is written to chapter files,
        while all structured fields are merged into memory.json.
        """

        payload = self._json_or_default(response, {})
        if not isinstance(payload, dict):
            payload = {}

        chapter_text = ""
        for key in text_keys:
            value = payload.get(key)
            if value:
                chapter_text = self._sanitize_chapter_text(value, chapter_number)
                break

        if not chapter_text:
            chapter_text = self._sanitize_chapter_text(response, chapter_number)

        memory_update = self._extract_memory_update(payload)
        if not memory_update.get("summary"):
            memory_update["summary"] = self._summarize_for_memory(chapter_text)

        normalized_payload = {
            "chapter_title": payload.get("chapter_title") or self._chapter_title_from_text(chapter_text, chapter_number),
            "chapter_text": chapter_text,
            "memory_update": memory_update,
        }
        return {"payload": normalized_payload, "chapter_text": chapter_text, "memory_update": memory_update}

    @staticmethod
    def _extract_memory_update(payload: dict[str, Any]) -> dict[str, Any]:
        memory_update = payload.get("memory_update")
        if isinstance(memory_update, dict):
            result = dict(memory_update)
        else:
            result = {key: payload.get(key) for key in MEMORY_FIELD_NAMES if key in payload and key != "memory_update"}

        for key in ("new_characters", "new_locations", "new_foreshadowing", "resolved_foreshadowing", "relationship_changes", "events", "discovered_clues", "forbidden_repetition_notes", "quality_notes"):
            if result.get(key) is None:
                result[key] = []
        if not isinstance(result.get("world_updates"), dict):
            result["world_updates"] = {"rules": [], "timeline": [], "locations": [], "factions": [], "systems": [], "taboos": []}
        return result

    @classmethod
    def _sanitize_chapter_text(cls, value: Any, chapter_number: int) -> str:
        if isinstance(value, (dict, list)):
            candidate = ""
        else:
            candidate = str(value or "").strip()

        if candidate.startswith("```"):
            candidate = re.sub(r"^```(?:markdown|md|text)?", "", candidate, flags=re.I).strip()
            candidate = re.sub(r"```$", "", candidate).strip()

        decoded = cls._decode_json_string(candidate)
        if decoded is not None:
            candidate = decoded.strip()

        if "\\n" in candidate or "\\r" in candidate or '\\"' in candidate:
            maybe_decoded = cls._decode_json_string(f'"{candidate}"')
            if maybe_decoded is not None:
                candidate = maybe_decoded.strip()
            else:
                candidate = candidate.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\r", "\n").replace('\\"', '"')

        candidate = cls._strip_embedded_memory_json(candidate).strip()
        candidate = candidate.strip('"').strip()
        if not candidate:
            candidate = f"# 第{chapter_number}章\n\n（本章正文生成失败，请重写本章。）"
        return candidate.rstrip() + "\n"

    @staticmethod
    def _decode_json_string(value: str) -> str | None:
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return None
        return decoded if isinstance(decoded, str) else None

    @staticmethod
    def _strip_embedded_memory_json(text: str) -> str:
        text = re.sub(r"```json\s*.*?```", "", text, flags=re.I | re.S)
        text = re.sub(r"(?is)\n+\s*(MEMORY_UPDATE|memory_update|后台记忆|记忆更新)\s*[:：].*$", "", text)
        memory_markers = tuple(MEMORY_FIELD_NAMES - {"summary", "chapter_summary"})
        first_brace = text.find("{")
        if first_brace != -1:
            tail = text[first_brace:]
            if any(f'"{marker}"' in tail or f"'{marker}'" in tail for marker in memory_markers):
                text = text[:first_brace]
        for marker in memory_markers:
            marker_index = text.find(marker)
            if marker_index != -1:
                line_start = text.rfind("\n", 0, marker_index)
                if line_start != -1:
                    text = text[:line_start]
        return text

    @staticmethod
    def _chapter_title_from_text(text: str, chapter_number: int) -> str:
        for line in text.splitlines():
            title = line.strip().lstrip("#").strip()
            if title:
                return title[:80]
        return f"第{chapter_number}章"

    @staticmethod
    def _summarize_for_memory(text: str, limit: int = 180) -> str:
        compact = re.sub(r"\s+", " ", text).strip("# ").strip()
        return compact[:limit]

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
