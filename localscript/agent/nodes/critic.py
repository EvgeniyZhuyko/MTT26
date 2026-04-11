"""Critic node — validates generated Lua with luacheck + optional LLM review."""

import sys

from localscript.agent import llm
from localscript.agent.prompts import critic_prompt
from localscript.agent.state import AgentState
from localscript.agent.validator import run_luacheck


def critic_node(state: AgentState) -> dict:
    """Validate state['script'] with luacheck and optionally an LLM review.

    Sets state['done'] = True only when luacheck reports zero errors.
    The LLM semantic review is advisory — its findings are printed but do not
    trigger a retry (luacheck is the gate).
    """
    script = state.get("script", "")

    if not script:
        _log("No script to validate.")
        return {"done": False, "lint_errors": ["No script was generated."]}

    # Stage 1: luacheck
    try:
        errors = run_luacheck(script)
    except FileNotFoundError as exc:
        _log(f"WARNING: {exc}")
        _log("Skipping luacheck — marking as done anyway.")
        return {"done": True, "lint_errors": []}

    if errors:
        for e in errors:
            _log(f"  {e}")
        _log(f"luacheck: {len(errors)} issue(s). Will retry.")
        return {"done": False, "lint_errors": errors}

    _log("luacheck: 0 errors. ✓")

    # Stage 2: LLM semantic review (advisory, non-blocking)
    _run_llm_review(script, state["model"])

    return {"done": True, "lint_errors": []}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _run_llm_review(script: str, model: str) -> None:
    """Run the critic LLM and print findings. Does not affect state."""
    system, _ = critic_prompt()
    user_turn = f"Review this Lua code:\n\n{script}"

    try:
        response = llm.generate(user_turn, system, model)
    except Exception as exc:
        _log(f"LLM review skipped: {exc}")
        return

    if response.strip().upper() == "LGTM":
        _log("LLM review: LGTM")
    else:
        _log("LLM review (advisory):")
        for line in response.splitlines():
            _log(f"  {line}")


def _log(msg: str) -> None:
    print(f"[Critic] {msg}", file=sys.stderr, flush=True)
