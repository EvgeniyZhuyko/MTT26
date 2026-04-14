# LocalScript — Refined Architecture

## 1. What We're Actually Building

A local CLI tool that accepts a natural-language task (RU or EN) plus an optional
`wf` context JSON, and returns a working Lua snippet for the Octapi LowCode platform.

The system runs a **single fine-tuned LLM** through a **three-node LangGraph agent**:
`Analyst → Generator → Critic`. No data leaves the machine at runtime.

---

## 2. Constraints That Shape Every Decision

| Constraint | Value | Impact |
|---|---|---|
| VRAM | ≤ 8 GB, no CPU offload | Limits model to Q4-quantized ≤7B |
| `num_ctx` | 4096 | Context window for all roles |
| `num_predict` | 256 | Hard output cap — no streaming |
| `batch` / `parallel` | 1 / 1 | One request at a time |
| Runtime | Ollama only | One `ollama pull <tag>` at eval |
| Python | 3.13 | All agent code |
| Validation | `luacheck` only | No Lua sandbox or test execution |

The 256-token output limit is tight but workable for most Octapi scripts
(the 8 examples in `selected_scripts.md` range from ~10 to ~250 tokens).
Complex scripts (e.g. ISO→UNIX conversion) will be truncated by the evaluator's
runner — this is accepted as a hackathon trade-off.

---

## 3. Octapi Lua Sandbox API (Ground Truth)

Extracted from `selected_scripts.md`. This is what the model must know and the
`luacheck` config must allow.

**Lua version:** 5.x

**Variable namespaces:**
- `wf.vars.*` — all LowCode workflow variables
- `wf.initVariables.*` — variables passed at workflow start

**Custom globals:**
- `_utils.array.new()` — create a new array-typed table
- `_utils.array.markAsArray(t)` — mark existing table as array

**Restrictions (must not appear in generated code):**
- No JsonPath syntax (`$.field`, `$['field']`)
- No `require()`, `io.*`, `os.*`, `dofile()`, `loadfile()` (sandbox)
- All variables accessed via `wf.vars.*` or `wf.initVariables.*` — never as bare names

**Output format (both forms accepted by CLI, see §8):**

*Raw Lua* — returned as-is:
```lua
return wf.vars.emails[#wf.vars.emails]
```

*JSON/manifest fragment* — wrapped in Octapi format:
```json
{"lastEmail": "lua{return wf.vars.emails[#wf.vars.emails]}lua"}
```

The CLI will output raw Lua by default and optionally wrap in JSON with `--json` flag.

---

## 4. Model Choice

**Base model: `Qwen/Qwen2.5-Coder-7B-Instruct`**

Rationale:
- Best-in-class code generation at 7B scale (outperforms CodeLlama, DeepSeek-Coder 6.7B on most code benchmarks)
- Native multilingual support — handles Russian task descriptions without translation
- Q4_K_M quantized GGUF ≈ 4.1 GB VRAM → leaves 3.9 GB headroom within the 8 GB limit
- Available on HuggingFace for Unsloth fine-tuning

**Ollama tag after fine-tuning:** `localscript:latest`

**Fallback base (if VRAM is tighter than expected):**
`Qwen/Qwen2.5-Coder-3B-Instruct` → ~2.0 GB VRAM, slightly lower quality.

---

## 5. Three Roles, One Model

Rather than three separate LoRA adapters (impossible to hot-swap in Ollama),
all three roles are trained into a **single fine-tuned model** using a role tag
in the system prompt. LangGraph selects the role at each node.

| Role | System prompt tag | What it does |
|---|---|---|
| Analyst | `[ROLE: analyst]` | Detects underspecified prompts, asks 1–3 clarifying questions |
| Generator | `[ROLE: generator]` | Produces Lua code given task + context |
| Critic | `[ROLE: critic]` | Reviews code for correctness, style, and Octapi constraints |

The LangGraph hint from the original spec likely refers to using LangGraph's
`StateGraph` to route between these roles — not literal adapter management.
With Ollama, role switching is just a different system prompt string.

---

## 6. Agent Architecture (LangGraph)

### 6.1 State

```python
class AgentState(TypedDict):
    user_prompt: str          # original task
    wf_context: dict | None   # parsed wf.vars / wf.initVariables JSON
    history: list[str]        # conversation turns (for clarification round)
    script: str               # last generated Lua code
    lint_errors: list[str]    # luacheck output
    iterations: int           # generation retries
    done: bool
    extract_lua: bool         # format flag: strip JSON wrapper on output
```

