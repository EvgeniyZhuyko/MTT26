#!/usr/bin/env bash
set -euo pipefail

OLLAMA_HOST="${OLLAMA_HOST:-http://ollama:11434}"
HUB_MODEL="andreysitaev/hkt_octapi_lua_mpl:latest"
LOCAL_ALIAS="localscript:latest"

# ── Wait for Ollama ────────────────────────────────────────────────────────────
echo "[entrypoint] Waiting for Ollama at ${OLLAMA_HOST} ..."
until curl -sf "${OLLAMA_HOST}/api/tags" > /dev/null 2>&1; do
  sleep 2
done
echo "[entrypoint] Ollama is ready."

# ── Pull fine-tuned model from Ollama Hub ──────────────────────────────────────
if OLLAMA_HOST="${OLLAMA_HOST}" ollama list | grep -q "^${LOCAL_ALIAS%:*}"; then
  echo "[entrypoint] Model ${LOCAL_ALIAS} already present, skipping pull."
else
  echo "[entrypoint] Pulling ${HUB_MODEL} from Ollama Hub ..."
  OLLAMA_HOST="${OLLAMA_HOST}" ollama pull "${HUB_MODEL}"
  OLLAMA_HOST="${OLLAMA_HOST}" ollama cp "${HUB_MODEL}" "${LOCAL_ALIAS}"
  echo "[entrypoint] Model ready as ${LOCAL_ALIAS}."
fi

# ── Start API server ───────────────────────────────────────────────────────────
echo "[entrypoint] Starting API server on :8080 ..."
exec uvicorn api:app --host 0.0.0.0 --port 8080
