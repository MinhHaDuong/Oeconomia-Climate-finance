"""Time-ordered citation genealogy of intellectual communities.

Visualizes the citation DAG constrained by community structure, with papers
positioned by year (x-axis) and lineage band (y-axis).

Produces:
- figures/fig3_genealogy.pdf: Citation genealogy (~500+ papers)
- tables/tab3_lineages.csv: Lineage assignments for backbone papers

Options:
  --robustness        Louvain resolution sensitivity (R3)
"""

import argparse
import os
import warnings

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.patheffects as pe
import numpy as np
import pandas as pd
from matplotlib.path import Path
from scipy.spatial.distance import cosine as cosine_dist

from utils import BASE_DIR, CATALOGS_DIR, normalize_doi

warnings.filterwarnings("ignore", category=FutureWarning)

# --- Paths ---
FIGURES_DIR = os.path.join(BASE_DIR, "figures")
TABLES_DIR = os.path.join(BASE_DIR, "tables")
os.makedirs(FIGURES_DIR, exist_ok=True)
os.makedirs(TABLES_DIR, exist_ok=True)

EMBEDDINGS_PATH = os.path.join(CATALOGS_DIR, "embeddings.npy")

# COP events
COP_EVENTS = {
    1992: "Rio",
    1997: "Kyoto",
    2009: "Copenhagen",
    2015: "Paris",
    2021: "Glasgow",
    2024: "Baku",
}

# Periods (from alluvial analysis: 2009 data-derived, 2015/2021 COP-imposed)
PERIOD_BOUNDS = [1990, 2009, 2015, 2021, 2026]
PERIOD_LABELS = ["1990–2008", "2009–2014", "2015–2020", "2021–2025"]
PERIOD_COLORS = ["#f0f0f0", "#e8e8e8", "#f0f0f0", "#e8e8e8"]

# --- Args ---
parser = argparse.ArgumentParser(description="Citation genealogy figure")
parser.add_argument("--robustness", action="store_true",
                    help="Run Louvain resolution sensitivity (R3)")
args = parser.parse_args()


# ============================================================
# Step 1: Load data
# ============================================================

print("Loading data...")
works = pd.read_csv(os.path.join(CATALOGS_DIR, "unified_works.csv"))
works["year"] = pd.to_numeric(works["year"], errors="coerce")
works["doi_norm"] = works["doi"].apply(normalize_doi)
works["cited_by_count"] = pd.to_numeric(works["cited_by_count"], errors="coerce").fillna(0)

# Build DOI → metadata lookup
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
print("Loading citations...")
cit = pd.read_csv(os.path.join(CATALOGS_DIR, "citations.csv"), low_memory=False)
cit["source_doi"] = cit["source_doi"].apply(normalize_doi)
cit["ref_doi"] = cit["ref_doi"].apply(normalize_doi)
cit = cit[(cit["source_doi"] != "") & (cit["ref_doi"] != "")]
cit = cit[~cit["source_doi"].isin(["nan", "none"])]
cit = cit[~cit["ref_doi"].isin(["nan", "none"])]

# Also add ref metadata from citations (for papers not in unified_works)
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

# Load KMeans semantic clusters (same as Fig 2 alluvial)
print("Loading semantic clusters (KMeans, same ontology as Fig 2)...")
sem_df = pd.read_csv(os.path.join(CATALOGS_DIR, "semantic_clusters.csv"))
sem_df["doi_norm"] = sem_df["doi"].apply(normalize_doi)
doi_to_cluster = dict(zip(sem_df["doi_norm"], sem_df["semantic_cluster"]))
n_communities = len(sem_df["semantic_cluster"].unique())
print(f"KMeans clusters: {n_communities}, papers: {len(sem_df)}")

# Load embeddings for centroid computation + label generation
print("Loading embeddings...")
emb_works = works[works["abstract"].notna() & (works["abstract"].str.len() > 50)].copy()
emb_works = emb_works[(emb_works["year"] >= 1990) & (emb_works["year"] <= 2025)].reset_index(drop=True)
embeddings = np.load(EMBEDDINGS_PATH)

