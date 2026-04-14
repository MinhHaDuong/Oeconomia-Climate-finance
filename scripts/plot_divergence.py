"""Unified divergence plot: one figure per method across all channels.

Reads any tab_*_divergence.csv conforming to the output contract:
    year, method, channel, window, hyperparams, value

and its companion _breaks.csv:
    method, channel, window, hyperparams, penalty, break_years

Produces one PNG per unique method found in the data:
    {output_stem}_{method}.png

Usage:
    python3 scripts/plot_divergence.py \
        --output content/figures/fig_divergence.png \
        --input content/tables/tab_semantic_divergence.csv \
               content/tables/tab_lexical_divergence.csv \
               content/tables/tab_citation_divergence.csv
"""

import os
import sys

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from script_io_args import parse_io_args, validate_io
from utils import get_logger

log = get_logger("plot_divergence")

matplotlib.rcParams.update({
    "font.family": "serif",
    "font.size": 8,
    "axes.titlesize": 10,
    "axes.labelsize": 8,
    "xtick.labelsize": 7,
    "ytick.labelsize": 7,
    "legend.fontsize": 6,
    "figure.dpi": 300,
    "savefig.dpi": 300,
    "axes.linewidth": 0.5,
    "lines.linewidth": 0.8,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": False,
})

# ── Visual encoding ──────────────────────────────────────────────────────

WINDOW_STYLES = {2: "-", 3: "--", 4: "-.", 5: ":", "cumulative": "-"}
COLORS = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
    "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
]
FIGWIDTH = 135 / 25.4   # ~5.3 inches
FIGHEIGHT = 3.2
DPI = 300
BREAK_PENALTY = 3        # default penalty for break overlay


# ── Method display names ─────────────────────────────────────────────────

METHOD_LABELS = {
    "S1_MMD": ("S1: MMD (RBF kernel)", "MMD²"),
    "S2_energy": ("S2: Energy distance", "Energy distance"),
    "S3_sliced_wasserstein": ("S3: Sliced Wasserstein", "Sliced Wasserstein"),
    "S4_frechet": ("S4: Fréchet distance", "Fréchet distance"),
    "L1": ("L1: JS divergence (TF-IDF)", "JS divergence"),
    "L2": ("L2: Novelty / Transience", "KL divergence"),
    "L3": ("L3: Term bursts", "Terms in burst"),
    "G1_pagerank_volatility": ("G1: PageRank volatility", "1 − Kendall τ"),
    "G2_spectral_gap": ("G2: Spectral gap", "λ₂ − λ₁"),
    "G3_coupling_age": ("G3: Bibliographic coupling age", "Median ref year"),
    "G4_cross_tradition": ("G4: Cross-tradition ratio", "Cross-community fraction"),
    "G5_pref_attachment": ("G5: Pref. attachment exponent", "α"),
    "G6_citation_entropy": ("G6: Citation entropy", "Shannon entropy"),
    "G7_disruption": ("G7: Disruption index", "Mean CD"),
    "G8_betweenness": ("G8: Betweenness centrality", "Mean betweenness"),
}


def _load_tables(input_paths):
    """Load and concatenate divergence + breaks tables."""
    div_frames = []
    breaks_frames = []

    for path in input_paths:
        if not os.path.exists(path):
            log.warning("Input not found: %s", path)
            continue
        df = pd.read_csv(path)
        # Enforce contract columns
        expected = {"year", "method", "channel", "window", "hyperparams", "value"}
        if not expected.issubset(set(df.columns)):
            log.warning("Skipping %s: missing columns %s",
                        path, expected - set(df.columns))
            continue
        div_frames.append(df)

        # Look for companion breaks file
        breaks_path = os.path.splitext(path)[0] + "_breaks.csv"
        if os.path.exists(breaks_path):
            breaks_frames.append(pd.read_csv(breaks_path))

    div_df = pd.concat(div_frames, ignore_index=True) if div_frames else pd.DataFrame()
    breaks_df = pd.concat(breaks_frames, ignore_index=True) if breaks_frames else pd.DataFrame()
    log.info("Loaded %d divergence rows, %d break rows from %d files",
             len(div_df), len(breaks_df), len(div_frames))
    return div_df, breaks_df


def _get_break_years(breaks_df, method, penalty=BREAK_PENALTY):
    """Extract break years for a method at given penalty."""
    if breaks_df.empty or "break_years" not in breaks_df.columns:
        return set()
    mask = (breaks_df["method"] == method) & (breaks_df["penalty"] == penalty)
    years = set()
    for val in breaks_df.loc[mask, "break_years"].dropna():
        for y in str(val).split(";"):
            y = y.strip()
            if y:
                try:
                    years.add(int(float(y)))
                except ValueError:
                    pass
    return years


