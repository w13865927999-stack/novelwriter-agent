"""LLM abstraction with OpenAI-compatible and mock backends."""

from __future__ import annotations

import json
import re
from typing import Any

from .config import AppConfig
from .prompts import SYSTEM_PROMPT


class LLMClient:
    def __init__(self, config: AppConfig):
        self.config = config
        self._client = None

    def generate(self, prompt: str, system_prompt: str = SYSTEM_PROMPT, temperature: float | None = None) -> str:
        if self.config.mock:
            return self._mock_generate(prompt)
        if not self.config.openai_api_key:
            raise RuntimeError("真实模型模式需要 OPENAI_API_KEY。请在本地 .env 或云端 secrets 中配置，不要提交密钥。")

        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("请先安装 openai：pip install -r requirements.txt") from exc

        if self._client is None:
            kwargs: dict[str, Any] = {"api_key": self.config.openai_api_key}
            if self.config.openai_base_url:
                kwargs["base_url"] = self.config.openai_base_url
            self._client = OpenAI(**kwargs)

        response = self._client.chat.completions.create(
            model=self.config.openai_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=self.config.temperature if temperature is None else temperature,
            max_tokens=self.config.max_tokens,
        )
        return response.choices[0].message.content or ""

    def _mock_generate(self, prompt: str) -> str:
        profile = self._extract_json_block(prompt, "PROFILE_JSON") or {}
        title = profile.get("title", "未命名小说")
        genre = profile.get("genre", "幻想")
        protagonist = self._short_name(profile.get("protagonist", "主角"))
        style = profile.get("style", "节奏明快")

        if "[TASK:CORE_SETTING]" in prompt:
            return json.dumps(
                {
                    "logline": f"{protagonist}在{genre}世界中追查一桩改变命运的秘密，却发现自己正是谜局的钥匙。",
                    "synopsis": (
                        f"《{title}》讲述{protagonist}被卷入一场横跨个人命运与世界秩序的危机。"
                        f"表面目标是解决眼前的失控事件，真正的矛盾却来自旧规则与新选择的碰撞。"
                        "随着线索推进，主角不断付出代价，也逐渐看清身边人的秘密、敌人的动机，以及世界运行的隐性规则。"
                    ),
                    "core_conflict": "主角想守住自我选择，旧秩序却要求所有人按既定命运付出代价。",
                    "main_plot": "主角从被动卷入事件，到主动追查真相，最终直面操控世界规则的核心势力。",
                    "subplots": [
                        "主角与关键同伴从互不信任到并肩承担代价。",
                        "反派用看似合理的秩序诱惑主角放弃自由选择。",
                        "隐藏道具或技术体系逐步揭开旧灾难的真相。",
                    ],
                    "selling_points": ["强钩子开局", "持续反转", "人物成长和世界谜团同步推进"],
                    "release_copy": f"当{genre}的规则开始崩塌，{protagonist}必须在真相和代价之间做出选择。",
                },
                ensure_ascii=False,
                indent=2,
            )

        if "[TASK:CHARACTERS]" in prompt:
            return json.dumps(
                {
                    "characters": [
                        {
                            "name": protagonist,
                            "age": "24",
                            "identity": "被卷入核心谜团的行动者",
                            "personality": "敏锐、克制、重承诺，但在压力下容易独自承担风险",
                            "goal": "找出改变命运的真相，并保护重要的人",
                            "weakness": "害怕自己的选择伤害他人",
                            "secret": "与旧灾难或核心规则存在未知关联",
                            "relationships": {"沈砚": "互相试探的同盟", "陆执": "理念相反的宿敌"},
                            "arc": [
                                {"stage": "前期", "change": "从被动自保到愿意追问真相"},
                                {"stage": "中期", "change": "学会承担代价并信任同伴"},
                                {"stage": "后期", "change": "以自己的选择改写规则"},
                            ],
                        },
                        {
                            "name": "沈砚",
                            "age": "27",
                            "identity": "掌握关键情报的调查者",
                            "personality": "冷静、毒舌、谨慎，内心有强烈责任感",
                            "goal": "阻止旧势力重启禁忌计划",
                            "weakness": "不愿解释自己的过去",
                            "secret": "曾是反派阵营的一员",
                            "relationships": {protagonist: "危险但必要的同盟"},
                            "arc": [{"stage": "全书", "change": "从隐瞒真相到主动交付信任"}],
                        },
                        {
                            "name": "陆执",
                            "age": "32",
                            "identity": "维护旧秩序的反派",
                            "personality": "温和、理性、控制欲强，习惯用大局压过个体",
                            "goal": "恢复他认为唯一稳定的世界规则",
                            "weakness": "无法承认自己的牺牲逻辑已经伤害无辜者",
                            "secret": "他曾亲眼见过规则失控造成的灾难",
                            "relationships": {protagonist: "想招揽也想摧毁的变数"},
                            "arc": [{"stage": "后期", "change": "理念被主角动摇，但仍选择极端方案"}],
                        },
                        {
                            "name": "乔梨",
                            "age": "21",
                            "identity": "提供情绪支点与民间线索的配角",
                            "personality": "外向、机灵、怕疼但不退缩",
                            "goal": "救出失踪的家人",
                            "weakness": "容易相信愿意给她希望的人",
                            "secret": "她家人保存着一份旧名单",
                            "relationships": {protagonist: "把主角当成最后的可信之人"},
                            "arc": [{"stage": "中期", "change": "从求助者成长为主动传递线索的人"}],
                        },
                    ]
                },
                ensure_ascii=False,
                indent=2,
            )

        if "[TASK:WORLDBUILDING]" in prompt:
            return (
                f"# {title} 世界观\n\n"
                "## 世界基础设定\n"
                f"这是一个带有{genre}气质的故事世界，普通生活表层之下存在一套被少数人掌握的隐性规则。\n\n"
                "## 时间线\n"
                "- 十年前：旧灾难发生，核心规则被封存。\n"
                "- 故事开始：异常事件重新出现，主角被卷入调查。\n"
                "- 中后期：各方势力争夺重启或改写规则的钥匙。\n\n"
                "## 地点\n"
                "- 雾港：故事开局城市，潮湿、拥挤、线索密集。\n"
                "- 第七码头：旧势力交易地点。\n"
                "- 白塔档案馆：保存旧灾难档案的禁区。\n\n"
                "## 势力\n"
                "- 白塔理事会：维护旧秩序的组织。\n"
                "- 灰线调查组：游离在制度边缘的调查者。\n"
                "- 黑市信使：贩卖情报和禁忌道具的松散网络。\n\n"
                "## 能力体系或科技体系\n"
                "- 核心规则需要媒介触发，使用者必须付出记忆、寿命或关系代价。\n"
                "- 任何改写现实的行为都会留下可追踪的回响。\n\n"
                "## 禁忌、限制和代价\n"
                "- 不能无代价复活死者。\n"
                "- 不能同时改写两条互相矛盾的事实。\n"
                "- 代价必须落在使用者最珍视的事物上。\n\n"
                "## 重要道具或资源\n"
                "- 黑匣钥匙：能打开旧灾难档案。\n"
                "- 回响罗盘：能追踪被改写事实留下的痕迹。\n\n"
                "## 世界观一致性规则\n"
                "- 新能力必须遵守代价原则。\n"
                "- 新势力必须与既有势力存在利益关系。\n"
                "- 所有重大反转必须能回溯到前文伏笔。\n"
            )

        if "[TASK:OUTLINE]" in prompt:
            count = int(profile.get("chapter_count") or 6)
            lines = [
                f"# {title} 完整大纲",
                "",
                "## 整体结构",
                "- 第一幕：异常出现，主角被迫入局。",
                "- 第二幕：线索扩张，人物秘密与世界代价显形。",
                "- 第三幕：真相逼近，主角必须做出不可逆选择。",
                "",
            ]
            for number in range(1, count + 1):
                lines.extend(
                    [
                        f"## 第{number}章 第{number}个回响",
                        f"- 核心事件：{protagonist}追查第{number}条异常线索，发现它与旧灾难有关。",
                        "- 冲突点：主角想保护无辜者，白塔理事会试图封锁现场。",
                        "- 悬念点：线索指向一个不该存在的名字。",
                        "- 人物变化：主角从怀疑旁观转向主动承担。",
                        f"- 伏笔：黑匣钥匙第{number}次出现异常回响。",
                        "- 结尾钩子：有人在暗处说出了主角不曾告诉任何人的秘密。",
                        "",
                    ]
                )
            return "\n".join(lines)

        if "[TASK:CHAPTER]" in prompt:
            chapter_number = self._extract_chapter_number(prompt)
            return self._mock_chapter_json(title, genre, protagonist, style, chapter_number)

        if "[TASK:CHAPTER_PLAN]" in prompt:
            chapter_number = self._extract_chapter_number(prompt)
            return json.dumps(
                {
                    "chapter_goal": f"推进第{chapter_number}条新线索，让{protagonist}离核心真相更近一步。",
                    "new_event": f"{protagonist}离开旧场景，进入第{chapter_number}个关键地点调查新异常。",
                    "conflict": "同伴隐瞒真相与外部势力阻拦同时升级。",
                    "clues": [f"第{chapter_number}章新增线索，不重复已发现信息"],
                    "foreshadowing": [f"第{chapter_number}章新伏笔"],
                    "ending_hook": f"结尾出现一个与第{chapter_number + 1}章直接相连的新钩子。",
                    "avoid_repetition": ["不回到第七码头重复发现徽章", "不重复生日刻痕", "不重复同一段白塔封锁冲突"],
                },
                ensure_ascii=False,
                indent=2,
            )

        if "[TASK:REFERENCE_ANALYSIS]" in prompt:
            return (
                "# 参考文本分析报告\n\n"
                "## 版权与原创性边界\n"
                "- 只借鉴抽象结构、节奏和技法，不复制原文、角色名、地名、独特设定或具体桥段。\n\n"
                "## 题材类型\n- 待用户提供更完整文本后细化。\n\n"
                "## 叙事节奏\n- 以问题推进场景，以钩子结束章节。\n\n"
                "## 章节结构\n- 开场抛出异常，中段升级冲突，结尾留下新问题。\n\n"
                "## 人物关系模式\n- 让信任、隐瞒和利益交换推动关系变化。\n\n"
                "## 冲突设计\n- 外部阻碍与内部选择同时出现。\n\n"
                "## 悬念设计\n- 线索逐步递进，不让角色重复发现同一信息。\n\n"
                "## 爽点/钩子\n- 每章至少出现一个新发现、反转或危险承诺。\n\n"
                "## 可借鉴方向\n- 借鉴节奏层级和冲突密度。\n\n"
                "## 必须避免直接复制的元素\n- 原文句子、专有名词、角色关系、独特设定和具体情节均不可复用。\n"
            )

        if "[TASK:CONTINUE_CHAPTER]" in prompt:
            chapter_number = self._extract_chapter_number(prompt)
            return json.dumps(
                {
                    "appended_markdown": (
                        "雨声压低了整座城市的呼吸。\n\n"
                        f"{protagonist}没有立刻回答。那枚钥匙在掌心发烫，像一段尚未说出口的证词。"
                        "沈砚望向走廊尽头，那里有脚步声停了一瞬，又极轻地退回黑暗里。\n\n"
                        "他们都明白，真正的追踪从这一刻才开始。"
                    ),
                    "summary": f"第{chapter_number}章续写：主角确认新线索，暗处追踪者出现。",
                    "new_characters": [],
                    "new_locations": [],
                    "new_foreshadowing": [{"description": "走廊尽头的神秘脚步声"}],
                    "resolved_foreshadowing": [],
                    "relationship_changes": [],
                    "world_updates": {"rules": [], "timeline": [], "locations": [], "factions": [], "systems": [], "taboos": []},
                    "events": [{"chapter": chapter_number, "event": "暗处追踪者首次显露踪迹"}],
                    "quality_notes": [],
                },
                ensure_ascii=False,
                indent=2,
            )

        if "[TASK:REWRITE_CHAPTER]" in prompt:
            chapter_number = self._extract_chapter_number(prompt)
            return self._mock_chapter_json(title, genre, protagonist, style, chapter_number, rewritten=True)

        if "[TASK:POLISH_CHAPTER]" in prompt:
            original = prompt.split("ORIGINAL_CHAPTER:", 1)[-1].strip()
            return original + "\n\n> 润色标记：mock 模式保留原剧情，仅示意润色流程已执行。\n"

        if "[TASK:MEMORY_UPDATE]" in prompt:
            chapter_number = self._extract_chapter_number(prompt)
            return json.dumps(
                {
                    "summary": f"第{chapter_number}章发生关键推进，主角获得新线索并承受新的压力。",
                    "new_characters": [],
                    "new_locations": [],
                    "new_foreshadowing": [{"description": f"第{chapter_number}章留下的未解线索"}],
                    "resolved_foreshadowing": [],
                    "relationship_changes": [],
                    "world_updates": {"rules": [], "timeline": [], "locations": [], "factions": [], "systems": [], "taboos": []},
                    "events": [{"chapter": chapter_number, "event": "章节事件已记录"}],
                    "quality_notes": [],
                },
                ensure_ascii=False,
                indent=2,
            )

        if "[TASK:QUALITY_CHECK]" in prompt:
            return json.dumps(
                {
                    "outline_deviation": False,
                    "character_inconsistency": False,
                    "worldbuilding_conflict": False,
                    "unexplained_jump": False,
                    "missing_conflict": False,
                    "missing_hook": False,
                    "repetitive_language": False,
                    "style_mismatch": False,
                    "suggestions": ["mock 质检未发现明显问题；接入真实模型后会给出更细的文本建议。"],
                },
                ensure_ascii=False,
                indent=2,
            )

        return "mock response"

    def _mock_chapter_json(
        self,
        title: str,
        genre: str,
        protagonist: str,
        style: str,
        chapter_number: int,
        rewritten: bool = False,
    ) -> str:
        chapter_title = f"第{chapter_number}个回响"
        prefix = "重写版：" if rewritten else ""
        body = (
            f"# 第{chapter_number}章 {chapter_title}\n\n"
            f"{prefix}{protagonist}没有再回第七码头。\n\n"
            f"第{chapter_number}天清晨，回响罗盘把他带到雾港高架下的旧电车站。站台早已停运，"
            "广告屏却在无人供电的情况下亮着一行白字：名单正在改写。\n\n"
            "沈砚拦住他，第一次没有用讥讽掩饰紧张：“这不是旧线索的残影，是有人刚刚动过手。”\n\n"
            f"{protagonist}打开黑匣钥匙，钥匙没有发热，而是渗出一段陌生的儿童歌声。"
            "歌声指向站台尽头的储物柜，柜门里没有尸体，没有徽章，只有一张被剪去半边的车票。\n\n"
            f"车票背面写着新的地点：第{chapter_number}环记忆中转站。"
            "白塔的人随后赶到，这次他们不是封锁现场，而是直接宣布沈砚为叛逃者。\n\n"
            f"{protagonist}必须在带走车票和救下沈砚之间做选择。乔梨从通讯器里喊他别犹豫，"
            "因为黑市刚刚放出消息：名单上的第二个人还活着，而且正在找他。\n\n"
            "他撕下车票编号，把原票塞进沈砚掌心，转身冲进检修通道。身后的广播忽然恢复，"
            f"用一个陌生孩子的声音播报：“第{chapter_number}次回响开始，下一站，旧城事故现场。”"
        )
        return json.dumps(
            {
                "chapter_title": chapter_title,
                "chapter_markdown": body,
                "summary": f"第{chapter_number}章：{protagonist}在旧电车站获得新车票线索，白塔宣布沈砚为叛逃者，名单第二人仍然活着。",
                "new_characters": [
                    {
                        "name": "乔梨",
                        "identity": "黑市信使",
                        "personality": "机灵但紧张",
                        "goal": "用名单换取家人下落",
                    }
                ]
                if chapter_number == 1
                else [],
                "new_locations": [{"name": "第七码头", "description": "旧势力交易与异常事件发生地"}]
                if chapter_number == 1
                else [],
                "new_foreshadowing": [
                    {"id": f"ticket-{chapter_number}", "description": f"第{chapter_number}章出现指向记忆中转站的半张车票"},
                    {"id": f"second-person-{chapter_number}", "description": "名单上的第二个人仍然活着并正在寻找主角"},
                ],
                "resolved_foreshadowing": [],
                "relationship_changes": [
                    {"characters": [protagonist, "沈砚"], "change": "从互相试探转向有限合作"}
                ],
                "world_updates": {
                    "rules": ["白塔会封锁与旧灾难相关的异常现场"],
                    "timeline": [{"chapter": chapter_number, "event": "第七码头异常事件被主角发现"}],
                    "locations": [{"name": "第七码头", "description": "雾港货运区，异常回响密集"}],
                    "factions": [],
                    "systems": ["黑匣钥匙会对旧灾难痕迹产生热感回响"],
                    "taboos": [],
                },
                "events": [
                    {"chapter": chapter_number, "event": "主角在旧电车站发现新的车票线索"},
                    {"chapter": chapter_number, "event": "白塔宣布沈砚为叛逃者"},
                ],
                "discovered_clues": [
                    {"chapter": chapter_number, "clue": f"第{chapter_number}环记忆中转站"},
                    {"chapter": chapter_number, "clue": "名单第二人仍然活着"},
                ],
                "current_plot_position": f"第{chapter_number}章结束：调查从码头旧案推进到记忆中转站与名单第二人。",
                "forbidden_repetition_notes": ["不要再重复第七码头、白塔徽章、生日刻痕、死人名单初次出现。"],
                "quality_notes": [],
            },
            ensure_ascii=False,
            indent=2,
        )

    @staticmethod
    def _extract_chapter_number(prompt: str) -> int:
        match = re.search(r"CHAPTER_NUMBER:\s*(\d+)", prompt)
        return int(match.group(1)) if match else 1

    @staticmethod
    def _short_name(value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            return "主角"
        for separator in ("：", ":", "，", ",", " ", "、"):
            if separator in text:
                parts = [part.strip() for part in text.split(separator) if part.strip()]
                if parts:
                    text = parts[0]
                    break
        chinese = re.sub(r"[^\u4e00-\u9fff]", "", text)
        if 2 <= len(chinese) <= 4:
            return chinese
        if len(chinese) > 4:
            return chinese[-2:]
        return text

    @staticmethod
    def _extract_json_block(prompt: str, name: str) -> dict[str, Any] | None:
        marker = f"{name}:"
        if marker not in prompt:
            return None
        start = prompt.find(marker) + len(marker)
        rest = prompt[start:].lstrip()
        if not rest.startswith("{"):
            return None
        depth = 0
        for index, char in enumerate(rest):
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(rest[: index + 1])
                    except json.JSONDecodeError:
                        return None
        return None
