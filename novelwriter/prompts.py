"""Prompt templates for NovelWriter Agent."""

from __future__ import annotations

import json
from typing import Any


SYSTEM_PROMPT = """你是 NovelWriter Agent，一个专业长篇小说创作智能体。

你的职责：
1. 你擅长长篇小说规划、人物弧光设计、世界观搭建、主线与支线编排。
2. 你必须保持剧情、人物、世界规则和时间线的一致性。
3. 你必须遵守 memory.json、characters.json、worldbuilding.md 和 outline.md 中已有设定。
4. 你不能随意推翻已确认设定；如需改变，必须让变化有明确铺垫、代价和因果。
5. 你需要主动维护伏笔：新增伏笔要登记，回收伏笔要明确标记。
6. 你需要保持人物成长线，避免角色行为突然崩坏。
7. 每章都必须包含冲突、推进、情绪变化和结尾钩子。
8. 你必须根据用户指定题材、目标读者、叙事节奏和写作风格创作。
9. 输出小说正文时，正文内容内部不要夹杂解释、分析、创作说明或元叙事。
10. 生成规划、记忆更新和质检时必须结构化输出，并优先输出合法 JSON 或清晰 Markdown。

写作底线：
- 不要重复灌水，不要让角色用解释性对白替代行动。
- 不要让新设定无代价解决旧冲突。
- 不要让章节停留在静态介绍，必须让情节发生变化。
- 不要遗忘未回收伏笔、人物秘密和世界观限制。
"""


def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def core_setting_prompt(profile: dict[str, Any]) -> str:
    target_words = int(profile.get("words_per_chapter") or 3000)
    return f"""[TASK:CORE_SETTING]
请根据 PROFILE_JSON 生成小说核心设定。只输出合法 JSON，不要输出 Markdown 代码块。
每章目标字数：约 {target_words} 字。请据此设计章节节奏、冲突密度和信息释放速度。

PROFILE_JSON:
{_json(profile)}

输出 JSON schema:
{{
  "logline": "一句话卖点",
  "synopsis": "故事简介，300-600字",
  "core_conflict": "核心冲突",
  "main_plot": "主线剧情",
  "subplots": ["支线剧情1", "支线剧情2", "支线剧情3"],
  "selling_points": ["卖点1", "卖点2", "卖点3"],
  "release_copy": "适合发布平台的简介文案"
}}
"""


def characters_prompt(profile: dict[str, Any], setting: str) -> str:
    return f"""[TASK:CHARACTERS]
请生成主要人物卡。只输出合法 JSON，不要输出 Markdown 代码块。

PROFILE_JSON:
{_json(profile)}

CORE_SETTING:
{setting}

人物卡字段必须包含：姓名、年龄、身份、性格、目标、弱点、秘密、关系网、人物成长线。
请至少生成：主角、反派、2-4 名重要配角。

输出 JSON schema:
{{
  "characters": [
    {{
      "name": "角色姓名",
      "age": "年龄",
      "identity": "身份",
      "personality": "性格",
      "goal": "目标",
      "weakness": "弱点",
      "secret": "秘密",
      "relationships": {{"另一个角色": "关系说明"}},
      "arc": [
        {{"stage": "前期", "change": "变化"}},
        {{"stage": "中期", "change": "变化"}},
        {{"stage": "后期", "change": "变化"}}
      ]
    }}
  ]
}}
"""


def worldbuilding_prompt(profile: dict[str, Any], setting: str, characters: dict[str, Any]) -> str:
    return f"""[TASK:WORLDBUILDING]
请生成世界观设定，输出 Markdown。需要包括：
- 世界基础设定
- 时间线
- 地点
- 势力
- 能力体系或科技体系
- 禁忌、限制和代价
- 重要道具或资源
- 世界观一致性规则

PROFILE_JSON:
{_json(profile)}

CORE_SETTING:
{setting}

CHARACTERS_JSON:
{_json(characters)}
"""


