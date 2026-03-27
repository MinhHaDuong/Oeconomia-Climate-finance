"""Detect pre-2007 intellectual traditions via citation network community detection.

Hypothesis: before climate finance crystallized (~2007), three disconnected
traditions existed:
  1. Environmental economics (carbon pricing, externalities, IAMs)
  2. Development economics (ODA, aid flows, concessionality)
  3. Burden-sharing (equity, Negishi weights, "who should pay")

This script tests that hypothesis using:
  (a) Direct citation graph -> Louvain communities
  (b) Co-citation network -> Louvain communities
  (c) Bibliographic coupling -> Louvain communities

For each approach it reports community sizes, top papers, and top TF-IDF terms.

Usage:
    uv run python scripts/detect_traditions_v2.py
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
from utils import CATALOGS_DIR, get_logger, normalize_doi

log = get_logger("detect_traditions_v2")

# ============================================================
# Step 1: Load and filter data to pre-2007
# ============================================================

log.info("=" * 70)
log.info("DETECTING PRE-2007 INTELLECTUAL TRADITIONS")
log.info("=" * 70)

log.info("\n--- Loading data ---")
works = pd.read_csv(os.path.join(CATALOGS_DIR, "refined_works.csv"))
works["year"] = pd.to_numeric(works["year"], errors="coerce")
works["doi_norm"] = works["doi"].apply(normalize_doi)
works["cited_by_count"] = pd.to_numeric(works["cited_by_count"], errors="coerce").fillna(0)
log.info(f"Total works: {len(works)}")

# Build DOI -> metadata lookup
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
            "abstract": "",
        }

# ============================================================
# Step 2: Coverage statistics for pre-2007
# ============================================================

log.info("\n--- Coverage statistics ---")

# Pre-2007 works in the corpus
pre2007 = works[works["year"] <= 2006].copy()
log.info(f"Works with year <= 2006: {len(pre2007)}")
log.info(f"  With DOI: {pre2007['doi_norm'].apply(lambda x: x not in ('', 'nan', 'none')).sum()}")
pre2007_dois = set(pre2007["doi_norm"]) - {"", "nan", "none"}
log.info(f"  Unique DOIs: {len(pre2007_dois)}")

# How many pre-2007 works appear as sources in citations?
source_dois = set(cit["source_doi"])
pre2007_as_sources = pre2007_dois & source_dois
log.info(f"  Pre-2007 DOIs appearing as citation sources: {len(pre2007_as_sources)}")

# How many pre-2007 works appear as references?
ref_dois = set(cit["ref_doi"])
pre2007_as_refs = pre2007_dois & ref_dois
log.info(f"  Pre-2007 DOIs appearing as cited references: {len(pre2007_as_refs)}")

# All pre-2007 DOIs involved in any citation link
pre2007_in_citations = pre2007_as_sources | pre2007_as_refs
log.info(f"  Pre-2007 DOIs in citation network (source or ref): {len(pre2007_in_citations)}")
log.info(f"  Coverage: {len(pre2007_in_citations)/len(pre2007_dois)*100:.1f}% of pre-2007 corpus DOIs")

# References in citations.csv with year <= 2006 (including outside corpus)
cit["ref_year_num"] = pd.to_numeric(cit["ref_year"], errors="coerce")
pre2007_refs_all = set(cit[cit["ref_year_num"] <= 2006]["ref_doi"]) - {"", "nan", "none"}
log.info(f"\nAll cited references with year <= 2006: {len(pre2007_refs_all)}")

# Citation links where BOTH source and ref are pre-2007
cit_source_year = cit["source_doi"].map(lambda d: doi_meta.get(d, {}).get("year"))
cit_pre2007 = cit[
    (cit_source_year <= 2006) & (cit["ref_year_num"] <= 2006)
].copy()
log.info(f"Citation links where both source AND ref are pre-2007: {len(cit_pre2007)}")

# ============================================================
# Step 3: Build networks — using ALL citations (not just pre-2007 sources)
# ============================================================
# Strategy: use co-citation among ALL citing papers (including post-2006)
# to detect pre-2007 intellectual communities. This gives much better coverage.

log.info("\n" + "=" * 70)
log.info("APPROACH A: Co-citation network of pre-2007 references")
log.info("(Two pre-2007 refs linked if co-cited by ANY paper in the corpus)")
log.info("=" * 70)

# Identify pre-2007 references that are frequently cited
ref_counts = cit.groupby("ref_doi").size().sort_values(ascending=False)

# Filter to refs with year <= 2006
pre2007_ref_counts = ref_counts[ref_counts.index.isin(pre2007_refs_all)]
log.info(f"\nPre-2007 references cited at least once: {len(pre2007_ref_counts)}")
log.info(f"Pre-2007 references cited >= 3 times: {(pre2007_ref_counts >= 3).sum()}")
log.info(f"Pre-2007 references cited >= 5 times: {(pre2007_ref_counts >= 5).sum()}")

# Use top N most-cited pre-2007 references
TOP_N = 150
top_pre2007_refs = pre2007_ref_counts.head(TOP_N).index.tolist()
top_set = set(top_pre2007_refs)
ref_to_idx = {ref: i for i, ref in enumerate(top_pre2007_refs)}

log.info(f"\nUsing top {TOP_N} most-cited pre-2007 references")
log.info(f"Min citations in top set: {pre2007_ref_counts.iloc[min(TOP_N-1, len(pre2007_ref_counts)-1)]}")

# Build co-citation matrix
log.info("Building co-citation matrix...")
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
n_pairs = np.count_nonzero(cocit_dense) // 2
log.info(f"Non-zero co-citation pairs: {n_pairs}")

# Build graph
G_cocit = nx.Graph()
for i, doi in enumerate(top_pre2007_refs):
    meta = doi_meta.get(doi, {})
    author = str(meta.get("first_author", "")).split(",")[0].split(";")[0].strip()
    year = meta.get("year", "")
    if year and not pd.isna(year):
        year = int(year)
    label = f"{author} ({year})" if author and year else doi[:25]
    G_cocit.add_node(doi, label=label, citations=int(ref_counts.get(doi, 0)))

MIN_COCIT = 2
for i in range(TOP_N):
    for j in range(i + 1, TOP_N):
        w = cocit_dense[i, j]
        if w >= MIN_COCIT:
            G_cocit.add_edge(top_pre2007_refs[i], top_pre2007_refs[j], weight=w)

isolates = list(nx.isolates(G_cocit))
G_cocit.remove_nodes_from(isolates)
log.info(f"Network: {G_cocit.number_of_nodes()} nodes, {G_cocit.number_of_edges()} edges")
log.info(f"Removed {len(isolates)} isolates")

# Louvain community detection
partition_cocit = community_louvain.best_partition(G_cocit, weight="weight", random_state=42)
n_comm = len(set(partition_cocit.values()))
log.info(f"Communities detected: {n_comm}")


def characterize_communities(partition, graph, doi_meta, ref_counts, label=""):
    """Print detailed community profiles with top papers and TF-IDF terms."""
    comm_papers = defaultdict(list)
    for doi, comm in partition.items():
        comm_papers[comm].append(doi)

    log.info(f"\n{'='*60}")
    log.info(f"COMMUNITY PROFILES {label}")
    log.info(f"{'='*60}")

    for c in sorted(comm_papers.keys()):
        papers = comm_papers[c]
        # Sort by citation count
        papers_sorted = sorted(papers,
                               key=lambda d: doi_meta.get(d, {}).get("cited_by_count", 0)
                               + ref_counts.get(d, 0),
                               reverse=True)

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
            title = str(meta.get("title", ""))[:75]
            if title in ("nan", "None", ""):
                title = f"[{d}]"
            rc = ref_counts.get(d, 0)
            log.info(f"    [{rc:>3}x ref'd] {author} ({year}) {title}")

        # TF-IDF: use abstracts first, fall back to titles
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
                    max_features=500, stop_words="english",
                    ngram_range=(1, 2), min_df=2, max_df=0.8
                )
                X = tfidf.fit_transform(texts)
                mean_tfidf = np.asarray(X.mean(axis=0)).flatten()
                top_idx = mean_tfidf.argsort()[::-1][:20]
                terms = tfidf.get_feature_names_out()
                top_terms = [terms[i] for i in top_idx]
                log.info(f"  Top TF-IDF terms ({len(texts)} texts): {', '.join(top_terms)}")
            except Exception as e:
                log.info(f"  (TF-IDF failed: {e})")
        else:
            log.info(f"  (Only {len(texts)} texts available — skipping TF-IDF)")

    return comm_papers


comm_papers_cocit = characterize_communities(
    partition_cocit, G_cocit, doi_meta, ref_counts,
    label="(Co-citation, top 150 pre-2007 refs)"
)

# ============================================================
# Approach B: Direct citation graph among pre-2007 works
# ============================================================

log.info("\n" + "=" * 70)
log.info("APPROACH B: Direct citation graph among pre-2007 works")
log.info("=" * 70)

# Build direct citation edges between pre-2007 works
# A -> B means A cites B, both pre-2007
direct_edges = []
for _, row in cit.iterrows():
    s = row["source_doi"]
    r = row["ref_doi"]
    s_year = doi_meta.get(s, {}).get("year")
    r_year = doi_meta.get(r, {}).get("year")
    if s_year and r_year and s_year <= 2006 and r_year <= 2006:
        if s in pre2007_dois and r in pre2007_dois:
            direct_edges.append((s, r))

direct_edges = list(set(direct_edges))
log.info(f"Direct citation edges (both in pre-2007 corpus): {len(direct_edges)}")

if len(direct_edges) > 10:
    G_direct = nx.Graph()  # undirected for community detection
    for s, r in direct_edges:
        if G_direct.has_edge(s, r):
            G_direct[s][r]["weight"] += 1
        else:
            G_direct.add_edge(s, r, weight=1)

    # Remove isolates
    isolates_d = list(nx.isolates(G_direct))
    G_direct.remove_nodes_from(isolates_d)
    log.info(f"Network: {G_direct.number_of_nodes()} nodes, {G_direct.number_of_edges()} edges")

    if G_direct.number_of_nodes() >= 5:
        partition_direct = community_louvain.best_partition(G_direct, weight="weight", random_state=42)
        n_comm_d = len(set(partition_direct.values()))
        log.info(f"Communities detected: {n_comm_d}")

        characterize_communities(
            partition_direct, G_direct, doi_meta, ref_counts,
            label="(Direct citation, pre-2007 corpus papers)"
        )
    else:
        log.info("Too few connected nodes for community detection.")
else:
    log.info("Too few direct citation edges for community detection.")

# ============================================================
# Approach C: Bibliographic coupling among pre-2007 works
# ============================================================

log.info("\n" + "=" * 70)
log.info("APPROACH C: Bibliographic coupling among pre-2007 works")
log.info("(Two papers linked if they share references)")
log.info("=" * 70)

# For each pre-2007 source paper, collect its reference set
source_to_refs = defaultdict(set)
for _, row in cit.iterrows():
    s = row["source_doi"]
    r = row["ref_doi"]
    if s in pre2007_dois:
        source_to_refs[s].add(r)

pre2007_with_refs = {d for d in pre2007_dois if d in source_to_refs and len(source_to_refs[d]) >= 2}
log.info(f"Pre-2007 papers with >= 2 references in citations.csv: {len(pre2007_with_refs)}")

if len(pre2007_with_refs) >= 10:
    # Build bibliographic coupling graph
    # Only among papers with enough shared refs
    pre2007_list = sorted(pre2007_with_refs)

    G_bibcoup = nx.Graph()

    # For efficiency, build inverted index: ref -> set of papers citing it
    ref_to_citers = defaultdict(set)
    for d in pre2007_with_refs:
        for r in source_to_refs[d]:
            ref_to_citers[r].add(d)

    # Count shared references between pairs
    coupling_counts = defaultdict(int)
    for ref, citers in ref_to_citers.items():
        citers_list = sorted(citers)
        if len(citers_list) < 2:
            continue
        for i in range(len(citers_list)):
            for j in range(i + 1, len(citers_list)):
                coupling_counts[(citers_list[i], citers_list[j])] += 1

    MIN_COUPLING = 3
    for (a, b), w in coupling_counts.items():
        if w >= MIN_COUPLING:
            G_bibcoup.add_edge(a, b, weight=w)

    isolates_bc = list(nx.isolates(G_bibcoup))
    G_bibcoup.remove_nodes_from(isolates_bc)
    log.info(f"Network (min coupling={MIN_COUPLING}): {G_bibcoup.number_of_nodes()} nodes, {G_bibcoup.number_of_edges()} edges")

    if G_bibcoup.number_of_nodes() >= 5:
        partition_bc = community_louvain.best_partition(G_bibcoup, weight="weight", random_state=42)
        n_comm_bc = len(set(partition_bc.values()))
        log.info(f"Communities detected: {n_comm_bc}")

        characterize_communities(
            partition_bc, G_bibcoup, doi_meta, ref_counts,
            label="(Bibliographic coupling, pre-2007 corpus)"
        )
    else:
        log.info("Too few connected nodes.")
else:
    log.info("Too few papers with references for bibliographic coupling.")


# ============================================================
# Approach D: Co-citation with resolution tuning for 3 communities
# ============================================================

log.info("\n" + "=" * 70)
log.info("APPROACH D: Co-citation with resolution tuning (targeting ~3 communities)")
log.info("=" * 70)

# Try different resolution parameters
for gamma in [0.5, 0.7, 1.0, 1.5, 2.0]:
    try:
        part = community_louvain.best_partition(
            G_cocit, weight="weight", resolution=gamma, random_state=42
        )
        n_c = len(set(part.values()))
        sizes = defaultdict(int)
        for v in part.values():
            sizes[v] += 1
        size_str = ", ".join(f"{s}" for s in sorted(sizes.values(), reverse=True))
        log.info(f"  gamma={gamma}: {n_c} communities (sizes: {size_str})")
    except TypeError:
        log.info(f"  gamma={gamma}: resolution parameter not supported")
        break

# Use gamma that gives ~3 communities
best_gamma = None
best_diff = 999
for gamma in [0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.2, 1.5, 2.0]:
    try:
        part = community_louvain.best_partition(
            G_cocit, weight="weight", resolution=gamma, random_state=42
        )
        n_c = len(set(part.values()))
        diff = abs(n_c - 3)
        if diff < best_diff or (diff == best_diff and gamma < best_gamma):
            best_diff = diff
            best_gamma = gamma
            best_partition = part
    except TypeError:
        break

if best_gamma is not None:
    n_c = len(set(best_partition.values()))
    log.info(f"\nBest resolution for ~3 communities: gamma={best_gamma} -> {n_c} communities")

    comm_papers_tuned = characterize_communities(
        best_partition, G_cocit, doi_meta, ref_counts,
        label=f"(Co-citation, gamma={best_gamma})"
    )

# Also show gamma=0.5 (5 communities) for finer detail
log.info("\n" + "=" * 70)
log.info("APPROACH E: Co-citation gamma=0.5 (5 communities — finer resolution)")
log.info("=" * 70)
try:
    part_05 = community_louvain.best_partition(
        G_cocit, weight="weight", resolution=0.5, random_state=42
    )
    n_c_05 = len(set(part_05.values()))
    log.info(f"Communities: {n_c_05}")
    characterize_communities(
        part_05, G_cocit, doi_meta, ref_counts,
        label="(Co-citation, gamma=0.5)"
    )
except TypeError:
    log.info("Resolution parameter not supported.")


# ============================================================
# Summary assessment
# ============================================================

log.info("\n" + "=" * 70)
log.info("SUMMARY AND ASSESSMENT")
log.info("=" * 70)

log.info("""
The hypothesis is that three disconnected traditions preceded climate finance:
  1. Environmental economics (carbon pricing, externalities, IAMs)
  2. Development economics (ODA, aid flows, concessionality)
  3. Burden-sharing (equity, Negishi weights, "who should pay")

Check the community profiles above. If communities map clearly to these
traditions, the hypothesis is supported. If communities are organized
along different lines (e.g., methodology, geography, journal), the
narrative needs revision.

Key caveats:
  - Citation data covers only the original ~12K corpus (stale for full 22K)
  - Pre-2007 papers are a small fraction of the corpus
  - Co-citation captures intellectual proximity but is biased toward
    papers that were later cited together in climate finance work
""")

log.info("Done.")
