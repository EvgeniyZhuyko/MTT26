#!/usr/bin/env python3
"""
Deterministic training data synthesizer for LocalScript.

Generates diverse, correct training examples from code templates + randomized
field/value pools — no LLM required. Every output is syntactically valid Lua
that follows Octapi sandbox rules.

17 template families × configurable examples per family ≈ 300–500 examples.

Usage:
  python data/synthesize.py --output data/generator_data.jsonl
  python data/synthesize.py --output data/generator_data.jsonl --per-template 20
  python data/synthesize.py --list-templates
"""

import argparse
import json
import random
import sys
from pathlib import Path

# ── Instruction header (same as other datasets) ───────────────────────────────

_INSTRUCTION = (
    "[ROLE: generator]\n\n"
    "Octapi Lua Sandbox:\n"
    "- Lua 5.x. Variables: wf.vars.* or wf.initVariables.*\n"
    "- New array: _utils.array.new(). Mark array: _utils.array.markAsArray(t)\n"
    "- Forbidden: require(), io.*, os.*, JsonPath syntax\n"
    "- Declare all variables with `local`. End with `return`.\n"
    "Output ONLY raw Lua. No fences, no explanation."
)

# ── Field / value pools ────────────────────────────────────────────────────────

_ARRAY_VARS = [
    "orders", "items", "records", "products", "emails",
    "users", "entries", "messages", "transactions", "packages",
    "invoices", "events", "tasks", "shipments", "payments",
]

_STRING_VARS = [
    "name", "email", "phone", "status", "region", "type",
    "code", "title", "category", "label", "priority", "source",
]

_NUMBER_VARS = [
    "count", "retry_count", "attempt_n", "step", "total",
    "amount", "quantity", "score", "index", "version",
]

_NESTED_ROOTS = ["order", "user", "payload", "data", "request", "response", "document"]
_NESTED_L2    = ["header", "body", "info", "meta", "details", "attributes"]
_NESTED_L3    = ["id", "status", "code", "type", "value", "name", "ref"]

_STATUS_VALUES = ["active", "inactive", "pending", "completed", "failed", "processing", "cancelled"]
_REGION_VALUES = ["MSK", "SPB", "NSK", "EKB", "KZN", "RND", "VLG"]
_TYPE_VALUES   = ["A", "B", "C", "standard", "premium", "basic"]

_FIELD_VALUES: dict[str, list] = {
    "status":   _STATUS_VALUES,
    "region":   _REGION_VALUES,
    "type":     _TYPE_VALUES,
    "priority": ["high", "medium", "low"],
    "source":   ["kafka", "rest", "db", "queue"],
    "category": ["alpha", "beta", "gamma", "delta"],
    "label":    ["red", "green", "blue", "yellow"],
    "code":     ["OK", "ERR", "WARN", "SKIP"],
}
_DEFAULT_STRING_VALUES = ["active", "pending", "standard", "A", "B"]

_DATE_VARS = ["date", "created_date", "ORDER_DATE", "delivery_date", "updated_date"]
_INIT_TIME_VARS = [
    "recallTime", "startTime", "eventTime", "createdAt",
    "updatedAt", "processedAt", "submittedAt", "scheduledAt",
    "completedAt", "triggeredAt", "expiresAt", "issuedAt",
    "deadline", "timestamp", "launchedAt", "closedAt",
]

# ── Task phrasings (EN/RU pairs per template) ─────────────────────────────────
# Each entry is (EN_phrasing, RU_phrasing)

def _pick_lang(rng: random.Random, en: str, ru: str) -> str:
    return rng.choice([en, ru])


# ── Example builder ────────────────────────────────────────────────────────────

def _example(wf_context: dict | None, task: str, output: str) -> dict:
    if wf_context:
        ctx_str = json.dumps(wf_context, ensure_ascii=False, indent=2)
        inp = f"Context:\n{ctx_str}\n\nTask: {task}"
    else:
        inp = f"Task: {task}"
    return {"instruction": _INSTRUCTION, "input": inp, "output": output}


def _items_with_field(rng: random.Random, field: str, match_val: str, n: int = 4) -> list[dict]:
    """Generate n dict items where ~half match field==match_val."""
    alt = rng.choice([v for v in _FIELD_VALUES.get(field, _DEFAULT_STRING_VALUES)
                      if v != match_val])
    items = []
    for i in range(n):
        items.append({
            "id": i + 1,
            field: match_val if i % 2 == 0 else alt,
            "value": rng.randint(10, 999),
        })
    return items


