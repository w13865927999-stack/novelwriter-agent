const state = {
  activeSlug: "",
  currentChapterNumber: null,
};

const $ = (selector) => document.querySelector(selector);
const output = $("#output");
const projectSelect = $("#projectSelect");
const activeProject = $("#activeProject");
const chaptersEl = $("#chapters");
const chapterTitle = $("#chapterTitle");
const chapterEditor = $("#chapterEditor");

function setOutput(value) {
  output.textContent = typeof value === "string" ? value : JSON.stringify(value, null, 2);
}

function currentChapterWordCount() {
  const input = document.querySelector('[name="chapter_word_count"]');
  const value = Number(input?.value || 3000);
  return Number.isFinite(value) && value > 0 ? value : 3000;
}

function generationPayload() {
  return { chapter_word_count: currentChapterWordCount() };
}

async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `HTTP ${response.status}`);
  }
  return response.json();
}

async function loadHealth() {
  const data = await request("/api/health");
  $("#health").textContent = data.mock
    ? "Mock 模式运行中，无需 API Key"
    : `真实模型模式：${data.model}${data.api_key_configured ? "" : "（缺少 API Key）"}`;
}

async function loadProjects(selectSlug = "") {
  const data = await request("/api/projects");
  const projects = data.projects || [];
  projectSelect.innerHTML = "";

  if (!projects.length) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "暂无项目";
    projectSelect.appendChild(option);
    state.activeSlug = "";
    activeProject.textContent = "未选择项目";
    chaptersEl.innerHTML = "";
    state.currentChapterNumber = null;
    return;
  }

  for (const project of projects) {
    const option = document.createElement("option");
    option.value = project.slug;
    option.textContent = `${project.title} (${project.slug})`;
    projectSelect.appendChild(option);
  }

  state.activeSlug = selectSlug || data.active_project || projects[0].slug;
  projectSelect.value = state.activeSlug;
  await loadProject(state.activeSlug);
}

async function loadProject(slug) {
  if (!slug) return;
  state.activeSlug = slug;
  const data = await request(`/api/projects/${slug}`);
  const project = data.project;
  activeProject.textContent = `${project.title} | ${project.genre} | ${project.chapter_count} 章`;
  renderChapters(data.chapters || []);
  setOutput({
    title: project.title,
    status: data.status,
    settingReady: Boolean(data.setting && !data.setting.includes("尚未生成")),
    characters: (data.characters.characters || []).length,
    outlineReady: Boolean(data.outline && !data.outline.includes("尚未生成")),
  });
}

function renderChapters(chapters) {
  chaptersEl.innerHTML = "";
  if (!chapters.length) {
    chaptersEl.innerHTML = '<p class="notice">还没有章节。</p>';
    return;
  }

  for (const chapter of chapters) {
    const button = document.createElement("button");
    button.className = "chapter-item";
    button.type = "button";
    button.innerHTML = `<span>${chapter.title}</span><span>#${chapter.number}</span>`;
    button.addEventListener("click", () => loadChapter(chapter.number));
    chaptersEl.appendChild(button);
  }
}

async function loadChapter(number) {
  const data = await request(`/api/projects/${state.activeSlug}/chapters/${number}`);
  state.currentChapterNumber = data.number;
  chapterTitle.textContent = `第 ${data.number} 章`;
  chapterEditor.value = data.content;
}

async function withBusy(button, task) {
  const oldText = button.textContent;
  button.disabled = true;
  button.textContent = "处理中...";
  try {
    await task();
  } catch (error) {
    setOutput(`操作失败：${error.message}`);
  } finally {
    button.textContent = oldText;
    button.disabled = false;
  }
}

$("#projectForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = event.submitter;
  await withBusy(button, async () => {
    const form = new FormData(event.currentTarget);
    const payload = Object.fromEntries(form.entries());
    payload.chapter_count = Number(payload.chapter_count || 10);
    payload.chapter_word_count = currentChapterWordCount();
    const data = await request("/api/projects", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    setOutput(data);
    await loadProjects(data.slug);
  });
});

document.querySelectorAll("[data-generate]").forEach((button) => {
  button.addEventListener("click", async () => {
    if (!state.activeSlug) {
      setOutput("请先创建或选择项目。");
      return;
    }
    const kind = button.dataset.generate;
    await withBusy(button, async () => {
      const data = await request(`/api/projects/${state.activeSlug}/generate/${kind}`, {
        method: "POST",
        body: JSON.stringify(generationPayload()),
      });
      setOutput(data);
      await loadProject(state.activeSlug);
      if (kind === "first_chapter") {
        await loadChapter(1);
      }
    });
  });
});

$("#exportNovel").addEventListener("click", async () => {
  if (!state.activeSlug) {
    setOutput("请先创建或选择项目。");
    return;
  }
  await withBusy($("#exportNovel"), async () => {
    const data = await request(`/api/projects/${state.activeSlug}/export`, { method: "POST" });
    setOutput(data);
    window.location.href = data.download_url;
  });
});

