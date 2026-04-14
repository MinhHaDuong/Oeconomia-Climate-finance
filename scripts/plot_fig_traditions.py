"""Pre-2007 co-citation network: three intellectual traditions.

Method: Louvain community detection on co-citation graph of the 250 most-cited
pre-2007 references. Three communities are identified as intellectual traditions
by matching anchor authors; the remaining seven are rendered as background.

Produces:
  content/figures/fig_traditions.png
  content/figures/fig_traditions.pdf

Usage:
    uv run python scripts/plot_fig_traditions.py --output content/figures/fig_traditions.png
    uv run python scripts/plot_fig_traditions.py --output content/figures/fig_traditions.png \
        --input refined_works.csv refined_citations.csv
"""

import argparse
import os

import community as community_louvain
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd

from pipeline_io import save_figure
from plot_style import DARK, DPI, FIGWIDTH, apply_style
from scipy.sparse import lil_matrix
from script_io_args import parse_io_args, validate_io
from utils import (
    BASE_DIR,
    CATALOGS_DIR,
    get_logger,
    load_refined_citations,
    normalize_doi,
)

log = get_logger("plot_fig_traditions")

# --- Parameters ---
CUTOFF_YEAR = 2006
TOP_N = 250
MIN_COCIT = 3
RANDOM_STATE = 42

TRADITION_ANCHORS = {
    "pricing": ["weitzman", "barrett", "carraro", "montgomery", "pizer"],
    "cdm":     ["michaelowa", "sutter", "ellis", "haites", "pearson"],
    "unfccc":  ["north", "dimaggio", "finnemore"],
}

TRADITION_LABELS = {
    "pricing": "Environmental economics\n(pricing & quantities)",
    "cdm":     "Development economics\n(CDM & carbon markets)",
    "unfccc":  "Burden-sharing\n(UNFCCC & institutions)",
    "other":   None,
}

TRADITION_COLORS = {
    "pricing": "#1a6496",
    "cdm":     "#e07b39",
    "unfccc":  "#4a9e6b",
    "other":   "#DDDDDD",
}
TRADITION_EDGE_COLORS = {
    "pricing": "#1a6496",
    "cdm":     "#e07b39",
    "unfccc":  "#4a9e6b",
    "other":   "#CCCCCC",
}


def _load_data(works_path, cit_path):
    """Load citations and works, build DOI metadata lookup."""
    log.info("Loading citations...")
    if cit_path is not None:
        cit = pd.read_csv(cit_path, low_memory=False)
    else:
        cit = load_refined_citations()
    cit["source_doi"] = cit["source_doi"].apply(normalize_doi)
    cit["ref_doi"] = cit["ref_doi"].apply(normalize_doi)
    cit = cit[(cit["source_doi"] != "") & (cit["ref_doi"] != "")]
    cit = cit[~cit["source_doi"].isin(["nan", "none"])]
    cit = cit[~cit["ref_doi"].isin(["nan", "none"])]
    log.info("  Citation pairs: %d", len(cit))

    works = pd.read_csv(works_path)
    works["doi_norm"] = works["doi"].apply(normalize_doi)
    doi_meta = {}
    for _, row in works.iterrows():
        d = row["doi_norm"]
        if d and d not in ("nan", "none"):
            doi_meta[d] = {
                "title": str(row.get("title", "") or ""),
                "author": str(row.get("first_author", "") or ""),
                "year": row.get("year", ""),
            }
    for _, row in cit.iterrows():
        d = row["ref_doi"]
        if d and d not in ("nan", "none") and d not in doi_meta:
            doi_meta[d] = {
                "title": str(row.get("ref_title", "") or ""),
                "author": str(row.get("ref_first_author", "") or ""),
                "year": row.get("ref_year", "") or "",
            }
    return cit, doi_meta


