"""Semantic landscape of climate finance literature using multilingual embeddings.

Method:
- Embed abstracts with a multilingual sentence-transformer
- UMAP dimensionality reduction to 2D
- HDBSCAN clustering to identify discourse communities
- Cross-validate with co-citation communities (if available)

Produces:
- figures/fig3_semantic.pdf: 2D semantic map colored by cluster
- figures/fig3_semantic_lang.pdf: Same map colored by language
- data/catalogs/embeddings.npy: Raw embedding vectors
- data/catalogs/semantic_clusters.csv: Cluster assignments
"""

import os
import warnings

import hdbscan
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import umap
from sentence_transformers import SentenceTransformer

from utils import BASE_DIR, CATALOGS_DIR, normalize_doi

warnings.filterwarnings("ignore", category=FutureWarning)

# --- Paths ---
FIGURES_DIR = os.path.join(BASE_DIR, "figures")
TABLES_DIR = os.path.join(BASE_DIR, "tables")
os.makedirs(FIGURES_DIR, exist_ok=True)
os.makedirs(TABLES_DIR, exist_ok=True)

EMBEDDINGS_PATH = os.path.join(CATALOGS_DIR, "embeddings.npy")
CLUSTERS_PATH = os.path.join(CATALOGS_DIR, "semantic_clusters.csv")

# --- Load data ---
print("Loading unified works...")
works = pd.read_csv(os.path.join(CATALOGS_DIR, "unified_works.csv"))
works["year"] = pd.to_numeric(works["year"], errors="coerce")

# Filter: must have abstract, year in range
has_abstract = works["abstract"].notna() & (works["abstract"].str.len() > 50)
in_range = (works["year"] >= 1990) & (works["year"] <= 2025)
df = works[has_abstract & in_range].copy().reset_index(drop=True)
print(f"Works with abstracts (1990-2025): {len(df)}")

# --- Compute or load embeddings ---
if os.path.exists(EMBEDDINGS_PATH):
    print(f"Loading cached embeddings from {EMBEDDINGS_PATH}...")
    embeddings = np.load(EMBEDDINGS_PATH)
    if len(embeddings) != len(df):
        print(f"Cache size mismatch ({len(embeddings)} vs {len(df)}), recomputing...")
        os.remove(EMBEDDINGS_PATH)
        embeddings = None
    else:
        print(f"Loaded {len(embeddings)} embeddings")
else:
    embeddings = None

if embeddings is None:
    print("Loading multilingual sentence-transformer model...")
    model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")

    print(f"Encoding {len(df)} abstracts (this may take a while on CPU)...")
    abstracts = df["abstract"].tolist()
    embeddings = model.encode(
        abstracts,
        batch_size=256,
        show_progress_bar=True,
        normalize_embeddings=True,
    )

    np.save(EMBEDDINGS_PATH, embeddings)
    print(f"Saved embeddings → {EMBEDDINGS_PATH}")

print(f"Embedding shape: {embeddings.shape}")


# ============================================================
# Step 1: UMAP dimensionality reduction
# ============================================================

print("\nComputing UMAP projection...")
reducer = umap.UMAP(
    n_components=2,
    n_neighbors=15,
    min_dist=0.05,
    metric="cosine",
    random_state=42,
    low_memory=True,
)
coords = reducer.fit_transform(embeddings)
df["umap_x"] = coords[:, 0]
df["umap_y"] = coords[:, 1]
print(f"UMAP done: {coords.shape}")


# ============================================================
# Step 2: HDBSCAN clustering
# ============================================================

print("\nClustering with KMeans (k=6, matching co-citation communities)...")
from sklearn.cluster import KMeans
kmeans = KMeans(n_clusters=6, random_state=42, n_init=20)
df["semantic_cluster"] = kmeans.fit_predict(coords)
n_clusters = 6
n_noise = 0
print(f"Semantic clusters: {n_clusters}")

# Cluster sizes
print("\nCluster sizes:")
for c in sorted(df["semantic_cluster"].unique()):
    label = f"Cluster {c}" if c >= 0 else "Noise"
    print(f"  {label}: {(df['semantic_cluster'] == c).sum()}")


# ============================================================
# Step 3: Characterize clusters
# ============================================================

# For each cluster, find most common keywords
print("\n=== Cluster keyword profiles ===")
for c in range(n_clusters):
    members = df[df["semantic_cluster"] == c]
    # Extract keywords
    all_kw = []
    for kw_str in members["keywords"].dropna():
        all_kw.extend([k.strip().lower() for k in str(kw_str).split(";")])
    from collections import Counter
    kw_counts = Counter(all_kw).most_common(10)
    kw_str = ", ".join(f"{k} ({n})" for k, n in kw_counts)
    median_year = int(members["year"].median())
    print(f"\nCluster {c} (n={len(members)}, median year={median_year}):")
    print(f"  Top keywords: {kw_str}")


# ============================================================
# Step 4: Cross-validate with co-citation communities
# ============================================================

cocit_path = os.path.join(CATALOGS_DIR, "communities.csv")
if os.path.exists(cocit_path):
    print("\n=== Cross-validation with co-citation communities ===")
    cocit = pd.read_csv(cocit_path)
    # Match by DOI
    df["doi_norm"] = df["doi"].apply(normalize_doi)
    cocit["doi_norm"] = cocit["doi"].apply(normalize_doi)

    merged = df.merge(cocit[["doi_norm", "community"]], on="doi_norm", how="inner")
    if len(merged) > 0:
        cross_tab = pd.crosstab(
            merged["semantic_cluster"],
            merged["community"],
            margins=True,
        )
        print(f"\nMatched {len(merged)} works with both assignments:")
        print(cross_tab)
    else:
        print("No DOI matches between semantic clusters and co-citation communities")


