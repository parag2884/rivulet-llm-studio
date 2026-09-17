const listEl = document.querySelector("#list");
const briefEl = document.querySelector("#brief");
const statsEl = document.querySelector("#stats");
const categoryEl = document.querySelector("#category");
const qualityEl = document.querySelector("#quality");
const searchEl = document.querySelector("#search");
const launchableEl = document.querySelector("#launchableOnly");
const frameEl = document.querySelector("#frame");
const stageEmpty = document.querySelector("#stageEmpty");
const stageLabel = document.querySelector("#stageLabel");
const popOut = document.querySelector("#popOut");

let catalog = { projects: [], categories: [], counts: {} };
let selectedId = null;

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
    ["Projects", counts.all || 0],
    ["Runnable", counts.launchable || 0],
    ["Flagship", counts.flagship || 0],
  ]
    .map(([label, value]) => `<div><b>${value}</b>${label}</div>`)
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
          <span class="pill ${escapeHtml(project.quality)}">${escapeHtml(project.quality)}</span>
          ${escapeHtml(project.category)} · ${escapeHtml(project.kind)}
        </div>
      </button>`;
    })
    .join("");
}

function renderBrief(project) {
  if (!project) return;
  const notes = (project.quality_notes || [])
    .map((note) => `<li>${escapeHtml(note)}</li>`)
    .join("");
  briefEl.innerHTML = `
    <p class="kicker">${escapeHtml(project.id)}</p>
    <h2>${escapeHtml(project.title)}</h2>
    <p>${escapeHtml(project.summary || "No extra blurb. This is a template from the collection.")}</p>
    <p>Stack: ${escapeHtml(project.stack)} · Tests: ${project.has_tests ? "yes" : "no"} · Dockerfile: ${project.has_docker ? "yes" : "no"}</p>
    ${notes ? `<ul>${notes}</ul>` : ""}
    <div class="actions">
      <button class="primary" id="openBtn">${project.always_on ? "Open app" : project.launchable ? "Launch in studio" : "Not runnable here"}</button>
      ${project.open_url ? `<a class="button" href="${escapeHtml(project.open_url)}" target="_blank" rel="noreferrer">New tab</a>` : ""}
    </div>
    <p id="openStatus"></p>
  `;
  document.querySelector("#openBtn").disabled = !project.launchable;
  document.querySelector("#openBtn").addEventListener("click", () => openProject(project));
}

function showFrame(url, label) {
  frameEl.hidden = false;
  stageEmpty.hidden = true;
  frameEl.src = url;
  stageLabel.textContent = label;
  popOut.hidden = false;
  popOut.href = url.replace("/?embed=true", "/");
}

async function openProject(project) {
  const status = document.querySelector("#openStatus");
  status.textContent = "Starting…";
  try {
    const response = await fetch("/api/projects/open", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: project.id }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "Open failed");
    if (payload.mode === "iframe" && payload.url) {
      showFrame(payload.url, project.title);
      status.textContent = payload.message || "Open.";
    } else {
      status.textContent = payload.message || "This project cannot boot in the runner.";
    }
  } catch (error) {
    status.textContent = error.message;
  }
}

async function load() {
  const payload = await fetch("/api/projects").then((response) => response.json());
  catalog = payload;
  categoryEl.innerHTML = `<option value="all">All categories</option>` + payload.categories.map((name) => `<option>${name}</option>`).join("");
  renderStats();
  renderList();
  const first = filtered().find((project) => project.featured) || filtered()[0];
  if (first) {
    selectedId = first.id;
    renderList();
    renderBrief(first);
  }
}

listEl.addEventListener("click", (event) => {
  const button = event.target.closest("[data-id]");
  if (!button) return;
  selectedId = button.dataset.id;
  renderList();
  renderBrief(catalog.projects.find((project) => project.id === selectedId));
});

for (const el of [searchEl, categoryEl, qualityEl, launchableEl]) {
  el.addEventListener("input", renderList);
  el.addEventListener("change", renderList);
}

load().catch((error) => {
  briefEl.innerHTML = `<p class="empty">${escapeHtml(error.message)}</p>`;
});
