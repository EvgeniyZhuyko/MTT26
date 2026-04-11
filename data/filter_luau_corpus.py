#!/usr/bin/env python3
"""
Filter the Roblox/luau_corpus HuggingFace dataset to produce supplementary
Lua training examples compatible with the Octapi sandbox.

Filters out:
- Luau-specific syntax (task., game., ::<type>::, type annotations)
- Examples longer than --max-tokens tokens (rough char-based estimate)
- Examples with require() or io.* calls that conflict with sandbox rules

Wraps accepted examples in the [ROLE: generator] instruction format.

Usage:
  python data/filter_luau_corpus.py --output data/luau_supplement.jsonl --max 100

Requires:
  pip install datasets transformers   (from requirements-train.txt)
"""

import argparse
import json
import re
import sys
from pathlib import Path

_INSTRUCTION = (
    "[ROLE: generator]\n\n"
    "Octapi Lua Sandbox:\n"
    "- Lua 5.x. Variables: wf.vars.* or wf.initVariables.*\n"
    "- New array: _utils.array.new(). Mark array: _utils.array.markAsArray(t)\n"
    "- Forbidden: require(), io.*, os.*, JsonPath syntax\n"
    "- Declare all variables with `local`. End with `return`.\n"
    "Output ONLY raw Lua. No fences, no explanation."
)

# Patterns that indicate Luau-specific or sandbox-incompatible code.
_REJECT_PATTERNS = [
    re.compile(r"\btask\s*\."),           # task.wait(), task.spawn(), etc.
    re.compile(r"\bgame\s*\."),           # game:GetService(), etc.
    re.compile(r"\bscript\s*\."),         # script.Parent, etc.
    re.compile(r"\bworkspace\b"),
    re.compile(r"\bplayers\s*\."),
    re.compile(r"::\s*\w"),               # Luau type cast syntax
    re.compile(r"\btype\s+\w+\s*="),      # Luau type alias
    re.compile(r"--\s*!\s*strict"),       # Luau strict mode comment
    re.compile(r"\brequire\s*\("),        # forbidden in Octapi sandbox
    re.compile(r"\bio\s*\."),             # forbidden I/O
    re.compile(r"\bos\s*\.(time|clock|date|exit|getenv)"),  # forbidden os calls
]

# Approximate token limit (using chars/4 as rough estimate).
_CHARS_PER_TOKEN = 4


def _is_acceptable(code: str, max_tokens: int) -> bool:
    if len(code) / _CHARS_PER_TOKEN > max_tokens:
        return False
    for pattern in _REJECT_PATTERNS:
        if pattern.search(code):
            return False
    # Must have at least one `return` statement — we want complete scripts.
    if "return" not in code:
        return False
    return True


def _find_code_field(example: dict) -> str | None:
    """Return the code string from a dataset example, regardless of field name."""
    for field in ("code", "text", "content", "source", "lua"):
        val = example.get(field)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", required=True, metavar="FILE",
                        help="Output JSONL file path")
    parser.add_argument("--max", type=int, default=100, metavar="N",
                        help="Maximum number of examples to output (default: 100)")
    parser.add_argument("--max-tokens", type=int, default=200, metavar="N",
                        help="Max approximate token length per example (default: 200)")
    parser.add_argument("--split", default="train",
                        help="Dataset split to use (default: train)")
    args = parser.parse_args()

    try:
        from datasets import load_dataset
    except ImportError:
        print(
            "[ERROR] 'datasets' package not installed.\n"
            "  pip install datasets   (or install requirements-train.txt)",
            file=sys.stderr,
        )
        sys.exit(1)

    print("Loading Roblox/luau_corpus (this may take a while on first run)...")
    try:
        ds = load_dataset("Roblox/luau_corpus", split=args.split, streaming=True)
    except Exception as exc:
        print(f"[ERROR] Failed to load dataset: {exc}", file=sys.stderr)
        sys.exit(1)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    accepted = 0
    examined = 0

    with open(output_path, "w", encoding="utf-8") as f:
        for example in ds:
            examined += 1
            code = _find_code_field(example)

            if not code:
                if examined == 1:
                    print(f"[INFO] Dataset fields: {list(example.keys())}", file=sys.stderr)
                continue

            if not _is_acceptable(code, args.max_tokens):
                continue

            record = {
                "instruction": _INSTRUCTION,
                "input": "Task: Complete or improve this Lua script for the Octapi platform.",
                "output": code,
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            accepted += 1

            if accepted >= args.max:
                break

            if accepted % 10 == 0:
                print(f"  Accepted {accepted}/{args.max} (examined {examined})...")

    print(f"Done. Accepted {accepted} examples (examined {examined} total).")
    print(f"Written to {output_path}")


if __name__ == "__main__":
    main()
