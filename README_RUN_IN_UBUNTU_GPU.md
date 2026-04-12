# Running LocalScript on Ubuntu — NVIDIA GPU

Full-speed setup. The Ollama container uses the GPU for inference —
typical response time 0.5–2 s.

---

## Prerequisites

| Requirement | Install |
|---|---|
| Docker + Docker Compose | `apt install docker.io docker-compose-v2` |
| NVIDIA driver ≥ 525 | `ubuntu-drivers install` or from [nvidia.com](https://www.nvidia.com/drivers) |
| NVIDIA Container Toolkit | see below |

### Install NVIDIA Container Toolkit

```bash
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
  | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
  | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
  | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt update && sudo apt install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

Verify:
```bash
docker run --rm --gpus all nvidia/cuda:12.0-base-ubuntu22.04 nvidia-smi
# Should print your GPU name and driver version.
```

---

## Step 1 — Uncomment the GPU block in compose.yml

Open `compose.yml` and uncomment the `deploy` section under the `ollama` service:

```yaml
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
```

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
agent-1  | INFO:     Application startup complete.
```

---

## Step 2 — Test

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

---

## Troubleshooting

**`docker: Error response from daemon: could not select device driver "nvidia"`**
The NVIDIA Container Toolkit is not configured. Re-run the setup from the
Prerequisites section and restart Docker.

**Ollama keeps restarting**
Check GPU memory: `nvidia-smi`. The 1B Q4_K_M model needs ~1.5 GB VRAM —
any modern NVIDIA card handles it. If VRAM is exhausted by another process,
stop it first.
