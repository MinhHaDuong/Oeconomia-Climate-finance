"""Violin plot of efficiency-accountability score distribution by period.

Produces a three-panel violin plot (one per period) showing how core papers
distribute along the efficiency-accountability seed axis. Replaces the
scatter plot for the manuscript figure.

Produces:
- figures/fig_seed_axis_core.{png,pdf}
- tables/tab_seed_axis_core.csv

Usage:
    uv run python scripts/plot_fig_seed_axis.py [--no-pdf]
"""

import argparse
import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.mixture import GaussianMixture

from plot_style import apply_style, FIGWIDTH, DPI, DARK, MED
from utils import (BASE_DIR, CATALOGS_DIR, get_logger, load_refined_embeddings,
                   save_figure, load_analysis_config, load_analysis_periods)

log = get_logger("plot_fig_seed_axis")

# --- Args ---
parser = argparse.ArgumentParser(description="Seed-axis violin plot (Fig seed)")
parser.add_argument("--no-pdf", action="store_true", help="Skip PDF generation (PNG only)")
args = parser.parse_args()

apply_style()

# --- Paths ---
FIGURES_DIR = os.path.join(BASE_DIR, "content", "figures")
TABLES_DIR = os.path.join(BASE_DIR, "content", "tables")
os.makedirs(FIGURES_DIR, exist_ok=True)
os.makedirs(TABLES_DIR, exist_ok=True)

# --- Constants ---
_cfg = load_analysis_config()
CITE_THRESHOLD = _cfg["clustering"]["cite_threshold"]

# Periods from config (fixes 2023 inconsistency)
_period_tuples, _period_labels = load_analysis_periods()
PERIODS = dict(zip(_period_labels, _period_tuples))

_SUBTITLES = ["", "(Bali)", "(Paris)"]
PERIOD_SUBTITLES = dict(zip(_period_labels, _SUBTITLES))

# Grayscale fills: light to dark
_FILLS = ["#CCCCCC", "#999999", "#666666"]
PERIOD_FILLS = dict(zip(_period_labels, _FILLS))

# Pole vocabularies (same as analyze_bimodality.py / plot_fig45_pca_scatter.py)
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


# ============================================================
# Step 1: Load data + embeddings (same filter as analyze_bimodality.py)
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

# Core filtering
df["cited_by_count"] = pd.to_numeric(df["cited_by_count"], errors="coerce").fillna(0)
core_mask = df["cited_by_count"] >= CITE_THRESHOLD
core_indices = df.index[core_mask].values
df = df.loc[core_mask].reset_index(drop=True)
embeddings = embeddings[core_indices]
log.info("Core subset: %d papers (cited_by_count >= %d)", len(df), CITE_THRESHOLD)

df["year"] = df["year"].astype(int)
df["abstract_lower"] = df["abstract"].str.lower()


# ============================================================
# Step 2: Compute seed axis (efficiency - accountability centroids)
# ============================================================

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
df["score"] = projections


# ============================================================
# Step 3: Per-period statistics
# ============================================================

stats_rows = []
period_data = {}

for period_label, (y_start, y_end) in PERIODS.items():
    pmask = (df["year"] >= y_start) & (df["year"] <= y_end)
    pscores = df.loc[pmask, "score"].values
    period_data[period_label] = pscores

    n = len(pscores)
    median_val = np.median(pscores) if n > 0 else np.nan
    mean_val = np.mean(pscores) if n > 0 else np.nan

    # Bimodality test within period
    dbic = np.nan
    if n >= 20:
        col = pscores.reshape(-1, 1)
        g1 = GaussianMixture(n_components=1, random_state=42).fit(col)
        g2 = GaussianMixture(n_components=2, random_state=42).fit(col)
        dbic = g1.bic(col) - g2.bic(col)

    stats_rows.append({
        "period": period_label,
        "n_papers": n,
        "median": round(median_val, 4),
        "mean": round(mean_val, 4),
        "bimodal_dbic": round(dbic, 1) if not np.isnan(dbic) else None,
    })

    log.info("  %s: n=%d, median=%.3f, mean=%.3f, DBIC=%.0f",
             period_label, n, median_val, mean_val, dbic)


# ============================================================
# Step 4: Violin plot
# ============================================================

fig, axes = plt.subplots(1, 3, figsize=(FIGWIDTH, FIGWIDTH * 0.6),
                         sharey=True)

period_labels = list(PERIODS.keys())
medians = [np.median(period_data[p]) for p in period_labels]

for i, (ax, period_label) in enumerate(zip(axes, period_labels)):
    pscores = period_data[period_label]

    if len(pscores) < 5:
        ax.set_title(f"{period_label}\n(n={len(pscores)}, too few)")
        continue

    # Violin
    parts = ax.violinplot(pscores, positions=[0], showmeans=False,
                          showmedians=False, showextrema=False)
    for pc in parts["bodies"]:
        pc.set_facecolor(PERIOD_FILLS[period_label])
        pc.set_edgecolor(DARK)
        pc.set_linewidth(0.5)
        pc.set_alpha(0.8)

    # Median dot
    ax.plot(0, medians[i], "o", color=DARK, markersize=4, zorder=5)

    # Horizontal dashed line at y=0
    ax.axhline(0, color=MED, linestyle="--", linewidth=0.5, zorder=1)

    # Labels
    subtitle = PERIOD_SUBTITLES[period_label]
    n = len(pscores)
    if subtitle:
        ax.set_xlabel(f"{period_label}\n{subtitle}\n(n={n})", fontsize=7)
    else:
        ax.set_xlabel(f"{period_label}\n(n={n})", fontsize=7)

    ax.set_xlim(-0.8, 0.8)
    ax.set_xticks([])

# Connect medians with a thin line across panels
# We need to use figure-level coordinates
for i in range(len(period_labels) - 1):
    # Draw a connection line using annotation in figure coords
    ax_left = axes[i]
    ax_right = axes[i + 1]
    # Use ConnectionPatch for cross-axes lines
    from matplotlib.patches import ConnectionPatch
    con = ConnectionPatch(
        xyA=(0, medians[i]), coordsA=ax_left.transData,
        xyB=(0, medians[i + 1]), coordsB=ax_right.transData,
        color=DARK, linewidth=0.8, linestyle="-", zorder=4,
    )
    fig.add_artist(con)

# y-axis settings
axes[0].set_ylim(-0.5, 0.5)
axes[0].set_ylabel("\u2190 Accountability     Score     Efficiency \u2192",
                    fontsize=7)

plt.tight_layout()

save_figure(fig, os.path.join(FIGURES_DIR, "fig_seed_axis_core"),
            no_pdf=args.no_pdf, dpi=DPI)
plt.close()


# ============================================================
# Step 5: Save CSV
# ============================================================

tab = pd.DataFrame(stats_rows)
tab.to_csv(os.path.join(TABLES_DIR, "tab_seed_axis_core.csv"), index=False)
log.info("Saved -> tables/tab_seed_axis_core.csv")

log.info("Done.")