def _build_cocitation_network(cit, doi_meta, ref_counts, top_refs):
    """Build co-citation graph from top references."""
    actual_top_n = len(top_refs)
    top_set = set(top_refs)
    ref_to_idx = {r: i for i, r in enumerate(top_refs)}

    log.info("Building co-citation matrix...")
    source_groups = cit.groupby("source_doi")["ref_doi"].apply(list)

    cocit = lil_matrix((actual_top_n, actual_top_n), dtype=np.float32)
    for ref_list in source_groups.values:
        in_top = [r for r in ref_list if r in top_set]
        if len(in_top) < 2:
            continue
        for i in range(len(in_top)):
            for j in range(i + 1, len(in_top)):
                a = ref_to_idx[in_top[i]]
                b = ref_to_idx[in_top[j]]
                cocit[a, b] += 1
                cocit[b, a] += 1

    cocit_dense = cocit.toarray()
    log.info("  Non-zero co-citation pairs: %d",
             np.count_nonzero(cocit_dense) // 2)

    G = nx.Graph()
    for doi in top_refs:
        meta = doi_meta.get(doi, {})
        author = (str(meta.get("author", "") or "")
                  .split(",")[0].split(";")[0].strip())
        year = str(meta.get("year", "") or "")
        title = str(meta.get("title", "") or "")
        if "." in year:
            year = year.split(".")[0]
        label = _make_node_label(author, year, title, doi)
        G.add_node(doi, label=label,
                   citations=int(ref_counts.get(doi, 0)),
                   author=author.lower())

    for i in range(actual_top_n):
        for j in range(i + 1, actual_top_n):
            w = cocit_dense[i, j]
            if w >= MIN_COCIT:
                G.add_edge(top_refs[i], top_refs[j], weight=float(w))

    isolates = list(nx.isolates(G))
    G.remove_nodes_from(isolates)
    log.info("Network: %d nodes, %d edges",
             G.number_of_nodes(), G.number_of_edges())
    log.info("  Removed %d isolates", len(isolates))
    return G


def _make_node_label(author, year, title, doi):
    """Create a readable label for a network node."""
    if (author and author.lower() not in ("nan", "none", "")
            and year and year not in ("nan", "none", "")):
        return f"{author} {year}"
    if title and title.lower() not in ("nan", "none", ""):
        words = [w for w in title.split() if len(w) > 2][:3]
        suffix = f" {year}" if year and year not in ("nan", "none") else ""
        return " ".join(words) + suffix
    return doi.split("/")[-1][:16]


def _assign_traditions(G, partition):
    """Map Louvain communities to named traditions via anchor matching."""
    comm_to_nodes = {}
    for doi, c in partition.items():
        comm_to_nodes.setdefault(c, []).append(doi)

    scores = {}
    for c, nodes in comm_to_nodes.items():
        for trad, anchors in TRADITION_ANCHORS.items():
            count = sum(
                1 for doi in nodes
                if any(a in G.nodes[doi].get("author", "")
                       for a in anchors)
            )
            scores[(c, trad)] = count

    comm_to_tradition = {}
    trad_to_comm = {}
    assigned_comms = set()
    assigned_trads = set()

    for (c, trad), score in sorted(scores.items(), key=lambda x: -x[1]):
        if score == 0:
            break
        if c in assigned_comms or trad in assigned_trads:
            continue
        comm_to_tradition[c] = trad
        trad_to_comm[trad] = c
        assigned_comms.add(c)
        assigned_trads.add(trad)

    for c in comm_to_nodes:
        if c not in comm_to_tradition:
            comm_to_tradition[c] = "other"

    return comm_to_tradition, trad_to_comm, comm_to_nodes


def _render_traditions(G, partition, pos, comm_to_tradition,
                       trad_to_comm, comm_to_nodes, ref_counts,
                       actual_top_n, n_comm, modularity,
                       out_stem, pdf):
    """Render the traditions network figure."""
    fig_w = FIGWIDTH * 1.6
    fig_h = fig_w * 0.75
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))

    # Edges
    edge_colors, edge_widths = [], []
    all_weights = [G[u][v]["weight"] for u, v in G.edges()]
    max_w = max(all_weights) if all_weights else 1.0

    for u, v in G.edges():
        t_u = comm_to_tradition.get(partition[u], "other")
        t_v = comm_to_tradition.get(partition[v], "other")
        if t_u == t_v and t_u != "other":
            edge_colors.append(TRADITION_EDGE_COLORS[t_u])
            edge_widths.append(0.5 + 1.5 * G[u][v]["weight"] / max_w)
        else:
            edge_colors.append("#E0E0E0")
            edge_widths.append(0.2)

    nx.draw_networkx_edges(G, pos, ax=ax, edge_color=edge_colors,
                           width=edge_widths, alpha=0.6)

    # Nodes
    cit_arr = np.array([G.nodes[n]["citations"] for n in G.nodes()])
    node_sizes = 30 + 250 * np.sqrt(cit_arr / cit_arr.max())
    node_colors = [
        TRADITION_COLORS[comm_to_tradition.get(partition[n], "other")]
        for n in G.nodes()
    ]
    nx.draw_networkx_nodes(G, pos, ax=ax, node_color=node_colors,
                           node_size=node_sizes, edgecolors="white",
                           linewidths=0.4, alpha=0.9)

    # Labels
    _draw_labels(ax, G, pos, trad_to_comm, comm_to_nodes, ref_counts)

    # Legend
    _draw_legend(ax, trad_to_comm, comm_to_nodes, comm_to_tradition)

    ax.set_title(
        f"Co-citation communities in pre-{CUTOFF_YEAR + 1} "
        f"climate finance scholarship\n"
        f"(top {actual_top_n} most-cited references, "
        f"{n_comm} communities, modularity={modularity:.2f})",
        fontsize=7, pad=8)
    ax.axis("off")
    plt.tight_layout(pad=0.5)

    save_figure(fig, out_stem, pdf=pdf, dpi=DPI)
    plt.close()


