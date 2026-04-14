#!/usr/bin/env python3
"""
Generate training data for LocalScript fine-tuning.

Three modes:
  prompts  — print numbered prompt blocks to stdout (paste into ChatGPT)
  convert  — parse saved ChatGPT responses into JSONL
  auto     — call OpenAI API directly (requires OPENAI_API_KEY)

Usage:
  python data/generate_data.py prompts --role generator --count 50
  python data/generate_data.py convert --role generator \\
      --input data/raw/generator_responses.txt --output data/generator_data.jsonl
  python data/generate_data.py auto --role generator --count 50 \\
      --output data/generator_data.jsonl
"""

import argparse
import json
import os
import random
import re
import sys
import time
from pathlib import Path

# ── Role definitions ───────────────────────────────────────────────────────────

# Fixed instruction prefix per role — added to every generated example.
_INSTRUCTIONS: dict[str, str] = {
    "generator": (
        "[ROLE: generator]\n\n"
        "Octapi Lua Sandbox:\n"
        "- Lua 5.x. Variables: wf.vars.* or wf.initVariables.*\n"
        "- New array: _utils.array.new(). Mark array: _utils.array.markAsArray(t)\n"
        "- Forbidden: require(), io.*, os.*, JsonPath syntax\n"
        "- Declare all variables with `local`. End with `return`.\n"
        "Output ONLY raw Lua. No fences, no explanation."
    ),
    "analyst": (
        "[ROLE: analyst]\n\n"
        "Assess if a Lua generation task is specific enough to act on.\n"
        "CLEAR = names field paths (wf.vars.*), the operation, and expected result.\n"
        "UNCLEAR = missing field names, data shape, or transformation logic.\n"
        "If CLEAR: respond PROCEED. If UNCLEAR: ask 1-3 questions. No preamble."
    ),
    "critic": (
        "[ROLE: critic]\n\n"
        "Review Lua code for the Octapi LowCode platform.\n"
        "Check: wf.vars.* access (no bare names), local declarations, "
        "_utils.array.new() for new arrays, ends with return, no forbidden calls.\n"
        "If correct: LGTM. If issues: list as \"Line N: problem\". Be concise."
    ),
}

# ── Variation pools ────────────────────────────────────────────────────────────

_GENERATOR_VARIATIONS = [
    "filter an array in wf.vars by a specific field value (e.g. status == 'active')",
    "access a deeply nested field (3-4 levels deep) in wf.vars and return its value",
    "increment or decrement a numeric counter stored in wf.vars",
    "check if a field in wf.vars is nil or empty string and return a default value",
    "convert a string field to uppercase using Lua string functions",
    "concatenate two string fields from wf.vars with a separator character",
    "compute and return the length of an array in wf.vars",
    "clear (nil out) specific keys from each object in an array in wf.vars",
    "format a date string from YYYYMMDD format to YYYY-MM-DD using string operations",
    "build a filtered array using _utils.array.new() based on a numeric threshold",
    "return the first non-nil value from a list of candidate fields in wf.vars",
    "convert a comma-separated string field in wf.vars into an array",
    "sum all numeric values in an array field in wf.vars",
    "find the maximum numeric value in an array field in wf.vars",
    "check if a specific key exists in a table stored in wf.vars",
]

_ANALYST_VARIATIONS = [
    "a vague request to 'process the data' with no field names or operation specified",
    "a request to filter something but without stating which field or condition",
    "a request to transform a date but without specifying source or target format",
    "a request that names the field but not what to do with it",
    "a clear, complete request naming wf.vars path, operation, and expected output",
    "a request to 'send the result somewhere' without naming the destination field",
    "a request that has a context JSON but the task description is ambiguous",
    "a complete request with field path, filter condition, and return shape",
    "a request to increment a counter with all necessary details provided",
    "a vague request to 'clean up the data' with no specifics",
]

_CRITIC_VARIATIONS = [
    "Lua code that accesses a variable without wf.vars.* (bare global name)",
    "Lua code that creates an array with {} instead of _utils.array.new()",
    "Lua code that is missing the `local` keyword on one variable declaration",
    "Lua code that calls require() which is forbidden in the sandbox",
    "Lua code that looks correct: proper wf.vars.* access, local, return, _utils.array.new()",
    "Lua code that uses os.time() or io.read() (forbidden sandbox calls)",
    "Lua code that accesses wf.vars correctly and returns the right value — should pass",
    "Lua code with an undefined variable used in a condition",
    "Lua code that forgets the return statement at the end",
    "Lua code that uses JsonPath syntax ($.field) instead of direct Lua access",
]

