# Running LocalScript on Ubuntu — CPU only

Use this if you have no NVIDIA GPU or no NVIDIA Container Toolkit installed.
Generation is slower (~5–20 s per request) but fully functional.

---

## Prerequisites

- Docker + Docker Compose (`apt install docker.io docker-compose-v2`)
- No NVIDIA anything required

---

## Step 1 — Start the stack

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
agent-1  | INFO:     Application startup complete.
```

---

## Step 3 — Test

Open the chat UI at **http://localhost:8081** or use curl:

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