### 6.2 Graph

```
START
  │
  ▼
┌───────────┐  prompt clear  ┌───────────┐
│  Analyst  │ ─────────────► │ Generator │
└───────────┘                └─────┬─────┘
      │                            │
      │ unclear                    ▼
      │                      ┌───────────┐
      ▼                      │  Critic   │
  CLI output:                └─────┬─────┘
  questions →                      │
  wait for user                    │ pass
  re-enter loop                    ▼
                               CLI output:
                               Lua script
                                    │
                               fail + iter < 3
                                    │
                                    └──► Generator (retry with errors)
                                          │
                                     iter ≥ 3
                                          ▼
                                     CLI output:
                                     best attempt + warning
```

### 6.3 Nodes

**Analyst node**

Prompt: `[ROLE: analyst]` + task + context.
Decision: if the task mentions specific field names, types, and transformation
logic → proceed to Generator. If too vague (no field names, no data shape) →
output clarifying questions to CLI, read user's answers, append to `history`,
re-evaluate. Maximum 1 clarification round (hackathon scope).

**Generator node**

Prompt: `[ROLE: generator]` + Octapi API reference snippet + wf context +
task (+ history if clarification happened + previous lint errors on retry).
Output: raw Lua code block. The node strips any markdown fences.

**Critic node**

Runs `luacheck` with a custom `.luacheckrc` that declares `wf`, `_utils` as
known globals. Parses stdout into structured errors. If zero errors → done.
If errors exist → feeds them back to Generator (up to 3 total iterations).

---

## 7. Validation Pipeline

Only `luacheck`. No Lua interpreter, no sandbox, no test execution.

**`.luacheckrc`** (committed to repo):
```lua
globals = { "wf", "_utils" }
ignore = { "611", "612" }   -- whitespace warnings
max_line_length = false
```

**Critic output format** passed to Generator on retry:
```
Line 3: accessing undefined global 'req' (use wf.vars.req)
Line 7: variable 'result' never used
```

---

## 8. CLI Interface

```
python cli.py "Задача на русском или English" [OPTIONS]

Options:
  --context FILE    Path to JSON file with wf.vars / wf.initVariables context
  --context-str STR Inline JSON string (alternative to --context)
  --key NAME        Field name to use in JSON output (default: "result")
  --lua             Extract and print raw Lua only, without the JSON wrapper
  --max-iter N      Max generation retries (default: 3)
  --verbose         Show lint errors and iteration count
  --model TAG       Ollama model tag (default: localscript:latest)
```

Default output is the Octapi JSON manifest fragment (`{"key": "lua{...}lua"}`).
Use `--lua` to get raw Lua code only — useful for debugging or piping elsewhere.

**Example session (default — JSON manifest):**

```
$ python cli.py "Отфильтруй элементы с Discount или Markdown" \
    --context-str '{"wf":{"vars":{"parsedCsv":[...]}}}'

[Analyst] Task is clear. Proceeding.
[Generator] Generating... (attempt 1/3)
[Critic] luacheck: 0 errors. ✓

--- Output ---
{
  "result": "lua{\nlocal result = _utils.array.new()\nlocal items = wf.vars.parsedCsv\n\nfor _, item in ipairs(items) do\n  if (item.Discount ~= \"\" and item.Discount ~= nil) or\n     (item.Markdown ~= \"\" and item.Markdown ~= nil) then\n    table.insert(result, item)\n  end\nend\n\nreturn result\n}lua"
}
```

**With `--lua` (raw Lua only):**

```
$ python cli.py "Отфильтруй элементы с Discount или Markdown" \
    --context-str '{"wf":{"vars":{"parsedCsv":[...]}}}' --lua

[Analyst] Task is clear. Proceeding.
[Generator] Generating... (attempt 1/3)
[Critic] luacheck: 0 errors. ✓

--- Output ---
local result = _utils.array.new()
local items = wf.vars.parsedCsv

for _, item in ipairs(items) do
  if (item.Discount ~= "" and item.Discount ~= nil) or
     (item.Markdown ~= "" and item.Markdown ~= nil) then
    table.insert(result, item)
  end
end

return result
```

---

## 9. Training Pipeline

Training runs **outside Docker** (Google Colab, local GPU, or any machine with
sufficient VRAM). The result is a merged model converted to GGUF and registered
as an Ollama model.

