#!/usr/bin/env python3
"""Generate venue table for the Oeconomia manuscript.

Shows distinctive journals per pole (efficiency vs accountability)
among core works (cited >= 50). Output: content/tables/tab_venues.md

Usage:
    uv run python scripts/make_tab_venues.py [--min-papers 10] [--core-threshold 50]
"""

import argparse
import os

import numpy as np
import pandas as pd
from utils import BASE_DIR, CATALOGS_DIR, get_logger

log = get_logger("make_tab_venues")

POLE_PAPERS = os.path.join(BASE_DIR, "content", "tables", "tab_pole_papers.csv")
OUTPUT = os.path.join(BASE_DIR, "content", "tables", "tab_venues.md")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--min-papers", type=int, default=10,
                        help="Minimum core papers per journal to include")
    parser.add_argument("--core-threshold", type=int, default=50,
                        help="Minimum cited_by_count for core subset")
    args = parser.parse_args()

    works = pd.read_csv(
        os.path.join(CATALOGS_DIR, "refined_works.csv"), low_memory=False
    )
    poles = pd.read_csv(POLE_PAPERS)

    # Deduplicate poles on DOI, merge with works for journal metadata
    poles_dedup = poles.drop_duplicates(subset="doi", keep="first")
    works_doi = works[works["doi"].fillna("") != ""].copy()
    merged = works_doi.merge(
        poles_dedup[["doi", "axis_score", "pole_assignment"]],
        on="doi", how="inner",
    )

    # Core only
    core = merged[merged["cited_by_count"] >= args.core_threshold].copy()

    # Count per journal per pole
    eff = core[core["pole_assignment"] == "efficiency"]
    acc = core[core["pole_assignment"] == "accountability"]
    eff_counts = eff["journal"].value_counts()
    acc_counts = acc["journal"].value_counts()

    rows = []
    for j in set(eff_counts.index) | set(acc_counts.index):
        ne = eff_counts.get(j, 0)
        na = acc_counts.get(j, 0)
        total = ne + na
        if total < args.min_papers:
            continue
        # Log-odds ratio with Laplace smoothing
        lor = np.log2((ne + 0.5) / (na + 0.5))
        rows.append({
            "journal": j, "efficiency": ne, "accountability": na,
            "total": total, "log_odds": lor,
        })

    df = pd.DataFrame(rows).sort_values("log_odds", ascending=False)

    # Assign lean labels
    def lean(lor):
        if lor > 0.5:
            return "Efficiency"
        elif lor < -0.5:
            return "Accountability"
        return "Shared"

    df["lean"] = df["log_odds"].apply(lean)

    # Select venues that are both distinctive and recognizable.
    # Strategy: top 5 by total per lean, then add key journals if missing.
    eff_sel = df[df["lean"] == "Efficiency"].nlargest(5, "total")
    shared_sel = df[df["lean"] == "Shared"].nlargest(2, "total")
    acc_sel = df[df["lean"] == "Accountability"].nlargest(5, "total")

    # Ensure key argument-relevant journals are included
    key_journals = [
        "Review of Financial Studies",
        "Journal of Financial Economics",
        "Energy Economics",
        "International Environmental Agreements Politics Law and Economics",
        "Global Environmental Politics",
        "Climatic Change",
        "Climate Policy",
        "Nature Climate Change",
        "Energy Policy",
    ]
    key_rows = df[df["journal"].isin(key_journals)]

    selected = pd.concat([eff_sel, shared_sel, acc_sel, key_rows])
    selected = selected.drop_duplicates(subset="journal")
    selected = selected.sort_values("log_odds", ascending=False)

    # Build markdown table
    lines = []
    lines.append(
        "| Lean | Journal | Eff. | Acc. | Total |"
    )
    lines.append("|:-----|:--------|-----:|-----:|------:|")

    for _, r in selected.iterrows():
        lines.append(
            f"| {r['lean']} | {r['journal']} "
            f"| {r['efficiency']:.0f} | {r['accountability']:.0f} "
            f"| {r['total']:.0f} |"
        )

    caption = (
        ": Publication venues of core works (cited $\\geq$ 50) by pole assignment. "
        "Each work is assigned to the efficiency or accountability pole based on "
        "its position along the embedding axis (§3.4). "
        "\"Lean\" indicates the venue's overall orientation: "
        "journals where a majority of core papers fall on one side. "
        "{#tbl-venues}"
    )
    lines.append("")
    lines.append(caption)

    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w") as f:
        f.write("\n".join(lines) + "\n")

    log.info("Wrote %d venues to %s", len(selected), OUTPUT)


if __name__ == "__main__":
    main()
