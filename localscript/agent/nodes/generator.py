"""Generator node — produces raw Lua code."""

import json
import re
import sys

from localscript.agent import llm
from localscript.agent.prompts import generator_prompt
from localscript.agent.state import AgentState


def generator_node(state: AgentState) -> dict:
    """Generate (or regenerate) Lua code.

    On the first call the user turn contains the task + context.
    On retries it also includes the previous lint errors to guide correction.
    """
    iteration = state.get("iterations", 0) + 1
    _log(f"Generating... (attempt {iteration}/{{max}})")

    system, _ = generator_prompt()
    user_turn = _build_user_turn(state)

    raw = llm.generate(user_turn, system, state["model"])
    script = _strip_fences(raw)

    return {
        "script": script,
        "iterations": iteration,
        "done": False,
        "lint_errors": [],
    }


# ── Helpers ────────────────────────────────────────────────────────────────────

def _build_user_turn(state: AgentState) -> str:
    parts: list[str] = []

    # Clarification history (if analyst asked questions)
    if state.get("history"):
        history_block = "\n".join(state["history"])
        parts.append(f"Clarification:\n{history_block}")

    # wf context
    if state.get("wf_context"):
        ctx_str = json.dumps(state["wf_context"], ensure_ascii=False, indent=2)
        parts.append(f"Context:\n{ctx_str}")

    parts.append(f"Task: {state['user_prompt']}")

    # Previous lint errors (retry path)
    if state.get("lint_errors"):
        error_block = "\n".join(state["lint_errors"])
        parts.append(
            f"Your previous attempt had these errors. Fix them:\n{error_block}"
        )

    return "\n\n".join(parts)


# Match ```lua ... ``` or plain ``` ... ``` blocks.
_FENCE_RE = re.compile(r"```(?:lua)?\s*\n?(.*?)```", re.DOTALL)


def _strip_fences(text: str) -> str:
    """Remove markdown code fences, return the inner code."""
    m = _FENCE_RE.search(text)
    if m:
        return m.group(1).strip()
    return text.strip()


def _log(msg: str) -> None:
    print(f"[Generator] {msg}", file=sys.stderr, flush=True)
