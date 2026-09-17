"""Launch one Python/Streamlit/FastAPI project at a time."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

APPS_ROOT = Path(os.getenv("APPS_ROOT", "/apps")).resolve()
VENVS = Path(os.getenv("VENV_ROOT", "/tmp/venvs"))
CHILD_PORT = int(os.getenv("CHILD_PORT", "8501"))

app = FastAPI(title="LLM Apps runner")
state: dict[str, Any] = {"process": None, "project": None, "started_at": None, "log": ""}


class LaunchRequest(BaseModel):
    id: str
    launch: list[str] = []
    kind: str = "streamlit"
    entry: str | None = None


def _safe_project(project_id: str) -> Path:
    path = (APPS_ROOT / project_id).resolve()
    if APPS_ROOT not in path.parents and path != APPS_ROOT:
        raise HTTPException(status_code=400, detail="Project path is outside the apps root.")
    if not path.exists():
        raise HTTPException(status_code=404, detail="Project folder not found.")
    return path


def _stop() -> None:
    proc: subprocess.Popen | None = state.get("process")
    if proc and proc.poll() is None:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError, OSError):
            proc.terminate()
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()
    state["process"] = None
    state["project"] = None


def _venv_python(project_id: str) -> Path:
    venv = VENVS / project_id.replace("/", "__")
    python = venv / "bin" / "python"
    if not python.exists():
        VENVS.mkdir(parents=True, exist_ok=True)
        subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True)
        subprocess.run([str(python), "-m", "pip", "install", "--upgrade", "pip"], check=True)
    return python


def _install(python: Path, project: Path) -> None:
    req = project / "requirements.txt"
    if not req.exists():
        return
    cmd = [str(python), "-m", "pip", "install", "-r", str(req)]
    index = os.getenv("PIP_INDEX_URL")
    if index:
        cmd.extend(
            [
                "--index-url",
                index,
                "--trusted-host",
                os.getenv("PIP_TRUSTED_HOST", "pypi.org"),
                "--trusted-host",
                "packagefeedproxy.microsoft.io",
                "--trusted-host",
                "files.pythonhosted.org",
            ]
        )
    subprocess.run(cmd, check=True, cwd=project, timeout=240)


@app.get("/status")
def status() -> dict:
    proc = state.get("process")
    alive = bool(proc and proc.poll() is None)
    log_path = Path("/tmp/runner-child.log")
    log_tail = ""
    if log_path.exists():
        log_tail = log_path.read_text(encoding="utf-8", errors="ignore")[-8000:]
    return {
        "running": alive,
        "project": state.get("project"),
        "kind": state.get("kind"),
        "started_at": state.get("started_at"),
        "log_tail": log_tail,
    }


@app.post("/stop")
def stop() -> dict:
    _stop()
    return {"ok": True}


@app.post("/launch")
def launch(request: LaunchRequest) -> dict:
    project = _safe_project(request.id)
    _stop()
    python = _venv_python(request.id)
    try:
        _install(python, project)
    except subprocess.CalledProcessError as exc:
        raise HTTPException(status_code=500, detail=f"pip install failed: {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(status_code=500, detail="pip install timed out.") from exc

    extra_env = os.environ.copy()
    extra_env["PYTHONUNBUFFERED"] = "1"
    extra_env["STREAMLIT_SERVER_HEADLESS"] = "true"
    extra_env["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
    extra_env["GRADIO_SERVER_NAME"] = "0.0.0.0"
    extra_env["GRADIO_SERVER_PORT"] = str(CHILD_PORT)

    if request.kind == "adk":
        adk = python.parent / "adk"
        if not adk.exists():
            raise HTTPException(status_code=500, detail="google-adk did not install the adk CLI.")
        cmd = [str(adk), "web", "--host", "0.0.0.0", "--port", str(CHILD_PORT)]
    elif request.kind == "script":
        entry = request.entry or (request.launch[0] if request.launch else None)
        if not entry:
            raise HTTPException(status_code=400, detail="No script entry file.")
        cmd = [str(python), entry]
    elif request.kind == "gradio":
        entry = request.entry or (request.launch[0] if request.launch else None)
        if not entry:
            raise HTTPException(status_code=400, detail="No Gradio entry file.")
        cmd = [str(python), entry]
    else:
        if not request.launch:
            raise HTTPException(status_code=400, detail="No launch command for this project.")
        cmd = [str(python), *request.launch]
        if request.kind == "streamlit":
            cmd.extend(
                [
                    "--server.port",
                    str(CHILD_PORT),
                    "--server.address",
                    "0.0.0.0",
                    "--server.headless",
                    "true",
                    "--server.enableCORS",
                    "false",
                    "--server.enableXsrfProtection",
                    "false",
                ]
            )
        elif request.kind == "fastapi":
            cmd.extend(["--host", "0.0.0.0", "--port", str(CHILD_PORT)])

    log_path = Path("/tmp/runner-child.log")
    log_file = log_path.open("w", encoding="utf-8")
    proc = subprocess.Popen(
        cmd,
        cwd=project,
        env=extra_env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        preexec_fn=os.setsid,
    )
    state["process"] = proc
    state["project"] = request.id
    state["kind"] = request.kind
    state["started_at"] = time.time()
    time.sleep(1.2)
    log_file.flush()
    if request.kind != "script" and proc.poll() is not None:
        log_file.close()
        state["log"] = log_path.read_text(encoding="utf-8", errors="ignore")
        raise HTTPException(
            status_code=500,
            detail=state["log"][-1500:] or "Project process exited immediately.",
        )
    if request.kind == "script":
        suffix = ""
        url = os.getenv("RUNNER_CONTROL_PUBLIC_URL", "http://localhost:8500") + "/console"
        message = f"Running {request.id} as a script. Logs are in the console."
    elif request.kind == "fastapi":
        suffix = "/docs"
        url = None
        message = f"Started {request.id} API docs on port {CHILD_PORT}."
    else:
        suffix = "/?embed=true" if request.kind == "streamlit" else "/"
        url = None
        message = f"Started {request.id} on port {CHILD_PORT}. First launch installs requirements."
    return {
        "ok": True,
        "project": request.id,
        "pid": proc.pid,
        "path_suffix": suffix,
        "url": url,
        "message": message,
    }


CONSOLE_HTML = """<!doctype html>
<html><head><meta charset="utf-8"/><title>Script console</title>
<style>
body{margin:0;background:#0e0c0a;color:#f3eee6;font:13px/1.45 ui-monospace,monospace}
header{padding:10px 14px;border-bottom:1px solid #3a3228;color:#a89a88}
pre{padding:14px;white-space:pre-wrap;margin:0}
</style></head>
<body>
<header id="meta">Script console</header>
<pre id="log">Waiting for output…</pre>
<script>
async function tick(){
  const res = await fetch('/status');
  const data = await res.json();
  document.getElementById('meta').textContent =
    (data.project || 'no project') + (data.running ? ' · running' : ' · stopped');
  document.getElementById('log').textContent = data.log_tail || 'No output yet.';
}
tick();
setInterval(tick, 1500);
</script>
</body></html>
"""


@app.get("/console", response_class=HTMLResponse)
def console() -> str:
    return CONSOLE_HTML
