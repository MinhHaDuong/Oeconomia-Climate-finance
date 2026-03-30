"""Lineage analysis of climate finance citation genealogy.

Selects highly-cited backbone papers, assigns them to three intellectual
lineages (CDM/Kyoto heritage, Accountability pole, Efficiency pole),
builds the internal citation DAG, and computes a year × band layout.

Reads:
  data/catalogs/refined_works.csv
  data/catalogs/refined_citations.csv
  data/catalogs/semantic_clusters.csv
  content/tables/tab_pole_papers.csv  (optional — from analyze_bimodality.py)

Produces:
  content/tables/tab_lineages.csv — backbone papers with lineage, position, metadata
"""

import argparse
import os
import warnings
from collections import defaultdict

import numpy as np
import pandas as pd
from utils import (
    BASE_DIR,
    CATALOGS_DIR,
    get_logger,
    load_analysis_config,
    load_analysis_periods,
    load_refined_citations,
    normalize_doi,
)

log = get_logger("analyze_genealogy")

warnings.filterwarnings("ignore", category=FutureWarning)

# --- Paths ---
TABLES_DIR = os.path.join(BASE_DIR, "content", "tables")
os.makedirs(TABLES_DIR, exist_ok=True)

# --- Config ---
_cfg = load_analysis_config()


# ============================================================
# Step 1: Load data
# ============================================================

def load_data():
    """Load works, citations, and semantic clusters."""
    log.info("Loading data...")
    works = pd.read_csv(os.path.join(CATALOGS_DIR, "refined_works.csv"))
    works["year"] = pd.to_numeric(works["year"], errors="coerce")
    works["doi_norm"] = works["doi"].apply(normalize_doi)
    works["cited_by_count"] = pd.to_numeric(
        works["cited_by_count"], errors="coerce"
    ).fillna(0)

    # Build DOI → metadata lookup
    doi_meta = {}
    for _, row in works.iterrows():
        d = row["doi_norm"]
        if d and d not in ("", "nan", "none"):
            doi_meta[d] = {
                "title": str(row.get("title", "") or ""),
                "first_author": str(row.get("first_author", "") or ""),
                "year": row["year"] if pd.notna(row["year"]) else None,
                "cited_by_count": row["cited_by_count"],
                "abstract": str(row.get("abstract", "") or ""),
            }

    # Load citations
    log.info("Loading citations...")
    cit = load_refined_citations()
    cit["source_doi"] = cit["source_doi"].apply(normalize_doi)
    cit["ref_doi"] = cit["ref_doi"].apply(normalize_doi)
    cit = cit[(cit["source_doi"] != "") & (cit["ref_doi"] != "")]
    cit = cit[~cit["source_doi"].isin(["nan", "none"])]
    cit = cit[~cit["ref_doi"].isin(["nan", "none"])]

    # Add ref metadata from citations (for papers not in refined_works)
    for _, row in cit.iterrows():
        d = row["ref_doi"]
        if d and d not in ("", "nan", "none") and d not in doi_meta:
            yr = row.get("ref_year", None)
            if pd.notna(yr):
                try:
                    yr = float(yr)
                except (ValueError, TypeError):
                    yr = None
            else:
                yr = None
            doi_meta[d] = {
                "title": str(row.get("ref_title", "") or ""),
                "first_author": str(row.get("ref_first_author", "") or ""),
                "year": yr,
                "cited_by_count": 0,
                "abstract": "",
            }

    # Load KMeans semantic clusters (needed for CDM cluster identification)
    log.info("Loading semantic clusters...")
    sem_df = pd.read_csv(os.path.join(CATALOGS_DIR, "semantic_clusters.csv"))
    sem_df["doi_norm"] = sem_df["doi"].apply(normalize_doi)
    doi_to_cluster = dict(zip(sem_df["doi_norm"], sem_df["semantic_cluster"]))
    log.info("Semantic clusters loaded: %d papers", len(sem_df))

    return works, cit, doi_meta, doi_to_cluster


# ============================================================
# Step 2: Select backbone papers
# ============================================================

def select_backbone(works, doi_meta):
    """Select highly-cited papers with abstracts and valid years."""
    cite_threshold = _cfg["clustering"]["cite_threshold"]
    year_max = _cfg["periodization"]["year_max"]
    log.info("Selecting backbone (cited_by_count >= %d)...", cite_threshold)

    has_abs = works["abstract"].notna() & (works["abstract"].str.len() > 50)
    high_cited = works[has_abs & (works["cited_by_count"] >= cite_threshold)]
    backbone_dois = set(high_cited["doi_norm"])

    # Filter to papers with valid year
    backbone_dois = {
        d for d in backbone_dois
        if d in doi_meta and doi_meta[d]["year"] is not None
        and 1985 <= (doi_meta[d]["year"] or 0) <= year_max
    }

    log.info("Backbone papers (with valid year): %d", len(backbone_dois))
    return backbone_dois


# ============================================================
# Step 3: Assign lineages (3 bands)
# ============================================================

# Band scheme constants
N_COMMUNITIES = 3
BAND_NAMES = {0: "CDM / Kyoto heritage", 1: "Accountability pole", 2: "Efficiency pole"}
BAND_COLORS_RGB = {0: "#F4A261", 1: "#457B9D", 2: "#E63946"}
CDM_CLUSTER = 2


