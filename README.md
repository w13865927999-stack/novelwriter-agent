# NovelWriter Agent

NovelWriter Agent 是一个本地可运行的自动写小说智能体项目。它可以根据小说类型、目标读者、世界观、主角设定、目标字数、章节数量和写作风格，自动生成核心设定、人物卡、世界观、大纲，并按章节连续创作正文。

项目默认支持 mock 模式：即使没有 API Key，也能先跑通项目结构、CLI 流程、文件保存、记忆更新和导出。

## 功能列表

- 创建新小说项目，并单独保存到 `novels/` 目录
- 自动生成一句话卖点、故事简介、核心冲突、主线和支线
- 生成人物卡，保存到 `characters.json`
- 生成世界观设定，保存到 `worldbuilding.md`
- 生成完整大纲，保存到 `outline.md`
- 按章节生成小说正文，每章保存为独立 Markdown 文件
- 使用 `memory.json` 记录人物、世界观、事件、章节摘要和伏笔
- 支持续写、重写、润色、更新记忆、质量检查
- 导出整本小说为一个 Markdown 文件
- 提供 FastAPI Web 页面，可创建项目、生成设定/人物/世界观/大纲/第一章、继续生成下一章、查看章节和导出 Markdown
- LLM 调用层可替换，支持 OpenAI API、本地模型和其他 OpenAI 兼容服务

## 项目结构

```text
novelwriter-agent/
AGENTS.md
README.md
requirements.txt
.env.example
main.py
.github/
  workflows/
    smoke.yml
novelwriter/
  __init__.py
  agent.py
  prompts.py
  memory.py
  storage.py
  models.py
  config.py
  quality.py
  llm.py
scripts/
  smoke_test.py
  smoke.ps1
  smoke.sh
  run_web.py
  codex_setup.sh
web/
  index.html
  styles.css
  app.js
novels/
  .gitkeep
  sample-cyber-mystery/
    metadata.json
    memory.json
    characters.json
    worldbuilding.md
    outline.md
    chapters/
      chapter_001.md
      chapter_002.md
    logs/
examples/
  sample_project.md
```

## 安装步骤

进入项目目录：

```powershell
cd E:\codex-work\codex-book\novelwriter-agent
```

创建并激活虚拟环境：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

安装依赖：

```powershell
pip install -r requirements.txt
```

## Smoke Test

项目提供一个离线 smoke test。它会强制使用 mock 模式，在临时目录创建小说项目，依次验证项目创建、设定生成、人物卡、世界观、大纲、章节生成、记忆更新、质检和导出。

Windows PowerShell：

```powershell
.\scripts\smoke.ps1
```

macOS/Linux/Codex Cloud：

```bash
bash scripts/smoke.sh
```

也可以直接运行：

```bash
python scripts/smoke_test.py
```

GitHub Actions 会在 `push` 和 `pull_request` 时自动运行同一个 smoke test。

## 环境变量配置

复制环境变量示例：

```powershell
Copy-Item .env.example .env
```

没有 API Key 时保持：

```env
NOVELWRITER_MOCK=true
OPENAI_API_KEY=
```

使用 OpenAI 或 OpenAI 兼容接口时：

```env
NOVELWRITER_MOCK=false
OPENAI_API_KEY=你的 API Key
OPENAI_BASE_URL=
OPENAI_MODEL=gpt-4o-mini
```

安全规则：

- `.env` 已加入 `.gitignore`，不要上传真实 API Key。
- `.env.example` 可以安全上传，只保留空值和示例值。
- 在 Codex Cloud 或 GitHub Actions 中使用真实模型时，请通过平台的 secrets/environment variables 配置密钥。

使用本地 OpenAI 兼容服务时，例如：

```env
NOVELWRITER_MOCK=false
OPENAI_API_KEY=local-key
OPENAI_BASE_URL=http://localhost:11434/v1
OPENAI_MODEL=qwen2.5:7b
```

## 如何启动

查看命令帮助：

```powershell
python main.py --help
```

查看已有项目：

```powershell
python main.py list
```

选择示例项目：

```powershell
python main.py select sample-cyber-mystery
```

## Web 版本

启动 FastAPI Web 应用：

```powershell
python scripts/run_web.py
```

如果当前环境没有 `python` 命令，请使用可用解释器运行同一个脚本，例如：

```powershell
C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe scripts\run_web.py
```

打开浏览器访问：

