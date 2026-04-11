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

## Step 1 — Get the model file

The GGUF is not in the repository. Place `training/localscript-q4_k_m.gguf`
(755 MB) in the `training/` directory before starting Docker.

**Option A — download from the person who trained it.**

**Option B — run the Colab notebook.**
Open `training/localscript_train.ipynb` in Google Colab (T4 GPU, free tier),
run all cells, download `localscript-q4_k_m.gguf` into `training/`.

**Option C — train locally on this machine.**
```bash
pip install -r requirements-train.txt
python training/train.py          # ~5 min on a T4-class GPU
python training/merge_export.py   # merges LoRA + exports to GGUF
```

> `merge_export.py` needs llama.cpp built once:
> ```bash
> git clone https://github.com/ggerganov/llama.cpp.git
> pip install -r llama.cpp/requirements.txt
> cd llama.cpp && cmake -B build && cmake --build build --target llama-quantize -j$(nproc)
> ```

---

## Step 2 — Start the stack

`compose.yml` already has the GPU block enabled — no changes needed.

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
restarts — model registration is skipped on the second run.

---

## Troubleshooting

**`docker: Error response from daemon: could not select device driver "nvidia"`**
The NVIDIA Container Toolkit is not configured. Re-run the setup from the
Prerequisites section and restart Docker.

**`[entrypoint] WARNING: GGUF not found`**
The `training/localscript-q4_k_m.gguf` file is missing. Follow Step 1.
The API will start but `/generate` will return 503 until the model is registered.

**Ollama keeps restarting**
Check GPU memory: `nvidia-smi`. The 1B Q4_K_M model needs ~1.5 GB VRAM —
any modern NVIDIA card handles it. If VRAM is exhausted by another process,
stop it first.
