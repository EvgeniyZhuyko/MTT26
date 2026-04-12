# LocalScript — Makefile
# Platform: macOS ARM or Linux Ubuntu
# Prerequisites: python3.13, luacheck, ollama
# See dev_setup.md for installation instructions.
#
# Quick start:
#   make setup
#   source .venv/bin/activate
#   make run PROMPT="Get last email" CTX='{"wf":{"vars":{"emails":["a@b.com"]}}}'

PYTHON   := python3.13
VENV     := .venv
VENV_BIN := $(VENV)/bin

MODEL ?= qwen2.5-coder:7b-instruct-q4_K_M
ROLE  ?= generator
COUNT ?= 50

.PHONY: setup check clean ollama-pull run lint validate \
        generate-data convert-data auto-data synthesize merge-data \
        train export-model register-model eval \
        chat-build

# ── Setup ──────────────────────────────────────────────────────────────────────

## setup: create venv and install runtime + dev dependencies
setup: $(VENV_BIN)/activate

$(VENV_BIN)/activate:
	$(PYTHON) -m venv $(VENV)
	$(VENV_BIN)/pip install --upgrade pip
	$(VENV_BIN)/pip install -r requirements.txt -r requirements-dev.txt
	@echo ""
	@echo "Venv ready. Activate with: source $(VENV)/bin/activate"

## check: verify key packages are importable and luacheck is on PATH
check:
	$(VENV_BIN)/python -c "import langgraph, requests; print('Python deps: OK')"
	luacheck --version | head -1
	@echo "All checks passed."

## clean: remove venv and compiled Python files
clean:
	rm -rf $(VENV)
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true

# ── Model ──────────────────────────────────────────────────────────────────────

## ollama-pull: pull a model for smoke-testing (default: qwen2.5-coder:7b)
## Usage: make ollama-pull MODEL=<tag>
ollama-pull:
	ollama pull $(MODEL)

# ── Chat app ───────────────────────────────────────────────────────────────────

## chat-build: build the chat Docker image
chat-build:
	docker build -t localscript-chat ./chat

# ── Run ────────────────────────────────────────────────────────────────────────

## run: run the agent
## Usage: make run PROMPT="Task description" [CTX='{"wf":{...}}'] [MODEL=tag]
run:
	$(VENV_BIN)/python cli.py "$(PROMPT)" \
	  $(if $(CTX),--context-str '$(CTX)',) \
	  --model $(MODEL) \
	  --verbose

# ── Validation ─────────────────────────────────────────────────────────────────

## lint: run luacheck on a Lua file
## Usage: make lint FILE=/path/to/script.lua
lint:
	luacheck $(FILE) --config .luacheckrc

## validate: verify luacheck config and Python validator work end-to-end
validate:
	luacheck --version
	$(VENV_BIN)/python -c \
	  "from localscript.agent.validator import run_luacheck; \
	   errs = run_luacheck('return 1'); \
	   print('luacheck validator: OK (errors:', errs, ')')"

# ── Training data ──────────────────────────────────────────────────────────────

OPENAI_MODEL ?= gpt-4o-mini

## generate-data: print ChatGPT prompt templates to stdout (manual mode)
## Paste the output into ChatGPT, save responses to data/raw/$(ROLE)_responses.txt,
## then run: make convert-data ROLE=$(ROLE)
## Usage: make generate-data ROLE=generator COUNT=50
generate-data:
	$(VENV_BIN)/python data/generate_data.py prompts \
	    --role $(ROLE) --count $(COUNT)

## convert-data: convert saved ChatGPT responses to JSONL
## Usage: make convert-data ROLE=generator
##   (reads data/raw/$(ROLE)_responses.txt, writes data/$(ROLE)_data.jsonl)
convert-data:
	$(VENV_BIN)/python data/generate_data.py convert \
	    --role $(ROLE) \
	    --input data/raw/$(ROLE)_responses.txt \
	    --output data/$(ROLE)_data.jsonl

## auto-data: generate data automatically via OpenAI API
## Requires: OPENAI_API_KEY env var set
## Usage: make auto-data ROLE=generator COUNT=50 [OPENAI_MODEL=gpt-4o-mini]
auto-data:
	$(VENV_BIN)/python data/generate_data.py auto \
	    --role $(ROLE) --count $(COUNT) \
	    --output data/$(ROLE)_data.jsonl \
	    --openai-model $(OPENAI_MODEL)

PER_TEMPLATE ?= 15

## synthesize: generate deterministic Lua training data (no LLM required)
## Usage: make synthesize [PER_TEMPLATE=20]
synthesize:
	$(VENV_BIN)/python data/synthesize.py \
	    --output data/generator_data.jsonl \
	    --per-template $(PER_TEMPLATE)

## merge-data: merge all JSONL files into data/train.jsonl
merge-data:
	$(VENV_BIN)/python data/merge_datasets.py \
	    data/seeds/generator_seeds.jsonl \
	    data/generator_data.jsonl \
	    data/seeds/analyst_seeds.jsonl \
	    data/analyst_data.jsonl \
	    data/seeds/critic_seeds.jsonl \
	    data/critic_data.jsonl \
	    --output data/train.jsonl --shuffle --seed 42

# ── Training ───────────────────────────────────────────────────────────────────

## train: run QLoRA fine-tuning (requires CUDA — Linux GPU / Colab only)
train:
	$(VENV_BIN)/pip install -r requirements-train.txt
	$(VENV_BIN)/python training/train.py

## export-model: merge LoRA adapter and convert to GGUF
export-model:
	$(VENV_BIN)/python training/merge_export.py

## register-model: register the GGUF with Ollama as localscript:latest
register-model:
	cd training && ollama create localscript -f Modelfile
	ollama list

## eval: smoke-test the fine-tuned model end-to-end
eval:
	$(MAKE) run MODEL=localscript:latest \
	    PROMPT="Get the last email from the list" \
	    CTX='{"wf":{"vars":{"emails":["a@b.com","b@c.com"]}}}'
