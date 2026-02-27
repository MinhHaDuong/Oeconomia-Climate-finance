#!/usr/bin/env python3
"""Export manuscript-ready markdown tables for core publication venues.

Reads:
- $DATA/catalogs/het_core.csv

Writes:
- tables/tab_core_venues_top10.md

Usage:
    uv run python scripts/export_core_venues_markdown.py
"""

import argparse
import os
import sys
from datetime import date

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from summarize_core_venues import canonical_venue, venue_type
from utils import BASE_DIR, CATALOGS_DIR


def parse_args():
    parser = argparse.ArgumentParser(description="Export top core venues as markdown tables")
    parser.add_argument(
        "--core",
        type=str,
        default=os.path.join(CATALOGS_DIR, "het_core.csv"),
        help="Input core works CSV",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=10,
        help="Top N venues per table",
    )
    parser.add_argument(
        "--out",
        type=str,
        default=os.path.join(BASE_DIR, "tables", "tab_core_venues_top10.md"),
        help="Output markdown file",
    )
    return parser.parse_args()


def summarize(df, types, top_n):
    subset = df[df["venue_type"].isin(types)].copy()
    out = (
        subset.groupby("venue_canonical", as_index=False)
        .agg(n_core_works=("venue_raw", "size"), cited_by_sum=("cited_by_count", "sum"))
        .sort_values(["n_core_works", "cited_by_sum"], ascending=[False, False])
        .head(top_n)
        .reset_index(drop=True)
    )
    return out


def summarize_institutions(df):
    out = (
        df.groupby("institution_group", as_index=False)
        .agg(n_core_works=("venue_raw", "size"), cited_by_sum=("cited_by_count", "sum"))
        .sort_values(["n_core_works", "cited_by_sum"], ascending=[False, False])
        .reset_index(drop=True)
    )
    return out


def to_markdown_table(df, label_col="venue_canonical", label_name="Venue"):
    if df.empty:
        return f"| {label_name} | Core works | Citation sum |\n|---|---:|---:|\n"

    rows = [f"| {label_name} | Core works | Citation sum |", "|---|---:|---:|"]
    for _, row in df.iterrows():
        label = str(row[label_col]).replace("|", "\\|")
        rows.append(f"| {label} | {int(row['n_core_works'])} | {int(row['cited_by_sum'])} |")
    return "\n".join(rows) + "\n"


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
    df["cited_by_count"] = pd.to_numeric(df.get("cited_by_count", 0), errors="coerce").fillna(0).astype(int)
    low = df["venue_canonical"].str.lower()
    df["institution_group"] = "Other/None"
    df.loc[low.str.contains("oecd", na=False), "institution_group"] = "OECD"
    df.loc[low.str.contains("world bank", na=False), "institution_group"] = "World Bank"
    df.loc[low.str.contains("imf", na=False), "institution_group"] = "IMF"

    journals = summarize(df, ["journal"], args.top)
    series = summarize(df, ["working_paper_series", "report_series"], args.top)
    institutions = summarize_institutions(df)

    header = [
        "# Core Venues (Top Lists)",
        "",
        f"Generated: {date.today().isoformat()}",
        "Source: catalogs/het_core.csv (resolved via CLIMATE_FINANCE_DATA)",
        "",
        "## Top Journals (by number of core works)",
        "",
        to_markdown_table(journals, label_col="venue_canonical", label_name="Venue"),
        "## Top Report/Working-Paper Series (by number of core works)",
        "",
        to_markdown_table(series, label_col="venue_canonical", label_name="Venue"),
        "## Institutional Presence in Core (OECD / World Bank / IMF)",
        "",
        to_markdown_table(institutions, label_col="institution_group", label_name="Institution"),
    ]
    content = "\n".join(header)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as handle:
        handle.write(content)

    print(f"Saved markdown table: {args.out}")
    print(f"  Journals rows: {len(journals)}")
    print(f"  Series rows: {len(series)}")


if __name__ == "__main__":
    main()
