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
import re
import sys
import time

import numpy as np
import pandas as pd
import requests
from scipy.stats import binomtest
from utils import CATALOGS_DIR, MAILTO, get_logger, normalize_doi

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


def _parse_year(value):
    """Convert a possibly-NaN year to int or None."""
    if pd.notna(value):
        return int(value)
    return None


def _compare_one_work(row, cr_title, cr_year, status):
    """Compare one work's metadata against Crossref; return detail dict and tallies.

    Returns (detail_dict, title_ok, year_ok, year_close) where the booleans
    are None when the comparison could not be made.
    """
    our_title = str(row.get("title", ""))
    our_year = _parse_year(row.get("year"))
    detail = {
        "doi": row["doi_norm"],
        "source": str(row.get("source", "")),
        "status": status,
    }
    title_ok = year_ok = year_close = None

    if status != "ok":
        return detail, title_ok, year_ok, year_close

    sim = title_similarity(our_title, cr_title)
    title_ok = sim >= TITLE_MATCH_THRESHOLD
    detail.update({
        "our_title": our_title[:100],
        "cr_title": (cr_title or "")[:100],
        "title_similarity": round(sim, 4),
        "title_match": title_ok,
    })

    if our_year is not None and cr_year is not None:
        year_ok = our_year == cr_year
        year_close = abs(our_year - cr_year) <= 1
        detail.update({
            "our_year": our_year,
            "cr_year": cr_year,
            "year_match": year_ok,
            "year_within_one": year_close,
        })

    return detail, title_ok, year_ok, year_close


def verify_doi_works(doi_sample):
    """Verify a sample of DOI-bearing works against Crossref.

    Returns (details, counters_dict).
    """
    title_matches = title_checked = 0
    year_matches = year_within_one = year_checked = 0
    details = []

    for i, (_, row) in enumerate(doi_sample.iterrows()):
        cr_title, cr_year, status = fetch_crossref_metadata(row["doi_norm"])
        detail, title_ok, year_ok, year_close = _compare_one_work(
            row, cr_title, cr_year, status
        )
        details.append(detail)

        if title_ok is not None:
            title_checked += 1
            title_matches += int(title_ok)
        if year_ok is not None:
            year_checked += 1
            year_matches += int(year_ok)
            year_within_one += int(year_close)

        if (i + 1) % 20 == 0:
            log.info("  Crossref progress: %d/%d", i + 1, len(doi_sample))

    # DOI resolution check (subsample to keep total API calls reasonable)
    doi_resolves = doi_checked_resolve = 0
    resolve_sample = doi_sample.head(min(30, len(doi_sample)))
    log.info("Checking DOI resolution for %d DOIs...", len(resolve_sample))
    for _, row in resolve_sample.iterrows():
        doi_checked_resolve += 1
        if check_doi_resolves(row["doi_norm"]):
            doi_resolves += 1

    counters = {
        "title_matches": title_matches, "title_checked": title_checked,
        "year_matches": year_matches, "year_within_one": year_within_one,
        "year_checked": year_checked,
        "doi_resolves": doi_resolves, "doi_checked": doi_checked_resolve,
    }
    return details, counters


def verify_no_doi_works(no_doi_sample):
    """Verify a sample of works without DOIs via OpenAlex title search.

    Returns (details, counters_dict).
    """
    details = []
    title_matches = title_checked = 0
    year_matches = year_checked = 0

    for i, (_, row) in enumerate(no_doi_sample.iterrows()):
        our_title = str(row.get("title", ""))
        our_year = _parse_year(row.get("year"))

        oa_title, oa_year, status = search_openalex_by_title(our_title)
        detail = {
            "our_title": our_title[:100],
            "source": str(row.get("source", "")),
            "status": status,
        }

        if status == "ok" and oa_title:
            sim = title_similarity(our_title, oa_title)
            detail["oa_title"] = (oa_title or "")[:100]
            detail["title_similarity"] = round(sim, 4)
            detail["title_match"] = sim >= TITLE_MATCH_THRESHOLD

            if sim >= TITLE_MATCH_THRESHOLD:
                title_checked += 1
                title_matches += 1
                if our_year is not None and oa_year is not None:
                    year_checked += 1
                    year_matches += int(our_year == oa_year)
                    detail["our_year"] = our_year
                    detail["oa_year"] = oa_year
                    detail["year_match"] = our_year == oa_year

        details.append(detail)
        if (i + 1) % 10 == 0:
            log.info("  OpenAlex progress: %d/%d", i + 1, len(no_doi_sample))

    counters = {
        "title_verified": title_checked, "title_matches": title_matches,
        "year_checked": year_checked, "year_matches": year_matches,
    }
    return details, counters


