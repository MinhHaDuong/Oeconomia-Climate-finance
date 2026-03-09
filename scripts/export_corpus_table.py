"""Export corpus composition table by source for the technical report.

Produces:
- content/tables/tab_corpus_sources.csv: detailed stats per source
- stdout: formatted markdown table

Shows for each source: query description, records before/after refinement,
non-English share, journal-article share, DOI coverage, reference coverage.
"""

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from utils import CATALOGS_DIR, save_csv, BASE_DIR

CORE_THRESHOLD = 50

# Source metadata: label and query description from catalog_*.py scripts
SOURCE_META = {
    "openalex": {
        "label": "OpenAlex",
        "query": 'title/abstract search: "climate finance", "finance climat"',
    },
    "openalex_historical": {
        "label": "OpenAlex (historical)",
        "query": "14 pre-2009 terms (CDM, carbon finance, adaptation fund, ...)",
    },
    "istex": {
        "label": "ISTEX",
        "query": "French institutional full-text repository (Springer, Elsevier, Wiley)",
    },
    "bibcnrs": {
        "label": "bibCNRS",
        "query": "non-English queries: FR, ZH, JA via WoS/EconLit/FRANCIS",
    },
    "scispsace": {
        "label": "SciSpace",
        "query": "AI-curated seed expansion (systematic review + RIS export)",
    },
    "grey": {
        "label": "Grey literature",
        "query": "World Bank OKR API + curated YAML (OECD, UNFCCC reports)",
    },
    "teaching": {
        "label": "Teaching canon",
        "query": "MBA/doctoral syllabi (hand-curated seed list)",
    },
}

PRIMARY_SOURCES = list(SOURCE_META.keys())


def main():
    # Load refined corpus (after filtering)
    path = os.path.join(CATALOGS_DIR, "refined_works.csv")
    df = pd.read_csv(path)
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df["cited_by_count"] = pd.to_numeric(df["cited_by_count"], errors="coerce").fillna(0)
    df["doi_lower"] = df["doi"].str.lower().str.strip()
    df["has_doi"] = df["doi_lower"].apply(
        lambda x: bool(x) and str(x) not in ("", "nan", "none")
    )
    df["is_english"] = df["language"].str.lower().str.startswith("en", na=True)
    df["has_journal"] = df["journal"].notna() & (df["journal"].str.strip() != "")
    print(f"Loaded {len(df)} refined works from {path}")

    # Load unified corpus (before filtering) for raw counts
    unified_path = os.path.join(CATALOGS_DIR, "unified_works.csv")
    unified = pd.read_csv(unified_path, usecols=["source"])
    print(f"Loaded {len(unified)} unified works from {unified_path}")

    # Load citations for reference coverage
    cit_path = os.path.join(CATALOGS_DIR, "citations.csv")
    cit = pd.read_csv(cit_path, usecols=["source_doi"], low_memory=False)
    source_dois = set(cit["source_doi"].str.lower().str.strip().dropna()) - {
        "", "nan", "none",
    }
    df["has_refs"] = df["doi_lower"].isin(source_dois)
    print(f"Loaded {len(cit)} citation rows")

    # Compute per-source statistics
    rows = []
    for src in PRIMARY_SOURCES:
        mask_u = unified["source"].str.contains(src, na=False)
        mask_r = df["source"].str.contains(src, na=False)
        sub = df[mask_r]
        meta = SOURCE_META[src]
        n_raw = int(mask_u.sum())
        n_refined = len(sub)
        if n_refined == 0:
            rows.append({
                "Source": meta["label"], "Query": meta["query"],
                "Raw": n_raw, "Refined": n_refined,
            })
            continue
        rows.append({
            "Source": meta["label"],
            "Query": meta["query"],
            "Raw": n_raw,
            "Refined": n_refined,
            "non-EN": int((~sub["is_english"]).sum()),
            "%Journal": f"{sub['has_journal'].mean() * 100:.0f}%",
            "%DOI": f"{sub['has_doi'].mean() * 100:.0f}%",
            "%Refs": f"{sub['has_refs'].mean() * 100:.0f}%",
        })

    # Totals row (deduplicated)
    rows.append({
        "Source": "TOTAL (deduplicated)",
        "Query": "",
        "Raw": len(unified),
        "Refined": len(df),
        "non-EN": int((~df["is_english"]).sum()),
        "%Journal": f"{df['has_journal'].mean() * 100:.0f}%",
        "%DOI": f"{df['has_doi'].mean() * 100:.0f}%",
        "%Refs": f"{df['has_refs'].mean() * 100:.0f}%",
    })

    summary = pd.DataFrame(rows)

    # Save CSV
    out_path = os.path.join(BASE_DIR, "content", "tables", "tab_corpus_sources.csv")
    save_csv(summary, out_path)

    # Print markdown table
    print()
    print(
        "| Source | Query | Raw | Refined | non-EN "
        "| %Journal | %DOI | %Refs |"
    )
    print("|:-------|:------|---:|---:|---:|---:|---:|---:|")
    for _, row in summary.iterrows():
        non_en = int(row.get("non-EN", 0)) if pd.notna(row.get("non-EN")) else 0
        print(
            f"| {row['Source']} | {row['Query']} "
            f"| {int(row['Raw']):,} | {int(row['Refined']):,} | {non_en:,} "
            f"| {row.get('%Journal', '')} | {row.get('%DOI', '')} "
            f"| {row.get('%Refs', '')} |"
        )
    print()


if __name__ == "__main__":
    main()
