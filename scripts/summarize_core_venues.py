#!/usr/bin/env python3
"""Summarize publication venues for core works.

Reads:
- $DATA/catalogs/het_mostcited_50.csv

Writes:
- tables/tab_core_venues_journals.csv
- tables/tab_core_venues_series.csv
- tables/tab_core_venues_all.csv

Usage:
    uv run python scripts/summarize_core_venues.py
"""

import argparse
import os
import re

import pandas as pd
from utils import BASE_DIR, CATALOGS_DIR, get_logger, save_csv

log = get_logger("summarize_core_venues")


def parse_args():
    parser = argparse.ArgumentParser(description="Summarize core venue distributions")
    parser.add_argument(
        "--core",
        type=str,
        default=os.path.join(CATALOGS_DIR, "het_mostcited_50.csv"),
        help="Input core works CSV",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=30,
        help="Top N venues per output table",
    )
    parser.add_argument(
        "--out-all",
        type=str,
        default=os.path.join(BASE_DIR, "content", "tables", "tab_core_venues_all.csv"),
        help="Output path for all venues summary",
    )
    parser.add_argument(
        "--out-journals",
        type=str,
        default=os.path.join(BASE_DIR, "content", "tables", "tab_core_venues_journals.csv"),
        help="Output path for journal-only summary",
    )
    parser.add_argument(
        "--out-series",
        type=str,
        default=os.path.join(BASE_DIR, "content", "tables", "tab_core_venues_series.csv"),
        help="Output path for report/WP series summary",
    )
    parser.add_argument(
        "--out-institutions",
        type=str,
        default=os.path.join(BASE_DIR, "content", "tables", "tab_core_institutions.csv"),
        help="Output path for institution summary (OECD/WB/IMF/other)",
    )
    parser.add_argument(
        "--out-institution-types",
        type=str,
        default=os.path.join(BASE_DIR, "content", "tables", "tab_core_institution_by_type.csv"),
        help="Output path for institution x venue_type summary",
    )
    return parser.parse_args()


# Each entry is (matcher, canonical_name).
# matcher is either a substring str or a callable(low: str) -> bool.
# More specific patterns must precede more general ones within the same family.
_VENUE_RULES: list[tuple] = [
    # Exact-match edge case
    (lambda s: s == "mf policy paper", "IMF Policy Paper"),
    # World Bank — most specific first
    (lambda s: "world bank" in s and ("ebook" in s or "publication" in s or "washington, dc" in s),
     "World Bank eBooks"),
    ("world bank policy research working paper", "World Bank Policy Research Working Paper"),
    ("world bank", "World Bank"),
    # OECD — most specific first
    ("oecd/iea climate change expert group papers", "OECD/IEA Climate Change Expert Group Papers"),
    (lambda s: "oecd" in s and "working paper" in s, "OECD Working Papers"),
    (lambda s: "oecd" in s and "paper" in s, "OECD Papers"),
    (lambda s: s.startswith("oecd"), "OECD"),
    # IMF — most specific first
    ("imf working paper", "IMF Working Paper"),
    ("imf staff climate notes", "IMF Staff Climate Notes"),
    ("imf staff country reports", "IMF Staff Country Reports"),
    (lambda s: "imf" in s and ("discussion note" in s or "staff" in s), "IMF Staff Notes"),
    ("imf", "IMF"),
    # Repositories and indexes
    ("ssrn", "SSRN Electronic Journal"),
    ("repec", "RePEc"),
    ("depositonce", "DepositOnce"),
    ("zenodo", "Zenodo"),
    ("figshare", "Figshare"),
    ("preprints", "Preprints"),
]


def canonical_venue(name):
    v = str(name or "").strip()
    low = v.lower()
    if not low:
        return "[missing]"
    for matcher, canonical in _VENUE_RULES:
        matched = matcher(low) if callable(matcher) else (matcher in low)
        if matched:
            return canonical
    return v


def venue_type(name):
    low = str(name or "").lower()
    if not low or low == "[missing]":
        return "missing"

    if low == "climate finance and the usd 100 billion goal":
        return "report_series"

    wp_pattern = re.compile(r"working paper|working papers|discussion paper|policy research working paper|\bwp\b")
    report_pattern = re.compile(
        r"ebook|ebooks|report|reports|publications|world bank|oecd|imf|unfccc|climate policy initiative|\bcpi\b"
    )
    non_journal_pattern = re.compile(
        r"ssrn|repec|zenodo|figshare|preprints|open science framework|depositonce|research online"
    )

    if wp_pattern.search(low):
        return "working_paper_series"
    if report_pattern.search(low):
        return "report_series"
    if non_journal_pattern.search(low):
        return "repository_or_index"
    return "journal"


def institution_group(name):
    low = str(name or "").lower()
    if "oecd" in low:
        return "OECD"
    if "world bank" in low:
        return "World Bank"
    if "imf" in low:
        return "IMF"
    return "Other/None"


def summarize(df, group_cols, top_n):
    out = (
        df.groupby(group_cols, as_index=False)
        .agg(n_core_works=("venue_raw", "size"), cited_by_sum=("cited_by_count", "sum"))
        .sort_values(["n_core_works", "cited_by_sum"], ascending=[False, False])
        .head(top_n)
        .reset_index(drop=True)
    )
    return out


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

    all_tbl = summarize(df, ["venue_type", "venue_canonical"], args.top)
    journals_tbl = summarize(df[df["venue_type"] == "journal"], ["venue_canonical"], args.top)
    series_tbl = summarize(
        df[df["venue_type"].isin(["working_paper_series", "report_series"])],
        ["venue_type", "venue_canonical"],
        args.top,
    )
    df["institution_group"] = df["venue_canonical"].map(institution_group)
    inst_tbl = (
        df.groupby("institution_group", as_index=False)
        .agg(n_core_works=("venue_raw", "size"), cited_by_sum=("cited_by_count", "sum"))
        .sort_values(["n_core_works", "cited_by_sum"], ascending=[False, False])
        .reset_index(drop=True)
    )
    inst_type_tbl = (
        df.groupby(["institution_group", "venue_type"], as_index=False)
        .agg(n_core_works=("venue_raw", "size"), cited_by_sum=("cited_by_count", "sum"))
        .sort_values(["institution_group", "n_core_works"], ascending=[True, False])
        .reset_index(drop=True)
    )

    save_csv(all_tbl, args.out_all)
    save_csv(journals_tbl, args.out_journals)
    save_csv(series_tbl, args.out_series)
    save_csv(inst_tbl, args.out_institutions)
    save_csv(inst_type_tbl, args.out_institution_types)

    coverage = (
        df.groupby("venue_type", as_index=False)
        .agg(n_core_works=("venue_raw", "size"))
        .sort_values("n_core_works", ascending=False)
    )

    log.info("Done.")
    log.info("  Input rows: %s", f"{len(df):,}")
    log.info("  Venue type coverage:")
    for _, row in coverage.iterrows():
        log.info("    - %s: %d", row['venue_type'], int(row['n_core_works']))
    log.info("  Institution coverage:")
    for _, row in inst_tbl.iterrows():
        log.info("    - %s: %d", row['institution_group'], int(row['n_core_works']))


if __name__ == "__main__":
    main()
