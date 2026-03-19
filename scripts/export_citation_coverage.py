"""Export citation coverage table by period for Quarto includes.

Produces:
- content/tables/tab_citation_coverage.md: period coverage + core coverage

Reads: refined_works.csv, citations.csv

Usage:
    uv run python scripts/export_citation_coverage.py
"""

import argparse
import os

import pandas as pd

from utils import CATALOGS_DIR, BASE_DIR, get_logger, normalize_doi, load_analysis_periods

log = get_logger("export_citation_coverage")

REFINED_PATH = os.path.join(CATALOGS_DIR, "refined_works.csv")
CITATIONS_PATH = os.path.join(CATALOGS_DIR, "citations.csv")
OUTPUT_PATH = os.path.join(BASE_DIR, "content", "tables", "tab_citation_coverage.md")

CORE_THRESHOLD = 50
_period_tuples, _period_labels = load_analysis_periods()
PERIODS = [(label, start, end) for label, (start, end) in zip(_period_labels, _period_tuples)]


def main():
    refined = pd.read_csv(REFINED_PATH, low_memory=False)
    citations = pd.read_csv(CITATIONS_PATH, usecols=["source_doi"], low_memory=False)

    # Normalize DOIs for matching
    refined["doi_norm"] = refined["doi"].apply(
        lambda x: normalize_doi(x) if pd.notna(x) else ""
    )
    fetched_dois = set(citations["source_doi"].dropna().apply(normalize_doi).unique())

    refined["has_citations"] = refined["doi_norm"].isin(fetched_dois)

    # Period table
    lines = [
        "| Period | Total works | With citation data | Coverage |",
        "|--------|------------:|-------------------:|---------:|",
    ]
    for label, lo, hi in PERIODS:
        mask = (refined["year"] >= lo) & (refined["year"] <= hi)
        period = refined[mask]
        total = len(period)
        with_data = period["has_citations"].sum()
        pct = 100 * with_data / total if total > 0 else 0
        lines.append(f"| {label} | {total:,} | {with_data:,} | {pct:.0f}% |")

    # Core coverage
    core = refined[refined["cited_by_count"] >= CORE_THRESHOLD]
    core_total = len(core)
    core_with = core["has_citations"].sum()
    core_pct = 100 * core_with / core_total if core_total > 0 else 0

    lines.append("")
    lines.append(
        f"Coverage is significantly higher for the most-cited works "
        f"(core papers with $\\geq {CORE_THRESHOLD}$ incoming citations): "
        f"{core_with:,} of {core_total:,} ({core_pct:.0f}%) have reference data."
    )

    content = "\n".join(lines) + "\n"

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        f.write(content)

    log.info("Wrote %s", OUTPUT_PATH)
    log.info("\n%s", content)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    main()
