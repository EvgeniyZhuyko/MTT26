# LocalScript — Jury Instructions

Generates Lua scripts for the **Octapi LowCode** platform from natural-language
task descriptions (Russian or English).
Fine-tuned [`andreysitaev/hkt_octapi_lua_mpl`](https://ollama.com/andreysitaev/hkt_octapi_lua_mpl) model served via Ollama, wrapped in a
FastAPI + LangGraph agentic loop with luacheck validation.

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Docker + Docker Compose | Any recent version |
| NVIDIA GPU with ≥4 GB VRAM | Recommended; CPU-only: see note below |
| [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html) | Required for GPU passthrough on Linux |

**CPU-only / macOS:** works out of the box — the GPU `deploy` block in `compose.yml`
is commented out. Linux NVIDIA GPU users: uncomment it for full speed.

---

## Step 1 — Start the stack

```bash
docker compose up --build
```

The first run:
1. Downloads the `ollama/ollama` image and builds the agent image (~2–3 min)
2. Pulls the fine-tuned model automatically from Ollama Hub:
   [`andreysitaev/hkt_octapi_lua_mpl`](https://ollama.com/andreysitaev/hkt_octapi_lua_mpl) (~800 MB, once)

On subsequent runs everything is cached and startup takes under 30 seconds.

**The stack is ready when you see:**

```
agent-1  | INFO:     Application startup complete.
```

---

## Step 2 — Test

### Chat UI (browser)

Open **http://localhost:8081** in a browser. Type a prompt and press Send —
the generated Lua code appears with a Copy button.

### Health check (API)

```bash
curl http://localhost:8080/health
# {"status":"ok"}
```

### Generate a Lua script — English prompt with context

```bash
curl -s -X POST http://localhost:8080/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Get the last email from the list",
    "context": {"wf": {"vars": {"emails": ["a@b.com", "b@c.com"]}}}
  }' | python3 -m json.tool
```

Expected response:

```json
{
    "lua": "return wf.vars.emails[#wf.vars.emails]",
    "manifest": {
        "result": "lua{return wf.vars.emails[#wf.vars.emails]}lua"
    },
    "iterations": 1,
    "lint_errors": []
}
```

### Generate a Lua script — Russian prompt with context

```bash
curl -s -X POST http://localhost:8080/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Увеличь счётчик попыток на 1",
    "context": {"wf": {"vars": {"try_count_n": 3}}}
  }' | python3 -m json.tool
```

Expected response:

```json
{
    "lua": "return wf.vars.try_count_n + 1",
    "manifest": {
        "result": "lua{return wf.vars.try_count_n + 1}lua"
    },
    "iterations": 1,
    "lint_errors": []
}
```

### Build a filtered array — Russian prompt

```bash
curl -s -X POST http://localhost:8080/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Отфильтруй письма, которые содержат слово inbox",
    "context": {"wf": {"vars": {"emails": ["inbox@a.com", "spam@b.com", "inbox@c.com"]}}}
  }' | python3 -m json.tool
```

---

## Response schema

| Field | Type | Description |
|---|---|---|
| `lua` | string | Raw Lua code, ready to paste into Octapi |
| `manifest` | object | `{"<key>": "lua{<code>}lua"}` — Octapi workflow format |
| `iterations` | int | Number of generate → validate cycles (1 = passed on first try) |
| `lint_errors` | array | Remaining luacheck warnings, if any |

---

## Interactive API docs

```
http://localhost:8080/docs
```

---

## Request parameters

| Field | Type | Default | Description |
|---|---|---|---|
| `prompt` | string | required | Task description — Russian or English |
| `context` | object | `null` | `{"wf": {"vars": {...}}}` workflow context |
| `key` | string | `"result"` | Key name in the `manifest` field |
| `model` | string | `"localscript:latest"` | Ollama model tag |
| `max_iter` | int | `3` | Generator → critic retry limit |

---

## Architecture

```
POST /generate
      │
      ▼
  Analyst node ── decides if the task is unambiguous
      │
      ▼
  Generator node ── calls andreysitaev/hkt_octapi_lua_mpl via Ollama → raw Lua
      │
      ▼
  Critic node ── runs luacheck; if errors, retries (up to max_iter)
      │
      ▼
  JSON response
```

- **Model:** `andreysitaev/hkt_octapi_lua_mpl` — fine-tuned with QLoRA on 314 Octapi Lua examples
- **Runtime:** Ollama (GGUF Q4\_K\_M, ~800 MB)
- **Inference params:** `num_ctx=4096`, `num_predict=256`, `temperature=0.1`, `top_p=0.9`
- **Validation:** luacheck static analysis
