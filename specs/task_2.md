# Task 2 — Agent Skeleton, CLI, and Validation

## Goal

Implement the working agent skeleton: LangGraph graph, all three role nodes
(Analyst, Generator, Critic), the Ollama HTTP client, the luacheck validator,
the system prompts with few-shot examples, and the CLI entry point.

At the end of this task `python localscript/cli.py "..."` runs the full
generate → validate → retry loop against a locally-running Ollama instance
with any code model (not yet the fine-tuned one). The output is the Octapi
JSON manifest fragment.

The Docker image and REST API are **not** part of this task (see `TODO.md`).

---

## Prerequisites

- Task 1 completed: venv active, all stub files exist.
- Ollama installed and running (`ollama serve`).
- A base code model pulled for smoke-testing, e.g.:
  ```bash
  ollama pull qwen2.5-coder:7b-instruct-q4_K_M
  ```
  The fine-tuned model (`localscript:latest`) will replace this in Task 3.

---

## Steps

### 1. Implement `localscript/agent/llm.py`

Thin HTTP wrapper around Ollama's `/api/generate` endpoint.
No Ollama Python SDK — use `requests` directly to keep deps minimal.

Interface:

```python
def generate(prompt: str, system: str, model: str, num_ctx: int, num_predict: int) -> str:
    """Call Ollama and return the generated text. Raises on HTTP error."""
```

Hardcode the eval parameters as defaults:
- `num_ctx = 4096`
- `num_predict = 256`
- `temperature = 0.1`

Read `OLLAMA_HOST` from environment (default: `http://localhost:11434`).
This allows compose.yml to override it without code changes.

### 2. Populate `context/octapi_api.md`

Write the Octapi Lua sandbox reference that will be injected into every
Generator prompt. Extract from `specs/selected_scripts.md`. Must include:

- Lua version (5.x)
- Variable namespaces: `wf.vars.*`, `wf.initVariables.*`
- Custom globals: `_utils.array.new()`, `_utils.array.markAsArray(t)`
- Forbidden constructs: `require()`, `io.*`, `os.*`, JsonPath syntax
- Rule: all variables declared with `local`
- Rule: script must end with `return`
- 3 short examples (copy from `selected_scripts.md`): last-element,
  counter increment, array filter

Keep it under 400 tokens — it's injected in every Generator call.

### 3. Implement `localscript/agent/prompts.py`

Three functions, one per role. Each returns a `(system_prompt, few_shot_suffix)`
tuple.

```python
def analyst_prompt() -> tuple[str, str]: ...
def generator_prompt(context_doc: str) -> tuple[str, str]: ...
def critic_prompt() -> tuple[str, str]: ...
```

**Analyst system prompt rules:**
- Output exactly `PROCEED` if task is clear (has field names + operation + result shape).
- Output 1–3 short questions if unclear. No preamble.
- Maximum 1 clarification round. Lean strongly toward `PROCEED`.

**Generator system prompt rules:**
- Output ONLY raw Lua code. No markdown fences, no explanation.
- On retry: the previous lint errors are appended to the user turn, not the system prompt.

**Critic system prompt rules:**
- Output exactly `LGTM` if code looks correct.
- Otherwise list issues as `Line N: <problem>`. No extra text.
- The actual luacheck run happens separately — this is a semantic review
  that catches things luacheck misses (e.g. wrong `wf.vars.*` path).

Each prompt must include the `[ROLE: analyst/generator/critic]` tag as the
first line of the system prompt (needed for the fine-tuned model).

### 4. Implement the three nodes

**`localscript/agent/nodes/analyst.py`**

```python
def analyst_node(state: AgentState) -> AgentState:
    ...
```

- Build prompt from `state.user_prompt` + `state.wf_context`.
- Call `llm.generate()` with the analyst system prompt.
- Parse response:
  - If `PROCEED` → set `state.analyst_done = True`, return.
  - Otherwise → print questions to stdout, read one line of user input,
    append to `state.history`, loop (max 1 round, then force PROCEED).

**`localscript/agent/nodes/generator.py`**

```python
def generator_node(state: AgentState) -> AgentState:
    ...
```

