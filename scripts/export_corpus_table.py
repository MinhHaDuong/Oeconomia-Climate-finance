"""Export corpus composition table by source for the technical report.

Produces:
- content/tables/tab_corpus_sources.csv: works per source (total and core)
- stdout: formatted markdown table
"""

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from utils import CATALOGS_DIR, save_csv, BASE_DIR

CORE_THRESHOLD = 50


def main():
    # Load refined corpus
    path = os.path.join(CATALOGS_DIR, "refined_works.csv")
    df = pd.read_csv(path, usecols=["source", "cited_by_count"])
    print(f"Loaded {len(df)} works from {path}")

    # Consolidate multi-source entries: "openalex|scispsace" → count for each
    PRIMARY_SOURCES = [
        "openalex", "openalex_historical", "istex", "bibcnrs",
        "scispsace", "grey", "teaching",
    ]
    rows = []
    for src in PRIMARY_SOURCES:
        mask = df["source"].str.contains(src, na=False)
        n_total = mask.sum()
        n_core = (mask & (df["cited_by_count"] >= CORE_THRESHOLD)).sum()
        rows.append({"source": src, "total": n_total, "core": n_core})
    summary = pd.DataFrame(rows).set_index("source")
    # Deduplicated totals (each work counted once)
    summary.loc["TOTAL (deduplicated)"] = [len(df),
        (df["cited_by_count"] >= CORE_THRESHOLD).sum()]
    summary = summary.astype(int)

    # Save CSV
    out_path = os.path.join(BASE_DIR, "content", "tables", "tab_corpus_sources.csv")
    summary.index.name = "source"
    save_csv(summary.reset_index(), out_path)

    # Print markdown table with self-explanatory labels
    LABELS = {
        "openalex": "OpenAlex --- scholarly database (title/abstract search)",
        "openalex_historical": "OpenAlex --- pre-2010 historical backfill",
        "istex": "ISTEX --- French institutional full-text repository",
        "bibcnrs": "bibCNRS --- non-English literature (FR, ZH, JA, DE)",
        "scispsace": "SciSpace --- AI-curated seed expansion",
        "grey": "Grey literature --- OECD, World Bank, UNFCCC reports",
        "teaching": "Teaching canon --- MBA/doctoral syllabi",
        "TOTAL (deduplicated)": "**Total (deduplicated)**",
    }
    print()
    print("| Source | Extended corpus | Core (cited >= 50) |")
    print("|:-------|---:|---:|")
    for src, row in summary.iterrows():
        label = LABELS.get(src, src)
        print(f"| {label} | {row['total']:,} | {row['core']:,} |")
    print()


if __name__ == "__main__":
    main()
