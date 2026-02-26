"""Co-citation analysis of the climate finance corpus.

Method (Small 1973, White & Griffith 1981):
- Two works are co-cited when they appear together in the same reference list.
- We build a co-citation matrix for the most-cited references, then detect
  communities using the Louvain algorithm.

Produces:
- figures/fig2_communities.pdf: Co-citation network with community coloring
- data/catalogs/communities.csv: Community assignments for top-cited works
- tables/tab2_community_summary.csv: Top works per community
"""

import os
from collections import Counter

import community as community_louvain
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd
from scipy.sparse import lil_matrix
from sklearn.metrics.pairwise import cosine_similarity

from utils import BASE_DIR, CATALOGS_DIR, normalize_doi

# --- Paths ---
FIGURES_DIR = os.path.join(BASE_DIR, "figures")
TABLES_DIR = os.path.join(BASE_DIR, "tables")
os.makedirs(FIGURES_DIR, exist_ok=True)
os.makedirs(TABLES_DIR, exist_ok=True)

# --- Load data ---
print("Loading citations...")
cit = pd.read_csv(os.path.join(CATALOGS_DIR, "citations.csv"), low_memory=False)
cit["source_doi"] = cit["source_doi"].apply(normalize_doi)
cit["ref_doi"] = cit["ref_doi"].apply(normalize_doi)

# Keep only rows where both source and ref have valid DOIs
cit = cit[(cit["source_doi"] != "") & (cit["ref_doi"] != "")]
cit = cit[~cit["source_doi"].isin(["nan", "none"])]
cit = cit[~cit["ref_doi"].isin(["nan", "none"])]
print(f"Citation pairs with DOIs: {len(cit)}")

# Load unified works for metadata lookups
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


# ============================================================
# Step 1: Identify most-cited references
# ============================================================

ref_counts = cit.groupby("ref_doi").size().sort_values(ascending=False)
print(f"\nUnique cited DOIs: {len(ref_counts)}")
print(f"Top 10 most cited:")
for doi, count in ref_counts.head(10).items():
    meta = doi_to_meta.get(doi, {})
    author = meta.get("first_author", "?")
    year = meta.get("year", "?")
    title = str(meta.get("title", "") or "")[:60]
    print(f"  {count:4d}x  {author} ({year}) {title}  [{doi}]")

# Take top N most-cited references for co-citation analysis
TOP_N = 200
top_refs = ref_counts.head(TOP_N).index.tolist()
top_set = set(top_refs)
ref_to_idx = {ref: i for i, ref in enumerate(top_refs)}

print(f"\nUsing top {TOP_N} most-cited references for co-citation matrix")


# ============================================================
# Step 2: Build co-citation matrix
# ============================================================

# Group references by source paper
print("Building co-citation matrix...")
source_groups = cit.groupby("source_doi")["ref_doi"].apply(list)

# Count co-citation pairs
cocit_matrix = lil_matrix((TOP_N, TOP_N), dtype=np.float64)

for source_doi, ref_list in source_groups.items():
    # Filter to top refs only
    refs_in_top = [r for r in ref_list if r in top_set]
    if len(refs_in_top) < 2:
        continue
    # All pairs
    for i in range(len(refs_in_top)):
        for j in range(i + 1, len(refs_in_top)):
            a = ref_to_idx[refs_in_top[i]]
            b = ref_to_idx[refs_in_top[j]]
            cocit_matrix[a, b] += 1
            cocit_matrix[b, a] += 1

cocit_dense = cocit_matrix.toarray()
print(f"Non-zero co-citation pairs: {np.count_nonzero(cocit_dense) // 2}")


# ============================================================
# Step 3: Build network and detect communities
# ============================================================

# Build weighted graph from co-citation matrix
G = nx.Graph()
for i, doi in enumerate(top_refs):
    meta = doi_to_meta.get(doi, {})
    author = str(meta.get("first_author", "")).split(",")[0].split(";")[0].strip()
    year = str(meta.get("year", ""))
    if year and "." in year:
        year = year.split(".")[0]
    label = f"{author} ({year})" if author and year else doi[:20]
    G.add_node(doi, label=label, citations=int(ref_counts.get(doi, 0)))

# Add edges (co-citation weight >= threshold)
MIN_COCIT = 3  # Minimum co-citations to form an edge
for i in range(TOP_N):
    for j in range(i + 1, TOP_N):
        w = cocit_dense[i, j]
        if w >= MIN_COCIT:
            G.add_edge(top_refs[i], top_refs[j], weight=w)

