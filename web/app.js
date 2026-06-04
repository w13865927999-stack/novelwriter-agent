const state = {
  activeSlug: "",
};

const $ = (selector) => document.querySelector(selector);
const output = $("#output");
const projectSelect = $("#projectSelect");
const activeProject = $("#activeProject");
const chaptersEl = $("#chapters");
const chapterTitle = $("#chapterTitle");
const chapterContent = $("#chapterContent");

function setOutput(value) {
  output.textContent = typeof value === "string" ? value : JSON.stringify(value, null, 2);
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
    : `模型：${data.model}`;
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
  chapterTitle.textContent = `第 ${data.number} 章`;
  chapterContent.textContent = data.content;
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
      const data = await request(`/api/projects/${state.activeSlug}/generate/${kind}`, { method: "POST" });
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
    const data = await request(`/api/projects/${state.activeSlug}/next`, { method: "POST" });
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
      chapterContent.textContent = data.chapter_content || "章节已生成。";
    }
  });
});

$("#refreshProjects").addEventListener("click", () => loadProjects(state.activeSlug));
projectSelect.addEventListener("change", () => loadProject(projectSelect.value));

loadHealth()
  .then(() => loadProjects())
  .catch((error) => setOutput(`启动失败：${error.message}`));
