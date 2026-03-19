"""Detect pre-2020 intellectual traditions via co-citation community detection.

Extends the pre-2007 analysis to a larger sample (year <= 2019, ~13,000+ papers)
to see how community structure evolves with the established-field period included.

Methodology:
  1. Identify the top 250 most-cited pre-2020 references in citations.csv
  2. Build co-citation network (two refs linked if co-cited by the same source)
  3. Apply Louvain community detection at default and gamma=0.5 resolutions
  4. Characterize each community: top papers, TF-IDF terms, size

Usage:
    uv run python scripts/detect_traditions_pre2020.py
"""

import os
from collections import defaultdict

import community as community_louvain
import networkx as nx
import numpy as np
import pandas as pd
from scipy.sparse import lil_matrix
from sklearn.feature_extraction.text import TfidfVectorizer

# Add scripts dir to path for utils
from utils import BASE_DIR, CATALOGS_DIR, normalize_doi

# ============================================================
# Step 1: Load and filter data to pre-2020
# ============================================================

YEAR_CUTOFF = 2019
TOP_N = 250
MIN_COCIT = 3  # minimum co-citation count for an edge

print("=" * 70)
print(f"DETECTING PRE-{YEAR_CUTOFF + 1} INTELLECTUAL TRADITIONS")
print("=" * 70)

print("\n--- Loading data ---")
works = pd.read_csv(os.path.join(CATALOGS_DIR, "refined_works.csv"))
works["year"] = pd.to_numeric(works["year"], errors="coerce")
works["doi_norm"] = works["doi"].apply(normalize_doi)
works["cited_by_count"] = pd.to_numeric(
    works["cited_by_count"], errors="coerce"
).fillna(0)
print(f"Total works: {len(works)}")

# Pre-2020 works
pre2020 = works[works["year"] <= YEAR_CUTOFF].copy()
print(f"Works with year <= {YEAR_CUTOFF}: {len(pre2020)}")

# Build DOI -> metadata lookup (vectorized, no iterrows on 22K rows)
doi_meta = {}
valid = works["doi_norm"].notna() & ~works["doi_norm"].isin(["", "nan", "none"])
for row in works.loc[valid].itertuples(index=False):
    doi_meta[row.doi_norm] = {
        "title": str(getattr(row, "title", "") or ""),
        "first_author": str(getattr(row, "first_author", "") or ""),
        "year": row.year if pd.notna(row.year) else None,
        "cited_by_count": row.cited_by_count,
        "abstract": str(getattr(row, "abstract", "") or ""),
    }

# Load citations
print("Loading citations...")
cit = pd.read_csv(os.path.join(CATALOGS_DIR, "citations.csv"), low_memory=False)
cit["source_doi"] = cit["source_doi"].apply(normalize_doi)
cit["ref_doi"] = cit["ref_doi"].apply(normalize_doi)
cit = cit[
    cit["source_doi"].notna()
    & ~cit["source_doi"].isin(["", "nan", "none"])
    & cit["ref_doi"].notna()
    & ~cit["ref_doi"].isin(["", "nan", "none"])
]
print(f"Citation pairs with DOIs: {len(cit)}")

# Add ref metadata from citations for papers not in works
cit["ref_year_num"] = pd.to_numeric(cit["ref_year"], errors="coerce")
for row in cit.itertuples(index=False):
    d = row.ref_doi
    if d and d not in ("", "nan", "none") and d not in doi_meta:
        yr = row.ref_year_num if pd.notna(row.ref_year_num) else None
        doi_meta[d] = {
            "title": str(getattr(row, "ref_title", "") or ""),
            "first_author": str(getattr(row, "ref_first_author", "") or ""),
            "year": float(yr) if yr is not None else None,
            "cited_by_count": 0,
            "abstract": "",
        }

# ============================================================
# Step 2: Coverage statistics
# ============================================================

print(f"\n--- Coverage statistics (year <= {YEAR_CUTOFF}) ---")

pre2020_dois = set(pre2020["doi_norm"]) - {"", "nan", "none"}
print(f"  Unique pre-{YEAR_CUTOFF + 1} DOIs in corpus: {len(pre2020_dois)}")

source_dois = set(cit["source_doi"])
pre2020_as_sources = pre2020_dois & source_dois
print(f"  Pre-{YEAR_CUTOFF + 1} DOIs as citation sources: {len(pre2020_as_sources)}")

