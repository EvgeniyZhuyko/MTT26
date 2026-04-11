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

# Lua statement starters — any line beginning with one of these is actual code.
_LUA_START_RE = re.compile(
    r"^(local\b|return\b|if\b|for\b|while\b|function\b|do\b|--|wf\b)",
    re.MULTILINE,
)


def _strip_fences(text: str) -> str:
    """Extract Lua code from raw model output.

    1. If markdown fences are present, return the fenced content.
    2. Otherwise find the first line that starts with a Lua keyword and
       return everything from that line to the end.  This handles the case
       where a completion model outputs a short text preamble before the code.
    """
    m = _FENCE_RE.search(text)
    if m:
        return m.group(1).strip()
    # Look for first real Lua line.
    start = _LUA_START_RE.search(text)
    if start:
        return text[start.start():].strip()
    return text.strip()


def _log(msg: str) -> None:
    print(f"[Generator] {msg}", file=sys.stderr, flush=True)
