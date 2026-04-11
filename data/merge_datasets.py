#!/usr/bin/env python3
"""
Merge multiple JSONL training data files into a single shuffled dataset.

- Skips files that do not exist (prints a warning).
- Deduplicates by (instruction, input) pair hash.
- Shuffles the merged result.
- Writes data/train.jsonl.

Usage:
  python data/merge_datasets.py \\
      data/seeds/generator_seeds.jsonl \\
      data/generator_data.jsonl \\
      data/seeds/analyst_seeds.jsonl \\
      data/analyst_data.jsonl \\
      data/seeds/critic_seeds.jsonl \\
      data/critic_data.jsonl \\
      --output data/train.jsonl --shuffle --seed 42
"""

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("inputs", nargs="+", metavar="FILE",
                        help="JSONL input files (missing files are skipped)")
    parser.add_argument("--output", required=True, metavar="FILE",
                        help="Output JSONL path")
    parser.add_argument("--shuffle", action="store_true",
                        help="Shuffle the merged dataset")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for shuffling (default: 42)")
    args = parser.parse_args()

    examples: list[dict] = []
    seen_hashes: set[str] = set()
    total_read = 0
    total_dupes = 0

    for path_str in args.inputs:
        path = Path(path_str)
        if not path.exists():
            print(f"[SKIP] {path} — file not found", file=sys.stderr)
            continue

        file_count = 0
        with open(path, encoding="utf-8") as f:
            for lineno, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError as exc:
                    print(f"[WARN] {path}:{lineno} — JSON parse error: {exc}", file=sys.stderr)
                    continue

                if not isinstance(obj, dict) or "instruction" not in obj or "output" not in obj:
                    print(f"[WARN] {path}:{lineno} — missing 'instruction' or 'output', skipping",
                          file=sys.stderr)
                    continue

                # Deduplicate by hash of (instruction, input, output)
                key = hashlib.md5(
                    json.dumps({
                        "instruction": obj.get("instruction", ""),
                        "input": obj.get("input", ""),
                        "output": obj.get("output", ""),
                    }, sort_keys=True).encode()
                ).hexdigest()

                if key in seen_hashes:
                    total_dupes += 1
                    continue

                seen_hashes.add(key)
                examples.append(obj)
                file_count += 1
                total_read += 1

        print(f"[OK]   {path} — {file_count} examples loaded")

    if not examples:
        print("[ERROR] No examples loaded. Check input files.", file=sys.stderr)
        sys.exit(1)

    if args.shuffle:
        random.Random(args.seed).shuffle(examples)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for ex in examples:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")

    print(
        f"\nMerge complete: {total_read} examples written to {output_path}"
        f" ({total_dupes} duplicates removed)."
    )

    # Role distribution summary
    role_counts: dict[str, int] = {}
    for ex in examples:
        role = "unknown"
        inst = ex.get("instruction", "")
        for r in ("generator", "analyst", "critic"):
            if f"[ROLE: {r}]" in inst:
                role = r
                break
        role_counts[role] = role_counts.get(role, 0) + 1
    print("Role distribution:")
    for role, cnt in sorted(role_counts.items()):
        print(f"  {role:12s}: {cnt}")


if __name__ == "__main__":
    main()
