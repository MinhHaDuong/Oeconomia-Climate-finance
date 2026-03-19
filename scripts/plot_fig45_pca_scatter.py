"""PCA scatter plots: year x score for bimodal embedding axes.

Two modes:
  --supervised : Project onto the efficiency↔accountability seed axis
                 (pole centroids from keyword matching, as in analyze_bimodality.py).
                 Produces a single-panel figure. Recommended with --core-only.
  (default)    : Unsupervised PCA, one panel per PC with ΔBIC > 200.
                 Best on full corpus (3 qualifying PCs). Good for appendix.

Produces:
- figures/fig_pca_scatter*.{png,pdf}: Scatter plot(s)
- tables/tab_pca_components*.csv: Component metadata

Usage:
    uv run python scripts/plot_fig45_pca_scatter.py --core-only --supervised [--no-pdf]
    uv run python scripts/plot_fig45_pca_scatter.py [--no-pdf]   # full corpus, unsupervised
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

from utils import (BASE_DIR, CATALOGS_DIR, get_logger, load_refined_embeddings,
                   save_figure, load_analysis_config, load_analysis_periods)

log = get_logger("plot_fig45_pca_scatter")

warnings.filterwarnings("ignore", category=FutureWarning)

# --- Args ---
parser = argparse.ArgumentParser(description="PCA scatter plots (Figs 4 & 5)")
parser.add_argument("--no-pdf", action="store_true", help="Skip PDF generation (PNG only)")
parser.add_argument("--core-only", action="store_true",
                    help="Restrict to core papers (cited_by_count >= 50)")
parser.add_argument("--supervised", action="store_true",
                    help="Use supervised seed axis (efficiency↔accountability) "
                         "instead of unsupervised PCA")
args = parser.parse_args()

# --- Paths ---
FIGURES_DIR = os.path.join(BASE_DIR, "content", "figures")
TABLES_DIR = os.path.join(BASE_DIR, "content", "tables")
os.makedirs(FIGURES_DIR, exist_ok=True)
os.makedirs(TABLES_DIR, exist_ok=True)


# --- Constants ---
_cfg = load_analysis_config()
CITE_THRESHOLD = _cfg["clustering"]["cite_threshold"]
DBIC_THRESHOLD = 200
N_COMPONENTS = 10

_period_tuples, _period_labels = load_analysis_periods()
PERIODS = dict(zip(_period_labels, _period_tuples))
PERIOD_COLORS = dict(zip(_period_labels, ["#8da0cb", "#fc8d62", "#66c2a5"]))

COP_EVENTS = {
    1992: "Rio",
    1997: "Kyoto",
    2009: "Copenhagen",
    2015: "Paris",
    2021: "Glasgow",
    2024: "Baku",
}

# Pole vocabularies (same as analyze_bimodality.py)
EFFICIENCY_TERMS = {
    "leverage", "de-risking", "mobilisation", "mobilization",
    "blended finance", "private finance", "green bond",
    "crowding-in", "bankable", "risk-adjusted", "financial instrument",
    "de-risk", "leveraging", "green bonds", "private sector",
}
ACCOUNTABILITY_TERMS = {
    "additionality", "over-reporting", "climate justice",
    "loss and damage", "grant-equivalent", "double counting",
    "accountability", "equity", "concessional", "oda",
    "grant equivalent", "overreporting", "climate debt",
}

# Output naming
if args.supervised:
    suffix = "_core" if args.core_only else ""
    FIG_STEM = f"fig_seed_axis{suffix}"
    TAB_FILE = f"tab_seed_axis{suffix}.csv"
elif args.core_only:
    FIG_STEM = "fig_pca_scatter_core"
    TAB_FILE = "tab_pca_components_core.csv"
else:
    FIG_STEM = "fig_pca_scatter"
    TAB_FILE = "tab_pca_components.csv"


# ============================================================
# Step 1: Load data + embeddings
# ============================================================

log.info("Loading data...")
_year_min = _cfg["periodization"]["year_min"]
_year_max = _cfg["periodization"]["year_max"]

works = pd.read_csv(os.path.join(CATALOGS_DIR, "refined_works.csv"))
works["year"] = pd.to_numeric(works["year"], errors="coerce")

has_title = works["title"].notna() & (works["title"].str.len() > 0)
in_range = (works["year"] >= _year_min) & (works["year"] <= _year_max)
df = works[has_title & in_range].copy().reset_index(drop=True)

embeddings = load_refined_embeddings()[(has_title & in_range).values]
assert len(embeddings) == len(df), (
    f"Embedding size mismatch: {len(embeddings)} vs {len(df)}"
)
log.info("Loaded %d papers with embeddings (%dD)", len(df), embeddings.shape[1])

df["cited_by_count"] = pd.to_numeric(df["cited_by_count"], errors="coerce").fillna(0)
if args.core_only:
    core_mask = df["cited_by_count"] >= CITE_THRESHOLD
    core_indices = df.index[core_mask].values
    df = df.loc[core_mask].reset_index(drop=True)
    embeddings = embeddings[core_indices]
    log.info("Core subset: %d papers (cited_by_count >= %d)", len(df), CITE_THRESHOLD)

df["year"] = df["year"].astype(int)
df["abstract_lower"] = df["abstract"].str.lower()


# ============================================================
# Step 2: Compute axes — supervised or unsupervised
# ============================================================

# Each entry: dict with keys component, scores (array), variance_explained,
#   delta_bic, top_positive_terms, top_negative_terms, label

axes_info = []

if args.supervised:
    # --- Supervised: seed axis from pole paper centroids ---
    log.info("--- Supervised mode: efficiency↔accountability seed axis ---")

    def count_pole_terms(text, terms):
        if pd.isna(text):
            return 0
        text = str(text).lower()
        return sum(1 for t in terms if t in text)

    df["eff_count"] = df["abstract_lower"].apply(
        lambda t: count_pole_terms(t, EFFICIENCY_TERMS))
    df["acc_count"] = df["abstract_lower"].apply(
        lambda t: count_pole_terms(t, ACCOUNTABILITY_TERMS))

    eff_mask = df["eff_count"] >= 2
    acc_mask = df["acc_count"] >= 2
    n_eff, n_acc = eff_mask.sum(), acc_mask.sum()
    log.info("Pole papers: %d efficiency, %d accountability", n_eff, n_acc)

    centroid_eff = embeddings[eff_mask].mean(axis=0)
    centroid_acc = embeddings[acc_mask].mean(axis=0)
    axis_vec = centroid_eff - centroid_acc
    axis_vec = axis_vec / np.linalg.norm(axis_vec)

    # Project all papers
    projections = embeddings @ axis_vec
    total_var = np.var(embeddings, axis=0).sum()
    axis_var = np.var(projections)
    explained_frac = axis_var / total_var
    log.info("Seed axis explains %.1f%% of total variance", explained_frac * 100)

    # Bimodality test
    proj_col = projections.reshape(-1, 1)
    gmm1 = GaussianMixture(n_components=1, random_state=42).fit(proj_col)
    gmm2 = GaussianMixture(n_components=2, random_state=42).fit(proj_col)
    dbic = gmm1.bic(proj_col) - gmm2.bic(proj_col)
    log.info("Seed axis ΔBIC = %.0f", dbic)

    axes_info.append({
        "component": "seed",
        "scores": projections,
        "variance_explained": explained_frac,
        "delta_bic": dbic,
        "bic_1comp": gmm1.bic(proj_col),
        "bic_2comp": gmm2.bic(proj_col),
        "top_positive_terms": "leverage, blended finance, private sector",
        "top_negative_terms": "additionality, climate justice, accountability",
        "label": "Efficiency \u2194 Accountability",
        "n_efficiency": n_eff,
        "n_accountability": n_acc,
    })

else:
    # --- Unsupervised: PCA + bimodality filtering ---
    log.info("Running PCA (n_components=%d)...", N_COMPONENTS)
    pca = PCA(n_components=N_COMPONENTS, random_state=42)
    pca_scores = pca.fit_transform(embeddings)

    log.info("Variance explained by first 10 PCs:")
    for i, v in enumerate(pca.explained_variance_ratio_):
        log.info("  PC%d: %.1f%%", i + 1, v * 100)
    log.info("  Total: %.1f%%", pca.explained_variance_ratio_.sum() * 100)

    log.info("Bimodality test (ΔBIC threshold = %d):", DBIC_THRESHOLD)
    for i in range(N_COMPONENTS):
        scores = pca_scores[:, i].reshape(-1, 1)
        gmm1 = GaussianMixture(n_components=1, random_state=42).fit(scores)
        gmm2 = GaussianMixture(n_components=2, random_state=42).fit(scores)
        dbic = gmm1.bic(scores) - gmm2.bic(scores)

        tag = " ***" if dbic > DBIC_THRESHOLD else ""
        log.info("  PC%d: ΔBIC = %.0f%s", i + 1, dbic, tag)

        if dbic > DBIC_THRESHOLD:
            axes_info.append({
                "component": i + 1,
                "scores": pca_scores[:, i],
                "variance_explained": pca.explained_variance_ratio_[i],
                "delta_bic": dbic,
                "bic_1comp": gmm1.bic(scores),
                "bic_2comp": gmm2.bic(scores),
            })

    if not axes_info:
        log.info("No PCs passed the bimodality threshold. Exiting.")
        raise SystemExit(0)

    log.info("%d qualifying PC(s): %s",
             len(axes_info), ", ".join("PC%d" % a['component'] for a in axes_info))

    # TF-IDF term labels for unsupervised PCs
    log.info("Fitting TF-IDF for term labelling...")
    abstracts = df["abstract"].fillna("").tolist()
    tfidf_vec = TfidfVectorizer(
        max_features=10000, ngram_range=(1, 2),
        sublinear_tf=True, stop_words="english",
    )
    X_tfidf = tfidf_vec.fit_transform(abstracts)
    feature_names = np.array(tfidf_vec.get_feature_names_out())

    for ax_info in axes_info:
        scores = ax_info["scores"]
        scores_centered = scores - scores.mean()
        scores_std = scores.std()
        if scores_std == 0:
            ax_info["top_positive_terms"] = ""
            ax_info["top_negative_terms"] = ""
            continue

        n = len(scores)
        col_means = np.asarray(X_tfidf.mean(axis=0)).flatten()
        xtz = np.asarray(X_tfidf.T.dot(scores_centered)).flatten()
        col_stds = np.sqrt(
            np.asarray(X_tfidf.multiply(X_tfidf).mean(axis=0)).flatten()
            - col_means ** 2)
        col_stds[col_stds == 0] = 1e-10
        correlations = xtz / (n * col_stds * scores_std)

        top_pos = feature_names[np.argsort(correlations)[-5:][::-1]].tolist()
        top_neg = feature_names[np.argsort(correlations)[:5]].tolist()
        ax_info["top_positive_terms"] = ", ".join(top_pos)
        ax_info["top_negative_terms"] = ", ".join(top_neg)
        ax_info["label"] = f"PC{ax_info['component']}"

        log.info("  PC%d (+): %s", ax_info['component'], ', '.join(top_pos))
        log.info("  PC%d (-): %s", ax_info['component'], ', '.join(top_neg))


# ============================================================
# Step 3: Scatter plot
# ============================================================

sns.set_style("whitegrid")
n_panels = len(axes_info)
fig_width = max(8, min(6 * n_panels, 24))
fig, plot_axes = plt.subplots(1, n_panels, figsize=(fig_width, 6), sharey=False,
                              squeeze=False)
plot_axes = plot_axes.flatten()

rng = np.random.RandomState(42)

for ax, ax_info in zip(plot_axes, axes_info):
    scores = ax_info["scores"]
    var_pct = ax_info["variance_explained"]
    dbic = ax_info["delta_bic"]

    # Period background bands
    for period_label, (y_start, y_end) in PERIODS.items():
        ax.axvspan(y_start - 0.5, y_end + 0.5,
                   alpha=0.08, color=PERIOD_COLORS[period_label], zorder=0)

    # Linear regression trend line (2000–2023, behind data)
    trend_mask = (df["year"] >= 2000) & (df["year"] <= 2023)
    trend_years = df.loc[trend_mask, "year"].values.astype(float)
    trend_scores = scores[trend_mask.values]
    slope, intercept = np.polyfit(trend_years, trend_scores, 1)
    x_line = np.array([2000, 2023])
    ax.plot(x_line, slope * x_line + intercept,
            color="black", linewidth=1.2, linestyle="--", alpha=0.5, zorder=1)

    # Scatter by period
    for period_label, (y_start, y_end) in PERIODS.items():
        pmask = (df["year"] >= y_start) & (df["year"] <= y_end)
        pscores = scores[pmask.values]
        cite_vals = df.loc[pmask, "cited_by_count"].values

        sizes = 8 + 3 * np.sqrt(cite_vals / max(CITE_THRESHOLD, 1))
        jitter = rng.uniform(-0.3, 0.3, size=pmask.sum())

        ax.scatter(
            df.loc[pmask, "year"].values + jitter, pscores,
            s=sizes, alpha=0.7, color=PERIOD_COLORS[period_label],
            edgecolors="none", label=period_label, zorder=2,
        )

    # Pole labels
    pos_terms = ax_info.get("top_positive_terms", "")
    neg_terms = ax_info.get("top_negative_terms", "")
    if pos_terms:
        top3 = ", ".join(pos_terms.split(", ")[:3])
        label_plus = "(+) Efficiency" if args.supervised else f"(+) {top3}"
        ax.text(0.97, 0.97, label_plus,
                transform=ax.transAxes, fontsize=7, ha="right", va="top",
                style="italic", color="#333333",
                bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                          edgecolor="grey", alpha=0.8))
    if neg_terms:
        top3 = ", ".join(neg_terms.split(", ")[:3])
        label_minus = "(-) Accountability" if args.supervised else f"(-) {top3}"
        ax.text(0.97, 0.03, label_minus,
                transform=ax.transAxes, fontsize=7, ha="right", va="bottom",
                style="italic", color="#333333",
                bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                          edgecolor="grey", alpha=0.8))

    # Title
    if args.supervised:
        ax.set_title(f"Efficiency \u2194 Accountability "
                     f"({var_pct:.1%} var, \u0394BIC={dbic:.0f})", fontsize=11)
        ax.set_ylabel("Score (efficiency \u2192 / \u2190 accountability)", fontsize=10)
    else:
        ax.set_title(f"PC{ax_info['component']} ({var_pct:.1%} var, "
                     f"\u0394BIC={dbic:.0f})", fontsize=11)
        ax.set_ylabel(f"PC{ax_info['component']} score", fontsize=10)
    ax.set_xlabel("Year", fontsize=10)
    ax.set_xlim(1999.5, 2023.5)
    ax.set_ylim(-0.5, 0.5)

    # Custom x-axis ticks: add (Bali) under 2007, (Paris) under 2015
    tick_years = list(range(2000, 2024, 5))  # 2000, 2005, 2010, 2015, 2020
    if 2007 not in tick_years:
        tick_years.append(2007)
    tick_years.sort()
    tick_labels = []
    for y in tick_years:
        if y == 2007:
            tick_labels.append("2007\n(Bali)")
        elif y == 2015:
            tick_labels.append("2015\n(Paris)")
        else:
            tick_labels.append(str(y))
    ax.set_xticks(tick_years)
    ax.set_xticklabels(tick_labels)

core_label = " (core, cited \u2265 50)" if args.core_only else ""
if args.supervised:
    fig.suptitle(f"Efficiency \u2194 Accountability axis over time{core_label}",
                 fontsize=13, y=1.02)
else:
    fig.suptitle(f"PCA bimodal axes: paper distribution over time{core_label}",
                 fontsize=13, y=1.02)
plt.tight_layout()

save_figure(fig, os.path.join(FIGURES_DIR, FIG_STEM), no_pdf=args.no_pdf)
plt.close()


# ============================================================
# Step 4: Save metadata table
# ============================================================

tab_rows = []
for ax_info in axes_info:
    row = {k: v for k, v in ax_info.items() if k != "scores"}
    tab_rows.append(row)
tab = pd.DataFrame(tab_rows)
tab.to_csv(os.path.join(TABLES_DIR, TAB_FILE), index=False)
log.info("Saved -> tables/%s", TAB_FILE)

log.info("Done.")
