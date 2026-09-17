"""Scan rivulet-llm-studio into a launch catalog."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

SKIP_DIRS = {
    ".git",
    ".github",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    "dist",
    ".next",
    "studio",
    "docs",
    "canvases",
    "assets",
    "windows_use",
    "prisma",
    "migrations",
    "frontend",
    "client",
    "mcp-server",
}

FEATURED = {
    "voice_ai_agents/insurance_claim_live_agent_team": {
        "featured": True,
        "service": "insurance-claim",
        "quality": "flagship",
        "summary": "Live FNOL notebook: voice, camera stills, policy lookup, routing stamp, adjuster packet.",
        "quality_notes": [
            "Hybrid LLM + deterministic Python rules; routing is not model-decided.",
            "Azure path is turn-based. Gemini Live speech-to-speech needs a Google key.",
            "Policy directory is a mock of six records. SIU is keyword/rule gating.",
            "Sessions are in-memory. Restarting the container drops open claims.",
        ],
    },
    "always_on_agents/always_on_hn_briefing_agent": {
        "featured": True,
        "quality": "flagship",
        "summary": "Scheduled Hacker News scout that ranks stories and ships a brief.",
    },
    "always_on_agents/release_radar_agent": {
        "featured": True,
        "quality": "flagship",
        "summary": "Watches dependency releases for breaking, deprecated, and security changes.",
    },
    "advanced_ai_agents/multi_agent_apps/ai_home_renovation_agent": {
        "featured": True,
        "quality": "flagship",
        "summary": "Photo in, renovation plan and photoreal render out (Google ADK).",
    },
    "advanced_ai_agents/single_agent_apps/ai_fraud_investigation_agent": {
        "featured": True,
        "quality": "flagship",
        "summary": "Cross-checks public records and street view for facility fraud signals.",
    },
    "advanced_ai_agents/single_agent_apps/earnings_call_analyst_agent": {
        "featured": True,
        "quality": "flagship",
        "summary": "YouTube earnings call to a live analyst workspace.",
    },
    "agent_skills/project-graveyard": {
        "featured": True,
        "quality": "solid",
        "summary": "Autopsies abandoned side projects. Install with npx skills add.",
    },
    "starter_ai_agents/ai_travel_agent": {
        "featured": True,
        "quality": "tutorial",
        "summary": "README quick start. Streamlit itinerary agent.",
    },
}


_SKIP_HEADINGS = (
    "for macos",
    "for linux",
    "for windows",
    "installation",
    "getting started",
    "prerequisites",
    "usage",
    "setup",
    "run the",
    "how to",
)


def _heading(readme: Path) -> str | None:
    try:
        for line in readme.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line.startswith("# "):
                continue
            title = line[2:].strip().strip("`").strip()
            title = title.encode("ascii", "ignore").decode("ascii").strip() or title
            lowered = title.lower()
            if lowered.endswith((".py", ".js", ".ts", ".md")):
                continue
            if any(lowered.startswith(prefix) for prefix in _SKIP_HEADINGS):
                continue
            if len(title) < 4:
                continue
            return title
    except OSError:
        return None
    return None


def _read_small(path: Path, limit: int = 4000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[:limit].lower()
    except OSError:
        return ""


def _detect_entry(path: Path, req: str) -> tuple[str, str | None, list[str]]:
    """Return kind, relative entry file, launch argv."""

    files = {p.name.lower() for p in path.iterdir() if p.is_file()}
    if "skill.md" in files:
        return "skill", "SKILL.md", []

    if "package.json" in files and "requirements.txt" not in files:
        return "node", "package.json", []

    streamlit_files: list[Path] = []
    fastapi_files: list[Path] = []
    py_candidates: list[Path] = list(path.glob("*.py"))
    for extra in ("live_demo", "frontend", "backend", "app"):
        folder = path / extra
        if folder.is_dir():
            py_candidates.extend(folder.glob("*.py"))
    for py in py_candidates:
        text = _read_small(py)
        if "streamlit" in text:
            streamlit_files.append(py)
        if "from fastapi" in text or "import fastapi" in text:
            fastapi_files.append(py)

    if "streamlit" in req or streamlit_files:
        preferred = None
        for py in streamlit_files:
            name = py.name.lower()
            if "agent" in name or name in {"app.py", "home.py"}:
                preferred = py
                break
        entry = preferred or (streamlit_files[0] if streamlit_files else None)
        if entry is not None:
            rel = entry.relative_to(path).as_posix()
            return "streamlit", rel, ["-m", "streamlit", "run", rel]
        return "streamlit", None, []

    if "fastapi" in req or fastapi_files:
        live = path / "live_demo" / "server.py"
        if live.exists():
            return "fastapi", "live_demo/server.py", ["-m", "uvicorn", "live_demo.server:app"]
        for py in fastapi_files:
            rel = py.relative_to(path).as_posix()
            module = rel[:-3].replace("/", ".")
            if py.name == "server.py":
                return "fastapi", rel, ["-m", "uvicorn", f"{module}:app"]
        if fastapi_files:
            rel = fastapi_files[0].relative_to(path).as_posix()
            module = rel[:-3].replace("/", ".")
            return "fastapi", rel, ["-m", "uvicorn", f"{module}:app"]

    if "requirements.txt" in files or any(f.endswith(".py") for f in files):
        return "python", None, []
    return "docs", None, []


def _quality(path: Path, rel: str, kind: str, overlay: dict[str, Any]) -> str:
    if overlay.get("quality"):
        return str(overlay["quality"])
    tests = (path / "tests").exists() or (path / "evals").exists()
    structured = (path / "schemas.py").exists()
    if tests and structured:
        return "solid"
    if kind in {"skill"}:
        return "skill"
    if kind in {"streamlit", "python"}:
        py_files = [p for p in path.glob("*.py")]
        if len(py_files) <= 2:
            return "tutorial"
    if kind == "fastapi":
        return "solid"
    return "tutorial"


def _stack(req: str, kind: str) -> str:
    libs: list[str] = []
    mapping = [
        ("streamlit", "streamlit"),
        ("google-adk", "adk"),
        ("openai-agents", "openai-agents"),
        ("agno", "agno"),
        ("phidata", "phidata"),
        ("crewai", "crewai"),
        ("langgraph", "langgraph"),
        ("langchain", "langchain"),
        ("fastapi", "fastapi"),
        ("pydantic-ai", "pydantic-ai"),
    ]
    for needle, label in mapping:
        if needle in req and label not in libs:
            libs.append(label)
    if kind == "skill":
        libs.append("agent-skill")
    if kind == "node":
        libs.append("javascript")
    return ", ".join(libs) or kind


def scan_projects(root: Path) -> list[dict[str, Any]]:
    cache_key = str(root.resolve())
    cached = getattr(scan_projects, "_cache", {})
    if cached.get("key") == cache_key and cached.get("rows"):
        return cached["rows"]
    found: list[dict[str, Any]] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        path = Path(dirpath)
        files = {name.lower() for name in filenames}
        markers = {"requirements.txt", "pyproject.toml", "package.json", "skill.md"}
        has_py = any(name.endswith(".py") for name in filenames)
        if "readme.md" not in files or not (files & markers or has_py):
            continue
        rel = path.relative_to(root).as_posix()
        if rel in {".", "studio"}:
            continue
        readme = next((path / name for name in filenames if name.lower() == "readme.md"), path / "README.md")
        req = _read_small(path / "requirements.txt") if "requirements.txt" in files else ""
        kind, entry, launch = _detect_entry(path, req)
        overlay = FEATURED.get(rel, {})
        has_tests = (path / "tests").exists() or any("test_" in name for name in filenames)
        has_docker = any(path.glob("Dockerfile*")) or any(name.lower().startswith("dockerfile") for name in filenames)
        project = {
            "id": rel,
            "name": path.name.replace("_", " ").replace("-", " "),
            "title": _heading(readme) or path.name.replace("_", " "),
            "category": rel.split("/")[0].replace("_", " "),
            "kind": kind,
            "stack": _stack(req, kind),
            "entry": entry,
            "launch": launch,
            "launchable": bool(launch) and kind in {"streamlit", "fastapi"},
            "has_tests": has_tests,
            "has_docker": has_docker,
            "has_requirements": "requirements.txt" in files,
            "quality": _quality(path, rel, kind, overlay),
            "summary": overlay.get("summary") or "",
            "quality_notes": overlay.get("quality_notes") or [],
            "featured": bool(overlay.get("featured")),
            "service": overlay.get("service"),
        }
        found.append(project)

    found.sort(key=lambda item: item["id"])
    kept: list[dict[str, Any]] = []
    for item in sorted(found, key=lambda row: row["id"].count("/")):
        if any(item["id"].startswith(parent["id"] + "/") for parent in kept):
            continue
        kept.append(item)
    kept.sort(key=lambda row: (not row["featured"], row["category"], row["title"].lower()))
    scan_projects._cache = {"key": str(root.resolve()), "rows": kept}
    return kept


if __name__ == "__main__":
    import json

    rows = scan_projects(Path(__file__).resolve().parents[1])
    print(json.dumps({"count": len(rows), "featured": [r["id"] for r in rows if r["featured"]], "kinds": sorted({r["kind"] for r in rows})}, indent=2))
    print("launchable", sum(1 for r in rows if r["launchable"]))