def outline_prompt(
    profile: dict[str, Any],
    setting: str,
    worldbuilding: str,
    characters: dict[str, Any],
) -> str:
    target_words = int(profile.get("words_per_chapter") or 3000)
    return f"""[TASK:OUTLINE]
请生成整本小说完整大纲，输出 Markdown。
每章目标字数：约 {target_words} 字。章节大纲需要匹配这个篇幅，避免单章事件过少或过载。

要求：
1. 先给出三幕或多卷结构。
2. 再逐章列出章节大纲。
3. 每章必须使用二级标题格式：## 第N章 章节标题
4. 每章必须包含：核心事件、冲突点、悬念点、人物变化、伏笔、结尾钩子。
5. 大纲必须遵守角色、世界观和核心冲突。
6. 章节数量必须等于 PROFILE_JSON.chapter_count。

PROFILE_JSON:
{_json(profile)}

CORE_SETTING:
{setting}

WORLDBUILDING:
{worldbuilding}

CHARACTERS_JSON:
{_json(characters)}
"""


def chapter_plan_prompt(
    profile: dict[str, Any],
    outline: str,
    chapter_outline: str,
    memory: dict[str, Any],
    previous_summary: str,
    chapter_number: int,
    reference_analysis: str = "",
) -> str:
    target_words = int(profile.get("words_per_chapter") or 3000)
    return f"""[TASK:CHAPTER_PLAN]
CHAPTER_NUMBER: {chapter_number}
请先为第 {chapter_number} 章生成本章计划。只输出合法 JSON，不要输出 Markdown 代码块。

计划目标：
- 本章正文目标字数约 {target_words} 字。
- 每章必须推进一个新事件，产生新的冲突、线索或反转。
- 不得重复上一章主要场景、开头描写、已发生事件、已发现线索或同一段冲突。
- 不得让角色重新发现已经发现过的信息。
- 不得使用“主角”“{profile.get("genre", "")}故事”等出戏表达。
- 结尾必须有新的钩子。

原创性要求：
- 如有参考分析，只借鉴抽象结构、节奏和技法。
- 不要照搬参考文本，不要复刻角色名、地名、独特设定或具体情节。

PROFILE_JSON:
{_json(profile)}

FULL_OUTLINE:
{outline}

CURRENT_CHAPTER_OUTLINE:
{chapter_outline}

MEMORY_JSON:
{_json(memory)}

PREVIOUS_CHAPTER_SUMMARY:
{previous_summary}

REFERENCE_ANALYSIS:
{reference_analysis}

输出 JSON schema:
{{
  "chapter_goal": "本章目标",
  "new_event": "本章新事件",
  "conflict": "本章冲突",
  "clues": ["新线索"],
  "foreshadowing": ["新伏笔"],
  "ending_hook": "结尾钩子",
  "avoid_repetition": ["本章必须避免重复的内容"]
}}
"""


