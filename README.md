# NovelWriter Agent

NovelWriter Agent 是一个本地可运行的小说创作智能体，支持 CLI 和 Web 两种使用方式。它可以根据题材、读者、世界观、主角设定、章节数量、每章目标字数和写作风格，自动生成小说设定、人物卡、世界观、大纲，并按章节持续写作和维护长篇记忆。

项目支持 Mock 模式和真实模型模式。Mock 模式不需要 API Key，适合测试流程；真实模型模式会调用 OpenAI 或 OpenAI 兼容接口生成内容。

## 功能列表

- 创建和管理多个小说项目，所有项目保存在 `novels/`
- 生成核心设定、人物卡、世界观、完整大纲和章节正文
- 每章保存为独立 Markdown 文件，并可导出整本小说
- 使用 `memory.json` 记录章节摘要、已发生事件、线索、伏笔、人物变化和剧情进度
- 生成章节前读取设定、人物、世界观、大纲、记忆、上一章摘要和参考分析
- 章节生成前先生成“本章计划”，再写正文
- 检查章节是否重复、是否偏离大纲、是否缺少冲突或钩子
- Web 页面支持创建项目、生成内容、生成下一章、编辑、删除、重写、续写章节
- 支持“参考文本 / 改编辅助”，只学习结构、节奏和技法，不复制原文
- CLI 功能保留，可继续通过 `main.py` 使用

## 项目结构

```text
novelwriter-agent/
README.md
requirements.txt
.env.example
main.py
novelwriter/
  __init__.py
  agent.py
  config.py
  llm.py
  memory.py
  models.py
  prompts.py
  quality.py
  storage.py
  web.py
scripts/
  smoke_test.py
  run_web.py
  smoke.ps1
  smoke.sh
  codex_setup.sh
web/
  index.html
  styles.css
  app.js
novels/
  .gitkeep
examples/
  sample_project.md
```

## 安装

进入项目目录：

```powershell
cd E:\codex-work\codex-book\novelwriter-agent
```

创建虚拟环境并安装依赖：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

如果当前环境没有 `python` 命令，可以使用 Codex 内置 Python：

```powershell
C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe scripts\smoke_test.py
```

## 环境变量

复制示例配置：

```powershell
Copy-Item .env.example .env
```

Mock 模式，不需要 API Key：

```env
NOVELWRITER_MOCK=true
OPENAI_API_KEY=
OPENAI_BASE_URL=
OPENAI_MODEL=gpt-4o-mini
NOVELWRITER_TEMPERATURE=0.8
NOVELWRITER_MAX_TOKENS=4096
```

真实模型模式：

```env
NOVELWRITER_MOCK=false
OPENAI_API_KEY=你的 API Key
OPENAI_BASE_URL=
OPENAI_MODEL=gpt-4o-mini
NOVELWRITER_TEMPERATURE=0.8
NOVELWRITER_MAX_TOKENS=4096
```

如果使用本地或第三方 OpenAI 兼容接口，可以设置：

```env
OPENAI_BASE_URL=http://localhost:11434/v1
OPENAI_MODEL=你的模型名
```

安全说明：

- `.env` 已被 `.gitignore` 忽略，不要提交真实 API Key
- `.env.example` 可以提交，只保留空值或示例值
- API Key 只保存在后端环境变量中，不会写入前端、README、日志或接口返回
- `/api/health` 只返回 `api_key_configured: true/false`，不会返回密钥内容

## 启动 Web

```powershell
python scripts/run_web.py
```

打开：

```text
http://127.0.0.1:8000
```

健康检查：

```text
http://127.0.0.1:8000/api/health
```

如果返回 `mock=true`，表示当前是 Mock 模式；如果返回 `mock=false`，表示真实模型模式。页面顶部也会显示 Mock 模式或真实模型模式。真实模型模式下如果没有配置 API Key，页面可以打开，但生成真实内容时会提示需要配置密钥。

停止 Web 服务：在运行服务的终端按 `Ctrl+C`。

## Web 使用顺序

推荐按下面顺序使用：

1. 创建项目：填写标题、题材、主角、风格、章节数量和每章目标字数
2. 生成设定
3. 生成人物
4. 生成世界观
5. 生成大纲
6. 生成第一章
7. 点击“生成下一章”持续写作
8. 在章节列表中选择章节，直接编辑正文
9. 使用“保存修改”“删除章节”“重写章节”“续写章节”
10. 导出整本小说 Markdown

也可以点击“一键初始化”，系统会按顺序生成：设定、人物、世界观、大纲、第一章。中途任何一步失败都会停止并显示错误。

每章目标字数默认是 `3000`，可以在创建项目表单中改为 `1000`、`2000`、`5000` 等数字。该值会传给后端，并写入设定、大纲和章节生成 prompt，让模型尽量贴近目标字数。模型输出字数可能不会完全精确，这是大语言模型的正常限制。

