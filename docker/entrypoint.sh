#!/usr/bin/env bash
set -euo pipefail

OLLAMA_HOST="${OLLAMA_HOST:-http://ollama:11434}"
MODELFILE="/app/training/Modelfile"
GGUF="/app/training/localscript-q4_k_m.gguf"

# ── Wait for Ollama ────────────────────────────────────────────────────────────
echo "[entrypoint] Waiting for Ollama at ${OLLAMA_HOST} ..."
until curl -sf "${OLLAMA_HOST}/api/tags" > /dev/null 2>&1; do
  sleep 2
done
echo "[entrypoint] Ollama is ready."

# ── Register fine-tuned model ──────────────────────────────────────────────────
if [ -f "${GGUF}" ]; then
  echo "[entrypoint] Registering localscript model ..."
  cd /app/training
  OLLAMA_HOST="${OLLAMA_HOST}" ollama create localscript -f Modelfile
  echo "[entrypoint] Model registered."
else
  echo "[entrypoint] WARNING: GGUF not found at ${GGUF}."
  echo "[entrypoint] Run 'make export-model' on the host first, then restart."
  echo "[entrypoint] Continuing — API will start but /generate will fail until a model is available."
fi

# ── Start API server ───────────────────────────────────────────────────────────
echo "[entrypoint] Starting API server on :8080 ..."
exec uvicorn api:app --host 0.0.0.0 --port 8080
