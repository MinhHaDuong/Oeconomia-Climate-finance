#!/usr/bin/env python3
"""Metadata accuracy spot-check: verify titles and years against Crossref ground truth.

Randomly samples works from refined_works.csv, stratified by source, and
independently verifies metadata against Crossref (for works with DOIs) and
OpenAlex title search (for works without DOIs).

Checks:
  - Title: fuzzy match (difflib.SequenceMatcher ratio > 0.85)
  - Year: exact match
  - DOI resolution: HTTP HEAD to https://doi.org/{doi}

Reports proportions with 95% Wilson confidence intervals.

Saves results to content/tables/qa_metadata_report.json

Usage:
    uv run python scripts/qa_metadata.py [--sample-n 100] [--seed 42]
"""

import argparse
import difflib
import json
import os
import sys
import time

import numpy as np
import pandas as pd
import requests
from scipy.stats import binomtest

from utils import CATALOGS_DIR, MAILTO, normalize_doi, get_logger

log = get_logger("qa_metadata")

HEADERS = {"User-Agent": f"ClimateFinancePipeline/1.0 (mailto:{MAILTO})"}
OUTPUT_PATH = os.path.join(
    os.path.dirname(__file__), "..", "content", "tables", "qa_metadata_report.json"
)

CROSSREF_DELAY = 0.15  # seconds between Crossref API calls
DOI_RESOLVE_TIMEOUT = 15  # seconds for DOI resolution HEAD request
TITLE_MATCH_THRESHOLD = 0.85  # SequenceMatcher ratio for "match"


def wilson_ci(successes, n, confidence=0.95):
    """Compute Wilson score confidence interval for a proportion.

    Returns (proportion, ci_lower, ci_upper).
    """
    if n == 0:
        return (0.0, 0.0, 0.0)
    result = binomtest(successes, n)
    ci = result.proportion_ci(confidence_level=confidence, method="wilson")
    return (successes / n, float(ci.low), float(ci.high))


def normalize_title(title):
    """Lowercase, strip whitespace and punctuation for comparison."""
    if not isinstance(title, str):
        return ""
    import re
    return re.sub(r"[^\w\s]", "", title.lower()).strip()


def title_similarity(our_title, crossref_title):
    """Compute SequenceMatcher ratio between normalized titles."""
    a = normalize_title(our_title)
    b = normalize_title(crossref_title)
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def fetch_crossref_metadata(doi):
    """Fetch title and year from Crossref for a DOI.

    Returns (title, year, status) where status is 'ok', 'not_in_crossref',
    or an error string.
    """
    url = f"https://api.crossref.org/works/{doi}"
    try:
        time.sleep(CROSSREF_DELAY)
        resp = requests.get(
            url, headers=HEADERS, timeout=30, params={"mailto": MAILTO}
        )
        if resp.status_code == 404:
            return None, None, "not_in_crossref"
        if resp.status_code != 200:
            return None, None, f"HTTP {resp.status_code}"
        data = resp.json()["message"]
        title_parts = data.get("title", [])
        title = title_parts[0] if title_parts else ""
        # Year: try published-print, then published-online, then created
        year = None
        for field in ("published-print", "published-online", "created"):
            date_parts = data.get(field, {}).get("date-parts", [[]])
            if date_parts and date_parts[0] and date_parts[0][0]:
                year = int(date_parts[0][0])
                break
        return title, year, "ok"
    except Exception as e:
        return None, None, f"error: {e}"


def check_doi_resolves(doi):
    """Check if a DOI resolves via doi.org (HTTP HEAD).

    Returns True if we get a 200 or redirect (302/301), False otherwise.
    """
    url = f"https://doi.org/{doi}"
    try:
        resp = requests.head(
            url, headers=HEADERS, timeout=DOI_RESOLVE_TIMEOUT, allow_redirects=True
        )
        return resp.status_code in (200, 301, 302)
    except Exception:
        return False


def search_openalex_by_title(title):
    """Search OpenAlex for a work by title, return best match (title, year) or None."""
    if not isinstance(title, str) or not title.strip():
        return None, None, "empty_title"
    url = "https://api.openalex.org/works"
    params = {
        "search": title[:200],  # Truncate very long titles
        "per_page": 1,
        "mailto": MAILTO,
    }
    try:
        time.sleep(CROSSREF_DELAY)
        resp = requests.get(url, params=params, headers=HEADERS, timeout=30)
        if resp.status_code != 200:
            return None, None, f"HTTP {resp.status_code}"
        results = resp.json().get("results", [])
        if not results:
            return None, None, "no_results"
        best = results[0]
        oa_title = best.get("title", "")
        oa_year = best.get("publication_year")
        return oa_title, oa_year, "ok"
    except Exception as e:
        return None, None, f"error: {e}"


