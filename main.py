"""Command line interface for NovelWriter Agent."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from novelwriter import AppConfig, NovelWriterAgent


def ask(label: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{label}{suffix}: ").strip()
    return value or default


def ask_int(label: str, default: int) -> int:
    while True:
        value = ask(label, str(default))
        try:
            return int(value)
        except ValueError:
            print("请输入数字。")


def collect_project_answers(args: argparse.Namespace) -> dict[str, Any]:
    answers = {
        "title": args.title or ask("小说标题", "未命名小说"),
        "slug": args.slug or "",
        "genre": args.genre or ask("小说类型/题材", "赛博朋克悬疑"),
        "target_readers": args.target_readers or ask("目标读者", "喜欢强剧情和反转的网文读者"),
        "target_words": args.target_words or ask_int("目标字数", 120000),
        "chapter_count": args.chapter_count or ask_int("章节数量", 40),
        "words_per_chapter": args.words_per_chapter or ask_int("每章大概字数", 3000),
        "protagonist": args.protagonist or ask("主角设定", "失去部分记忆的城市调查员林澈"),
        "world_seed": args.world_seed or ask("世界观设定", "巨型城市被算法和财阀共同统治，记忆可被交易"),
        "style": args.style or ask("写作风格", "网文节奏，悬疑推进，画面感强"),
        "pacing_reference": args.pacing_reference
        or ask("是否参考某种叙事节奏或网文风格", "三章一钩子，十章一反转"),
    }
    return answers


def resolve_project(agent: NovelWriterAgent, args: argparse.Namespace) -> str:
    slug = getattr(args, "project", None) or agent.active_project()
    if not slug:
        raise RuntimeError("当前没有选择小说项目。请先运行：python main.py list 或 python main.py select <项目slug>")
    return slug


def print_path(label: str, path: Path) -> None:
    print(f"{label}: {path.resolve()}")


def cmd_new(args: argparse.Namespace) -> None:
    agent = NovelWriterAgent()
    slug, path = agent.create_project(collect_project_answers(args))
    print(f"已创建并选择项目：{slug}")
    print_path("项目目录", path)


def cmd_list(args: argparse.Namespace) -> None:
    agent = NovelWriterAgent()
    active = agent.active_project()
    projects = agent.list_projects()
    if not projects:
        print("还没有小说项目。请运行：python main.py new")
        return
    for item in projects:
        marker = "*" if item.get("slug") == active else " "
        print(f"{marker} {item.get('slug')} | {item.get('title')} | {item.get('genre')} | {item.get('status')}")


def cmd_select(args: argparse.Namespace) -> None:
    agent = NovelWriterAgent()
    agent.select_project(args.slug)
    print(f"已选择项目：{args.slug}")


def cmd_setting(args: argparse.Namespace) -> None:
    agent = NovelWriterAgent()
    slug = resolve_project(agent, args)
    result = agent.generate_core_setting(slug)
    print_path("核心设定已保存", result["path"])
    print(result["data"].get("logline", ""))


def cmd_characters(args: argparse.Namespace) -> None:
    agent = NovelWriterAgent()
    slug = resolve_project(agent, args)
    result = agent.generate_characters(slug)
    print_path("人物卡已保存", result["path"])
    print(f"人物数量：{len(result['data'].get('characters', []))}")


def cmd_world(args: argparse.Namespace) -> None:
    agent = NovelWriterAgent()
    slug = resolve_project(agent, args)
    result = agent.generate_worldbuilding(slug)
    print_path("世界观已保存", result["path"])


def cmd_outline(args: argparse.Namespace) -> None:
    agent = NovelWriterAgent()
    slug = resolve_project(agent, args)
    result = agent.generate_outline(slug)
    print_path("完整大纲已保存", result["path"])


def cmd_chapter(args: argparse.Namespace) -> None:
    agent = NovelWriterAgent()
    slug = resolve_project(agent, args)
    result = agent.generate_chapter(slug, args.number)
    print_path(f"第 {args.number} 章已保存", result["path"])
    print("摘要：", result["data"].get("summary", ""))
    print("质检建议：", "；".join(result["quality"].get("suggestions", [])))


def cmd_next(args: argparse.Namespace) -> None:
    agent = NovelWriterAgent()
    slug = resolve_project(agent, args)
    result = agent.generate_next_chapter(slug)
    print_path("下一章已保存", result["path"])
    print("摘要：", result["data"].get("summary", ""))


def cmd_continue(args: argparse.Namespace) -> None:
    agent = NovelWriterAgent()
    slug = resolve_project(agent, args)
    result = agent.continue_chapter(slug, args.number)
    print_path(f"第 {args.number} 章已续写", result["path"])
    print("摘要：", result["data"].get("summary", ""))


def cmd_rewrite(args: argparse.Namespace) -> None:
    agent = NovelWriterAgent()
    slug = resolve_project(agent, args)
    result = agent.rewrite_chapter(slug, args.number, args.instruction)
    print_path(f"第 {args.number} 章已重写", result["path"])
    print("摘要：", result["data"].get("summary", ""))


def cmd_polish(args: argparse.Namespace) -> None:
    agent = NovelWriterAgent()
    slug = resolve_project(agent, args)
    result = agent.polish_chapter(slug, args.number, args.instruction)
    print_path(f"第 {args.number} 章已润色", result["path"])


def cmd_memory(args: argparse.Namespace) -> None:
    agent = NovelWriterAgent()
    slug = resolve_project(agent, args)
    result = agent.update_memory_from_chapter(slug, args.number)
    print_path("memory.json 已更新", result["path"])
    print(json.dumps(result["data"], ensure_ascii=False, indent=2))


def cmd_check(args: argparse.Namespace) -> None:
    agent = NovelWriterAgent()
    slug = resolve_project(agent, args)
    report = agent.check_chapter(slug, args.number)
    print(json.dumps(report, ensure_ascii=False, indent=2))


def cmd_export(args: argparse.Namespace) -> None:
    agent = NovelWriterAgent()
    slug = resolve_project(agent, args)
    path = agent.export_novel(slug)
    print_path("整本小说已导出", path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="NovelWriter Agent CLI")
    parser.add_argument("--project", help="指定小说项目 slug；不填则使用当前已选择项目")
    subparsers = parser.add_subparsers(dest="command", required=True)

    new_parser = subparsers.add_parser("new", help="创建新小说项目")
    new_parser.add_argument("--title")
    new_parser.add_argument("--slug")
    new_parser.add_argument("--genre")
    new_parser.add_argument("--target-readers")
    new_parser.add_argument("--target-words", type=int)
    new_parser.add_argument("--chapter-count", type=int)
    new_parser.add_argument("--words-per-chapter", type=int)
    new_parser.add_argument("--protagonist")
    new_parser.add_argument("--world-seed")
    new_parser.add_argument("--style")
    new_parser.add_argument("--pacing-reference")
    new_parser.set_defaults(func=cmd_new)

    subparsers.add_parser("list", help="查看项目列表").set_defaults(func=cmd_list)

    select_parser = subparsers.add_parser("select", help="选择小说项目")
    select_parser.add_argument("slug")
    select_parser.set_defaults(func=cmd_select)

    subparsers.add_parser("setting", help="生成小说核心设定").set_defaults(func=cmd_setting)
    subparsers.add_parser("characters", help="生成人物卡").set_defaults(func=cmd_characters)
    subparsers.add_parser("world", help="生成世界观").set_defaults(func=cmd_world)
    subparsers.add_parser("outline", help="生成完整大纲").set_defaults(func=cmd_outline)

    chapter_parser = subparsers.add_parser("chapter", help="生成指定章节")
    chapter_parser.add_argument("number", type=int)
    chapter_parser.set_defaults(func=cmd_chapter)

    subparsers.add_parser("next", help="连续生成下一章").set_defaults(func=cmd_next)

    continue_parser = subparsers.add_parser("continue", help="续写当前章节或指定章节")
    continue_parser.add_argument("number", type=int)
    continue_parser.set_defaults(func=cmd_continue)

    rewrite_parser = subparsers.add_parser("rewrite", help="重写某一章")
    rewrite_parser.add_argument("number", type=int)
    rewrite_parser.add_argument("--instruction", default="加强冲突、减少解释、保持原有剧情事实")
    rewrite_parser.set_defaults(func=cmd_rewrite)

    polish_parser = subparsers.add_parser("polish", help="润色某一章")
    polish_parser.add_argument("number", type=int)
    polish_parser.add_argument("--instruction", default="提升画面感、对白自然度和节奏张力")
    polish_parser.set_defaults(func=cmd_polish)

    memory_parser = subparsers.add_parser("memory", help="根据章节正文更新 memory.json")
    memory_parser.add_argument("number", type=int)
    memory_parser.set_defaults(func=cmd_memory)

    check_parser = subparsers.add_parser("check", help="检查剧情矛盾和章节质量")
    check_parser.add_argument("number", type=int)
    check_parser.set_defaults(func=cmd_check)

    subparsers.add_parser("export", help="导出整本小说为 Markdown").set_defaults(func=cmd_export)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
        return 0
    except Exception as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

