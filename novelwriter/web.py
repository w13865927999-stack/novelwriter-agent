"""FastAPI web application for NovelWriter Agent."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import AppConfig, NovelWriterAgent


ROOT_DIR = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT_DIR / "web"
DATA_DIR = ROOT_DIR / "data"
TASKS_PATH = DATA_DIR / "tasks.json"

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
    chapter_word_count: int | None = Field(default=None, ge=300, le=20000)
    words_per_chapter: int = Field(default=3000, ge=300, le=20000)
    pacing_reference: str = "每章有冲突、推进和结尾钩子"


class GenerationOptions(BaseModel):
    chapter_word_count: int | None = Field(default=None, ge=300, le=20000)
    words_per_chapter: int | None = Field(default=None, ge=300, le=20000)


class ChapterEditRequest(BaseModel):
    content: str = Field(min_length=1)


class ChapterInstructionRequest(BaseModel):
    instruction: str = "加强冲突、减少解释、保持原有剧情事实"


class ReferenceRequest(BaseModel):
    reference_text: str = Field(min_length=1)
    reference_note: str = ""


class WorkspaceTaskRequest(BaseModel):
    task: str | None = None
    message: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)
    options: dict[str, Any] = Field(default_factory=dict)
    route: dict[str, Any] = Field(default_factory=dict)


def _project_or_404(slug: str) -> None:
    try:
        agent.storage.require_project(slug)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Project not found: {slug}") from exc


def _path_payload(path: Path) -> dict[str, str]:
    return {"path": str(path.resolve())}


def _requested_chapter_word_count(options: GenerationOptions | None) -> int | None:
    if options is None:
        return None
    value = options.chapter_word_count or options.words_per_chapter
    return int(value) if value else None


def _apply_chapter_word_count(slug: str, options: GenerationOptions | None) -> None:
    chapter_word_count = _requested_chapter_word_count(options)
    if chapter_word_count is None:
        return

    project = agent.storage.load_metadata(slug)
    project.words_per_chapter = chapter_word_count
    if not project.target_words:
        project.target_words = chapter_word_count * project.chapter_count
    agent.storage.save_metadata(project)

    memory = agent.storage.load_project_memory(slug)
    memory.setdefault("novel_info", {})["words_per_chapter"] = chapter_word_count
    agent.storage.save_project_memory(slug, memory)


def _project_status(slug: str) -> dict[str, Any]:
    _project_or_404(slug)
    setting = agent.storage.read_project_text(slug, "setting.md")
    worldbuilding = agent.storage.read_project_text(slug, "worldbuilding.md")
    outline = agent.storage.read_project_text(slug, "outline.md")
    characters = agent.storage.load_project_json(slug, "characters.json")
    has_setting = bool(setting.strip()) and "尚未生成" not in setting
    has_worldbuilding = bool(worldbuilding.strip()) and "尚未生成" not in worldbuilding
    has_outline = bool(outline.strip()) and "尚未生成" not in outline
    has_characters = bool(characters.get("characters"))
    missing = [
        name
        for name, ready in (
            ("设定", has_setting),
            ("人物", has_characters),
            ("世界观", has_worldbuilding),
            ("大纲", has_outline),
        )
        if not ready
    ]
    return {
        "has_setting": has_setting,
        "has_characters": has_characters,
        "has_worldbuilding": has_worldbuilding,
        "has_outline": has_outline,
        "ready_for_chapters": not missing,
        "missing": missing,
    }


def _ensure_ready_for_chapters(slug: str) -> None:
    status = _project_status(slug)
    if not status["ready_for_chapters"]:
        raise HTTPException(
            status_code=400,
            detail="请先点击“一键初始化”，或按顺序生成前置资料：" + "、".join(status["missing"]),
        )


def _capabilities() -> list[dict[str, str]]:
    return [
        {"name": "create_project", "description": "创建小说项目"},
        {"name": "generate_setting", "description": "生成小说设定"},
        {"name": "generate_characters", "description": "生成人物卡"},
        {"name": "generate_world", "description": "生成世界观"},
        {"name": "generate_outline", "description": "生成大纲"},
        {"name": "generate_first_chapter", "description": "生成第一章"},
        {"name": "generate_next_chapter", "description": "生成下一章"},
        {"name": "rewrite_chapter", "description": "重写章节"},
        {"name": "continue_chapter", "description": "续写章节"},
        {"name": "export_markdown", "description": "导出 Markdown"},
    ]


def _task_history() -> list[dict[str, Any]]:
    if not TASKS_PATH.exists():
        return []
    try:
        data = json.loads(TASKS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def _save_task_record(record: dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tasks = _task_history()
    tasks.insert(0, record)
    TASKS_PATH.write_text(json.dumps(tasks[:200], ensure_ascii=False, indent=2), encoding="utf-8")


def _record_task(
    *,
    task_id: str,
    task: str,
    action: str,
    project: str | None,
    success: bool,
    result: Any = None,
    files: list[str] | None = None,
    warnings: list[str] | None = None,
    error: str = "",
) -> dict[str, Any]:
    record = {
        "task_id": task_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": "novelwriter-agent",
        "task": task,
        "action": action,
        "project": project,
        "success": success,
        "result": result,
        "files": files or [],
        "warnings": warnings or [],
        "error": error,
    }
    _save_task_record(record)
    return record


def _resolve_workspace_task_text(payload: WorkspaceTaskRequest) -> str:
    return (payload.task or payload.message or "").strip()


def _detect_workspace_action(task_text: str) -> str:
    lowered = task_text.lower()
    if any(keyword in task_text for keyword in ("下一章", "继续写", "生成下一章")):
        return "generate_next_chapter"
    if any(keyword in task_text for keyword in ("第一章", "生成第一章")):
        return "generate_first_chapter"
    if "设定" in task_text:
        return "generate_setting"
    if "人物" in task_text:
        return "generate_characters"
    if "世界观" in task_text:
        return "generate_world"
    if "大纲" in task_text:
        return "generate_outline"
    if "导出" in task_text or "export" in lowered:
        return "export_markdown"
    if "重写" in task_text:
        return "rewrite_chapter"
    if "续写" in task_text:
        return "continue_chapter"
    return "unknown"


def _recent_project_slug() -> str | None:
    active = agent.active_project()
    if active:
        return active
    projects = agent.list_projects()
    if not projects:
        return None
    projects.sort(key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""), reverse=True)
    return str(projects[0].get("slug") or "") or None


def _resolve_project_slug(payload: WorkspaceTaskRequest) -> str | None:
    context = payload.context or {}
    options = payload.options or {}
    raw = context.get("project") or context.get("slug") or options.get("project") or options.get("slug")
    if raw:
        return str(raw).strip()
    return _recent_project_slug()


def _chapter_number_from_payload(payload: WorkspaceTaskRequest, slug: str, default: int = 1) -> int:
    for source in (payload.options or {}, payload.context or {}):
        value = source.get("chapter_number") or source.get("chapter")
        if value:
            try:
                return int(value)
            except (TypeError, ValueError):
                continue
    memory = agent.storage.load_project_memory(slug)
    current = int(memory.get("current_chapter", 0) or 0)
    return current or default


def _result_summary(action: str, result: dict[str, Any] | Path | Any) -> str:
    if isinstance(result, Path):
        return f"{action} 执行完成：{result.name}"
    if isinstance(result, dict):
        path = result.get("path") or result.get("chapter_path") or result.get("analysis_path")
        if path:
            return f"{action} 执行完成：{Path(path).name}"
        if result.get("message"):
            return str(result["message"])
    return f"{action} 执行完成"


def _files_from_result(result: dict[str, Any] | Path | Any) -> list[str]:
    if isinstance(result, Path):
        return [str(result.resolve())]
    if not isinstance(result, dict):
        return []
    files: list[str] = []
    for key in ("path", "chapter_path", "analysis_path", "reference_path"):
        value = result.get(key)
        if isinstance(value, Path):
            files.append(str(value.resolve()))
        elif value:
            files.append(str(value))
    return files


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    index_path = WEB_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=500, detail="web/index.html is missing")
    return index_path.read_text(encoding="utf-8")


@app.get("/api/health")
def health() -> dict[str, Any]:
    mode = "mock" if agent.config.mock else "real"
    return {
        "ok": True,
        "mock": agent.config.mock,
        "mode": mode,
        "mode_label": "Mock 模式" if agent.config.mock else "真实模型模式",
        "model": agent.config.openai_model,
        "novels_dir": str(agent.config.novels_dir.resolve()),
        "api_key_configured": bool(agent.config.openai_api_key),
    }


@app.get("/api/capabilities")
def capabilities() -> dict[str, Any]:
    return {
        "agent_id": "novelwriter-agent",
        "name": "小说智能体",
        "type": "writing",
        "capabilities": _capabilities(),
    }


@app.post("/api/tasks")
def run_workspace_task(payload: WorkspaceTaskRequest) -> dict[str, Any]:
    task_id = str(uuid4())
    task_text = _resolve_workspace_task_text(payload)
    action = _detect_workspace_action(task_text)
    warnings: list[str] = []

    if not task_text:
        error = "任务内容不能为空。"
        _record_task(task_id=task_id, task=task_text, action=action, project=None, success=False, error=error)
        return {"success": False, "agent": "novelwriter-agent", "task_id": task_id, "action": action, "error": error, "warnings": warnings}

    if action == "unknown":
        error = "暂未识别到可执行的小说操作。请说明要生成设定、人物、世界观、大纲、章节、续写、重写或导出。"
        _record_task(task_id=task_id, task=task_text, action=action, project=None, success=False, error=error)
        return {"success": False, "agent": "novelwriter-agent", "task_id": task_id, "action": action, "error": error, "warnings": warnings}

    slug = _resolve_project_slug(payload)
    if not slug:
        error = "请先指定小说项目，或在小说智能体中创建项目。"
        _record_task(task_id=task_id, task=task_text, action=action, project=None, success=False, error=error)
        return {"success": False, "agent": "novelwriter-agent", "task_id": task_id, "action": action, "error": error, "warnings": warnings}

    try:
        agent.storage.require_project(slug)
    except FileNotFoundError:
        error = f"请先指定有效小说项目，当前找不到项目：{slug}"
        _record_task(task_id=task_id, task=task_text, action=action, project=slug, success=False, error=error)
        return {"success": False, "agent": "novelwriter-agent", "task_id": task_id, "action": action, "error": error, "warnings": warnings}

    try:
        result: Any
        if action == "generate_setting":
            result = agent.generate_core_setting(slug)
        elif action == "generate_characters":
            result = agent.generate_characters(slug)
        elif action == "generate_world":
            result = agent.generate_worldbuilding(slug)
        elif action == "generate_outline":
            result = agent.generate_outline(slug)
        elif action == "generate_first_chapter":
            result = agent.generate_chapter(slug, 1)
        elif action == "generate_next_chapter":
            result = agent.generate_next_chapter(slug)
        elif action == "rewrite_chapter":
            chapter_number = _chapter_number_from_payload(payload, slug)
            instruction = str((payload.options or {}).get("instruction") or task_text)
            result = agent.rewrite_chapter(slug, chapter_number, instruction)
        elif action == "continue_chapter":
            chapter_number = _chapter_number_from_payload(payload, slug)
            result = agent.continue_chapter(slug, chapter_number)
        elif action == "export_markdown":
            result = agent.export_novel(slug)
        else:
            raise ValueError("暂未支持该动作。")
    except Exception as exc:
        error = str(exc)
        _record_task(task_id=task_id, task=task_text, action=action, project=slug, success=False, error=error)
        return {"success": False, "agent": "novelwriter-agent", "task_id": task_id, "action": action, "error": error, "warnings": warnings}

    files = _files_from_result(result)
    summary = _result_summary(action, result)
    _record_task(
        task_id=task_id,
        task=task_text,
        action=action,
        project=slug,
        success=True,
        result=summary,
        files=files,
        warnings=warnings,
    )
    return {
        "success": True,
        "agent": "novelwriter-agent",
        "task_id": task_id,
        "action": action,
        "result": summary,
        "files": files,
        "warnings": warnings,
    }


@app.get("/api/tasks")
def list_workspace_tasks() -> dict[str, Any]:
    return {"tasks": _task_history()}


@app.get("/api/tasks/{task_id}")
def get_workspace_task(task_id: str) -> dict[str, Any]:
    for task in _task_history():
        if task.get("task_id") == task_id:
            return task
    raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")


@app.get("/api/projects")
def list_projects() -> dict[str, Any]:
    return {"projects": agent.list_projects(), "active_project": agent.active_project()}


@app.post("/api/projects")
def create_project(payload: CreateProjectRequest) -> dict[str, Any]:
    chapter_word_count = int(payload.chapter_word_count or payload.words_per_chapter or 3000)
    answers = {
        "title": payload.title,
        "genre": payload.genre,
        "target_readers": payload.target_readers,
        "target_words": int(payload.target_words or chapter_word_count * payload.chapter_count),
        "chapter_count": payload.chapter_count,
        "words_per_chapter": chapter_word_count,
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
        "status": _project_status(slug),
    }


@app.get("/api/projects/{slug}/status")
def project_status(slug: str) -> dict[str, Any]:
    return _project_status(slug)


@app.post("/api/projects/{slug}/generate/{kind}")
def generate(slug: str, kind: str, options: GenerationOptions | None = Body(default=None)) -> dict[str, Any]:
    _project_or_404(slug)
    _apply_chapter_word_count(slug, options)
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
        _ensure_ready_for_chapters(slug)
        result = agent.generate_chapter(slug, 1)
        chapter_path = Path(result["path"])
        return {
            "kind": kind,
            **_path_payload(chapter_path),
            "chapter_content": chapter_path.read_text(encoding="utf-8"),
            "summary": result.get("memory_update", {}).get("summary", ""),
            "quality": result["quality"],
        }
    raise HTTPException(status_code=400, detail="kind must be one of: setting, characters, world, outline, first_chapter")


@app.post("/api/projects/{slug}/initialize")
def initialize_project(slug: str, options: GenerationOptions | None = Body(default=None)) -> dict[str, Any]:
    _project_or_404(slug)
    _apply_chapter_word_count(slug, options)
    steps: list[dict[str, Any]] = []
    for name, fn in (
        ("setting", agent.generate_core_setting),
        ("characters", agent.generate_characters),
        ("world", agent.generate_worldbuilding),
        ("outline", agent.generate_outline),
    ):
        result = fn(slug)
        steps.append({"step": name, "path": str(result["path"].resolve())})
    chapter = agent.generate_chapter(slug, 1)
    steps.append({"step": "first_chapter", "path": str(chapter["path"].resolve())})
    return {"project_name": slug, "message": "一键初始化完成。", "steps": steps}


@app.post("/api/projects/{slug}/next")
def generate_next_chapter(slug: str, options: GenerationOptions | None = Body(default=None)) -> dict[str, Any]:
    _project_or_404(slug)
    _apply_chapter_word_count(slug, options)
    _ensure_ready_for_chapters(slug)
    try:
        result = agent.generate_next_chapter(slug)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to generate next chapter: {exc}") from exc

    chapter_path = Path(result["path"])
    try:
        chapter_number = int(chapter_path.stem.replace("chapter_", ""))
    except ValueError:
        chapter_number = int(agent.storage.load_project_memory(slug).get("current_chapter", 0))

    content = chapter_path.read_text(encoding="utf-8") if chapter_path.exists() else ""
    title = result["data"].get("chapter_title") or _chapter_title_from_content(content, chapter_number)
    return {
        "project_name": slug,
        "chapter_number": chapter_number,
        "chapter_title": title,
        "chapter_content": content,
        "path": str(chapter_path.resolve()),
        "message": f"第 {chapter_number} 章生成成功。",
    }


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


@app.put("/api/projects/{slug}/chapters/{chapter_number}")
def update_chapter(slug: str, chapter_number: int, payload: ChapterEditRequest) -> dict[str, Any]:
    _project_or_404(slug)
    result = agent.save_edited_chapter(slug, chapter_number, payload.content)
    return {
        "project_name": slug,
        "chapter_number": chapter_number,
        "path": str(result["chapter_path"].resolve()),
        "message": f"第 {chapter_number} 章已保存并更新记忆。",
    }


@app.delete("/api/projects/{slug}/chapters/{chapter_number}")
def delete_chapter(slug: str, chapter_number: int) -> dict[str, Any]:
    _project_or_404(slug)
    try:
        path = agent.delete_chapter(slug, chapter_number)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Chapter not found: {chapter_number}") from exc
    return {"project_name": slug, "chapter_number": chapter_number, "path": str(path.resolve()), "message": f"第 {chapter_number} 章已删除。"}


@app.post("/api/projects/{slug}/chapters/{chapter_number}/rewrite")
def rewrite_chapter(slug: str, chapter_number: int, payload: ChapterInstructionRequest) -> dict[str, Any]:
    _project_or_404(slug)
    result = agent.rewrite_chapter(slug, chapter_number, payload.instruction)
    content = Path(result["path"]).read_text(encoding="utf-8")
    return {
        "project_name": slug,
        "chapter_number": chapter_number,
        "chapter_content": content,
        "path": str(result["path"].resolve()),
        "message": f"第 {chapter_number} 章已重写。",
    }


@app.post("/api/projects/{slug}/chapters/{chapter_number}/continue")
def continue_chapter(slug: str, chapter_number: int) -> dict[str, Any]:
    _project_or_404(slug)
    result = agent.continue_chapter(slug, chapter_number)
    content = Path(result["path"]).read_text(encoding="utf-8")
    return {
        "project_name": slug,
        "chapter_number": chapter_number,
        "chapter_content": content,
        "path": str(result["path"].resolve()),
        "message": f"第 {chapter_number} 章已续写。",
    }


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


@app.post("/api/projects/{slug}/references")
def save_reference_text(slug: str, payload: ReferenceRequest) -> dict[str, str]:
    _project_or_404(slug)
    path = agent.save_reference_text(slug, payload.reference_text, payload.reference_note)
    return {"project_name": slug, "path": str(path.resolve()), "message": "参考文本已保存。"}


@app.post("/api/projects/{slug}/references/analyze")
def analyze_reference_text(slug: str, payload: ReferenceRequest) -> dict[str, str]:
    _project_or_404(slug)
    result = agent.analyze_reference_text(slug, payload.reference_text, payload.reference_note)
    return {
        "project_name": slug,
        "reference_path": str(result["reference_path"].resolve()),
        "analysis_path": str(result["analysis_path"].resolve()),
        "analysis": result["analysis"],
        "message": "参考分析已生成。输出将只借鉴抽象结构、节奏和技法。",
    }


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


def _chapter_title_from_content(content: str, chapter_number: int) -> str:
    for line in content.splitlines():
        title = line.strip().lstrip("#").strip()
        if title:
            return title
    return f"第{chapter_number}章"
