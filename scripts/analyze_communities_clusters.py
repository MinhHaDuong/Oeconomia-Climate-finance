"""Cross-reference pre-2007 co-citation communities with KMeans semantic clusters.

Compares two independent categorizations of the same papers:
  - KMeans (k=6) on sentence embeddings (full corpus, same as analyze_alluvial.py)
  - Louvain co-citation communities (gamma=0.5, top-150 pre-2007 refs,
    same as detect_traditions_v2.py Approach E)

Produces a contingency table (community x cluster) for overlapping DOIs.

Usage:
    uv run python scripts/analyze_communities_clusters.py
"""

import os
from collections import defaultdict

import numpy as np
import pandas as pd
from scipy.sparse import lil_matrix
from sklearn.cluster import KMeans
from utils import (
    CATALOGS_DIR,
    get_logger,
    load_analysis_config,
    load_cluster_labels,
    load_refined_citations,
    load_refined_embeddings,
    normalize_doi,
)

log = get_logger("analyze_communities_clusters")

CLUSTER_LABELS = load_cluster_labels()

# ============================================================
# Step 1: Load data and embeddings, run KMeans (k=6)
# ============================================================

log.info("=" * 70)
log.info("CROSS-REFERENCING CO-CITATION COMMUNITIES vs KMEANS CLUSTERS")
log.info("=" * 70)

log.info("--- Step 1: Load data and run KMeans ---")
works = pd.read_csv(os.path.join(CATALOGS_DIR, "refined_works.csv"))
works["year"] = pd.to_numeric(works["year"], errors="coerce")

# Filter: must have abstract, year in range (matches embedding generation)
_cfg = load_analysis_config()
_year_min = _cfg["periodization"]["year_min"]
_year_max = _cfg["periodization"]["year_max"]
has_abstract = works["abstract"].notna() & (works["abstract"].str.len() > 50)
in_range = (works["year"] >= _year_min) & (works["year"] <= _year_max)
df = works[has_abstract & in_range].copy().reset_index(drop=True)
log.info("Works with abstracts (%d-%d): %d", _year_min, _year_max, len(df))

embeddings = load_refined_embeddings()
if len(embeddings) != len(df):
    raise RuntimeError(
        f"Embedding cache size mismatch ({len(embeddings)} vs {len(df)}). "
        "Re-run analyze_embeddings.py first."
    )
log.info("Embedding shape: %s", embeddings.shape)

# KMeans k=6, same parameters as analyze_alluvial.py
kmeans = KMeans(n_clusters=6, random_state=42, n_init=20)
df["cluster"] = kmeans.fit_predict(embeddings)
df["doi_norm"] = df["doi"].apply(normalize_doi)

# Build DOI -> cluster lookup
doi_to_cluster = {}
for _, row in df.iterrows():
    d = row["doi_norm"]
    if d and d not in ("", "nan", "none"):
        doi_to_cluster[d] = row["cluster"]

log.info("Papers with KMeans cluster assignments: %d", len(doi_to_cluster))

# ============================================================
# Step 2: Build co-citation communities (same as detect_traditions_v2.py)
# ============================================================

log.info("--- Step 2: Build co-citation communities ---")

# Build DOI -> metadata lookup (needed for year info on references)
works["doi_norm"] = works["doi"].apply(normalize_doi)
works["cited_by_count"] = pd.to_numeric(works["cited_by_count"], errors="coerce").fillna(0)

doi_meta = {}
for _, row in works.iterrows():
    d = row["doi_norm"]
    if d and d not in ("", "nan", "none"):
        doi_meta[d] = {
            "title": str(row.get("title", "") or ""),
            "first_author": str(row.get("first_author", "") or ""),
            "year": row["year"] if pd.notna(row["year"]) else None,
            "cited_by_count": row["cited_by_count"],
        }

# Load citations
log.info("Loading citations...")
cit = load_refined_citations()
cit["source_doi"] = cit["source_doi"].apply(normalize_doi)
cit["ref_doi"] = cit["ref_doi"].apply(normalize_doi)
cit = cit[(cit["source_doi"] != "") & (cit["ref_doi"] != "")]
cit = cit[~cit["source_doi"].isin(["nan", "none", ""])]
cit = cit[~cit["ref_doi"].isin(["nan", "none", ""])]
log.info("Citation pairs with DOIs: %d", len(cit))

