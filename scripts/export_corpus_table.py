"""Export corpus composition table by source.

Produces:
- content/tables/tab_corpus_sources.csv: detailed stats per source
- content/tables/tab_corpus_sources.md: Quarto-includable markdown table

Shows for each source: query description, records before/after refinement,
non-English share, journal-article share, DOI coverage, reference coverage,
and abstract availability.
"""

import argparse
import os

import pandas as pd

from utils import CATALOGS_DIR, get_logger, save_csv, BASE_DIR

log = get_logger("export_corpus_table")

CORE_THRESHOLD = 50

# Source metadata: label and query description from catalog_*.py scripts
SOURCE_META = {
    "openalex": {
        "label": "OpenAlex",
        "query": "4-tier keyword taxonomy, 9 languages (default.search on title+abstract+fulltext)",
    },
    "istex": {
        "label": "ISTEX",
        "query": '"climate finance" OR "finance climat*" on French institutional archive',
    },
    "bibcnrs": {
        "label": "bibCNRS",
        "query": "FR, ZH, JA, DE queries via Gale/Wanfang/NewsBank (CNRS legacy portal)",
    },
    "scispsace": {
        "label": "SciSpace",
        "query": "AI-curated systematic review (RIS + CSV exports)",
    },
    "grey": {
        "label": "Grey literature",
        "query": "World Bank Open Knowledge Repository API + curated YAML (OECD, UNFCCC, CPI)",
    },
    "teaching": {
        "label": "Teaching canon",
        "query": "Syllabi from 15 programmes (doctoral, MBA, professional, MOOC)",
    },
}

PRIMARY_SOURCES = list(SOURCE_META.keys())

CAPTION = (
    ": Corpus sources. *Raw*: records with `from_*` provenance flag before"
    " filtering (a record in multiple sources is counted once per source)."
    " *Refined*: after six-flag quality filtering."
    " *Unique*: found only in that source (`source_count = 1`)."
    " *%DOI*, *%Abstract*, *%Refs*: metadata completeness among refined"
    " records. {#tbl-quality}"
)


def _write_md_table(summary: pd.DataFrame, path: str) -> None:
    """Write a Quarto-includable markdown table with selected columns."""
    cols = ["Source", "Raw", "Refined", "Unique", "%DOI", "%Abstract", "%Refs"]
    lines = [
        "| Source | Raw | Refined | Unique | %DOI | %Abstract | %Refs |",
        "|:-------|----:|--------:|-------:|-----:|----------:|------:|",
    ]
    for _, row in summary.iterrows():
        is_total = "TOTAL" in str(row["Source"])
        vals = []
        for c in cols:
            v = row.get(c, "")
            if c in ("Raw", "Refined", "Unique"):
                v = f"{int(v):,}" if pd.notna(v) else ""
            vals.append(f"**{v}**" if is_total else str(v))
        lines.append("| " + " | ".join(vals) + " |")
    lines.append("")
    lines.append(CAPTION)
    lines.append("")
    with open(path, "w") as f:
        f.write("\n".join(lines))


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

    # Abstract availability
    abs_s = df["abstract"].fillna("").astype(str).str.strip()
    df["has_abstract"] = (abs_s.str.len() > 10) & (abs_s != "nan")

    log.info("Loaded %d refined works from %s", len(df), path)

    # Load unified corpus (before filtering) for raw counts
    # Must include from_* columns — usecols=["source"] dropped them (#251 bug)
    unified_path = os.path.join(CATALOGS_DIR, "unified_works.csv")
    unified_cols = pd.read_csv(unified_path, nrows=0).columns.tolist()
    use = [c for c in unified_cols if c.startswith("from_") or c in ("source", "source_count")]
    unified = pd.read_csv(unified_path, usecols=use)
    log.info("Loaded %d unified works from %s", len(unified), unified_path)

    # Load citations for reference coverage
    cit_path = os.path.join(CATALOGS_DIR, "citations.csv")
    cit = pd.read_csv(cit_path, usecols=["source_doi"], low_memory=False)
    source_dois = set(cit["source_doi"].str.lower().str.strip().dropna()) - {
        "", "nan", "none",
    }
    df["has_refs"] = df["doi_lower"].isin(source_dois)
    log.info("Loaded %d citation rows", len(cit))

    # Compute per-source statistics
    rows = []
    for src in PRIMARY_SOURCES:
        from_col = f"from_{src}"
        mask_u = unified[from_col] == 1 if from_col in unified.columns else unified["source"].str.contains(src, na=False)
        mask_r = df[from_col] == 1 if from_col in df.columns else df["source"].str.contains(src, na=False)
        sub = df[mask_r]
        meta = SOURCE_META[src]
        n_raw = int(mask_u.sum())
        n_refined = len(sub)
        n_unique = int(((df["source_count"] == 1) & (df[from_col] == 1)).sum()) if from_col in df.columns else 0
        if n_refined == 0:
            rows.append({
                "Source": meta["label"], "Query": meta["query"],
                "Raw": n_raw, "Refined": n_refined, "Unique": n_unique,
            })
            continue
        rows.append({
            "Source": meta["label"],
            "Query": meta["query"],
            "Raw": n_raw,
            "Refined": n_refined,
            "Unique": n_unique,
            "%non-EN": f"{(~sub['is_english']).mean() * 100:.0f}%",
            "%Journal": f"{sub['has_journal'].mean() * 100:.0f}%",
            "%DOI": f"{sub['has_doi'].mean() * 100:.0f}%",
            "%Refs": f"{sub['has_refs'].mean() * 100:.0f}%",
            "%Abstract": f"{sub['has_abstract'].mean() * 100:.0f}%",
        })

    # Totals row (deduplicated)
    n_unique_total = int((df["source_count"] == 1).sum()) if "source_count" in df.columns else 0
    rows.append({
        "Source": "TOTAL",
        "Query": "",
        "Raw": len(unified),
        "Refined": len(df),
        "Unique": n_unique_total,
        "%non-EN": f"{(~df['is_english']).mean() * 100:.0f}%",
        "%Journal": f"{df['has_journal'].mean() * 100:.0f}%",
        "%DOI": f"{df['has_doi'].mean() * 100:.0f}%",
        "%Refs": f"{df['has_refs'].mean() * 100:.0f}%",
        "%Abstract": f"{df['has_abstract'].mean() * 100:.0f}%",
    })

    summary = pd.DataFrame(rows)

    # Save CSV (full detail)
    csv_path = os.path.join(BASE_DIR, "content", "tables", "tab_corpus_sources.csv")
    save_csv(summary, csv_path)

    # Save markdown table (included by data-paper.qmd and _includes/tab_corpus_sources.md)
    md_path = os.path.join(BASE_DIR, "content", "tables", "tab_corpus_sources.md")
    _write_md_table(summary, md_path)
    log.info("Wrote %s", md_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    main()