def _numeric_items(rng: random.Random, num_field: str, n: int = 5) -> list[dict]:
    return [{"id": i + 1, num_field: rng.randint(1, 500)} for i in range(n)]


# ── Template implementations ───────────────────────────────────────────────────

def tmpl_filter_string_eq(rng: random.Random) -> dict:
    arr = rng.choice(_ARRAY_VARS)
    field = rng.choice([f for f in _FIELD_VALUES])
    val = rng.choice(_FIELD_VALUES[field])
    items = _items_with_field(rng, field, val)
    ctx = {"wf": {"vars": {arr: items}}}
    task = _pick_lang(rng,
        f"Filter wf.vars.{arr}: keep only items where {field} equals \"{val}\".",
        f"Отфильтруй wf.vars.{arr}: оставь только элементы, где {field} равно \"{val}\".")
    output = (
        f"local result = _utils.array.new()\n"
        f"local items = wf.vars.{arr}\n"
        f"for _, item in ipairs(items) do\n"
        f"  if item.{field} == \"{val}\" then\n"
        f"    table.insert(result, item)\n"
        f"  end\n"
        f"end\n"
        f"return result"
    )
    return _example(ctx, task, output)


def tmpl_filter_string_neq(rng: random.Random) -> dict:
    arr = rng.choice(_ARRAY_VARS)
    field = rng.choice([f for f in _FIELD_VALUES])
    val = rng.choice(_FIELD_VALUES[field])
    items = _items_with_field(rng, field, val)
    ctx = {"wf": {"vars": {arr: items}}}
    task = _pick_lang(rng,
        f"Filter wf.vars.{arr}: exclude items where {field} is \"{val}\".",
        f"Отфильтруй wf.vars.{arr}: исключи элементы, где {field} равно \"{val}\".")
    output = (
        f"local result = _utils.array.new()\n"
        f"local items = wf.vars.{arr}\n"
        f"for _, item in ipairs(items) do\n"
        f"  if item.{field} ~= \"{val}\" then\n"
        f"    table.insert(result, item)\n"
        f"  end\n"
        f"end\n"
        f"return result"
    )
    return _example(ctx, task, output)


def tmpl_filter_nonempty(rng: random.Random) -> dict:
    arr = rng.choice(_ARRAY_VARS)
    field = rng.choice(_STRING_VARS)
    items = [
        {"id": 1, field: "value_a", "other": "x"},
        {"id": 2, field: "",         "other": "y"},
        {"id": 3, field: "value_b", "other": "z"},
        {"id": 4, field: None,       "other": "w"},
    ]
    ctx = {"wf": {"vars": {arr: items}}}
    task = _pick_lang(rng,
        f"Keep only items from wf.vars.{arr} that have a non-empty {field} field.",
        f"Оставь в wf.vars.{arr} только элементы с непустым полем {field}.")
    output = (
        f"local result = _utils.array.new()\n"
        f"local items = wf.vars.{arr}\n"
        f"for _, item in ipairs(items) do\n"
        f"  if item.{field} ~= nil and item.{field} ~= \"\" then\n"
        f"    table.insert(result, item)\n"
        f"  end\n"
        f"end\n"
        f"return result"
    )
    return _example(ctx, task, output)


def tmpl_filter_numeric_gt(rng: random.Random) -> dict:
    arr = rng.choice(_ARRAY_VARS)
    num_f = rng.choice(["amount", "quantity", "score", "total", "value"])
    threshold = rng.choice([10, 50, 100, 200, 500])
    items = _numeric_items(rng, num_f)
    ctx = {"wf": {"vars": {arr: items}}}
    task = _pick_lang(rng,
        f"From wf.vars.{arr}, keep only items where {num_f} is greater than {threshold}.",
        f"Из wf.vars.{arr} оставь элементы, где {num_f} больше {threshold}.")
    output = (
        f"local result = _utils.array.new()\n"
        f"local items = wf.vars.{arr}\n"
        f"for _, item in ipairs(items) do\n"
        f"  if item.{num_f} > {threshold} then\n"
        f"    table.insert(result, item)\n"
        f"  end\n"
        f"end\n"
        f"return result"
    )
    return _example(ctx, task, output)


def tmpl_get_last(rng: random.Random) -> dict:
    arr = rng.choice(_ARRAY_VARS)
    sample = [f"val_{i}" for i in range(1, 5)]
    ctx = {"wf": {"vars": {arr: sample}}}
    task = _pick_lang(rng,
        f"Return the last element of wf.vars.{arr}.",
        f"Верни последний элемент массива wf.vars.{arr}.")
    output = f"return wf.vars.{arr}[#wf.vars.{arr}]"
    return _example(ctx, task, output)


