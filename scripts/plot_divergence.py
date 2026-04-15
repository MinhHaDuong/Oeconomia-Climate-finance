"""Unified divergence plot: one figure per method across all channels.

Reads any CSV conforming to DivergenceSchema:
    year, channel, window, hyperparams, value

The method name is derived from the filename (tab_div_{method}.csv or
tab_sens_{pca,jl}_{method}.csv).

Styles:
  --style lines     One curve per (window, hyperparams) group (default)
  --style gradient  Curves ordered by a continuous variable (e.g. PCA dim),
                    color gradient from light to dark, black baseline
  --style ribbon    Aggregate over replicate runs: median +/- IQR ribbon

Produces one PNG: --output path.

Usage:
    # Standard divergence plot
    python3 scripts/plot_divergence.py \
        --output content/figures/fig_divergence_S1_MMD.png \
        --input content/tables/tab_div_S1_MMD.csv

    # PCA sensitivity
    python3 scripts/plot_divergence.py --style pca \
        --output content/figures/fig_sensitivity_pca_S1_MMD.png \
        --input content/tables/tab_sens_pca_S1_MMD.csv

    # JL sensitivity
    python3 scripts/plot_divergence.py --style jl \
        --output content/figures/fig_sensitivity_jl_S2_energy.png \
        --input content/tables/tab_sens_jl_S2_energy.csv
"""

import argparse
import os
import re
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
    "G1_pagerank": ("G1: PageRank volatility", "1 − Kendall τ"),
    "G2_spectral": ("G2: Spectral gap", "λ₂ − λ₁"),
    "G3_coupling_age": ("G3: Bibliographic coupling age", "Median ref year"),
    "G4_cross_tradition": ("G4: Cross-tradition ratio", "Cross-community fraction"),
    "G5_pref_attachment": ("G5: Pref. attachment exponent", "α"),
    "G6_entropy": ("G6: Citation entropy", "Shannon entropy"),
    "G7_disruption": ("G7: Disruption index", "Mean CD"),
    "G8_betweenness": ("G8: Betweenness centrality", "Mean betweenness"),
}


# ── PCA / JL visual encoding ────────────────────────────────────────────

PCA_COLORS = {32: "#bdbdbd", 64: "#969696", 128: "#737373", 256: "#525252", 512: "#252525"}
JL_COLORS = {64: "#1f77b4", 128: "#ff7f0e", 256: "#2ca02c"}


def _parse_projection_tag(hyperparams):
    """Extract projection tag from hyperparams string."""
    match = re.search(r"projection=(\S+)", str(hyperparams))
    if not match:
        return None, None, None
    tag = match.group(1)
    if tag == "original":
        return "original", None, None
    m = re.match(r"pca_(\d+)", tag)
    if m:
        return "pca", int(m.group(1)), None
    m = re.match(r"jl_(\d+)_run(\d+)", tag)
    if m:
        return "jl", int(m.group(1)), int(m.group(2))
    return tag, None, None


def _strip_projection_from_hp(hp):
    return re.sub(r";?projection=\S+", "", str(hp)).strip(";").strip()


def _pick_base_hp(df):
    """Pick a single base hyperparam setting for clean plotting."""
    base_hps = sorted(df["base_hp"].unique())
    for hp in base_hps:
        if hp in ("", "default"):
            return hp
    return base_hps[0] if base_hps else ""


# ── Method name extraction ──────────────────────────────────────────────

def _extract_method_from_path(path):
    """Extract method name from filename.

    Supports: tab_div_{method}.csv, tab_sens_pca_{method}.csv,
    tab_sens_jl_{method}.csv.
    """
    basename = os.path.splitext(os.path.basename(path))[0]
    if basename.startswith("tab_div_"):
        return basename[len("tab_div_"):]
    m = re.match(r"tab_sens_(?:pca|jl)_(.+)", basename)
    if m:
        return m.group(1)
    return None


def _load_tables(input_paths):
    """Load and concatenate divergence tables.

    Supports both new (tab_div_{method}.csv, no 'method' column) and legacy
    (tab_{channel}_divergence.csv, has 'method' column) formats.
    """
    div_frames = []
    breaks_frames = []

    for path in input_paths:
        if not os.path.exists(path):
            log.warning("Input not found: %s", path)
            continue
        df = pd.read_csv(path)

        # New format: method derived from filename, columns have no 'method'
        if "method" not in df.columns:
            method = _extract_method_from_path(path)
            if method is None:
                log.warning("Cannot determine method from filename: %s", path)
                continue
            df["method"] = method

        # Enforce minimum columns
        expected = {"year", "channel", "window", "hyperparams", "value"}
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
    log.info("Saved %s_%s.png", out_stem, method)


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


# ── Gradient style (e.g. PCA dimensionality sweep) ──────────────────────

