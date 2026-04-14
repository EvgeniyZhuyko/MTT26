from typing import TypedDict


class AgentState(TypedDict):
    user_prompt: str
    wf_context: dict | None       # parsed wf.vars / wf.initVariables JSON
    history: list[str]            # clarification turns: ["Q: ...", "A: ..."]
    script: str                   # last generated Lua code (raw, no fences)
    lint_errors: list[str]        # luacheck error lines from last critic pass
    iterations: int               # number of generator calls so far
    done: bool                    # True when critic is satisfied
    extract_lua: bool             # CLI flag: True = print raw Lua, False = JSON manifest
    model: str                    # Ollama model tag
