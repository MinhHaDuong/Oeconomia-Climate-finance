#!/usr/bin/env python3
"""Identify works taught at multiple institutions for the technical report.

Reads:
  data/syllabi/reading_lists.csv     — scraped syllabi
  data/syllabi/manual_catalog.yaml   — manually cataloged syllabi
  data/catalogs/unified_works.csv    — corpus

Writes:
  content/tables/tab_teaching_canon.csv

Lists works from the corpus that appear on syllabi at 3+ distinct
institutions, combining both collection sources. This documents the
absence of a clear teaching canon: only a handful of works converge
across institutions.

Usage:
    python scripts/analyze_teaching_canon.py
"""

import os
from collections import defaultdict

import pandas as pd
import yaml

from utils import BASE_DIR, DATA_DIR, get_logger

log = get_logger("analyze_teaching_canon")

INPUT_CSV = os.path.join(DATA_DIR, "syllabi", "reading_lists.csv")
INPUT_MANUAL = os.path.join(DATA_DIR, "syllabi", "manual_catalog.yaml")
DEFAULT_UNIFIED = os.path.join(DATA_DIR, "catalogs", "unified_works.csv")
OUTPUT_TABLE = os.path.join(BASE_DIR, "content", "tables", "tab_teaching_canon.csv")

MIN_INSTITUTIONS = 3

# Normalize variant names to a single institution
INST_NORMALIZE = {
    "Harvard FECS": "Harvard",
    "Harvard University": "Harvard",
    "FINANCIAL ECONOMICS OF CLIMATE AND SUSTAINABILITY": "Harvard",
}


def _norm_inst(name):
    """Normalize institution name, return None for empty/nan."""
    name = name.strip()
    if not name or name == "nan":
        return None
    return INST_NORMALIZE.get(name, name)


def collect_institutions():
    """Count distinct institutions per work across both sources."""
    work_insts = defaultdict(set)  # dedup_key → set of institution names

    # Source 1: manual catalog
    if os.path.exists(INPUT_MANUAL):
        with open(INPUT_MANUAL, encoding="utf-8") as f:
            sources = yaml.safe_load(f)
        for src in sources:
            inst = _norm_inst(src["institution"])
            if not inst:
                continue
            for r in src.get("readings", []):
                doi = (r.get("doi") or "").lower().strip()
                title = (r.get("title") or "").lower().strip()
                key = doi if doi else title
                if key:
                    work_insts[key].add(inst)

    # Source 2: scraped CSV
    if os.path.exists(INPUT_CSV):
        df = pd.read_csv(INPUT_CSV)
        for _, row in df.iterrows():
            doi = str(row["doi"]).lower().strip() if pd.notna(row["doi"]) else ""
            title = str(row["title"]).lower().strip() if pd.notna(row["title"]) else ""
            key = doi if doi else title
            if not key:
                continue
            for i in str(row.get("institutions", "")).split(";"):
                inst = _norm_inst(i)
                if inst:
                    work_insts[key].add(inst)

    return work_insts


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--works-input", default=DEFAULT_UNIFIED,
                        help="Path to unified_works.csv")
    args = parser.parse_args()

    work_insts = collect_institutions()

    # Load corpus for matching and metadata
    uw = pd.read_csv(args.works_input)
    uw_dois = set(uw["doi"].fillna("").str.lower().str.strip()) - {""}
    uw_titles = set(uw["title"].fillna("").str.lower().str.strip()) - {""}

    rows = []
    for key, insts in work_insts.items():
        if len(insts) < MIN_INSTITUTIONS:
            continue
        if key not in uw_dois and key not in uw_titles:
            continue

        # Get metadata from corpus
        match = uw[uw["doi"].fillna("").str.lower().str.strip() == key]
        if match.empty:
            match = uw[uw["title"].fillna("").str.lower().str.strip() == key]
        r = match.iloc[0]

        rows.append({
            "first_author": r["first_author"] if pd.notna(r.get("first_author")) else "",
            "year": int(r["year"]) if pd.notna(r.get("year")) else "",
            "title": r["title"] if pd.notna(r["title"]) else key,
            "doi": r["doi"] if pd.notna(r["doi"]) else "",
            "n_institutions": len(insts),
            "institutions": ", ".join(sorted(insts)),
        })

    rows.sort(key=lambda x: (-x["n_institutions"], x["first_author"]))
    table = pd.DataFrame(rows)

    os.makedirs(os.path.dirname(OUTPUT_TABLE), exist_ok=True)
    table.to_csv(OUTPUT_TABLE, index=False)

    log.info("Works in corpus taught at %d+ institutions: %d", MIN_INSTITUTIONS, len(table))
    log.info("Wrote %s", OUTPUT_TABLE)
    for _, r in table.iterrows():
        auth = r["first_author"].split(",")[0].split()[-1] if r["first_author"] else "?"
        log.info("  %d  %s (%s) %s", r['n_institutions'], auth, r['year'], r['title'][:65])


if __name__ == "__main__":
    main()