def tmpl_get_first(rng: random.Random) -> dict:
    arr = rng.choice(_ARRAY_VARS)
    sample = [f"item_{i}" for i in range(1, 5)]
    ctx = {"wf": {"vars": {arr: sample}}}
    task = _pick_lang(rng,
        f"Return the first element of wf.vars.{arr}.",
        f"Верни первый элемент массива wf.vars.{arr}.")
    output = f"return wf.vars.{arr}[1]"
    return _example(ctx, task, output)


def tmpl_array_length(rng: random.Random) -> dict:
    arr = rng.choice(_ARRAY_VARS)
    n = rng.randint(2, 8)
    ctx = {"wf": {"vars": {arr: list(range(n))}}}
    task = _pick_lang(rng,
        f"Return the number of elements in wf.vars.{arr}.",
        f"Верни количество элементов в массиве wf.vars.{arr}.")
    output = f"return #wf.vars.{arr}"
    return _example(ctx, task, output)


def tmpl_counter_inc(rng: random.Random) -> dict:
    var = rng.choice(_NUMBER_VARS)
    val = rng.randint(0, 10)
    ctx = {"wf": {"vars": {var: val}}}
    step = rng.choice([1, 2])
    task = _pick_lang(rng,
        f"Increment wf.vars.{var} by {step}.",
        f"Увеличь значение wf.vars.{var} на {step}.")
    output = f"return wf.vars.{var} + {step}"
    return _example(ctx, task, output)


def tmpl_counter_dec(rng: random.Random) -> dict:
    var = rng.choice(_NUMBER_VARS)
    val = rng.randint(2, 20)
    ctx = {"wf": {"vars": {var: val}}}
    task = _pick_lang(rng,
        f"Decrement wf.vars.{var} by 1.",
        f"Уменьши wf.vars.{var} на 1.")
    output = f"return wf.vars.{var} - 1"
    return _example(ctx, task, output)


def tmpl_nested_access(rng: random.Random) -> dict:
    depth = rng.randint(2, 4)
    parts = [rng.choice(_NESTED_ROOTS)]
    if depth >= 2:
        parts.append(rng.choice(_NESTED_L2))
    if depth >= 3:
        parts.append(rng.choice(_NESTED_L3))
    if depth >= 4:
        parts.append(rng.choice(["id", "value", "ref", "key"]))

    # Build nested dict
    def _build(keys: list[str], val) -> dict:
        if len(keys) == 1:
            return {keys[0]: val}
        return {keys[0]: _build(keys[1:], val)}

    leaf_val = rng.choice(["abc-123", 42, "pending", True])
    ctx = {"wf": {"vars": _build(parts, leaf_val)}}
    path = "wf.vars." + ".".join(parts)
    task = _pick_lang(rng,
        f"Return the value of {path}.",
        f"Верни значение {path}.")
    output = f"return {path}"
    return _example(ctx, task, output)


def tmpl_string_concat(rng: random.Random) -> dict:
    f1, f2 = rng.sample(_STRING_VARS, 2)
    sep = rng.choice([" ", "-", "_", ", ", " | "])
    ctx = {"wf": {"vars": {f1: "Hello", f2: "World"}}}
    task = _pick_lang(rng,
        f"Concatenate wf.vars.{f1} and wf.vars.{f2} with \"{sep}\" as separator.",
        f"Объедини wf.vars.{f1} и wf.vars.{f2} через разделитель \"{sep}\".")
    output = f"return wf.vars.{f1} .. \"{sep}\" .. wf.vars.{f2}"
    return _example(ctx, task, output)


def tmpl_first_non_nil(rng: random.Random) -> dict:
    fields = rng.sample(_STRING_VARS, rng.randint(2, 4))
    non_nil_idx = rng.randint(0, len(fields) - 1)
    ctx_vars = {f: (f"value_{f}" if i == non_nil_idx else None)
                for i, f in enumerate(fields)}
    ctx = {"wf": {"vars": ctx_vars}}
    fields_lua = ", ".join(f'"{f}"' for f in fields)
    task = _pick_lang(rng,
        f"Return the first non-nil value from wf.vars fields: {', '.join(fields)}.",
        f"Верни первое ненулевое значение из полей wf.vars: {', '.join(fields)}.")
    output = (
        f"local fields = {{{fields_lua}}}\n"
        f"for _, key in ipairs(fields) do\n"
        f"  if wf.vars[key] ~= nil then\n"
        f"    return wf.vars[key]\n"
        f"  end\n"
        f"end\n"
        f"return nil"
    )
    return _example(ctx, task, output)


