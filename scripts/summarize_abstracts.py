"""LLM-generate summaries for oversized abstracts (#415).

~230 records have abstracts >1000 tokens that are actually full introductions,
book reviews, or correction notices. These degrade embedding quality.

This script:
1. Classifies abstracts by length (ok / too_long / missing)
2. Generates ~250-token summaries via LLM for too_long records
3. Caches results in enrich_cache/ (JSONL, keyed by DOI)
4. Updates the DataFrame with summaries and abstract_status column

Usage:
    uv run python scripts/summarize_abstracts.py [--works-input PATH] [--model MODEL]
"""

import argparse
import json
import math
import os
import time

import litellm
import pandas as pd

from utils import CATALOGS_DIR, get_logger, save_run_report, make_run_id

log = get_logger("summarize_abstracts")

# Abstracts longer than this (in whitespace-separated tokens) are summarized
TOKEN_LIMIT = 1000
# Target summary length
TARGET_TOKENS = 250
# Max tokens for LLM response
MAX_RESPONSE_TOKENS = 400
# Cache location
DEFAULT_CACHE_PATH = os.path.join(CATALOGS_DIR, "enrich_cache",
                                   "abstract_summaries_cache.jsonl")
# Default model (litellm provider-prefixed)
DEFAULT_MODEL = "openrouter/deepseek/deepseek-chat-v3-0324"

PROMPT_TEMPLATE = """\
You are an academic abstracting service. Summarize the following text into a \
concise academic abstract of approximately {target} words. Preserve all key \
technical terms, institution names, and findings. Output ONLY the summary, \
no preamble.

Text:
{text}"""


def _count_tokens(text: str) -> int:
    """Count whitespace-separated tokens. Fast approximation."""
    if not text or (isinstance(text, float) and math.isnan(text)):
        return 0
    return len(str(text).split())


def classify_abstract_length(abstract) -> str:
    """Classify an abstract as ok, too_long, or missing."""
    if abstract is None or (isinstance(abstract, float) and math.isnan(abstract)):
        return "missing"
    text = str(abstract).strip()
    if not text:
        return "missing"
    if _count_tokens(text) > TOKEN_LIMIT:
        return "too_long"
    return "ok"


def load_summary_cache(path: str) -> dict:
    """Load JSONL cache: {doi: {summary, model, tokens_original, error}}."""
    if not os.path.exists(path):
        return {}
    cache = {}
    with open(path) as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                doi = entry.pop("doi")
            except (json.JSONDecodeError, KeyError):
                log.warning("Skipping corrupted cache line %d in %s", lineno, path)
                continue
            cache[doi] = entry
    return cache


