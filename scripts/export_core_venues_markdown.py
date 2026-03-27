#!/usr/bin/env python3
"""Export manuscript-ready venue table for core publication venues.

Produces a Quarto-includable markdown table grouping venues by publisher
where institutional series overlap, matching the manuscript's @tbl-venues.

Reads:
- $DATA/catalogs/het_mostcited_50.csv

Writes:
- content/tables/tab_core_venues_top10.md

Usage:
    uv run python scripts/export_core_venues_markdown.py
"""

import argparse
import os

import pandas as pd
from summarize_core_venues import canonical_venue, venue_type
from utils import BASE_DIR, CATALOGS_DIR, get_logger

log = get_logger("export_core_venues_markdown")

TABLES_DIR = os.path.join(BASE_DIR, "content", "tables")

# Institutional publisher groups: label → list of canonical venue prefixes
PUBLISHER_GROUPS = [
    ("World Bank reports and working papers", ["World Bank"], "Institutional"),
    ("OECD publications (incl. IEA Expert Group)", ["OECD"], "Institutional"),
    ("IMF working papers", ["IMF"], "Institutional"),
    ("UNFCCC/climate fund reports", ["Climate finance and the USD 100 billion goal"], "Institutional"),
]

# Top journals to include (by paper count, after institutional groups)
N_TOP_JOURNALS = 3


def parse_args():
    parser = argparse.ArgumentParser(description="Export top core venues as markdown table")
    parser.add_argument(
        "--core",
        type=str,
        default=os.path.join(CATALOGS_DIR, "het_mostcited_50.csv"),
        help="Input core works CSV",
    )
    parser.add_argument(
        "--out",
        type=str,
        default=os.path.join(TABLES_DIR, "tab_core_venues_top10.md"),
        help="Output markdown file (Quarto-includable)",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    if not os.path.exists(args.core):
        raise FileNotFoundError(f"Core file not found: {args.core}")

    df = pd.read_csv(args.core)
    if "journal" not in df.columns:
        raise ValueError("Expected column 'journal' in core file")

    df = df.copy()
    df["venue_raw"] = df["journal"].fillna("").astype(str).str.strip()
    df["venue_raw"] = df["venue_raw"].mask(df["venue_raw"].eq(""), "[missing]")
    df["venue_canonical"] = df["venue_raw"].map(canonical_venue)
    df["venue_type"] = df["venue_canonical"].map(venue_type)

    n_core = len(df)

    # Build grouped rows: institutional publishers
    table_rows = []
    used_indices = set()
    for label, prefixes, vtype in PUBLISHER_GROUPS:
        lower_prefixes = [p.lower() for p in prefixes]
        mask = df["venue_canonical"].str.lower().apply(
            lambda v, _pfx=lower_prefixes: any(v.startswith(p) for p in _pfx)
        )
        count = mask.sum()
        if count > 0:
            table_rows.append((label, count, vtype))
            used_indices.update(df[mask].index)

    # Top journals (not already consumed by institutional groups)
    remaining = df.drop(index=used_indices)
    journals = remaining[remaining["venue_type"] == "journal"]
    top_journals = (
        journals.groupby("venue_canonical")
        .size()
        .sort_values(ascending=False)
        .head(N_TOP_JOURNALS)
    )
    for venue, count in top_journals.items():
        table_rows.append((venue, count, "Journal"))

    # Sort: institutional first (descending), then journals (descending)
    inst_rows = [(v, n, t) for v, n, t in table_rows if t == "Institutional"]
    jour_rows = [(v, n, t) for v, n, t in table_rows if t == "Journal"]
    inst_rows.sort(key=lambda x: -x[1])
    jour_rows.sort(key=lambda x: -x[1])
    table_rows = inst_rows + jour_rows

    # Render Quarto-compatible markdown
    lines = [
        "| Venue | Papers | Type |",
        "|:------|-------:|:-----|",
    ]
    for venue, count, vtype in table_rows:
        lines.append(f"| {venue} | {count} | {vtype} |")

    lines.append("")
    lines.append(
        f": Top publication venues in the core subset (works cited 50 times or more), "
        f"by number of papers. Authors' analysis of the corpus "
        f"(core subset, N = {n_core:,}). "
        f"Venues grouped by publisher where institutional series overlap. "
        f"Repositories (SSRN, RePEc) excluded as they duplicate content "
        f"published elsewhere. {{#tbl-venues}}"
    )

    content = "\n".join(lines) + "\n"

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as handle:
        handle.write(content)

    log.info("Saved manuscript table: %s", args.out)
    for venue, count, vtype in table_rows:
        log.info("  %s: %d (%s)", venue, count, vtype)


if __name__ == "__main__":
    main()