# Add ref metadata from citations for papers not in works
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
        }

# Identify pre-2007 references
cit["ref_year_num"] = pd.to_numeric(cit["ref_year"], errors="coerce")
pre2007_refs_all = set(cit[cit["ref_year_num"] <= 2006]["ref_doi"]) - {"", "nan", "none"}

# Top 150 most-cited pre-2007 references
ref_counts = cit.groupby("ref_doi").size().sort_values(ascending=False)
pre2007_ref_counts = ref_counts[ref_counts.index.isin(pre2007_refs_all)]

TOP_N = 150
top_pre2007_refs = pre2007_ref_counts.head(TOP_N).index.tolist()
top_set = set(top_pre2007_refs)
ref_to_idx = {ref: i for i, ref in enumerate(top_pre2007_refs)}

log.info("Using top %d most-cited pre-2007 references", TOP_N)

# Build co-citation matrix
log.info("Building co-citation matrix...")
source_groups = cit.groupby("source_doi")["ref_doi"].apply(list)

cocit_matrix = lil_matrix((TOP_N, TOP_N), dtype=np.float64)
for ref_list in source_groups.values():
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

# Build graph
import community as community_louvain
import networkx as nx

G_cocit = nx.Graph()
for i, doi in enumerate(top_pre2007_refs):
    G_cocit.add_node(doi, citations=int(ref_counts.get(doi, 0)))

MIN_COCIT = 2
for i in range(TOP_N):
    for j in range(i + 1, TOP_N):
        w = cocit_dense[i, j]
        if w >= MIN_COCIT:
            G_cocit.add_edge(top_pre2007_refs[i], top_pre2007_refs[j], weight=w)

isolates = list(nx.isolates(G_cocit))
G_cocit.remove_nodes_from(isolates)
log.info("Co-citation network: %d nodes, %d edges", G_cocit.number_of_nodes(), G_cocit.number_of_edges())
log.info("Removed %d isolates", len(isolates))

# Louvain community detection with gamma=0.5 (Approach E)
partition = community_louvain.best_partition(
    G_cocit, weight="weight", resolution=0.5, random_state=42
)
n_comm = len(set(partition.values()))
log.info("Co-citation communities detected (gamma=0.5): %d", n_comm)

# ============================================================
# Step 3: Cross-tabulation
# ============================================================

log.info("--- Step 3: Cross-tabulation ---")

# For each community paper, find its KMeans cluster (if it has one)
records = []
for doi, comm_id in partition.items():
    meta = doi_meta.get(doi, {})
    author = str(meta.get("first_author", "?"))
    if author in ("nan", "None", ""):
        author = "?"
    year = meta.get("year", "?")
    if year and not pd.isna(year):
        year = int(year)
    title = str(meta.get("title", ""))[:60]
    if title in ("nan", "None", ""):
        title = f"[{doi}]"

    cluster = doi_to_cluster.get(doi, None)
    records.append({
        "doi": doi,
        "community": comm_id,
        "cluster": cluster,
        "cluster_label": CLUSTER_LABELS.get(cluster, "N/A (no embedding)"),
        "author": author,
        "year": year,
        "title": title,
    })

cross_df = pd.DataFrame(records)
n_total = len(cross_df)
n_matched = cross_df["cluster"].notna().sum()
n_unmatched = n_total - n_matched

log.info("Co-citation community papers: %d", n_total)
log.info("  With KMeans cluster (have embeddings): %d", n_matched)
log.info("  Without KMeans cluster (no embedding): %d", n_unmatched)

# ============================================================
# Step 4: Direct contingency table (community node DOIs that have embeddings)
# ============================================================

log.info("=" * 70)
log.info("PART A: DIRECT MATCH — Community nodes that also have embeddings")
log.info("=" * 70)

matched = cross_df[cross_df["cluster"].notna()].copy()
if len(matched) > 0:
    matched["cluster"] = matched["cluster"].astype(int)

