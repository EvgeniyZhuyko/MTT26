"""Analyst node — decides whether the task needs clarification."""

import json
import sys

from localscript.agent import llm
from localscript.agent.prompts import analyst_prompt
from localscript.agent.state import AgentState


def analyst_node(state: AgentState) -> dict:
    """Assess the task. Ask one round of clarifying questions if needed.

    Returns an updated slice of AgentState (LangGraph merges it in).
    """
    system, _ = analyst_prompt()
    user_turn = _build_user_turn(state)

    response = llm.generate(user_turn, system, state["model"])

    if _is_proceed(response):
        _log("Task is clear. Proceeding to generator.")
        return {}  # state unchanged — no clarification needed

    # --- Clarification round (max 1) ---
    _log("Clarification needed:")
    print(response, flush=True)
    print()

    try:
        answer = input("Your answer: ").strip()
    except EOFError:
        # Non-interactive mode (e.g. piped input) — skip clarification.
        _log("Non-interactive mode detected. Skipping clarification.")
        return {}

    history = list(state.get("history", []))
    history.append(f"Q: {response}")
    history.append(f"A: {answer}")

    return {"history": history}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _is_proceed(response: str) -> bool:
    return response.strip().upper() == "PROCEED"


def _build_user_turn(state: AgentState) -> str:
    parts = [f"Task: {state['user_prompt']}"]

    if state.get("wf_context"):
        ctx_str = json.dumps(state["wf_context"], ensure_ascii=False, indent=2)
        parts.append(f"Context:\n{ctx_str}")

    return "\n\n".join(parts)


def _log(msg: str) -> None:
    print(f"[Analyst] {msg}", file=sys.stderr, flush=True)
