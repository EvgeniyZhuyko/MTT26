#!/usr/bin/env python3
"""
LocalScript REST API

POST /generate  — generate a Lua script from a natural-language prompt
GET  /health    — liveness probe

Run:
  uvicorn api:app --host 0.0.0.0 --port 8080
"""

from __future__ import annotations

from typing import Any

import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from localscript.agent.graph import build_graph
from localscript.agent.state import AgentState

app = FastAPI(title="LocalScript API", version="1.0.0")


# ── Request / Response schemas ─────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    prompt: str
    context: dict[str, Any] | None = None
    key: str = "result"
    model: str = "localscript:latest"
    max_iter: int = 3


class GenerateResponse(BaseModel):
    lua: str
    manifest: dict[str, str]
    iterations: int
    lint_errors: list[str]


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/generate", response_model=GenerateResponse)
def generate(req: GenerateRequest) -> GenerateResponse:
    """Generate a Lua script for the Octapi LowCode platform.

    - **prompt**: task description in Russian or English
    - **context**: optional `{"wf": {"vars": {...}}}` JSON
    - **key**: field name in the returned manifest (default: `result`)
    - **model**: Ollama model tag (default: `localscript:latest`)
    - **max_iter**: generator → critic retry limit (default: 3)
    """
    graph = build_graph(max_iter=req.max_iter)

    initial_state: AgentState = {
        "user_prompt": req.prompt,
        "wf_context": req.context,
        "history": [],
        "script": "",
        "lint_errors": [],
        "iterations": 0,
        "done": False,
        "extract_lua": True,
        "model": req.model,
    }

    try:
        result = graph.invoke(initial_state)
    except requests.ConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    script: str = result.get("script", "")
    if not script:
        raise HTTPException(status_code=500, detail="Agent produced no script.")

    return GenerateResponse(
        lua=script,
        manifest={req.key: f"lua{{{script}}}lua"},
        iterations=result["iterations"],
        lint_errors=result.get("lint_errors", []),
    )