log.info("Direct overlap: %d of %d community papers have embeddings", len(matched), n_total)
if len(matched) > 0:
    contingency_direct = pd.crosstab(
        matched["community"], matched["cluster"],
        margins=True, margins_name="Total",
    )
    col_rename = {c: f"{c}: {CLUSTER_LABELS[c]}" for c in range(6) if c in contingency_direct.columns}
    col_rename["Total"] = "Total"
    contingency_direct = contingency_direct.rename(columns=col_rename)
    contingency_direct.index = [f"Comm {i}" if i != "Total" else "Total"
                                for i in contingency_direct.index]
    log.info("\n%s", contingency_direct.to_string())
else:
    log.info("No direct overlap found.")

log.info("NOTE: The direct overlap is tiny (%d/%d) because the co-citation\n"
         "communities are built from top-150 most-cited pre-2007 *references* — foundational\n"
         "papers in economics, political science, etc. that are mostly NOT in the embedding\n"
         "corpus (which covers climate-finance papers with abstracts).",
         len(matched), n_total)

# ============================================================
# Step 5: INDIRECT mapping — which corpus papers cite each community?
# ============================================================

log.info("=" * 70)
log.info("PART B: INDIRECT MATCH — Corpus papers that CITE community references")
log.info("(For each community, find all citing papers with KMeans clusters)")
log.info("=" * 70)

# Build: community DOI -> community ID
doi_to_community = {}
for doi, comm_id in partition.items():
    doi_to_community[doi] = comm_id

# For each citation, if ref_doi is in a community, record (source_doi, community)
log.info("Mapping citations to communities...")
citer_records = []
for _, row in cit.iterrows():
    ref = row["ref_doi"]
    src = row["source_doi"]
    if ref in doi_to_community and src in doi_to_cluster:
        citer_records.append({
            "source_doi": src,
            "community": doi_to_community[ref],
            "cluster": doi_to_cluster[src],
        })

citer_df = pd.DataFrame(citer_records)
log.info("Citation links from corpus papers (with clusters) to community refs: %d", len(citer_df))

# Deduplicate: count each citing paper once per community (even if it cites
# multiple refs in the same community)
citer_unique = citer_df.drop_duplicates(subset=["source_doi", "community"])
log.info("Unique (citer, community) pairs: %d", len(citer_unique))

# Count unique citers
n_unique_citers = citer_unique["source_doi"].nunique()
log.info("Unique corpus papers citing at least one community ref: %d", n_unique_citers)

# Contingency table: community x cluster (counting unique citers)
if len(citer_unique) > 0:
    contingency_indirect = pd.crosstab(
        citer_unique["community"],
        citer_unique["cluster"],
        margins=True,
        margins_name="Total",
    )

    # Rename columns
    col_rename = {c: f"{c}: {CLUSTER_LABELS[c]}" for c in range(6)
                  if c in contingency_indirect.columns}
    col_rename["Total"] = "Total"
    contingency_indirect = contingency_indirect.rename(columns=col_rename)
    contingency_indirect.index = [f"Comm {i}" if i != "Total" else "Total"
                                  for i in contingency_indirect.index]

    log.info("CONTINGENCY TABLE (unique citers per community x cluster):\n%s",
             contingency_indirect.to_string())

    # Row-normalized percentage
    log.info("=" * 70)
    log.info("ROW-NORMALIZED (%%): Cluster distribution of papers citing each community")
    log.info("=" * 70)

    body = contingency_indirect.iloc[:-1, :-1]
    row_totals = contingency_indirect.iloc[:-1, -1]
    pct = body.div(row_totals, axis=0) * 100
    pct = pct.round(1)
    pct["N citers"] = row_totals.values

    log.info("\n%s", pct.to_string())

    # Dominant cluster per community
    log.info("--- Dominant KMeans cluster per co-citation community (indirect) ---")
    for comm_id in sorted(citer_unique["community"].unique()):
        comm_data = citer_unique[citer_unique["community"] == comm_id]
        cluster_counts = comm_data["cluster"].value_counts()
        dominant = cluster_counts.index[0]
        dominant_pct = cluster_counts.iloc[0] / len(comm_data) * 100
        second = cluster_counts.index[1] if len(cluster_counts) > 1 else None
        second_pct = cluster_counts.iloc[1] / len(comm_data) * 100 if second is not None else 0
        line = (f"  Community {comm_id}: dominant = Cluster {int(dominant)} "
                f"({CLUSTER_LABELS[int(dominant)]}) at {dominant_pct:.0f}%")
        if second is not None:
            line += (f", 2nd = Cluster {int(second)} "
                     f"({CLUSTER_LABELS[int(second)]}) at {second_pct:.0f}%")
        line += f"  [N={len(comm_data)}]"
        log.info("%s", line)

    # Cramer's V for association strength
    from scipy.stats import chi2_contingency

    ct_values = pd.crosstab(citer_unique["community"], citer_unique["cluster"])
    if ct_values.shape[0] > 1 and ct_values.shape[1] > 1:
        chi2, p, dof, expected = chi2_contingency(ct_values)
        n = ct_values.sum().sum()
        k = min(ct_values.shape) - 1
        cramers_v = np.sqrt(chi2 / (n * k)) if k > 0 and n > 0 else 0
        log.info("  Cramer's V = %.3f  (chi2=%.1f, p=%.2e, dof=%d)", cramers_v, chi2, p, dof)
        if cramers_v > 0.5:
            log.info("  => Strong association between communities and clusters.")
        elif cramers_v > 0.3:
            log.info("  => Moderate association: partial alignment.")
        elif cramers_v > 0.15:
            log.info("  => Weak-to-moderate association: some structure shared.")
        else:
            log.info("  => Weak association: largely independent categorizations.")

