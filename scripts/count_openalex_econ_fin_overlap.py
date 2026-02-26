#!/usr/bin/env python3
"""Compute consistent Econ/Finance overlap for climate-finance papers.

For each year, fetches actual paper IDs for:
  - Economics + "climate finance"
  - Finance + "climate finance"
Then computes: econ_only, both, fin_only from set operations.

Output: $DATA/catalogs/openalex_econ_fin_overlap.csv

Usage:
    uv run python scripts/count_openalex_econ_fin_overlap.py [--delay 0.3]
"""

import argparse
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from utils import CATALOGS_DIR, MAILTO, polite_get, save_csv

OPENALEX_WORKS_URL = "https://api.openalex.org/works"
ECONOMICS_CONCEPT_ID = "C162324750"
FINANCE_CONCEPT_ID = "C10138342"
YEAR_MIN = 1990
YEAR_MAX = 2025


def parse_args():
    parser = argparse.ArgumentParser(description="Econ/Finance CF overlap via ID sets")
    parser.add_argument("--delay", type=float, default=0.3)
    return parser.parse_args()


def fetch_ids(filter_expr, delay):
    ids = set()
    cursor = "*"
    while cursor:
        params = {
            "filter": filter_expr,
            "select": "id",
            "per_page": 200,
            "cursor": cursor,
            "mailto": MAILTO,
        }
        resp = polite_get(OPENALEX_WORKS_URL, params=params, delay=delay)
        payload = resp.json()
        for row in payload.get("results", []):
            wid = row.get("id", "")
            if wid:
                ids.add(wid)
        cursor = payload.get("meta", {}).get("next_cursor")
    return ids


def main():
    args = parse_args()
    phrase = '"climate finance"'
    rows = []

    for year in range(YEAR_MIN, YEAR_MAX + 1):
        econ_base = f"concept.id:{ECONOMICS_CONCEPT_ID},publication_year:{year}"
        fin_base = f"concept.id:{FINANCE_CONCEPT_ID},publication_year:{year}"

        # Fetch econ CF IDs (title OR abstract)
        econ_title = fetch_ids(f"{econ_base},title.search:{phrase}", args.delay)
        econ_abs = fetch_ids(f"{econ_base},abstract.search:{phrase}", args.delay)
        econ_ids = econ_title | econ_abs

        # Fetch finance CF IDs (title OR abstract)
        fin_title = fetch_ids(f"{fin_base},title.search:{phrase}", args.delay)
        fin_abs = fetch_ids(f"{fin_base},abstract.search:{phrase}", args.delay)
        fin_ids = fin_title | fin_abs

        both = econ_ids & fin_ids
        econ_only = econ_ids - fin_ids
        fin_only = fin_ids - econ_ids

        rows.append({
            "year": year,
            "n_econ_cf": len(econ_ids),
            "n_fin_cf": len(fin_ids),
            "n_both": len(both),
            "n_econ_only": len(econ_only),
            "n_fin_only": len(fin_only),
        })
        print(f"{year}: econ={len(econ_ids)} fin={len(fin_ids)} "
              f"both={len(both)} econ_only={len(econ_only)} fin_only={len(fin_only)}")

    df = pd.DataFrame(rows).sort_values("year").reset_index(drop=True)
    out = os.path.join(CATALOGS_DIR, "openalex_econ_fin_overlap.csv")
    save_csv(df, out)
    print("Done.")


if __name__ == "__main__":
    main()
