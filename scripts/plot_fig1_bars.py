"""Fig 1 (bars): Corpus documents per year, 2000-2025.

Stacked bar chart showing total corpus size and the subset mentioning
"climate finance" in title or abstract. For Oeconomia submission.
"""

import argparse
import os
import re
import sys

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from plot_style import (
    apply_style, FIGWIDTH, DPI, MED, LIGHT, DARK, FILL,
    INCOMPLETE_FROM, PERIODS, add_period_bands, add_period_lines,
)
from utils import CATALOGS_DIR, save_figure, BASE_DIR

apply_style()

matplotlib.rcParams.update({
    "axes.labelsize": 10,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
})

CF_PATTERN = re.compile(r"\bclimate[\s-]?finance\b", re.IGNORECASE)


def main():
    parser = argparse.ArgumentParser(description="Plot Fig 1 bar chart")
    parser.add_argument("--no-pdf", action="store_true",
                        help="Skip PDF output")
    args = parser.parse_args()

    # --- Load corpus ---
    csv_path = os.path.join(CATALOGS_DIR, "refined_works.csv")
    df = pd.read_csv(csv_path, usecols=["year", "title", "abstract"],
                     dtype={"year": "Int64"})
    df = df[(df["year"] >= 1992) & (df["year"] <= 2023)].copy()

    # Flag papers mentioning "climate finance" in title or abstract
    title = df["title"].fillna("")
    abstract = df["abstract"].fillna("")
    df["has_cf"] = title.str.contains(CF_PATTERN) | abstract.str.contains(CF_PATTERN)

    yearly = df.groupby("year")["has_cf"].agg(["sum", "count"])
    yearly.columns = ["cf", "total"]
    yearly["other"] = yearly["total"] - yearly["cf"]
    yearly = yearly.sort_index()

    years = yearly.index.values
    cf = yearly["cf"].values
    other = yearly["other"].values

    # --- Plot ---
    fig, ax = plt.subplots(figsize=(FIGWIDTH, 3.5))

    ax.bar(years, cf, color=DARK, edgecolor="white", linewidth=0.3,
           zorder=2, label='"Climate finance"')
    ax.bar(years, other, bottom=cf, color=LIGHT, edgecolor="white",
           linewidth=0.3, zorder=2, label="Broader corpus")

    # --- Period bands (no vertical lines — save ink) ---
    bands = [
        ("Before", 1990, 2007, FILL, 1999),
        ("Crystallisation", 2007, 2015, "#EEEEEE", None),
        ("Disputes", 2015, 2024, FILL, None),
    ]
    for label, x0, x1, color, label_x in bands:
        ax.axvspan(x0, x1, color=color, alpha=0.4, zorder=0, linewidth=0)
        cx = label_x if label_x else (x0 + x1) / 2
        ax.text(cx, 0.97, label, transform=ax.get_xaxis_transform(),
                ha="center", va="top", fontsize=7, fontstyle="italic",
                color=MED)
    # Event labels at period boundaries (centered on the boundary)
    for year, label in [
        (1992, "Rio\nUNFCCC\n(1992)"),
        (2007, "Bali\nAction Plan\n(2007)"),
        (2015, "Paris\nAgreement\n(2015)"),
    ]:
        ax.text(year, 0.88, label, transform=ax.get_xaxis_transform(),
                ha="center", va="top", fontsize=7, color=MED,
                multialignment="center")

    # --- Legend (reverse order to match stacked bars: broader on top) ---
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles[::-1], labels[::-1],
              loc="upper left", frameon=False, bbox_to_anchor=(0.0, 0.62))

    # --- Axes ---
    ax.set_xlim(1990, 2023.5)
    ax.set_xticks(range(1995, 2024, 5))
    ax.tick_params(axis="x", rotation=0)

    # No axis spines — ticks only
    ax.yaxis.set_label_position("right")
    ax.yaxis.tick_right()
    for spine in ax.spines.values():
        spine.set_visible(False)

    ax.text(2024, 2600, "Number\nof works", ha="left", va="bottom",
            fontsize=10, color=DARK)
    ax.set_ylabel("")
    ax.set_xlabel("")

    fig.tight_layout()

    # --- Save ---
    out_path = os.path.join(BASE_DIR, "content", "figures", "fig_bars")
    save_figure(fig, out_path, no_pdf=args.no_pdf, dpi=DPI)
    plt.close(fig)


if __name__ == "__main__":
    main()
