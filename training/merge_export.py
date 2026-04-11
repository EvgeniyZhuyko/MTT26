#!/usr/bin/env python3
"""
Merge the LoRA adapter into base weights and export to GGUF for Ollama.

Handles both Unsloth-trained and standard-PEFT-trained checkpoints
(auto-detected from training_meta.json saved by train.py).

Unsloth path  — merge + GGUF conversion in one step, no llama.cpp needed.
Standard-PEFT — merge with PEFT, then convert via llama.cpp.

llama.cpp setup (only needed for the standard-PEFT path):
  git clone https://github.com/ggerganov/llama.cpp.git
  pip install -r llama.cpp/requirements.txt

Usage:
  python training/merge_export.py
  python training/merge_export.py --checkpoint training/checkpoints/final \\
      --gguf training/localscript-q4_k_m.gguf
"""

import argparse
import glob
import json
import shutil
import subprocess
import sys
from pathlib import Path


def _export_unsloth(checkpoint: Path, gguf_path: Path) -> None:
    """Merge LoRA + quantise to GGUF in one step using Unsloth."""
    from unsloth import FastLanguageModel

    model, tokenizer = FastLanguageModel.from_pretrained(
        str(checkpoint),
        max_seq_length=1024,
        load_in_4bit=False,
        dtype=None,
    )

    tmp_dir = str(gguf_path.parent / "_gguf_tmp")
    print(f"  Saving GGUF to {tmp_dir} ...")
    model.save_pretrained_gguf(tmp_dir, tokenizer, quantization_method="q4_k_m")

    # Unsloth names the file unsloth.Q4_K_M.gguf inside the dir.
    candidates = glob.glob(f"{tmp_dir}/*.gguf")
    if not candidates:
        raise RuntimeError(f"No .gguf file found in {tmp_dir}")
    shutil.move(candidates[0], str(gguf_path))
    shutil.rmtree(tmp_dir, ignore_errors=True)


def _export_peft(checkpoint: Path, gguf_path: Path,
                 base_model: str, llama_cpp: str) -> None:
    """Merge with standard PEFT then convert via llama.cpp (two-step: f16 → Q4_K_M)."""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel

    merged_dir = gguf_path.parent / "merged"
    convert_script = Path(llama_cpp) / "convert_hf_to_gguf.py"
    quantize_bin = Path(llama_cpp) / "build" / "bin" / "llama-quantize"

    if not convert_script.exists():
        raise SystemExit(
            f"[ERROR] llama.cpp convert script not found: {convert_script}\n"
            "  git clone https://github.com/ggerganov/llama.cpp.git\n"
            "  pip install -r llama.cpp/requirements.txt"
        )

    if not quantize_bin.exists():
        raise SystemExit(
            f"[ERROR] llama-quantize not found: {quantize_bin}\n"
            "  cd llama.cpp && cmake -B build && cmake --build build --target llama-quantize -j$(nproc)"
        )

    print(f"  Loading base model {base_model} in fp16 (CPU) ...")
    tokenizer = AutoTokenizer.from_pretrained(base_model)
    base = AutoModelForCausalLM.from_pretrained(
        base_model, torch_dtype=torch.float16, device_map="cpu"
    )
    print(f"  Merging LoRA adapter from {checkpoint} ...")
    model = PeftModel.from_pretrained(base, str(checkpoint))
    model = model.merge_and_unload()
    merged_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(merged_dir))
    tokenizer.save_pretrained(str(merged_dir))
    print(f"  Merged weights saved to {merged_dir}")

    # Step 1: convert to f16 GGUF (newer llama.cpp doesn't support --outtype q4_k_m directly)
    f16_path = gguf_path.with_suffix("").with_name(gguf_path.stem.replace("q4_k_m", "f16") + ".gguf")
    print(f"  Step 1/2: Converting to f16 GGUF ({f16_path}) ...")
    subprocess.run([
        sys.executable, str(convert_script),
        str(merged_dir), "--outtype", "f16", "--outfile", str(f16_path),
    ], check=True)

    # Step 2: quantize f16 → Q4_K_M
    print(f"  Step 2/2: Quantizing to Q4_K_M ({gguf_path}) ...")
    subprocess.run([str(quantize_bin), str(f16_path), str(gguf_path), "Q4_K_M"], check=True)
    f16_path.unlink(missing_ok=True)
    print(f"  Intermediate f16 GGUF removed.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--checkpoint", default="training/checkpoints/final",
                        help="Fine-tuned checkpoint directory")
    parser.add_argument("--gguf", default="training/localscript-q4_k_m.gguf",
                        help="Output path for the GGUF file")
    parser.add_argument("--llama-cpp", default="llama.cpp",
                        help="Path to llama.cpp repo (standard-PEFT path only)")
    args = parser.parse_args()

    checkpoint = Path(args.checkpoint)
    gguf_path  = Path(args.gguf)

    if not checkpoint.exists():
        raise SystemExit(
            f"[ERROR] Checkpoint not found: {checkpoint}\n"
            "  Run training/train.py first."
        )

    meta_path = checkpoint / "training_meta.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    use_unsloth = meta.get("use_unsloth", False)
    base_model  = meta.get("base_model", "nuprl/MultiPLCoder-1b")

    gguf_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Exporting {checkpoint} → {gguf_path}")
    print(f"  Path: {'Unsloth' if use_unsloth else 'standard PEFT'}")

    if use_unsloth:
        try:
            _export_unsloth(checkpoint, gguf_path)
        except Exception as exc:
            print(f"  Unsloth export failed ({exc!r}), falling back to PEFT path ...")
            _export_peft(checkpoint, gguf_path, base_model, args.llama_cpp)
    else:
        _export_peft(checkpoint, gguf_path, base_model, args.llama_cpp)

    size_mb = gguf_path.stat().st_size / 1e6
    print(f"\nGGUF saved: {gguf_path} ({size_mb:.0f} MB)")
    print("Next step:")
    print("  cd training && ollama create localscript -f Modelfile")
    print("  ollama list")


if __name__ == "__main__":
    main()
