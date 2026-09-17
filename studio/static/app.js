const listEl = document.querySelector("#list");
const briefEl = document.querySelector("#brief");
const statsEl = document.querySelector("#stats");
const categoryEl = document.querySelector("#category");
const qualityEl = document.querySelector("#quality");
const searchEl = document.querySelector("#search");
const launchableEl = document.querySelector("#launchableOnly");
const frameEl = document.querySelector("#frame");
const stageEmpty = document.querySelector("#stageEmpty");

let catalog = { projects: [], categories: [], counts: {} };
let selectedId = null;
let openId = null;

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function filtered() {
  const q = searchEl.value.trim().toLowerCase();
  return catalog.projects.filter((project) => {
    if (categoryEl.value !== "all" && project.category !== categoryEl.value) return false;
    if (qualityEl.value !== "all" && project.quality !== qualityEl.value) return false;
    if (launchableEl.checked && !project.launchable) return false;
    if (!q) return true;
    return [project.title, project.id, project.stack, project.summary, project.kind].join(" ").toLowerCase().includes(q);
  });
}

function renderStats() {
  const counts = catalog.counts || {};
  statsEl.innerHTML = [
    ["all", counts.all || 0],
    ["run", counts.launchable || 0],
    ["flagship", counts.flagship || 0],
  ]
    .map(([label, value]) => `<span><b>${value}</b>${label}</span>`)
    .join("");
}

function renderList() {
  const rows = filtered();
  listEl.innerHTML = rows
    .map((project) => {
      const active = project.id === selectedId ? "active" : "";
      return `<button class="card ${active}" data-id="${escapeHtml(project.id)}">
        <div class="title">${escapeHtml(project.title)}</div>
        <div class="meta">
          <span class="dot ${project.launchable ? "on" : ""}"></span>
          <span class="pill ${escapeHtml(project.quality)}">${escapeHtml(project.quality)}</span>
          ${escapeHtml(project.kind)}
        </div>
      </button>`;
    })
    .join("");
}

function actionLabel(project) {
  if (project.always_on) return "Open";
  if (project.launchable) return "Launch";
  return "Can't run";
}

function renderBrief(project) {
  if (!project) return;
  const hint = project.launchable
    ? project.summary || `${project.stack || project.kind} · ${project.id}`
    : project.blocked_reason || "This is a skill, Node app, or notebook — open the folder README.";
  briefEl.innerHTML = `
    <div class="title" title="${escapeHtml(project.id)}">${escapeHtml(project.title)}</div>
    <div class="hint" title="${escapeHtml(hint)}">${escapeHtml(hint)}</div>
    <div class="actions">
      <span id="openStatus"></span>
      <button class="primary" id="openBtn">${actionLabel(project)}</button>
      ${project.open_url ? `<a class="button" href="${escapeHtml(project.open_url)}" target="_blank" rel="noreferrer">Tab</a>` : ""}
    </div>
  `;
  document.querySelector("#openBtn").disabled = !project.launchable;
  document.querySelector("#openBtn").addEventListener("click", () => openProject(project));
}

function showFrame(url) {
  frameEl.hidden = false;
  stageEmpty.hidden = true;
  if (frameEl.src !== url) frameEl.src = url;
}

async function openProject(project) {
  const status = document.querySelector("#openStatus");
  if (status) status.textContent = "Starting…";
  try {
    const response = await fetch("/api/projects/open", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: project.id }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "Open failed");
    if (payload.mode === "iframe" && payload.url) {
      showFrame(payload.url);
      openId = project.id;
      if (status) status.textContent = payload.message || "Open";
    } else if (status) {
      status.textContent = payload.message || "Not runnable in Studio.";
    }
  } catch (error) {
    if (status) status.textContent = error.message;
  }
}

function selectProject(id, { launchAlwaysOn = false } = {}) {
  selectedId = id;
  const project = catalog.projects.find((item) => item.id === selectedId);
  renderList();
  renderBrief(project);
  if (launchAlwaysOn && project?.always_on) openProject(project);
}

async function load() {
  briefEl.innerHTML = `<p class="empty">Loading projects…</p>`;
  const payload = await fetch("/api/projects").then((response) => response.json());
  catalog = payload;
  categoryEl.innerHTML = `<option value="all">All categories</option>` + payload.categories.map((name) => `<option>${name}</option>`).join("");
  renderStats();
  renderList();
  const first =
    filtered().find((project) => project.always_on) ||
    filtered().find((project) => project.featured) ||
    filtered()[0];
  if (first) selectProject(first.id, { launchAlwaysOn: true });
}

listEl.addEventListener("click", (event) => {
  const button = event.target.closest("[data-id]");
  if (!button) return;
  selectProject(button.dataset.id, { launchAlwaysOn: true });
});

for (const el of [searchEl, categoryEl, qualityEl, launchableEl]) {
  el.addEventListener("input", renderList);
  el.addEventListener("change", renderList);
}

load().catch((error) => {
  briefEl.innerHTML = `<p class="empty">${escapeHtml(error.message)}</p>`;
});