def tmpl_clear_keys(rng: random.Random) -> dict:
    arr = rng.choice(_ARRAY_VARS)
    all_keys = rng.sample(_STRING_VARS + _NUMBER_VARS, 5)
    keep_keys = rng.sample(all_keys, rng.randint(2, 3))
    items = [{k: f"v_{k}_{i}" for k in all_keys} for i in range(3)]
    ctx = {"wf": {"vars": {arr: items}}}
    keep_str = ", ".join(f'"{k}"' for k in keep_keys)
    keep_cond = " and ".join(f'key ~= "{k}"' for k in keep_keys)
    task = _pick_lang(rng,
        f"In wf.vars.{arr}, remove all keys except: {', '.join(keep_keys)}.",
        f"В wf.vars.{arr} удали все ключи кроме: {', '.join(keep_keys)}.")
    output = (
        f"local result = wf.vars.{arr}\n"
        f"for _, entry in pairs(result) do\n"
        f"  for key, _ in pairs(entry) do\n"
        f"    if {keep_cond} then\n"
        f"      entry[key] = nil\n"
        f"    end\n"
        f"  end\n"
        f"end\n"
        f"return result"
    )
    return _example(ctx, task, output)


def tmpl_date_format(rng: random.Random) -> dict:
    var = rng.choice(_DATE_VARS)
    y, m, d = rng.randint(2020, 2025), rng.randint(1, 12), rng.randint(1, 28)
    date_str = f"{y:04d}{m:02d}{d:02d}"
    ctx = {"wf": {"vars": {var: date_str}}}
    task = _pick_lang(rng,
        f"Convert wf.vars.{var} from YYYYMMDD to YYYY-MM-DD format.",
        f"Преобразуй wf.vars.{var} из формата YYYYMMDD в YYYY-MM-DD.")
    output = (
        f"local d = wf.vars.{var}\n"
        f"return string.sub(d,1,4) .. \"-\" .. string.sub(d,5,6) .. \"-\" .. string.sub(d,7,8)"
    )
    return _example(ctx, task, output)


def tmpl_sum_array(rng: random.Random) -> dict:
    arr = rng.choice(_ARRAY_VARS)
    num_f = rng.choice(["amount", "quantity", "score", "total", "value", "price"])
    items = [{num_f: rng.randint(1, 100)} for _ in range(4)]
    ctx = {"wf": {"vars": {arr: items}}}
    task = _pick_lang(rng,
        f"Return the sum of all {num_f} values in wf.vars.{arr}.",
        f"Верни сумму всех значений {num_f} в wf.vars.{arr}.")
    output = (
        f"local total = 0\n"
        f"for _, item in ipairs(wf.vars.{arr}) do\n"
        f"  total = total + (item.{num_f} or 0)\n"
        f"end\n"
        f"return total"
    )
    return _example(ctx, task, output)


def tmpl_max_array(rng: random.Random) -> dict:
    arr = rng.choice(_ARRAY_VARS)
    num_f = rng.choice(["amount", "quantity", "score", "total", "value", "priority_num"])
    items = [{num_f: rng.randint(1, 500)} for _ in range(5)]
    ctx = {"wf": {"vars": {arr: items}}}
    task = _pick_lang(rng,
        f"Find and return the maximum {num_f} value across all items in wf.vars.{arr}.",
        f"Найди и верни максимальное значение {num_f} среди всех элементов wf.vars.{arr}.")
    output = (
        f"local max = nil\n"
        f"for _, item in ipairs(wf.vars.{arr}) do\n"
        f"  if max == nil or item.{num_f} > max then\n"
        f"    max = item.{num_f}\n"
        f"  end\n"
        f"end\n"
        f"return max"
    )
    return _example(ctx, task, output)


_UPPER_SAMPLE_VALUES = [
    "hello world", "test input", "foo bar", "example string",
    "sample text", "some value", "pending", "active",
    "draft", "open", "closed", "processing",
    "done", "ready", "waiting", "error",
    "warning", "info", "debug", "trace",
]

def tmpl_string_upper(rng: random.Random) -> dict:
    var = rng.choice(_STRING_VARS)
    val = rng.choice(_UPPER_SAMPLE_VALUES)
    ctx = {"wf": {"vars": {var: val}}}
    task = _pick_lang(rng,
        f"Convert wf.vars.{var} to uppercase.",
        f"Преобразуй wf.vars.{var} в верхний регистр.")
    output = f"return string.upper(wf.vars.{var})"
    return _example(ctx, task, output)


