# Running LocalScript on Ubuntu — CPU only

Use this if you have no NVIDIA GPU or no NVIDIA Container Toolkit installed.
Generation is slower (~5–20 s per request) but fully functional.

---

## Prerequisites

- Docker + Docker Compose (`apt install docker.io docker-compose-v2`)
- No NVIDIA anything required

---

## Step 1 — Get the model file

The GGUF is not in the repository. Place `training/localscript-q4_k_m.gguf`
(755 MB) in the `training/` directory before starting Docker.

**Option A — download from the person who trained it.**

**Option B — run the Colab notebook.**
Open `training/localscript_train.ipynb` in Google Colab (T4 GPU, free tier),
run all cells, download `localscript-q4_k_m.gguf` into `training/`.

**Option C — train locally (requires a CUDA GPU on another machine).**
```bash
pip install -r requirements-train.txt
python training/train.py
python training/merge_export.py
```

---

## Step 2 — Remove the GPU block from compose.yml

Open `compose.yml` and delete the `deploy` section under the `ollama` service
so it looks like this:

```yaml
  ollama:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    restart: unless-stopped
```

The four lines to remove:
```yaml
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
```

---

## Step 3 — Start the stack

```bash
docker compose up --build
```

First run downloads the `ollama/ollama` image and builds the agent image —
allow 3–5 minutes. Subsequent starts take under a minute.

**Ready when you see:**
```
agent_1  | [entrypoint] Starting API server on :8080 ...
```

---

## Step 4 — Test

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

## Stopping

```bash
docker compose down
```

Model weights are cached in the `ollama_data` Docker volume and survive
restarts — model registration is skipped on the second run.
