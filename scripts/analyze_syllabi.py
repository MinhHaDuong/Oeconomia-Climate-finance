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

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from utils import BASE_DIR, DATA_DIR

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
    print(f"Loaded {len(df)} readings from {INPUT_CSV}")

    table = build_breakdown(df)

    os.makedirs(os.path.dirname(OUTPUT_TABLE), exist_ok=True)
    table.to_csv(OUTPUT_TABLE, index=False)
    print(f"\nWrote {OUTPUT_TABLE}")

    # Print summary
    n_courses = df["courses"].str.split(";").apply(
        lambda x: len([c for c in x if c.strip()]) if isinstance(x, list) else 0
    )
    print(f"\n{'='*65}")
    print(f"SYLLABI READING LIST ANALYSIS")
    print(f"{'='*65}")
    print(f"  Total unique readings: {len(df)}")
    print(f"  With DOI: {df['doi'].notna().sum()}")
    print(f"  Without DOI: {df['doi'].isna().sum()}")
    print(f"  In corpus: {(df['in_corpus'] == True).sum()}")
    print(f"\nBreakdown table:")
    print(table.to_string(index=False))

    # Selection summary
    has_doi = df["doi"].notna()
    n2 = df["n_courses"] >= 2
    selected = has_doi & n2
    print(f"\nSelection (DOI + n_courses≥2): {selected.sum()} readings")


if __name__ == "__main__":
    main()
