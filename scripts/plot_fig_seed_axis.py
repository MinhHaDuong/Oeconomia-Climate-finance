"""Violin plot of efficiency-accountability score distribution by period.

Produces a three-panel violin plot (one per period) showing how core papers
distribute along the efficiency-accountability seed axis. Replaces the
scatter plot for the manuscript figure.

Produces:
- figures/fig_seed_axis_core.{png,pdf}
- tables/tab_seed_axis_core.csv

Usage:
    uv run python scripts/plot_fig_seed_axis.py --output content/figures/fig_seed_axis_core.png [--pdf]
"""

import argparse
import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from plot_style import DARK, DPI, FIGWIDTH, MED, apply_style
from sklearn.mixture import GaussianMixture
from script_io_args import parse_io_args, validate_io
from utils import (
    BASE_DIR,
    CATALOGS_DIR,
    get_logger,
    load_analysis_config,
    load_analysis_periods,
    load_refined_embeddings,
    save_figure,
)

log = get_logger("plot_fig_seed_axis")

TABLES_DIR = os.path.join(BASE_DIR, "content", "tables")

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


def _count_pole_terms(text, terms):
    if pd.isna(text):
        return 0
    text = str(text).lower()
    return sum(1 for t in terms if t in text)


def main():
    io_args, extra = parse_io_args()
    validate_io(output=io_args.output)

    parser = argparse.ArgumentParser(description="Seed-axis violin plot (Fig seed)")
    parser.add_argument("--pdf", action="store_true", help="Also save PDF output")
    args = parser.parse_args(extra)

    apply_style()

    _cfg = load_analysis_config()
    cite_threshold = _cfg["clustering"]["cite_threshold"]
    _year_min = _cfg["periodization"]["year_min"]
    _year_max = _cfg["periodization"]["year_max"]

    _period_tuples, _period_labels = load_analysis_periods()
    periods = dict(zip(_period_labels, _period_tuples))
    _subtitles = ["", "(Bali)", "(Paris)"]
    period_subtitles = dict(zip(_period_labels, _subtitles))
    _fills = ["#CCCCCC", "#999999", "#666666"]
    period_fills = dict(zip(_period_labels, _fills))

    # ── Load data + embeddings ──
    log.info("Loading data...")
    works = pd.read_csv(os.path.join(CATALOGS_DIR, "refined_works.csv"))
    works["year"] = pd.to_numeric(works["year"], errors="coerce")

    has_title = works["title"].notna() & (works["title"].str.len() > 0)
    in_range = (works["year"] >= _year_min) & (works["year"] <= _year_max)
    df = works[has_title & in_range].copy().reset_index(drop=True)

    embeddings = load_refined_embeddings()[(has_title & in_range).values]
    assert len(embeddings) == len(df)
    log.info("Loaded %d papers with embeddings (%dD)", len(df), embeddings.shape[1])

    df["cited_by_count"] = pd.to_numeric(df["cited_by_count"], errors="coerce").fillna(0)
    core_mask = df["cited_by_count"] >= cite_threshold
    core_indices = df.index[core_mask].values
    df = df.loc[core_mask].reset_index(drop=True)
    embeddings = embeddings[core_indices]
    log.info("Core subset: %d papers (cited_by_count >= %d)", len(df), cite_threshold)

    df["year"] = df["year"].astype(int)
    df["abstract_lower"] = df["abstract"].str.lower()

    # ── Compute seed axis ──
    df["eff_count"] = df["abstract_lower"].apply(lambda t: _count_pole_terms(t, EFFICIENCY_TERMS))
    df["acc_count"] = df["abstract_lower"].apply(lambda t: _count_pole_terms(t, ACCOUNTABILITY_TERMS))

    eff_mask = df["eff_count"] >= 2
    acc_mask = df["acc_count"] >= 2
    log.info("Pole papers: %d efficiency, %d accountability", eff_mask.sum(), acc_mask.sum())

    centroid_eff = embeddings[eff_mask].mean(axis=0)
    centroid_acc = embeddings[acc_mask].mean(axis=0)
    axis_vec = centroid_eff - centroid_acc
    axis_vec = axis_vec / np.linalg.norm(axis_vec)
    df["score"] = embeddings @ axis_vec

    # ── Per-period statistics ──
    stats_rows = []
    period_data = {}

    for period_label, (y_start, y_end) in periods.items():
        pmask = (df["year"] >= y_start) & (df["year"] <= y_end)
        pscores = df.loc[pmask, "score"].values
        period_data[period_label] = pscores

        n = len(pscores)
        median_val = np.median(pscores) if n > 0 else np.nan
        mean_val = np.mean(pscores) if n > 0 else np.nan
        dbic = np.nan
        if n >= 20:
            col = pscores.reshape(-1, 1)
            g1 = GaussianMixture(n_components=1, random_state=42).fit(col)
            g2 = GaussianMixture(n_components=2, random_state=42).fit(col)
            dbic = g1.bic(col) - g2.bic(col)

        stats_rows.append({
            "period": period_label, "n_papers": n,
            "median": round(median_val, 4), "mean": round(mean_val, 4),
            "bimodal_dbic": round(dbic, 1) if not np.isnan(dbic) else None,
        })
        log.info("  %s: n=%d, median=%.3f, mean=%.3f, DBIC=%.0f",
                 period_label, n, median_val, mean_val, dbic)

    # ── Violin plot ──
    fig, axes = plt.subplots(1, 3, figsize=(FIGWIDTH, FIGWIDTH * 0.6), sharey=True)

    period_labels_list = list(periods.keys())
    medians = [np.median(period_data[p]) for p in period_labels_list]

    for i, (ax, period_label) in enumerate(zip(axes, period_labels_list)):
        pscores = period_data[period_label]
        if len(pscores) < 5:
            ax.set_title(f"{period_label}\n(n={len(pscores)}, too few)")
            continue

        parts = ax.violinplot(pscores, positions=[0], showmeans=False,
                              showmedians=False, showextrema=False)
        for pc in parts["bodies"]:
            pc.set_facecolor(period_fills[period_label])
            pc.set_edgecolor(DARK)
            pc.set_linewidth(0.5)
            pc.set_alpha(0.8)

        ax.plot(0, medians[i], "o", color=DARK, markersize=4, zorder=5)
        ax.axhline(0, color=MED, linestyle="--", linewidth=0.5, zorder=1)

        subtitle = period_subtitles[period_label]
        n = len(pscores)
        if subtitle:
            ax.set_xlabel(f"{period_label}\n{subtitle}\n(n={n})", fontsize=7)
        else:
            ax.set_xlabel(f"{period_label}\n(n={n})", fontsize=7)
        ax.set_xlim(-0.8, 0.8)
        ax.set_xticks([])

    for i in range(len(period_labels_list) - 1):
        from matplotlib.patches import ConnectionPatch
        con = ConnectionPatch(
            xyA=(0, medians[i]), coordsA=axes[i].transData,
            xyB=(0, medians[i + 1]), coordsB=axes[i + 1].transData,
            color=DARK, linewidth=0.8, linestyle="-", zorder=4,
        )
        fig.add_artist(con)

    axes[0].set_ylim(-0.5, 0.5)
    axes[0].set_ylabel("\u2190 Accountability     Score     Efficiency \u2192", fontsize=7)

    plt.tight_layout()
    out_stem = os.path.splitext(io_args.output)[0]
    save_figure(fig, out_stem, pdf=args.pdf, dpi=DPI)
    plt.close()

    # ── Save CSV ──
    out_dir = os.path.dirname(io_args.output)
    tab = pd.DataFrame(stats_rows)
    csv_path = os.path.join(out_dir, "tab_seed_axis_core.csv") if out_dir else "tab_seed_axis_core.csv"
    tab.to_csv(csv_path, index=False)
    log.info("Saved -> %s", csv_path)

    log.info("Done.")


if __name__ == "__main__":
    main()