# All references with year <= 2019
pre2020_refs_all = set(
    cit[cit["ref_year_num"] <= YEAR_CUTOFF]["ref_doi"]
) - {"", "nan", "none"}
print(f"  All cited references with year <= {YEAR_CUTOFF}: {len(pre2020_refs_all)}")

# ============================================================
# Step 3: Build co-citation network
# ============================================================

print("\n" + "=" * 70)
print(f"CO-CITATION NETWORK: top {TOP_N} pre-{YEAR_CUTOFF + 1} references")
print("(Two pre-2020 refs linked if co-cited by ANY paper in the corpus)")
print("=" * 70)

# Count how often each reference is cited
ref_counts = cit.groupby("ref_doi").size().sort_values(ascending=False)

# Filter to pre-2020 references
pre2020_ref_counts = ref_counts[ref_counts.index.isin(pre2020_refs_all)]
print(f"\nPre-{YEAR_CUTOFF + 1} references cited at least once: {len(pre2020_ref_counts)}")
print(f"Pre-{YEAR_CUTOFF + 1} references cited >= 3 times: {(pre2020_ref_counts >= 3).sum()}")
print(f"Pre-{YEAR_CUTOFF + 1} references cited >= 5 times: {(pre2020_ref_counts >= 5).sum()}")
print(f"Pre-{YEAR_CUTOFF + 1} references cited >= 10 times: {(pre2020_ref_counts >= 10).sum()}")

# Select top N
actual_n = min(TOP_N, len(pre2020_ref_counts))
top_refs = pre2020_ref_counts.head(actual_n).index.tolist()
top_set = set(top_refs)
ref_to_idx = {ref: i for i, ref in enumerate(top_refs)}

print(f"\nUsing top {actual_n} most-cited pre-{YEAR_CUTOFF + 1} references")
print(f"Min citations in top set: {pre2020_ref_counts.iloc[actual_n - 1]}")

# Build co-citation matrix
print("Building co-citation matrix...")
source_groups = cit.groupby("source_doi")["ref_doi"].apply(list)

cocit_matrix = lil_matrix((actual_n, actual_n), dtype=np.float64)
for _source_doi, ref_list in source_groups.items():
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
print(f"Non-zero co-citation pairs: {n_pairs}")

# Build graph
G = nx.Graph()
for i, doi in enumerate(top_refs):
    meta = doi_meta.get(doi, {})
    author = str(meta.get("first_author", "")).split(",")[0].split(";")[0].strip()
    year = meta.get("year", "")
    if year and not pd.isna(year):
        year = int(year)
    label = f"{author} ({year})" if author and year else doi[:25]
    G.add_node(doi, label=label, citations=int(ref_counts.get(doi, 0)))

for i in range(actual_n):
    for j in range(i + 1, actual_n):
        w = cocit_dense[i, j]
        if w >= MIN_COCIT:
            G.add_edge(top_refs[i], top_refs[j], weight=w)

