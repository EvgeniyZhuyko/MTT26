FROM python:3.13-slim

# ── System deps: luacheck + curl (health checks) + ollama CLI ─────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        luarocks \
    && luarocks install luacheck \
    && curl -fsSL https://ollama.com/install.sh | sh \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# ── Python deps ────────────────────────────────────────────────────────────────
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt fastapi "uvicorn[standard]"

# ── Application code ───────────────────────────────────────────────────────────
COPY localscript/ ./localscript/
COPY api.py cli.py ./
COPY context/ ./context/
COPY docker/entrypoint.sh /entrypoint.sh

# training/ is mounted at runtime via compose volume (contains the GGUF).
# We copy only the Modelfile so it's available even without the volume.
COPY training/Modelfile ./training/Modelfile

EXPOSE 8080

ENTRYPOINT ["/entrypoint.sh"]