def _plot_gradient(div_df, method, output_path):
    """Curves ordered by projection dimension, color gradient, black baseline."""
    mdf = div_df[div_df["method"] == method].dropna(subset=["value"]).copy()
    if mdf.empty:
        log.warning("No data for %s; skipping", method)
        return

    fig, ax = plt.subplots(figsize=(FIGWIDTH, FIGHEIGHT))

    parsed = mdf["hyperparams"].apply(_parse_projection_tag)
    mdf["proj_type"] = [p[0] for p in parsed]
    mdf["proj_dim"] = [p[1] for p in parsed]
    mdf["base_hp"] = mdf["hyperparams"].apply(_strip_projection_from_hp)

    target_hp = _pick_base_hp(mdf)
    sub = mdf[mdf["base_hp"] == target_hp]

    orig = sub[sub["proj_type"] == "original"].sort_values("year")
    if not orig.empty:
        ax.plot(orig["year"], orig["value"], color="black", linewidth=1.2,
                label="original (1024d)", zorder=10)

    for d in sorted(PCA_COLORS.keys()):
        pca_d = sub[sub["proj_dim"] == d].sort_values("year")
        if not pca_d.empty:
            ax.plot(pca_d["year"], pca_d["value"],
                    color=PCA_COLORS[d], linewidth=0.9, label=f"d={d}")

    title, ylabel = METHOD_LABELS.get(method, (method, "value"))
    if isinstance(title, tuple):
        title = title[0]
    ax.set_title(f"{title} — dimensionality sensitivity")
    ax.set_xlabel("Year")
    ax.set_ylabel("Divergence value")
    ax.legend(loc="best", frameon=False, fontsize=6)
    fig.tight_layout()
    fig.savefig(output_path, dpi=DPI)
    plt.close(fig)
    log.info("Saved %s", output_path)


# ── Ribbon style (e.g. JL random projections) ──────────────────────────

def _plot_ribbon(div_df, method, output_path):
    """Fan/ribbon: median +/- IQR across replicate runs, per dimension."""
    mdf = div_df[div_df["method"] == method].dropna(subset=["value"]).copy()
    if mdf.empty:
        log.warning("No data for %s; skipping", method)
        return

    fig, ax = plt.subplots(figsize=(FIGWIDTH, FIGHEIGHT))

    parsed = mdf["hyperparams"].apply(_parse_projection_tag)
    mdf["proj_type"] = [p[0] for p in parsed]
    mdf["proj_dim"] = [p[1] for p in parsed]
    mdf["run"] = [p[2] for p in parsed]
    mdf["base_hp"] = mdf["hyperparams"].apply(_strip_projection_from_hp)

    target_hp = _pick_base_hp(mdf)
    sub = mdf[(mdf["base_hp"] == target_hp) & (mdf["proj_type"] == "jl")]

    for d in sorted(JL_COLORS.keys()):
        dim_data = sub[sub["proj_dim"] == d]
        if dim_data.empty:
            continue
        stats = dim_data.groupby("year")["value"].agg(
            ["median", lambda x: x.quantile(0.25), lambda x: x.quantile(0.75)]
        ).reset_index()
        stats.columns = ["year", "median", "q25", "q75"]
        stats = stats.sort_values("year")

        color = JL_COLORS[d]
        ax.fill_between(stats["year"], stats["q25"], stats["q75"],
                        alpha=0.25, color=color)
        ax.plot(stats["year"], stats["median"], color=color, linewidth=1.0,
                label=f"d={d} (median ± IQR)")

    title, ylabel = METHOD_LABELS.get(method, (method, "value"))
    if isinstance(title, tuple):
        title = title[0]
    ax.set_title(f"{title} — random projection stability")
    ax.set_xlabel("Year")
    ax.set_ylabel("Divergence value")
    ax.legend(loc="best", frameon=False, fontsize=6)
    fig.tight_layout()
    fig.savefig(output_path, dpi=DPI)
    plt.close(fig)
    log.info("Saved %s", output_path)


# ── Main ────────────────────────────────────────────────────────────────

def main():
    io_args, extra = parse_io_args()
    validate_io(output=io_args.output)

    parser = argparse.ArgumentParser()
    parser.add_argument("--style", default="lines",
                        choices=["lines", "gradient", "ribbon"],
                        help="Plot style: lines (default), gradient, ribbon")
    args = parser.parse_args(extra)

    if not io_args.input:
        tables_dir = os.path.join(os.path.dirname(os.path.dirname(io_args.output)),
                                  "tables")
        import glob
        io_args.input = sorted(glob.glob(os.path.join(tables_dir, "tab_div_*.csv")))

    div_df, breaks_df = _load_tables(io_args.input)

    if div_df.empty:
        log.warning("No divergence data found; nothing to plot")
        return

    methods = sorted(div_df["method"].unique())
    log.info("Plotting %d methods (style=%s): %s", len(methods), args.style, methods)

    for method in methods:
        if args.style == "gradient":
            _plot_gradient(div_df, method, io_args.output)
        elif args.style == "ribbon":
            _plot_ribbon(div_df, method, io_args.output)
        else:
            out_stem = os.path.splitext(io_args.output)[0]
            _plot_one_method(div_df, breaks_df, method, out_stem)

    log.info("Done.")


if __name__ == "__main__":
    main()
