"""QA verification of corpus metadata using a strong LLM on OpenRouter.

Samples records and asks the LLM to verify: language, document type,
DOI validity, and whether references should be available.

Computes per-field error rates and flags systematic issues.
Target: 99% reliability on the corpus table's numbers.

Usage:
    uv run python scripts/qa_llm_verify.py [--sample N] [--model MODEL]

Requires:
    OPENROUTER_API_KEY environment variable

Outputs:
    - content/tables/qa_llm_verification.csv: per-record verdicts
    - stdout: error rates and confidence intervals
"""

import argparse
import json
import os
import sys
import time

import pandas as pd
import requests

from utils import CATALOGS_DIR, save_csv, BASE_DIR, get_logger

log = get_logger("qa_llm_verify")

DEFAULT_MODEL = "google/gemini-2.5-flash"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def build_prompt(row):
    """Build a verification prompt for one record."""
    title = str(row.get("title", "") or "")[:200]
    abstract = str(row.get("abstract", "") or "")[:500]
    journal = str(row.get("journal", "") or "")
    doi = str(row.get("doi", "") or "")
    language = str(row.get("language", "") or "")
    year = str(row.get("year", "") or "")
    first_author = str(row.get("first_author", "") or "")
    source = str(row.get("source", "") or "")

    text = f"""You are a research librarian verifying bibliographic metadata.

RECORD:
- Title: {title}
- Author: {first_author}
- Year: {year}
- Journal: {journal}
- DOI: {doi}
- Language tag: {language}
- Source database: {source}
- Abstract: {abstract}

Return a JSON object with exactly these keys:
{{"language_correct": true or false, "language_should_be": "xx" or null, "doc_type": "article" or "review" or "book" or "book-chapter" or "report" or "working-paper" or "conference-paper" or "dissertation" or "other", "doi_looks_valid": true or false or "na", "refs_expected": true or false or "uncertain", "is_climate_finance": true or false or "borderline"}}

For language_correct: is "{language}" the correct ISO 639-1 code for the title/abstract language? If the language tag is empty/missing, answer false and provide language_should_be.
For doc_type: classify based on all metadata clues.
For doi_looks_valid: "na" if DOI is empty.
For refs_expected: true if a journal article with a DOI (Crossref likely has references).
For is_climate_finance: does this work study climate finance, green finance, carbon markets, climate adaptation/mitigation funding, or closely related topics?

JSON only, no markdown, no explanation."""

    return text


