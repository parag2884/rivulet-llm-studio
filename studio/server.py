"""Studio dashboard: catalog every rivulet-llm-studio project and open one."""

from __future__ import annotations

import os
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from catalog import scan_projects

ROOT = Path(os.getenv("APPS_ROOT", Path(__file__).resolve().parents[1]))
STATIC = Path(__file__).resolve().parent / "static"
INSURANCE_URL = os.getenv("INSURANCE_PUBLIC_URL", "http://localhost:4177")
RUNNER_URL = os.getenv("RUNNER_INTERNAL_URL", "http://127.0.0.1:8500")
RUNNER_PUBLIC_URL = os.getenv("RUNNER_PUBLIC_URL", "http://localhost:8501")

app = FastAPI(title="LLM Apps Studio")
app.mount("/assets", StaticFiles(directory=STATIC), name="assets")


class OpenRequest(BaseModel):
    id: str


def projects() -> list[dict]:
    rows = scan_projects(ROOT)
    for row in rows:
        if row.get("service") == "insurance-claim":
            row["open_url"] = INSURANCE_URL
            row["always_on"] = True
            row["launchable"] = True
        else:
            row["open_url"] = RUNNER_PUBLIC_URL if row["launchable"] else None
            row["always_on"] = False
    return rows


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "root": str(ROOT), "projects": len(projects())}


@app.get("/api/projects")
def list_projects() -> dict:
    rows = projects()
    categories = sorted({row["category"] for row in rows})
    return {
        "projects": rows,
        "categories": categories,
        "counts": {
            "all": len(rows),
            "launchable": sum(1 for row in rows if row["launchable"]),
            "featured": sum(1 for row in rows if row["featured"]),
            "flagship": sum(1 for row in rows if row["quality"] == "flagship"),
        },
    }


@app.post("/api/projects/open")
async def open_project(request: OpenRequest) -> dict:
    match = next((row for row in projects() if row["id"] == request.id), None)
    if match is None:
        raise HTTPException(status_code=404, detail="Unknown project.")

    if match.get("service") == "insurance-claim":
        return {
            "ok": True,
            "mode": "iframe",
            "url": INSURANCE_URL,
            "project": match,
            "message": "Insurance claim agent is a dedicated container.",
        }

    if not match["launchable"]:
        return {
            "ok": False,
            "mode": "docs",
            "url": None,
            "project": match,
            "message": (
                "This one is not a Python Streamlit/FastAPI app the runner can boot. "
                "Open the folder in the repo and follow its README."
            ),
        }

    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(
                f"{RUNNER_URL}/launch",
                json={"id": match["id"], "launch": match["launch"], "kind": match["kind"]},
            )
            payload = response.json()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail=f"Project runner is unavailable: {exc}") from exc
    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=payload.get("detail") or payload)

    return {
        "ok": True,
        "mode": "iframe",
        "url": f"{RUNNER_PUBLIC_URL}{payload.get('path_suffix', '')}",
        "project": match,
        "message": payload.get("message", "Project is starting."),
        "runner": payload,
    }


@app.get("/api/runner/status")
async def runner_status() -> dict:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{RUNNER_URL}/status")
            return response.json()
    except httpx.HTTPError:
        return {"running": False, "project": None}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")