```text
http://127.0.0.1:8000
```

Web 页面支持：

- 创建小说项目
- 输入小说标题、题材、主角、风格、章节数量和每章目标字数
- 每章目标字数默认是 3000，可调整为 1000、2000、3000、5000 等数字
- 点击按钮生成设定、人物、世界观、大纲、第一章
- 点击“生成下一章”继续按当前项目记忆和大纲写作
- 查看已生成章节
- 导出整本小说 Markdown

FastAPI 入口：

```bash
uvicorn novelwriter.web:app --reload
```

Web API 不会返回 `.env` 内容，也不会把 API Key 渲染到前端。真实密钥仍然只应保存在本地 `.env` 或云平台 secrets 中。

## 创建新小说

交互式创建：

```powershell
python main.py new
```

也可以一次性传入参数：

```powershell
python main.py new --title "霓虹回声" --slug neon-echo ^
  --genre "赛博朋克悬疑" ^
  --target-readers "喜欢强情节和反转的网文读者" ^
  --target-words 120000 ^
  --chapter-count 40 ^
  --words-per-chapter 3000 ^
  --protagonist "失去部分记忆的城市调查员林澈" ^
  --world-seed "巨型城市被算法和财阀共同统治，记忆可被交易" ^
  --style "网文节奏，悬疑推进，画面感强" ^
  --pacing-reference "三章一钩子，十章一反转"
```

## 生成设定、人物、世界观和大纲

```powershell
python main.py setting
python main.py characters
python main.py world
python main.py outline
```

生成结果分别保存到：

- `novels/<项目slug>/setting.md`
- `novels/<项目slug>/characters.json`
- `novels/<项目slug>/worldbuilding.md`
- `novels/<项目slug>/outline.md`

## 生成章节

生成指定章节：

```powershell
python main.py chapter 1
```

连续生成下一章：

```powershell
python main.py next
```

章节会保存到：

```text
novels/<项目slug>/chapters/chapter_001.md
```

每次生成章节后，Agent 会自动：

- 读取小说简介、世界观、人物卡、大纲、当前章节大纲和 `memory.json`
- 读取前一章摘要和未回收伏笔
- 保存章节正文
- 更新 `memory.json`
- 写入生成日志
- 执行质量检查

## 续写、重写和润色

续写第 1 章：

```powershell
python main.py continue 1
```

重写第 1 章：

```powershell
python main.py rewrite 1 --instruction "加强悬疑感，减少说明，增加主角行动"
```

润色第 1 章：

```powershell
python main.py polish 1 --instruction "提升画面感和对白自然度"
```

## 更新记忆和质量检查

如果你手动改过某章，可以重新提取记忆：

```powershell
python main.py memory 1
```

检查剧情矛盾和章节质量：

```powershell
python main.py check 1
```

检查器会输出：

- 是否偏离大纲
- 是否人物性格不一致
- 是否世界观矛盾
- 是否存在未解释突变
- 是否章节缺少冲突
- 是否结尾缺少钩子
- 是否语言重复
- 修改建议

## 导出整本小说

```powershell
python main.py export
```

导出文件：

```text
novels/<项目slug>/exported_novel.md
```

## 使用指定项目

大多数命令默认使用当前选中的项目。你也可以用全局参数指定项目：

```powershell
python main.py --project sample-cyber-mystery chapter 2
```

注意：`--project` 是全局参数，需要放在子命令前面。

## GitHub 仓库准备

当前项目适合直接作为 GitHub 仓库提交。建议提交代码、README、示例项目、脚本和 workflow；不要提交 `.env`、本地状态、缓存、日志和导出文件。

首次初始化并推送：

```bash
git init
git add .
git status --short
git commit -m "Initial NovelWriter Agent"
git branch -M main
git remote add origin https://github.com/<your-name>/novelwriter-agent.git
git push -u origin main
```

推送前可检查 `.env` 是否被忽略：

```bash
git check-ignore -v .env
```

如果你使用 GitHub CLI，也可以：

```bash
gh repo create novelwriter-agent --private --source . --remote origin --push
```

## Codex Cloud / Codex Web 使用

把仓库推送到 GitHub 后，可以在 Codex Web 中连接并维护这个项目：

1. 打开 Codex Web，并连接你的 GitHub 账号。
2. 授权 Codex 访问 `novelwriter-agent` 仓库。
3. 创建 Codex environment，选择这个仓库。
4. 如果平台要求 setup script，可以使用：

