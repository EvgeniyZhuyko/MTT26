# TODO — Deferred Work

Items explicitly deferred from Tasks 1–3. Pick these up after the core
training loop is working.

---

## High Priority (needed for final submission)

### Dockerfile and compose.yml

The Docker image is required by the hackathon jury for reproducible evaluation.
See `refined_architecture.md §11` for the full spec.

Steps:
1. Write `Dockerfile` (python:3.13-slim base, install luacheck + Ollama).
2. Write `compose.yml` with two services: `ollama` + `agent`.
3. Add `make docker-build` and `make docker-run` to `Makefile`.
4. Verify on macOS ARM and Ubuntu that `docker compose up` produces the same
   output as the native `make run`.

Key issue to resolve: the fine-tuned GGUF must either be baked into the image
(large image) or mounted as a volume / pulled at container startup via
`ollama pull localscript:latest`. Decide based on whether the model is
published to a registry.

---

### README for jury

Write a `README.md` at the repo root (replace the placeholder from the
hackathon organizers) covering:

- One-line description
- `ollama pull localscript:latest` (exact tag)
- Runtime parameters used at eval: `num_ctx=4096`, `num_predict=256`,
  `batch=1`, `parallel=1`
- `make setup && make run PROMPT="..."` quick-start
- Docker quick-start: `docker compose up`
- All CLI flags documented with examples
- Architecture overview (1 paragraph, link to `specs/refined_architecture.md`)

---

## Medium Priority (quality improvements)


### Eval harness

A script that runs the agent against the 8 seed examples and scores:
- luacheck pass/fail for each output
- Exact or fuzzy match against the expected output from `selected_scripts.md`

```bash
python data/eval.py --model localscript:latest
```

Useful for comparing model quality across training iterations.

---

### REST API

The file `specs_russian/localscript-openapi.yaml` defines a `POST /generate`
endpoint at `localhost:8080`. Implement if the jury evaluates via HTTP:

- Use FastAPI.
- Request body: `{"prompt": "...", "context": {...}}` (context is optional, added beyond the spec).
- Response: `{"code": "<raw Lua>"}` (per spec) or optionally JSON manifest format.
- Add `make serve` target: `uvicorn localscript.api:app --port 8080`.
- Update `compose.yml` to expose port 8080.

---

## Low Priority (nice to have)

### Luau corpus filtering improvements

`data/filter_luau_corpus.py` currently uses a simple keyword blocklist for
Luau-specific syntax. A better approach: run `luacheck` on each example and
only keep those with zero errors under the Octapi `.luacheckrc` config.

### Multi-round clarification (Analyst)

Currently the Analyst asks at most 1 round of questions before forcing
`PROCEED`. A proper implementation would support configurable rounds and
track full conversation history for the Generator context.

### Streaming output

`num_predict=256` is the eval constraint but the CLI could support
`--stream` for longer local sessions (not used at eval time).
