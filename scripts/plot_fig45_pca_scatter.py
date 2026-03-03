"""PCA scatter plots: year x PC score for each bimodal embedding axis.

For each embedding PCA component with significant bimodality (ΔBIC > 200),
plots ~1,176 core papers with X=year, Y=score along that PC.

Produces:
- figures/fig4_pca_scatter.{png,pdf}: Multi-panel scatter (one per qualifying PC)
- tables/tab4_pca_components.csv: Component metadata (variance, ΔBIC, top terms)

Usage:
    uv run python scripts/plot_fig45_pca_scatter.py [--no-pdf] [--core-only]
"""

import argparse
import os
import warnings

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.decomposition import PCA
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.mixture import GaussianMixture

from utils import BASE_DIR, CATALOGS_DIR, save_figure

warnings.filterwarnings("ignore", category=FutureWarning)

# --- Args ---
parser = argparse.ArgumentParser(description="PCA scatter plots (Figs 4 & 5)")
parser.add_argument("--no-pdf", action="store_true", help="Skip PDF generation (PNG only)")
parser.add_argument("--core-only", action="store_true",
                    help="Restrict to core papers (cited_by_count >= 50)")
args = parser.parse_args()

# --- Paths ---
FIGURES_DIR = os.path.join(BASE_DIR, "figures")
TABLES_DIR = os.path.join(BASE_DIR, "tables")
os.makedirs(FIGURES_DIR, exist_ok=True)
os.makedirs(TABLES_DIR, exist_ok=True)

EMBEDDINGS_PATH = os.path.join(CATALOGS_DIR, "embeddings.npy")

# --- Constants ---
CITE_THRESHOLD = 50
DBIC_THRESHOLD = 200
N_COMPONENTS = 10

PERIODS = {
    "1990\u20132006": (1990, 2006),
    "2007\u20132014": (2007, 2014),
    "2015\u20132025": (2015, 2025),
}
PERIOD_COLORS = {
    "1990\u20132006": "#8da0cb",
    "2007\u20132014": "#fc8d62",
    "2015\u20132025": "#66c2a5",
}

COP_EVENTS = {
    1992: "Rio",
    1997: "Kyoto",
    2009: "Copenhagen",
    2015: "Paris",
    2021: "Glasgow",
    2024: "Baku",
}

# Output naming depends on mode
if args.core_only:
    FIG_STEM = "fig4_pca_scatter_core"
    TAB_FILE = "tab4b_pca_components_core.csv"
else:
    FIG_STEM = "fig4_pca_scatter"
    TAB_FILE = "tab4_pca_components.csv"


# ============================================================
# Step 1: Load data + embeddings
# ============================================================

print("Loading data...")
works = pd.read_csv(os.path.join(CATALOGS_DIR, "refined_works.csv"))
works["year"] = pd.to_numeric(works["year"], errors="coerce")

# Filter: must have abstract, year in range (matches embedding generation)
has_abstract = works["abstract"].notna() & (works["abstract"].str.len() > 50)
in_range = (works["year"] >= 1990) & (works["year"] <= 2025)
df = works[has_abstract & in_range].copy().reset_index(drop=True)

embeddings = np.load(EMBEDDINGS_PATH)
assert len(embeddings) == len(df), (
    f"Embedding size mismatch: {len(embeddings)} vs {len(df)}"
)
print(f"Loaded {len(df)} papers with embeddings ({embeddings.shape[1]}D)")

# Core filtering
df["cited_by_count"] = pd.to_numeric(df["cited_by_count"], errors="coerce").fillna(0)
if args.core_only:
    core_mask = df["cited_by_count"] >= CITE_THRESHOLD
    core_indices = df.index[core_mask].values
    df = df.loc[core_mask].reset_index(drop=True)
    embeddings = embeddings[core_indices]
    print(f"Core subset: {len(df)} papers (cited_by_count >= {CITE_THRESHOLD})")

df["year"] = df["year"].astype(int)


# ============================================================
# Step 2: PCA on embeddings
# ============================================================

print(f"\nRunning PCA (n_components={N_COMPONENTS})...")
pca = PCA(n_components=N_COMPONENTS, random_state=42)
pca_scores = pca.fit_transform(embeddings)