emb_doi_to_idx = {}
for i, row in emb_works.iterrows():
    d = normalize_doi(row["doi"])
    if d and d not in ("", "nan", "none"):
        emb_doi_to_idx[d] = i

# Compute cluster centroids from all clustered papers
cluster_embeddings = {c: [] for c in range(n_communities)}
for d, c in doi_to_cluster.items():
    if d in emb_doi_to_idx:
        cluster_embeddings[c].append(embeddings[emb_doi_to_idx[d]])

cluster_centroids = {}
for c, embs in cluster_embeddings.items():
    if embs:
        cluster_centroids[c] = np.mean(embs, axis=0)

# Load cluster labels from alluvial (shared across Fig 2 and Fig 3)
import json
labels_path = os.path.join(CATALOGS_DIR, "cluster_labels.json")
if os.path.exists(labels_path):
    with open(labels_path) as f:
        COMMUNITY_NAMES = {int(k): v for k, v in json.load(f).items()}
    print(f"Loaded cluster labels from {labels_path}")
else:
    print(f"WARNING: {labels_path} not found. Run analyze_alluvial.py first.")
    print("Falling back to generic labels.")
    COMMUNITY_NAMES = {c: f"Cluster {c}" for c in range(n_communities)}

print("\nCluster labels (same ontology as Fig 2):")
for c, label in COMMUNITY_NAMES.items():
    print(f"  {c}: {label}")


# ============================================================
# Step 2: Select backbone papers
# ============================================================

print("\nSelecting backbone (cited_by_count >= 20)...")

has_abs = works["abstract"].notna() & (works["abstract"].str.len() > 50)
high_cited = works[has_abs & (works["cited_by_count"] >= 20)]
backbone_dois = set(high_cited["doi_norm"])

# Filter to papers with valid year
backbone_dois = {d for d in backbone_dois
                 if d in doi_meta and doi_meta[d]["year"] is not None
                 and 1985 <= (doi_meta[d]["year"] or 0) <= 2025}

print(f"Backbone papers (with valid year): {len(backbone_dois)}")


# ============================================================
# Step 3: Assign lineages (KMeans clusters, same as Fig 2)
# ============================================================

lineage = {}  # doi -> cluster_id
peripheral = set()  # dois marked as peripheral

# Most backbone papers have direct KMeans assignments
direct = 0
for d in backbone_dois:
    if d in doi_to_cluster:
        lineage[d] = doi_to_cluster[d]
        direct += 1

# For papers without KMeans assignment, use nearest centroid
assigned = 0
periph_count = 0
for d in backbone_dois:
    if d in lineage:
        continue
    if d not in emb_doi_to_idx:
        # No embedding — assign to largest cluster, mark peripheral
        lineage[d] = max(cluster_centroids.keys(),
                         key=lambda c: len(cluster_embeddings.get(c, [])))
        peripheral.add(d)
        periph_count += 1
        continue

    emb = embeddings[emb_doi_to_idx[d]]
    best_c, best_sim = None, -1
    for c, centroid in cluster_centroids.items():
        sim = 1 - cosine_dist(emb, centroid)
        if sim > best_sim:
            best_sim = sim
            best_c = c

    if best_sim < 0.4:
        peripheral.add(d)
        periph_count += 1
    lineage[d] = best_c
    assigned += 1

print(f"Direct KMeans assignments: {direct}")
print(f"Assigned via nearest centroid: {assigned}")
print(f"Peripheral papers (cosine < 0.4): {periph_count}")

# Filter backbone to papers with lineage assignment
backbone_dois = {d for d in backbone_dois if d in lineage}
print(f"Final backbone with lineage: {len(backbone_dois)}")


# ============================================================
# Step 4: Build citation DAG (internal links only)
# ============================================================

print("\nBuilding citation DAG...")
edges = []
for _, row in cit.iterrows():
    s = row["source_doi"]
    r = row["ref_doi"]
    if s in backbone_dois and r in backbone_dois:
        # Edge from cited (older) to citing (newer)
        edges.append((r, s))

# Deduplicate
edges = list(set(edges))
print(f"Internal citation edges: {len(edges)}")


