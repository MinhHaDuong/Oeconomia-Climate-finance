"""Compare co-citation communities across three time windows (pre-2007, pre-2015, pre-2020).

Uses IDENTICAL methodology for each window:
  1. Identify all references with year <= cutoff cited in the corpus
  2. Take the top 250 most-cited such references
  3. Build co-citation graph: two refs linked if co-cited by ANY corpus paper
  4. Edge weight = number of co-citing papers; threshold >= 3
  5. Remove isolates
  6. Louvain with resolution=1.0 (default), random_state=42
  7. Characterize communities (top papers, TF-IDF terms)

Then align communities across windows using Jaccard similarity on DOI sets.

Usage:
    uv run python scripts/compare_communities_across_windows.py
"""

import os
import sys
from collections import defaultdict

import community as community_louvain
import networkx as nx
import numpy as np
import pandas as pd
from scipy.sparse import lil_matrix
from sklearn.feature_extraction.text import TfidfVectorizer

# Add scripts dir to path for utils
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils import CATALOGS_DIR, normalize_doi

# ============================================================
# Parameters
# ============================================================

WINDOWS = [
    {"label": "Pre-2007", "cutoff": 2006},
    {"label": "Pre-2015", "cutoff": 2014},
    {"label": "Pre-2020", "cutoff": 2019},
    {"label": "Full", "cutoff": 2025},
]
TOP_N = 250
MIN_COCIT = 3
RESOLUTION = 1.0
RANDOM_STATE = 42

# ============================================================
# Step 1: Load data (once)
# ============================================================

print("=" * 80)
print("COMPARING CO-CITATION COMMUNITIES ACROSS THREE TIME WINDOWS")
print("=" * 80)

print("\n--- Loading data ---")
works = pd.read_csv(os.path.join(CATALOGS_DIR, "refined_works.csv"))
works["year"] = pd.to_numeric(works["year"], errors="coerce")
works["doi_norm"] = works["doi"].apply(normalize_doi)
works["cited_by_count"] = pd.to_numeric(
    works["cited_by_count"], errors="coerce"
).fillna(0)
print(f"Total works in corpus: {len(works)}")

# Build DOI -> metadata lookup from works
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
print(f"Citation pairs with valid DOIs: {len(cit)}")

# Add ref metadata from citations for papers not already in works
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

# Precompute source_doi -> [ref_doi] grouping (used for all windows)
print("Grouping citations by source paper...")
source_groups = cit.groupby("source_doi")["ref_doi"].apply(list)
print(f"Unique source papers with citations: {len(source_groups)}")

# Global ref counts (times cited across the entire corpus)
ref_counts = cit.groupby("ref_doi").size().sort_values(ascending=False)
print(f"Unique referenced DOIs: {len(ref_counts)}")


# ============================================================
# Step 2: Run detection for each window
# ============================================================