_VARIATIONS: dict[str, list[str]] = {
    "generator": _GENERATOR_VARIATIONS,
    "analyst":   _ANALYST_VARIATIONS,
    "critic":    _CRITIC_VARIATIONS,
}

# ── Prompt templates ───────────────────────────────────────────────────────────

def _make_prompt(role: str, variation: str, index: int, total: int) -> str:
    if role == "generator":
        return _generator_prompt(variation, index, total)
    if role == "analyst":
        return _analyst_prompt(variation, index, total)
    return _critic_prompt(variation, index, total)


def _generator_prompt(variation: str, index: int, total: int) -> str:
    return f"""\
=== Prompt {index} / {total} ===
Create a training example for an Octapi Lua code generator.

Octapi Lua sandbox rules:
- Variables are accessed via wf.vars.* or wf.initVariables.*
- Use _utils.array.new() to create a new array (not plain {{}})
- Forbidden: require(), io.*, os.*
- Declare all local variables with `local`
- The script must end with `return`

The task should require Lua to: {variation}

Return a single JSON object with exactly these two keys:
- "input": a string containing an optional wf context JSON block followed by the task description
  (in Russian or English). Format:
    "Context:\\n{{...json...}}\\n\\nTask: ..."
  If no context is needed, just: "Task: ..."
- "output": the raw Lua code only. No markdown fences. No explanation.

Respond with ONLY the JSON object, nothing else."""


def _analyst_prompt(variation: str, index: int, total: int) -> str:
    return f"""\
=== Prompt {index} / {total} ===
Create a training example for an Octapi Lua analyst agent.
The analyst decides if a task is CLEAR (respond PROCEED) or UNCLEAR (ask 1-3 questions).

Create an example involving: {variation}

Return a single JSON object with exactly these two keys:
- "input": the user's task description (and optional wf context JSON)
- "output": either the single word PROCEED, or 1-3 short clarifying questions (no preamble)

Respond with ONLY the JSON object, nothing else."""


def _critic_prompt(variation: str, index: int, total: int) -> str:
    return f"""\
=== Prompt {index} / {total} ===
Create a training example for an Octapi Lua code reviewer.

Octapi rules the critic checks:
- Variables accessed via wf.vars.* or wf.initVariables.* (not bare globals)
- New arrays created with _utils.array.new()
- All variables declared with `local`
- Script ends with `return`
- No require(), io.*, os.*

Create an example involving: {variation}

Return a single JSON object with exactly these two keys:
- "input": "Review this Lua code:\\n\\n" followed by the Lua code
- "output": either the single word LGTM, or a list of issues as "Line N: problem"

Respond with ONLY the JSON object, nothing else."""


# ── Subcommand: prompts ────────────────────────────────────────────────────────

def cmd_prompts(args: argparse.Namespace) -> None:
    """Print numbered prompt blocks to stdout."""
    role = args.role
    count = args.count
    seed = args.seed

    rng = random.Random(seed)
    pool = _VARIATIONS[role].copy()

    for i in range(1, count + 1):
        if not pool:
            pool = _VARIATIONS[role].copy()
        variation = rng.choice(pool)
        pool.remove(variation)

        prompt = _make_prompt(role, variation, i, count)
        print(prompt)
        print()


# ── Subcommand: convert ────────────────────────────────────────────────────────

def cmd_convert(args: argparse.Namespace) -> None:
    """Parse saved ChatGPT responses from a text file and write JSONL."""
    role = args.role
    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        print(f"[ERROR] Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    raw = input_path.read_text(encoding="utf-8")
    objects = _extract_json_objects(raw)

    valid, skipped = [], 0
    for obj in objects:
        ex = _build_example(obj, role)
        if ex:
            valid.append(ex)
        else:
            skipped += 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for ex in valid:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")

    print(f"Written {len(valid)} examples to {output_path} ({skipped} skipped).")


# ── Subcommand: auto ───────────────────────────────────────────────────────────

def cmd_auto(args: argparse.Namespace) -> None:
    """Generate data automatically via the OpenAI API."""
    try:
        from openai import OpenAI
    except ImportError:
        print(
            "[ERROR] openai package not installed.\n"
            "  pip install openai\n"
            "  or: pip install -r requirements-dev.txt",
            file=sys.stderr,
        )
        sys.exit(1)

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print(
            "[ERROR] OPENAI_API_KEY environment variable is not set.\n"
            "  export OPENAI_API_KEY=sk-...",
            file=sys.stderr,
        )
        sys.exit(1)

    client = OpenAI(api_key=api_key)
    role = args.role
    count = args.count
    output_path = Path(args.output)
    model = args.openai_model
    seed = args.seed
    delay = args.delay

    rng = random.Random(seed)
    pool = _VARIATIONS[role].copy()

    output_path.parent.mkdir(parents=True, exist_ok=True)

    valid, skipped, errors = 0, 0, 0
    with open(output_path, "a", encoding="utf-8") as f:
        for i in range(1, count + 1):
            if not pool:
                pool = _VARIATIONS[role].copy()
            variation = rng.choice(pool)
            pool.remove(variation)

            prompt_text = _make_prompt(role, variation, i, count)
            # Strip the "=== Prompt N / M ===" header — send only the task.
            prompt_body = "\n".join(prompt_text.splitlines()[1:]).strip()

            print(f"[{i}/{count}] {role} — {variation[:50]}...", end=" ", flush=True)

            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt_body}],
                    temperature=0.8,
                    max_tokens=512,
                )
                content = response.choices[0].message.content or ""
                objects = _extract_json_objects(content)

                if not objects:
                    print("SKIP (no JSON found)")
                    skipped += 1
                    continue

                ex = _build_example(objects[0], role)
                if not ex:
                    print("SKIP (validation failed)")
                    skipped += 1
                    continue

                f.write(json.dumps(ex, ensure_ascii=False) + "\n")
                f.flush()
                valid += 1
                print("OK")

            except Exception as exc:
                print(f"ERROR: {exc}")
                errors += 1

            if i < count and delay > 0:
                time.sleep(delay)

    print(f"\nDone. Written {valid} examples to {output_path}. Skipped: {skipped}. Errors: {errors}.")


