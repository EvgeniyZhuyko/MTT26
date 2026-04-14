"""Thin HTTP client for the Ollama /api/generate endpoint."""

import os
import requests

# Allow compose.yml or env to override the host without code changes.
_OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

# Fixed evaluation parameters — match the hackathon judge's runner.
_DEFAULT_NUM_CTX     = 4096
_DEFAULT_NUM_PREDICT = 256
_DEFAULT_TEMPERATURE = 0.1


def generate(
    prompt: str,
    system: str,
    model: str,
    num_ctx: int = _DEFAULT_NUM_CTX,
    num_predict: int = _DEFAULT_NUM_PREDICT,
) -> str:
    """Call Ollama and return the generated text.

    Args:
        prompt:      The user-turn content.
        system:      The system prompt string.
        model:       Ollama model tag (e.g. 'localscript:latest').
        num_ctx:     Context window size (tokens).
        num_predict: Maximum output tokens.

    Returns:
        Generated text, stripped of leading/trailing whitespace.

    Raises:
        requests.HTTPError: On non-2xx response from Ollama.
        requests.ConnectionError: If Ollama is not running.
    """
    # The model is a plain completion model trained on:
    #   {instruction}\n\n{input}\n{output}
    # Passing `system` separately makes Ollama format the prompt differently,
    # causing the model to generate text continuations instead of code.
    # Build one flat string matching the training format exactly.
    full_prompt = f"{system}\n\n{prompt}\n"

    payload = {
        "model": model,
        "prompt": full_prompt,
        "stream": False,
        "options": {
            "num_ctx": num_ctx,
            "num_predict": num_predict,
            "temperature": _DEFAULT_TEMPERATURE,
            "top_p": 0.9,
        },
    }

    try:
        response = requests.post(
            f"{_OLLAMA_HOST}/api/generate",
            json=payload,
            timeout=120,
        )
        response.raise_for_status()
    except requests.ConnectionError:
        raise requests.ConnectionError(
            f"Cannot reach Ollama at {_OLLAMA_HOST}. "
            "Is 'ollama serve' running?"
        )

    return response.json()["response"].strip()
