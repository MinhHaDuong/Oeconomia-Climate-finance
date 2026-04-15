"""Unified divergence plot: one figure per method across all channels.

Reads any CSV conforming to DivergenceSchema:
    year, channel, window, hyperparams, value

The method name is derived from the filename (tab_div_{method}.csv or
tab_sens_{pca,jl}_{method}.csv).

Styles:
  --aggregate none    One curve per (window, hyperparams) group (default)
  --aggregate ribbon  Median +/- IQR over replicate runs

  --palette auto      Discrete colors per group (default)
  --palette gradient  Light-to-dark gradient ordered by dimension, black baseline

Produces one PNG: --output path.

Usage:
    # Standard divergence plot
    python3 scripts/plot_divergence.py \
        --output content/figures/fig_divergence_S1_MMD.png \
        --input content/tables/tab_div_S1_MMD.csv

    # PCA sensitivity (gradient palette)
    python3 scripts/plot_divergence.py --palette gradient \
        --output content/figures/fig_sensitivity_pca_S1_MMD.png \
        --input content/tables/tab_sens_pca_S1_MMD.csv

    # JL sensitivity (ribbon aggregate)
    python3 scripts/plot_divergence.py --aggregate ribbon \
        --output content/figures/fig_sensitivity_jl_S2_energy.png \
        --input content/tables/tab_sens_jl_S2_energy.csv
"""

import argparse
import os
import re
import sys

import matplotlib
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _divergence_io import load_divergence_tables
from pipeline_io import save_figure
from plot_style import apply_style
from script_io_args import parse_io_args, validate_io
from utils import get_logger

log = get_logger("plot_divergence")

apply_style()
# Override base style: larger titles, smaller legends for dense divergence plots
matplotlib.rcParams.update({
    "axes.titlesize": 10,
    "legend.fontsize": 6,
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


# _extract_method_from_path and _load_tables live in _divergence_io.py


def _get_break_years(breaks_df, method, penalty=BREAK_PENALTY):
    """Extract break years for a method at given penalty.

    Supports both the changepoints table (detector_params="pen=3") and
    legacy per-method breaks (penalty=3 integer column).
    """
    if breaks_df.empty or "break_years" not in breaks_df.columns:
        return set()

    # Filter by method
    mask = breaks_df["method"] == method

    # Match penalty: new format uses detector_params string, old uses penalty int
    if "detector_params" in breaks_df.columns:
        pen_str = f"pen={penalty}"
        mask = mask & (breaks_df["detector_params"] == pen_str)
    elif "penalty" in breaks_df.columns:
        mask = mask & (breaks_df["penalty"] == penalty)

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


def _plot_one_method(div_df, breaks_df, method, out_stem,
                     aggregate="none", palette="auto"):
    """Plot one figure for a single method."""
    mdf = div_df[div_df["method"] == method].dropna(subset=["value"]).copy()
    if mdf.empty:
        log.warning("No data for %s; skipping", method)
        return

    title, ylabel = METHOD_LABELS.get(method, (method, "value"))

    # L2 has sub-metrics (novelty, transience, resonance) encoded in hyperparams
    is_l2 = method == "L2" and aggregate == "none" and palette == "auto"
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
                _draw_curves(ax, sub, breaks_df, method, aggregate, palette)
                ax.set_ylabel(metric_name.capitalize())
                ax.set_title("")
            axes[0].set_title(title)
            axes[-1].set_xlabel("Year")
            fig.tight_layout()
            save_figure(fig, f"{out_stem}_{method}", dpi=DPI)
            plt.close(fig)
            log.info("Saved %s_%s.png (%d panels)", out_stem, method, n_panels)
            return

    fig, ax = plt.subplots(figsize=(FIGWIDTH, FIGHEIGHT))
    _draw_curves(ax, mdf, breaks_df, method, aggregate, palette)
    ax.set_xlabel("Year")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    fig.tight_layout()
    save_figure(fig, f"{out_stem}_{method}", dpi=DPI)
    plt.close(fig)
    log.info("Saved %s_%s.png", out_stem, method)


def _draw_curves(ax, mdf, breaks_df, method, aggregate="none", palette="auto"):
    """Draw temporal curves on a single axes.

    Parameters
    ----------
    ax : matplotlib.axes.Axes
        Target axes.
    mdf : pd.DataFrame
        Divergence data for one method.
    breaks_df : pd.DataFrame
        Break detection results (may be empty).
    method : str
        Method name, used to look up breaks.
    aggregate : {"none", "ribbon"}
        "none": one curve per (window, hyperparams) group.
        "ribbon": median +/- IQR across replicate runs, grouped by dimension.
    palette : {"auto", "gradient"}
        "auto": discrete colors per group.
        "gradient": light-to-dark by projection dimension, black baseline.

    """
    if aggregate == "ribbon":
        _draw_ribbon(ax, mdf)
    elif palette == "gradient":
        _draw_gradient(ax, mdf)
    else:
        _draw_lines(ax, mdf)

    # Break lines (only for standard plots where breaks are meaningful)
    if aggregate == "none" and palette == "auto":
        break_years = _get_break_years(breaks_df, method, BREAK_PENALTY)
        for by in sorted(break_years):
            ax.axvline(by, color="red", linewidth=0.7, linestyle="--", alpha=0.7)

    handles, labels = ax.get_legend_handles_labels()
    if handles:
        ncol = 2 if len(handles) <= 12 else 3
        ax.legend(loc="best", frameon=False, fontsize=5.5, ncol=ncol)


def _draw_lines(ax, mdf):
    """One curve per (window, hyperparams) group, discrete colors."""
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


def _draw_gradient(ax, mdf):
    """Curves ordered by projection dimension, light-to-dark + black baseline."""
    parsed = mdf["hyperparams"].apply(_parse_projection_tag)
    mdf = mdf.copy()
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


def _draw_ribbon(ax, mdf):
    """Median +/- IQR across replicate runs, one ribbon per dimension."""
    parsed = mdf["hyperparams"].apply(_parse_projection_tag)
    mdf = mdf.copy()
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


# ── Main ────────────────────────────────────────────────────────────────

def main():
    io_args, extra = parse_io_args()
    validate_io(output=io_args.output)

    parser = argparse.ArgumentParser()
    parser.add_argument("--aggregate", default="none",
                        choices=["none", "ribbon"])
    parser.add_argument("--palette", default="auto",
                        choices=["auto", "gradient"])
    args = parser.parse_args(extra)

    if not io_args.input:
        tables_dir = os.path.join(os.path.dirname(os.path.dirname(io_args.output)),
                                  "tables")
        import glob
        io_args.input = sorted(glob.glob(os.path.join(tables_dir, "tab_div_*.csv")))

    div_df, breaks_df = load_divergence_tables(io_args.input)

    if div_df.empty:
        log.warning("No divergence data found; nothing to plot")
        return

    methods = sorted(div_df["method"].unique())
    log.info("Plotting %d methods (aggregate=%s, palette=%s): %s",
             len(methods), args.aggregate, args.palette, methods)

    for method in methods:
        _plot_one_method(div_df, breaks_df, method,
                         os.path.splitext(io_args.output)[0],
                         aggregate=args.aggregate, palette=args.palette)

    log.info("Done.")


if __name__ == "__main__":
    main()
