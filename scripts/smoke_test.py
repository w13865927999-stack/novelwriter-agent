"""Offline smoke test for NovelWriter Agent.

This script intentionally runs in mock mode and writes to a temporary directory,
so it is suitable for local checks, GitHub Actions, and Codex Cloud validation.
"""

from __future__ import annotations

import json
import os
import py_compile
import shutil
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from novelwriter import AppConfig, NovelWriterAgent  # noqa: E402


def assert_exists(path: Path, label: str) -> None:
    if not path.exists():
        raise AssertionError(f"{label} does not exist: {path}")


def main() -> int:
    temp_root = Path(tempfile.mkdtemp(prefix="novelwriter-smoke-"))
    keep_dir = os.getenv("NOVELWRITER_KEEP_SMOKE_DIR") == "1"
    print(f"[smoke] temp root: {temp_root}")

    try:
        config = AppConfig(mock=True, novels_dir=temp_root / "novels")
        agent = NovelWriterAgent(config)

        slug, project_path = agent.create_project(
            {
                "title": "Smoke Test Novel",
                "slug": "smoke-test-novel",
                "genre": "科幻悬疑",
                "target_readers": "喜欢快节奏反转的读者",
                "target_words": 30000,
                "chapter_count": 3,
                "words_per_chapter": 1500,
                "protagonist": "调查员洛青",
                "world_seed": "近未来城市里，梦境记录可以作为证据使用",
                "style": "节奏明快，悬疑推进",
                "pacing_reference": "每章结尾保留钩子",
            }
        )
        assert slug == "smoke-test-novel"
        assert_exists(project_path / "metadata.json", "metadata")

        setting = agent.generate_core_setting(slug)
        characters = agent.generate_characters(slug)
        world = agent.generate_worldbuilding(slug)
        outline = agent.generate_outline(slug)
        chapter = agent.generate_chapter(slug, 1)
        report = agent.check_chapter(slug, 1)
        export_path = agent.export_novel(slug)
        web_files = [
            ROOT / "novelwriter" / "web.py",
            ROOT / "web" / "index.html",
            ROOT / "web" / "styles.css",
            ROOT / "web" / "app.js",
            ROOT / "scripts" / "run_web.py",
        ]

        for label, result in {
            "setting": setting,
            "characters": characters,
            "world": world,
            "outline": outline,
            "chapter": chapter,
        }.items():
            assert_exists(Path(result["path"]), label)

        assert_exists(export_path, "exported novel")
        for web_file in web_files:
            assert_exists(web_file, f"web file {web_file.name}")
        py_compile.compile(str(ROOT / "novelwriter" / "web.py"), doraise=True)
        py_compile.compile(str(ROOT / "scripts" / "run_web.py"), doraise=True)

        memory_path = project_path / "memory.json"
        memory = json.loads(memory_path.read_text(encoding="utf-8"))
        if int(memory.get("current_chapter", 0)) < 1:
            raise AssertionError("memory.json was not updated after chapter generation")
        if not report.get("heuristic"):
            raise AssertionError("quality check did not return heuristic report")

        print("[smoke] OK: project creation, generation, memory update, quality check, export, web files")
        return 0
    finally:
        if keep_dir:
            print(f"[smoke] kept temp root: {temp_root}")
        else:
            shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