- Build user turn: `state.user_prompt` + optional wf context JSON
  + clarification history + (on retry) previous lint errors.
- Inject `context/octapi_api.md` as part of the system prompt.
- Call `llm.generate()` with generator system prompt.
- Strip markdown fences from response (` ```lua ... ``` ` or plain ` ``` `).
- Store clean Lua in `state.script`.
- Increment `state.iterations`.

**`localscript/agent/nodes/critic.py`**

```python
def critic_node(state: AgentState) -> AgentState:
    ...
```

Two-stage validation:

1. **luacheck** (always runs):
   - Write `state.script` to a temp file.
   - Run `luacheck <tmpfile> --config .luacheckrc`.
   - Parse stdout for errors/warnings.

2. **LLM semantic review** (only if luacheck passes):
   - Call `llm.generate()` with critic system prompt + the script.
   - If response is not `LGTM`, treat non-fatal findings as warnings
     (print them, do not retry).

Store luacheck errors in `state.lint_errors`. If any errors exist,
set `state.done = False`. If luacheck clean, set `state.done = True`.

### 5. Implement `localscript/agent/validator.py`

```python
def run_luacheck(lua_code: str) -> list[str]:
    """Run luacheck on lua_code string. Return list of error strings."""
```

- Writes code to `tempfile.NamedTemporaryFile(suffix='.lua')`.
- Runs `luacheck <path> --config .luacheckrc --formatter plain`.
- Returns parsed error lines (empty list = clean).
- Raises `FileNotFoundError` with a helpful message if `luacheck` is not on PATH.

### 6. Implement `localscript/agent/graph.py`

```python
from langgraph.graph import StateGraph, END
from .nodes.analyst import analyst_node
from .nodes.generator import generator_node
from .nodes.critic import critic_node
from .state import AgentState

def build_graph(max_iter: int = 3) -> ...:
    graph = StateGraph(AgentState)
    graph.add_node("analyst", analyst_node)
    graph.add_node("generator", generator_node)
    graph.add_node("critic", critic_node)

    graph.set_entry_point("analyst")
    graph.add_edge("analyst", "generator")
    graph.add_edge("generator", "critic")
    graph.add_conditional_edges(
        "critic",
        lambda s: "done" if s["done"] or s["iterations"] >= max_iter else "retry",
        {"done": END, "retry": "generator"},
    )
    return graph.compile()
```

Define `AgentState` as a `TypedDict` in `localscript/agent/state.py`:

```python
class AgentState(TypedDict):
    user_prompt: str
    wf_context: dict | None
    history: list[str]
    script: str
    lint_errors: list[str]
    iterations: int
    done: bool
    extract_lua: bool          # True = print raw Lua; False = print JSON manifest
```

### 7. Implement `localscript/cli.py`

```python
#!/usr/bin/env python3
"""
LocalScript — Octapi Lua code generator.
Usage: python cli.py "Task description" [OPTIONS]
Run with --help for full options.
"""
import argparse, json, sys
from localscript.agent.graph import build_graph

def main():
    parser = argparse.ArgumentParser(
        description="Generate Octapi Lua scripts from natural language.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=EXAMPLES,
    )
    parser.add_argument("prompt", help="Task in Russian or English")
    parser.add_argument("--context", metavar="FILE",
                        help="JSON file with wf.vars / wf.initVariables context")
    parser.add_argument("--context-str", metavar="JSON",
                        help="Inline JSON context string")
    parser.add_argument("--key", default="result", metavar="NAME",
                        help="Field name in JSON output (default: result)")
    parser.add_argument("--lua", action="store_true",
                        help="Output raw Lua only, without the JSON wrapper")
    parser.add_argument("--max-iter", type=int, default=3, metavar="N",
                        help="Max generation retries (default: 3)")
    parser.add_argument("--verbose", action="store_true",
                        help="Show lint errors and iteration details")
    parser.add_argument("--model", default="localscript:latest", metavar="TAG",
                        help="Ollama model tag (default: localscript:latest)")
    args = parser.parse_args()

    # Load context
    wf_context = None
    if args.context:
        with open(args.context) as f:
            wf_context = json.load(f)
    elif args.context_str:
        wf_context = json.loads(args.context_str)

    # Run agent
    graph = build_graph(max_iter=args.max_iter)
    result = graph.invoke({
        "user_prompt": args.prompt,
        "wf_context": wf_context,
        "history": [],
        "script": "",
        "lint_errors": [],
        "iterations": 0,
        "done": False,
        "extract_lua": args.lua,
    })

    script = result["script"]
    if not script:
        print("[ERROR] No script generated.", file=sys.stderr)
        sys.exit(1)

    if args.verbose:
        print(f"[Info] Iterations: {result['iterations']}")
        if result["lint_errors"]:
            print("[Lint errors]")
            for e in result["lint_errors"]:
                print(f"  {e}")

    # Format output
    if args.lua:
        print(script)
    else:
        manifest = {args.key: f"lua{{{script}}}lua"}
        print(json.dumps(manifest, ensure_ascii=False, indent=2))

EXAMPLES = """
Examples:
  python cli.py "Get the last email from wf.vars.emails"
  python cli.py "Фильтр по Discount" --context context.json --verbose
  python cli.py "Increment try_count_n" --context-str '{"wf":{"vars":{"try_count_n":3}}}' --lua
"""

if __name__ == "__main__":
    main()
```

### 8. Add Makefile targets

Extend the Makefile from Task 1:

```makefile
MODEL ?= qwen2.5-coder:7b-instruct-q4_K_M   # override with make run MODEL=localscript:latest

.PHONY: ollama-pull run lint validate

## ollama-pull: pull the base model for smoke-testing
ollama-pull:
	ollama pull $(MODEL)

## run: run the agent (pass PROMPT="..." and optionally CTX="...")
run:
	$(VENV_BIN)/python localscript/cli.py $(PROMPT) \
	  $(if $(CTX),--context-str '$(CTX)',) \
	  --model $(MODEL) \
	  --verbose

## lint: run luacheck on a Lua file (pass FILE=path/to/script.lua)
lint:
	luacheck $(FILE) --config .luacheckrc

## validate: check that luacheck is on PATH and the config is valid
validate:
	luacheck --version
	$(VENV_BIN)/python -c "from localscript.agent.validator import run_luacheck; print(run_luacheck('return 1'))"
```

Usage examples to include in a Makefile comment:

```makefile
# make run PROMPT="Get last email" CTX='{"wf":{"vars":{"emails":["a@b.com"]}}}'
# make run PROMPT="Increment counter" MODEL=localscript:latest
# make lint FILE=/tmp/test.lua
```

---

## Smoke Test (Manual)

After implementing, run:

```bash
source .venv/bin/activate
ollama serve &          # if not already running as a service

make run PROMPT="Get the last email from the list" \
  CTX='{"wf":{"vars":{"emails":["a@b.com","b@c.com","c@d.com"]}}}'
```

Expected output (approximate):

```
[Analyst] PROCEED
[Generator] attempt 1/3...
[Critic] luacheck: 0 errors. ✓

{
  "result": "lua{return wf.vars.emails[#wf.vars.emails]}lua"
}
```

With `--lua`:
```
return wf.vars.emails[#wf.vars.emails]
```

---

## Acceptance Criteria

- [ ] `make validate` exits 0 (luacheck on PATH, validator importable)
- [ ] `make run PROMPT="Get last email" CTX='...'` produces valid JSON output
- [ ] `--lua` flag returns raw Lua without the JSON wrapper
- [ ] `--verbose` flag shows iteration count and lint errors
- [ ] `--help` output is human-readable and documents all flags with examples
- [ ] Agent retries on luacheck failure (inject a deliberately bad prompt to test)
- [ ] `OLLAMA_HOST` env var overrides the default `localhost:11434`
- [ ] Analyst asks a question if the prompt contains zero field names,
      then proceeds after one user reply
- [ ] No crash if `--context` and `--context-str` are both omitted

## What Is NOT Done Yet (intentional)

- Dockerfile and compose.yml (see `TODO.md`)
- Fine-tuned model — using base model for smoke tests only
- Full end-to-end eval against the hidden test set
- REST API (see `TODO.md`)
