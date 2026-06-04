"""Offline smoke test for NovelWriter Agent.

This script intentionally runs the core generation flow in mock mode and writes
to a temporary directory, so it is suitable for local checks, GitHub Actions,
and Codex Cloud validation. It also performs static checks for the Web UI/API
surface so lightweight regressions are caught before deployment.
"""

from __future__ import annotations

import json
import os
import py_compile
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from novelwriter import AppConfig, NovelWriterAgent  # noqa: E402


def assert_exists(path: Path, label: str) -> None:
    if not path.exists():
        raise AssertionError(f"{label} does not exist: {path}")


def assert_contains(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise AssertionError(f"{label} must contain: {needle}")


def assert_git_ignores_env() -> None:
    result = subprocess.run(
        ["git", "check-ignore", "-q", ".env"],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(".env must be ignored by git")


def assert_real_mode_config_can_load() -> None:
    original_mock = os.environ.get("NOVELWRITER_MOCK")
    original_key = os.environ.get("OPENAI_API_KEY")
    try:
        os.environ["NOVELWRITER_MOCK"] = "false"
        os.environ["OPENAI_API_KEY"] = original_key or "sk-test-not-real"
        config = AppConfig.load()
        if config.mock:
            raise AssertionError("NOVELWRITER_MOCK=false must load real model mode")
        if not config.openai_api_key:
            raise AssertionError("real mode config should read OPENAI_API_KEY when present")
    finally:
        if original_mock is None:
            os.environ.pop("NOVELWRITER_MOCK", None)
        else:
            os.environ["NOVELWRITER_MOCK"] = original_mock
        if original_key is None:
            os.environ.pop("OPENAI_API_KEY", None)
        else:
            os.environ["OPENAI_API_KEY"] = original_key


def assert_web_surface() -> None:
    web_files = [
        ROOT / "novelwriter" / "web.py",
        ROOT / "web" / "index.html",
        ROOT / "web" / "styles.css",
        ROOT / "web" / "app.js",
        ROOT / "scripts" / "run_web.py",
    ]
    for web_file in web_files:
        assert_exists(web_file, f"web file {web_file.name}")

    py_compile.compile(str(ROOT / "novelwriter" / "web.py"), doraise=True)
    py_compile.compile(str(ROOT / "scripts" / "run_web.py"), doraise=True)

    index_text = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    app_text = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
    web_text = (ROOT / "novelwriter" / "web.py").read_text(encoding="utf-8")
    prompts_text = (ROOT / "novelwriter" / "prompts.py").read_text(encoding="utf-8")

    for label in [
        "\u751f\u6210\u8bbe\u5b9a",
        "\u751f\u6210\u4eba\u7269",
        "\u751f\u6210\u4e16\u754c\u89c2",
        "\u751f\u6210\u5927\u7eb2",
        "\u751f\u6210\u7b2c\u4e00\u7ae0",
        "\u751f\u6210\u4e0b\u4e00\u7ae0",
        "\u6bcf\u7ae0\u76ee\u6807\u5b57\u6570",
        "\u7f16\u8f91\u7ae0\u8282",
        "\u5220\u9664\u7ae0\u8282",
        "\u91cd\u5199\u7ae0\u8282",
        "\u7eed\u5199\u7ae0\u8282",
        "\u53c2\u8003\u6587\u672c",
        "\u4e00\u952e\u521d\u59cb\u5316",
    ]:
        assert_contains(index_text, label, "web/index.html")

    for marker in [
        "chapter_word_count",
        "/next",
        "/initialize",
        "/references",
        "generateNextChapter",
        "saveChapter",
        "deleteChapter",
        "rewriteChapter",
        "continueChapter",
        "\u64cd\u4f5c\u5931\u8d25",
        "\u771f\u5b9e\u6a21\u578b\u6a21\u5f0f",
        "Mock \u6a21\u5f0f",
        "loadProjects",
        "setOutput",
    ]:
        assert_contains(app_text, marker, "web/app.js")

    for marker in [
        '@app.get("/api/health")',
        '@app.post("/api/projects")',
        'kind == "setting"',
        'kind == "characters"',
        'kind == "world"',
        'kind == "outline"',
        'kind == "first_chapter"',
        '@app.post("/api/projects/{slug}/next")',
        '@app.get("/api/projects/{slug}/chapters")',
        '@app.get("/api/projects/{slug}/chapters/{chapter_number}")',
        '@app.put("/api/projects/{slug}/chapters/{chapter_number}")',
        '@app.delete("/api/projects/{slug}/chapters/{chapter_number}")',
        '@app.post("/api/projects/{slug}/chapters/{chapter_number}/rewrite")',
        '@app.post("/api/projects/{slug}/chapters/{chapter_number}/continue")',
        '@app.post("/api/projects/{slug}/export")',
        '@app.post("/api/projects/{slug}/references")',
        '@app.post("/api/projects/{slug}/references/analyze")',
        "chapter_word_count",
    ]:
        assert_contains(web_text, marker, "novelwriter/web.py")

    for marker in [
        "\u6bcf\u7ae0\u76ee\u6807\u5b57\u6570",
        "\u4e0d\u5f97\u91cd\u590d\u4e0a\u4e00\u7ae0\u4e3b\u8981\u573a\u666f",
        "\u4e0d\u8981\u7167\u642c\u53c2\u8003\u6587\u672c",
        "TASK:CHAPTER_PLAN",
        "TASK:REFERENCE_ANALYSIS",
    ]:
        assert_contains(prompts_text, marker, "novelwriter/prompts.py")


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
                "genre": "\u79d1\u5e7b\u60ac\u7591",
                "target_readers": "\u559c\u6b22\u5feb\u8282\u594f\u53cd\u8f6c\u7684\u8bfb\u8005",
                "target_words": 30000,
                "chapter_count": 3,
                "words_per_chapter": 1500,
                "protagonist": "\u8c03\u67e5\u5458\u6d1b\u9752",
                "world_seed": "\u8fd1\u672a\u6765\u57ce\u5e02\u91cc\uff0c\u68a6\u5883\u8bb0\u5f55\u53ef\u4ee5\u4f5c\u4e3a\u8bc1\u636e\u4f7f\u7528",
                "style": "\u8282\u594f\u660e\u5feb\uff0c\u60ac\u7591\u63a8\u8fdb",
                "pacing_reference": "\u6bcf\u7ae0\u7ed3\u5c3e\u4fdd\u7559\u94a9\u5b50",
            }
        )
        assert slug == "smoke-test-novel"
        assert_exists(project_path / "metadata.json", "metadata")

        setting = agent.generate_core_setting(slug)
        characters = agent.generate_characters(slug)
        world = agent.generate_worldbuilding(slug)
        reference = agent.analyze_reference_text(
            slug,
            "\u8fd9\u662f\u4e00\u6bb5\u7528\u4e8e\u5206\u6790\u8282\u594f\u548c\u60ac\u5ff5\u8bbe\u8ba1\u7684\u539f\u521b\u53c2\u8003\u7247\u6bb5\u3002",
            "\u53ea\u53c2\u8003\u60ac\u5ff5\u94a9\u5b50\u548c\u7ae0\u8282\u8282\u594f\uff0c\u4e0d\u590d\u5236\u5177\u4f53\u8868\u8fbe\u3002",
        )
        outline = agent.generate_outline(slug)
        chapter = agent.generate_chapter(slug, 1)
        next_chapter = agent.generate_next_chapter(slug)
        edited = agent.save_edited_chapter(slug, 1, Path(chapter["path"]).read_text(encoding="utf-8") + "\n")
        report = agent.check_chapter(slug, 1)
        export_path = agent.export_novel(slug)

        for label, result in {
            "setting": setting,
            "characters": characters,
            "world": world,
            "reference": reference,
            "outline": outline,
            "chapter": chapter,
            "next_chapter": next_chapter,
            "edited_chapter": edited,
        }.items():
            path = result.get("path") or result.get("analysis_path") or result.get("chapter_path")
            assert_exists(Path(path), label)

        assert_exists(export_path, "exported novel")
        assert_web_surface()
        assert_git_ignores_env()
        assert_real_mode_config_can_load()

        memory_path = project_path / "memory.json"
        memory = json.loads(memory_path.read_text(encoding="utf-8"))
        if int(memory.get("current_chapter", 0)) < 2:
            raise AssertionError("memory.json was not updated after chapter generation")
        for key in [
            "chapter_summaries",
            "occurred_events",
            "discovered_clues",
            "unresolved_hooks",
            "resolved_hooks",
            "character_changes",
            "current_plot_position",
            "forbidden_repetition_notes",
        ]:
            if key not in memory:
                raise AssertionError(f"memory.json missing key: {key}")
        if not report.get("heuristic"):
            raise AssertionError("quality check did not return heuristic report")
        if "repetition_warning" not in report["heuristic"]:
            raise AssertionError("quality check did not include repetition scan")

        exported_text = Path(export_path).read_text(encoding="utf-8")
        if "\u7b2c" not in exported_text and "Chapter" not in exported_text:
            raise AssertionError("exported Markdown does not appear to contain chapters")

        print(
            "[smoke] OK: project creation, generation, memory update, "
            "quality check, export, web/API checks, env safety"
        )
        return 0
    finally:
        if keep_dir:
            print(f"[smoke] kept temp root: {temp_root}")
        else:
            shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
