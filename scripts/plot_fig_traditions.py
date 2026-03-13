"""Pre-2007 co-citation network: three intellectual traditions.

Method: Louvain community detection on co-citation graph of the 250 most-cited
pre-2007 references. Three communities are identified as intellectual traditions
by matching anchor authors; the remaining seven are rendered as background.

Produces:
  content/figures/fig_traditions.png
  content/figures/fig_traditions.pdf
"""

import os
import sys

import community as community_louvain
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import networkx as nx
import numpy as np
import pandas as pd
from scipy.sparse import lil_matrix

# Add scripts dir to path for local imports
sys.path.insert(0, os.path.dirname(__file__))
from plot_style import apply_style, DARK, MED, LIGHT, FIGWIDTH, DPI
from utils import BASE_DIR, CATALOGS_DIR, load_refined_citations, normalize_doi

apply_style()

FIGURES_DIR = os.path.join(BASE_DIR, "content", "figures")
os.makedirs(FIGURES_DIR, exist_ok=True)

# --- Parameters ---
CUTOFF_YEAR = 2006
TOP_N = 250
MIN_COCIT = 3
RANDOM_STATE = 42

# Anchor author surnames (lowercase) used to label each tradition community.
# A community is assigned to the tradition for which it has the most anchor matches.
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

# Grayscale shades for three traditions + background
TRADITION_COLORS = {
    "pricing": DARK,       # "#333333"
    "cdm":     MED,        # "#777777"
    "unfccc":  "#AAAAAA",
    "other":   "#DDDDDD",
}
TRADITION_EDGE_COLORS = {
    "pricing": DARK,
    "cdm":     MED,
    "unfccc":  "#888888",
    "other":   "#CCCCCC",
}

# ============================================================
# Load data
# ============================================================

print("Loading citations...")
cit = load_refined_citations()
cit["source_doi"] = cit["source_doi"].apply(normalize_doi)
cit["ref_doi"]    = cit["ref_doi"].apply(normalize_doi)
cit = cit[(cit["source_doi"] != "") & (cit["ref_doi"] != "")]
cit = cit[~cit["source_doi"].isin(["nan", "none"])]
cit = cit[~cit["ref_doi"].isin(["nan", "none"])]
print(f"  Citation pairs: {len(cit)}")

# Load works for metadata
works = pd.read_csv(os.path.join(CATALOGS_DIR, "refined_works.csv"))
works["doi_norm"] = works["doi"].apply(normalize_doi)
doi_meta = {}
for _, row in works.iterrows():
    d = row["doi_norm"]
    if d and d not in ("nan", "none"):
        doi_meta[d] = {
            "title": str(row.get("title", "") or ""),
            "author": str(row.get("first_author", "") or ""),
            "year":   row.get("year", ""),
        }
# Fill gaps from citation records
for _, row in cit.iterrows():
    d = row["ref_doi"]
    if d and d not in ("nan", "none") and d not in doi_meta:
        doi_meta[d] = {
            "title":  str(row.get("ref_title", "") or ""),
            "author": str(row.get("ref_first_author", "") or ""),
            "year":   row.get("ref_year", "") or "",
        }

# ============================================================
# Filter to pre-2007 references
# ============================================================

# Use row-level year filter (same as compare_communities_across_windows.py):
# a ref is "pre-CUTOFF" if ANY citation row for it has ref_year <= cutoff.
# This avoids missing refs where year is populated in some rows but not others.
cit["ref_year_num"] = pd.to_numeric(cit["ref_year"], errors="coerce")
pre_dois = (
    set(cit.loc[cit["ref_year_num"] <= CUTOFF_YEAR, "ref_doi"])
    - {"", "nan", "none"}
)

ref_counts_all = cit.groupby("ref_doi").size()
ref_counts = ref_counts_all.loc[ref_counts_all.index.isin(pre_dois)].sort_values(ascending=False)
print(f"  Pre-{CUTOFF_YEAR} refs: {len(ref_counts)} (cited >= 1)")

top_refs = ref_counts.head(TOP_N).index.tolist()
top_set  = set(top_refs)
ref_to_idx = {r: i for i, r in enumerate(top_refs)}
print(f"  Using top {TOP_N}; citation range: {ref_counts.iloc[0]} .. {ref_counts.iloc[TOP_N - 1]}")

