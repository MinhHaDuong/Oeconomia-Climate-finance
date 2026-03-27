#!/usr/bin/env python3
"""Citation graph quality control: accuracy and completeness against Crossref.

Two statistical tests on the citation network:

Test A (accuracy): sample citation rows, verify each (source_doi, ref_doi) pair
    exists in Crossref metadata. Reports proportion confirmed with 95% Wilson CI.

Test B (completeness): sample source DOIs, re-fetch from Crossref, check all
    their ref DOIs are in our data. Reports proportion captured with 95% Wilson CI.

Saves results to content/tables/qa_citations_report.json

Usage:
    uv run python scripts/qa_citations.py [--sample-n 300] [--seed 42]
        [--works-input data/catalogs/enriched_works.csv]
"""

import argparse
import json
import os
import time

import numpy as np
import pandas as pd
import requests
from utils import CATALOGS_DIR, MAILTO, get_logger, normalize_doi

log = get_logger("qa_citations")

HEADERS = {"User-Agent": f"ClimateFinancePipeline/1.0 (mailto:{MAILTO})"}
OUTPUT_PATH = os.path.join(
    os.path.dirname(__file__), "..", "content", "tables", "qa_citations_report.json"
)
CROSSREF_DELAY = 0.15  # seconds between API calls (polite rate limiting)


def wilson_ci(successes: int, n: int, z: float = 1.96) -> tuple[float, float, float]:
    """Wilson score interval for a binomial proportion.

    Returns (proportion, ci_lower, ci_upper). Handles edge cases (n=0, p=0, p=1).
    """
    if n == 0:
        return 0.0, 0.0, 0.0
    p = successes / n
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    spread = z * (p * (1 - p) / n + z**2 / (4 * n**2)) ** 0.5 / denom
    return round(p, 6), round(max(0.0, center - spread), 6), round(min(1.0, center + spread), 6)


def fetch_crossref_refs(doi: str) -> tuple[set[str], str]:
    """Fetch reference DOIs for a source DOI from Crossref.

    Returns (set_of_normalized_ref_dois, status_string).
    """
    url = f"https://api.crossref.org/works/{doi}"
    try:
        time.sleep(CROSSREF_DELAY)
        resp = requests.get(
            url, headers=HEADERS, timeout=30, params={"mailto": MAILTO}
        )
        if resp.status_code == 404:
            return set(), "not_in_crossref"
        if resp.status_code == 429:
            # Rate limited — wait and retry once
            time.sleep(2.0)
            resp = requests.get(
                url, headers=HEADERS, timeout=30, params={"mailto": MAILTO}
            )
        if resp.status_code != 200:
            return set(), f"HTTP {resp.status_code}"
        data = resp.json()["message"]
        refs = data.get("reference", [])
        doi_refs = set()
        for r in refs:
            d = normalize_doi(r.get("DOI", ""))
            if d not in ("", "nan", "none"):
                doi_refs.add(d)
        return doi_refs, "ok"
    except requests.exceptions.Timeout:
        return set(), "timeout"
    except Exception as e:
        return set(), f"error: {e}"


def test_accuracy(cit: pd.DataFrame, sample_n: int, rng: np.random.Generator) -> dict:
    """Test A: sample citation rows, verify each link against Crossref.

    Unit of sampling is the individual (source_doi, ref_doi) link.
    """
    # Filter to rows with both DOIs present
    valid = cit[
        cit["source_doi"].notna() & (cit["source_doi"] != "")
        & (cit["source_doi"] != "nan")
        & cit["ref_doi"].notna() & (cit["ref_doi"] != "")
        & (cit["ref_doi"] != "nan")
    ].copy()

    n = min(sample_n, len(valid))
    sample_idx = rng.choice(len(valid), size=n, replace=False)
    sample = valid.iloc[sample_idx]

    log.info("Test A (accuracy): verifying %d citation links against Crossref...", n)

    confirmed = 0
    not_confirmed = 0
    errors = 0
    details = []

    # Group by source_doi to reduce API calls: fetch refs once per source
    source_groups = {}
    for _, row in sample.iterrows():
        src = row["source_doi"]
        if src not in source_groups:
            source_groups[src] = []
        source_groups[src].append(row["ref_doi"])

    log.info("  %d unique source DOIs to fetch for %d links", len(source_groups), n)

    for i, (src_doi, ref_dois) in enumerate(source_groups.items()):
        cr_refs, status = fetch_crossref_refs(src_doi)
        if i % 50 == 0 and i > 0:
            log.info("  ... fetched %d / %d source DOIs", i, len(source_groups))

        for ref_doi in ref_dois:
            if status != "ok":
                errors += 1
                details.append({
                    "source_doi": src_doi, "ref_doi": ref_doi,
                    "confirmed": None, "status": status,
                })
            elif ref_doi in cr_refs:
                confirmed += 1
                details.append({
                    "source_doi": src_doi, "ref_doi": ref_doi,
                    "confirmed": True, "status": "ok",
                })
            else:
                not_confirmed += 1
                details.append({
                    "source_doi": src_doi, "ref_doi": ref_doi,
                    "confirmed": False, "status": "ok",
                })

    # Compute proportion and CI over links with successful API calls
    n_tested = confirmed + not_confirmed
    proportion, ci_lower, ci_upper = wilson_ci(confirmed, n_tested)

    log.info("  Accuracy: %d/%d confirmed (%.1f%%), CI [%.3f, %.3f], %d errors",
             confirmed, n_tested, proportion * 100, ci_lower, ci_upper, errors)

    return {
        "test": "accuracy",
        "description": "Proportion of sampled citation links confirmed by Crossref",
        "sample_n": n,
        "tested_n": n_tested,
        "confirmed": confirmed,
        "not_confirmed": not_confirmed,
        "errors": errors,
        "proportion": proportion,
        "ci_lower": ci_lower,
        "ci_upper": ci_upper,
        "unique_sources_fetched": len(source_groups),
        "details": details,
    }