# ============================================================
# Step 5: Visualize
# ============================================================

sns.set_style("whitegrid")

# --- Figure 3a: Colored by semantic cluster ---
fig, ax = plt.subplots(figsize=(12, 9))

# Plot clusters
palette = plt.cm.Set2(np.linspace(0, 1, n_clusters))
for c in range(n_clusters):
    members = df[df["semantic_cluster"] == c]
    ax.scatter(
        members["umap_x"], members["umap_y"],
        c=[palette[c]], s=8, alpha=0.5,
        label=f"Cluster {c} (n={len(members)})",
    )

ax.legend(loc="upper right", fontsize=8, framealpha=0.9, markerscale=3)
ax.set_title(
    "Semantic landscape of climate finance literature\n"
    "(multilingual abstract embeddings, UMAP projection)",
    fontsize=13,
)
ax.set_xlabel("UMAP 1")
ax.set_ylabel("UMAP 2")

plt.tight_layout()
fig.savefig(os.path.join(FIGURES_DIR, "fig3_semantic.pdf"), dpi=300, bbox_inches="tight")
fig.savefig(os.path.join(FIGURES_DIR, "fig3_semantic.png"), dpi=150, bbox_inches="tight")
print(f"\nSaved Figure 3a → figures/fig3_semantic.pdf")
plt.close()


# --- Figure 3b: Colored by language ---
fig, ax = plt.subplots(figsize=(12, 9))

lang_map = {"en": "English", "fr": "French", "zh": "Chinese",
            "ja": "Japanese", "de": "German", "es": "Spanish", "pt": "Portuguese"}
df["lang_label"] = df["language"].map(lang_map).fillna("Other")

lang_colors = {
    "English": "lightgrey",
    "French": "#E63946",
    "Chinese": "#E9C46A",
    "Japanese": "#264653",
    "German": "#2A9D8F",
    "Spanish": "#F4A261",
    "Portuguese": "#606C38",
    "Other": "#ADB5BD",
}

# Plot English first (background)
en = df[df["lang_label"] == "English"]
ax.scatter(en["umap_x"], en["umap_y"],
           c=lang_colors["English"], s=3, alpha=0.2, label=f"English (n={len(en)})")

# Plot non-English on top
for lang in ["French", "Chinese", "Japanese", "German", "Spanish", "Portuguese", "Other"]:
    subset = df[df["lang_label"] == lang]
    if len(subset) > 0:
        ax.scatter(
            subset["umap_x"], subset["umap_y"],
            c=lang_colors[lang], s=20, alpha=0.8,
            label=f"{lang} (n={len(subset)})",
            edgecolors="white", linewidths=0.3,
        )

ax.legend(loc="upper right", fontsize=8, framealpha=0.9, markerscale=2)
ax.set_title(
    "Language distribution in the semantic landscape\n"
    "(non-English works highlighted)",
    fontsize=13,
)
ax.set_xlabel("UMAP 1")
ax.set_ylabel("UMAP 2")

plt.tight_layout()
fig.savefig(os.path.join(FIGURES_DIR, "fig3_semantic_lang.pdf"), dpi=300, bbox_inches="tight")
fig.savefig(os.path.join(FIGURES_DIR, "fig3_semantic_lang.png"), dpi=150, bbox_inches="tight")
print(f"Saved Figure 3b → figures/fig3_semantic_lang.pdf")
plt.close()


# --- Figure 3c: Colored by period ---
fig, ax = plt.subplots(figsize=(12, 9))

period_map = {
    (1990, 2008): "1990–2008",
    (2009, 2015): "2009–2015",
    (2016, 2021): "2016–2021",
    (2022, 2025): "2022–2025",
}
period_colors = {
    "1990–2008": "#ADB5BD",
    "2009–2015": "#F4A261",
    "2016–2021": "#E76F51",
    "2022–2025": "#264653",
}

def assign_period(year):
    for (lo, hi), label in period_map.items():
        if lo <= year <= hi:
            return label
    return "Other"

df["period"] = df["year"].apply(assign_period)

for period in ["1990–2008", "2009–2015", "2016–2021", "2022–2025"]:
    subset = df[df["period"] == period]
    ax.scatter(
        subset["umap_x"], subset["umap_y"],
        c=period_colors[period], s=5, alpha=0.4,
        label=f"{period} (n={len(subset)})",
    )

ax.legend(loc="upper right", fontsize=9, framealpha=0.9, markerscale=4)
ax.set_title(
    "Temporal evolution of the semantic landscape\n"
    "(colored by article's periodization)",
    fontsize=13,
)
ax.set_xlabel("UMAP 1")
ax.set_ylabel("UMAP 2")

plt.tight_layout()
fig.savefig(os.path.join(FIGURES_DIR, "fig3_semantic_period.pdf"), dpi=300, bbox_inches="tight")
fig.savefig(os.path.join(FIGURES_DIR, "fig3_semantic_period.png"), dpi=150, bbox_inches="tight")
print(f"Saved Figure 3c → figures/fig3_semantic_period.pdf")
plt.close()


# --- Save cluster assignments ---
out = df[["source", "doi", "title", "first_author", "year", "language",
          "semantic_cluster", "umap_x", "umap_y"]].copy()
out.to_csv(CLUSTERS_PATH, index=False)
print(f"\nSaved cluster assignments → {CLUSTERS_PATH}")
print("Done.")
