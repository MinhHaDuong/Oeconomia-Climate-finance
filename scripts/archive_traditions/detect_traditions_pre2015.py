"""Detect pre-2015 intellectual traditions via co-citation community detection.

This extends the pre-2007 analysis to the full "Before + Crystallisation" period
(year <= 2014, ~5,400 papers). With more data, we expect to see whether the three
traditions identified in the pre-2007 analysis persist or merge as climate finance
crystallizes.

Method:
  1. Build a co-citation network of the top 250 most-cited pre-2015 references
  2. Apply Louvain community detection at default and gamma=0.5 resolutions
  3. For each community: top papers, TF-IDF terms, community size

Usage:
    uv run python scripts/detect_traditions_pre2015.py
"""

import os
import sys
from collections import defaultdict

# archive_traditions/ is a subdirectory of scripts/ — need parent on path to import utils
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import community as community_louvain
import networkx as nx
import numpy as np
import pandas as pd
from scipy.sparse import lil_matrix
from sklearn.feature_extraction.text import TfidfVectorizer
from utils import BASE_DIR, CATALOGS_DIR, get_logger, normalize_doi

log = get_logger("detect_traditions_pre2015")

CUTOFF_YEAR = 2014
TOP_N = 250
MIN_COCIT = 2
OUTPUT_CSV = os.path.join(BASE_DIR, "content", "tables", "traditions_pre2015_communities.csv")

# ============================================================
# Step 1: Load and filter data
# ============================================================

log.info("=" * 70)
log.info(f"DETECTING PRE-{CUTOFF_YEAR + 1} INTELLECTUAL TRADITIONS")
log.info(f"(Co-citation network, top {TOP_N} most-cited references)")
log.info("=" * 70)

log.info("\n--- Loading data ---")
works = pd.read_csv(os.path.join(CATALOGS_DIR, "refined_works.csv"))
works["year"] = pd.to_numeric(works["year"], errors="coerce")
works["doi_norm"] = works["doi"].apply(normalize_doi)
works["cited_by_count"] = pd.to_numeric(works["cited_by_count"], errors="coerce").fillna(0)
log.info(f"Total works: {len(works)}")

pre_cutoff = works[works["year"] <= CUTOFF_YEAR].copy()
log.info(f"Works with year <= {CUTOFF_YEAR}: {len(pre_cutoff)}")

# Build DOI -> metadata lookup from refined_works
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
cit = pd.read_csv(os.path.join(CATALOGS_DIR, "citations.csv"), low_memory=False)
cit["source_doi"] = cit["source_doi"].apply(normalize_doi)
cit["ref_doi"] = cit["ref_doi"].apply(normalize_doi)
cit = cit[(cit["source_doi"] != "") & (cit["ref_doi"] != "")]
cit = cit[~cit["source_doi"].isin(["nan", "none", ""])]
cit = cit[~cit["ref_doi"].isin(["nan", "none", ""])]
log.info(f"Citation pairs with DOIs: {len(cit)}")

# Enrich doi_meta with ref metadata from citations for papers not in works
ref_meta_added = 0
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
        ref_meta_added += 1

log.info(f"Added metadata for {ref_meta_added} references not in refined_works")

# ============================================================
# Step 2: Coverage statistics
# ============================================================

log.info(f"\n--- Coverage statistics for year <= {CUTOFF_YEAR} ---")

pre_dois = set(pre_cutoff["doi_norm"]) - {"", "nan", "none"}
log.info(f"Pre-{CUTOFF_YEAR + 1} corpus DOIs: {len(pre_dois)}")

source_dois = set(cit["source_doi"])
pre_as_sources = pre_dois & source_dois
log.info(f"  Appearing as citation sources: {len(pre_as_sources)}")

ref_dois = set(cit["ref_doi"])
pre_as_refs = pre_dois & ref_dois
log.info(f"  Appearing as cited references: {len(pre_as_refs)}")

# All cited references with year <= CUTOFF_YEAR
cit["ref_year_num"] = pd.to_numeric(cit["ref_year"], errors="coerce")
pre_refs_all = set(cit[cit["ref_year_num"] <= CUTOFF_YEAR]["ref_doi"]) - {"", "nan", "none"}
log.info(f"\nAll cited references with year <= {CUTOFF_YEAR}: {len(pre_refs_all)}")

# Also count refs without year info that have DOIs in pre-cutoff works
pre_refs_in_works = pre_refs_all & pre_dois
log.info(f"  Of which in corpus: {len(pre_refs_in_works)}")

# ============================================================
# Step 3: Build co-citation network
# ============================================================

log.info("\n" + "=" * 70)
log.info(f"CO-CITATION NETWORK: top {TOP_N} most-cited pre-{CUTOFF_YEAR + 1} references")
log.info("(Two refs linked if co-cited by ANY paper in the corpus)")
log.info("=" * 70)

# Count how often each ref is cited
ref_counts = cit.groupby("ref_doi").size().sort_values(ascending=False)