def build_report(args, works, has_doi, no_doi, doi_counters, doi_details,
                 no_doi_counters, no_doi_details):
    """Assemble the JSON report from verification results."""
    c = doi_counters
    title_ci = wilson_ci(c["title_matches"], c["title_checked"])
    year_ci = wilson_ci(c["year_matches"], c["year_checked"])
    yw1_ci = wilson_ci(c["year_within_one"], c["year_checked"])
    doi_ci = wilson_ci(c["doi_resolves"], c["doi_checked"])

    for label, vals in [("Title match", title_ci), ("Year exact", year_ci),
                        ("Year within 1", yw1_ci), ("DOI resolves", doi_ci)]:
        log.info("%s: %.3f [%.3f, %.3f]", label, *vals)

    return {
        "generated": pd.Timestamp.now().isoformat(),
        "seed": args.seed,
        "corpus_size": len(works),
        "with_doi": len(has_doi),
        "without_doi": len(no_doi),
        "title_match": {
            "sample_n": c["title_checked"], "matches": c["title_matches"],
            "proportion": round(title_ci[0], 6),
            "ci_lower": round(title_ci[1], 6), "ci_upper": round(title_ci[2], 6),
            "threshold": TITLE_MATCH_THRESHOLD,
        },
        "year_match": {
            "sample_n": c["year_checked"], "matches": c["year_matches"],
            "proportion": round(year_ci[0], 6),
            "ci_lower": round(year_ci[1], 6), "ci_upper": round(year_ci[2], 6),
        },
        "year_within_one": {
            "sample_n": c["year_checked"], "matches": c["year_within_one"],
            "proportion": round(yw1_ci[0], 6),
            "ci_lower": round(yw1_ci[1], 6), "ci_upper": round(yw1_ci[2], 6),
        },
        "doi_resolution": {
            "sample_n": c["doi_checked"], "resolves": c["doi_resolves"],
            "proportion": round(doi_ci[0], 6),
            "ci_lower": round(doi_ci[1], 6), "ci_upper": round(doi_ci[2], 6),
        },
        "no_doi_verification": {
            "sample_n": len(no_doi_details), **no_doi_counters,
        },
        "details": doi_details,
        "no_doi_details": no_doi_details,
    }


def log_mismatches(details):
    """Log title and year mismatches for human review."""
    title_mm = [d for d in details if d.get("title_match") is False]
    if title_mm:
        log.info("Title mismatches (%d):", len(title_mm))
        for m in title_mm[:5]:
            log.info("  DOI: %s  sim=%.3f", m["doi"], m.get("title_similarity", 0))
            log.info("    Ours: %s", m.get("our_title", ""))
            log.info("    CR:   %s", m.get("cr_title", ""))

    year_mm = [d for d in details if d.get("year_match") is False]
    if year_mm:
        log.info("Year mismatches (%d):", len(year_mm))
        for m in year_mm[:5]:
            log.info("  DOI: %s  ours=%s cr=%s",
                     m["doi"], m.get("our_year"), m.get("cr_year"))


def _valid_doi(s):
    """Return True if s is a non-empty, non-sentinel DOI string."""
    return pd.notna(s) and s not in ("", "nan", "none")


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

    # ── Load data ─────────────────────────────────────────────────────────────
    if not os.path.isfile(args.works_input):
        log.error("Works file not found: %s", args.works_input)
        sys.exit(1)

    works = pd.read_csv(args.works_input, low_memory=False)
    works["doi_norm"] = works["doi"].apply(normalize_doi)
    log.info("Loaded %d works from %s", len(works), args.works_input)

    has_doi = works[works["doi_norm"].apply(_valid_doi)].copy()
    no_doi = works[~works["doi_norm"].apply(_valid_doi)].copy()
    log.info("Works with DOI: %d, without DOI: %d", len(has_doi), len(no_doi))

    # ── Verify works with DOIs against Crossref ──────────────────────────────
    doi_sample = stratified_sample(has_doi, min(args.sample_n, len(has_doi)),
                                   args.seed)
    log.info("Sampled %d works with DOIs, querying Crossref...", len(doi_sample))
    doi_details, doi_counters = verify_doi_works(doi_sample)

    # ── Verify works without DOIs via OpenAlex ───────────────────────────────
    n_no_doi = min(args.no_doi_n, len(no_doi))
    if n_no_doi > 0:
        no_doi_sample = stratified_sample(no_doi, n_no_doi, args.seed)
        log.info("Sampled %d works without DOIs, searching OpenAlex...",
                 len(no_doi_sample))
        no_doi_details, no_doi_counters = verify_no_doi_works(no_doi_sample)
    else:
        log.info("No works without DOIs to check")
        no_doi_details, no_doi_counters = [], {}

    # ── Build and save report ─────────────────────────────────────────────────
    report = build_report(args, works, has_doi, no_doi,
                          doi_counters, doi_details,
                          no_doi_counters, no_doi_details)

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(report, f, indent=2)
    log.info("Report saved to: %s", OUTPUT_PATH)

    log_mismatches(doi_details)


if __name__ == "__main__":
    main()
