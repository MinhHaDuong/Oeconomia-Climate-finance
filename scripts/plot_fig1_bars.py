"""Fig 1 (bars): Climate finance papers per year, 2000-2025.

Simple bar chart for Oeconomia submission showing growth of climate finance
scholarship with period boundaries.
"""

import argparse
import os
import sys

import matplotlib
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from plot_style import (
    apply_style, FIGWIDTH, DPI, MED, LIGHT, DARK, FILL,
    INCOMPLETE_FROM, add_period_bands, add_period_lines,
)
from utils import CATALOGS_DIR, save_figure, BASE_DIR

apply_style()

# Override font sizes for readability at 120mm print width (8-10pt minimum)
import matplotlib.pyplot as plt
matplotlib.rcParams.update({
    "axes.labelsize": 10,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
})


def main():
    parser = argparse.ArgumentParser(description="Plot Fig 1 bar chart")
    parser.add_argument("--no-pdf", action="store_true",
                        help="Skip PDF output")
    args = parser.parse_args()

    # --- Load data ---
    csv_path = os.path.join(CATALOGS_DIR, "openalex_econ_yearly.csv")
    df = pd.read_csv(csv_path)
    df = df[(df["year"] >= 2000) & (df["year"] <= 2025)].copy()
    df = df.sort_values("year")

    years = df["year"].values
    counts = df["n_climate_finance"].values

    # --- Plot ---
    fig, ax = plt.subplots(figsize=(FIGWIDTH, 3.5))

    # All bars same color (no incomplete-year distinction)
    ax.bar(years, counts,
           color=MED, edgecolor="white", linewidth=0.3, zorder=2)

    # --- Period bands and lines ---
    add_period_bands(ax)
    add_period_lines(ax)

    # --- Axes ---
    ax.set_xlim(1999.5, 2025.5)
    ax.set_xticks(range(2000, 2026, 5))
    ax.tick_params(axis="x", rotation=0)  # horizontal tick labels

    # Move y-axis to the right side (near the data)
    ax.yaxis.set_label_position("right")
    ax.yaxis.tick_right()
    ax.spines["right"].set_visible(True)
    ax.spines["left"].set_visible(False)

    ax.set_ylabel("Number of works")
    ax.set_xlabel("")

    fig.tight_layout()

    # --- Save ---
    out_path = os.path.join(BASE_DIR, "content", "figures", "fig1_bars")
    save_figure(fig, out_path, no_pdf=args.no_pdf, dpi=DPI)
    plt.close(fig)


if __name__ == "__main__":
    main()