```bash
bash scripts/codex_setup.sh
```

5. 验证命令使用：

```bash
python scripts/smoke_test.py
```

之后你可以直接在 Codex 里发任务，例如：

- “帮我给 NovelWriter Agent 加一个 Web UI”
- “帮我把 memory.json 改成 SQLite 存储”
- “帮我新增 EPUB 导出功能，并跑 smoke test”
- “帮我检查这个 PR 是否会破坏章节生成流程”

仓库中的 `AGENTS.md` 已写入 Codex 维护说明，Codex 打开仓库后会优先知道如何运行、验证和避免提交敏感文件。

## 核心文件说明

- `main.py`：CLI 入口
- `novelwriter/agent.py`：NovelWriter Agent 核心编排逻辑
- `novelwriter/prompts.py`：系统提示词、设定、大纲、章节、记忆和质检提示词
- `novelwriter/memory.py`：`memory.json` 的读取、写入和合并更新
- `novelwriter/storage.py`：项目目录、章节、日志和导出管理
- `novelwriter/models.py`：项目、人物卡、章节、记忆补丁等数据结构
- `novelwriter/config.py`：环境变量和模型配置
- `novelwriter/quality.py`：离线可运行的启发式质量检查
- `novelwriter/llm.py`：OpenAI 兼容模型接口和 mock 模式
- `novelwriter/web.py`：FastAPI Web 后端
- `web/`：HTML、CSS、JavaScript 前端页面
- `scripts/smoke_test.py`：离线 smoke test
- `scripts/run_web.py`：启动 Web 应用
- `AGENTS.md`：给 Codex/自动化维护者的仓库说明

## 记忆管理方案

`memory.json` 会持续保存：

- 小说基本信息
- 已出现人物
- 世界规则、时间线、地点、势力、能力体系和禁忌
- 已发生事件
- 未回收伏笔
- 已回收伏笔
- 章节摘要
- 人物关系变化
- 质量问题记录

生成新章节前，Agent 会读取这些内容作为上下文，避免剧情前后矛盾。

## 人物卡格式

```json
{
  "name": "角色姓名",
  "age": "年龄",
  "identity": "身份",
  "personality": "性格",
  "goal": "目标",
  "weakness": "弱点",
  "secret": "秘密",
  "relationships": {
    "其他角色": "关系说明"
  },
  "arc": [
    {
      "stage": "前期",
      "change": "人物变化"
    }
  ]
}
```

## 世界观设定格式

`worldbuilding.md` 建议保持以下结构：

- 世界基础设定
- 时间线
- 地点
- 势力
- 能力体系或科技体系
- 禁忌、限制和代价
- 重要道具或资源
- 世界观一致性规则

## 章节生成模板

章节生成会要求模型输出 JSON，其中 `chapter_markdown` 是正文：

```json
{
  "chapter_title": "章节标题",
  "chapter_markdown": "# 第1章 标题\n\n小说正文",
  "summary": "本章摘要",
  "new_characters": [],
  "new_locations": [],
  "new_foreshadowing": [],
  "resolved_foreshadowing": [],
  "relationship_changes": [],
  "world_updates": {
    "rules": [],
    "timeline": [],
    "locations": [],
    "factions": [],
    "systems": [],
    "taboos": []
  },
  "events": [],
  "quality_notes": []
}
```

## 连续写作逻辑

1. 读取当前项目元数据
2. 读取核心设定、人物卡、世界观、完整大纲
3. 提取当前章节大纲
4. 读取 `memory.json`
5. 读取前一章摘要和未回收伏笔
6. 生成当前章正文和记忆补丁
7. 保存章节 Markdown
8. 合并更新 `memory.json`
9. 执行质量检查
10. 继续生成下一章，直到达到章节上限

## 后续扩展建议

- 接入向量数据库：把章节、人物和设定切片存入 Chroma、Qdrant 或 SQLite 向量扩展
- 增加 MCP 工具：搜索资料、时间线数据库、角色关系图谱、发布平台适配器
- 增加编辑插件：错别字检查、敏感词检查、风格一致性评分、重复段落检测
- 增加创作模式：多 POV、卷纲锁定、章节草稿多版本、自动回收伏笔
- 增加导出格式：EPUB、DOCX、PDF
- 增加 Web UI：项目看板、人物关系图、章节进度条、伏笔状态面板