def test_completeness(
    cit: pd.DataFrame, works: pd.DataFrame, sample_n: int, rng: np.random.Generator
) -> dict:
    """Test B: sample source DOIs, re-fetch from Crossref, check ref coverage.

    For each sampled source DOI, fetch its Crossref references and check what
    proportion of Crossref ref DOIs are present in our citations.csv.
    """
    # Source DOIs that appear in our citation data
    fetched_dois = list(
        set(cit["source_doi"].dropna()) - {"", "nan", "none"}
    )

    n = min(sample_n, len(fetched_dois))
    sample_idx = rng.choice(len(fetched_dois), size=n, replace=False)
    sample_dois = [fetched_dois[i] for i in sample_idx]

    log.info("Test B (completeness): checking %d source DOIs against Crossref...", n)

    captured = 0
    missed = 0
    errors = 0
    skipped_no_refs = 0
    details = []

    for i, src_doi in enumerate(sample_dois):
        cr_refs, status = fetch_crossref_refs(src_doi)
        if i % 50 == 0 and i > 0:
            log.info("  ... fetched %d / %d DOIs", i, n)

        if status != "ok":
            errors += 1
            details.append({
                "source_doi": src_doi, "status": status,
                "cr_refs": 0, "captured": 0, "missed": 0,
            })
            continue

        if not cr_refs:
            skipped_no_refs += 1
            details.append({
                "source_doi": src_doi, "status": "ok_no_refs",
                "cr_refs": 0, "captured": 0, "missed": 0,
            })
            continue

        # Our ref DOIs for this source
        our_refs = set(
            cit[cit["source_doi"] == src_doi]["ref_doi"].dropna()
        ) - {"", "nan", "none"}

        n_captured = len(cr_refs & our_refs)
        n_missed = len(cr_refs - our_refs)
        captured += n_captured
        missed += n_missed

        details.append({
            "source_doi": src_doi, "status": "ok",
            "cr_refs": len(cr_refs), "captured": n_captured, "missed": n_missed,
        })

    # Proportion: of all Crossref ref DOIs across sampled sources, how many did we capture?
    total_cr_refs = captured + missed
    proportion, ci_lower, ci_upper = wilson_ci(captured, total_cr_refs)

    log.info("  Completeness: %d/%d Crossref refs captured (%.1f%%), CI [%.3f, %.3f], "
             "%d errors, %d sources without DOI refs",
             captured, total_cr_refs, proportion * 100, ci_lower, ci_upper,
             errors, skipped_no_refs)

    return {
        "test": "completeness",
        "description": "Proportion of Crossref reference DOIs present in our data",
        "sample_n": n,
        "sources_with_refs": n - errors - skipped_no_refs,
        "sources_no_refs": skipped_no_refs,
        "errors": errors,
        "total_cr_ref_dois": total_cr_refs,
        "captured": captured,
        "missed": missed,
        "proportion": proportion,
        "ci_lower": ci_lower,
        "ci_upper": ci_upper,
        "details": details,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Citation QA: verify accuracy and completeness against Crossref"
    )
    parser.add_argument("--sample-n", type=int, default=300,
                        help="Sample size for each test (default 300)")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for reproducibility (default 42)")
    parser.add_argument("--works-input",
                        default=os.path.join(CATALOGS_DIR, "enriched_works.csv"),
                        help="Works CSV to read DOIs from (default: enriched_works.csv)")
    args = parser.parse_args()

    rng = np.random.default_rng(args.seed)

    # ── Load data ────────────────────────────────────────────────────────────
    cit_path = os.path.join(CATALOGS_DIR, "citations.csv")
    cit = pd.read_csv(cit_path, low_memory=False)
    cit["source_doi"] = cit["source_doi"].apply(normalize_doi)
    cit["ref_doi"] = cit["ref_doi"].apply(normalize_doi)

    works = pd.read_csv(args.works_input, usecols=["doi", "source", "year"])
    works["doi_norm"] = works["doi"].apply(normalize_doi)

    # Corpus stats
    fetched_dois = set(cit["source_doi"].dropna()) - {"", "nan", "none"}
    all_dois = set(works["doi_norm"].dropna()) - {"", "nan", "none"}
    total_rows = len(cit)
    doi_ref_rows = int((
        cit["ref_doi"].notna() & (cit["ref_doi"] != "") & (cit["ref_doi"] != "nan")
    ).sum())

    log.info("Loaded: %d citation rows (%d with ref DOI), %d corpus DOIs, %d fetched",
             total_rows, doi_ref_rows, len(all_dois), len(fetched_dois))

    # ── Test A: Accuracy ─────────────────────────────────────────────────────
    accuracy = test_accuracy(cit, args.sample_n, rng)

    # ── Test B: Completeness ─────────────────────────────────────────────────
    completeness = test_completeness(cit, works, args.sample_n, rng)

    # ── Save JSON report ─────────────────────────────────────────────────────
    report = {
        "generated": pd.Timestamp.now().isoformat(),
        "seed": args.seed,
        "corpus": {
            "total_dois": len(all_dois),
            "fetched_dois": len(fetched_dois),
            "never_fetched_dois": len(all_dois - fetched_dois),
            "coverage_pct": round(len(fetched_dois) / len(all_dois) * 100, 1),
            "total_citation_rows": int(total_rows),
            "doi_ref_rows": doi_ref_rows,
        },
        "accuracy": accuracy,
        "completeness": completeness,
    }

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(report, f, indent=2)
    log.info("Report saved to: %s", OUTPUT_PATH)


if __name__ == "__main__":
    main()