def chapter_generation_prompt(
    profile: dict[str, Any],
    setting: str,
    worldbuilding: str,
    characters: dict[str, Any],
    outline: str,
    chapter_outline: str,
    memory: dict[str, Any],
    previous_summary: str,
    chapter_number: int,
    chapter_plan: dict[str, Any] | None = None,
    reference_analysis: str = "",
) -> str:
    target_words = int(profile.get("words_per_chapter") or 3000)
    return f"""[TASK:CHAPTER]
CHAPTER_NUMBER: {chapter_number}
请生成第 {chapter_number} 章正文和记忆更新。只输出合法 JSON，不要输出 Markdown 代码块。

硬性要求：
1. 生成章节前必须遵守 memory.json、人物卡、世界观、完整大纲和当前章节大纲。
2. chapter_markdown 字段内部只写小说正文，不要夹杂解释。
3. 正文必须符合用户指定风格：{profile.get("style", "")}
4. 每章必须有冲突、推进、人物变化和结尾钩子。
5. 不要制造与既有记忆冲突的新设定。
6. 如新增伏笔、地点、人物、事件，必须在对应字段登记。
7. 本章正文目标字数约 {target_words} 字，请尽量贴近该篇幅并保持节奏完整。
8. 不得重复上一章主要场景、已发生事件、已发现线索或上一章开头描写。
9. 不得让角色重新发现已经发现过的信息，不得重复同一段冲突。
10. 不得使用“主角”“{profile.get("genre", "")}故事”等出戏表达，要直接使用角色姓名和故事内语言。
11. 每章必须推进一个新事件，产生新的冲突、线索或反转，结尾必须有新的钩子。
12. 参考文本只允许借鉴抽象结构、节奏和技法，不得照搬原文、角色名、地名、独特设定或具体情节。

PROFILE_JSON:
{_json(profile)}

CORE_SETTING:
{setting}

WORLDBUILDING:
{worldbuilding}

CHARACTERS_JSON:
{_json(characters)}

FULL_OUTLINE:
{outline}

CURRENT_CHAPTER_OUTLINE:
{chapter_outline}

MEMORY_JSON:
{_json(memory)}

PREVIOUS_CHAPTER_SUMMARY:
{previous_summary}

CHAPTER_PLAN_JSON:
{_json(chapter_plan or {})}

REFERENCE_ANALYSIS:
{reference_analysis}

输出 JSON schema:
{{
  "chapter_title": "章节标题",
  "chapter_markdown": "# 第{chapter_number}章 章节标题\\n\\n小说正文",
  "summary": "本章摘要",
  "new_characters": [],
  "new_locations": [],
  "new_foreshadowing": [],
  "resolved_foreshadowing": [],
  "relationship_changes": [],
  "world_updates": {{"rules": [], "timeline": [], "locations": [], "factions": [], "systems": [], "taboos": []}},
  "events": [],
  "discovered_clues": [],
  "current_plot_position": "当前剧情进度",
  "forbidden_repetition_notes": [],
  "quality_notes": []
}}
"""


def reference_analysis_prompt(profile: dict[str, Any], reference_text: str, reference_note: str) -> str:
    return f"""[TASK:REFERENCE_ANALYSIS]
请分析用户提供的参考文本，输出 Markdown 报告。

版权与原创性要求：
- 用户只能上传自己有权使用的文本、公版文本，或用于合法分析的片段。
- 不要复制、洗稿或照搬受版权保护作品。
- 只提取结构、节奏、人物关系、主题和写作技巧。
- 后续输出必须是原创内容。
- 不要复刻角色名、地名、独特设定、具体情节或原文句子。

PROFILE_JSON:
{_json(profile)}

REFERENCE_NOTE:
{reference_note}

REFERENCE_TEXT:
{reference_text[:12000]}

报告必须包含：
- 题材类型
- 叙事节奏
- 章节结构
- 人物关系模式
- 冲突设计
- 悬念设计
- 爽点/钩子
- 可借鉴方向
- 必须避免直接复制的元素
"""


def memory_update_prompt(
    profile: dict[str, Any],
    chapter_number: int,
    chapter_text: str,
    memory: dict[str, Any],
) -> str:
    return f"""[TASK:MEMORY_UPDATE]
请根据章节正文提取 memory.json 更新。只输出合法 JSON，不要输出 Markdown 代码块。

PROFILE_JSON:
{_json(profile)}

CHAPTER_NUMBER: {chapter_number}

CURRENT_MEMORY_JSON:
{_json(memory)}

CHAPTER_TEXT:
{chapter_text}

输出 JSON schema 与章节生成的记忆字段一致：
{{
  "summary": "本章摘要",
  "new_characters": [],
  "new_locations": [],
  "new_foreshadowing": [],
  "resolved_foreshadowing": [],
  "relationship_changes": [],
  "world_updates": {{"rules": [], "timeline": [], "locations": [], "factions": [], "systems": [], "taboos": []}},
  "events": [],
  "quality_notes": []
}}
"""