def tmpl_nil_default(rng: random.Random) -> dict:
    var = rng.choice(_STRING_VARS)
    default = rng.choice(["unknown", "N/A", "default", "none", ""])
    ctx = {"wf": {"vars": {var: None}}}
    task = _pick_lang(rng,
        f"Return wf.vars.{var}, or \"{default}\" if it is nil.",
        f"Верни wf.vars.{var}, или \"{default}\" если значение nil.")
    output = f"return wf.vars.{var} or \"{default}\""
    return _example(ctx, task, output)


def tmpl_initvars_access(rng: random.Random) -> dict:
    var = rng.choice(_INIT_TIME_VARS)
    other = rng.choice(_STRING_VARS)
    ctx = {"wf": {"initVariables": {var: "2024-01-15T10:30:00+00:00"}, "vars": {}}}
    task = _pick_lang(rng,
        f"Return the value of wf.initVariables.{var}.",
        f"Верни значение wf.initVariables.{var}.")
    output = f"return wf.initVariables.{var}"
    return _example(ctx, task, output)


def tmpl_collect_field(rng: random.Random) -> dict:
    """Extract one field from each object in an array into a new array."""
    arr = rng.choice(_ARRAY_VARS)
    field = rng.choice(_STRING_VARS)
    items = [{field: f"v{i}", "other": i} for i in range(4)]
    ctx = {"wf": {"vars": {arr: items}}}
    task = _pick_lang(rng,
        f"Collect all {field} values from wf.vars.{arr} into a new array.",
        f"Собери все значения {field} из wf.vars.{arr} в новый массив.")
    output = (
        f"local result = _utils.array.new()\n"
        f"for _, item in ipairs(wf.vars.{arr}) do\n"
        f"  table.insert(result, item.{field})\n"
        f"end\n"
        f"return result"
    )
    return _example(ctx, task, output)


# ── Template registry ──────────────────────────────────────────────────────────

_TEMPLATES: dict[str, callable] = {
    "filter_string_eq":   tmpl_filter_string_eq,
    "filter_string_neq":  tmpl_filter_string_neq,
    "filter_nonempty":    tmpl_filter_nonempty,
    "filter_numeric_gt":  tmpl_filter_numeric_gt,
    "get_last":           tmpl_get_last,
    "get_first":          tmpl_get_first,
    "array_length":       tmpl_array_length,
    "counter_inc":        tmpl_counter_inc,
    "counter_dec":        tmpl_counter_dec,
    "nested_access":      tmpl_nested_access,
    "string_concat":      tmpl_string_concat,
    "first_non_nil":      tmpl_first_non_nil,
    "clear_keys":         tmpl_clear_keys,
    "date_format":        tmpl_date_format,
    "sum_array":          tmpl_sum_array,
    "max_array":          tmpl_max_array,
    "string_upper":       tmpl_string_upper,
    "nil_default":        tmpl_nil_default,
    "initvars_access":    tmpl_initvars_access,
    "collect_field":      tmpl_collect_field,
}

# ── CLI ────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--output", default="data/generator_data.jsonl",
                        help="Output JSONL path (default: data/generator_data.jsonl)")
    parser.add_argument("--per-template", type=int, default=15, metavar="N",
                        help="Examples per template family (default: 15)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--list-templates", action="store_true",
                        help="Print available template names and exit")
    parser.add_argument("--templates", nargs="+", metavar="NAME",
                        help="Generate only these template families (default: all)")
    args = parser.parse_args()

    if args.list_templates:
        for name in sorted(_TEMPLATES):
            print(name)
        return

    selected = {k: v for k, v in _TEMPLATES.items()
                if not args.templates or k in args.templates}

    rng = random.Random(args.seed)
    examples: list[dict] = []
    counts: dict[str, int] = {}

    for name, fn in selected.items():
        generated = 0
        attempts = 0
        seen = set()
        while generated < args.per_template and attempts < args.per_template * 5:
            attempts += 1
            try:
                ex = fn(rng)
                key = ex["input"][:80]  # deduplicate on first 80 chars of input
                if key not in seen:
                    seen.add(key)
                    examples.append(ex)
                    generated += 1
            except Exception as e:
                print(f"[WARN] {name}: {e}", file=sys.stderr)
        counts[name] = generated

    # Shuffle so roles/patterns interleave
    random.Random(args.seed).shuffle(examples)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for ex in examples:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")

    total = len(examples)
    print(f"Written {total} examples to {out_path}")
    print(f"({args.per_template} per template × {len(selected)} templates)")
    print("\nBreakdown:")
    for name, cnt in counts.items():
        print(f"  {name:<22}: {cnt}")


if __name__ == "__main__":
    main()
