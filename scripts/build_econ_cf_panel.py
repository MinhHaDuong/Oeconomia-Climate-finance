#!/usr/bin/env python3
"""Build harmonized yearly panel for economics and climate-finance counts.

Runs:
1) OpenAlex yearly counting
2) RePEc yearly counting (from local ReDIF files)
3) Merge both into one panel

Outputs:
- $DATA/catalogs/openalex_econ_yearly.csv
- $DATA/catalogs/repec_econ_yearly.csv
- $DATA/catalogs/econ_cf_yearly_panel.csv

Usage:
    uv run python scripts/build_econ_cf_panel.py --repec-root ~/data/repec/RePEc
"""

import argparse
import os

import pandas as pd

import sys
sys.path.insert(0, os.path.dirname(__file__))
from count_openalex_econ_cf import fetch_climate_finance_by_year, fetch_economics_by_year
from count_repec_econ_cf import count_repec_yearly
from utils import CATALOGS_DIR, save_csv

YEAR_MIN = 1990
YEAR_MAX = 2025
DEFAULT_REPEC_ROOT = os.path.expanduser(
    os.environ.get("REPEC_ROOT", "~/data/datasets/external/RePEc")
)


def parse_args():
    parser = argparse.ArgumentParser(description="Build OpenAlex+RePEc economics/climate-finance panel")
    parser.add_argument("--delay", type=float, default=0.4,
                        help="OpenAlex API delay in seconds")
    parser.add_argument("--types", type=str, default="",
                        help="Optional comma-separated OpenAlex types")
    parser.add_argument(
        "--repec-root",
        type=str,
        default=DEFAULT_REPEC_ROOT,
        help="Path to local RePEc ReDIF root (passed to count_repec_econ_cf.py)",
    )
    parser.add_argument(
        "--repec-templates",
        type=str,
        default="ReDIF-Article,ReDIF-Paper,ReDIF-Book,ReDIF-Chapter",
        help="Comma-separated ReDIF templates to include",
    )
    parser.add_argument(
        "--panel-out",
        type=str,
        default=os.path.join(CATALOGS_DIR, "econ_cf_yearly_panel.csv"),
        help="Output merged panel CSV",
    )
    return parser.parse_args()


def build_type_filter(types_arg):
    if not types_arg.strip():
        return ""
    parts = [t.strip() for t in types_arg.split(",") if t.strip()]
    if not parts:
        return ""
    return ",type:" + "|".join(parts)


def run_openalex(delay, types_arg):
    type_filter = build_type_filter(types_arg)
    denom = fetch_economics_by_year(delay=delay, type_filter=type_filter)
    numer = fetch_climate_finance_by_year(delay=delay, type_filter=type_filter)

    rows = []
    for year in range(YEAR_MIN, YEAR_MAX + 1):
        n_econ = int(denom.get(year, 0))
        n_title = int(numer.get(year, {}).get("n_climate_finance_title", 0))
        n_abstract = int(numer.get(year, {}).get("n_climate_finance_abstract", 0))
        n_union = int(numer.get(year, {}).get("n_climate_finance_union", 0))
        share = (n_union / n_econ) if n_econ else 0.0

        rows.append({
            "source": "openalex",
            "year": year,
            "n_economics": n_econ,
            "n_climate_finance_title": n_title,
            "n_climate_finance_abstract": n_abstract,
            "n_climate_finance": n_union,
            "share_climate_finance": share,
            "types_filter": types_arg.strip(),
        })

    out = pd.DataFrame(rows)
    save_csv(out, os.path.join(CATALOGS_DIR, "openalex_econ_yearly.csv"))
    return out


def run_repec(repec_root, templates):
    resolved_root = repec_root.strip()
    out = count_repec_yearly(repec_root=resolved_root, include_templates=templates)
    save_csv(out, os.path.join(CATALOGS_DIR, "repec_econ_yearly.csv"))
    return out


def merge_panel(openalex_df, repec_df):
    panel = pd.concat([openalex_df, repec_df], ignore_index=True)
    panel = panel.sort_values(["source", "year"]).reset_index(drop=True)
    return panel


def main():
    args = parse_args()

    print("[1/3] Building OpenAlex yearly counts")
    openalex_df = run_openalex(delay=args.delay, types_arg=args.types)

    print("[2/3] Building RePEc yearly counts")
    repec_df = run_repec(repec_root=args.repec_root, templates=args.repec_templates)

    print("[3/3] Merging panel")
    panel = merge_panel(openalex_df, repec_df)
    save_csv(panel, args.panel_out)

    print("Done.")
    print(f"  Panel rows: {len(panel)}")
    print(f"  Sources: {', '.join(sorted(panel['source'].unique()))}")
    print(f"  Years: {panel['year'].min()}–{panel['year'].max()}")


if __name__ == "__main__":
    main()
