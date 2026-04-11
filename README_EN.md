# LocalScript — Jury Instructions

Generates Lua scripts for the **Octapi LowCode** platform from natural-language
task descriptions (Russian or English).
Fine-tuned `nuprl/MultiPLCoder-1b` model served via Ollama, wrapped in a
FastAPI + LangGraph agentic loop with luacheck validation.

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Docker + Docker Compose | Any recent version |
| NVIDIA GPU with ≥4 GB VRAM | CPU-only: see note below |
| [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html) | Required for GPU passthrough |

**CPU-only fallback:** remove the `deploy` block from `compose.yml` before
starting. Generation will work but will be slower.

---

## Step 1 — Get the fine-tuned model file

The GGUF file is not stored in the repository (it is ~755 MB and git-ignored).
You need to produce it once before starting Docker.

### Option A — Train locally (requires a CUDA GPU)

```bash
pip install -r requirements-train.txt
python training/train.py          # QLoRA fine-tuning, ~5 min on T4
python training/merge_export.py   # merge LoRA + export to GGUF
```

This writes `training/localscript-q4_k_m.gguf`.

> **Note:** `merge_export.py` uses llama.cpp for the GGUF step.  
> Build it once before running:
> ```bash
> git clone https://github.com/ggerganov/llama.cpp.git
> pip install -r llama.cpp/requirements.txt
> cd llama.cpp && cmake -B build && cmake --build build --target llama-quantize -j$(nproc)
> ```

### Option B — Run the Colab notebook (no local GPU needed)

Open `training/localscript_train.ipynb` in Google Colab with a **T4 GPU**
runtime (free tier), run all cells, then download the generated
`localscript-q4_k_m.gguf` and place it in the `training/` directory.

---

## Step 2 — Start the stack

```bash
docker compose up --build
```

The first run downloads the `ollama/ollama` image and builds the agent image
(Python 3.13 + luacheck + Ollama CLI + Python dependencies).  This takes
roughly 2–3 minutes on a fresh machine.

On subsequent runs the images are cached and startup takes under 30 seconds.

**The stack is ready when you see:**

```
agent_1  | [entrypoint] Starting API server on :8080 ...
```

---

## Step 3 — Test

### Health check

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
  Generator node ── calls MultiPLCoder-1b via Ollama → raw Lua
      │
      ▼
  Critic node ── runs luacheck; if errors, retries (up to max_iter)
      │
      ▼
  JSON response
```

- **Model:** `nuprl/MultiPLCoder-1b` fine-tuned with QLoRA on 314 Octapi Lua examples
- **Runtime:** Ollama (GGUF Q4\_K\_M, ~755 MB)
- **Inference params:** `num_ctx=4096`, `num_predict=256`, `temperature=0.1`, `top_p=0.9`
- **Validation:** luacheck static analysis
