"""Cross-reference pre-2007 co-citation communities with KMeans semantic clusters.

Compares two independent categorizations of the same papers:
  - KMeans (k=6) on sentence embeddings (full corpus, same as analyze_alluvial.py)
  - Louvain co-citation communities (gamma=0.5, top-150 pre-2007 refs,
    same as detect_traditions_v2.py Approach E)

Produces a contingency table (community x cluster) for overlapping DOIs.

Usage:
    uv run python scripts/cross_ref_communities_clusters.py
"""

import os
import sys
from collections import defaultdict

import numpy as np
import pandas as pd
from scipy.sparse import lil_matrix
from sklearn.cluster import KMeans

# Add scripts dir to path for utils
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils import CATALOGS_DIR, load_cluster_labels, normalize_doi

CLUSTER_LABELS = load_cluster_labels()

# ============================================================
# Step 1: Load data and embeddings, run KMeans (k=6)
# ============================================================

print("=" * 70)
print("CROSS-REFERENCING CO-CITATION COMMUNITIES vs KMEANS CLUSTERS")
print("=" * 70)

print("\n--- Step 1: Load data and run KMeans ---")
works = pd.read_csv(os.path.join(CATALOGS_DIR, "refined_works.csv"))
works["year"] = pd.to_numeric(works["year"], errors="coerce")

# Filter: must have abstract, year in range (matches embedding generation)
has_abstract = works["abstract"].notna() & (works["abstract"].str.len() > 50)
in_range = (works["year"] >= 1990) & (works["year"] <= 2025)
df = works[has_abstract & in_range].copy().reset_index(drop=True)
print(f"Works with abstracts (1990-2025): {len(df)}")

embeddings_path = os.path.join(CATALOGS_DIR, "embeddings.npz")
embeddings = np.load(embeddings_path, allow_pickle=True)["vectors"]
if len(embeddings) != len(df):
    raise RuntimeError(
        f"Embedding cache size mismatch ({len(embeddings)} vs {len(df)}). "
        "Re-run analyze_embeddings.py first."
    )
print(f"Embedding shape: {embeddings.shape}")

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

print(f"Papers with KMeans cluster assignments: {len(doi_to_cluster)}")

# ============================================================
# Step 2: Build co-citation communities (same as detect_traditions_v2.py)
# ============================================================

print("\n--- Step 2: Build co-citation communities ---")

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
print("Loading citations...")
cit = pd.read_csv(os.path.join(CATALOGS_DIR, "citations.csv"), low_memory=False)
cit["source_doi"] = cit["source_doi"].apply(normalize_doi)
cit["ref_doi"] = cit["ref_doi"].apply(normalize_doi)
cit = cit[(cit["source_doi"] != "") & (cit["ref_doi"] != "")]
cit = cit[~cit["source_doi"].isin(["nan", "none", ""])]
cit = cit[~cit["ref_doi"].isin(["nan", "none", ""])]
print(f"Citation pairs with DOIs: {len(cit)}")

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

print(f"Using top {TOP_N} most-cited pre-2007 references")

# Build co-citation matrix
print("Building co-citation matrix...")
source_groups = cit.groupby("source_doi")["ref_doi"].apply(list)

cocit_matrix = lil_matrix((TOP_N, TOP_N), dtype=np.float64)
for source_doi, ref_list in source_groups.items():
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
print(f"Co-citation network: {G_cocit.number_of_nodes()} nodes, {G_cocit.number_of_edges()} edges")
print(f"Removed {len(isolates)} isolates")

# Louvain community detection with gamma=0.5 (Approach E)
partition = community_louvain.best_partition(
    G_cocit, weight="weight", resolution=0.5, random_state=42
)
n_comm = len(set(partition.values()))
print(f"Co-citation communities detected (gamma=0.5): {n_comm}")

# ============================================================
# Step 3: Cross-tabulation
# ============================================================

print("\n--- Step 3: Cross-tabulation ---")

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

print(f"\nCo-citation community papers: {n_total}")
print(f"  With KMeans cluster (have embeddings): {n_matched}")
print(f"  Without KMeans cluster (no embedding): {n_unmatched}")

# ============================================================
# Step 4: Direct contingency table (community node DOIs that have embeddings)
# ============================================================

print("\n" + "=" * 70)
print("PART A: DIRECT MATCH — Community nodes that also have embeddings")
print("=" * 70)

matched = cross_df[cross_df["cluster"].notna()].copy()
if len(matched) > 0:
    matched["cluster"] = matched["cluster"].astype(int)

print(f"\nDirect overlap: {len(matched)} of {n_total} community papers have embeddings")
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
    print(f"\n{contingency_direct.to_string()}")
else:
    print("No direct overlap found.")

print(f"""
NOTE: The direct overlap is tiny ({len(matched)}/{n_total}) because the co-citation
communities are built from top-150 most-cited pre-2007 *references* — foundational
papers in economics, political science, etc. that are mostly NOT in the embedding
corpus (which covers climate-finance papers with abstracts).
""")