def _plot_one_method(div_df, breaks_df, method, out_stem):
    """Plot one figure for a single method."""
    mdf = div_df[div_df["method"] == method].dropna(subset=["value"]).copy()
    if mdf.empty:
        log.warning("No data for %s; skipping", method)
        return

    title, ylabel = METHOD_LABELS.get(method, (method, "value"))

    # L2 has sub-metrics (novelty, transience, resonance) encoded in hyperparams
    is_l2 = method == "L2"
    if is_l2:
        metrics = [hp for hp in mdf["hyperparams"].unique()
                   if any(m in str(hp) for m in ["novelty", "transience", "resonance"])]
        n_panels = max(1, len(set(
            m.split(",")[1].split("=")[1] if "," in str(m) else "all"
            for m in metrics
        )))
        if n_panels > 1:
            fig, axes = plt.subplots(n_panels, 1, figsize=(FIGWIDTH, FIGHEIGHT * n_panels * 0.7),
                                     sharex=True)
            metric_names = sorted(set(
                str(hp).split("metric=")[1] if "metric=" in str(hp) else "all"
                for hp in mdf["hyperparams"].unique()
            ))
            for ax, metric_name in zip(axes, metric_names):
                sub = mdf[mdf["hyperparams"].str.contains(metric_name, na=False)]
                _draw_curves(ax, sub, breaks_df, method)
                ax.set_ylabel(metric_name.capitalize())
                ax.set_title("")
            axes[0].set_title(title)
            axes[-1].set_xlabel("Year")
            fig.tight_layout()
            fig.savefig(f"{out_stem}_{method}.png", dpi=DPI)
            plt.close(fig)
            log.info("Saved %s_%s.png (%d panels)", out_stem, method, n_panels)
            return

    fig, ax = plt.subplots(figsize=(FIGWIDTH, FIGHEIGHT))
    _draw_curves(ax, mdf, breaks_df, method)
    ax.set_xlabel("Year")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(f"{out_stem}_{method}.png", dpi=DPI)
    plt.close(fig)
    log.info("Saved %s_%method.png", out_stem, method)


def _draw_curves(ax, mdf, breaks_df, method):
    """Draw temporal curves and break lines on a single axes."""
    # Group by (window, hyperparams) → one curve each
    groups = mdf.groupby(["window", "hyperparams"])
    color_idx = 0
    for (window, hp), grp in sorted(groups):
        grp = grp.sort_values("year")
        w_key = int(window) if str(window).isdigit() else window
        ls = WINDOW_STYLES.get(w_key, "-")
        color = COLORS[color_idx % len(COLORS)]
        label = f"w={window}" if hp in ("default", "", "cumulative") else f"w={window}, {hp}"
        ax.plot(grp["year"], grp["value"], color=color, linestyle=ls,
                linewidth=0.9, label=label)
        color_idx += 1

    # Break lines
    break_years = _get_break_years(breaks_df, method, BREAK_PENALTY)
    for by in sorted(break_years):
        ax.axvline(by, color="red", linewidth=0.7, linestyle="--", alpha=0.7)

    # Legend
    handles, labels = ax.get_legend_handles_labels()
    if handles:
        ncol = 2 if len(handles) <= 12 else 3
        ax.legend(loc="best", frameon=False, fontsize=5.5, ncol=ncol)


def main():
    io_args, _extra = parse_io_args()
    validate_io(output=io_args.output)

    if not io_args.input:
        # Default: look for all three divergence tables
        tables_dir = os.path.join(os.path.dirname(os.path.dirname(io_args.output)),
                                  "tables")
        io_args.input = [
            os.path.join(tables_dir, f)
            for f in ["tab_semantic_divergence.csv",
                       "tab_lexical_divergence.csv",
                       "tab_citation_divergence.csv"]
            if os.path.exists(os.path.join(tables_dir, f))
        ]

    div_df, breaks_df = _load_tables(io_args.input)

    if div_df.empty:
        log.warning("No divergence data found; nothing to plot")
        return

    out_stem = os.path.splitext(io_args.output)[0]

    methods = sorted(div_df["method"].unique())
    log.info("Plotting %d methods: %s", len(methods), methods)

    for method in methods:
        _plot_one_method(div_df, breaks_df, method, out_stem)

    log.info("All %d figures done.", len(methods))


if __name__ == "__main__":
    main()
