"""Plot citation graph divergence: one figure per method (G1-G8).

Reads:
  content/tables/tab_citation_divergence.csv       — divergence series
  content/tables/tab_citation_divergence_breaks.csv — PELT breakpoints

Writes:
  content/figures/fig_divergence_G{N}.png  (one per method)

The --output flag specifies the first figure path (G1); remaining figures
are saved alongside with the appropriate G{N} suffix.

Usage:
    python3 scripts/plot_divergence_citation.py \
        --output content/figures/fig_divergence_G1.png \
        --input content/tables/tab_citation_divergence.csv \
               content/tables/tab_citation_divergence_breaks.csv
"""

import os
import re

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from script_io_args import parse_io_args, validate_io
from utils import get_logger, save_figure

log = get_logger("plot_divergence_citation")

matplotlib.use("Agg")

# -- Style (Oeconomia grayscale + minimal color for breaks) --
RCPARAMS = {
    "font.family": "serif",
    "font.size": 8,
    "axes.titlesize": 9,
    "axes.labelsize": 8,
    "xtick.labelsize": 7,
    "ytick.labelsize": 7,
    "legend.fontsize": 7,
    "figure.dpi": 300,
    "savefig.dpi": 300,
    "axes.linewidth": 0.5,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": False,
    "lines.linewidth": 1.0,
}

DARK = "#333333"
MED = "#777777"
BREAK_COLOR = "#CC0000"  # red for break lines

FIGWIDTH = 135 / 25.4  # 135mm -> inches
DPI = 300

# Method metadata for nice labels
METHOD_INFO = {
    "G1_pagerank_volatility": {
        "number": 1,
        "title": "G1: PageRank Volatility",
        "ylabel": "1 - Kendall tau",
    },
    "G2_spectral_gap": {
        "number": 2,
        "title": "G2: Spectral Gap",
        "ylabel": "lambda_2 - lambda_1",
    },
    "G3_age_shift": {
        "number": 3,
        "title": "G3: Bibliographic Coupling Age Shift",
        "ylabel": "Median ref year",
    },
    "G4_cross_tradition": {
        "number": 4,
        "title": "G4: Cross-Tradition Citation Ratio",
        "ylabel": "Fraction cross-community",
    },
    "G5_pa_exponent": {
        "number": 5,
        "title": "G5: Preferential Attachment Exponent",
        "ylabel": "Power-law alpha",
    },
    "G6_citation_entropy": {
        "number": 6,
        "title": "G6: Citation Entropy",
        "ylabel": "Shannon entropy (bits)",
    },
    "G7_disruption": {
        "number": 7,
        "title": "G7: Disruption Index",
        "ylabel": "Mean CD (or IQR proxy)",
    },
    "G8_betweenness": {
        "number": 8,
        "title": "G8: Betweenness Centrality",
        "ylabel": "Mean betweenness",
    },
}


def load_data(input_paths, output_dir):
    """Load divergence series and breaks tables.

    Falls back to files alongside --output if --input not given.
    """
    if input_paths and len(input_paths) >= 2:
        series_path = input_paths[0]
        breaks_path = input_paths[1]
    else:
        tables_dir = os.path.join(os.path.dirname(output_dir), "tables")
        series_path = os.path.join(tables_dir, "tab_citation_divergence.csv")
        breaks_path = os.path.join(tables_dir, "tab_citation_divergence_breaks.csv")

    df = pd.read_csv(series_path)
    df_breaks = pd.read_csv(breaks_path)
    return df, df_breaks


def plot_method(method, df_method, breaks_pen3, out_stem):
    """Plot a single method's time series with PELT breaks."""
    matplotlib.rcParams.update(RCPARAMS)

    info = METHOD_INFO.get(method, {
        "number": 0,
        "title": method,
        "ylabel": "value",
    })

    years = df_method["year"].values
    values = df_method["value"].values

    # Check if all NaN
    valid = ~np.isnan(values.astype(float))
    if not valid.any():
        log.info("  %s: all NaN, generating placeholder", method)
        fig, ax = plt.subplots(figsize=(FIGWIDTH, 3.0))
        ax.text(0.5, 0.5, f"{info['title']}\n(no data — insufficient internal edges)",
                ha="center", va="center", transform=ax.transAxes,
                fontsize=9, color=MED)
        ax.set_xlabel("Year")
        ax.set_ylabel(info["ylabel"])
        ax.set_title(info["title"], fontsize=9, color=DARK)
        fig.tight_layout()
        save_figure(fig, out_stem, dpi=DPI)
        plt.close(fig)
        return

    fig, ax = plt.subplots(figsize=(FIGWIDTH, 3.0))

    # Plot the series (skip NaN gaps)
    valid_years = years[valid]
    valid_vals = values[valid].astype(float)
    ax.plot(valid_years, valid_vals, "-o", color=DARK, markersize=3,
            linewidth=1.0, zorder=3)

    # Draw PELT breaks (penalty=3) as vertical red dashed lines
    if breaks_pen3:
        for bp_year in breaks_pen3:
            ax.axvline(bp_year, color=BREAK_COLOR, linestyle="--",
                       linewidth=0.8, alpha=0.7, zorder=2,
                       label="PELT break" if bp_year == breaks_pen3[0] else "")

    ax.set_xlabel("Year")
    ax.set_ylabel(info["ylabel"])
    ax.set_title(info["title"], fontsize=9, color=DARK)

    # Legend only if breaks present
    if breaks_pen3:
        ax.legend(loc="best", frameon=False)

    fig.tight_layout()
    save_figure(fig, out_stem, dpi=DPI)
    plt.close(fig)


def main():
    io_args, _ = parse_io_args()
    validate_io(output=io_args.output)

    output_dir = os.path.dirname(io_args.output)
    df, df_breaks = load_data(io_args.input, output_dir)

    methods = sorted(df["method"].unique())
    log.info("Plotting %d methods: %s", len(methods), methods)

    # Parse breaks: method -> penalty -> list of years
    breaks_map = {}
    for _, row in df_breaks.iterrows():
        m = row["method"]
        pen = row["penalty"]
        bp_str = str(row.get("breakpoints", ""))
        bp_years = []
        for y_str in bp_str.split(";"):
            y_str = y_str.strip()
            if y_str and y_str != "nan":
                try:
                    bp_years.append(int(y_str))
                except ValueError:
                    pass
        breaks_map.setdefault(m, {})[pen] = bp_years

    for method in methods:
        info = METHOD_INFO.get(method, {"number": 0})
        n = info.get("number", 0)
        out_stem = os.path.join(output_dir,
                                f"fig_divergence_G{n}")

        df_m = df[df["method"] == method].sort_values("year")
        pen3_breaks = breaks_map.get(method, {}).get(3, [])

        log.info("Plotting %s -> %s.png", method, out_stem)
        plot_method(method, df_m, pen3_breaks, out_stem)

    log.info("Done. Saved %d figures to %s", len(methods), output_dir)


if __name__ == "__main__":
    main()
