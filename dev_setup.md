# Dev Setup

## System Prerequisites

### macOS ARM (Apple Silicon)

```bash
# Python 3.13
brew install python@3.13

# luacheck (Lua static analysis)
brew install luacheck

# Ollama (model runtime)
brew install ollama
# Alternative: curl -fsSL https://ollama.com/install.sh | sh
```

### Ubuntu 22.04 / 24.04

```bash
# Python 3.13
# Ubuntu 24.04 — in main repos:
sudo apt-get install -y python3.13 python3.13-venv

# Ubuntu 22.04 — needs deadsnakes PPA:
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt-get update && sudo apt-get install -y python3.13 python3.13-venv

# luacheck
sudo apt-get install -y luarocks
sudo luarocks install luacheck

# Ollama
curl -fsSL https://ollama.com/install.sh | sh
```

---

## Project Setup (both platforms)

```bash
git clone <repo-url>
cd MTT26

make setup          # creates .venv, installs runtime + dev deps
source .venv/bin/activate
make check          # verifies imports and luacheck are working
```

---

## Pulling a Model

The fine-tuned model is registered after training (see training setup below).
For smoke-testing during development, pull a base code model:

```bash
make ollama-pull                     # pulls qwen2.5-coder:7b-instruct-q4_K_M by default
make ollama-pull MODEL=<other-tag>   # any Ollama model tag
```

Ollama must be running as a background service before starting the agent:

```bash
ollama serve &    # or: systemctl start ollama   (Ubuntu with systemd)
```

---

## Running the Agent

```bash
# Basic usage
python cli.py "Get the last email from wf.vars.emails"

# With wf context from file
python cli.py "Filter by Discount" --context context.json

# With inline context
python cli.py "Increment the counter" \
  --context-str '{"wf":{"vars":{"try_count_n":3}}}'

# Raw Lua output instead of JSON manifest
python cli.py "Get the last email" \
  --context-str '{"wf":{"vars":{"emails":["a@b.com"]}}}' \
  --lua

# Use fine-tuned model (after training)
python cli.py "..." --model localscript:latest

# All options
python cli.py --help
```

Full Makefile shortcut:

```bash
make run PROMPT="Get last email" CTX='{"wf":{"vars":{"emails":["a@b.com"]}}}'
```

---

## Training Setup

Training requires a Linux machine with NVIDIA GPU (≥16 GB VRAM) or Google Colab.
Do **not** run training on macOS — Unsloth requires CUDA.

```bash
# On Linux GPU machine:
pip install -r requirements-train.txt

# Generate data, train, export — see task_3.md and Makefile targets:
make generate-data ROLE=generator COUNT=50
make train
make export-model
make register-model
```

See `specs/task_3.md` for the full training workflow.

---

## Makefile Reference

| Target | Description |
|---|---|
| `make setup` | Create venv, install runtime + dev deps |
| `make check` | Verify imports and luacheck are on PATH |
| `make clean` | Remove venv and compiled Python files |
| `make ollama-pull` | Pull base model for smoke-testing |
| `make run PROMPT="..."` | Run the agent |
| `make lint FILE=x.lua` | Run luacheck on a Lua file |
| `make validate` | Check luacheck config works end-to-end |
