#!/usr/bin/env python3
"""
Merge the LoRA adapter into base weights and convert to GGUF for Ollama.

Steps:
  1. Load fine-tuned checkpoint (LoRA adapter + base model).
  2. Merge adapter into base weights and save as HuggingFace safetensors.
  3. Convert to GGUF Q4_K_M using llama.cpp convert_hf_to_gguf.py.

Prerequisites:
  - Completed training: training/checkpoints/final must exist.
  - llama.cpp cloned and built in ./llama.cpp/ (see instructions below).
  - pip install -r requirements-train.txt

llama.cpp setup (one-time, on the training machine):
  git clone https://github.com/ggerganov/llama.cpp.git
  cd llama.cpp
  make -j$(nproc)                # Linux
  # macOS ARM: make -j$(sysctl -n hw.ncpu)
  pip install -r llama.cpp/requirements.txt

Usage:
  python training/merge_export.py
  python training/merge_export.py --checkpoint training/checkpoints/final \\
      --merged training/merged --gguf training/localscript-q4_k_m.gguf
"""

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--checkpoint", default="training/checkpoints/final",
                        help="Path to the fine-tuned checkpoint directory")
    parser.add_argument("--merged", default="training/merged",
                        help="Output directory for merged HuggingFace weights")
    parser.add_argument("--gguf", default="training/localscript-q4_k_m.gguf",
                        help="Output path for the GGUF file")
    parser.add_argument("--llama-cpp", default="llama.cpp",
                        help="Path to llama.cpp repo (default: ./llama.cpp)")
    args = parser.parse_args()

    checkpoint = Path(args.checkpoint)
    merged_dir = Path(args.merged)
    gguf_path  = Path(args.gguf)
    convert_script = Path(args.llama_cpp) / "convert_hf_to_gguf.py"

    # ── Validate inputs ─────────────────────────────────────────────────────────
    if not checkpoint.exists():
        raise SystemExit(
            f"[ERROR] Checkpoint not found: {checkpoint}\n"
            "  Run training/train.py first."
        )

    if not convert_script.exists():
        raise SystemExit(
            f"[ERROR] llama.cpp convert script not found: {convert_script}\n"
            "  Clone and build llama.cpp:\n"
            "    git clone https://github.com/ggerganov/llama.cpp.git\n"
            "    cd llama.cpp && make -j$(nproc)\n"
            "    pip install -r llama.cpp/requirements.txt"
        )

    # ── Step 1: Merge LoRA adapter into base weights ────────────────────────────
    print(f"Step 1/2: Merging adapter from {checkpoint} ...")
    try:
        from unsloth import FastLanguageModel
    except ImportError:
        raise SystemExit(
            "[ERROR] unsloth not installed. Run: pip install -r requirements-train.txt"
        )

    model, tokenizer = FastLanguageModel.from_pretrained(
        str(checkpoint),
        max_seq_length=1024,
        load_in_4bit=False,   # load full precision for merging
        dtype=None,
    )

    merged_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained_merged(
        str(merged_dir),
        tokenizer,
        save_method="merged_16bit",
    )
    print(f"  Merged weights saved to {merged_dir}")

    # ── Step 2: Convert to GGUF Q4_K_M ─────────────────────────────────────────
    print(f"\nStep 2/2: Converting to GGUF ({gguf_path}) ...")
    gguf_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        str(convert_script),
        str(merged_dir),
        "--outtype", "q4_k_m",
        "--outfile", str(gguf_path),
    ]
    result = subprocess.run(cmd, check=True)

    print(f"\nGGUF saved to {gguf_path}")
    print("\nNext step: register with Ollama:")
    print(f"  cd training && ollama create localscript -f Modelfile")
    print(f"  ollama list")


if __name__ == "__main__":
    main()
