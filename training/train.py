#!/usr/bin/env python3
"""
QLoRA fine-tuning for LocalScript using Unsloth + SFTTrainer.

Trains Qwen/Qwen2.5-Coder-7B-Instruct on the combined JSONL dataset
(generator + analyst + critic roles) with 4-bit quantisation.

Requirements:
  pip install -r requirements-train.txt
  CUDA GPU with ≥16 GB VRAM recommended (tested on A100/T4 in Colab).

Usage:
  python training/train.py
  python training/train.py --dataset data/train.jsonl --epochs 3 --output training/checkpoints
"""

import argparse
from pathlib import Path

# ── Defaults ───────────────────────────────────────────────────────────────────

BASE_MODEL   = "Qwen/Qwen2.5-Coder-7B-Instruct"
DATASET_PATH = "data/train.jsonl"
OUTPUT_DIR   = "training/checkpoints"
MAX_SEQ_LEN  = 1024   # covers all seed examples comfortably within 256-token output budget


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
    args = parser.parse_args()

    # Imports here so the script fails fast with a clear error if deps missing.
    try:
        from unsloth import FastLanguageModel
        from unsloth.chat_templates import get_chat_template
        from datasets import load_dataset
        from trl import SFTTrainer
        from transformers import TrainingArguments
    except ImportError as exc:
        raise SystemExit(
            f"[ERROR] Missing dependency: {exc}\n"
            "  Run: pip install -r requirements-train.txt"
        )

    Path(args.output).mkdir(parents=True, exist_ok=True)

    # ── Load base model in 4-bit ────────────────────────────────────────────────
    print(f"Loading {args.model} in 4-bit ...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=args.model,
        max_seq_length=MAX_SEQ_LEN,
        load_in_4bit=True,
        dtype=None,   # auto-detect
    )

    # Apply Qwen 2.5 chat template so generation format matches inference.
    tokenizer = get_chat_template(tokenizer, chat_template="qwen-2.5")

    # ── Attach LoRA adapter ─────────────────────────────────────────────────────
    model = FastLanguageModel.get_peft_model(
        model,
        r=args.lora_r,
        target_modules=[
            "q_proj", "v_proj", "k_proj", "o_proj",
            "gate_proj", "up_proj", "down_proj",
        ],
        lora_alpha=args.lora_r,   # alpha = r is a stable default
        lora_dropout=0.0,
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=42,
    )

    # ── Format dataset ──────────────────────────────────────────────────────────
    print(f"Loading dataset from {args.dataset} ...")
    raw = load_dataset("json", data_files=args.dataset, split="train")

    def _format(batch):
        texts = []
        for inst, inp, out in zip(
            batch["instruction"],
            batch.get("input", [""] * len(batch["instruction"])),
            batch["output"],
        ):
            user_content = f"{inp}\n\n{inst}" if inp else inst
            messages = [
                {"role": "user",      "content": user_content},
                {"role": "assistant", "content": out},
            ]
            text = tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=False
            )
            texts.append(text)
        return {"text": texts}

    dataset = raw.map(_format, batched=True, remove_columns=raw.column_names)
    print(f"Dataset size: {len(dataset)} examples")

    # ── Train ───────────────────────────────────────────────────────────────────
    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        dataset_text_field="text",
        max_seq_length=MAX_SEQ_LEN,
        dataset_num_proc=2,
        args=TrainingArguments(
            output_dir=args.output,
            num_train_epochs=args.epochs,
            per_device_train_batch_size=args.batch_size,
            gradient_accumulation_steps=args.grad_accum,
            warmup_steps=5,
            learning_rate=args.lr,
            fp16=True,
            logging_steps=10,
            save_strategy="epoch",
            optim="adamw_8bit",
            weight_decay=0.01,
            lr_scheduler_type="linear",
            report_to="none",
            seed=42,
        ),
    )

    print("Starting training ...")
    trainer.train()

    final_dir = f"{args.output}/final"
    model.save_pretrained(final_dir)
    tokenizer.save_pretrained(final_dir)
    print(f"\nCheckpoint saved to {final_dir}")
    print("Next step: python training/merge_export.py")


if __name__ == "__main__":
    main()