## 章节编辑、删除、重写和续写

Web 页面会列出当前项目已生成的章节。点击章节后，正文会出现在可编辑区域。

- 保存修改：写回对应 Markdown 文件，并更新 `memory.json` 中的章节摘要
- 删除章节：删除对应 Markdown 文件，并从 `memory.json` 中移除该章摘要
- 重写章节：根据当前章节大纲、记忆和你的修改要求重新生成，并覆盖原文
- 续写章节：在现有正文末尾继续生成，不覆盖原文

生成章节前，后端会检查设定、人物、世界观和大纲是否存在。如果前置资料缺失，Web 会提示先补齐。

## 如何避免章节重复

系统已经做了几层处理：

- `memory.json` 记录 `occurred_events`、`discovered_clues`、`unresolved_hooks`、`resolved_hooks` 和 `current_plot_position`
- 每章生成前读取最近章节摘要、上一章摘要、已发生事件、已发现线索和伏笔状态
- prompt 明确要求不得重复上一章主要场景、开头描写、已发生事件和已发现信息
- 每章先生成计划，要求包含新事件、新冲突、新线索、新伏笔和结尾钩子
- `quality.py` 会对比最近 3 章，检查重复开头、重复场景、重复事件和重复线索
- 如果发现明显重复，Agent 会尝试要求模型重写一次

如果仍然重复，通常是因为大纲过于空泛、章节目标不清晰、模型上下文不足或 Mock 模式输出固定。建议先修改大纲，让每章有清楚的新事件和新冲突。

## 参考文本 / 改编辅助

Web 页面提供“参考文本 / 改编辅助”区域，可以粘贴参考文本并填写参考说明，例如“想参考节奏、人物关系、世界观复杂度、悬疑结构”。

版权安全要求：

- 只能上传自己有权使用的文本、公版文本，或用于合法分析的片段
- 不要要求系统直接复制、洗稿或照搬受版权保护作品
- 系统只提取结构、节奏、人物关系、主题和写作技巧
- 生成内容必须是原创内容
- prompt 会要求不要复刻角色名、地名、独特设定、具体情节或原文句子

后端会把参考文本保存到项目的 `references/` 目录，并生成 `reference_analysis.md`。后续生成小说时会参考分析报告，但不会复用原文。

## CLI 使用

查看命令：

```powershell
python main.py --help
```

创建新项目：

```powershell
python main.py new
```

生成前置内容：

```powershell
python main.py setting
python main.py characters
python main.py world
python main.py outline
```

生成章节：

```powershell
python main.py chapter 1
python main.py next
```

续写、重写、润色：

```powershell
python main.py continue 1
python main.py rewrite 1 --instruction "增强冲突，减少解释"
python main.py polish 1 --instruction "提升画面感和对白自然度"
```

检查与导出：

```powershell
python main.py check 1
python main.py export
```

## Smoke Test

运行离线 smoke test：

```powershell
python scripts/smoke_test.py
```

它会在临时目录中使用 Mock 模式创建项目、生成设定、人物、世界观、大纲、参考分析、章节、下一章，检查记忆更新、质量检查、导出、Web 文件、后端路由、prompt 标记和 `.env` 忽略规则。

成功时会输出：

```text
[smoke] OK
```

## Codex Cloud / Codex Web

把仓库推送到 GitHub 后，可以在 Codex Web 里连接这个仓库。推荐流程：

1. 打开 Codex Web 并连接 GitHub 账号
2. 授权访问 `w13865927999-stack/novelwriter-agent`
3. 创建环境并选择该仓库
4. 如需要 setup script，使用：

```bash
bash scripts/codex_setup.sh
```

之后可以直接在 Codex 中要求修改、运行测试、提交和推送。例如：

- “给 Web 页面增加章节版本历史”
- “把记忆系统改成 SQLite”
- “新增 EPUB 导出，并运行 smoke test”

## 常见问题

为什么显示 Mock 模式？

检查 `.env` 中是否是 `NOVELWRITER_MOCK=true`。如果要使用真实模型，请改成 `NOVELWRITER_MOCK=false` 并配置 `OPENAI_API_KEY`。

为什么不能生成真实内容？

真实模型模式需要有效 API Key、正确模型名和可访问的 `OPENAI_BASE_URL`。如果没有配置密钥，后端会给出清晰错误。

为什么章节重复？

可能是大纲太泛、上一章记忆不足、章节目标太相似，或正在使用 Mock 模式。可以先补充章节大纲的新事件、新线索和结尾钩子，再重写章节。

为什么字数不完全准确？

每章目标字数会写入 prompt，但模型输出不是严格计数器。建议把目标设为略高于实际需要，生成后再扩写或压缩。

`.env` 会不会上传？

不会。`.env` 已被 `.gitignore` 忽略，smoke test 也会检查这一点。提交前仍建议运行：

```bash
git check-ignore -v .env
git status --short
```
