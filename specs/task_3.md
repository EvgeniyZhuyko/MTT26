# Task 3 — Training Data, Fine-Tuning, and Model Export

## Goal

Produce a fine-tuned `localscript:latest` Ollama model and wire it into the
agent built in Task 2.

By end of this task:
- `data/` contains 200–500 JSONL examples across all three roles.
- `training/train.py` fine-tunes `Qwen2.5-Coder-7B-Instruct` with QLoRA on a
  Linux CUDA machine or Google Colab.
- `training/merge_export.py` converts the result to GGUF and registers it with
  Ollama.
- `make run MODEL=localscript:latest PROMPT="..."` runs the fine-tuned model.
- A Colab notebook (`.ipynb`) wraps the training steps for convenience.

---

## Prerequisites

- Task 2 completed and smoke-tested against a base model.
- **For training only**: Linux machine with NVIDIA GPU (≥16 GB VRAM recommended
  for 7B QLoRA), CUDA 12.x, Python 3.13.
- **For inference**: any machine with Ollama installed (macOS ARM works fine).
- `llama.cpp` built locally **or** available via Docker (for GGUF conversion).
  See platform notes in §5.

---

## Steps

### 1. Seed dataset — extract from `selected_scripts.md`

Create `data/seeds/generator_seeds.jsonl` with the 8 examples from
`specs/selected_scripts.md` converted to the training JSONL format.

Each example has:

```json
{
  "instruction": "[ROLE: generator]\n\n<octapi_api_rules>\n...\n</octapi_api_rules>\n\nContext:\n{...wf JSON...}\n\nTask: <user request in original language>",
  "output": "<raw Lua code>"
}
```

The `<octapi_api_rules>` block is the condensed version of
`context/octapi_api.md` (same text injected at inference time).

Create `data/seeds/analyst_seeds.jsonl` with 3 hand-crafted examples:
- One clearly underspecified prompt → 2 questions
- One borderline prompt → 1 question
- One clear prompt → `PROCEED`

Create `data/seeds/critic_seeds.jsonl` with 3 hand-crafted examples:
- Take a generator seed, introduce a bug (e.g. missing `local`) → `Line N: ...`
- Take a clean generator output → `LGTM`

### 2. Write `data/generate_data.py` — prompt template approach

The script generates more training examples by printing ChatGPT-ready prompts
to stdout. The user pastes them into ChatGPT, saves the responses into files,
and the script converts them to JSONL.

**Two modes:**

```bash
# Mode 1: print prompts to paste into ChatGPT
python data/generate_data.py prompts --role generator --count 50

# Mode 2: convert saved ChatGPT responses to JSONL
python data/generate_data.py convert --role generator \
    --input data/raw/generator_responses.txt \
    --output data/generator_data.jsonl
```

**`prompts` mode** — print to stdout, one per numbered block:

```
=== Prompt 1 / 50 ===
Generate a training example for an Octapi Lua code generator.

Rules for the Lua code:
- Variables are in wf.vars.* or wf.initVariables.*
- Use _utils.array.new() for arrays
- No require(), io.*, os.*
- Declare locals with `local`
- End with `return`

Create a task in Russian or English that requires Lua to:
[variation]

Return a JSON object with keys "instruction" and "output".
The instruction must include the wf context JSON.
The output must be only the Lua code.
```

Variation pool (cycle through randomly, seed with `--seed N`):
- filter an array by a field value
- access a nested field at depth 3–4
- increment or decrement a numeric counter
- check if a field is nil or empty string
- convert a string field to uppercase/lowercase
- concatenate two string fields with a separator
- compute the length of an array
- clear specific keys from each object in an array
- format a date string (YYYYMMDD → YYYY-MM-DD)
- iterate and build a new filtered array

For `analyst` role: variations are vague prompts (no field names).
For `critic` role: variations are Lua snippets with one introduced bug.

**`convert` mode** — parse numbered blocks from the saved text file
(one JSON object per block), validate the keys, write JSONL.

```python
def validate_example(obj: dict, role: str) -> bool:
    """Return True if the example looks valid for the given role."""
```

### 3. Build the combined training dataset

```bash
python data/generate_data.py prompts --role generator --count 200
# paste prompts into ChatGPT → save responses to data/raw/generator_responses.txt

python data/generate_data.py convert \
    --role generator \
    --input data/raw/generator_responses.txt \
    --output data/generator_data.jsonl

# Repeat for analyst (50 examples) and critic (50 examples)
python data/generate_data.py prompts --role analyst --count 50
python data/generate_data.py prompts --role critic  --count 50
```

