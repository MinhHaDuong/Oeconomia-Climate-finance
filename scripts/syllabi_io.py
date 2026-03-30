"""I/O helpers and LLM utilities for the syllabi collection pipeline.

Extracted from catalog_syllabi.py to keep the main script under the
god-module 800-line threshold (see test_script_hygiene.py).

Public API (all re-exported by catalog_syllabi.py):
  CHUNK_SIZE, CHUNK_OVERLAP, MAX_TEXT_CHARS
  load_jsonl, append_jsonl
  extract_pdf_text
  make_chunks
  llm_call
  extract_json_from_text
"""

import json
import logging
import os
import re
import threading

# --- Constants ---
# No text truncation — make_chunks() handles splitting for LLM calls.
# Tested: 20K chunks cause 0 extractions with gemma-2-27b-it on dense
# bibliographies (Harvard FECS). 8K works. Model-dependent — recalibrate
# if switching models (see #289).
CHUNK_SIZE = 8000       # ~2K tokens per chunk — proven to work with gemma-2-27b-it
CHUNK_OVERLAP = 500     # Overlap between chunks to avoid splitting references at boundaries
MAX_TEXT_CHARS = 500000 # Skip pages over 500K chars (misclassified books/reports, not syllabi)

_log = logging.getLogger("pipeline.syllabi_io")


def load_jsonl(path):
    """Load all records from a JSONL file."""
    records = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
    return records


_jsonl_lock = threading.Lock()


def append_jsonl(records, path):
    """Append records to a JSONL file (thread-safe)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with _jsonl_lock, open(path, "a", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def extract_pdf_text(pdf_path, page_cap=50):
    """Extract text from a PDF using pdfplumber's extract_text().

    Table extraction (extract_tables) was removed because it duplicates
    reading list text as pipe-separated rows alongside the normal body text,
    confusing the LLM in overlapping chunks. pdfplumber's extract_text()
    already captures table content in most PDFs.
    """
    import pdfplumber

    text_parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages[:page_cap]:
            t = page.extract_text()
            if t:
                text_parts.append(t)
    return "\n\n".join(text_parts)


def make_chunks(text, chunk_size=CHUNK_SIZE, overlap=None):
    """Split text into overlapping chunks for LLM extraction.

    Overlap prevents references from being split across chunk boundaries.
    """
    if overlap is None:
        overlap = CHUNK_OVERLAP
    if overlap >= chunk_size:
        raise ValueError(f"overlap ({overlap}) must be < chunk_size ({chunk_size})")
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap  # Step back by overlap amount
        if start + overlap >= len(text):
            break  # Last chunk captured everything
    return chunks


def llm_call(prompt, model="openrouter/google/gemma-2-27b-it", max_tokens=2000):
    """Call LLM via litellm. Model string encodes the provider.

    Examples:
        ollama/qwen3.5:27b          → routes to local Ollama
        openrouter/google/gemma-2-27b-it → routes to OpenRouter

    litellm reads OPENROUTER_API_KEY from env automatically.

    """
    import litellm

    # Prepend /no_think for Qwen models on Ollama to suppress chain-of-thought
    actual_prompt = prompt
    if model.startswith("ollama/") and "qwen" in model.lower():
        actual_prompt = "/no_think\n" + prompt

    try:
        response = litellm.completion(
            model=model,
            messages=[{"role": "user", "content": actual_prompt}],
            max_tokens=max_tokens,
            temperature=0,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        _log.error("LLM error (%s): %s", model, e)
        return None


def extract_json_from_text(text):
    """Extract the first JSON object or array from LLM response text."""
    if not text:
        return None
    # Try to find JSON block in markdown code fence
    m = re.search(r"```(?:json)?\s*\n?([\s\S]*?)\n?```", text)
    if m:
        text = m.group(1)
    # Try to parse the whole thing
    text = text.strip()
    for start_char, end_char in [("{", "}"), ("[", "]")]:
        idx_start = text.find(start_char)
        idx_end = text.rfind(end_char)
        if idx_start != -1 and idx_end > idx_start:
            candidate = text[idx_start:idx_end + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue
    return None
