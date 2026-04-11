# Running LocalScript on macOS

Works on both Apple Silicon (M1/M2/M3) and Intel Macs.
Apple Silicon gets Metal GPU acceleration via Ollama — responses in 1–3 s.
Intel runs CPU-only — responses in 5–20 s depending on the chip.

No Docker required.

---

## Prerequisites

- Python 3.11+ (`brew install python` or pyenv)
- [Ollama for macOS](https://ollama.com/download/mac) — native app, ~100 MB
- `luacheck` for script validation (optional but recommended)

```bash
brew install ollama luacheck
```

---

## Step 1 — Get the model file

The GGUF is not in the repository. Obtain `training/localscript-q4_k_m.gguf`
by one of these methods:

**Option A — download from the person who trained it.**
Copy the 755 MB file into the `training/` directory of this repo.

**Option B — run the Colab notebook yourself.**
Open `training/localscript_train.ipynb` in Google Colab with a T4 GPU runtime
(free tier), run all cells, download `localscript-q4_k_m.gguf`, place it in
`training/`.

**Option C — train locally (requires any CUDA GPU, not typical on Mac).**
```bash
pip install -r requirements-train.txt
python training/train.py
python training/merge_export.py
```

---

## Step 2 — Register the model with Ollama

```bash
# Start the Ollama background service (if not already running)
ollama serve &

# Register the fine-tuned model
cd training
ollama create localscript -f Modelfile
cd ..

# Verify
ollama list
# NAME                  ID              SIZE    MODIFIED
# localscript:latest    ...             755 MB  just now
```

---

## Step 3 — Set up Python environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt fastapi "uvicorn[standard]"
```

---

## Step 4 — Start the API server

```bash
source .venv/bin/activate
uvicorn api:app --host 127.0.0.1 --port 8080
```

The server is ready when you see:
```
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8080
```

---

## Step 5 — Test

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