Also merge in the Roblox/luau_corpus filtered subset
(~100 clean, short Lua examples without Luau-specific syntax):

```bash
python data/filter_luau_corpus.py \
    --output data/luau_supplement.jsonl \
    --max 100
```

`filter_luau_corpus.py` uses `datasets.load_dataset("Roblox/luau_corpus")`,
filters for examples shorter than 200 tokens, strips any that contain
`task.`, `game.`, `::`, or Luau type annotations, and wraps them in the
`[ROLE: generator]` format.

Final merge:

```bash
python data/merge_datasets.py \
    data/seeds/generator_seeds.jsonl \
    data/generator_data.jsonl \
    data/seeds/analyst_seeds.jsonl \
    data/analyst_data.jsonl \
    data/seeds/critic_seeds.jsonl \
    data/critic_data.jsonl \
    data/luau_supplement.jsonl \
    --output data/train.jsonl \
    --shuffle --seed 42
```

`merge_datasets.py` concatenates, deduplicates by `instruction` hash,
shuffles, and writes `data/train.jsonl`.

### 4. Write `training/train.py`

QLoRA fine-tune using Unsloth:

```python
from unsloth import FastLanguageModel
from datasets import load_dataset
from trl import SFTTrainer
from transformers import TrainingArguments

BASE_MODEL   = "Qwen/Qwen2.5-Coder-7B-Instruct"
MAX_SEQ_LEN  = 1024
OUTPUT_DIR   = "training/checkpoints"
DATASET_PATH = "data/train.jsonl"

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name=BASE_MODEL,
    max_seq_length=MAX_SEQ_LEN,
    load_in_4bit=True,
)

model = FastLanguageModel.get_peft_model(
    model,
    r=16,
    target_modules=["q_proj", "v_proj", "k_proj", "o_proj",
                    "gate_proj", "up_proj", "down_proj"],
    lora_alpha=16,
    lora_dropout=0,
    bias="none",
    use_gradient_checkpointing="unsloth",
)

def format_example(row):
    return {"text": f"<|system|>{row['instruction']}<|assistant|>{row['output']}<|endoftext|>"}

dataset = load_dataset("json", data_files=DATASET_PATH, split="train")
dataset = dataset.map(format_example)

trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=dataset,
    dataset_text_field="text",
    max_seq_length=MAX_SEQ_LEN,
    args=TrainingArguments(
        output_dir=OUTPUT_DIR,
        num_train_epochs=3,
        per_device_train_batch_size=2,
        gradient_accumulation_steps=4,
        learning_rate=2e-4,
        fp16=True,
        logging_steps=10,
        save_strategy="epoch",
        report_to="none",
    ),
)
trainer.train()
model.save_pretrained(f"{OUTPUT_DIR}/final")
tokenizer.save_pretrained(f"{OUTPUT_DIR}/final")
print(f"Saved to {OUTPUT_DIR}/final")
```

Run:
```bash
python training/train.py
```

### 5. Write `training/merge_export.py`

Merges the LoRA adapter into the base weights, saves as HuggingFace format,
then converts to GGUF.

```python
from unsloth import FastLanguageModel

CHECKPOINT = "training/checkpoints/final"
HF_MERGED  = "training/merged"
GGUF_PATH  = "training/localscript-q4_k_m.gguf"

model, tokenizer = FastLanguageModel.from_pretrained(CHECKPOINT, load_in_4bit=False)
model.save_pretrained_merged(HF_MERGED, tokenizer, save_method="merged_16bit")
print(f"Merged model saved to {HF_MERGED}")

# GGUF conversion — requires llama.cpp convert script on PATH
import subprocess, sys
result = subprocess.run([
    sys.executable, "llama.cpp/convert_hf_to_gguf.py",
    HF_MERGED,
    "--outtype", "q4_k_m",
    "--outfile", GGUF_PATH,
], check=True)
print(f"GGUF saved to {GGUF_PATH}")
```

**Platform note for llama.cpp:**

```bash
# Clone and build llama.cpp (one-time, on the training machine)
git clone https://github.com/ggerganov/llama.cpp.git
cd llama.cpp && make -j$(nproc)
pip install -r requirements.txt    # for convert_hf_to_gguf.py
```

On macOS ARM, `make` produces a Metal-accelerated binary. On Linux, use
`make LLAMA_CUDA=1` if CUDA conversion is needed (optional for this step).