### 9.1 Dataset Strategy

**Three datasets, one combined training run:**

| File | Role | Size target | Source |
|---|---|---|---|
| `data/generator_data.jsonl` | generator | 200–500 examples | 8 existing + generated variants |
| `data/analyst_data.jsonl` | analyst | 100–200 examples | Synthetic dialogues |
| `data/critic_data.jsonl` | critic | 100–200 examples | Buggy variants of generator examples |

**Supplementary:** filter ~100 examples from `Roblox/luau_corpus` — short,
clean Lua patterns (array iteration, string ops, table manipulation) that
transfer to the Octapi idiom. Exclude Luau-specific syntax (type annotations,
`task.*`, `game.*`).

**JSONL format (all datasets):**

```json
{
  "instruction": "[ROLE: generator]\n\nOctapi Lua sandbox rules:\n- Variables in wf.vars.* or wf.initVariables.*\n- Use _utils.array.new() for new arrays\n- No require(), io.*, os.*\n\nContext:\n{\"wf\":{\"vars\":{\"emails\":[\"a@b.com\",\"c@d.com\"]}}}\n\nTask: Get the last email from the list.",
  "output": "return wf.vars.emails[#wf.vars.emails]"
}
```

### 9.2 Data Generation Script

`data/generate_data.py` — uses the OpenAI-compatible API (ChatGPT, or any
locally-running large model) to generate variants from the 8 seed examples.

Strategies for generator data:
- Rephrase the task in Russian / English
- Change field names and data shapes
- Combine two operations (filter + transform)
- Add edge cases (nil checks, empty arrays)

Strategies for critic data:
- Take a generator example → introduce a bug (missing `local`, wrong field path,
  using `req` instead of `wf.vars.req`, calling `require("json")`)
- Output: description of the error and the corrected line

### 9.3 Fine-Tuning

**Stack:** Unsloth + QLoRA

```python
# training/train.py  (sketch)
from unsloth import FastLanguageModel

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="Qwen/Qwen2.5-Coder-7B-Instruct",
    max_seq_length=1024,     # sufficient for our examples
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
)
```

Training data: merged shuffled JSONL from all three role files.

Recommended Colab config: Tesla T4 (15 GB VRAM), ~1–2 hours for 500 examples.

### 9.4 Export to Ollama

```
# training/merge_export.py
1. Merge LoRA adapter into base weights (Unsloth built-in)
2. Save as HuggingFace safetensors
3. Convert to GGUF Q4_K_M via llama.cpp convert script
4. Register with Ollama:
   ollama create localscript -f training/Modelfile
```

**`training/Modelfile`:**
```
FROM ./localscript-q4_k_m.gguf
PARAMETER num_ctx 4096
PARAMETER num_predict 256
PARAMETER temperature 0.1
SYSTEM "You are a Lua code generator for the Octapi LowCode platform. Always follow the Octapi Lua sandbox rules."
```

---

## 10. Project Structure

```
localscript/
├── agent/
│   ├── graph.py              # LangGraph StateGraph definition
│   ├── nodes/
│   │   ├── analyst.py        # Analyst node: clarification detection
│   │   ├── generator.py      # Generator node: Lua code production
│   │   └── critic.py         # Critic node: luacheck wrapper
│   ├── llm.py                # Ollama HTTP client (requests, no SDK needed)
│   └── prompts.py            # System prompts + few-shot examples per role
├── context/
│   └── octapi_api.md         # Lua sandbox reference injected into prompts
├── data/
│   ├── generate_data.py      # Synthetic data generation script
│   ├── generator_data.jsonl  # (generated / hand-crafted)
│   ├── analyst_data.jsonl
│   └── critic_data.jsonl
├── training/
│   ├── train.py              # Unsloth QLoRA fine-tune
│   ├── merge_export.py       # Merge adapter → GGUF → Ollama
│   └── Modelfile             # Ollama model definition
├── .luacheckrc               # luacheck globals config
├── cli.py                    # CLI entry point
├── Dockerfile
├── compose.yml
├── requirements.txt
└── README.md
```

---

## 11. Docker

### Dockerfile

```dockerfile
FROM python:3.13-slim

# Install system deps
RUN apt-get update && apt-get install -y \
    curl luarocks \
    && luarocks install luacheck \
    && rm -rf /var/lib/apt/lists/*

# Install Ollama
RUN curl -fsSL https://ollama.com/install.sh | sh

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 11434

ENTRYPOINT ["python", "cli.py"]
```