def quality_check_prompt(
    profile: dict[str, Any],
    chapter_number: int,
    chapter_outline: str,
    chapter_text: str,
    memory: dict[str, Any],
) -> str:
    return f"""[TASK:QUALITY_CHECK]
请检查第 {chapter_number} 章质量。只输出合法 JSON，不要输出 Markdown 代码块。

检查项：
- 是否偏离大纲
- 是否人物性格不一致
- 是否世界观矛盾
- 是否存在未解释突变
- 是否章节缺少冲突
- 是否结尾缺少钩子
- 是否语言重复
- 是否符合用户指定风格

PROFILE_JSON:
{_json(profile)}

CHAPTER_OUTLINE:
{chapter_outline}

MEMORY_JSON:
{_json(memory)}

CHAPTER_TEXT:
{chapter_text}

输出 JSON schema:
{{
  "outline_deviation": false,
  "character_inconsistency": false,
  "worldbuilding_conflict": false,
  "unexplained_jump": false,
  "missing_conflict": false,
  "missing_hook": false,
  "repetitive_language": false,
  "style_mismatch": false,
  "suggestions": ["修改建议"]
}}
"""


def continue_chapter_prompt(
    profile: dict[str, Any],
    chapter_number: int,
    chapter_text: str,
    memory: dict[str, Any],
) -> str:
    return f"""[TASK:CONTINUE_CHAPTER]
请续写第 {chapter_number} 章。只输出合法 JSON，不要输出 Markdown 代码块。
续写内容必须接在原文之后，保持语气、人物、冲突和世界观一致。

PROFILE_JSON:
{_json(profile)}

MEMORY_JSON:
{_json(memory)}

EXISTING_CHAPTER:
{chapter_text}

输出 JSON schema:
{{
  "appended_markdown": "续写正文，不要重复原文",
  "summary": "续写后的本章摘要",
  "new_characters": [],
  "new_locations": [],
  "new_foreshadowing": [],
  "resolved_foreshadowing": [],
  "relationship_changes": [],
  "world_updates": {{"rules": [], "timeline": [], "locations": [], "factions": [], "systems": [], "taboos": []}},
  "events": [],
  "quality_notes": []
}}
"""


def rewrite_chapter_prompt(
    profile: dict[str, Any],
    chapter_number: int,
    chapter_text: str,
    instruction: str,
    memory: dict[str, Any],
) -> str:
    return f"""[TASK:REWRITE_CHAPTER]
请重写第 {chapter_number} 章。只输出合法 JSON，不要输出 Markdown 代码块。
必须保留大纲方向和已确认事实，并按照用户要求改写：{instruction}

PROFILE_JSON:
{_json(profile)}

MEMORY_JSON:
{_json(memory)}

ORIGINAL_CHAPTER:
{chapter_text}

输出 JSON schema:
{{
  "chapter_markdown": "# 第{chapter_number}章 标题\\n\\n重写后的小说正文",
  "summary": "本章摘要",
  "new_characters": [],
  "new_locations": [],
  "new_foreshadowing": [],
  "resolved_foreshadowing": [],
  "relationship_changes": [],
  "world_updates": {{"rules": [], "timeline": [], "locations": [], "factions": [], "systems": [], "taboos": []}},
  "events": [],
  "quality_notes": []
}}
"""


def polish_chapter_prompt(
    profile: dict[str, Any],
    chapter_number: int,
    chapter_text: str,
    instruction: str,
) -> str:
    return f"""[TASK:POLISH_CHAPTER]
请润色第 {chapter_number} 章。只输出润色后的 Markdown 正文，不要输出解释。
润色要求：{instruction}
必须保持原剧情事实、人物关系和伏笔不变。

PROFILE_JSON:
{_json(profile)}

ORIGINAL_CHAPTER:
{chapter_text}
"""
