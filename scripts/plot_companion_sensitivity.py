"""Sensitivity small-multiples figure for multilayer-detection companion paper.

Reads tab_sensitivity_grid.csv and produces a 4×4 grid of subplots
(rows=gap, cols=window) with 5 curves per cell (one per PCA dim).

Usage:
    uv run python scripts/plot_companion_sensitivity.py \
        --input content/tables/tab_sensitivity_grid.csv \
        --output content/figures/fig_companion_sensitivity.png
"""

import os
import sys

import matplotlib.pyplot as plt
import pandas as pd
from plot_style import apply_style
from script_io_args import parse_io_args, validate_io
from utils import get_logger, save_figure

apply_style()

log = get_logger("plot_companion_sensitivity")

# Ordered parameter lists (match analysis.yaml sensitivity block)
WINDOWS = [1, 3, 5, 7]
GAPS = [0, 1, 3, 5]
DIM_COLORS = {
    64: "#1f77b4",
    128: "#ff7f0e",
    256: "#2ca02c",
    512: "#9467bd",
    1024: "#d62728",
}
DIM_LABELS = {
    64: "64",
    128: "128",
    256: "256",
    512: "512",
    1024: "full",
}


def main():
    io_args, _ = parse_io_args()

    validate_io(output=io_args.output, inputs=io_args.input)

    input_path = io_args.input[0]
    log.info("Reading %s", input_path)
    df = pd.read_csv(input_path)

    # Coerce types
    df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    df["dim"] = pd.to_numeric(df["dim"], errors="coerce").astype("Int64")
    df["window"] = df["window"].astype(str)
    df["gap"] = pd.to_numeric(df["gap"], errors="coerce").astype("Int64")
    df["z_score"] = pd.to_numeric(df["z_score"], errors="coerce")

    dims = sorted(df["dim"].dropna().unique())

    n_rows = len(GAPS)
    n_cols = len(WINDOWS)
    fig, axes = plt.subplots(
        n_rows,
        n_cols,
        figsize=(3.5 * n_cols, 2.5 * n_rows),
        sharex=False,
        sharey=False,
    )

    legend_handles = []
    legend_labels = []
    legend_plotted = False

    for row_idx, gap in enumerate(GAPS):
        for col_idx, window in enumerate(WINDOWS):
            ax = axes[row_idx][col_idx]
            cell = df[(df["gap"] == gap) & (df["window"] == str(window))]

            for dim in dims:
                dim_data = cell[cell["dim"] == dim].sort_values("year")
                if dim_data.empty:
                    continue
                color = DIM_COLORS.get(int(dim), "#333333")
                label = DIM_LABELS.get(int(dim), str(dim))
                (line,) = ax.plot(
                    dim_data["year"],
                    dim_data["z_score"],
                    color=color,
                    linewidth=1.2,
                    label=label,
                )
                if not legend_plotted:
                    legend_handles.append(line)
                    legend_labels.append(label)

            legend_plotted = True  # only collect handles from first cell

            ax.axhline(0, color="#999999", linewidth=0.6, linestyle="--")
            ax.axhline(2, color="#cccccc", linewidth=0.5, linestyle=":")
            ax.set_title(f"w={window}, g={gap}", fontsize=9)
            ax.tick_params(labelsize=7)

            if col_idx == 0:
                ax.set_ylabel("Z-score", fontsize=8)
            if row_idx == n_rows - 1:
                ax.set_xlabel("Year", fontsize=8)

    # Place legend in top-right cell
    ax_legend = axes[0][n_cols - 1]
    ax_legend.legend(
        legend_handles,
        [f"dim={l}" for l in legend_labels],
        title="PCA dim",
        fontsize=7,
        title_fontsize=8,
        loc="upper left",
    )

    fig.suptitle(
        "S2 Energy Z-score: 4×4 window × gap grid, 5 PCA dims (R=3 median)",
        fontsize=10,
        y=1.01,
    )
    fig.tight_layout()

    stem = os.path.splitext(io_args.output)[0]
    save_figure(fig, stem, dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    sys.exit(main())