# ============================================================
# Build co-citation matrix (only papers published pre-2007)
# ============================================================

print("Building co-citation matrix...")
# Use ALL source papers (any year) — we filter only the *referenced* papers by year.
# This counts how often pre-2007 foundational works are cited together, regardless
# of when the citing paper was published.
source_groups = cit.groupby("source_doi")["ref_doi"].apply(list)

cocit = lil_matrix((TOP_N, TOP_N), dtype=np.float32)
for _, ref_list in source_groups.items():
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
print(f"  Non-zero co-citation pairs: {np.count_nonzero(cocit_dense) // 2}")

# ============================================================
# Build network and detect communities
# ============================================================

G = nx.Graph()
for doi in top_refs:
    meta = doi_meta.get(doi, {})
    author = str(meta.get("author", "") or "").split(",")[0].split(";")[0].strip()
    year   = str(meta.get("year", "") or "")
    title  = str(meta.get("title", "") or "")
    if "." in year:
        year = year.split(".")[0]
    # Build label: prefer "Author Year", fall back to title fragment, then DOI
    if author and author.lower() not in ("nan", "none", "") and year and year not in ("nan", "none", ""):
        label = f"{author} {year}"
    elif title and title.lower() not in ("nan", "none", ""):
        # Use first 3 meaningful words of title
        words = [w for w in title.split() if len(w) > 2][:3]
        label = " ".join(words) + (f" {year}" if year and year not in ("nan", "none") else "")
    else:
        label = doi.split("/")[-1][:16]
    G.add_node(doi, label=label, citations=int(ref_counts.get(doi, 0)),
               author=author.lower())

for i in range(TOP_N):
    for j in range(i + 1, TOP_N):
        w = cocit_dense[i, j]
        if w >= MIN_COCIT:
            G.add_edge(top_refs[i], top_refs[j], weight=float(w))