# ============================================================
# Step 5: Layout computation
# ============================================================

print("\nComputing layout...")

# X = year (normalized to 0-1)
year_min = min(doi_meta[d]["year"] for d in backbone_dois)
year_max = max(doi_meta[d]["year"] for d in backbone_dois)

# Y = lineage band
# Order bands by median year of earliest papers (foundational at edges)
comm_median_years = {}
for c in range(n_communities):
    years_c = [doi_meta[d]["year"] for d in backbone_dois
               if lineage.get(d) == c and doi_meta[d]["year"] is not None]
    if years_c:
        comm_median_years[c] = np.median(years_c)
    else:
        comm_median_years[c] = 2020

# Sort: foundational (old median) at top, recent at bottom
sorted_comms = sorted(comm_median_years.keys(), key=lambda c: comm_median_years[c])
comm_to_band = {c: i for i, c in enumerate(sorted_comms)}

# Compute positions
positions = {}
band_height = 1.0 / max(n_communities, 1)

# Count papers per (community, year) for jittering
from collections import defaultdict
comm_year_counts = defaultdict(int)
comm_year_assigned = defaultdict(int)

for d in backbone_dois:
    c = lineage[d]
    yr = doi_meta[d]["year"]
    comm_year_counts[(c, int(yr))] += 1

for d in backbone_dois:
    c = lineage[d]
    yr = doi_meta[d]["year"]
    band = comm_to_band[c]

    # X position: year
    x = (yr - year_min) / max(year_max - year_min, 1)

    # Y position: band center + jitter
    band_center = (band + 0.5) * band_height
    n_in_slot = comm_year_counts[(c, int(yr))]
    idx_in_slot = comm_year_assigned[(c, int(yr))]
    comm_year_assigned[(c, int(yr))] += 1

    # Spread papers within band
    jitter_range = band_height * 0.35
    if n_in_slot > 1:
        jitter = -jitter_range + 2 * jitter_range * idx_in_slot / (n_in_slot - 1)
    else:
        jitter = 0
    y = band_center + jitter

    positions[d] = (x, y)


# ============================================================
# Step 6: Render figure
# ============================================================

import matplotlib
matplotlib.rcParams['font.size'] = 8

palette = plt.cm.Set2(np.linspace(0, 1, max(n_communities, 3)))

fig, ax = plt.subplots(figsize=(16, 10))

# Period bands
for i in range(len(PERIOD_BOUNDS) - 1):
    x0 = (PERIOD_BOUNDS[i] - year_min) / max(year_max - year_min, 1)
    x1 = (PERIOD_BOUNDS[i + 1] - year_min) / max(year_max - year_min, 1)
    ax.axvspan(x0, x1, alpha=0.15, color=PERIOD_COLORS[i], zorder=0)
    # Period label at top
    xmid = (x0 + x1) / 2
    ax.text(xmid, 1.02, PERIOD_LABELS[i], ha="center", va="bottom",
            fontsize=8, color="grey", transform=ax.transAxes if False else ax.transData)

# COP event markers
for yr, label in COP_EVENTS.items():
    if year_min <= yr <= year_max:
        x = (yr - year_min) / max(year_max - year_min, 1)
        ax.axvline(x, color="grey", linestyle="--", alpha=0.3, linewidth=0.7)
        ax.text(x, 1.01, label, ha="center", va="bottom", fontsize=6,
                color="grey", rotation=45)

# Draw citation edges (thin lines)
for src, tgt in edges:
    if src in positions and tgt in positions:
        x0, y0 = positions[src]
        x1, y1 = positions[tgt]
        src_comm = lineage.get(src)
        tgt_comm = lineage.get(tgt)

        if src_comm == tgt_comm:
            # Within-lineage: solid, colored
            color = palette[src_comm]
            alpha = 0.15
            style = "-"
        else:
            # Cross-lineage: grey dashed
            color = "grey"
            alpha = 0.08
            style = "--"

        ax.plot([x0, x1], [y0, y1], linestyle=style, color=color,
                alpha=alpha, linewidth=0.3, zorder=1)