print("Variance explained by first 10 PCs:")
for i, v in enumerate(pca.explained_variance_ratio_):
    print(f"  PC{i+1}: {v:.1%}")
print(f"  Total: {pca.explained_variance_ratio_.sum():.1%}")


# ============================================================
# Step 3: Bimodality test for each PC
# ============================================================

print(f"\nBimodality test (ΔBIC threshold = {DBIC_THRESHOLD}):")
qualifying_pcs = []

for i in range(N_COMPONENTS):
    scores = pca_scores[:, i].reshape(-1, 1)
    gmm1 = GaussianMixture(n_components=1, random_state=42).fit(scores)
    gmm2 = GaussianMixture(n_components=2, random_state=42).fit(scores)
    bic1 = gmm1.bic(scores)
    bic2 = gmm2.bic(scores)
    dbic = bic1 - bic2  # positive = 2-component preferred

    tag = " ***" if dbic > DBIC_THRESHOLD else ""
    print(f"  PC{i+1}: ΔBIC = {dbic:.0f}{tag}")

    if dbic > DBIC_THRESHOLD:
        qualifying_pcs.append({
            "component": i + 1,
            "variance_explained": pca.explained_variance_ratio_[i],
            "bic_1comp": bic1,
            "bic_2comp": bic2,
            "delta_bic": dbic,
        })

if not qualifying_pcs:
    print("\nNo PCs passed the bimodality threshold. Exiting.")
    raise SystemExit(0)

print(f"\n{len(qualifying_pcs)} qualifying PC(s): "
      + ", ".join(f"PC{pc['component']}" for pc in qualifying_pcs))


# ============================================================
# Step 4: TF-IDF term labels for each qualifying PC
# ============================================================

print("\nFitting TF-IDF for term labelling...")
abstracts = df["abstract"].fillna("").tolist()
tfidf = TfidfVectorizer(
    max_features=10000,
    ngram_range=(1, 2),
    sublinear_tf=True,
    stop_words="english",
)
X_tfidf = tfidf.fit_transform(abstracts)
feature_names = np.array(tfidf.get_feature_names_out())
print(f"TF-IDF matrix: {X_tfidf.shape}")

for pc_info in qualifying_pcs:
    idx = pc_info["component"] - 1
    scores = pca_scores[:, idx]

    # Correlate PC scores with TF-IDF features
    # For efficiency, compute correlation using matrix multiply
    scores_centered = scores - scores.mean()
    scores_std = scores.std()
    if scores_std == 0:
        pc_info["top_positive_terms"] = ""
        pc_info["top_negative_terms"] = ""
        continue

    # Sparse-friendly correlation: r = (X^T z) / (n * std_x * std_z)
    n = len(scores)
    Xc = X_tfidf.copy()
    # Column means for sparse matrix
    col_means = np.asarray(Xc.mean(axis=0)).flatten()
    # X^T (z - mean_z)
    xtz = np.asarray(Xc.T.dot(scores_centered)).flatten()
    # Approximate: skip full column centering for speed, use raw correlation
    col_stds = np.sqrt(np.asarray(Xc.multiply(Xc).mean(axis=0)).flatten()
                       - col_means ** 2)
    col_stds[col_stds == 0] = 1e-10
    correlations = xtz / (n * col_stds * scores_std)

    # Top positive and negative terms
    top_pos_idx = np.argsort(correlations)[-5:][::-1]
    top_neg_idx = np.argsort(correlations)[:5]

    top_pos = feature_names[top_pos_idx].tolist()
    top_neg = feature_names[top_neg_idx].tolist()

    pc_info["top_positive_terms"] = ", ".join(top_pos)
    pc_info["top_negative_terms"] = ", ".join(top_neg)

    print(f"  PC{pc_info['component']} (+): {', '.join(top_pos)}")
    print(f"  PC{pc_info['component']} (-): {', '.join(top_neg)}")


# ============================================================
# Step 5: Scatter plot — one panel per qualifying PC
# ============================================================

sns.set_style("whitegrid")
n_panels = len(qualifying_pcs)
fig_width = min(6 * n_panels, 24)
fig, axes = plt.subplots(1, n_panels, figsize=(fig_width, 6), sharey=False,
                         squeeze=False)
axes = axes.flatten()

rng = np.random.RandomState(42)