$("#generateNextChapter").addEventListener("click", async () => {
  if (!state.activeSlug) {
    setOutput("请先创建或选择项目。");
    return;
  }
  await withBusy($("#generateNextChapter"), async () => {
    const data = await request(`/api/projects/${state.activeSlug}/next`, {
      method: "POST",
      body: JSON.stringify(generationPayload()),
    });
    setOutput({
      message: data.message,
      project: data.project_name,
      chapter: data.chapter_number,
      title: data.chapter_title,
      path: data.path,
    });
    await loadProject(state.activeSlug);
    if (data.chapter_number) {
      chapterTitle.textContent = data.chapter_title || `第 ${data.chapter_number} 章`;
      state.currentChapterNumber = data.chapter_number;
      chapterEditor.value = data.chapter_content || "章节已生成。";
    }
  });
});

$("#initializeProject").addEventListener("click", async () => {
  if (!state.activeSlug) {
    setOutput("请先创建或选择项目。");
    return;
  }
  await withBusy($("#initializeProject"), async () => {
    const data = await request(`/api/projects/${state.activeSlug}/initialize`, {
      method: "POST",
      body: JSON.stringify(generationPayload()),
    });
    setOutput(data);
    await loadProject(state.activeSlug);
    await loadChapter(1);
  });
});

$("#saveChapter").addEventListener("click", async () => {
  if (!state.activeSlug || !state.currentChapterNumber) {
    setOutput("请先选择章节。");
    return;
  }
  await withBusy($("#saveChapter"), async () => {
    const data = await request(`/api/projects/${state.activeSlug}/chapters/${state.currentChapterNumber}`, {
      method: "PUT",
      body: JSON.stringify({ content: chapterEditor.value }),
    });
    setOutput(data);
    await loadProject(state.activeSlug);
  });
});

$("#deleteChapter").addEventListener("click", async () => {
  if (!state.activeSlug || !state.currentChapterNumber) {
    setOutput("请先选择章节。");
    return;
  }
  if (!window.confirm(`确认删除第 ${state.currentChapterNumber} 章？此操作会删除 Markdown 文件。`)) {
    return;
  }
  await withBusy($("#deleteChapter"), async () => {
    const data = await request(`/api/projects/${state.activeSlug}/chapters/${state.currentChapterNumber}`, {
      method: "DELETE",
    });
    setOutput(data);
    state.currentChapterNumber = null;
    chapterTitle.textContent = "章节正文";
    chapterEditor.value = "选择或生成章节后在这里查看。";
    await loadProject(state.activeSlug);
  });
});

$("#rewriteChapter").addEventListener("click", async () => {
  if (!state.activeSlug || !state.currentChapterNumber) {
    setOutput("请先选择章节。");
    return;
  }
  if (!window.confirm(`确认覆盖重写第 ${state.currentChapterNumber} 章？`)) {
    return;
  }
  await withBusy($("#rewriteChapter"), async () => {
    const instruction = $("#rewriteInstruction").value || "加强冲突、减少解释、保持原有剧情事实";
    const data = await request(`/api/projects/${state.activeSlug}/chapters/${state.currentChapterNumber}/rewrite`, {
      method: "POST",
      body: JSON.stringify({ instruction }),
    });
    setOutput(data);
    chapterEditor.value = data.chapter_content || chapterEditor.value;
    await loadProject(state.activeSlug);
  });
});

$("#continueChapter").addEventListener("click", async () => {
  if (!state.activeSlug || !state.currentChapterNumber) {
    setOutput("请先选择章节。");
    return;
  }
  await withBusy($("#continueChapter"), async () => {
    const data = await request(`/api/projects/${state.activeSlug}/chapters/${state.currentChapterNumber}/continue`, {
      method: "POST",
    });
    setOutput(data);
    chapterEditor.value = data.chapter_content || chapterEditor.value;
    await loadProject(state.activeSlug);
  });
});

function referencePayload() {
  return {
    reference_text: $("#referenceText").value,
    reference_note: $("#referenceNote").value,
  };
}

$("#saveReference").addEventListener("click", async () => {
  if (!state.activeSlug) {
    setOutput("请先创建或选择项目。");
    return;
  }
  await withBusy($("#saveReference"), async () => {
    const data = await request(`/api/projects/${state.activeSlug}/references`, {
      method: "POST",
      body: JSON.stringify(referencePayload()),
    });
    setOutput(data);
  });
});

$("#analyzeReference").addEventListener("click", async () => {
  if (!state.activeSlug) {
    setOutput("请先创建或选择项目。");
    return;
  }
  await withBusy($("#analyzeReference"), async () => {
    const data = await request(`/api/projects/${state.activeSlug}/references/analyze`, {
      method: "POST",
      body: JSON.stringify(referencePayload()),
    });
    setOutput(data);
  });
});

$("#refreshProjects").addEventListener("click", () => loadProjects(state.activeSlug));
projectSelect.addEventListener("change", () => loadProject(projectSelect.value));

loadHealth()
  .then(() => loadProjects())
  .catch((error) => setOutput(`启动失败：${error.message}`));
