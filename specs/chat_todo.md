# Chat App — Spec

A minimal web-based chat UI that lets a user send natural-language prompts and
receive generated Lua code, backed by the existing `agent` service.

---

## Architecture

```
Browser
  │  GET  /          → chat/app.py injects JS into HTML, returns full page
  │  POST /chat      → chat/app.py → agent:8080/generate → returns Lua
  └──────────────────────────────────────────────────────────────────────

Docker Compose network:
  chat   (port 8081)  →  agent (port 8080)  →  ollama (port 11434)
```

The chat app is a thin proxy. It owns the UI and delegates all inference to the
existing agent service. The agent API is **not modified**.

---

## Folder structure

```
chat/
  app.py              # FastAPI application
  static/
    index.html        # HTML shell — a <script> placeholder gets substituted
    chat.js           # Vanilla JS — injected inline by app.py at request time
  requirements.txt    # fastapi, uvicorn[standard], httpx
  Dockerfile
```

Lives at the repo root as a peer of `localscript/`, `data/`, etc.
Has no imports from the parent project.

---

## Endpoints

### GET /
1. Read `static/index.html` and `static/chat.js` from disk.
2. Replace the literal placeholder `<!-- INJECT_JS -->` in the HTML with
   `<script>` + JS content + `</script>`.
3. Return the resulting string as `text/html`.

No template engine. Plain string substitution.

### POST /chat

**Request body:**
```json
{ "prompt": "Get the last email from the list" }
```

**Behaviour:**
1. Forward `prompt` to `POST {AGENT_URL}/generate` via `httpx`.
2. Return the agent's response verbatim.

**Response body** (agent's schema, passed through):
```json
{
  "lua":        "return wf.vars.emails[#wf.vars.emails]",
  "manifest":   {"result": "lua{...}lua"},
  "iterations": 1,
  "lint_errors": []
}
```

**Config:** `AGENT_URL` environment variable, default `http://localhost:8080`.

---

## UI

Single-page. No frontend build step. No framework. Vanilla JS + minimal CSS
inline in the HTML.

Layout:
```
┌──────────────────────────────────────┐
│  LocalScript Chat                    │
├──────────────────────────────────────┤
│                                      │
│  [user]   Get the last email …       │
│                                      │
│  [model]  return wf.vars.emails…     │
│           (code block, monospace)    │
│                                      │
│  [user]   Increment the counter      │
│                                      │
│  [model]  return wf.vars.count + 1   │
│                                      │
├──────────────────────────────────────┤
│  [ prompt input          ] [Send]    │
└──────────────────────────────────────┘
```

Behaviour:
- History is stored in the JS array `messages` (client-side only). No server
  session. Refresh clears the history.
- Each prompt sends only the latest message to `/chat`. History is display-only;
  it is **not** fed back to the model (the model is a stateless code generator).
- While waiting for a response, the Send button is disabled and shows "…".
- Lua responses are rendered in a `<pre><code>` block with a "Copy" button.
- `lint_errors` (if non-empty) are shown as a small warning below the code block.
- Enter key submits the form.

---

## Docker

### chat/Dockerfile

Base: `python:3.13-slim`.
No system packages needed (no luacheck, no ollama).

```
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8081
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8081"]
```

### chat/requirements.txt

```
fastapi>=0.100
uvicorn[standard]>=0.29
httpx>=0.27
```

### compose.yml addition

```yaml
  chat:
    build: ./chat
    ports:
      - "8081:8081"
    environment:
      - AGENT_URL=http://agent:8080
    depends_on:
      - agent
    restart: on-failure
```

### Makefile target

```makefile
## chat-build: build the chat Docker image
chat-build:
    docker build -t localscript-chat ./chat

## chat-run: run the full stack including the chat UI
chat-run:
    docker compose up --build
```

---

## TODO (deferred)

- **wf context input** — add a collapsible JSON textarea above the prompt field.
  The POST body becomes `{"prompt": "...", "context": {...}}` when non-empty.
- **Streaming** — replace the single `/chat` round-trip with SSE once the agent
  supports streaming (`/api/generate stream=true`).
- **Persistent history** — store conversation in a server-side session (e.g. Redis
  or an in-memory dict keyed by a cookie) so refresh doesn't lose history.
- **Multi-session** — support multiple independent conversations with a session
  switcher in the sidebar.
- **Model selector** — expose the `model` and `max_iter` fields as UI controls.
- **Error display** — show HTTP errors from the agent (503 Ollama down, 500 no
  script) as inline chat messages rather than silent failures.