for ax, pc_info in zip(axes, qualifying_pcs):
    idx = pc_info["component"] - 1
    scores = pca_scores[:, idx]
    var_pct = pc_info["variance_explained"]
    dbic = pc_info["delta_bic"]

    # Period background bands
    for period_label, (y_start, y_end) in PERIODS.items():
        ax.axvspan(y_start - 0.5, y_end + 0.5,
                   alpha=0.08, color=PERIOD_COLORS[period_label],
                   zorder=0)

    # COP markers (vertical lines only; labels added after data sets y-limits)
    for cop_year in COP_EVENTS:
        ax.axvline(cop_year, color="grey", linestyle="--", alpha=0.3,
                   linewidth=0.8, zorder=1)

    # Scatter by period
    for period_label, (y_start, y_end) in PERIODS.items():
        pmask = (df["year"] >= y_start) & (df["year"] <= y_end)
        pdata = df[pmask]
        pscores = scores[pmask.values]

        # Point size scaled by citations
        sizes = 8 + 3 * np.sqrt(pdata["cited_by_count"].values / CITE_THRESHOLD)

        # Jitter x
        jitter = rng.uniform(-0.3, 0.3, size=len(pdata))

        ax.scatter(
            pdata["year"].values + jitter,
            pscores,
            s=sizes,
            alpha=0.4,
            color=PERIOD_COLORS[period_label],
            edgecolors="none",
            label=period_label,
            zorder=2,
        )

    # Yearly median line
    yearly_median = df.assign(score=scores).groupby("year")["score"].median()
    ax.plot(yearly_median.index, yearly_median.values,
            color="black", linewidth=2, zorder=3, label="Yearly median")

    # Re-draw COP labels at actual y-limits (now that data is plotted)
    ymin, ymax = ax.get_ylim()
    for cop_year, cop_name in COP_EVENTS.items():
        ax.text(cop_year + 0.3, ymax - 0.02 * (ymax - ymin),
                cop_name, fontsize=6, color="grey", alpha=0.7,
                ha="left", va="top", rotation=90)

    # Axis pole labels (top 3 terms for + and - poles)
    pos_terms = pc_info.get("top_positive_terms", "")
    neg_terms = pc_info.get("top_negative_terms", "")
    if pos_terms:
        top3_pos = ", ".join(pos_terms.split(", ")[:3])
        ax.text(0.97, 0.97, f"(+) {top3_pos}",
                transform=ax.transAxes, fontsize=7, ha="right", va="top",
                style="italic", color="#333333",
                bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                          edgecolor="grey", alpha=0.8))
    if neg_terms:
        top3_neg = ", ".join(neg_terms.split(", ")[:3])
        ax.text(0.97, 0.03, f"(-) {top3_neg}",
                transform=ax.transAxes, fontsize=7, ha="right", va="bottom",
                style="italic", color="#333333",
                bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                          edgecolor="grey", alpha=0.8))

    # Panel title
    ax.set_title(f"PC{pc_info['component']} ({var_pct:.1%} variance, "
                 f"\u0394BIC={dbic:.0f})", fontsize=11)
    ax.set_xlabel("Year", fontsize=10)
    ax.set_ylabel(f"PC{pc_info['component']} score", fontsize=10)

# Legend (from last axis, shared)
handles = [mpatches.Patch(color=c, label=l, alpha=0.6)
           for l, c in PERIOD_COLORS.items()]
handles.append(plt.Line2D([0], [0], color="black", linewidth=2, label="Yearly median"))
axes[-1].legend(handles=handles, fontsize=8, loc="upper left",
                framealpha=0.9)

mode_label = " (core, cited \u2265 50)" if args.core_only else ""
fig.suptitle(f"PCA bimodal axes: paper distribution over time{mode_label}",
             fontsize=13, y=1.02)
plt.tight_layout()

save_figure(fig, os.path.join(FIGURES_DIR, FIG_STEM), no_pdf=args.no_pdf)
plt.close()


# ============================================================
# Step 6: Save component metadata table
# ============================================================

tab = pd.DataFrame(qualifying_pcs)
tab.to_csv(os.path.join(TABLES_DIR, TAB_FILE), index=False)
print(f"\nSaved -> tables/{TAB_FILE} ({len(tab)} qualifying PCs)")

print("\nDone.")
