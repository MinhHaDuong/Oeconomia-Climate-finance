"""Plot cross-year Z-score time series for one zoo method.

Reads tab_crossyear_{method}.csv (produced by compute_crossyear_zscore.py)
and renders one panel showing Z(t,w) for windows w=2,3,4.

Degrades gracefully: if the input CSV does not exist, writes an empty figure
with a "Data not yet computed" annotation so Make does not fail.

Usage::

    uv run python scripts/plot_zoo_results.py \\
        --method S2_energy \\
        --output content/figures/fig_zoo_S2_energy.png

    # With null CI band overlay:
    uv run python scripts/plot_zoo_results.py \\
        --method S2_energy \\
        --output content/figures/fig_zoo_S2_energy.png \\
        --null-ci content/tables/tab_null_S2_energy.csv
"""

import argparse
import os
import sys
from pathlib import Path

import matplotlib.lines as mlines
import matplotlib.pyplot as plt
import pandas as pd
from pipeline_io import save_figure
from plot_style import DARK, FILL, LIGHT, MED, apply_style
from script_io_args import parse_io_args, validate_io
from utils import get_logger

log = get_logger("plot_zoo_results")
apply_style()

# Three shades from lightest to darkest — w=2 lightest, w=3 prominent.
_WINDOW_STYLES = {
    "2": {"color": LIGHT, "linewidth": 0.9, "label": "w=2"},
    "3": {"color": DARK, "linewidth": 1.6, "label": "w=3 (lead)"},
    "4": {"color": MED, "linewidth": 0.9, "label": "w=4"},
}

_Z_THRESHOLD = 2.0
_PERIOD_BREAKS = [2007, 2013]


def _build_method_parser() -> argparse.ArgumentParser:
    """Return the method-level argument parser (used by tests and main)."""
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument(
        "--method",
        required=True,
        help="Method name, e.g. S2_energy",
    )
    parser.add_argument(
        "--null-ci",
        metavar="PATH",
        default=None,
        help="Optional: tab_null_{method}.csv for CI band overlay",
    )
    return parser


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


def _load_null_df(null_ci_path: str | None) -> pd.DataFrame | None:
    """Load null model CSV if path provided and file exists. Returns None otherwise."""
    if null_ci_path is None:
        return None
    if not Path(null_ci_path).exists():
        log.warning("Null CI file not found: %s — skipping CI band", null_ci_path)
        return None
    null_df = pd.read_csv(null_ci_path)
    null_df["window"] = null_df["window"].astype(str)
    return null_df


def _compute_null_z_threshold(df: pd.DataFrame, null_df: pd.DataFrame) -> pd.DataFrame:
    """Add z_threshold column to null_df.

    Z_threshold = (null_mean + 1.96 * null_std - mu_w) / sigma_w

    where mu_w and sigma_w are the per-window mean and std of the crossyear
    Z-scores (from the observed data).
    """
    # tab_crossyear_*.csv always has both 'value' (raw D) and 'z_score'; use 'value'
    # to match the original Z-score normalization: Z = (D - mu_w) / sigma_w.
    col = "value" if "value" in df.columns else "z_score"
    mu_w = df.groupby("window")[col].mean()
    sigma_w = df.groupby("window")[col].std()

    null_df = null_df.copy()
    null_df["z_threshold"] = (
        null_df["null_mean"] + 1.96 * null_df["null_std"] - null_df["window"].map(mu_w)
    ) / null_df["window"].map(sigma_w)
    return null_df


def _plot(
    df: pd.DataFrame,
    method: str,
    output_stem: str,
    null_df: pd.DataFrame | None = None,
) -> None:
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

    # One line per sliding window (w=2..4).
    plotted = []
    for w_str in ("2", "3", "4"):
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

        # Null CI band: dashed line at 95th-percentile null threshold.
        if null_df is not None:
            ci_sub = null_df[null_df["window"] == w_str].sort_values("year")
            if not ci_sub.empty:
                ax.plot(
                    ci_sub["year"],
                    ci_sub["z_threshold"],
                    linestyle="--",
                    color=style["color"],
                    linewidth=0.7,
                    alpha=0.7,
                    label=None,
                    zorder=2,
                )

        plotted.append(w_str)

    # Fallback: cumulative or single-window methods (G3, G4, G7, L3).
    if not plotted:
        non_sliding = df[~df["window"].isin(("2", "3", "4"))].sort_values("year")
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

    # Add a single legend entry for the null CI band if present.
    handles, labels = ax.get_legend_handles_labels()
    if null_df is not None and plotted:
        handles.append(
            mlines.Line2D(
                [],
                [],
                color="0.5",
                linestyle="--",
                linewidth=0.7,
                label="null 95% CI",
            )
        )
        labels.append("null 95% CI")

    ax.legend(
        handles=handles, labels=labels, loc="upper left", frameon=False, fontsize=7
    )
    fig.tight_layout()
    save_figure(fig, output_stem, dpi=150)
    plt.close(fig)
    log.info("Saved figure to %s.png", output_stem)


def main() -> None:
    io_args, extra = parse_io_args()

    parser = _build_method_parser()
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

    null_df = _load_null_df(args.null_ci)
    if null_df is not None:
        null_df = _compute_null_z_threshold(df, null_df)

    _plot(df, method, output_stem, null_df=null_df)


if __name__ == "__main__":
    sys.exit(main())
