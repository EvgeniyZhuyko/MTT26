# Running LocalScript on Ubuntu — CPU only

Use this if you have no NVIDIA GPU or no NVIDIA Container Toolkit installed.
Generation is slower (~5–20 s per request) but fully functional.

---

## Prerequisites

- Docker + Docker Compose (`apt install docker.io docker-compose-v2`)
- No NVIDIA anything required

---

## Step 1 — Remove the GPU block from compose.yml

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

The lines to remove:
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

## Step 2 — Start the stack

```bash
docker compose up --build
```

The first run:
1. Downloads the `ollama/ollama` image and builds the agent image (~3–5 min)
2. Pulls the fine-tuned model automatically from Ollama Hub:
   [`andreysitaev/hkt_octapi_lua_mpl`](https://ollama.com/andreysitaev/hkt_octapi_lua_mpl) (~800 MB, once)

On subsequent runs everything is cached and startup takes under a minute.

**Ready when you see:**
```
agent_1  | [entrypoint] Starting API server on :8080 ...
```

---

## Step 3 — Test

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
restarts — the pull is skipped on the second run.