def detect_communities(cutoff_year, top_n, min_cocit, resolution, random_state):
    """Run the full co-citation community detection pipeline for one time window.

    Returns: dict with partition, graph, ref_counts_in_window, community_dois, stats.
    """
    label = f"year <= {cutoff_year}"
    print(f"\n{'=' * 80}")
    print(f"WINDOW: {label} | Top {top_n} refs | min co-cit >= {min_cocit} | "
          f"resolution={resolution}")
    print("=" * 80)

    # Identify all references with year <= cutoff
    pre_refs = set(
        cit[cit["ref_year_num"] <= cutoff_year]["ref_doi"]
    ) - {"", "nan", "none"}
    print(f"  Unique refs with year <= {cutoff_year}: {len(pre_refs)}")

    # Count how often each such ref is cited (by ANY paper in corpus)
    pre_ref_counts = ref_counts[ref_counts.index.isin(pre_refs)]
    print(f"  Refs cited >= 1 time: {len(pre_ref_counts)}")
    print(f"  Refs cited >= 3 times: {(pre_ref_counts >= 3).sum()}")
    print(f"  Refs cited >= 5 times: {(pre_ref_counts >= 5).sum()}")
    print(f"  Refs cited >= 10 times: {(pre_ref_counts >= 10).sum()}")

    # Select top N
    actual_n = min(top_n, len(pre_ref_counts))
    top_refs = pre_ref_counts.head(actual_n).index.tolist()
    top_set = set(top_refs)
    ref_to_idx = {ref: i for i, ref in enumerate(top_refs)}

    print(f"  Using top {actual_n} most-cited refs")
    if actual_n > 0:
        print(f"  Citation range in top set: "
              f"{pre_ref_counts.iloc[0]} .. {pre_ref_counts.iloc[actual_n - 1]}")

    # Build co-citation matrix
    print("  Building co-citation matrix...")
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
    print(f"  Non-zero co-citation pairs: {n_pairs}")

    # Build graph
    G = nx.Graph()
    for i, doi in enumerate(top_refs):
        meta = doi_meta.get(doi, {})
        author = str(meta.get("first_author", "")).split(",")[0].split(";")[0].strip()
        year = meta.get("year", "")
        if year and not pd.isna(year):
            year = int(year)
        node_label = f"{author} ({year})" if author and year else doi[:25]
        G.add_node(doi, label=node_label, citations=int(ref_counts.get(doi, 0)))

    for i in range(actual_n):
        for j in range(i + 1, actual_n):
            w = cocit_dense[i, j]
            if w >= min_cocit:
                G.add_edge(top_refs[i], top_refs[j], weight=w)

    isolates = list(nx.isolates(G))
    G.remove_nodes_from(isolates)
    print(f"  Network: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    print(f"  Removed {len(isolates)} isolates")

    if G.number_of_nodes() == 0:
        print("  WARNING: empty graph, no communities to detect.")
        return {
            "partition": {},
            "graph": G,
            "community_dois": {},
            "community_labels": {},
            "stats": {
                "nodes": 0, "edges": 0, "n_communities": 0, "modularity": 0
            },
        }

    # Louvain
    partition = community_louvain.best_partition(
        G, weight="weight", resolution=resolution, random_state=random_state
    )
    modularity = community_louvain.modularity(partition, G, weight="weight")
    n_comm = len(set(partition.values()))
    sizes = defaultdict(int)
    for v in partition.values():
        sizes[v] += 1
    size_str = ", ".join(str(s) for s in sorted(sizes.values(), reverse=True))
    print(f"  Louvain: {n_comm} communities (sizes: {size_str})")
    print(f"  Modularity: {modularity:.4f}")

    # Collect community DOI sets and characterize
    community_dois = defaultdict(set)
    for doi, c in partition.items():
        community_dois[c].add(doi)

    community_labels = {}
    for c in sorted(community_dois.keys()):
        papers = list(community_dois[c])
        papers_sorted = sorted(
            papers, key=lambda d: ref_counts.get(d, 0), reverse=True
        )

        # Top 5 papers
        print(f"\n  Community {c} ({len(papers)} papers):")
        print("    Top 5 papers:")
        top_authors = []
        for d in papers_sorted[:5]:
            meta = doi_meta.get(d, {})
            author = str(meta.get("first_author", "?"))
            if author in ("nan", "None", ""):
                author = "?"
            year_val = meta.get("year", "?")
            if year_val and not pd.isna(year_val):
                year_val = int(year_val)
            title = str(meta.get("title", ""))[:70]
            if title in ("nan", "None", ""):
                title = f"[{d[:30]}]"
            rc = ref_counts.get(d, 0)
            print(f"      [{rc:>3}x] {author} ({year_val}) {title}")
            surname = author.split(",")[0].split(";")[0].strip().split()[-1]
            if surname not in ("?", "nan", "None", ""):
                top_authors.append(surname)

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

        tfidf_terms = []
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
                top_idx = mean_tfidf.argsort()[::-1][:15]
                terms = tfidf.get_feature_names_out()
                tfidf_terms = [terms[i] for i in top_idx]
                print(f"    TF-IDF ({len(texts)} texts): {', '.join(tfidf_terms[:10])}")
            except Exception as e:
                print(f"    (TF-IDF failed: {e})")
        else:
            print(f"    (Only {len(texts)} texts -- skipping TF-IDF)")

        # Build a short label from top 3 TF-IDF unigrams
        label_terms = [t for t in tfidf_terms if " " not in t][:3]
        if label_terms:
            short_label = " / ".join(label_terms)
        elif top_authors:
            short_label = " / ".join(top_authors[:3])
        else:
            short_label = "(?)"
        community_labels[c] = short_label

    return {
        "partition": partition,
        "graph": G,
        "community_dois": dict(community_dois),
        "community_labels": community_labels,
        "stats": {
            "nodes": G.number_of_nodes(),
            "edges": G.number_of_edges(),
            "n_communities": n_comm,
            "modularity": modularity,
        },
    }


# Run for all three windows
results = {}
for w in WINDOWS:
    results[w["label"]] = detect_communities(
        w["cutoff"], TOP_N, MIN_COCIT, RESOLUTION, RANDOM_STATE
    )


# ============================================================
# Step 3: Jaccard similarity across windows
# ============================================================

print("\n" + "=" * 80)
print("JACCARD SIMILARITY MATRICES BETWEEN COMMUNITY PAIRS")
print("=" * 80)

window_labels = [w["label"] for w in WINDOWS]


def jaccard(set_a, set_b):
    """Compute Jaccard similarity between two sets."""
    if not set_a and not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


# For each pair of windows, compute Jaccard between all community pairs
for i in range(len(window_labels)):
    for j in range(i + 1, len(window_labels)):
        w1, w2 = window_labels[i], window_labels[j]
        r1, r2 = results[w1], results[w2]
        cd1 = r1["community_dois"]
        cd2 = r2["community_dois"]
        cl1 = r1["community_labels"]
        cl2 = r2["community_labels"]

        comms1 = sorted(cd1.keys())
        comms2 = sorted(cd2.keys())

        print(f"\n--- {w1} vs {w2} ---")
        # Header
        header = f"{'':>20s}"
        for c2 in comms2:
            header += f" | C{c2}({len(cd2[c2]):>3d})"
        print(header)
        print("-" * len(header))

        for c1 in comms1:
            row = f"C{c1}({len(cd1[c1]):>3d}) {cl1[c1][:12]:>12s}"
            for c2 in comms2:
                j_val = jaccard(cd1[c1], cd2[c2])
                if j_val >= 0.01:
                    row += f" | {j_val:>8.3f}"
                else:
                    row += f" | {'---':>8s}"
            print(row)


# ============================================================
# Step 4: Align communities using greedy Jaccard matching
# ============================================================

print("\n" + "=" * 80)
print("COMMUNITY ALIGNMENT ACROSS TIME WINDOWS")
print("=" * 80)


def build_jaccard_matrix(cd1, cd2):
    """Build a matrix of Jaccard similarities between all pairs of communities."""
    comms1 = sorted(cd1.keys())
    comms2 = sorted(cd2.keys())
    matrix = {}
    for c1 in comms1:
        for c2 in comms2:
            matrix[(c1, c2)] = jaccard(cd1[c1], cd2[c2])
    return matrix, comms1, comms2


def greedy_alignment(cd_list, labels_list, window_names):
    """Align communities across multiple windows using greedy Jaccard matching.

    Uses the last (largest) window as anchor and finds best matches backward.
    """
    n_windows = len(cd_list)
    # Use last window as anchor
    anchor_comms = sorted(cd_list[-1].keys())

    # For each anchor community, find best match in each earlier window
    rows = []
    for anchor_c in anchor_comms:
        row = [None] * n_windows
        row[-1] = anchor_c
        # Walk backward
        for w in range(n_windows - 2, -1, -1):
            best_c = None
            best_j = 0.0
            for c in sorted(cd_list[w].keys()):
                # Compare with the next window's matched community
                next_c = row[w + 1]
                if next_c is None:
                    continue
                j_val = jaccard(cd_list[w][c], cd_list[w + 1][next_c])
                if j_val > best_j:
                    best_j = j_val
                    best_c = c
            if best_j >= 0.05:  # threshold for meaningful overlap
                row[w] = best_c
        rows.append(row)

    # Also find communities in earlier windows that have no match in later ones
    # Check pre-2007 communities not yet matched
    for w in range(n_windows - 1):
        matched = {row[w] for row in rows if row[w] is not None}
        unmatched = set(cd_list[w].keys()) - matched
        for c in sorted(unmatched):
            row = [None] * n_windows
            row[w] = c
            # Try to find matches forward
            for w2 in range(w + 1, n_windows):
                best_c = None
                best_j = 0.0
                for c2 in sorted(cd_list[w2].keys()):
                    j_val = jaccard(cd_list[w][c], cd_list[w2][c2])
                    if j_val > best_j:
                        best_j = j_val
                        best_c = c2
                if best_j >= 0.05:
                    row[w2] = best_c
            rows.append(row)

    # Deduplicate rows (same combination)
    seen = set()
    unique_rows = []
    for row in rows:
        key = tuple(row)
        if key not in seen:
            seen.add(key)
            unique_rows.append(row)

    return unique_rows


# Gather data
cd_list = [results[w]["community_dois"] for w in window_labels]
cl_list = [results[w]["community_labels"] for w in window_labels]

aligned_rows = greedy_alignment(cd_list, cl_list, window_labels)

# Print the aligned table
print(f"\n{'ALIGNED COMMUNITIES ACROSS TIME WINDOWS':^100}")
print()

# Column widths
col_w = 32
sep = "-" * (6 + (col_w + 3) * len(window_labels))

# Header
header = f"{'Row':>4s}"
for w_idx, w in enumerate(WINDOWS):
    header += f" | {w['label'] + ' (<=' + str(w['cutoff']) + ')':^{col_w}s}"
print(header)
print(sep)

row_letter = ord('A')
for aligned_row in aligned_rows:
    # Main line: community ID, size, label
    line1 = f"  {chr(row_letter):>2s}"
    line2 = f"{'':>4s}"
    for w_idx in range(len(window_labels)):
        c = aligned_row[w_idx]
        if c is not None:
            cd = cd_list[w_idx]
            cl = cl_list[w_idx]
            size = len(cd[c])
            label = cl[c]
            # Top 3 authors
            papers = list(cd[c])
            papers_sorted = sorted(
                papers, key=lambda d: ref_counts.get(d, 0), reverse=True
            )
            top_auth = []
            for d in papers_sorted[:3]:
                meta = doi_meta.get(d, {})
                auth = str(meta.get("first_author", "?"))
                if auth in ("nan", "None", ""):
                    auth = "?"
                surname = auth.split(",")[0].split(";")[0].strip().split()[-1]
                if surname not in ("?", "nan", "None", ""):
                    top_auth.append(surname)
            cell1 = f"C{c} ({size}): {label[:18]}"
            cell2 = f"  {', '.join(top_auth[:3])}"
        else:
            cell1 = "---"
            cell2 = ""
        line1 += f" | {cell1:<{col_w}s}"
        line2 += f" | {cell2:<{col_w}s}"
    print(line1)
    print(line2)
    row_letter += 1

print(sep)

# ============================================================
# Step 5: Summary of DOI flow across windows
# ============================================================

print("\n" + "=" * 80)
print("DOI OVERLAP SUMMARY")
print("=" * 80)

for i in range(len(window_labels)):
    for j in range(i + 1, len(window_labels)):
        w1, w2 = window_labels[i], window_labels[j]
        all_dois_1 = set()
        for s in results[w1]["community_dois"].values():
            all_dois_1 |= s
        all_dois_2 = set()
        for s in results[w2]["community_dois"].values():
            all_dois_2 |= s
        overlap = all_dois_1 & all_dois_2
        only_1 = all_dois_1 - all_dois_2
        only_2 = all_dois_2 - all_dois_1
        print(f"\n  {w1} ({len(all_dois_1)} refs) vs {w2} ({len(all_dois_2)} refs):")
        print(f"    Shared: {len(overlap)}, Only in {w1}: {len(only_1)}, "
              f"Only in {w2}: {len(only_2)}")
        print(f"    Jaccard (full sets): {jaccard(all_dois_1, all_dois_2):.3f}")

# ============================================================
# Final summary
# ============================================================

print("\n" + "=" * 80)
print("PARAMETER SUMMARY")
print("=" * 80)
print(f"  Top N references per window: {TOP_N}")
print(f"  Min co-citation for edge: {MIN_COCIT}")
print(f"  Louvain resolution: {RESOLUTION}")
print(f"  Random state: {RANDOM_STATE}")
for w in WINDOWS:
    r = results[w["label"]]
    s = r["stats"]
    print(f"\n  {w['label']} (year <= {w['cutoff']}):")
    print(f"    Network: {s['nodes']} nodes, {s['edges']} edges")
    print(f"    Communities: {s['n_communities']}, Modularity: {s['modularity']:.4f}")

print("\nDone.")
