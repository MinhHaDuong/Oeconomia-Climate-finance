#!/usr/bin/env python3
"""Compute venue concentration (Herfindahl-Hirschman Index / Shannon entropy) per year.

Reads refined_works, filters to journal-type venues, groups by year,
and computes per-year concentration metrics.

Inputs:
  - refined_works.csv (via pipeline_loaders or --input)

Outputs:
  - content/tables/tab_venue_concentration.csv

Usage:
    uv run python scripts/compute_venue_concentration.py --output content/tables/tab_venue_concentration.csv
"""

import numpy as np
import pandas as pd
from pipeline_io import save_csv
from schemas import VenueConcentrationSchema
from script_io_args import parse_io_args, validate_io
from summarize_core_venues import canonical_venue, venue_type
from utils import get_logger

log = get_logger("compute_venue_concentration")


def compute_concentration(df: pd.DataFrame) -> pd.DataFrame:
    """Compute per-year venue concentration from a DataFrame with year and journal columns.

    Filters to journal-type venues (excludes working papers, repositories, reports),
    then computes HHI and Shannon entropy (natural log) per year.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain columns ``year`` (int-like) and ``journal`` (str, nullable).

    Returns
    -------
    pd.DataFrame
        Columns: year, hhi, shannon_entropy, n_venues, n_papers.

    """
    work = df[["year", "journal"]].copy()
    work["year"] = pd.to_numeric(work["year"], errors="coerce")
    work = work.dropna(subset=["year"])
    work["year"] = work["year"].astype(int)

    # Clean journal: fill nulls, strip whitespace, drop empty
    work["journal"] = work["journal"].fillna("").astype(str).str.strip()
    work = work[work["journal"] != ""]

    # Apply canonical venue mapping and filter to journals only
    work["venue_canonical"] = work["journal"].map(canonical_venue)
    work["venue_type"] = work["venue_canonical"].map(venue_type)
    work = work[work["venue_type"] == "journal"]

    if work.empty:
        return pd.DataFrame(
            columns=["year", "hhi", "shannon_entropy", "n_venues", "n_papers"]
        )

    rows = []
    for year, group in work.groupby("year"):
        counts = group["venue_canonical"].value_counts()
        n_papers = counts.sum()
        n_venues = len(counts)
        shares = counts / n_papers

        hhi = float((shares**2).sum())
        entropy = float(-(shares * np.log(shares)).sum()) if n_venues > 1 else 0.0

        rows.append(
            {
                "year": year,
                "hhi": hhi,
                "shannon_entropy": entropy,
                "n_venues": n_venues,
                "n_papers": n_papers,
            }
        )

    result = pd.DataFrame(rows)
    return result


def main():
    io_args, _extra = parse_io_args()
    validate_io(output=io_args.output)

    if io_args.input:
        log.info("Reading from --input: %s", io_args.input[0])
        df = pd.read_csv(io_args.input[0], dtype=str, keep_default_na=False)
    else:
        from pipeline_loaders import load_refined_works

        df = load_refined_works()

    result = compute_concentration(df)
    VenueConcentrationSchema.validate(result)
    save_csv(result, io_args.output)
    log.info("Wrote %d rows to %s", len(result), io_args.output)


if __name__ == "__main__":
    main()
