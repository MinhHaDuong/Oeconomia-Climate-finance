"""Plot cross-year Z-score time series for one zoo method.

Reads tab_crossyear_{method}.csv (produced by compute_crossyear_zscore.py)
and renders one panel showing Z(t,w) for windows w=2,3,4,5.

Degrades gracefully: if the input CSV does not exist, writes an empty figure
with a "Data not yet computed" annotation so Make does not fail.

Usage::

    uv run python scripts/plot_zoo_results.py \\
        --method S2_energy \\
        --output content/figures/fig_zoo_S2_energy.png
"""

import argparse
import os
import sys

import matplotlib.pyplot as plt
import pandas as pd
from pipeline_io import save_figure
from plot_style import DARK, FILL, LIGHT, MED, apply_style
from script_io_args import parse_io_args, validate_io
from utils import get_logger

log = get_logger("plot_zoo_results")
apply_style()

# Four shades from lightest to darkest — w=2 lightest, w=3 prominent.
_WINDOW_STYLES = {
    "2": {"color": LIGHT, "linewidth": 0.9, "label": "w=2"},
    "3": {"color": DARK, "linewidth": 1.6, "label": "w=3 (lead)"},
    "4": {"color": MED, "linewidth": 0.9, "label": "w=4"},
    "5": {"color": "#555555", "linewidth": 0.9, "label": "w=5"},
}

_Z_THRESHOLD = 2.0
_PERIOD_BREAKS = [2007, 2013]


def _empty_figure(output_stem: str, method: str) -> None:
    """Produce a placeholder figure when data is unavailable."""
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.text(
        0.5,
        0.5,
        "Data not yet computed",
        transform=ax.transAxes,
        ha="center",
        va="center",
        fontsize=12,
        color=MED,
    )
    ax.set_title(f"Cross-year Z-score: {method}")
    ax.set_axis_off()
    save_figure(fig, output_stem, dpi=150)
    plt.close(fig)


def _plot(df: pd.DataFrame, method: str, output_stem: str) -> None:
    """Render the Z-score panel and save to output_stem.png."""
    fig, ax = plt.subplots(figsize=(6, 4))

    # Null zone band.
    ax.axhspan(
        -_Z_THRESHOLD,
        _Z_THRESHOLD,
        color=FILL,
        alpha=0.15,
        zorder=0,
        label=None,
    )

    # Threshold lines.
    for sign in (+1, -1):
        ax.axhline(
            sign * _Z_THRESHOLD,
            color=MED,
            linewidth=0.6,
            linestyle="--",
            zorder=1,
        )

    # Period boundary verticals.
    for year in _PERIOD_BREAKS:
        ax.axvline(year, color=LIGHT, linewidth=0.6, linestyle="--", zorder=1)
        ax.text(
            year,
            1.01,
            str(year),
            transform=ax.get_xaxis_transform(),
            ha="center",
            va="bottom",
            fontsize=6,
            color=MED,
        )

    # One line per sliding window (w=2..5).
    plotted = []
    for w_str in ("2", "3", "4", "5"):
        sub = df[df["window"] == w_str].sort_values("year")
        if sub.empty:
            continue
        style = _WINDOW_STYLES[w_str]
        ax.plot(
            sub["year"],
            sub["z_score"],
            color=style["color"],
            linewidth=style["linewidth"],
            label=style["label"],
            zorder=3,
        )
        plotted.append(w_str)

    # Fallback: cumulative or single-window methods (G3, G4, G7, L3).
    if not plotted:
        non_sliding = df[~df["window"].isin(("2", "3", "4", "5"))].sort_values("year")
        non_sliding = non_sliding.dropna(subset=["z_score"])
        if not non_sliding.empty:
            wlabel = non_sliding["window"].iloc[0]
            ax.plot(
                non_sliding["year"],
                non_sliding["z_score"],
                color=DARK,
                linewidth=1.6,
                label=wlabel,
                zorder=3,
            )
            plotted.append(wlabel)
        else:
            log.warning("No plottable rows found for method %s", method)

    ax.set_xlabel("Year")
    ax.set_ylabel("Cross-year Z-score Z(t,w)")
    ax.set_title(f"Cross-year Z-score: {method}")

    if not df.empty:
        ax.set_xlim(df["year"].min() - 0.5, df["year"].max() + 0.5)

    ax.legend(loc="upper left", frameon=False, fontsize=7)
    fig.tight_layout()
    save_figure(fig, output_stem, dpi=150)
    plt.close(fig)
    log.info("Saved figure to %s.png", output_stem)


def main() -> None:
    io_args, extra = parse_io_args()

    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument(
        "--method",
        required=True,
        help="Method name, e.g. S2_energy",
    )
    args = parser.parse_args(extra)

    method = args.method
    validate_io(output=io_args.output)

    output_stem = os.path.splitext(io_args.output)[0]
    input_path = f"content/tables/tab_crossyear_{method}.csv"

    if not os.path.exists(input_path):
        log.warning("Input not found: %s — producing empty figure", input_path)
        _empty_figure(output_stem, method)
        return

    df = pd.read_csv(input_path)
    for col in ("year", "window", "z_score"):
        if col not in df.columns:
            log.warning(
                "Missing column '%s' in %s — producing empty figure", col, input_path
            )
            _empty_figure(output_stem, method)
            return

    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df["z_score"] = pd.to_numeric(df["z_score"], errors="coerce")
    df = df.dropna(subset=["year"])
    df["year"] = df["year"].astype(int)
    # window is written as str but pd.read_csv may infer int; normalise.
    df["window"] = df["window"].astype(str)

    _plot(df, method, output_stem)


if __name__ == "__main__":
    sys.exit(main())
