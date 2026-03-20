"""LLM backend for the syllabi collection pipeline.

Supports two backends:
  - OpenRouter (cloud): set OPENROUTER_API_KEY env var
  - Ollama (local): set OLLAMA_MODEL env var (e.g. qwen3.5:9b)

Ollama takes precedence if both are set.
"""

import json
import os
import urllib.request

from utils import get_logger

log = get_logger("syllabi_llm")


def llm_call(prompt, api_key, model="google/gemma-2-27b-it", max_tokens=2000):
    """Call LLM via OpenRouter or local Ollama.

    Backend selection:
      - If OLLAMA_MODEL env var is set, use local Ollama (ignores api_key/model).
      - Otherwise, use OpenRouter with the given api_key and model.
    """
    ollama_model = os.environ.get("OLLAMA_MODEL", "")
    if ollama_model:
        return _llm_call_ollama(prompt, ollama_model, max_tokens)
    return _llm_call_openrouter(prompt, api_key, model, max_tokens)


def _llm_call_ollama(prompt, model, max_tokens):
    """Call local Ollama server (OpenAI-compatible API)."""
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0,
        "stream": False,
    }).encode()

    req = urllib.request.Request(
        "http://localhost:11434/v1/chat/completions",
        data=body,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read())
        return result["choices"][0]["message"]["content"].strip()
    except Exception as e:
        log.error("Ollama error: %s", e)
        return None


def _llm_call_openrouter(prompt, api_key, model, max_tokens):
    """Call OpenRouter API."""
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0,
    }).encode()

    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read())
        return result["choices"][0]["message"]["content"].strip()
    except Exception as e:
        log.error("LLM error: %s", e)
        return None