isolates = list(nx.isolates(G))
G.remove_nodes_from(isolates)
print(f"Network: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
print(f"Removed {len(isolates)} isolates")


# ============================================================
# Helper: characterize communities
# ============================================================


def characterize_communities(partition, ref_counts, doi_meta, label=""):
    """Print detailed community profiles with top papers and TF-IDF terms."""
    comm_papers = defaultdict(list)
    for doi, comm in partition.items():
        comm_papers[comm].append(doi)

    print(f"\n{'=' * 60}")
    print(f"COMMUNITY PROFILES {label}")
    print(f"{'=' * 60}")

    results = []

    for c in sorted(comm_papers.keys()):
        papers = comm_papers[c]
        # Sort by citation count (ref_counts = times cited within our corpus)
        papers_sorted = sorted(
            papers,
            key=lambda d: ref_counts.get(d, 0),
            reverse=True,
        )

        print(f"\n--- Community {c} ({len(papers)} papers) ---")

        # Top papers
        print("  Top 10 papers:")
        for d in papers_sorted[:10]:
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
            print(f"    [{rc:>3}x cited] {author} ({year}) {title}")

        # TF-IDF on abstracts (fall back to titles)
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

        if len(texts) >= 3:
            try:
                tfidf = TfidfVectorizer(
                    max_features=500,
                    stop_words="english",
                    ngram_range=(1, 2),
                    min_df=2,
                    max_df=0.8,
                )
                X = tfidf.fit_transform(texts)
                mean_tfidf = np.asarray(X.mean(axis=0)).flatten()
                top_idx = mean_tfidf.argsort()[::-1][:20]
                terms = tfidf.get_feature_names_out()
                top_terms = [terms[i] for i in top_idx]
                print(
                    f"  Top TF-IDF terms ({len(texts)} texts): {', '.join(top_terms)}"
                )
            except Exception as e:
                print(f"  (TF-IDF failed: {e})")
        else:
            print(f"  (Only {len(texts)} texts available -- skipping TF-IDF)")

        # Collect results for CSV
        for d in papers:
            meta = doi_meta.get(d, {})
            results.append(
                {
                    "community": c,
                    "doi": d,
                    "first_author": meta.get("first_author", ""),
                    "year": meta.get("year", ""),
                    "title": meta.get("title", ""),
                    "times_cited": ref_counts.get(d, 0),
                }
            )

    return pd.DataFrame(results)


# ============================================================
# Step 4: Louvain — default resolution
# ============================================================

print("\n--- Louvain community detection (default resolution) ---")
partition_default = community_louvain.best_partition(
    G, weight="weight", random_state=42
)
n_comm = len(set(partition_default.values()))
sizes = defaultdict(int)
for v in partition_default.values():
    sizes[v] += 1
size_str = ", ".join(str(s) for s in sorted(sizes.values(), reverse=True))
print(f"Communities: {n_comm} (sizes: {size_str})")

df_default = characterize_communities(
    partition_default,
    ref_counts,
    doi_meta,
    label=f"(default resolution, top {actual_n} pre-{YEAR_CUTOFF + 1} refs)",
)

# ============================================================
# Step 5: Louvain — resolution scan
# ============================================================

print("\n" + "=" * 70)
print("RESOLUTION SCAN")
print("=" * 70)

for gamma in [0.3, 0.5, 0.7, 1.0, 1.5, 2.0]:
    part = community_louvain.best_partition(
        G, weight="weight", resolution=gamma, random_state=42
    )
    n_c = len(set(part.values()))
    sz = defaultdict(int)
    for v in part.values():
        sz[v] += 1
    sz_str = ", ".join(str(s) for s in sorted(sz.values(), reverse=True))
    print(f"  gamma={gamma}: {n_c} communities (sizes: {sz_str})")

# ============================================================
# Step 6: Louvain — gamma=0.5 for finer detail
# ============================================================

print("\n" + "=" * 70)
print("DETAILED PROFILES: gamma=0.5")
print("=" * 70)

partition_05 = community_louvain.best_partition(
    G, weight="weight", resolution=0.5, random_state=42
)
n_comm_05 = len(set(partition_05.values()))
sizes_05 = defaultdict(int)
for v in partition_05.values():
    sizes_05[v] += 1
size_str_05 = ", ".join(str(s) for s in sorted(sizes_05.values(), reverse=True))
print(f"Communities: {n_comm_05} (sizes: {size_str_05})")

df_05 = characterize_communities(
    partition_05,
    ref_counts,
    doi_meta,
    label="(gamma=0.5)",
)

# ============================================================
# Step 7: Save community assignments
# ============================================================

output_dir = os.path.join(BASE_DIR, "content", "tables")
os.makedirs(output_dir, exist_ok=True)

# Save the gamma=0.5 partition (finer detail) as the main output
# Add a column for the default-resolution community too
df_05 = df_05.rename(columns={"community": "community_gamma05"})

# Build default-resolution mapping
default_map = {}
for doi, c in partition_default.items():
    default_map[doi] = c
df_05["community_default"] = df_05["doi"].map(default_map)

# Sort by community, then by times_cited descending
df_05 = df_05.sort_values(
    ["community_gamma05", "times_cited"], ascending=[True, False]
)

outpath = os.path.join(output_dir, "traditions_pre2020_communities.csv")
df_05.to_csv(outpath, index=False)
print(f"\nSaved community assignments to {outpath}")
print(f"  Rows: {len(df_05)}, Communities (gamma=0.5): {n_comm_05}, "
      f"Communities (default): {n_comm}")

# ============================================================
# Summary
# ============================================================

print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
print(f"""
Analysis: co-citation communities among top {actual_n} most-cited
references published <= {YEAR_CUTOFF}, co-cited by ANY paper in the corpus.

Network: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges
  (min co-citation = {MIN_COCIT}, {len(isolates)} isolates removed)

Default resolution: {n_comm} communities
gamma=0.5:          {n_comm_05} communities

Output: {outpath}

Key caveat: citation data covers only the original ~12K corpus (stale).
""")

print("Done.")