# ── Shared helpers ─────────────────────────────────────────────────────────────

def _extract_json_objects(text: str) -> list[dict]:
    """Extract all JSON objects from a text string (greedy brace matching)."""
    objects = []
    i = 0
    while i < len(text):
        if text[i] == "{":
            depth = 0
            for j in range(i, len(text)):
                if text[j] == "{":
                    depth += 1
                elif text[j] == "}":
                    depth -= 1
                    if depth == 0:
                        candidate = text[i : j + 1]
                        try:
                            obj = json.loads(candidate)
                            if isinstance(obj, dict):
                                objects.append(obj)
                        except json.JSONDecodeError:
                            pass
                        i = j
                        break
        i += 1
    return objects


def _build_example(obj: dict, role: str) -> dict | None:
    """Validate a raw parsed object and build a complete training example."""
    inp = obj.get("input", "").strip()
    out = obj.get("output", "").strip()

    if not inp or not out:
        return None

    if role == "generator" and len(out) < 5:
        return None  # suspiciously short Lua code

    if role == "analyst" and out.upper() not in ("PROCEED",) and "?" not in out:
        return None  # analyst must either PROCEED or ask a question

    return {
        "instruction": _INSTRUCTIONS[role],
        "input": inp,
        "output": out,
    }


# ── CLI ────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # ── prompts ──
    p_prompts = sub.add_parser("prompts", help="Print prompt templates to stdout")
    p_prompts.add_argument("--role", choices=["generator", "analyst", "critic"],
                            required=True)
    p_prompts.add_argument("--count", type=int, default=50,
                            help="Number of prompts to generate (default: 50)")
    p_prompts.add_argument("--seed", type=int, default=42,
                            help="Random seed for variation selection (default: 42)")
    p_prompts.set_defaults(func=cmd_prompts)

    # ── convert ──
    p_convert = sub.add_parser("convert", help="Convert saved responses to JSONL")
    p_convert.add_argument("--role", choices=["generator", "analyst", "critic"],
                            required=True)
    p_convert.add_argument("--input", required=True, metavar="FILE",
                            help="Text file containing saved ChatGPT responses")
    p_convert.add_argument("--output", required=True, metavar="FILE",
                            help="Output JSONL file path")
    p_convert.set_defaults(func=cmd_convert)

    # ── auto ──
    p_auto = sub.add_parser(
        "auto",
        help="Generate data via OpenAI API (requires OPENAI_API_KEY)",
    )
    p_auto.add_argument("--role", choices=["generator", "analyst", "critic"],
                         required=True)
    p_auto.add_argument("--count", type=int, default=50,
                         help="Number of examples to generate (default: 50)")
    p_auto.add_argument("--output", required=True, metavar="FILE",
                         help="Output JSONL file (appended if exists)")
    p_auto.add_argument("--openai-model", default="gpt-4o-mini", metavar="MODEL",
                         help="OpenAI model to use (default: gpt-4o-mini)")
    p_auto.add_argument("--seed", type=int, default=42,
                         help="Random seed for variation selection (default: 42)")
    p_auto.add_argument("--delay", type=float, default=1.0, metavar="SECONDS",
                         help="Delay between API calls in seconds (default: 1.0)")
    p_auto.set_defaults(func=cmd_auto)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
