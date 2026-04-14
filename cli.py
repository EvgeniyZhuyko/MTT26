#!/usr/bin/env python3
"""
LocalScript — Octapi Lua code generator.

Generates Lua scripts for the Octapi LowCode platform from natural-language
task descriptions (Russian or English). Runs fully locally via Ollama.

Usage:
  python cli.py "Task description" [OPTIONS]
  python cli.py --help
"""

import argparse
import json
import sys

from localscript.agent.graph import build_graph
from localscript.agent.state import AgentState

# ── CLI definition ─────────────────────────────────────────────────────────────

_EXAMPLES = """
examples:
  python cli.py "Get the last email from the list" \\
    --context-str '{"wf":{"vars":{"emails":["a@b.com","b@c.com"]}}}'

  python cli.py "Отфильтруй элементы с Discount или Markdown" \\
    --context context.json --key filtered --verbose

  python cli.py "Increment the counter" \\
    --context-str '{"wf":{"vars":{"try_count_n":3}}}' --lua

  python cli.py "Convert recallTime to unix epoch" \\
    --context-str '{"wf":{"initVariables":{"recallTime":"2023-10-15T15:30:00+00:00"}}}' \\
    --model localscript:latest
"""


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cli.py",
        description=(
            "Generate Octapi Lua scripts from natural language.\n"
            "Output is a JSON manifest fragment: {\"key\": \"lua{...}lua\"}.\n"
            "Use --lua to get raw Lua code instead."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=_EXAMPLES,
    )

    parser.add_argument(
        "prompt",
        help="Task description in Russian or English.",
    )
    parser.add_argument(
        "--context",
        metavar="FILE",
        help="Path to a JSON file containing the wf.vars / wf.initVariables context.",
    )
    parser.add_argument(
        "--context-str",
        metavar="JSON",
        dest="context_str",
        help="Inline JSON context string (alternative to --context).",
    )
    parser.add_argument(
        "--key",
        default="result",
        metavar="NAME",
        help="Field name in the JSON manifest output (default: result).",
    )
    parser.add_argument(
        "--lua",
        action="store_true",
        help="Output raw Lua code only, without the JSON manifest wrapper.",
    )
    parser.add_argument(
        "--max-iter",
        type=int,
        default=3,
        metavar="N",
        dest="max_iter",
        help="Maximum generator → critic retries (default: 3).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print iteration count and lint errors to stderr.",
    )
    parser.add_argument(
        "--model",
        default="localscript:latest",
        metavar="TAG",
        help="Ollama model tag (default: localscript:latest).",
    )

    return parser


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    # --- Load context ---
    wf_context = _load_context(args, parser)

    # --- Build and run graph ---
    graph = build_graph(max_iter=args.max_iter)

    initial_state: AgentState = {
        "user_prompt": args.prompt,
        "wf_context": wf_context,
        "history": [],
        "script": "",
        "lint_errors": [],
        "iterations": 0,
        "done": False,
        "extract_lua": args.lua,
        "model": args.model,
    }

    result = graph.invoke(initial_state)

    # --- Verbose info ---
    if args.verbose:
        print(f"[Info] Iterations: {result['iterations']}", file=sys.stderr)
        if result.get("lint_errors"):
            print("[Info] Remaining lint issues:", file=sys.stderr)
            for e in result["lint_errors"]:
                print(f"  {e}", file=sys.stderr)

    # --- Output ---
    script = result.get("script", "")
    if not script:
        print("[ERROR] No script was generated.", file=sys.stderr)
        sys.exit(1)

    if args.lua:
        print(script)
    else:
        manifest = {args.key: f"lua{{{script}}}lua"}
        print(json.dumps(manifest, ensure_ascii=False, indent=2))


# ── Helpers ────────────────────────────────────────────────────────────────────

def _load_context(args, parser) -> dict | None:
    if args.context and args.context_str:
        parser.error("Use --context or --context-str, not both.")

    if args.context:
        try:
            with open(args.context, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            parser.error(f"Cannot load --context file: {exc}")

    if args.context_str:
        try:
            return json.loads(args.context_str)
        except json.JSONDecodeError as exc:
            parser.error(f"Invalid --context-str JSON: {exc}")

    return None


if __name__ == "__main__":
    main()
