#!/usr/bin/env python3
"""
QLoRA fine-tuning for LocalScript using nuprl/MultiPLCoder-1b.

MultiPLCoder-1b is a GPT-BigCode (StarCoder) base completion model — no chat
template.  Training data is formatted as plain-text completion so the layout
matches what Ollama sends at inference time:

    {system_prompt}\n\n{user_prompt}\n{lua_output}<eos>

Unsloth is tried first for speed; if the architecture is unsupported it falls
back to standard HuggingFace PEFT automatically.

Requirements:
  pip install -r requirements-train.txt
  CUDA GPU with ≥8 GB VRAM (1B model fits comfortably).

Usage:
  python training/train.py
  python training/train.py --dataset data/train.jsonl --epochs 3
"""

import argparse
import json
from pathlib import Path

# ── Defaults ───────────────────────────────────────────────────────────────────

BASE_MODEL   = "nuprl/MultiPLCoder-1b"
DATASET_PATH = "data/train.jsonl"
OUTPUT_DIR   = "training/checkpoints"
MAX_SEQ_LEN  = 1024

# GPT-BigCode attention + MLP projection names (StarCoder architecture).
# c_attn  = combined QKV (multi-query attention uses a single projection)
# c_proj  = output projection (attention and MLP share this name)
# c_fc    = MLP first linear
LORA_TARGETS = ["c_attn", "c_proj", "c_fc"]


def _load_with_unsloth(model_name, max_seq_len, lora_r):
    """Try Unsloth fast path.  Raises if architecture is unsupported."""
    from unsloth import FastLanguageModel

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=model_name,
        max_seq_length=max_seq_len,
        load_in_4bit=True,
        dtype=None,
    )
    model = FastLanguageModel.get_peft_model(
        model,
        r=lora_r,
        target_modules=LORA_TARGETS,
        lora_alpha=lora_r,
        lora_dropout=0.0,
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=42,
    )
    return model, tokenizer


def _load_with_peft(model_name, max_seq_len, lora_r):
    """Standard HuggingFace + BitsAndBytes + PEFT fallback."""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training

    bnb = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        quantization_config=bnb,
        device_map="auto",
    )
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = prepare_model_for_kbit_training(model)
    lora_cfg = LoraConfig(
        r=lora_r,
        lora_alpha=lora_r,
        target_modules=LORA_TARGETS,
        lora_dropout=0.0,
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora_cfg)
    return model, tokenizer


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", default=BASE_MODEL,
                        help=f"Base HuggingFace model (default: {BASE_MODEL})")
    parser.add_argument("--dataset", default=DATASET_PATH, metavar="FILE",
                        help=f"Training JSONL file (default: {DATASET_PATH})")
    parser.add_argument("--output", default=OUTPUT_DIR, metavar="DIR",
                        help=f"Checkpoint output directory (default: {OUTPUT_DIR})")
    parser.add_argument("--epochs", type=int, default=3,
                        help="Number of training epochs (default: 3)")
    parser.add_argument("--batch-size", type=int, default=2, dest="batch_size",
                        help="Per-device train batch size (default: 2)")
    parser.add_argument("--grad-accum", type=int, default=4, dest="grad_accum",
                        help="Gradient accumulation steps (default: 4)")
    parser.add_argument("--lr", type=float, default=2e-4,
                        help="Learning rate (default: 2e-4)")
    parser.add_argument("--lora-r", type=int, default=16, dest="lora_r",
                        help="LoRA rank r (default: 16)")
    parser.add_argument("--max-seq-len", type=int, default=MAX_SEQ_LEN, dest="max_seq_len",
                        help=f"Max sequence length (default: {MAX_SEQ_LEN})")
    args = parser.parse_args()

    try:
        from transformers import Trainer, TrainingArguments
    except ImportError as exc:
        raise SystemExit(
            f"[ERROR] Missing dependency: {exc}\n"
            "  Run: pip install -r requirements-train.txt"
        )

    Path(args.output).mkdir(parents=True, exist_ok=True)

    # ── Load model + LoRA ───────────────────────────────────────────────────────
    print(f"Loading {args.model} in 4-bit ...")
    use_unsloth = False
    try:
        model, tokenizer = _load_with_unsloth(args.model, args.max_seq_len, args.lora_r)
        use_unsloth = True
        print("  (using Unsloth fast path)")
    except Exception as exc:
        print(f"  Unsloth unavailable ({exc!r}), falling back to standard PEFT ...")
        model, tokenizer = _load_with_peft(args.model, args.max_seq_len, args.lora_r)

    # ── Format dataset ──────────────────────────────────────────────────────────
    # Plain-text completion format to match Ollama inference layout:
    #   {system_prompt}\n\n{user_prompt}\n{output}<eos>
    # Built from a plain Python list to avoid dill pickling Unsloth globals.
    print(f"Loading dataset from {args.dataset} ...")
    import json as _json
    from datasets import Dataset

    eos = tokenizer.eos_token or "<|endoftext|>"

    with open(args.dataset) as f:
        records = [_json.loads(line) for line in f if line.strip()]

    print("Tokenizing ...")
    all_input_ids = []
    for r in records:
        inst = r["instruction"]
        inp  = r.get("input", "")
        out  = r["output"]
        text = f"{inst}\n\n{inp}\n{out}{eos}" if inp else f"{inst}\n{out}{eos}"
        ids = tokenizer(
            text,
            truncation=True,
            max_length=args.max_seq_len,
            padding=False,
            return_attention_mask=False,
        )["input_ids"]
        all_input_ids.append(ids)

    dataset = Dataset.from_dict({"input_ids": all_input_ids, "labels": all_input_ids})
    print(f"Dataset size: {len(dataset)} examples")

    # ── Train ───────────────────────────────────────────────────────────────────
    import torch
    from torch.nn.utils.rnn import pad_sequence

    pad_id = tokenizer.pad_token_id or tokenizer.eos_token_id

    def collate(batch):
        ids = pad_sequence(
            [torch.tensor(ex["input_ids"], dtype=torch.long) for ex in batch],
            batch_first=True, padding_value=pad_id,
        )
        lbl = pad_sequence(
            [torch.tensor(ex["labels"], dtype=torch.long) for ex in batch],
            batch_first=True, padding_value=-100,
        )
        return {"input_ids": ids, "labels": lbl, "attention_mask": (ids != pad_id).long()}

    trainer = Trainer(
        model=model,
        processing_class=tokenizer,
        train_dataset=dataset,
        data_collator=collate,
        args=TrainingArguments(
            output_dir=args.output,
            num_train_epochs=args.epochs,
            per_device_train_batch_size=args.batch_size,
            gradient_accumulation_steps=args.grad_accum,
            warmup_steps=5,
            learning_rate=args.lr,
            fp16=False,
            bf16=True,
            logging_steps=10,
            save_strategy="epoch",
            optim="adamw_8bit",
            weight_decay=0.01,
            lr_scheduler_type="linear",
            report_to="none",
            seed=42,
            dataloader_num_workers=0,
        ),
    )

    print("Starting training ...")
    trainer.train()

    # ── Save checkpoint + metadata ──────────────────────────────────────────────
    final_dir = f"{args.output}/final"
    model.save_pretrained(final_dir)
    tokenizer.save_pretrained(final_dir)

    meta = {"base_model": args.model, "use_unsloth": use_unsloth}
    json.dump(meta, open(f"{final_dir}/training_meta.json", "w"), indent=2)

    print(f"\nCheckpoint saved to {final_dir}")
    print("Next step: python training/merge_export.py")


if __name__ == "__main__":
    main()