# ============================================================
# Step 5: INDIRECT mapping — which corpus papers cite each community?
# ============================================================

print("=" * 70)
print("PART B: INDIRECT MATCH — Corpus papers that CITE community references")
print("(For each community, find all citing papers with KMeans clusters)")
print("=" * 70)

# Build: community DOI -> community ID
doi_to_community = {}
for doi, comm_id in partition.items():
    doi_to_community[doi] = comm_id

# For each citation, if ref_doi is in a community, record (source_doi, community)
print("\nMapping citations to communities...")
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
print(f"Citation links from corpus papers (with clusters) to community refs: {len(citer_df)}")

# Deduplicate: count each citing paper once per community (even if it cites
# multiple refs in the same community)
citer_unique = citer_df.drop_duplicates(subset=["source_doi", "community"])
print(f"Unique (citer, community) pairs: {len(citer_unique)}")

# Count unique citers
n_unique_citers = citer_unique["source_doi"].nunique()
print(f"Unique corpus papers citing at least one community ref: {n_unique_citers}")

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

    print(f"\nCONTINGENCY TABLE (unique citers per community x cluster):\n")
    print(contingency_indirect.to_string())

    # Row-normalized percentage
    print("\n" + "=" * 70)
    print("ROW-NORMALIZED (%): Cluster distribution of papers citing each community")
    print("=" * 70)

    body = contingency_indirect.iloc[:-1, :-1]
    row_totals = contingency_indirect.iloc[:-1, -1]
    pct = body.div(row_totals, axis=0) * 100
    pct = pct.round(1)
    pct["N citers"] = row_totals.values

    print(f"\n{pct.to_string()}")

    # Dominant cluster per community
    print("\n--- Dominant KMeans cluster per co-citation community (indirect) ---")
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
        print(line)

    # Cramer's V for association strength
    from scipy.stats import chi2_contingency

    ct_values = pd.crosstab(citer_unique["community"], citer_unique["cluster"])
    if ct_values.shape[0] > 1 and ct_values.shape[1] > 1:
        chi2, p, dof, expected = chi2_contingency(ct_values)
        n = ct_values.sum().sum()
        k = min(ct_values.shape) - 1
        cramers_v = np.sqrt(chi2 / (n * k)) if k > 0 and n > 0 else 0
        print(f"\n  Cramer's V = {cramers_v:.3f}  (chi2={chi2:.1f}, p={p:.2e}, dof={dof})")
        if cramers_v > 0.5:
            print("  => Strong association between communities and clusters.")
        elif cramers_v > 0.3:
            print("  => Moderate association: partial alignment.")
        elif cramers_v > 0.15:
            print("  => Weak-to-moderate association: some structure shared.")
        else:
            print("  => Weak association: largely independent categorizations.")

# ============================================================
# Step 6: Community profiles (top cited refs with labels)
# ============================================================

print("\n" + "=" * 70)
print("COMMUNITY PROFILES: Top 8 references per community")
print("=" * 70)

comm_dois = defaultdict(list)
for doi, comm_id in partition.items():
    comm_dois[comm_id].append(doi)

for comm_id in sorted(comm_dois.keys()):
    papers = comm_dois[comm_id]
    papers_sorted = sorted(papers, key=lambda d: ref_counts.get(d, 0), reverse=True)
    n_citers = len(citer_unique[citer_unique["community"] == comm_id]) if len(citer_unique) > 0 else 0
    print(f"\n--- Community {comm_id} ({len(papers)} refs, {n_citers} corpus citers) ---")
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
        print(f"    [{rc:>3}x cited] {author} ({year}) {title}")

# ============================================================
# Step 7: Summary interpretation
# ============================================================

print("\n" + "=" * 70)
print("SUMMARY INTERPRETATION")
print("=" * 70)

print(f"""
Cross-referencing method:
  - Co-citation communities: Louvain on co-citation network of top-{TOP_N}
    most-cited pre-2007 references (gamma=0.5, {n_comm} communities)
  - KMeans clusters: k=6 on sentence embeddings of {len(df)} papers
    with abstracts (1990-2025)

Direct overlap: {len(matched)}/{n_total} community papers have embeddings (most
foundational references lack abstracts in the corpus).

Indirect mapping: {n_unique_citers} corpus papers (with KMeans clusters) cite at
least one community reference, yielding {len(citer_unique)} (citer, community) pairs.

The indirect contingency table above shows how the semantic profile of papers
*citing into* each co-citation community distributes across KMeans clusters.

- If a community is cited predominantly by one cluster, citation lineage and
  semantic content align: that community is an intellectual ancestor of that cluster.
- If a community is cited across many clusters, it represents a cross-cutting
  intellectual foundation (e.g., general econometric methods).
""")

print("Done.")
