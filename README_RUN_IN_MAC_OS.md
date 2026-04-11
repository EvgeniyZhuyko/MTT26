# Running LocalScript on macOS

Works on both Apple Silicon (M1/M2/M3) and Intel Macs.
Apple Silicon gets Metal GPU acceleration via Ollama — responses in 1–3 s.
Intel runs CPU-only — responses in 5–20 s depending on the chip.

---

## Option A — Docker (Rancher Desktop or Docker Desktop)

### Prerequisites

- [Rancher Desktop](https://rancherdesktop.io/) or [Docker Desktop](https://www.docker.com/products/docker-desktop/)
  — choose **dockerd (moby)** as the container runtime
- No NVIDIA GPU needed; Ollama inside the container runs CPU-only

### Step 1 — Remove the GPU block

Open `compose.yml` and delete the `deploy` section (macOS doesn't support NVIDIA
passthrough), so the `ollama` service looks like:

```yaml
  ollama:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    restart: unless-stopped
```

### Step 2 — Start

```bash
docker compose up --build
```

First run pulls the model (~800 MB). Ready when you see:

```
agent-1  | INFO:     Application startup complete.
```

### Step 3 — Test

```bash
curl http://localhost:8080/health
# {"status":"ok"}

curl -s -X POST http://localhost:8080/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Get the last email from the list",
    "context": {"wf": {"vars": {"emails": ["a@b.com", "b@c.com"]}}}
  }' | python3 -m json.tool
```

Interactive docs: `http://localhost:8080/docs`

---

## Option B — Native (no Docker)

Native Ollama uses Metal acceleration — faster than the Docker CPU path.

### Prerequisites

- Python 3.11+ (`brew install python` or pyenv)
- [Ollama for macOS](https://ollama.com/download/mac) — native app, ~100 MB
- `luacheck` for script validation (optional but recommended)

```bash
brew install ollama luacheck
```

### Step 1 — Pull the model

```bash
ollama pull andreysitaev/hkt_octapi_lua_mpl
ollama cp andreysitaev/hkt_octapi_lua_mpl localscript:latest

# Verify
ollama list
# NAME                  ID              SIZE    MODIFIED
# localscript:latest    ...             793 MB  just now
```

### Step 2 — Set up Python environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt fastapi "uvicorn[standard]"
```

### Step 3 — Start the API server

```bash
source .venv/bin/activate
uvicorn api:app --host 127.0.0.1 --port 8080
```

Ready when you see:
```
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8080
```

### Step 4 — Test

```bash
# Health check
curl http://localhost:8080/health
# {"status":"ok"}

# English prompt
curl -s -X POST http://localhost:8080/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Get the last email from the list",
    "context": {"wf": {"vars": {"emails": ["a@b.com", "b@c.com"]}}}
  }' | python3 -m json.tool

# Russian prompt
curl -s -X POST http://localhost:8080/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Увеличь счётчик попыток на 1",
    "context": {"wf": {"vars": {"try_count_n": 3}}}
  }' | python3 -m json.tool
```

Interactive docs: `http://localhost:8080/docs`

---

## CLI alternative (no API server needed)

```bash
source .venv/bin/activate

python cli.py "Get the last email from the list" \
  --context-str '{"wf":{"vars":{"emails":["a@b.com","b@c.com"]}}}'

python cli.py "Увеличь счётчик на 1" \
  --context-str '{"wf":{"vars":{"try_count_n":3}}}' --lua
```
