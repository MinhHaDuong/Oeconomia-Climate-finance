"""Plot lexical divergence figures (one per method L1, L2, L3).

Reads:  tab_lexical_divergence.csv, tab_lexical_divergence_breaks.csv
Writes: fig_divergence_L1.png, fig_divergence_L2.png, fig_divergence_L3.png

Usage:
    python3 scripts/plot_divergence_lexical.py \
        --output content/figures/fig_divergence_L1.png

The --output path determines the base directory; all three figures are written
relative to it (using the L1 path as anchor).
"""

import os

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
from plot_style import DARK, DPI, FIGWIDTH, MED, apply_style
from script_io_args import parse_io_args, validate_io
from utils import get_logger, save_figure

log = get_logger("plot_divergence_lexical")

apply_style()

# Line styles for different windows
WINDOW_STYLES = {
    0: "-",
    2: "-",
    3: "--",
    4: "-.",
    5: ":",
}

# Colors for different curves (grayscale-safe)
WINDOW_COLORS = {
    0: DARK,
    2: DARK,
    3: "#555555",
    4: "#777777",
    5: "#999999",
}

BREAK_PENALTY = 3  # which penalty to show as vertical lines


def _load_data(output_path):
    """Load series and breaks CSVs from the tables directory."""
    # Infer table paths from output figure path
    tables_dir = os.path.join(
        os.path.dirname(os.path.dirname(output_path)), "tables"
    )
    series_path = os.path.join(tables_dir, "tab_lexical_divergence.csv")
    breaks_path = os.path.join(tables_dir, "tab_lexical_divergence_breaks.csv")

    if not os.path.exists(series_path):
        raise FileNotFoundError(
            f"Series CSV not found: {series_path}. "
            "Run compute_divergence_lexical.py first."
        )

    series = pd.read_csv(series_path)
    breaks = pd.DataFrame()
    if os.path.exists(breaks_path):
        breaks = pd.read_csv(breaks_path)

    return series, breaks


def _get_break_years(breaks, method, penalty=BREAK_PENALTY):
    """Get unique break years for a method at a given penalty."""
    if breaks.empty:
        return []
    mask = (breaks["method"] == method) & (breaks["penalty"] == penalty)
    return sorted(breaks.loc[mask, "break_year"].unique())


def plot_l1(series, breaks, out_dir):
    """L1: JS divergence on TF-IDF, one curve per window."""
    l1 = series[series["method"] == "L1"].copy()
    if l1.empty:
        log.warning("No L1 data to plot")
        return

    fig, ax = plt.subplots(figsize=(FIGWIDTH, 3.0))

    for w in sorted(l1["window"].unique()):
        subset = l1[l1["window"] == w].sort_values("year")
        style = WINDOW_STYLES.get(w, "-")
        color = WINDOW_COLORS.get(w, MED)
        ax.plot(subset["year"], subset["value"],
                linestyle=style, color=color, label=f"w={w}")

    # Break lines
    break_years = _get_break_years(breaks, "L1")
    for by in break_years:
        ax.axvline(by, color="red", linestyle="--", linewidth=0.7, alpha=0.7)

    ax.set_xlabel("Year")
    ax.set_ylabel("JS divergence")
    ax.set_title("L1: TF-IDF JS divergence (sliding window)")
    ax.legend(fontsize=7, frameon=False)
    fig.tight_layout()

    stem = os.path.join(out_dir, "fig_divergence_L1")
    save_figure(fig, stem, dpi=DPI)
    plt.close(fig)
    log.info("Saved L1 figure -> %s.png", stem)


def plot_l2(series, breaks, out_dir):
    """L2: Novelty / Transience / Resonance, one subplot per metric."""
    l2 = series[series["method"] == "L2"].copy()
    if l2.empty:
        log.warning("No L2 data to plot")
        return

    # Extract metric from hyperparams string
    l2["metric"] = l2["hyperparams"].str.extract(r"metric=(\w+)")

    metrics = ["novelty", "transience", "resonance"]
    fig, axes = plt.subplots(len(metrics), 1, figsize=(FIGWIDTH, 6.0),
                             sharex=True)

    break_years = _get_break_years(breaks, "L2")

    for ax, metric in zip(axes, metrics):
        metric_data = l2[l2["metric"] == metric]
        if metric_data.empty:
            ax.set_title(metric.capitalize())
            continue

        for w in sorted(metric_data["window"].unique()):
            subset = metric_data[metric_data["window"] == w].sort_values("year")
            style = WINDOW_STYLES.get(w, "-")
            color = WINDOW_COLORS.get(w, MED)
            ax.plot(subset["year"], subset["value"],
                    linestyle=style, color=color, label=f"w={w}")

        for by in break_years:
            ax.axvline(by, color="red", linestyle="--", linewidth=0.7,
                       alpha=0.7)

        ax.set_ylabel(metric.capitalize())
        ax.legend(fontsize=6, frameon=False, loc="upper right")

    axes[0].set_title("L2: Novelty / Transience / Resonance (Barron et al.)")
    axes[-1].set_xlabel("Year")
    fig.tight_layout()

    stem = os.path.join(out_dir, "fig_divergence_L2")
    save_figure(fig, stem, dpi=DPI)
    plt.close(fig)
    log.info("Saved L2 figure -> %s.png", stem)


def plot_l3(series, breaks, out_dir):
    """L3: Burst detection, terms in burst per year."""
    l3 = series[series["method"] == "L3"].copy()
    if l3.empty:
        log.warning("No L3 data to plot")
        return

    fig, ax = plt.subplots(figsize=(FIGWIDTH, 3.0))

    l3 = l3.sort_values("year")
    ax.plot(l3["year"], l3["value"], color=DARK, marker="o", markersize=3)
    ax.fill_between(l3["year"], l3["value"], alpha=0.2, color=MED)

    break_years = _get_break_years(breaks, "L3")
    for by in break_years:
        ax.axvline(by, color="red", linestyle="--", linewidth=0.7, alpha=0.7)

    ax.set_xlabel("Year")
    ax.set_ylabel("Terms in burst (z > 2)")
    ax.set_title("L3: Burst detection (top-100 terms, z-score)")
    fig.tight_layout()

    stem = os.path.join(out_dir, "fig_divergence_L3")
    save_figure(fig, stem, dpi=DPI)
    plt.close(fig)
    log.info("Saved L3 figure -> %s.png", stem)


def main():
    io_args, _extra = parse_io_args()
    validate_io(output=io_args.output)

    series, breaks = _load_data(io_args.output)
    out_dir = os.path.dirname(io_args.output)
    os.makedirs(out_dir, exist_ok=True)

    plot_l1(series, breaks, out_dir)
    plot_l2(series, breaks, out_dir)
    plot_l3(series, breaks, out_dir)

    log.info("All lexical divergence figures saved to %s", out_dir)


if __name__ == "__main__":
    main()