def _draw_labels(ax, G, pos, trad_to_comm, comm_to_nodes, ref_counts):
    """Draw node labels for top-cited nodes per tradition."""
    label_nodes = set()
    for trad, c in trad_to_comm.items():
        nodes_sorted = sorted(
            comm_to_nodes[c], key=lambda d: -ref_counts.get(d, 0))
        label_nodes.update(nodes_sorted[:5])

    other_nodes = sorted(
        [d for d in G.nodes()
         if d not in {n for s in
                      [comm_to_nodes.get(trad_to_comm.get(t), [])
                       for t in TRADITION_ANCHORS]
                      for n in s}],
        key=lambda d: -ref_counts.get(d, 0))
    label_nodes.update(other_nodes[:4])

    labels = {
        n: G.nodes[n]["label"] for n in label_nodes
        if n in G.nodes() and " " in G.nodes[n]["label"]
        and not G.nodes[n]["label"].startswith("10.")
    }
    nx.draw_networkx_labels(
        G, pos, labels, ax=ax, font_size=5.5, font_color=DARK,
        bbox=dict(boxstyle="round,pad=0.15", fc="white",
                  ec="none", alpha=0.7))


def _draw_legend(ax, trad_to_comm, comm_to_nodes, comm_to_tradition):
    """Draw tradition legend."""
    legend_handles = []
    for trad in ("pricing", "cdm", "unfccc"):
        c = trad_to_comm.get(trad)
        if c is None:
            continue
        n = len(comm_to_nodes[c])
        label = TRADITION_LABELS[trad] + f"  (n={n})"
        patch = mpatches.Patch(
            facecolor=TRADITION_COLORS[trad],
            edgecolor="white", linewidth=0.5, label=label)
        legend_handles.append(patch)

    other_count = sum(
        len(v) for c, v in comm_to_nodes.items()
        if comm_to_tradition[c] == "other")
    legend_handles.append(
        mpatches.Patch(
            facecolor=TRADITION_COLORS["other"],
            edgecolor="white", linewidth=0.5,
            label=f"Other communities  (n={other_count})"))

    ax.legend(handles=legend_handles, loc="lower left",
              framealpha=0.9, edgecolor=DARK, fontsize=6,
              handlelength=1.2, handleheight=1.0)


def main():
    io_args, extra = parse_io_args()
    validate_io(output=io_args.output, inputs=io_args.input)

    parser = argparse.ArgumentParser(
        description="Pre-2007 co-citation traditions network")
    parser.add_argument("--pdf", action="store_true",
                        help="Also save PDF output")
    args = parser.parse_args(extra)

    apply_style()
    out_stem = os.path.splitext(io_args.output)[0]

    works_path = (
        io_args.input[0] if io_args.input
        else os.path.join(CATALOGS_DIR, "refined_works.csv")
    )
    cit_path = (
        io_args.input[1] if io_args.input and len(io_args.input) >= 2
        else None
    )

    cit, doi_meta = _load_data(works_path, cit_path)

    # Filter to pre-2007 references
    cit["ref_year_num"] = pd.to_numeric(cit["ref_year"], errors="coerce")
    pre_dois = (
        set(cit.loc[cit["ref_year_num"] <= CUTOFF_YEAR, "ref_doi"])
        - {"", "nan", "none"}
    )

    ref_counts_all = cit.groupby("ref_doi").size()
    ref_counts = ref_counts_all.loc[
        ref_counts_all.index.isin(pre_dois)
    ].sort_values(ascending=False)
    log.info("  Pre-%d refs: %d (cited >= 1)",
             CUTOFF_YEAR, len(ref_counts))

    actual_top_n = min(TOP_N, len(ref_counts))
    if actual_top_n == 0:
        log.info("No pre-%d references found. Creating empty output.",
                 CUTOFF_YEAR)
        open(io_args.output, "w").close()
        return

    top_refs = ref_counts.head(actual_top_n).index.tolist()
    log.info("  Using top %d; citation range: %d .. %d",
             actual_top_n,
             ref_counts.iloc[0],
             ref_counts.iloc[actual_top_n - 1])

    G = _build_cocitation_network(cit, doi_meta, ref_counts, top_refs)

    if G.number_of_nodes() == 0:
        log.info("Empty network. Creating empty output.")
        open(io_args.output, "w").close()
        return

    partition = community_louvain.best_partition(
        G, weight="weight", random_state=RANDOM_STATE)
    n_comm = len(set(partition.values()))
    modularity = community_louvain.modularity(
        partition, G, weight="weight")
    log.info("  Louvain: %d communities, modularity=%.4f",
             n_comm, modularity)

    comm_to_tradition, trad_to_comm, comm_to_nodes = _assign_traditions(
        G, partition)

    log.info("Tradition assignments:")
    for trad, c in trad_to_comm.items():
        nodes = comm_to_nodes[c]
        top3 = sorted(nodes, key=lambda d: -ref_counts.get(d, 0))[:3]
        names = [G.nodes[d]["label"] for d in top3]
        log.info("  %10s -> community %d (n=%d): %s",
                 trad, c, len(nodes), ", ".join(names))

    log.info("Computing layout...")
    pos = nx.spring_layout(G, weight="weight", k=2.5,
                           iterations=200, seed=RANDOM_STATE)

    _render_traditions(G, partition, pos, comm_to_tradition,
                       trad_to_comm, comm_to_nodes, ref_counts,
                       actual_top_n, n_comm, modularity,
                       out_stem, args.pdf)

    log.info("Done.")


if __name__ == "__main__":
    main()
