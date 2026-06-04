"""Filesystem storage for NovelWriter projects."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from .memory import default_memory, load_memory, save_memory
from .models import NovelProject, utc_now


class Storage:
    def __init__(self, novels_dir: Path):
        self.novels_dir = novels_dir
        self.base_dir = novels_dir.parent
        self.state_path = self.base_dir / ".novelwriter_state.json"
        self.novels_dir.mkdir(parents=True, exist_ok=True)

    def make_slug(self, title: str) -> str:
        slug = re.sub(r"[^a-z0-9_-]+", "-", title.lower()).strip("-")
        if not slug:
            slug = "novel-" + datetime.now().strftime("%Y%m%d-%H%M%S")
        candidate = slug
        index = 2
        while (self.novels_dir / candidate).exists():
            candidate = f"{slug}-{index}"
            index += 1
        return candidate

    def create_project(self, project: NovelProject) -> Path:
        project_path = self.project_path(project.slug)
        (project_path / "chapters").mkdir(parents=True, exist_ok=True)
        (project_path / "logs").mkdir(parents=True, exist_ok=True)
        self.save_json(project_path / "metadata.json", project.to_dict())
        self.save_json(project_path / "memory.json", default_memory(project.to_dict()))
        self.save_json(project_path / "characters.json", {"characters": []})
        self.write_text(project_path / "setting.md", f"# {project.title} 核心设定\n\n尚未生成。\n")
        self.write_text(project_path / "worldbuilding.md", f"# {project.title} 世界观\n\n尚未生成。\n")
        self.write_text(project_path / "outline.md", f"# {project.title} 大纲\n\n尚未生成。\n")
        self.write_text(project_path / "logs" / ".gitkeep", "")
        self.select_project(project.slug)
        return project_path

    def project_path(self, slug: str) -> Path:
        return self.novels_dir / slug

    def require_project(self, slug: str) -> Path:
        path = self.project_path(slug)
        if not path.exists():
            raise FileNotFoundError(f"找不到小说项目：{slug}")
        return path

    def list_projects(self) -> list[dict[str, Any]]:
        projects: list[dict[str, Any]] = []
        for path in sorted(self.novels_dir.iterdir()):
            if not path.is_dir():
                continue
            metadata_path = path / "metadata.json"
            if metadata_path.exists():
                data = self.load_json(metadata_path)
                data["_path"] = str(path)
                projects.append(data)
        return projects

    def select_project(self, slug: str) -> None:
        self.require_project(slug)
        self.save_json(self.state_path, {"active_project": slug, "updated_at": utc_now()})

    def active_project(self) -> str | None:
        if not self.state_path.exists():
            return None
        data = self.load_json(self.state_path)
        slug = data.get("active_project")
        if slug and self.project_path(slug).exists():
            return slug
        return None

    def load_metadata(self, slug: str) -> NovelProject:
        data = self.load_json(self.require_project(slug) / "metadata.json")
        return NovelProject.from_dict(data)

    def save_metadata(self, project: NovelProject) -> None:
        project.updated_at = utc_now()
        self.save_json(self.require_project(project.slug) / "metadata.json", project.to_dict())

    def load_project_memory(self, slug: str) -> dict[str, Any]:
        return load_memory(self.require_project(slug) / "memory.json")

    def save_project_memory(self, slug: str, memory: dict[str, Any]) -> None:
        save_memory(self.require_project(slug) / "memory.json", memory)

    def read_project_text(self, slug: str, filename: str) -> str:
        path = self.require_project(slug) / filename
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

    def write_project_text(self, slug: str, filename: str, content: str) -> Path:
        path = self.require_project(slug) / filename
        self.write_text(path, content)
        return path

    def load_project_json(self, slug: str, filename: str) -> dict[str, Any]:
        path = self.require_project(slug) / filename
        if not path.exists():
            return {}
        return self.load_json(path)

    def save_project_json(self, slug: str, filename: str, data: dict[str, Any]) -> Path:
        path = self.require_project(slug) / filename
        self.save_json(path, data)
        return path

    def chapter_path(self, slug: str, chapter_number: int) -> Path:
        return self.require_project(slug) / "chapters" / f"chapter_{chapter_number:03d}.md"

    def save_chapter(self, slug: str, chapter_number: int, content: str) -> Path:
        path = self.chapter_path(slug, chapter_number)
        self.write_text(path, content.rstrip() + "\n")
        return path

    def append_chapter(self, slug: str, chapter_number: int, content: str) -> Path:
        path = self.chapter_path(slug, chapter_number)
        existing = path.read_text(encoding="utf-8") if path.exists() else ""
        separator = "\n\n" if existing.strip() else ""
        self.write_text(path, existing.rstrip() + separator + content.rstrip() + "\n")
        return path

    def read_chapter(self, slug: str, chapter_number: int) -> str:
        path = self.chapter_path(slug, chapter_number)
        if not path.exists():
            raise FileNotFoundError(f"找不到第 {chapter_number} 章：{path}")
        return path.read_text(encoding="utf-8")

    def append_log(self, slug: str, name: str, content: str) -> Path:
        log_dir = self.require_project(slug) / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        safe_name = re.sub(r"[^a-zA-Z0-9_-]+", "-", name).strip("-") or "log"
        path = log_dir / f"{timestamp}-{safe_name}.md"
        self.write_text(path, content)
        return path

    def export_project(self, slug: str, output_name: str = "exported_novel.md") -> Path:
        project = self.load_metadata(slug)
        project_path = self.require_project(slug)
        chapters = sorted((project_path / "chapters").glob("chapter_*.md"))
        parts = [
            f"# {project.title}",
            "",
            f"> 类型：{project.genre}  \n> 风格：{project.style}",
            "",
        ]
        for chapter in chapters:
            parts.append(chapter.read_text(encoding="utf-8").strip())
            parts.append("")
        output_path = project_path / output_name
        self.write_text(output_path, "\n\n".join(parts).rstrip() + "\n")
        return output_path

    @staticmethod
    def load_json(path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def save_json(path: Path, data: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def write_text(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