def stratified_sample(df, n, seed, group_col="source"):
    """Sample n rows stratified by group_col."""
    rng = np.random.RandomState(seed)
    groups = df[group_col].unique()
    samples = []
    for grp in groups:
        sub = df[df[group_col] == grp]
        k = max(1, int(n * len(sub) / len(df)))
        k = min(k, len(sub))
        samples.append(sub.sample(k, random_state=rng))
    result = pd.concat(samples)
    # If we got more than n due to rounding, trim; if fewer, that's ok
    if len(result) > n:
        result = result.sample(n, random_state=rng)
    return result


def main():
    parser = argparse.ArgumentParser(
        description="QA metadata: spot-check titles/years against Crossref"
    )
    parser.add_argument(
        "--sample-n", type=int, default=100,
        help="Number of works with DOIs to verify (default 100)"
    )
    parser.add_argument(
        "--no-doi-n", type=int, default=30,
        help="Number of works without DOIs to verify via OpenAlex (default 30)"
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--works-input",
        default=os.path.join(CATALOGS_DIR, "refined_works.csv"),
        help="Works CSV (default: refined_works.csv)"
    )
    args = parser.parse_args()

    # ── Load data ────────────────────────────────────────────────────────────────
    works_path = args.works_input
    if not os.path.isfile(works_path):
        log.error("Works file not found: %s", works_path)
        sys.exit(1)

    works = pd.read_csv(works_path, low_memory=False)
    works["doi_norm"] = works["doi"].apply(normalize_doi)
    log.info("Loaded %d works from %s", len(works), works_path)

    has_doi = works[
        works["doi_norm"].notna()
        & (works["doi_norm"] != "")
        & (works["doi_norm"] != "nan")
        & (works["doi_norm"] != "none")
    ].copy()
    no_doi = works[
        works["doi_norm"].isna()
        | (works["doi_norm"] == "")
        | (works["doi_norm"] == "nan")
        | (works["doi_norm"] == "none")
    ].copy()

    log.info("Works with DOI: %d, without DOI: %d", len(has_doi), len(no_doi))

    # ── Sample 1: Works with DOIs → verify against Crossref ──────────────────
    n_doi_sample = min(args.sample_n, len(has_doi))
    doi_sample = stratified_sample(has_doi, n_doi_sample, args.seed)
    log.info("Sampled %d works with DOIs, querying Crossref...", len(doi_sample))

    title_matches = 0
    title_checked = 0
    year_matches = 0
    year_within_one = 0  # off-by-one (online-first vs print date)
    year_checked = 0
    doi_resolves = 0
    doi_checked = 0
    details = []

    for i, (_, row) in enumerate(doi_sample.iterrows()):
        doi = row["doi_norm"]
        our_title = str(row.get("title", ""))
        our_year = row.get("year")
        if pd.notna(our_year):
            our_year = int(our_year)
        else:
            our_year = None

        cr_title, cr_year, status = fetch_crossref_metadata(doi)

        detail = {
            "doi": doi,
            "source": str(row.get("source", "")),
            "status": status,
        }

        if status == "ok":
            # Title comparison
            sim = title_similarity(our_title, cr_title)
            t_match = sim >= TITLE_MATCH_THRESHOLD
            title_checked += 1
            if t_match:
                title_matches += 1
            detail["our_title"] = our_title[:100]
            detail["cr_title"] = (cr_title or "")[:100]
            detail["title_similarity"] = round(sim, 4)
            detail["title_match"] = t_match

            # Year comparison
            if our_year is not None and cr_year is not None:
                y_match = our_year == cr_year
                y_close = abs(our_year - cr_year) <= 1
                year_checked += 1
                if y_match:
                    year_matches += 1
                if y_close:
                    year_within_one += 1
                detail["our_year"] = our_year
                detail["cr_year"] = cr_year
                detail["year_match"] = y_match
                detail["year_within_one"] = y_close

        details.append(detail)

        if (i + 1) % 20 == 0:
            log.info("  Crossref progress: %d/%d", i + 1, len(doi_sample))

    # DOI resolution check (subsample to keep total API calls reasonable)
    doi_resolve_sample = doi_sample.head(min(30, len(doi_sample)))
    log.info("Checking DOI resolution for %d DOIs...", len(doi_resolve_sample))
    for _, row in doi_resolve_sample.iterrows():
        doi = row["doi_norm"]
        resolves = check_doi_resolves(doi)
        doi_checked += 1
        if resolves:
            doi_resolves += 1

    # ── Sample 2: Works without DOIs → verify via OpenAlex title search ──────
    n_no_doi = min(args.no_doi_n, len(no_doi))
    no_doi_details = []
    no_doi_title_matches = 0
    no_doi_title_checked = 0
    no_doi_year_matches = 0
    no_doi_year_checked = 0

    if n_no_doi > 0:
        no_doi_sample = stratified_sample(no_doi, n_no_doi, args.seed)
        log.info("Sampled %d works without DOIs, searching OpenAlex...",
                 len(no_doi_sample))

        for i, (_, row) in enumerate(no_doi_sample.iterrows()):
            our_title = str(row.get("title", ""))
            our_year = row.get("year")
            if pd.notna(our_year):
                our_year = int(our_year)
            else:
                our_year = None

            oa_title, oa_year, status = search_openalex_by_title(our_title)

            detail = {
                "our_title": our_title[:100],
                "source": str(row.get("source", "")),
                "status": status,
            }

            if status == "ok" and oa_title:
                sim = title_similarity(our_title, oa_title)
                # Only count as verified if OpenAlex found a good match
                if sim >= TITLE_MATCH_THRESHOLD:
                    no_doi_title_checked += 1
                    no_doi_title_matches += 1
                    detail["oa_title"] = (oa_title or "")[:100]
                    detail["title_similarity"] = round(sim, 4)
                    detail["title_match"] = True

                    if our_year is not None and oa_year is not None:
                        y_match = our_year == oa_year
                        no_doi_year_checked += 1
                        if y_match:
                            no_doi_year_matches += 1
                        detail["our_year"] = our_year
                        detail["oa_year"] = oa_year
                        detail["year_match"] = y_match
                else:
                    detail["oa_title"] = (oa_title or "")[:100]
                    detail["title_similarity"] = round(sim, 4)
                    detail["title_match"] = False

            no_doi_details.append(detail)

            if (i + 1) % 10 == 0:
                log.info("  OpenAlex progress: %d/%d", i + 1, len(no_doi_sample))
    else:
        log.info("No works without DOIs to check")

    # ── Compute Wilson CIs ───────────────────────────────────────────────────
    title_prop, title_ci_lo, title_ci_hi = wilson_ci(title_matches, title_checked)
    year_prop, year_ci_lo, year_ci_hi = wilson_ci(year_matches, year_checked)
    yw1_prop, yw1_ci_lo, yw1_ci_hi = wilson_ci(year_within_one, year_checked)
    doi_prop, doi_ci_lo, doi_ci_hi = wilson_ci(doi_resolves, doi_checked)

    log.info("Title match: %d/%d = %.3f [%.3f, %.3f]",
             title_matches, title_checked, title_prop, title_ci_lo, title_ci_hi)
    log.info("Year exact match: %d/%d = %.3f [%.3f, %.3f]",
             year_matches, year_checked, year_prop, year_ci_lo, year_ci_hi)
    log.info("Year within 1: %d/%d = %.3f [%.3f, %.3f]",
             year_within_one, year_checked, yw1_prop, yw1_ci_lo, yw1_ci_hi)
    log.info("DOI resolves: %d/%d = %.3f [%.3f, %.3f]",
             doi_resolves, doi_checked, doi_prop, doi_ci_lo, doi_ci_hi)

    # ── Build report ─────────────────────────────────────────────────────────
    report = {
        "generated": pd.Timestamp.now().isoformat(),
        "seed": args.seed,
        "corpus_size": len(works),
        "with_doi": len(has_doi),
        "without_doi": len(no_doi),
        "title_match": {
            "sample_n": title_checked,
            "matches": title_matches,
            "proportion": round(title_prop, 6),
            "ci_lower": round(title_ci_lo, 6),
            "ci_upper": round(title_ci_hi, 6),
            "threshold": TITLE_MATCH_THRESHOLD,
        },
        "year_match": {
            "sample_n": year_checked,
            "matches": year_matches,
            "proportion": round(year_prop, 6),
            "ci_lower": round(year_ci_lo, 6),
            "ci_upper": round(year_ci_hi, 6),
        },
        "year_within_one": {
            "sample_n": year_checked,
            "matches": year_within_one,
            "proportion": round(yw1_prop, 6),
            "ci_lower": round(yw1_ci_lo, 6),
            "ci_upper": round(yw1_ci_hi, 6),
        },
        "doi_resolution": {
            "sample_n": doi_checked,
            "resolves": doi_resolves,
            "proportion": round(doi_prop, 6),
            "ci_lower": round(doi_ci_lo, 6),
            "ci_upper": round(doi_ci_hi, 6),
        },
        "no_doi_verification": {
            "sample_n": len(no_doi_details),
            "title_verified": no_doi_title_checked,
            "title_matches": no_doi_title_matches,
            "year_checked": no_doi_year_checked,
            "year_matches": no_doi_year_matches,
        },
        "details": details,
        "no_doi_details": no_doi_details,
    }

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(report, f, indent=2)
    log.info("Report saved to: %s", OUTPUT_PATH)

    # ── Summary ──────────────────────────────────────────────────────────────
    mismatches = [d for d in details if d.get("title_match") is False]
    if mismatches:
        log.info("Title mismatches (%d):", len(mismatches))
        for m in mismatches[:5]:
            log.info("  DOI: %s  sim=%.3f", m["doi"], m.get("title_similarity", 0))
            log.info("    Ours: %s", m.get("our_title", ""))
            log.info("    CR:   %s", m.get("cr_title", ""))

    year_mismatches = [d for d in details if d.get("year_match") is False]
    if year_mismatches:
        log.info("Year mismatches (%d):", len(year_mismatches))
        for m in year_mismatches[:5]:
            log.info("  DOI: %s  ours=%s cr=%s",
                     m["doi"], m.get("our_year"), m.get("cr_year"))


if __name__ == "__main__":
    main()
