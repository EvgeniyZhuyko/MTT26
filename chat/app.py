"""
LocalScript Chat — FastAPI app

GET  /       render the chat page (index.html with chat.js injected inline)
POST /chat   forward prompt to the agent service, return its response
"""

from __future__ import annotations

import os
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

app = FastAPI(title="LocalScript Chat")

AGENT_URL = os.getenv("AGENT_URL", "http://localhost:8080")
_STATIC = Path(__file__).parent / "static"


# ── Pages ──────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    html = (_STATIC / "index.html").read_text(encoding="utf-8")
    js   = (_STATIC / "chat.js").read_text(encoding="utf-8")
    return html.replace("<!-- INJECT_JS -->", f"<script>\n{js}\n</script>")


# ── Chat ───────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    prompt: str


@app.post("/chat")
async def chat(req: ChatRequest) -> dict:
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{AGENT_URL}/generate",
                json={"prompt": req.prompt},
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code,
            detail=exc.response.text,
        )
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail=f"Agent unreachable: {exc}")
