"""Co-citation analysis of the climate finance corpus.

Method (Small 1973, White & Griffith 1981):
- Two works are co-cited when they appear together in the same reference list.
- We build a co-citation matrix for the most-cited references, then detect
  communities using the Louvain algorithm.

Produces:
- data/catalogs/communities.csv: Community assignments for top-cited works
- tables/tab_community_summary.csv: Top works per community

Options:
  --robustness    Louvain resolution sensitivity (R3)
"""

import argparse
import os

import community as community_louvain
import networkx as nx
import numpy as np
import pandas as pd
from scipy.sparse import lil_matrix
from script_io_args import parse_io_args, validate_io
from utils import (
    BASE_DIR,
    CATALOGS_DIR,
    get_logger,
    load_refined_citations,
    normalize_doi,
)

log = get_logger("analyze_cocitation")

# --- Constants ---
TOP_N = 200
MIN_COCIT = 3


def load_citation_data():
    """Load and clean citation pairs with DOIs."""
    cit = load_refined_citations()
    cit["source_doi"] = cit["source_doi"].apply(normalize_doi)
    cit["ref_doi"] = cit["ref_doi"].apply(normalize_doi)

    # Keep only rows where both source and ref have valid DOIs
    cit = cit[(cit["source_doi"] != "") & (cit["ref_doi"] != "")]
    cit = cit[~cit["source_doi"].isin(["nan", "none"])]
    cit = cit[~cit["ref_doi"].isin(["nan", "none"])]
    log.info("Citation pairs with DOIs: %d", len(cit))
    return cit


def build_doi_metadata(cit):
    """Build DOI-to-metadata lookup from works and citations."""
    works = pd.read_csv(os.path.join(CATALOGS_DIR, "refined_works.csv"))
    works["doi_norm"] = works["doi"].apply(normalize_doi)
    doi_to_meta = {}
    for _, row in works.iterrows():
        d = row["doi_norm"]
        if d and d not in ("nan", "none"):
            doi_to_meta[d] = {
                "title": str(row.get("title", "") or ""),
                "first_author": str(row.get("first_author", "") or ""),
                "year": row.get("year", ""),
            }

    # Also build lookup from citations metadata (for refs not in our corpus)
    for _, row in cit.iterrows():
        d = row["ref_doi"]
        if d and d not in ("nan", "none") and d not in doi_to_meta:
            doi_to_meta[d] = {
                "title": str(row.get("ref_title", "") or ""),
                "first_author": str(row.get("ref_first_author", "") or ""),
                "year": row.get("ref_year", "") or "",
            }
    return doi_to_meta