# Filter to refs with year <= CUTOFF_YEAR
pre_ref_counts = ref_counts[ref_counts.index.isin(pre_refs_all)]
log.info(f"\nPre-{CUTOFF_YEAR + 1} references cited at least once: {len(pre_ref_counts)}")
log.info(f"  cited >= 3 times: {(pre_ref_counts >= 3).sum()}")
log.info(f"  cited >= 5 times: {(pre_ref_counts >= 5).sum()}")
log.info(f"  cited >= 10 times: {(pre_ref_counts >= 10).sum()}")

# Use top N most-cited
top_refs = pre_ref_counts.head(TOP_N).index.tolist()
top_set = set(top_refs)
ref_to_idx = {ref: i for i, ref in enumerate(top_refs)}

min_cit_in_top = pre_ref_counts.iloc[min(TOP_N - 1, len(pre_ref_counts) - 1)]
log.info(f"\nUsing top {TOP_N} most-cited pre-{CUTOFF_YEAR + 1} references")
log.info(f"Min citations in top set: {min_cit_in_top}")

# Build co-citation matrix
log.info("Building co-citation matrix...")
source_groups = cit.groupby("source_doi")["ref_doi"].apply(list)

cocit_matrix = lil_matrix((TOP_N, TOP_N), dtype=np.float64)
for ref_list in source_groups.values:
    refs_in_top = [r for r in ref_list if r in top_set]
    if len(refs_in_top) < 2:
        continue
    for i in range(len(refs_in_top)):
        for j in range(i + 1, len(refs_in_top)):
            a = ref_to_idx[refs_in_top[i]]
            b = ref_to_idx[refs_in_top[j]]
            cocit_matrix[a, b] += 1
            cocit_matrix[b, a] += 1

cocit_dense = cocit_matrix.toarray()
n_pairs = np.count_nonzero(cocit_dense) // 2
log.info(f"Non-zero co-citation pairs: {n_pairs}")

# Build graph
G = nx.Graph()
for i, doi in enumerate(top_refs):
    meta = doi_meta.get(doi, {})
    author = str(meta.get("first_author", "")).split(",")[0].split(";")[0].strip()
    year = meta.get("year", "")
    if year and not pd.isna(year):
        year = int(year)
    label = f"{author} ({year})" if author and year else doi[:30]
    G.add_node(doi, label=label, citations=int(ref_counts.get(doi, 0)))

for i in range(TOP_N):
    for j in range(i + 1, TOP_N):
        w = cocit_dense[i, j]
        if w >= MIN_COCIT:
            G.add_edge(top_refs[i], top_refs[j], weight=w)