### compose.yml

Two services: one for Ollama (model server), one for the agent.
The agent service depends on Ollama being healthy.

```yaml
services:
  ollama:
    image: ollama/ollama
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:11434/api/tags"]
      interval: 5s
      timeout: 3s
      retries: 10

  agent:
    build: .
    depends_on:
      ollama:
        condition: service_healthy
    environment:
      - OLLAMA_HOST=http://ollama:11434
    volumes:
      - .:/app
    stdin_open: true
    tty: true

volumes:
  ollama_data:
```

---

## 12. Prompt Design

Prompts are assembled in `agent/prompts.py`. Each role gets a fixed system
prompt and 2–3 few-shot examples drawn from `selected_scripts.md`.

**Generator system prompt (condensed):**

```
[ROLE: generator]

You generate Lua code for the Octapi LowCode platform.

Rules:
- Lua 5.x only
- Variables live in wf.vars.* or wf.initVariables.*
- To create an array: _utils.array.new()
- To mark a table as array: _utils.array.markAsArray(t)
- Never use: require(), io.*, os.*, JsonPath syntax
- All local variables must be declared with `local`
- End with `return <value>`
- Output ONLY the Lua code. No markdown, no explanation.

Example:
Task: Get the last email from wf.vars.emails
Context: {"wf":{"vars":{"emails":["a@b.com","c@d.com"]}}}
Output:
return wf.vars.emails[#wf.vars.emails]
```

**Analyst system prompt (condensed):**

```
[ROLE: analyst]

You decide if a Lua code generation task is clear enough to proceed.

A task is CLEAR if it names: the source variable (wf.vars.*), the operation,
and the expected result shape.

A task is UNCLEAR if it lacks field names, data shape, or transformation logic.

If CLEAR: respond with exactly: PROCEED
If UNCLEAR: respond with 1–3 specific questions. No more.
```

**Critic system prompt (condensed):**

```
[ROLE: critic]

You review Lua code for the Octapi LowCode platform.

Check:
1. All variables accessed via wf.vars.* or wf.initVariables.* (never bare)
2. Arrays created with _utils.array.new() where needed
3. All variables declared with `local`
4. Script ends with `return`

If correct: respond with exactly: LGTM
If issues found: list them as "Line N: <problem>". Be concise.
```

---

## 13. Output Format

Default output is the Octapi JSON manifest fragment `{"key": "lua{...}lua"}`.

The `--lua` flag extracts only the raw Lua body — implemented as a trivial
post-processing step in `cli.py`:

```python
import re

def extract_lua(json_output: str) -> str:
    match = re.search(r'lua\{(.*?)\}lua', json_output, re.DOTALL)
    return match.group(1).strip() if match else json_output
```

This means the Generator is always trained to output raw Lua internally;
the JSON wrapping (`lua{...}lua`) is applied by the CLI as formatting,
not by the model. This keeps the model output clean and avoids wasting
tokens on JSON boilerplate within the 256-token budget.

---

## 14. Iteration Workflow

```
Iteration 0 (bootstrap)
  └─ hand-craft 8 generator examples from selected_scripts.md
  └─ generate 50 analyst + 50 critic examples via ChatGPT
  └─ fine-tune base model
  └─ test locally → identify failure modes

Iteration 1+
  └─ generate more examples targeting failure modes
  └─ re-fine-tune (can start from previous checkpoint)
  └─ repeat until luacheck pass rate is acceptable on local test set

Final
  └─ merge + export GGUF
  └─ build Docker image
  └─ write README with: ollama pull localscript:latest + run instructions
```

---

## 15. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| 256-token limit truncates complex scripts | Train on concise examples; teach model to prefer compact idioms |
| `luacheck` false positives on `wf`/`_utils` | `.luacheckrc` declares them as globals |
| Analyst asks questions at eval time, stalling evaluation | Analyst threshold tuned to lean toward PROCEED unless clearly missing info |
| Roblox/luau_corpus introduces Luau-specific syntax | Filter examples: exclude any with `::`, `task.`, `game.`, type annotations |
| GGUF conversion changes model behavior | Keep merged HF checkpoint; re-quantize if quality drops |
| Single `num_predict=256` blocks multi-turn generation | Architecture uses multiple LLM calls (each 256 tokens), not multi-turn single call |
