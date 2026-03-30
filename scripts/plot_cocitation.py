"""Co-citation network visualization.

Reads community assignments from communities.csv and the citation graph,
then renders a spring-layout network figure with community coloring.

Produces:
  content/figures/fig_communities.png
"""

import argparse
import os

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd
from pipeline_io import save_figure
from script_io_args import parse_io_args, validate_io
from utils import get_logger

log = get_logger("plot_cocitation")

DPI = 150


def main():
    io_args, extra = parse_io_args()
    validate_io(output=io_args.output)

    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", action="store_true", help="Also save PDF")
    args = parser.parse_args(extra)

    # --input expects: communities.csv
    if not io_args.input:
        raise SystemExit("--input required: path to communities.csv")
    communities_path = io_args.input[0]

    # --- Load community data ---
    comm_df = pd.read_csv(communities_path)
    log.info("Loaded %d community members from %s", len(comm_df), communities_path)

    # --- Rebuild the network from community data ---
    # We need the co-citation edges. Re-derive from citations would duplicate
    # compute logic. Instead, we build a visual-only graph: nodes from
    # communities.csv, edges approximated by community membership (fully
    # connected within community with uniform weight). This is acceptable
    # because the original script's visualization used the same partition-based
    # coloring — the layout is aesthetic, not analytical.
    #
    # However, to preserve visual fidelity with the original, we read the
    # citation data and rebuild edges the same way the analyze script does.
    from scipy.sparse import lil_matrix
    from utils import CATALOGS_DIR, load_refined_citations, normalize_doi

    cit = load_refined_citations()
    cit["source_doi"] = cit["source_doi"].apply(normalize_doi)
    cit["ref_doi"] = cit["ref_doi"].apply(normalize_doi)
    cit = cit[(cit["source_doi"] != "") & (cit["ref_doi"] != "")]
    cit = cit[~cit["source_doi"].isin(["nan", "none"])]
    cit = cit[~cit["ref_doi"].isin(["nan", "none"])]

    # Use community DOIs as the node set
    top_refs = comm_df["doi"].tolist()
    top_set = set(top_refs)
    ref_to_idx = {ref: i for i, ref in enumerate(top_refs)}
    n = len(top_refs)

    # Build co-citation matrix
    source_groups = cit.groupby("source_doi")["ref_doi"].apply(list)
    cocit_matrix = lil_matrix((n, n), dtype=np.float64)

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

    # Build graph
    G = nx.Graph()
    for _, row in comm_df.iterrows():
        G.add_node(
            row["doi"],
            label=row["label"],
            citations=int(row["citations"]),
            community=int(row["community"]),
        )

    # Determine min_cocit: try 3, fall back to 2
    min_cocit = 3
    for i in range(n):
        for j in range(i + 1, n):
            w = cocit_dense[i, j]
            if w >= min_cocit:
                G.add_edge(top_refs[i], top_refs[j], weight=w)

    isolates = list(nx.isolates(G))
    G.remove_nodes_from(isolates)

    if G.number_of_nodes() < 5:
        log.warning("Too few nodes with MIN_COCIT=3, rebuilding with 2")
        # Rebuild
        G = nx.Graph()
        for _, row in comm_df.iterrows():
            G.add_node(
                row["doi"],
                label=row["label"],
                citations=int(row["citations"]),
                community=int(row["community"]),
            )
        min_cocit = 2
        for i in range(n):
            for j in range(i + 1, n):
                w = cocit_dense[i, j]
                if w >= min_cocit:
                    G.add_edge(top_refs[i], top_refs[j], weight=w)
        isolates = list(nx.isolates(G))
        G.remove_nodes_from(isolates)

    log.info("Network for plotting: %d nodes, %d edges", G.number_of_nodes(), G.number_of_edges())

    # --- Visualization ---
    partition = {n: G.nodes[n]["community"] for n in G.nodes()}
    n_communities = len(set(partition.values()))

    palette = plt.cm.Set2(np.linspace(0, 1, max(n_communities, 3)))
    node_colors = [palette[partition[node]] for node in G.nodes()]

    citations_arr = np.array([G.nodes[node]["citations"] for node in G.nodes()])
    node_sizes = 50 + 300 * np.sqrt(citations_arr / citations_arr.max())

    log.info("Computing layout...")
    pos = nx.spring_layout(G, weight="weight", k=1.5, iterations=100, seed=42)

    edge_weights = [G[u][v]["weight"] for u, v in G.edges()]
    max_w = max(edge_weights) if edge_weights else 1
    edge_widths = [0.3 + 2.0 * w / max_w for w in edge_weights]

    fig, ax = plt.subplots(figsize=(14, 10))

    nx.draw_networkx_edges(
        G, pos, ax=ax,
        width=edge_widths,
        alpha=0.15,
        edge_color="grey",
    )

    nx.draw_networkx_nodes(
        G, pos, ax=ax,
        node_color=node_colors,
        node_size=node_sizes,
        alpha=0.85,
        edgecolors="white",
        linewidths=0.5,
    )

    # Label only the most-cited nodes (top 30)
    top_nodes = sorted(G.nodes(), key=lambda node: G.nodes[node]["citations"], reverse=True)[:30]
    labels = {node: G.nodes[node]["label"] for node in top_nodes}
    nx.draw_networkx_labels(
        G, pos, labels, ax=ax,
        font_size=7,
        font_weight="bold",
    )

    # Legend for communities
    for c in sorted(set(partition.values())):
        members = [node for node, comm in partition.items() if comm == c]
        ax.scatter([], [], c=[palette[c]], s=80,
                   label=f"Community {c} (n={len(members)})")
    ax.legend(loc="upper left", fontsize=9, framealpha=0.9)

    ax.set_title(
        "Co-citation network: intellectual communities in climate finance literature",
        fontsize=13, pad=15,
    )
    ax.axis("off")

    plt.tight_layout()

    out_stem = os.path.splitext(io_args.output)[0]
    save_figure(fig, out_stem, pdf=args.pdf, dpi=DPI)
    log.info("Saved communities figure -> %s", io_args.output)

    plt.close()
    log.info("Done.")


if __name__ == "__main__":
    main()
