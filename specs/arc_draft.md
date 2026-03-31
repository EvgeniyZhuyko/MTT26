# LocalScript — Architecture Draft

## Purpose

LocalScript is a fully local agent system that generates, validates, and iterates on **Lua code** used within the MWS Octapi Event Mesh platform — specifically for data transformation, filtering, and routing logic inside adapters/manifests. It runs on a lightweight local LLM, ensuring **no data leaves the machine**.

---

## Context: Where Lua Fits in Octapi

In Octapi's Event Mesh, data flows through a 4-step pipeline: receive → standardize → buffer (Kafka) → filter/transform. The filter/transform step executes custom logic — this is where **Lua scripts** live. They handle:

- **Transformations** — reshaping payloads (JSON↔XML, field mapping, enrichment)
- **Filters** — selecting messages by attributes (region, type, metadata)
- **Routing rules** — content-based routing decisions (CBR)
- **Validators** — checking message schema/integrity before forwarding

These scripts are referenced by the manifest and executed by adapters at runtime on Apache Flink.

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────┐
│                      User / CLI                         │
│  (task prompt, manifest context, sample data)           │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│                   Agent Orchestrator                    │
│                                                         │
│  Manages the generate → validate → fix loop.            │
│  Decides when output is ready or needs another pass.    │
│  Holds conversation state and retry budget.             │
└───┬──────────────┬──────────────────┬───────────────────┘
    │              │                  │
    ▼              ▼                  ▼
┌────────┐  ┌────────────┐  ┌──────────────────┐
│  Code  │  │  Lua       │  │  Context         │
│  Gen   │  │  Validator  │  │  Provider        │
│  (LLM) │  │  (local)   │  │  (local files)   │
└────────┘  └────────────┘  └──────────────────┘
```

### Components

#### 1. Agent Orchestrator

The central loop controller. Receives a task (natural-language prompt + optional context), drives the generation/validation cycle, and returns the final Lua script.

Responsibilities:
- Parse and enrich the user prompt with relevant context
- Call the LLM for code generation
- Send generated code to the Validator
- If validation fails: feed errors back to the LLM for a fix attempt
- Enforce a retry budget (e.g., max 5 iterations) to avoid infinite loops
- Return the final script or a failure report

#### 2. Code Generator (Local LLM)

A small, quantized language model running locally (e.g., CodeLlama 7B, DeepSeek-Coder 6.7B, or similar). It receives a structured prompt containing:

- The user's task description
- Relevant Octapi context (manifest snippet, schema, sample data)
- Lua API reference (available functions, libraries)
- Previous validation errors (on retry)

Output: a Lua code block.

Requirements:
- Must run fully offline (llama.cpp, Ollama, or similar runtime)
- Quantized to fit in ≤16 GB RAM (Q4/Q5 GGUF)
- Structured prompting via system/user message format

#### 3. Lua Validator

A local validation pipeline that checks the generated code **without executing it against live data**. Stages:

| Stage | Tool | Checks |
|-------|------|--------|
| **Syntax** | `luacheck` / Lua parser | Parse errors, undefined globals |
| **Static analysis** | `luacheck` with config | Unused variables, type mismatches, style |
| **Sandbox execution** | Lua 5.x interpreter | Run against sample input/output fixtures |
| **Schema conformance** | Custom checker | Output matches expected JSON/XML schema |

Returns a structured report: `{ pass: bool, errors: [{ line, message, severity }] }`.

#### 4. Context Provider

Loads and indexes local reference material so the LLM has domain knowledge without internet access.

Sources (stored locally in the project):
- **Lua API reference** — available functions in the Octapi Lua sandbox (I/O, JSON, XML libs)
- **Manifest examples** — sample manifests showing how Lua scripts are referenced
- **Schema catalog** — JSON/AsyncAPI schemas for common message types
- **Code snippets** — proven patterns (filter-by-region, XML-to-JSON, etc.)

Retrieval: simple keyword/embedding search over these docs (can use a lightweight local embedding model or just TF-IDF).

---

## Agent Loop — Step by Step

```
1. User submits task
   "Filter Kafka messages: keep only region=MSK, transform to XML"

2. Context Provider retrieves
   - Lua sandbox API reference
   - filter + XML transform snippet templates
   - Relevant manifest fragment

3. Orchestrator builds prompt
   System: "You are a Lua code generator for Octapi Event Mesh..."
   User: task + context + output format instructions

4. LLM generates Lua code

5. Validator runs all stages
   → If PASS: return code to user
   → If FAIL: extract errors, append to prompt, go to step 4
      (up to N retries)

6. Final output: validated Lua script + validation report
```

---

## Project Structure (Proposed)

```
localscript/
├── agent/
│   ├── orchestrator.py       # Main loop controller
│   ├── llm_client.py         # Interface to local LLM (Ollama/llama.cpp)
│   ├── prompt_builder.py     # Assembles structured prompts
│   └── config.py             # Model params, retry budget, paths
├── validator/
│   ├── syntax_check.py       # Lua syntax validation
│   ├── static_analysis.py    # luacheck wrapper
│   ├── sandbox_runner.py     # Execute Lua with sample fixtures
│   └── schema_check.py       # Validate output shape
├── context/
│   ├── loader.py             # Load and index reference docs
│   ├── retriever.py          # Search relevant context for a prompt
│   └── data/
│       ├── lua_api.md        # Octapi Lua sandbox reference
│       ├── manifests/        # Example manifests
│       ├── schemas/          # JSON / AsyncAPI schemas
│       └── snippets/         # Reusable Lua patterns
├── cli.py                    # Command-line entry point
├── requirements.txt
└── README.md
```

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Fully local** | Core requirement — no data leaves the machine. Enables use with sensitive manifests and schemas. |
| **Small LLM (≤13B params)** | Must run on a developer laptop. Bigger models don't justify the cost for focused Lua generation. |
| **Generate-validate loop** | LLMs make mistakes. Automated validation + retry dramatically increases first-pass success. |
| **Lua sandbox for testing** | Real execution against fixtures catches logic errors that static analysis misses. |
| **Prompt includes API reference** | The LLM has no internet — it needs the Octapi Lua API injected in-context. |
| **Python orchestrator** | Ecosystem support (Ollama bindings, subprocess for Lua tools, JSON handling). |

---

## What We Don't Know Yet (Pending API Spec)

These items are blocked until the Octapi Lua API specification is available:

- Exact list of built-in Lua functions available in the sandbox
- Manifest format for referencing Lua scripts
- Input/output data envelope structure (headers, payload shape)
- Available libraries (cjson, xml2lua, etc.) and their versions
- Error handling conventions (return codes vs. exceptions)
- Constraints: max script size, execution timeout, memory limits

Once the API spec arrives, these unknowns will directly shape the **Context Provider data** and the **Validator's schema checks**.

---

## Risks

| Risk | Mitigation |
|------|------------|
| Local LLM quality too low for Lua | Use code-specialized models; augment with strong few-shot examples |
| Octapi Lua sandbox has unusual constraints | Validator catches issues; API reference keeps the LLM aligned |
| Validate-fix loop doesn't converge | Retry budget + fallback to human review with error report |
| Context window too small for complex tasks | Chunk context; prioritize most relevant snippets via retrieval |