def save_summary_cache(cache: dict, path: str) -> None:
    """Save cache as JSONL."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        for doi, entry in cache.items():
            row = {"doi": doi, **entry}
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def generate_summary(text: str, *, model: str) -> dict:
    """Generate a summary via LLM. Returns {summary, model, tokens_original, error}."""
    tokens_original = _count_tokens(text)
    try:
        prompt = PROMPT_TEMPLATE.format(target=TARGET_TOKENS, text=text)
        response = litellm.completion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=MAX_RESPONSE_TOKENS,
            temperature=0,
        )
        summary = (response.choices[0].message.content or "").strip()
        if not summary:
            log.warning("LLM returned empty summary for %d-token abstract", tokens_original)
            return {
                "summary": "",
                "model": model,
                "tokens_original": tokens_original,
                "error": "empty response",
            }
        return {
            "summary": summary,
            "model": model,
            "tokens_original": tokens_original,
            "error": None,
        }
    except Exception as e:
        log.error("LLM error for %d-token abstract: %s", tokens_original, e)
        return {
            "summary": "",
            "model": model,
            "tokens_original": tokens_original,
            "error": str(e),
        }


def summarize_too_long_abstracts(
    df: pd.DataFrame,
    *,
    model: str = DEFAULT_MODEL,
    cache_path: str = DEFAULT_CACHE_PATH,
    checkpoint_every: int = 50,
) -> pd.DataFrame:
    """Classify abstracts and generate LLM summaries for too_long ones.

    Returns a copy of df with:
    - abstract_status column: "original" | "generated" | "missing"
    - abstract column: replaced with summary for too_long records
    """
    result = df.copy()

    # Classify all abstracts
    result["abstract_status"] = result["abstract"].apply(classify_abstract_length)

    too_long_mask = result["abstract_status"] == "too_long"
    # Reclassify: ok → original (these won't be touched)
    result.loc[result["abstract_status"] == "ok", "abstract_status"] = "original"

    n_too_long = too_long_mask.sum()
    if n_too_long == 0:
        log.info("No oversized abstracts found")
        return result

    log.info("Found %d oversized abstracts (>%d tokens)", n_too_long, TOKEN_LIMIT)

    # Load cache
    cache = load_summary_cache(cache_path)
    cached_count = 0
    generated_count = 0
    skipped_no_doi = 0

    try:
        for i, idx in enumerate(result.index[too_long_mask]):
            doi = result.at[idx, "doi"]

            # Skip records without a usable DOI — NaN keys corrupt JSON cache
            if pd.isna(doi):
                skipped_no_doi += 1
                result.at[idx, "abstract_status"] = "too_long"
                continue
            doi = str(doi)

            # Check cache
            if doi in cache and cache[doi]["error"] is None:
                result.at[idx, "abstract"] = cache[doi]["summary"]
                result.at[idx, "abstract_status"] = "generated"
                cached_count += 1
                continue

            # Generate summary
            original_text = str(result.at[idx, "abstract"])
            entry = generate_summary(original_text, model=model)
            cache[doi] = entry

            if entry["error"] is None:
                result.at[idx, "abstract"] = entry["summary"]
                result.at[idx, "abstract_status"] = "generated"
                generated_count += 1
            else:
                # Keep original on error — don't lose data
                log.warning("Keeping original abstract for %s (LLM error)", doi)
                result.at[idx, "abstract_status"] = "too_long"

            # Checkpoint every N LLM calls (successes + errors, not cache hits)
            if (i + 1) % checkpoint_every == 0:
                save_summary_cache(cache, cache_path)
                log.info("Checkpoint at item %d: %d generated, %d cached",
                         i + 1, generated_count, cached_count)

            # Rate limit (skip in tests where model is test/*)
            if not model.startswith("test/"):
                time.sleep(0.5)
    finally:
        # Save cache even on interrupt so completed work isn't lost
        save_summary_cache(cache, cache_path)

    if skipped_no_doi:
        log.warning("Skipped %d records with no DOI (cannot cache)", skipped_no_doi)
    log.info("Done: %d cached, %d generated, %d total too_long",
             cached_count, generated_count, n_too_long)

    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--works-input",
        default=os.path.join(CATALOGS_DIR, "enriched_works.csv"),
        help="Works CSV to process (default: enriched_works.csv)",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("SUMMARIZE_MODEL", DEFAULT_MODEL),
        help="LiteLLM model string (default: %(default)s)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Classify and report counts without calling LLM",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Run identifier for report (default: UTC timestamp)",
    )
    args = parser.parse_args()

    run_id = args.run_id or make_run_id()
    t0 = time.time()

    df = pd.read_csv(args.works_input, low_memory=False)
    log.info("Loaded %d works from %s", len(df), args.works_input)

    if args.dry_run:
        statuses = df["abstract"].apply(classify_abstract_length)
        for status, count in statuses.value_counts().items():
            log.info("  %s: %d", status, count)
        return

    result = summarize_too_long_abstracts(df, model=args.model)

    # Report
    status_counts = result["abstract_status"].value_counts().to_dict()
    for status, count in status_counts.items():
        log.info("  %s: %d", status, count)

    # Cache-only: join_enrichments.py applies summaries to the monolith (#428)

    elapsed = time.time() - t0
    counters = {
        "total_works": len(df),
        "model": args.model,
        "elapsed_seconds": round(elapsed, 1),
        **{f"status_{k}": v for k, v in status_counts.items()},
    }
    report_path = save_run_report(counters, run_id, "summarize_abstracts")
    log.info("Run report: %s", report_path)


if __name__ == "__main__":
    main()
