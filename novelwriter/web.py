"""FastAPI web application for NovelWriter Agent."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import AppConfig, NovelWriterAgent


ROOT_DIR = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT_DIR / "web"

app = FastAPI(title="NovelWriter Agent", version="0.2.0")
agent = NovelWriterAgent(AppConfig.load())

if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


class CreateProjectRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    genre: str = Field(min_length=1, max_length=120)
    protagonist: str = Field(min_length=1, max_length=300)
    style: str = Field(min_length=1, max_length=300)
    chapter_count: int = Field(default=10, ge=1, le=300)
    target_readers: str = "喜欢强剧情和连续追更的读者"
    world_seed: str = "由 NovelWriter Agent 根据题材自动扩展世界观"
    target_words: int | None = None
    words_per_chapter: int = Field(default=3000, ge=300, le=20000)
    pacing_reference: str = "每章有冲突、推进和结尾钩子"


def _project_or_404(slug: str) -> None:
    try:
        agent.storage.require_project(slug)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Project not found: {slug}") from exc


def _path_payload(path: Path) -> dict[str, str]:
    return {"path": str(path.resolve())}


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    index_path = WEB_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=500, detail="web/index.html is missing")
    return index_path.read_text(encoding="utf-8")


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "mock": agent.config.mock,
        "model": agent.config.openai_model,
        "novels_dir": str(agent.config.novels_dir.resolve()),
    }


@app.get("/api/projects")
def list_projects() -> dict[str, Any]:
    return {"projects": agent.list_projects(), "active_project": agent.active_project()}


@app.post("/api/projects")
def create_project(payload: CreateProjectRequest) -> dict[str, Any]:
    words_per_chapter = int(payload.words_per_chapter)
    answers = {
        "title": payload.title,
        "genre": payload.genre,
        "target_readers": payload.target_readers,
        "target_words": int(payload.target_words or words_per_chapter * payload.chapter_count),
        "chapter_count": payload.chapter_count,
        "words_per_chapter": words_per_chapter,
        "protagonist": payload.protagonist,
        "world_seed": payload.world_seed,
        "style": payload.style,
        "pacing_reference": payload.pacing_reference,
    }
    slug, path = agent.create_project(answers)
    return {"slug": slug, "project": agent.storage.load_metadata(slug).to_dict(), "path": str(path.resolve())}


@app.get("/api/projects/{slug}")
def get_project(slug: str) -> dict[str, Any]:
    _project_or_404(slug)
    project_path = agent.storage.require_project(slug)
    return {
        "project": agent.storage.load_metadata(slug).to_dict(),
        "memory": agent.storage.load_project_memory(slug),
        "setting": agent.storage.read_project_text(slug, "setting.md"),
        "worldbuilding": agent.storage.read_project_text(slug, "worldbuilding.md"),
        "outline": agent.storage.read_project_text(slug, "outline.md"),
        "characters": agent.storage.load_project_json(slug, "characters.json"),
        "chapters": _list_chapters(project_path),
    }


@app.post("/api/projects/{slug}/generate/{kind}")
def generate(slug: str, kind: str) -> dict[str, Any]:
    _project_or_404(slug)
    if kind == "setting":
        result = agent.generate_core_setting(slug)
        return {"kind": kind, **_path_payload(result["path"]), "data": result["data"]}
    if kind == "characters":
        result = agent.generate_characters(slug)
        return {"kind": kind, **_path_payload(result["path"]), "data": result["data"]}
    if kind == "world":
        result = agent.generate_worldbuilding(slug)
        return {"kind": kind, **_path_payload(result["path"])}
    if kind == "outline":
        result = agent.generate_outline(slug)
        return {"kind": kind, **_path_payload(result["path"])}
    if kind == "first_chapter":
        result = agent.generate_chapter(slug, 1)
        return {
            "kind": kind,
            **_path_payload(result["path"]),
            "summary": result["data"].get("summary", ""),
            "quality": result["quality"],
        }
    raise HTTPException(status_code=400, detail="kind must be one of: setting, characters, world, outline, first_chapter")


@app.get("/api/projects/{slug}/chapters")
def list_chapters(slug: str) -> dict[str, Any]:
    _project_or_404(slug)
    return {"chapters": _list_chapters(agent.storage.require_project(slug))}


@app.get("/api/projects/{slug}/chapters/{chapter_number}")
def read_chapter(slug: str, chapter_number: int) -> dict[str, Any]:
    _project_or_404(slug)
    try:
        content = agent.storage.read_chapter(slug, chapter_number)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Chapter not found: {chapter_number}") from exc
    return {"number": chapter_number, "content": content}


@app.post("/api/projects/{slug}/export")
def export_novel(slug: str) -> dict[str, str]:
    _project_or_404(slug)
    path = agent.export_novel(slug)
    return {"path": str(path.resolve()), "download_url": f"/api/projects/{slug}/export/download"}


@app.get("/api/projects/{slug}/export/download")
def download_export(slug: str) -> FileResponse:
    _project_or_404(slug)
    path = agent.export_novel(slug)
    return FileResponse(path, media_type="text/markdown; charset=utf-8", filename=path.name)


@app.exception_handler(Exception)
async def plain_exception_handler(_, exc: Exception) -> PlainTextResponse:
    return PlainTextResponse(str(exc), status_code=500)


def _list_chapters(project_path: Path) -> list[dict[str, Any]]:
    chapter_dir = project_path / "chapters"
    chapters: list[dict[str, Any]] = []
    for path in sorted(chapter_dir.glob("chapter_*.md")):
        stem = path.stem.replace("chapter_", "")
        try:
            number = int(stem)
        except ValueError:
            continue
        text = path.read_text(encoding="utf-8")
        title = text.splitlines()[0].lstrip("# ").strip() if text.splitlines() else f"第{number}章"
        chapters.append({"number": number, "title": title, "path": str(path.resolve())})
    return chapters