def build_cocitation_matrix(cit, top_refs, top_set, ref_to_idx):
    """Build co-citation matrix from citation pairs."""
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
    log.info("Non-zero co-citation pairs: %d", np.count_nonzero(cocit_dense) // 2)
    return cocit_dense


def build_network(top_refs, ref_counts, doi_to_meta, cocit_dense, min_cocit):
    """Build weighted co-citation network and remove isolates."""
    G = nx.Graph()
    for i, doi in enumerate(top_refs):
        meta = doi_to_meta.get(doi, {})
        author = str(meta.get("first_author", "")).split(",")[0].split(";")[0].strip()
        year = str(meta.get("year", ""))
        if year and "." in year:
            year = year.split(".")[0]
        label = f"{author} ({year})" if author and year else doi[:20]
        G.add_node(doi, label=label, citations=int(ref_counts.get(doi, 0)))

    for i in range(TOP_N):
        for j in range(i + 1, TOP_N):
            w = cocit_dense[i, j]
            if w >= min_cocit:
                G.add_edge(top_refs[i], top_refs[j], weight=w)

    isolates = list(nx.isolates(G))
    G.remove_nodes_from(isolates)
    log.info("Network: %d nodes, %d edges", G.number_of_nodes(), G.number_of_edges())
    log.info("Removed %d isolated nodes (co-cited < %d times with any other top ref)",
             len(isolates), min_cocit)
    return G


def detect_communities(G):
    """Run Louvain community detection on the network."""
    partition = community_louvain.best_partition(G, weight="weight", random_state=42)
    n_communities = len(set(partition.values()))
    log.info("Communities detected: %d", n_communities)
    nx.set_node_attributes(G, partition, "community")
    return partition, n_communities


def save_community_data(G, partition, ref_counts, doi_to_meta, output_path):
    """Save community assignments and summary table."""
    community_data = []
    for doi, comm in partition.items():
        meta = doi_to_meta.get(doi, {})
        community_data.append({
            "doi": doi,
            "community": comm,
            "label": G.nodes[doi].get("label", ""),
            "title": str(meta.get("title", "") or ""),
            "first_author": str(meta.get("first_author", "") or ""),
            "year": meta.get("year", ""),
            "citations": ref_counts.get(doi, 0),
        })

    comm_df = pd.DataFrame(community_data).sort_values(
        ["community", "citations"], ascending=[True, False]
    )
    comm_df.to_csv(output_path, index=False)
    log.info("Saved community assignments -> %s", output_path)

    # Summary table: top 5 works per community
    summary_rows = []
    for c in sorted(comm_df["community"].unique()):
        members = comm_df[comm_df["community"] == c]
        top5 = members.head(5)
        for _, row in top5.iterrows():
            summary_rows.append({
                "community": c,
                "community_size": len(members),
                "author_year": row["label"],
                "title": str(row["title"] or "")[:80],
                "citations": row["citations"],
            })

    summary_df = pd.DataFrame(summary_rows)
    tables_dir = os.path.join(BASE_DIR, "content", "tables")
    os.makedirs(tables_dir, exist_ok=True)
    summary_path = os.path.join(tables_dir, "tab_community_summary.csv")
    summary_df.to_csv(summary_path, index=False)
    log.info("Saved community summary -> %s", summary_path)

    log.info("=== Community profiles ===")
    for c in sorted(comm_df["community"].unique()):
        members = comm_df[comm_df["community"] == c]
        log.info("Community %d (%d works):", c, len(members))
        for _, row in members.head(5).iterrows():
            title_short = str(row["title"] or "")[:60]
            log.info("  [%3d] %-30s %s", row['citations'], row['label'], title_short)

    return comm_df


def run_robustness(G, tables_dir):
    """Louvain resolution sensitivity analysis (R3)."""
    from sklearn.metrics import adjusted_rand_score

    log.info("=== Robustness: Louvain resolution sensitivity ===")

    resolutions = [0.5, 1.0, 1.5, 2.0]
    partitions = {}

    try:
        for gamma in resolutions:
            part = community_louvain.best_partition(
                G, weight="weight", resolution=gamma, random_state=42
            )
            partitions[gamma] = part
            n_c = len(set(part.values()))
            log.info("  gamma=%.1f: %d communities", gamma, n_c)

        # Build sensitivity table
        common_nodes = list(G.nodes())
        sens_rows = []
        for doi in common_nodes:
            row = {"doi": doi}
            for gamma in resolutions:
                col = f"community_g{str(gamma).replace('.', '')}"
                row[col] = partitions[gamma].get(doi, -1)
            sens_rows.append(row)

        sens_df = pd.DataFrame(sens_rows)
        sens_path = os.path.join(tables_dir, "tab_louvain_sensitivity.csv")
        sens_df.to_csv(sens_path, index=False)
        log.info("Saved Louvain sensitivity -> %s", sens_path)

        # ARI between resolution levels
        log.info("  Pairwise ARI:")
        for i, g1 in enumerate(resolutions):
            for g2 in resolutions[i + 1:]:
                labels1 = [partitions[g1][n] for n in common_nodes]
                labels2 = [partitions[g2][n] for n in common_nodes]
                ari = adjusted_rand_score(labels1, labels2)
                log.info("    gamma=%.1f vs gamma=%.1f: ARI=%.3f", g1, g2, ari)

    except TypeError:
        log.warning("community_louvain.best_partition does not support 'resolution'.")
        log.warning("Skipping R3 sensitivity analysis.")


def main():
    io_args, extra = parse_io_args()
    validate_io(output=io_args.output)

    parser = argparse.ArgumentParser()
    parser.add_argument("--robustness", action="store_true",
                        help="Run Louvain resolution sensitivity (R3)")
    args = parser.parse_args(extra)

    # --- Load data ---
    cit = load_citation_data()
    doi_to_meta = build_doi_metadata(cit)

    # --- Identify most-cited references ---
    ref_counts = cit.groupby("ref_doi").size().sort_values(ascending=False)
    log.info("Unique cited DOIs: %d", len(ref_counts))
    log.info("Top 10 most cited:")
    for doi, count in ref_counts.head(10).items():
        meta = doi_to_meta.get(doi, {})
        author = meta.get("first_author", "?")
        year = meta.get("year", "?")
        title = str(meta.get("title", "") or "")[:60]
        log.info("  %4dx  %s (%s) %s  [%s]", count, author, year, title, doi)

    top_refs = ref_counts.head(TOP_N).index.tolist()
    top_set = set(top_refs)
    ref_to_idx = {ref: i for i, ref in enumerate(top_refs)}

    log.info("Using top %d most-cited references for co-citation matrix", TOP_N)

    # --- Build co-citation matrix ---
    cocit_dense = build_cocitation_matrix(cit, top_refs, top_set, ref_to_idx)

    # --- Build network and detect communities ---
    min_cocit = MIN_COCIT
    G = build_network(top_refs, ref_counts, doi_to_meta, cocit_dense, min_cocit)

    if G.number_of_nodes() < 5:
        log.warning("Too few connected nodes. Trying MIN_COCIT=2.")
        min_cocit = 2
        G = build_network(top_refs, ref_counts, doi_to_meta, cocit_dense, min_cocit)

    partition, _n_communities = detect_communities(G)

    # --- Save outputs ---
    output_path = io_args.output
    save_community_data(G, partition, ref_counts, doi_to_meta, output_path)

    # --- Optional robustness ---
    if args.robustness:
        tables_dir = os.path.join(BASE_DIR, "content", "tables")
        run_robustness(G, tables_dir)

    log.info("Done.")


if __name__ == "__main__":
    main()
