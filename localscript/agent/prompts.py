"""System prompts for all three agent roles.

Each function returns a (system_prompt, few_shot_note) tuple.
The few_shot_note is appended to the user turn during prompt assembly
and may be empty when few-shot examples are already in the system prompt.
"""

from pathlib import Path

# Load the Octapi Lua sandbox reference once at import time.
_API_DOC_PATH = Path(__file__).parents[2] / "context" / "octapi_api.md"

def _load_api_doc() -> str:
    if _API_DOC_PATH.exists():
        return _API_DOC_PATH.read_text(encoding="utf-8")
    return "(Octapi API reference not found — see context/octapi_api.md)"

_API_DOC = _load_api_doc()


# ── Analyst ────────────────────────────────────────────────────────────────────

_ANALYST_SYSTEM = """\
[ROLE: analyst]

You assess whether a Lua code generation task is specific enough to act on.

A task is CLEAR if it names:
- the source variable path (e.g. wf.vars.emails, wf.initVariables.recallTime)
- the operation to perform (filter, transform, extract, etc.)
- the expected result shape

A task is UNCLEAR if it lacks field names, data shape, or the transformation logic.

Rules:
- If CLEAR: respond with exactly one word: PROCEED
- If UNCLEAR: ask 1–3 short, specific questions. No preamble, no explanation.
- Lean strongly toward PROCEED. Only ask if genuinely missing critical info.
- Never ask more than 3 questions.
"""


def analyst_prompt() -> tuple[str, str]:
    return _ANALYST_SYSTEM, ""


# ── Generator ──────────────────────────────────────────────────────────────────

# This text must match the `instruction` field used in training data exactly.
# The model is a completion model — deviating from the training format causes
# it to generate text continuations instead of Lua code.
_GENERATOR_SYSTEM = """\
[ROLE: generator]

Octapi Lua Sandbox:
- Lua 5.x. Variables: wf.vars.* or wf.initVariables.*
- New array: _utils.array.new(). Mark array: _utils.array.markAsArray(t)
- Forbidden: require(), io.*, os.*, JsonPath syntax
- Declare all variables with `local`. End with `return`.
Output ONLY raw Lua. No fences, no explanation."""


def generator_prompt() -> tuple[str, str]:
    return _GENERATOR_SYSTEM, ""


# ── Critic ─────────────────────────────────────────────────────────────────────

_CRITIC_SYSTEM = """\
[ROLE: critic]

You review Lua code written for the Octapi LowCode platform.

Check for:
1. Variables accessed via wf.vars.* or wf.initVariables.* (never as bare names)
2. Arrays built with _utils.array.new() where a new array is returned
3. All variables declared with `local`
4. Script ends with `return`
5. No forbidden calls: require(), io.*, os.*

Rules:
- If the code is correct: respond with exactly one word: LGTM
- If there are issues: list them as "Line N: <problem>". One issue per line.
  Be concise. Do not repeat the code. Do not explain.
"""


def critic_prompt() -> tuple[str, str]:
    return _CRITIC_SYSTEM, ""