def call_llm(prompt, api_key, model):
    """Call OpenRouter API and return parsed JSON response."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
        "max_tokens": 300,
    }
    resp = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"].strip()
    # Strip markdown fences if present
    if content.startswith("```"):
        content = content.split("\n", 1)[1] if "\n" in content else content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
    return json.loads(content)


def main():
    parser = argparse.ArgumentParser(description="LLM-based QA verification")
    parser.add_argument("--sample", type=int, default=100,
                        help="Number of records to verify (default: 100)")
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL,
                        help=f"OpenRouter model (default: {DEFAULT_MODEL})")
    args = parser.parse_args()

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        log.error("OPENROUTER_API_KEY not set")
        sys.exit(1)

    path = os.path.join(CATALOGS_DIR, "refined_works.csv")
    df = pd.read_csv(path)
    log.info("Loaded %d works", len(df))

    # Stratified sample: oversample rare sources for better coverage
    PRIMARY_SOURCES = [
        "openalex", "openalex_historical", "istex", "bibcnrs",
        "scispace", "grey", "teaching",
    ]
    # Allocate samples proportional to sqrt(N) for each source
    source_masks = {}
    for src in PRIMARY_SOURCES:
        from_col = f"from_{src}"
        source_masks[src] = df[from_col] == 1 if from_col in df.columns else df["source"].str.contains(src, na=False)

    import numpy as np
    weights = {src: np.sqrt(mask.sum()) for src, mask in source_masks.items()}
    total_weight = sum(weights.values())
    allocations = {src: max(3, int(args.sample * w / total_weight))
                   for src, w in weights.items()}
    # Adjust to hit target
    total_alloc = sum(allocations.values())
    if total_alloc < args.sample:
        allocations["openalex"] += args.sample - total_alloc

    log.info("Sample allocation: %s", allocations)

    sampled = []
    for src, n in allocations.items():
        pool = df[source_masks[src]]
        n_actual = min(n, len(pool))
        if n_actual > 0:
            sampled.append(pool.sample(n_actual, random_state=42))
    sample_df = pd.concat(sampled).drop_duplicates(subset="doi").head(args.sample)
    log.info("Sampled %d records for verification", len(sample_df))

    # Run LLM verification
    results = []
    errors = 0
    for i, (idx, row) in enumerate(sample_df.iterrows()):
        if i % 10 == 0:
            log.info("  Verifying %d/%d...", i + 1, len(sample_df))
        prompt = build_prompt(row)
        try:
            verdict = call_llm(prompt, api_key, args.model)
            verdict["_idx"] = idx
            verdict["_source"] = row.get("source", "")
            verdict["_title"] = str(row.get("title", ""))[:100]
            verdict["_language_tag"] = str(row.get("language", ""))
            verdict["_doi"] = str(row.get("doi", ""))
            results.append(verdict)
        except Exception as e:
            errors += 1
            log.error("  Error on record %s: %s", idx, e)
            if errors > 10:
                log.error("  Too many errors, stopping.")
                break
        # Rate limiting
        time.sleep(0.3)

    if not results:
        log.error("No results. Check API key and model.")
        sys.exit(1)

    rdf = pd.DataFrame(results)
    log.info("Verified %d records (%d errors)", len(rdf), errors)

    # Compute error rates
    log.info("=" * 60)
    log.info("QA VERIFICATION RESULTS")
    log.info("=" * 60)

    # Language accuracy
    lang_correct = rdf["language_correct"].apply(
        lambda x: x is True or str(x).lower() == "true"
    )
    lang_err = 1.0 - lang_correct.mean()
    log.info("Language tag accuracy: %.1f%% (error rate: %.1f%%)",
             lang_correct.mean() * 100, lang_err * 100)
    if not lang_correct.all():
        wrong_lang = rdf[~lang_correct]
        log.info("  Mismatches:")
        for _, r in wrong_lang.head(10).iterrows():
            log.info("    %s -> %s: %s",
                     r.get('_language_tag', '?'),
                     r.get('language_should_be', '?'),
                     r.get('_title', '')[:60])

    # DOI validity
    doi_valid = rdf["doi_looks_valid"].apply(
        lambda x: x is True or str(x).lower() in ("true", "na")
    )
    doi_err = 1.0 - doi_valid.mean()
    log.info("DOI validity: %.1f%% (error rate: %.1f%%)",
             doi_valid.mean() * 100, doi_err * 100)

    # Reference availability
    refs_expected = rdf["refs_expected"].apply(
        lambda x: str(x).lower() if pd.notna(x) else "uncertain"
    )
    log.info("Reference availability (LLM expectation):")
    log.info("  %s", refs_expected.value_counts().to_dict())

    # Document type distribution
    log.info("Document types (LLM classification):")
    log.info("  %s", rdf['doc_type'].value_counts().to_dict())

    # Climate finance relevance
    relevance = rdf["is_climate_finance"].apply(
        lambda x: str(x).lower() if pd.notna(x) else "unknown"
    )
    log.info("Climate finance relevance:")
    log.info("  %s", relevance.value_counts().to_dict())

    # Per-source breakdown
    log.info("=== Per-source error rates ===")
    for src in PRIMARY_SOURCES:
        mask = rdf["_source"] == src
        sub = rdf[mask]
        if len(sub) < 2:
            continue
        lc = sub["language_correct"].apply(
            lambda x: x is True or str(x).lower() == "true"
        ).mean()
        dv = sub["doi_looks_valid"].apply(
            lambda x: x is True or str(x).lower() in ("true", "na")
        ).mean()
        rel = sub["is_climate_finance"].apply(
            lambda x: str(x).lower() in ("true", "borderline")
        ).mean()
        log.info("  %-22s N=%3d  lang=%.0f%%  doi=%.0f%%  relevant=%.0f%%",
                 src, len(sub), lc * 100, dv * 100, rel * 100)

    # Confidence intervals (Wilson score for binomial)
    n = len(rdf)
    from math import sqrt
    z = 1.96  # 95% CI
    for name, rate in [("Language", lang_correct.mean()), ("DOI", doi_valid.mean())]:
        p = rate
        denom = 1 + z**2 / n
        center = (p + z**2 / (2 * n)) / denom
        margin = z * sqrt((p * (1 - p) + z**2 / (4 * n)) / n) / denom
        log.info("%s: %.1f%% [%.1f%%, %.1f%%] (95%% CI)",
                 name, p * 100, (center - margin) * 100, (center + margin) * 100)

    # Save results
    out_path = os.path.join(BASE_DIR, "content", "tables", "qa_llm_verification.csv")
    save_csv(rdf, out_path)
    log.info("Saved detailed results to %s", out_path)


if __name__ == "__main__":
    main()
