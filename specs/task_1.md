# Task 1 — Folder Structure, Boilerplate, Dev Setup

## Goal

Create the full project skeleton as specified in `refined_architecture.md`,
write `dev_setup.md` with human-readable setup instructions for macOS ARM and
Ubuntu, and produce a `Makefile` covering the initial setup targets.

At the end of this task the repo compiles, the venv is functional, and
`make setup` works end-to-end on both platforms.

There is no runnable agent code yet — only empty modules, placeholder files,
and configuration.

---

## Prerequisites

- Git repo already initialised (this repo).
- Python 3.13 available on the target machine (see platform notes below).
- No prior virtualenv exists in the project.

---

## Steps

### 1. Create the directory tree

```
localscript/
├── agent/
│   └── nodes/
├── context/
├── data/
│   └── seeds/
├── training/
specs/          ← already exists
```

Each leaf directory must contain a `.gitkeep` so it is tracked by git.

### 2. Create placeholder Python modules

Create empty `__init__.py` files in every Python package:

```
localscript/agent/__init__.py
localscript/agent/nodes/__init__.py
```

Create stub files (just a module-level docstring, no implementation):

```
localscript/agent/graph.py
localscript/agent/nodes/analyst.py
localscript/agent/nodes/generator.py
localscript/agent/nodes/critic.py
localscript/agent/llm.py
localscript/agent/prompts.py
localscript/agent/validator.py
localscript/cli.py
```

### 3. Create `requirements.txt`

Runtime deps for the agent (no training libraries):

```
langgraph>=0.2
langchain-core>=0.3
requests>=2.32        # Ollama HTTP client
```

Pin to compatible minor versions once confirmed working.

### 4. Create `requirements-dev.txt`

```
-r requirements.txt
pytest>=8.0
```

### 5. Create `requirements-train.txt`

Training deps — only installed on the Linux GPU machine or Colab:

```
unsloth
torch
transformers
datasets
peft
trl
bitsandbytes
```

> Note: `unsloth` requires CUDA. Do not install on macOS ARM.

### 6. Create `.luacheckrc`

```lua
globals = { "wf", "_utils" }
ignore  = { "611", "612" }   -- trailing whitespace warnings
max_line_length = false
```

Place at the project root (not inside `localscript/`).

### 7. Create `.gitignore`

```
.venv/
__pycache__/
*.pyc
*.pyo
*.gguf
*.safetensors
.env
*.ipynb_checkpoints/
```

### 8. Write `dev_setup.md`

See the detailed content requirements in the section below.

### 9. Write the `Makefile`

See the detailed content requirements in the section below.

### 10. Verify

```bash
make setup          # creates venv, installs deps
make check          # python -c "import langgraph; import requests"
```

Both must exit 0 on macOS ARM and Ubuntu.

---

## `dev_setup.md` Content Requirements

The file must cover:

### System prerequisites

**macOS ARM (Apple Silicon)**

```bash
# Python 3.13
brew install python@3.13

# luacheck (for Lua static analysis)
brew install luacheck

# Ollama (for running the model at runtime)
brew install ollama
# or: curl -fsSL https://ollama.com/install.sh | sh
```

**Ubuntu 22.04 / 24.04**

```bash
# Python 3.13
# Ubuntu 24.04 — available in main repos:
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

### Project setup (both platforms)

```bash
git clone <repo-url>
cd MTT26

make setup        # creates .venv, installs requirements.txt + requirements-dev.txt
source .venv/bin/activate
make check        # verifies imports work
```

### Notes

- Training (`requirements-train.txt`) is intentionally **not** installed by
  `make setup` — see `task_3.md` for training setup.
- Ollama must be running as a background service (`ollama serve`) before
  running the agent. The `make run` target (Task 2) starts it automatically
  if not already running.
- The fine-tuned model is not pulled in this task. Model setup is covered in Task 3.

---

## `Makefile` Targets for This Task

```makefile
PYTHON   := python3.13
VENV     := .venv
VENV_BIN := $(VENV)/bin

# Detect OS for platform-specific steps
UNAME := $(shell uname -s)

.PHONY: setup check clean

## setup: create venv and install runtime + dev dependencies
setup: $(VENV)/bin/activate

$(VENV)/bin/activate:
	$(PYTHON) -m venv $(VENV)
	$(VENV_BIN)/pip install --upgrade pip
	$(VENV_BIN)/pip install -r requirements.txt -r requirements-dev.txt
	@echo "Venv ready. Run: source $(VENV)/bin/activate"

## check: verify that key packages are importable
check:
	$(VENV_BIN)/python -c "import langgraph, requests; print('OK')"

## clean: remove venv and compiled Python files
clean:
	rm -rf $(VENV) __pycache__ localscript/__pycache__
	find . -name "*.pyc" -delete
```

### Platform note in Makefile

Add a comment block near the top:

```makefile
# Platform: macOS ARM or Linux Ubuntu
# Prerequisites: python3.13, luacheck, ollama
# See dev_setup.md for installation instructions.
```

---

## Acceptance Criteria

- [ ] `make setup` runs clean on macOS ARM (no errors)
- [ ] `make setup` runs clean on Ubuntu (no errors)
- [ ] `make check` prints `OK` after setup
- [ ] `make clean` removes `.venv` and caches without errors
- [ ] All stub files exist and are importable (no syntax errors)
- [ ] `.luacheckrc` and `.gitignore` are at repo root
- [ ] `dev_setup.md` covers both platforms end-to-end
- [ ] No training deps installed by `make setup`