# Identify top cross-lineage citations for highlight
cross_edges = [(s, t) for s, t in edges
               if s in lineage and t in lineage and lineage[s] != lineage[t]]

# Score by citation count of target
cross_scored = []
for s, t in cross_edges:
    score = doi_meta.get(t, {}).get("cited_by_count", 0) + doi_meta.get(s, {}).get("cited_by_count", 0)
    cross_scored.append((s, t, score))
cross_scored.sort(key=lambda x: -x[2])

# Draw top 15 cross-lineage arcs
for s, t, _ in cross_scored[:15]:
    if s in positions and t in positions:
        x0, y0 = positions[s]
        x1, y1 = positions[t]
        # Bezier arc
        cx = (x0 + x1) / 2
        cy = (y0 + y1) / 2 + 0.05 * (1 if y0 < y1 else -1)
        verts = [(x0, y0), (cx, cy), (x1, y1)]
        codes = [Path.MOVETO, Path.CURVE3, Path.CURVE3]
        path = Path(verts, codes)
        patch = mpatches.PathPatch(
            path, facecolor="none", edgecolor="#E63946",
            linewidth=0.6, alpha=0.4, linestyle="--", zorder=2,
        )
        ax.add_patch(patch)

# Draw nodes
for d in backbone_dois:
    if d not in positions:
        continue
    x, y = positions[d]
    c = lineage[d]
    cit_count = doi_meta.get(d, {}).get("cited_by_count", 0)

    size = 10 + 60 * np.sqrt(max(cit_count, 0) / 200)
    alpha = 0.3 if d in peripheral else 0.8

    ax.scatter(x, y, s=size, c=[palette[c]], alpha=alpha,
               edgecolors="white", linewidths=0.3, zorder=3)

# Labels for top papers
n_labels = 40
top_papers = sorted(backbone_dois,
                    key=lambda d: doi_meta.get(d, {}).get("cited_by_count", 0),
                    reverse=True)[:n_labels]

label_positions = []
for d in top_papers:
    if d not in positions:
        continue
    x, y = positions[d]
    meta = doi_meta.get(d, {})
    author = str(meta.get("first_author", ""))
    # Clean author name
    author = author.split(",")[0].split(";")[0].strip()
    if not author or author in ("nan", ""):
        continue
    yr = meta.get("year", "")
    if yr and not np.isnan(yr):
        yr = int(yr)
    else:
        continue

    label = f"{author} ({yr})"

    # Simple offset: alternate up/down based on position in list
    idx = top_papers.index(d)
    offset_y = 0.012 if idx % 2 == 0 else -0.012

    ax.annotate(
        label,
        (x, y),
        xytext=(3, offset_y * 500),
        textcoords="offset points",
        fontsize=5.5,
        color="black",
        ha="left",
        va="center",
        path_effects=[pe.withStroke(linewidth=2, foreground="white")],
        zorder=4,
    )

# Legend for lineage bands
handles = []
for c in sorted_comms:
    name = COMMUNITY_NAMES.get(c, f"Community {c}")
    n = sum(1 for d in backbone_dois if lineage.get(d) == c)
    handles.append(mpatches.Patch(
        facecolor=palette[c], label=f"{name} (n={n})"
    ))
ax.legend(handles=handles, loc="upper left", fontsize=7, framealpha=0.9,
          title="Intellectual lineages", title_fontsize=8)

# Year axis
year_ticks = list(range(int(year_min) - int(year_min) % 5, int(year_max) + 5, 5))
for yr in year_ticks:
    x = (yr - year_min) / max(year_max - year_min, 1)
    if 0 <= x <= 1:
        ax.text(x, -0.02, str(yr), ha="center", va="top", fontsize=7, color="grey")

ax.set_xlim(-0.02, 1.05)
ax.set_ylim(-0.05, 1.05)

n_backbone = len(backbone_dois)
ax.set_title(
    f"Citation genealogy of climate finance intellectual communities ({n_backbone} papers)\n"
    "Node size ∝ √citations, cross-lineage arcs in red",
    fontsize=12, pad=20,
)
ax.axis("off")

