# LocalScript

Generates Lua scripts for the **Octapi LowCode** platform from natural-language
task descriptions (Russian or English).  
Runs fully locally via a fine-tuned `nuprl/MultiPLCoder-1b` model served by Ollama.

---

## Quick Start (Docker)

### Prerequisites
- Docker + Docker Compose
- NVIDIA GPU with ≥4 GB VRAM + [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)  
  *(CPU-only: remove the `deploy` block from `compose.yml` — generation will be slower)*
- The fine-tuned GGUF file at `training/localscript-q4_k_m.gguf`

### 1. Get the model

Either run training yourself:

```bash
pip install -r requirements-train.txt
python training/train.py          # fine-tune (~5 min on T4 GPU)
python training/merge_export.py   # export to GGUF
```

Or open `training/localscript_train.ipynb` in Google Colab (T4 GPU, free tier),
run all cells, and download `localscript-q4_k_m.gguf` into `training/`.

### 2. Start the stack

```bash
docker compose up --build
```

The first start registers the model with Ollama (~30 s).  
The API is ready when you see:

```
agent_1  | [entrypoint] Starting API server on :8080 ...
```

### 3. Test

```bash
# Health check
curl http://localhost:8080/health

# Generate a Lua script (English)
curl -s -X POST http://localhost:8080/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Get the last email from the list",
    "context": {"wf": {"vars": {"emails": ["a@b.com", "b@c.com"]}}}
  }' | python3 -m json.tool

# Generate a Lua script (Russian)
curl -s -X POST http://localhost:8080/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Напиши Луа скрипт для получения последнего email из списка"}' \
  | python3 -m json.tool
```

**Response schema:**

```json
{
  "lua":        "return wf.vars.emails[#wf.vars.emails]",
  "manifest":   {"result": "lua{return wf.vars.emails[#wf.vars.emails]}lua"},
  "iterations": 1,
  "lint_errors": []
}
```

Interactive API docs: `http://localhost:8080/docs`

---

## REST API Reference

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/health` | Liveness probe — returns `{"status": "ok"}` |
| `POST` | `/generate` | Generate a Lua script |

### `POST /generate` — request body

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `prompt` | `string` | required | Task description (Russian or English) |
| `context` | `object` | `null` | `{"wf": {"vars": {...}}}` workflow context |
| `key` | `string` | `"result"` | Manifest field name in the response |
| `model` | `string` | `"localscript:latest"` | Ollama model tag |
| `max_iter` | `int` | `3` | Generator → critic retry limit |

### `POST /generate` — response (`200 OK`)

| Field | Type | Description |
|-------|------|-------------|
| `lua` | `string` | Raw Lua code |
| `manifest` | `object` | `{"<key>": "lua{<code>}lua"}` |
| `iterations` | `int` | Number of generation attempts |
| `lint_errors` | `array` | Remaining luacheck warnings, if any |

---

## CLI Usage

Without Docker (requires Ollama running locally with `localscript:latest`):

```bash
# Setup
python3.13 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Basic
python cli.py "Get the last email from the list" \
  --context-str '{"wf":{"vars":{"emails":["a@b.com","b@c.com"]}}}'

# Russian prompt, raw Lua output
python cli.py "Увеличь счётчик на 1" \
  --context-str '{"wf":{"vars":{"try_count_n":3}}}' --lua

# All options
python cli.py --help
```

---

## Architecture

```
User prompt
     │
     ▼
 Analyst node ─── checks if the task is unambiguous
     │
     ▼
 Generator node ── generates Lua via MultiPLCoder-1b (Ollama)
     │
     ▼
 Critic node ───── validates with luacheck
     │
  ┌──┴──────────────────────────────┐
  │ LGTM → done                     │ errors → retry (max 3×)
  ▼                                  ▼
output                          Generator node
```

- **Model**: `nuprl/MultiPLCoder-1b` fine-tuned with QLoRA on 314 Octapi Lua examples
- **Runtime**: Ollama (GGUF Q4\_K\_M, ~700 MB)
- **Evaluation params**: `num_ctx=4096`, `num_predict=256`, `temperature=0.1`, `top_p=0.9`
- **Validation**: luacheck static analysis

---

## Makefile Targets

```bash
make setup          # create .venv, install runtime + dev deps
make check          # verify imports + luacheck
make run PROMPT="..." CTX='{"wf":{...}}'
make train          # QLoRA fine-tuning (requires CUDA GPU)
make export-model   # merge LoRA adapter + export to GGUF
make register-model # register GGUF with local Ollama
make eval           # smoke-test the fine-tuned model
```