isolates = list(nx.isolates(G))
G.remove_nodes_from(isolates)
print(f"\nNetwork: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
print(f"  Removed {len(isolates)} isolates")

partition = community_louvain.best_partition(G, weight="weight", random_state=RANDOM_STATE)
n_comm = len(set(partition.values()))
modularity = community_louvain.modularity(partition, G, weight="weight")
print(f"  Louvain: {n_comm} communities, modularity={modularity:.4f}")

# ============================================================
# Identify which community maps to which tradition
# ============================================================

# For each community, count how many of its nodes match each tradition's anchors
comm_to_nodes = {}
for doi, c in partition.items():
    comm_to_nodes.setdefault(c, []).append(doi)

def count_anchor_matches(nodes, anchors):
    count = 0
    for doi in nodes:
        author = G.nodes[doi].get("author", "")
        if any(a in author for a in anchors):
            count += 1
    return count

# Score each (community, tradition) pair
scores = {}
for c, nodes in comm_to_nodes.items():
    for trad, anchors in TRADITION_ANCHORS.items():
        scores[(c, trad)] = count_anchor_matches(nodes, anchors)

# Greedy assignment: highest score first, no community or tradition reused
comm_to_tradition = {}
trad_to_comm = {}
assigned_comms  = set()
assigned_trads  = set()

sorted_pairs = sorted(scores.items(), key=lambda x: -x[1])
for (c, trad), score in sorted_pairs:
    if score == 0:
        break
    if c in assigned_comms or trad in assigned_trads:
        continue
    comm_to_tradition[c] = trad
    trad_to_comm[trad] = c
    assigned_comms.add(c)
    assigned_trads.add(trad)

# Remaining communities → "other"
for c in comm_to_nodes:
    if c not in comm_to_tradition:
        comm_to_tradition[c] = "other"

print("\nTradition assignments:")
for trad, c in trad_to_comm.items():
    nodes = comm_to_nodes[c]
    top3  = sorted(nodes, key=lambda d: -ref_counts.get(d, 0))[:3]
    names = [G.nodes[d]["label"] for d in top3]
    print(f"  {trad:10s} → community {c} (n={len(nodes)}): {', '.join(names)}")

# ============================================================
# Compute layout
# ============================================================

print("\nComputing layout...")
pos = nx.spring_layout(G, weight="weight", k=2.5, iterations=200, seed=RANDOM_STATE)

# ============================================================
# Plot
# ============================================================

fig_w = FIGWIDTH * 1.6   # slightly wider than standard for a network figure
fig_h = fig_w * 0.75
fig, ax = plt.subplots(figsize=(fig_w, fig_h))

# --- Edges (draw first, behind nodes) ---
edge_colors = []
edge_widths  = []
all_weights  = [G[u][v]["weight"] for u, v in G.edges()]
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

nx.draw_networkx_edges(G, pos, ax=ax,
                       edge_color=edge_colors, width=edge_widths, alpha=0.6)

# --- Nodes ---
cit_arr = np.array([G.nodes[n]["citations"] for n in G.nodes()])
node_sizes  = 30 + 250 * np.sqrt(cit_arr / cit_arr.max())
node_colors = [TRADITION_COLORS[comm_to_tradition.get(partition[n], "other")]
               for n in G.nodes()]
node_borders = ["white" for _ in G.nodes()]

nx.draw_networkx_nodes(G, pos, ax=ax,
                       node_color=node_colors, node_size=node_sizes,
                       edgecolors=node_borders, linewidths=0.4, alpha=0.9)

# --- Labels: top-cited nodes per tradition + top-cited overall ---
# For each tradition community, label the top 5 most-cited nodes.
# For other communities, label top 3 overall if highly cited.
label_nodes = set()
for trad, c in trad_to_comm.items():
    nodes_sorted = sorted(comm_to_nodes[c],
                          key=lambda d: -ref_counts.get(d, 0))
    label_nodes.update(nodes_sorted[:5])

# Also label a few prominent "other" nodes for context
other_nodes = [d for d, t in
               ((d, comm_to_tradition[partition[d]]) for d in G.nodes())
               if t == "other"]
other_sorted = sorted(other_nodes, key=lambda d: -ref_counts.get(d, 0))
label_nodes.update(other_sorted[:4])

# Only label nodes with a meaningful name — skip bare DOI fragments.
# A label is a DOI fragment if it has no space (no "Author Year" structure)
# or starts with digits/DOI-like patterns.
def is_meaningful_label(lbl):
    if " " not in lbl:
        return False  # no space → DOI fragment or single token
    if lbl.startswith("10."):
        return False
    return True

labels = {n: G.nodes[n]["label"] for n in label_nodes
          if n in G.nodes() and is_meaningful_label(G.nodes[n]["label"])}

nx.draw_networkx_labels(G, pos, labels, ax=ax,
                        font_size=5.5, font_color=DARK,
                        bbox=dict(boxstyle="round,pad=0.15", fc="white",
                                  ec="none", alpha=0.7))

# --- Legend ---
legend_handles = []
for trad in ("pricing", "cdm", "unfccc"):
    c = trad_to_comm.get(trad)
    if c is None:
        continue
    n = len(comm_to_nodes[c])
    label = TRADITION_LABELS[trad] + f"  (n={n})"
    patch = mpatches.Patch(facecolor=TRADITION_COLORS[trad],
                           edgecolor="white", linewidth=0.5, label=label)
    legend_handles.append(patch)

other_count = sum(len(v) for c, v in comm_to_nodes.items()
                  if comm_to_tradition[c] == "other")
legend_handles.append(
    mpatches.Patch(facecolor=TRADITION_COLORS["other"],
                   edgecolor="white", linewidth=0.5,
                   label=f"Other communities  (n={other_count})"))

ax.legend(handles=legend_handles, loc="lower left",
          framealpha=0.9, edgecolor=DARK, fontsize=6,
          handlelength=1.2, handleheight=1.0)

ax.set_title(
    f"Co-citation communities in pre-{CUTOFF_YEAR + 1} climate finance scholarship\n"
    f"(top {TOP_N} most-cited references, {n_comm} communities, "
    f"modularity={modularity:.2f})",
    fontsize=7, pad=8)
ax.axis("off")

plt.tight_layout(pad=0.5)

out_png = os.path.join(FIGURES_DIR, "fig_traditions.png")
out_pdf = os.path.join(FIGURES_DIR, "fig_traditions.pdf")
fig.savefig(out_pdf, bbox_inches="tight")
fig.savefig(out_png, dpi=DPI, bbox_inches="tight")
print(f"\nSaved → {out_png}")
print(f"Saved → {out_pdf}")
plt.close()