plt.tight_layout()
fig_path = os.path.join(FIGURES_DIR, "fig3_genealogy")
fig.savefig(f"{fig_path}.pdf", dpi=300, bbox_inches="tight")
fig.savefig(f"{fig_path}.png", dpi=150, bbox_inches="tight")
print(f"\nSaved Figure 3 → figures/fig3_genealogy.pdf")
plt.close()


# ============================================================
# Step 7: Save lineage table
# ============================================================

rows = []
for d in backbone_dois:
    meta = doi_meta.get(d, {})
    rows.append({
        "doi": d,
        "lineage": lineage.get(d, -1),
        "lineage_name": COMMUNITY_NAMES.get(lineage.get(d, -1), "Unknown"),
        "peripheral": d in peripheral,
        "first_author": meta.get("first_author", ""),
        "year": meta.get("year", ""),
        "cited_by_count": meta.get("cited_by_count", 0),
        "title": meta.get("title", "")[:100],
    })

lineage_df = pd.DataFrame(rows).sort_values(["lineage", "cited_by_count"], ascending=[True, False])
lineage_df.to_csv(os.path.join(TABLES_DIR, "tab3_lineages.csv"), index=False)
print(f"Saved lineage table → tables/tab3_lineages.csv ({len(lineage_df)} papers)")


# ============================================================
# Robustness: Louvain resolution sensitivity (R3)
# ============================================================

if args.robustness:
    print("\n=== Robustness: Louvain resolution sensitivity ===")
    import community as community_louvain
    import networkx as nx
    from sklearn.metrics import adjusted_rand_score

    # Rebuild co-citation network (from analyze_cocitation.py logic)
    from scipy.sparse import lil_matrix

    ref_counts = cit.groupby("ref_doi").size().sort_values(ascending=False)
    TOP_N = 200
    top_refs = ref_counts.head(TOP_N).index.tolist()
    top_set = set(top_refs)
    ref_to_idx = {ref: i for i, ref in enumerate(top_refs)}

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

    G = nx.Graph()
    for i, doi in enumerate(top_refs):
        G.add_node(doi)
    MIN_COCIT = 3
    for i in range(TOP_N):
        for j in range(i + 1, TOP_N):
            w = cocit_dense[i, j]
            if w >= MIN_COCIT:
                G.add_edge(top_refs[i], top_refs[j], weight=w)
    isolates = list(nx.isolates(G))
    G.remove_nodes_from(isolates)

    # Test resolution parameters
    resolutions = [0.5, 1.0, 1.5, 2.0]
    partitions = {}

    try:
        for gamma in resolutions:
            part = community_louvain.best_partition(G, weight="weight",
                                                     resolution=gamma, random_state=42)
            partitions[gamma] = part
            n_c = len(set(part.values()))
            print(f"  γ={gamma}: {n_c} communities")

        # Build sensitivity table
        common_nodes = list(G.nodes())
        sens_rows = []
        for doi in common_nodes:
            row = {"doi": doi}
            for gamma in resolutions:
                row[f"community_g{str(gamma).replace('.', '')}"] = partitions[gamma].get(doi, -1)
            sens_rows.append(row)

        sens_df = pd.DataFrame(sens_rows)
        sens_df.to_csv(os.path.join(TABLES_DIR, "tab3_louvain_sensitivity.csv"), index=False)
        print(f"Saved Louvain sensitivity → tables/tab3_louvain_sensitivity.csv")

        # ARI between resolution levels
        print("\n  Pairwise ARI:")
        for i, g1 in enumerate(resolutions):
            for g2 in resolutions[i + 1:]:
                labels1 = [partitions[g1][n] for n in common_nodes]
                labels2 = [partitions[g2][n] for n in common_nodes]
                ari = adjusted_rand_score(labels1, labels2)
                print(f"    γ={g1} vs γ={g2}: ARI={ari:.3f}")

    except TypeError:
        print("  WARNING: community_louvain.best_partition does not support 'resolution' parameter.")
        print("  Skipping R3 sensitivity analysis.")

print("\nDone.")