isolates = list(nx.isolates(G))
G.remove_nodes_from(isolates)
log.info(f"Network: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
log.info(f"Removed {len(isolates)} isolates")


# ============================================================
# Helper: characterize communities
# ============================================================

def characterize_communities(partition, graph, doi_meta, ref_counts, label=""):
    """Print detailed community profiles with top papers and TF-IDF terms."""
    comm_papers = defaultdict(list)
    for doi, comm in partition.items():
        comm_papers[comm].append(doi)

    log.info(f"\n{'=' * 60}")
    log.info(f"COMMUNITY PROFILES {label}")
    log.info(f"{'=' * 60}")

    results = []  # For CSV output

    for c in sorted(comm_papers.keys()):
        papers = comm_papers[c]
        # Sort by citation count within corpus
        papers_sorted = sorted(
            papers,
            key=lambda d: ref_counts.get(d, 0),
            reverse=True,
        )

        log.info(f"\n--- Community {c} ({len(papers)} papers) ---")

        # Top papers
        log.info("  Top papers:")
        for d in papers_sorted[:12]:
            meta = doi_meta.get(d, {})
            author = str(meta.get("first_author", "?"))
            if author in ("nan", "None", ""):
                author = "?"
            year = meta.get("year", "?")
            if year and not pd.isna(year):
                year = int(year)
            title = str(meta.get("title", ""))[:80]
            if title in ("nan", "None", ""):
                title = f"[{d}]"
            rc = ref_counts.get(d, 0)
            log.info(f"    [{rc:>3}x cited] {author} ({year}) {title}")

        # TF-IDF terms
        texts = []
        for d in papers:
            meta = doi_meta.get(d, {})
            ab = meta.get("abstract", "")
            title = meta.get("title", "")
            text = ""
            if ab and len(str(ab)) > 30 and str(ab) != "nan":
                text = str(ab)
            elif title and len(str(title)) > 5 and str(title) != "nan":
                text = str(title)
            if text:
                texts.append(text)

        top_terms_str = ""
        if len(texts) >= 3:
            try:
                tfidf = TfidfVectorizer(
                    max_features=500, stop_words="english",
                    ngram_range=(1, 2), min_df=2, max_df=0.8,
                )
                X = tfidf.fit_transform(texts)
                mean_tfidf = np.asarray(X.mean(axis=0)).flatten()
                top_idx = mean_tfidf.argsort()[::-1][:20]
                terms = tfidf.get_feature_names_out()
                top_terms = [terms[i] for i in top_idx]
                top_terms_str = ", ".join(top_terms)
                log.info(f"  Top TF-IDF terms ({len(texts)} texts): {top_terms_str}")
            except Exception as e:
                log.info(f"  (TF-IDF failed: {e})")
        else:
            log.info(f"  (Only {len(texts)} texts available — skipping TF-IDF)")

        # Collect for CSV
        for d in papers:
            meta = doi_meta.get(d, {})
            results.append({
                "community": c,
                "community_size": len(papers),
                "doi": d,
                "first_author": meta.get("first_author", ""),
                "year": meta.get("year", ""),
                "title": meta.get("title", ""),
                "corpus_citations": ref_counts.get(d, 0),
                "cited_by_count": meta.get("cited_by_count", 0),
                "top_tfidf_terms": top_terms_str,
            })

    return comm_papers, results


# ============================================================
# Step 4: Louvain at default resolution
# ============================================================

log.info("\n" + "=" * 70)
log.info("DEFAULT RESOLUTION (gamma=1.0)")
log.info("=" * 70)

partition_default = community_louvain.best_partition(G, weight="weight", random_state=42)
n_comm = len(set(partition_default.values()))
sizes = defaultdict(int)
for v in partition_default.values():
    sizes[v] += 1
size_str = ", ".join(f"{s}" for s in sorted(sizes.values(), reverse=True))
log.info(f"Communities detected: {n_comm} (sizes: {size_str})")

comm_papers_default, results_default = characterize_communities(
    partition_default, G, doi_meta, ref_counts,
    label=f"(Co-citation, top {TOP_N} pre-{CUTOFF_YEAR + 1} refs, gamma=1.0)",
)


# ============================================================
# Step 5: Resolution sweep
# ============================================================

log.info("\n" + "=" * 70)
log.info("RESOLUTION SWEEP")
log.info("=" * 70)

for gamma in [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.2, 1.5, 2.0]:
    part = community_louvain.best_partition(
        G, weight="weight", resolution=gamma, random_state=42
    )
    n_c = len(set(part.values()))
    sizes = defaultdict(int)
    for v in part.values():
        sizes[v] += 1
    size_str = ", ".join(f"{s}" for s in sorted(sizes.values(), reverse=True))
    log.info(f"  gamma={gamma:.1f}: {n_c} communities (sizes: {size_str})")


# ============================================================
# Step 6: Louvain at gamma=0.5 (finer resolution)
# ============================================================

log.info("\n" + "=" * 70)
log.info("FINER RESOLUTION (gamma=0.5)")
log.info("=" * 70)

partition_fine = community_louvain.best_partition(
    G, weight="weight", resolution=0.5, random_state=42
)
n_comm_fine = len(set(partition_fine.values()))
sizes_fine = defaultdict(int)
for v in partition_fine.values():
    sizes_fine[v] += 1
size_str_fine = ", ".join(f"{s}" for s in sorted(sizes_fine.values(), reverse=True))
log.info(f"Communities detected: {n_comm_fine} (sizes: {size_str_fine})")

comm_papers_fine, results_fine = characterize_communities(
    partition_fine, G, doi_meta, ref_counts,
    label=f"(Co-citation, top {TOP_N} pre-{CUTOFF_YEAR + 1} refs, gamma=0.5)",
)


# ============================================================
# Step 7: Save community assignments to CSV (use default resolution)
# ============================================================

log.info("\n--- Saving community assignments ---")
os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)

df_out = pd.DataFrame(results_default)
df_out = df_out.sort_values(["community", "corpus_citations"], ascending=[True, False])
df_out.to_csv(OUTPUT_CSV, index=False)
log.info(f"Saved {len(df_out)} rows to {OUTPUT_CSV}")


# ============================================================
# Summary
# ============================================================

log.info("\n" + "=" * 70)
log.info("SUMMARY")
log.info("=" * 70)
log.info(f"""
Analysis period: year <= {CUTOFF_YEAR} ("Before" + "Crystallisation")
Corpus papers in period: {len(pre_cutoff)}
Co-citation network: top {TOP_N} most-cited pre-{CUTOFF_YEAR + 1} references
Network size: {G.number_of_nodes()} connected nodes, {G.number_of_edges()} edges

Default resolution (gamma=1.0): {len(set(partition_default.values()))} communities
Fine resolution (gamma=0.5): {len(set(partition_fine.values()))} communities

Community assignments saved to: {OUTPUT_CSV}

Compare with pre-2007 analysis (5 communities at gamma=0.5):
  - Environmental economics (IAMs, corporate finance, econometrics)
  - Burden-sharing (international political economy, adaptation/vulnerability)
  - Development/aid/CDM (aid flows, CDM projects, international agreements)

Key question: Do these traditions persist, merge, or split with the
additional 2007-2014 data from the crystallisation period?
""")

log.info("Done.")