# ============================================================
# Step 6: Community profiles (top cited refs with labels)
# ============================================================

log.info("=" * 70)
log.info("COMMUNITY PROFILES: Top 8 references per community")
log.info("=" * 70)

comm_dois = defaultdict(list)
for doi, comm_id in partition.items():
    comm_dois[comm_id].append(doi)

for comm_id in sorted(comm_dois.keys()):
    papers = comm_dois[comm_id]
    papers_sorted = sorted(papers, key=lambda d: ref_counts.get(d, 0), reverse=True)
    n_citers = len(citer_unique[citer_unique["community"] == comm_id]) if len(citer_unique) > 0 else 0
    log.info("--- Community %d (%d refs, %d corpus citers) ---", comm_id, len(papers), n_citers)
    for d in papers_sorted[:8]:
        meta = doi_meta.get(d, {})
        author = str(meta.get("first_author", "?"))
        if author in ("nan", "None", ""):
            author = "?"
        year = meta.get("year", "?")
        if year and not pd.isna(year):
            year = int(year)
        title = str(meta.get("title", ""))[:65]
        if title in ("nan", "None", ""):
            title = f"[{d}]"
        rc = ref_counts.get(d, 0)
        log.info("    [%3dx cited] %s (%s) %s", rc, author, year, title)

# ============================================================
# Step 7: Summary interpretation
# ============================================================

log.info("=" * 70)
log.info("SUMMARY INTERPRETATION")
log.info("=" * 70)

log.info("Cross-referencing method:\n"
         "  - Co-citation communities: Louvain on co-citation network of top-%d\n"
         "    most-cited pre-2007 references (gamma=0.5, %d communities)\n"
         "  - KMeans clusters: k=6 on sentence embeddings of %d papers\n"
         "    with abstracts (%d-%d)\n"
         "\n"
         "Direct overlap: %d/%d community papers have embeddings (most\n"
         "foundational references lack abstracts in the corpus).\n"
         "\n"
         "Indirect mapping: %d corpus papers (with KMeans clusters) cite at\n"
         "least one community reference, yielding %d (citer, community) pairs.\n"
         "\n"
         "The indirect contingency table above shows how the semantic profile of papers\n"
         "*citing into* each co-citation community distributes across KMeans clusters.\n"
         "\n"
         "- If a community is cited predominantly by one cluster, citation lineage and\n"
         "  semantic content align: that community is an intellectual ancestor of that cluster.\n"
         "- If a community is cited across many clusters, it represents a cross-cutting\n"
         "  intellectual foundation (e.g., general econometric methods).",
         TOP_N, n_comm, len(df), _year_min, _year_max, len(matched), n_total,
         n_unique_citers, len(citer_unique))

log.info("Done.")
