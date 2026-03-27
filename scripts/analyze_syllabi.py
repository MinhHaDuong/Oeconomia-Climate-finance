#!/usr/bin/env python3
"""Analyze syllabi reading lists for the technical report.

Reads:  data/syllabi/reading_lists.csv
Writes: content/tables/tab_syllabi_breakdown.csv

Produces a breakdown table of reading list entries by type (article, book,
chapter, report, other, course) × DOI presence × n_courses thresholds.
This table documents the coverage and convergence of the scraped syllabi,
supporting the choice of selection criteria for the teaching source pipeline.

Usage:
    python scripts/analyze_syllabi.py
"""

import argparse
import os

import pandas as pd
from build_teaching_yaml import _dedup_course_names
from utils import BASE_DIR, DATA_DIR, get_logger

log = get_logger("analyze_syllabi")

INPUT_CSV = os.path.join(DATA_DIR, "syllabi", "reading_lists.csv")
OUTPUT_TABLE = os.path.join(BASE_DIR, "content", "tables", "tab_syllabi_breakdown.csv")


def build_breakdown(df):
    """Build breakdown table: type × DOI × n_courses thresholds."""
    df = df.copy()
    df["has_doi"] = df["doi"].notna()

    rows = []
    types = ["article", "book", "chapter", "report", "other", "course"]
    for typ in types:
        for has_doi, doi_label in [(True, "with DOI"), (False, "no DOI")]:
            sub = df[(df["type"] == typ) & (df["has_doi"] == has_doi)]
            if len(sub) == 0:
                continue
            rows.append({
                "type": typ,
                "DOI": doi_label,
                "total": len(sub),
                "n≥2": int((sub["n_courses"] >= 2).sum()),
                "n≥3": int((sub["n_courses"] >= 3).sum()),
                "n≥4": int((sub["n_courses"] >= 4).sum()),
            })

    # Totals
    for has_doi, doi_label in [(True, "with DOI"), (False, "no DOI")]:
        sub = df[df["has_doi"] == has_doi]
        rows.append({
            "type": "TOTAL",
            "DOI": doi_label,
            "total": len(sub),
            "n≥2": int((sub["n_courses"] >= 2).sum()),
            "n≥3": int((sub["n_courses"] >= 3).sum()),
            "n≥4": int((sub["n_courses"] >= 4).sum()),
        })

    return pd.DataFrame(rows)


def main():
    df = pd.read_csv(INPUT_CSV)
    log.info("Loaded %d readings from %s", len(df), INPUT_CSV)

    # Apply course dedup before counting (same logic as build_teaching_yaml.py)
    df = _dedup_course_names(df)

    table = build_breakdown(df)

    os.makedirs(os.path.dirname(OUTPUT_TABLE), exist_ok=True)
    table.to_csv(OUTPUT_TABLE, index=False)
    log.info("Wrote %s", OUTPUT_TABLE)

    # Print summary
    log.info("=" * 65)
    log.info("SYLLABI READING LIST ANALYSIS")
    log.info("=" * 65)
    log.info("  Total unique readings: %d", len(df))
    log.info("  With DOI: %d", df['doi'].notna().sum())
    log.info("  Without DOI: %d", df['doi'].isna().sum())
    log.info("  In corpus: %d", (df['in_corpus'] == True).sum())
    log.info("Breakdown table:\n%s", table.to_string(index=False))

    # Selection summary
    has_doi = df["doi"].notna()
    n2 = df["n_courses"] >= 2
    selected = has_doi & n2
    log.info("Selection (DOI + n_courses>=2): %d readings", selected.sum())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    main()