def assign_lineages(backbone_dois, doi_meta, doi_to_cluster):
    """Assign each backbone paper to one of three lineage bands."""
    # Load bimodality pole scores if available
    pole_path = os.path.join(TABLES_DIR, "tab_pole_papers.csv")
    use_bimodal = os.path.exists(pole_path)

    if use_bimodal:
        log.info("Loading bimodality axis scores from tab_pole_papers.csv...")
        pole_df = pd.read_csv(pole_path)
        pole_df["doi_norm"] = pole_df["doi"].apply(normalize_doi)
        doi_to_score = dict(zip(pole_df["doi_norm"], pole_df["axis_score"]))
        log.info("  Pole scores for %d papers", len(doi_to_score))
    else:
        log.warning("tab_pole_papers.csv not found. Run analyze_bimodality.py first.")
        log.warning("Falling back to 6-cluster KMeans lineages.")
        doi_to_score = {}

    lineage = {}
    for d in backbone_dois:
        cluster = doi_to_cluster.get(d)
        score = doi_to_score.get(d, 0)

        if use_bimodal:
            if cluster == CDM_CLUSTER:
                lineage[d] = 0  # CDM heritage
            elif score < 0:
                lineage[d] = 1  # Accountability
            else:
                lineage[d] = 2  # Efficiency
        else:
            lineage[d] = doi_to_cluster.get(d, 0)

    # Keep only papers with assigned lineages
    backbone_dois = {d for d in backbone_dois if d in lineage}
    band_counts = {
        b: sum(1 for d in backbone_dois if lineage[d] == b)
        for b in range(N_COMMUNITIES)
    }
    log.info("Final backbone: %d papers", len(backbone_dois))
    for b, name in BAND_NAMES.items():
        log.info("  Band %d (%s): %d papers", b, name, band_counts.get(b, 0))

    return backbone_dois, lineage


# ============================================================
# Step 4: Build citation DAG (internal links only)
# ============================================================

def build_citation_dag(backbone_dois, cit):
    """Build directed edges between backbone papers (cited → citing)."""
    log.info("Building citation DAG...")
    edges = set()
    for _, row in cit.iterrows():
        s = row["source_doi"]
        r = row["ref_doi"]
        if s in backbone_dois and r in backbone_dois:
            edges.add((r, s))  # cited → citing

    edges = list(edges)
    log.info("Internal citation edges: %d", len(edges))
    return edges


# ============================================================
# Step 5: Layout computation
# ============================================================

def compute_layout(backbone_dois, lineage, doi_meta):
    """Compute x (year-normalized) and y (lineage band + jitter) positions."""
    log.info("Computing layout...")

    year_min = min(doi_meta[d]["year"] for d in backbone_dois)
    year_max = max(doi_meta[d]["year"] for d in backbone_dois)

    # Order bands by median year (foundational at top)
    comm_median_years = {}
    for c in range(N_COMMUNITIES):
        years_c = [
            doi_meta[d]["year"] for d in backbone_dois
            if lineage.get(d) == c and doi_meta[d]["year"] is not None
        ]
        comm_median_years[c] = np.median(years_c) if years_c else 2020

    sorted_comms = sorted(comm_median_years.keys(), key=lambda c: comm_median_years[c])
    comm_to_band = {c: i for i, c in enumerate(sorted_comms)}

    band_height = 1.0 / max(N_COMMUNITIES, 1)

    # Count papers per (community, year) for jittering
    comm_year_counts = defaultdict(int)
    comm_year_assigned = defaultdict(int)

    for d in backbone_dois:
        c = lineage[d]
        yr = doi_meta[d]["year"]
        comm_year_counts[(c, int(yr))] += 1

    positions = {}
    for d in backbone_dois:
        c = lineage[d]
        yr = doi_meta[d]["year"]
        band = comm_to_band[c]

        x = (yr - year_min) / max(year_max - year_min, 1)

        band_center = (band + 0.5) * band_height
        n_in_slot = comm_year_counts[(c, int(yr))]
        idx_in_slot = comm_year_assigned[(c, int(yr))]
        comm_year_assigned[(c, int(yr))] += 1

        jitter_range = band_height * 0.35
        if n_in_slot > 1:
            jitter = -jitter_range + 2 * jitter_range * idx_in_slot / (n_in_slot - 1)
        else:
            jitter = 0
        y = band_center + jitter

        positions[d] = (x, y)

    return positions


# ============================================================
# Step 6: Save lineage table
# ============================================================

def save_lineage_table(backbone_dois, lineage, positions, doi_meta, output_path):
    """Write tab_lineages.csv with lineage assignments and layout positions."""
    rows = []
    for d in backbone_dois:
        meta = doi_meta.get(d, {})
        x, y = positions.get(d, (0, 0))
        rows.append({
            "doi": d,
            "lineage": lineage.get(d, -1),
            "lineage_name": BAND_NAMES.get(lineage.get(d, -1), "Unknown"),
            "peripheral": False,
            "first_author": meta.get("first_author", ""),
            "year": meta.get("year", ""),
            "cited_by_count": meta.get("cited_by_count", 0),
            "title": meta.get("title", "")[:100],
            "x": round(x, 6),
            "y": round(y, 6),
        })

    lineage_df = pd.DataFrame(rows).sort_values(
        ["lineage", "cited_by_count"], ascending=[True, False]
    )
    lineage_df.to_csv(output_path, index=False)
    log.info("Saved lineage table -> %s (%d papers)", output_path, len(lineage_df))


# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Genealogy lineage analysis")
    parser.add_argument("--output", default=os.path.join(TABLES_DIR, "tab_lineages.csv"),
                        help="Output CSV path")
    args = parser.parse_args()

    works, cit, doi_meta, doi_to_cluster = load_data()
    backbone_dois = select_backbone(works, doi_meta)
    backbone_dois, lineage = assign_lineages(backbone_dois, doi_meta, doi_to_cluster)
    build_citation_dag(backbone_dois, cit)  # logs edge count
    positions = compute_layout(backbone_dois, lineage, doi_meta)
    save_lineage_table(backbone_dois, lineage, positions, doi_meta, args.output)

    log.info("Done.")


if __name__ == "__main__":
    main()
