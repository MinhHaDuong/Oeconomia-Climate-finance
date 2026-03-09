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

sys.path.insert(0, os.path.dirname(__file__))
from utils import CATALOGS_DIR, save_csv, BASE_DIR

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
Given this record, answer each question with a JSON object.

RECORD:
  Title: {title}
  Author: {first_author}
  Year: {year}
  Journal: {journal}
  DOI: {doi}
  Language tag: {language}
  Source: {source}
  Abstract (truncated): {abstract}

QUESTIONS (answer in JSON):
1. "language_correct": Is the language tag "{language}" correct for this record's
   title/abstract text? Answer true/false. If false, give "language_should_be" (ISO 639-1 code).
2. "doc_type": What type of document is this? One of: article, review, book,
   book-chapter, report, working-paper, conference-paper, dissertation, other.
3. "doi_looks_valid": Does the DOI "{doi}" look like a plausible DOI for this record?
   Answer true/false/na (na if no DOI).
4. "refs_expected": Would you expect Crossref to have reference data for this record?
   Answer true (journal article with DOI), false (grey lit, book, no DOI), or uncertain.
5. "is_climate_finance": Is this record genuinely about climate finance or closely related?
   Answer true/false/borderline.

Respond ONLY with a JSON object, no markdown fences, no explanation."""

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
        print("ERROR: OPENROUTER_API_KEY not set")
        sys.exit(1)

    path = os.path.join(CATALOGS_DIR, "refined_works.csv")
    df = pd.read_csv(path)
    print(f"Loaded {len(df)} works")

    # Stratified sample: oversample rare sources for better coverage
    PRIMARY_SOURCES = [
        "openalex", "openalex_historical", "istex", "bibcnrs",
        "scispsace", "grey", "teaching",
    ]
    # Allocate samples proportional to sqrt(N) for each source
    source_masks = {}
    for src in PRIMARY_SOURCES:
        source_masks[src] = df["source"].str.contains(src, na=False)

    import numpy as np
    weights = {src: np.sqrt(mask.sum()) for src, mask in source_masks.items()}
    total_weight = sum(weights.values())
    allocations = {src: max(3, int(args.sample * w / total_weight))
                   for src, w in weights.items()}
    # Adjust to hit target
    total_alloc = sum(allocations.values())
    if total_alloc < args.sample:
        allocations["openalex"] += args.sample - total_alloc

    print(f"\nSample allocation: {allocations}")

    sampled = []
    for src, n in allocations.items():
        pool = df[source_masks[src]]
        n_actual = min(n, len(pool))
        if n_actual > 0:
            sampled.append(pool.sample(n_actual, random_state=42))
    sample_df = pd.concat(sampled).drop_duplicates(subset="doi").head(args.sample)
    print(f"Sampled {len(sample_df)} records for verification")

    # Run LLM verification
    results = []
    errors = 0
    for i, (idx, row) in enumerate(sample_df.iterrows()):
        if i % 10 == 0:
            print(f"  Verifying {i+1}/{len(sample_df)}...")
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
            print(f"  Error on record {idx}: {e}")
            if errors > 10:
                print("  Too many errors, stopping.")
                break
        # Rate limiting
        time.sleep(0.3)

    if not results:
        print("No results. Check API key and model.")
        sys.exit(1)

    rdf = pd.DataFrame(results)
    print(f"\nVerified {len(rdf)} records ({errors} errors)")

    # Compute error rates
    print(f"\n{'='*60}")
    print("QA VERIFICATION RESULTS")
    print(f"{'='*60}")

    # Language accuracy
    lang_correct = rdf["language_correct"].apply(
        lambda x: x is True or str(x).lower() == "true"
    )
    lang_err = 1.0 - lang_correct.mean()
    print(f"\nLanguage tag accuracy: {lang_correct.mean()*100:.1f}% "
          f"(error rate: {lang_err*100:.1f}%)")
    if not lang_correct.all():
        wrong_lang = rdf[~lang_correct]
        print("  Mismatches:")
        for _, r in wrong_lang.head(10).iterrows():
            print(f"    {r.get('_language_tag','?')} → {r.get('language_should_be','?')}: "
                  f"{r.get('_title','')[:60]}")

    # DOI validity
    doi_valid = rdf["doi_looks_valid"].apply(
        lambda x: x is True or str(x).lower() in ("true", "na")
    )
    doi_err = 1.0 - doi_valid.mean()
    print(f"\nDOI validity: {doi_valid.mean()*100:.1f}% "
          f"(error rate: {doi_err*100:.1f}%)")

    # Reference availability
    refs_expected = rdf["refs_expected"].apply(
        lambda x: str(x).lower() if pd.notna(x) else "uncertain"
    )
    print(f"\nReference availability (LLM expectation):")
    print(f"  {refs_expected.value_counts().to_dict()}")

    # Document type distribution
    print(f"\nDocument types (LLM classification):")
    print(f"  {rdf['doc_type'].value_counts().to_dict()}")

    # Climate finance relevance
    relevance = rdf["is_climate_finance"].apply(
        lambda x: str(x).lower() if pd.notna(x) else "unknown"
    )
    print(f"\nClimate finance relevance:")
    print(f"  {relevance.value_counts().to_dict()}")

    # Per-source breakdown
    print(f"\n=== Per-source error rates ===")
    for src in PRIMARY_SOURCES:
        mask = rdf["_source"].str.contains(src, na=False)
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
        print(f"  {src:<22} N={len(sub):>3}  lang={lc*100:.0f}%  "
              f"doi={dv*100:.0f}%  relevant={rel*100:.0f}%")

    # Confidence intervals (Wilson score for binomial)
    n = len(rdf)
    from math import sqrt
    z = 1.96  # 95% CI
    for name, rate in [("Language", lang_correct.mean()), ("DOI", doi_valid.mean())]:
        p = rate
        denom = 1 + z**2 / n
        center = (p + z**2 / (2 * n)) / denom
        margin = z * sqrt((p * (1 - p) + z**2 / (4 * n)) / n) / denom
        print(f"\n{name}: {p*100:.1f}% [{(center-margin)*100:.1f}%, {(center+margin)*100:.1f}%] (95% CI)")

    # Save results
    out_path = os.path.join(BASE_DIR, "content", "tables", "qa_llm_verification.csv")
    save_csv(rdf, out_path)
    print(f"\nSaved detailed results to {out_path}")


if __name__ == "__main__":
    main()