# Remove isolated nodes
isolates = list(nx.isolates(G))
G.remove_nodes_from(isolates)
print(f"\nNetwork: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
print(f"Removed {len(isolates)} isolated nodes (co-cited < {MIN_COCIT} times with any other top ref)")

if G.number_of_nodes() < 5:
    print("WARNING: Too few connected nodes. Try lowering MIN_COCIT.")
    MIN_COCIT = 2
    # Rebuild with lower threshold
    G2 = nx.Graph()
    for i, doi in enumerate(top_refs):
        meta = doi_to_meta.get(doi, {})
        author = str(meta.get("first_author", "")).split(",")[0].split(";")[0].strip()
        year = str(meta.get("year", ""))
        if year and "." in year:
            year = year.split(".")[0]
        label = f"{author} ({year})" if author and year else doi[:20]
        G2.add_node(doi, label=label, citations=int(ref_counts.get(doi, 0)))
    for i in range(TOP_N):
        for j in range(i + 1, TOP_N):
            w = cocit_dense[i, j]
            if w >= MIN_COCIT:
                G2.add_edge(top_refs[i], top_refs[j], weight=w)
    isolates2 = list(nx.isolates(G2))
    G2.remove_nodes_from(isolates2)
    G = G2
    print(f"Rebuilt with MIN_COCIT={MIN_COCIT}: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

# Louvain community detection
partition = community_louvain.best_partition(G, weight="weight", random_state=42)
n_communities = len(set(partition.values()))
print(f"Communities detected: {n_communities}")

# Assign community to nodes
nx.set_node_attributes(G, partition, "community")


# ============================================================
# Step 4: Characterize communities
# ============================================================

# Build community summary
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

comm_df = pd.DataFrame(community_data).sort_values(["community", "citations"], ascending=[True, False])
comm_df.to_csv(os.path.join(CATALOGS_DIR, "communities.csv"), index=False)
print(f"\nSaved community assignments → data/catalogs/communities.csv")

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
summary_df.to_csv(os.path.join(TABLES_DIR, "tab2_community_summary.csv"), index=False)
print(f"Saved community summary → tables/tab2_community_summary.csv")

print("\n=== Community profiles ===")
for c in sorted(comm_df["community"].unique()):
    members = comm_df[comm_df["community"] == c]
    print(f"\nCommunity {c} ({len(members)} works):")
    for _, row in members.head(5).iterrows():
        title_short = str(row["title"] or "")[:60]
        print(f"  [{row['citations']:3d}] {row['label']:30s} {title_short}")


# ============================================================
# Step 5: Visualize
# ============================================================

# Color palette for communities
palette = plt.cm.Set2(np.linspace(0, 1, max(n_communities, 3)))
node_colors = [palette[partition[n]] for n in G.nodes()]

# Node sizes proportional to citation count (sqrt scale)
citations_arr = np.array([G.nodes[n]["citations"] for n in G.nodes()])
node_sizes = 50 + 300 * np.sqrt(citations_arr / citations_arr.max())

# Layout
print("\nComputing layout...")
pos = nx.spring_layout(G, weight="weight", k=1.5, iterations=100, seed=42)

# Edge widths proportional to co-citation weight
edge_weights = [G[u][v]["weight"] for u, v in G.edges()]
max_w = max(edge_weights) if edge_weights else 1
edge_widths = [0.3 + 2.0 * w / max_w for w in edge_weights]

fig, ax = plt.subplots(figsize=(14, 10))

# Draw edges
nx.draw_networkx_edges(
    G, pos, ax=ax,
    width=edge_widths,
    alpha=0.15,
    edge_color="grey",
)

# Draw nodes
nx.draw_networkx_nodes(
    G, pos, ax=ax,
    node_color=node_colors,
    node_size=node_sizes,
    alpha=0.85,
    edgecolors="white",
    linewidths=0.5,
)

# Label only the most-cited nodes (top 30)
top_nodes = sorted(G.nodes(), key=lambda n: G.nodes[n]["citations"], reverse=True)[:30]
labels = {n: G.nodes[n]["label"] for n in top_nodes}
nx.draw_networkx_labels(
    G, pos, labels, ax=ax,
    font_size=7,
    font_weight="bold",
)

# Legend for communities
for c in sorted(set(partition.values())):
    members = [n for n, comm in partition.items() if comm == c]
    ax.scatter([], [], c=[palette[c]], s=80,
               label=f"Community {c} (n={len(members)})")
ax.legend(loc="upper left", fontsize=9, framealpha=0.9)

ax.set_title(
    "Co-citation network: intellectual communities in climate finance literature",
    fontsize=13, pad=15,
)
ax.axis("off")

plt.tight_layout()
fig.savefig(os.path.join(FIGURES_DIR, "fig2_communities.pdf"), dpi=300, bbox_inches="tight")
fig.savefig(os.path.join(FIGURES_DIR, "fig2_communities.png"), dpi=150, bbox_inches="tight")
print(f"\nSaved Figure 2 → figures/fig2_communities.pdf")
plt.close()