### 6. Write `training/Modelfile`

```
FROM ./localscript-q4_k_m.gguf
PARAMETER num_ctx      4096
PARAMETER num_predict  256
PARAMETER temperature  0.1
PARAMETER top_p        0.9
SYSTEM """You are a Lua code generator for the Octapi LowCode platform.
Output only Lua code. No markdown fences. No explanation."""
```

Register with Ollama:

```bash
cd training
ollama create localscript -f Modelfile
ollama list    # confirm localscript:latest appears
```

### 7. Write `training/localscript_train.ipynb`

Colab notebook with the following cells:

1. **Setup** — install Unsloth, clone repo, mount Google Drive
2. **Dataset** — upload `data/train.jsonl` or generate on-the-fly
3. **Train** — inline version of `train.py`
4. **Export** — inline version of `merge_export.py` (GGUF conversion)
5. **Download** — download the GGUF file to local machine
6. **Register** — instructions: copy GGUF to local machine, run
   `ollama create localscript -f Modelfile`

The notebook should be runnable top-to-bottom with no manual steps
except providing the dataset file.

### 8. Add Makefile targets

```makefile
.PHONY: generate-data train export-model register-model eval

## generate-data: print ChatGPT prompt templates to stdout
generate-data:
	$(VENV_BIN)/python data/generate_data.py prompts \
	    --role $(ROLE) --count $(COUNT)
# Usage: make generate-data ROLE=generator COUNT=50

## convert-data: convert raw ChatGPT responses to JSONL
convert-data:
	$(VENV_BIN)/python data/generate_data.py convert \
	    --role $(ROLE) \
	    --input data/raw/$(ROLE)_responses.txt \
	    --output data/$(ROLE)_data.jsonl
# Usage: make convert-data ROLE=generator

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

## train: run QLoRA fine-tuning (requires CUDA)
train:
	$(VENV_BIN)/pip install -r requirements-train.txt
	$(VENV_BIN)/python training/train.py

## export-model: merge adapter + convert to GGUF
export-model:
	$(VENV_BIN)/python training/merge_export.py

## register-model: register GGUF with Ollama as localscript:latest
register-model:
	cd training && ollama create localscript -f Modelfile
	ollama list

## eval: smoke-test the fine-tuned model
eval:
	make run MODEL=localscript:latest \
	    PROMPT="Get the last email from the list" \
	    CTX='{"wf":{"vars":{"emails":["a@b.com","b@c.com"]}}}'
```

---

## End-to-End Flow Summary

```
1.  make generate-data ROLE=generator COUNT=200
    → paste printed prompts into ChatGPT
    → save responses to data/raw/generator_responses.txt

2.  make convert-data ROLE=generator
3.  (repeat steps 1–2 for analyst and critic roles)

4.  make merge-data
    → produces data/train.jsonl (~300–500 examples)

5.  make train                     # on Linux GPU / Colab
6.  make export-model              # on same machine
7.  scp training/localscript-q4_k_m.gguf <local>:~/  # copy GGUF to local machine

8.  make register-model            # on local machine (Ollama installed)
9.  make eval                      # smoke test
```

---

## What Is Intentionally Left Unfinished

- **Dockerfile and compose.yml** — not part of this task; see `TODO.md`.
- **Automated data generation** via OpenAI API — prompt-template approach only;
  see `TODO.md` for the automated option.
- **Eval harness** — no automated scoring against a held-out set yet.
- **CLI polish** — the interface from Task 2 is functional but may need
  README improvements before final submission.

---

## Acceptance Criteria

- [ ] `data/seeds/` contains 14 hand-crafted JSONL examples (8 generator + 3 analyst + 3 critic)
- [ ] `make generate-data ROLE=generator COUNT=5` prints 5 numbered prompt blocks
- [ ] `make convert-data ROLE=generator` produces valid JSONL from a sample response file
- [ ] `make merge-data` produces `data/train.jsonl` with no duplicate instructions
- [ ] `make train` starts and runs at least 1 step without error (on CUDA machine)
- [ ] `make export-model` produces `training/localscript-q4_k_m.gguf`
- [ ] `make register-model` registers `localscript:latest` in `ollama list`
- [ ] `make eval` returns a valid JSON manifest fragment using the fine-tuned model
- [ ] `training/localscript_train.ipynb` runs cell-by-cell on Google Colab
      (T4 runtime) without errors
