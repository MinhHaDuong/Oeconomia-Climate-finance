#!/usr/bin/env python3
"""Count yearly works and climate-finance works in OpenAlex by concept scope.

Outputs:
- $DATA/catalogs/openalex_econ_yearly.csv (default scope: economics)

Definitions:
- Denominator: works tagged with selected OpenAlex concept scope
- Numerator: those works with "climate finance" in title OR abstract

Usage:
    uv run python scripts/count_openalex_econ_cf.py
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

SCOPE_TO_FILTER = {
    "economics": f"concept.id:{ECONOMICS_CONCEPT_ID}",
    "finance": f"concept.id:{FINANCE_CONCEPT_ID}",
    "economics_or_finance": f"concept.id:{ECONOMICS_CONCEPT_ID}|{FINANCE_CONCEPT_ID}",
    "finance_only": f"concept.id:{FINANCE_CONCEPT_ID},concept.id:!{ECONOMICS_CONCEPT_ID}",
    "economics_and_finance": f"concept.id:{ECONOMICS_CONCEPT_ID},concept.id:{FINANCE_CONCEPT_ID}",
}


def parse_args():
    parser = argparse.ArgumentParser(description="Count OpenAlex scope/climate-finance yearly")
    parser.add_argument("--delay", type=float, default=0.4,
                        help="Delay between API requests in seconds")
    parser.add_argument(
        "--scope",
        type=str,
        default="economics",
        choices=list(SCOPE_TO_FILTER.keys()),
        help="OpenAlex concept scope",
    )
    parser.add_argument("--types", type=str, default="",
                        help="Optional comma-separated OpenAlex types (e.g. article,review)")
    parser.add_argument("--out", type=str,
                        default=os.path.join(CATALOGS_DIR, "openalex_econ_yearly.csv"),
                        help="Output CSV path")
    return parser.parse_args()


def build_type_filter(types_arg):
    if not types_arg.strip():
        return ""
    parts = [t.strip() for t in types_arg.split(",") if t.strip()]
    if not parts:
        return ""
    return ",type:" + "|".join(parts)


def fetch_scope_by_year(delay, type_filter, scope_clause):
    params = {
        "filter": (
            f"{scope_clause},"
            f"publication_year:{YEAR_MIN}-{YEAR_MAX}{type_filter}"
        ),
        "group_by": "publication_year",
        "mailto": MAILTO,
    }
    resp = polite_get(OPENALEX_WORKS_URL, params=params, delay=delay)
    data = resp.json()

    counts = {year: 0 for year in range(YEAR_MIN, YEAR_MAX + 1)}
    for item in data.get("group_by", []):
        year = int(item.get("key", 0))
        if YEAR_MIN <= year <= YEAR_MAX:
            counts[year] = int(item.get("count", 0))
    return counts


def fetch_ids_for_filter(filter_expr, delay):
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
            work_id = row.get("id", "")
            if work_id:
                ids.add(work_id)

        cursor = payload.get("meta", {}).get("next_cursor")
    return ids


def fetch_climate_finance_by_year(delay, type_filter, scope_clause):
    phrase = '"climate finance"'
    results = {}

    for year in range(YEAR_MIN, YEAR_MAX + 1):
        base = (
            f"{scope_clause},"
            f"publication_year:{year}{type_filter}"
        )
        title_filter = f"{base},title.search:{phrase}"
        abstract_filter = f"{base},abstract.search:{phrase}"

        title_ids = fetch_ids_for_filter(title_filter, delay=delay)
        abstract_ids = fetch_ids_for_filter(abstract_filter, delay=delay)
        union_ids = title_ids | abstract_ids

        results[year] = {
            "n_climate_finance_title": len(title_ids),
            "n_climate_finance_abstract": len(abstract_ids),
            "n_climate_finance_union": len(union_ids),
        }
        print(
            f"Year {year}: title={len(title_ids)} abstract={len(abstract_ids)} "
            f"union={len(union_ids)}"
        )

    return results


def main():
    args = parse_args()
    type_filter = build_type_filter(args.types)
    scope_clause = SCOPE_TO_FILTER[args.scope]

    out_path = args.out
    if args.out == os.path.join(CATALOGS_DIR, "openalex_econ_yearly.csv") and args.scope != "economics":
        out_path = os.path.join(CATALOGS_DIR, f"openalex_{args.scope}_yearly.csv")

    print(f"Fetching OpenAlex denominator for scope={args.scope}...")
    denom = fetch_scope_by_year(delay=args.delay, type_filter=type_filter, scope_clause=scope_clause)

    print("Fetching OpenAlex climate-finance numerator (title OR abstract)...")
    numer = fetch_climate_finance_by_year(
        delay=args.delay,
        type_filter=type_filter,
        scope_clause=scope_clause,
    )

    rows = []
    for year in range(YEAR_MIN, YEAR_MAX + 1):
        n_econ = int(denom.get(year, 0))
        n_title = int(numer.get(year, {}).get("n_climate_finance_title", 0))
        n_abstract = int(numer.get(year, {}).get("n_climate_finance_abstract", 0))
        n_union = int(numer.get(year, {}).get("n_climate_finance_union", 0))
        share = (n_union / n_econ) if n_econ else 0.0

        rows.append({
            "source": "openalex",
            "scope": args.scope,
            "year": year,
            "n_economics": n_econ,
            "n_climate_finance_title": n_title,
            "n_climate_finance_abstract": n_abstract,
            "n_climate_finance": n_union,
            "share_climate_finance": share,
            "climate_finance_pattern": r"\\bclimate[\\s-]?finance\\b",
            "economics_definition": scope_clause,
            "query_mode": "title.search OR abstract.search",
            "types_filter": args.types.strip(),
        })

    df = pd.DataFrame(rows)
    df = df.sort_values("year").reset_index(drop=True)
    save_csv(df, out_path)

    print("Done.")
    print(f"  Scope: {args.scope} ({scope_clause})")
    print(f"  Years: {df['year'].min()}–{df['year'].max()}")
    print(f"  Total economics: {int(df['n_economics'].sum()):,}")
    print(f"  Total climate finance: {int(df['n_climate_finance'].sum()):,}")


if __name__ == "__main__":
    main()
