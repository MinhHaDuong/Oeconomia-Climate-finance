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

    # With analytical null overlay (C2ST only, ticket 0115):
    uv run python scripts/plot_zoo_results.py \\
        --method C2ST_embedding \\
        --output content/figures/fig_zoo_C2ST_embedding.png \\
        --analytical-null content/tables/tab_analytical_null_C2ST_embedding.csv
"""

import argparse
import os
import sys
from pathlib import Path

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd
from pipeline_io import save_figure
from pipeline_loaders import load_analysis_config
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

_METHOD_TITLES: dict[str, str] = (
    load_analysis_config().get("zoo", {}).get("method_titles", {})
)


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
    parser.add_argument(
        "--analytical-null",
        metavar="PATH",
        default=None,
        help="Optional: tab_analytical_null_{method}.csv for analytical null overlay",
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
    ax.set_title(_METHOD_TITLES.get(method, method))
    ax.set_axis_off()
    save_figure(fig, output_stem, dpi=150)
    plt.close(fig)


def _load_null_csv(path: str | None, label: str = "null") -> pd.DataFrame | None:
    """Load a null model CSV if path is given and file exists; return None otherwise.

    Parameters
    ----------
    path : str | None
        File path, or None to skip.
    label : str
        Short label for the warning message (e.g. "CI band", "analytical null").

    """
    if path is None:
        return None
    if not Path(path).exists():
        log.warning("%s file not found: %s — skipping", label, path)
        return None
    df = pd.read_csv(path)
    df["window"] = df["window"].astype(str)
    return df


def _load_null_df(null_ci_path: str | None) -> pd.DataFrame | None:
    """Load MC null model CSV. Thin wrapper around _load_null_csv."""
    return _load_null_csv(null_ci_path, label="Null CI")


def _load_analytical_null(path: str | None) -> pd.DataFrame | None:
    """Load analytical null CSV. Thin wrapper around _load_null_csv."""
    return _load_null_csv(path, label="Analytical null")


def _compute_null_z_threshold(df: pd.DataFrame, null_df: pd.DataFrame) -> pd.DataFrame:
    """Add z_threshold_upper / z_threshold_lower columns to null_df.

    Bounds = (null_mean ± 1.96 * null_std - mu_w) / sigma_w

    where mu_w and sigma_w are the per-window mean and std of the crossyear
    Z-scores (from the observed data).
    """
    # tab_crossyear_*.csv always has both 'value' (raw D) and 'z_score'; use 'value'
    # to match the original Z-score normalization: Z = (D - mu_w) / sigma_w.
    col = "value" if "value" in df.columns else "z_score"
    mu_w = df.groupby("window")[col].mean()
    sigma_w = df.groupby("window")[col].std()

    null_df = null_df.copy()
    null_df["z_threshold_upper"] = (
        null_df["null_mean"] + 1.96 * null_df["null_std"] - null_df["window"].map(mu_w)
    ) / null_df["window"].map(sigma_w)
    null_df["z_threshold_lower"] = (
        null_df["null_mean"] - 1.96 * null_df["null_std"] - null_df["window"].map(mu_w)
    ) / null_df["window"].map(sigma_w)
    return null_df


def _plot(
    df: pd.DataFrame,
    method: str,
    output_stem: str,
    null_df: pd.DataFrame | None = None,
    analytical_null_df: pd.DataFrame | None = None,
) -> None:
    """Render the Z-score panel and save to output_stem.png."""
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.axhline(0, color="0.75", linewidth=0.5, zorder=0)

    # Null zone: ribbon for w=3 if null data available, else flat ±2 box.
    w3_null = (
        null_df[null_df["window"] == "3"].sort_values("year")
        if null_df is not None
        else None
    )
    has_ribbon = (
        w3_null is not None
        and not w3_null.empty
        and "z_threshold_upper" in w3_null.columns
        and w3_null["z_threshold_upper"].notna().any()
    )
    if has_ribbon:
        ax.fill_between(
            w3_null["year"],
            w3_null["z_threshold_lower"],
            w3_null["z_threshold_upper"],
            color=FILL,
            alpha=0.40,
            zorder=0,
            label=None,
        )
    else:
        ax.axhspan(
            -_Z_THRESHOLD,
            _Z_THRESHOLD,
            color=FILL,
            alpha=0.15,
            zorder=0,
            label=None,
        )
        for sign in (+1, -1):
            ax.axhline(
                sign * _Z_THRESHOLD,
                color=MED,
                linewidth=0.6,
                linestyle="--",
                zorder=1,
            )

    # Analytical null ribbon (w=3): null_mean ± 1.96 * null_std in native units.
    # Orange fill so it remains visually distinct from the MC ribbon (blue/FILL).
    # Where the two ribbons overlap, combined alpha makes coincidence visible.
    has_an_ribbon = False
    if analytical_null_df is not None:
        w3_an = analytical_null_df[analytical_null_df["window"] == "3"].sort_values(
            "year"
        )
        if not w3_an.empty and w3_an["null_mean"].notna().any():
            has_an_ribbon = True
            ax.fill_between(
                w3_an["year"],
                w3_an["null_mean"] - 1.96 * w3_an["null_std"],
                w3_an["null_mean"] + 1.96 * w3_an["null_std"],
                color="tab:orange",
                alpha=0.20,
                zorder=0,
                label=None,
            )

    # Period boundary verticals — shorten by 1 ex so year labels clear the title.
    # 1 ex at fontsize 6 on a (6, 4) figure with default subplot params ≈ 0.012 axes units.
    _one_ex = (6 * 0.45) / (fig.get_figheight() * 72 * ax.get_position().height)
    _vline_ymax = 1.0 - _one_ex
    for year in _PERIOD_BREAKS:
        ax.axvline(
            year, color=LIGHT, linewidth=0.6, linestyle="--", zorder=1, ymax=_vline_ymax
        )
        ax.text(
            year,
            _vline_ymax,
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

        plotted.append(w_str)

    # Fallback: cumulative or single-window methods (G3, G4, G7, L3).
    if not plotted:
        non_sliding = df[~df["window"].isin(("2", "3", "4"))].sort_values("year")
        value_col = "value" if "value" in non_sliding.columns else "z_score"
        non_sliding = non_sliding.dropna(subset=[value_col])
        if not non_sliding.empty:
            wlabel = non_sliding["window"].iloc[0]
            ax.plot(
                non_sliding["year"],
                non_sliding[value_col],
                color=DARK,
                linewidth=1.6,
                label=wlabel,
                zorder=3,
            )
            plotted.append(wlabel)

            # Null ribbon for window="0" (L3): null_mean ± 1.96 * null_std
            # in the same raw-value units as the curve above.
            w0_null = (
                null_df[null_df["window"] == "0"].sort_values("year")
                if null_df is not None
                else None
            )
            has_w0_ribbon = (
                w0_null is not None
                and not w0_null.empty
                and w0_null["null_mean"].notna().any()
            )
            if has_w0_ribbon:
                ax.fill_between(
                    w0_null["year"],
                    w0_null["null_mean"] - 1.96 * w0_null["null_std"],
                    w0_null["null_mean"] + 1.96 * w0_null["null_std"],
                    color=FILL,
                    alpha=0.40,
                    zorder=0,
                    label=None,
                )
        else:
            log.warning("No plottable rows found for method %s", method)

    ax.set_xlabel("Year")
    ax.set_ylabel("Cross-year Z-score Z(t,w)")
    ax.set_title(_METHOD_TITLES.get(method, method))

    if not df.empty:
        ax.set_xlim(df["year"].min() - 0.5, df["year"].max() + 0.5)
    ax.xaxis.set_major_locator(mticker.MaxNLocator(integer=True))

    # Add legend entry for null ribbon or flat band.
    handles, labels = ax.get_legend_handles_labels()

    if has_ribbon:
        handles.append(mpatches.Patch(color=FILL, alpha=0.40, label="null 95% (w=3)"))
        labels.append("null 95% (w=3)")
    else:
        handles.append(mpatches.Patch(color=FILL, alpha=0.15, label="null ±2σ"))
        labels.append("null ±2σ")

    if has_an_ribbon:
        handles.append(
            mpatches.Patch(
                color="tab:orange", alpha=0.20, label="analytical null 95% (w=3)"
            )
        )
        labels.append("analytical null 95% (w=3)")

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

    analytical_null_df = _load_analytical_null(args.analytical_null)

    _plot(
        df, method, output_stem, null_df=null_df, analytical_null_df=analytical_null_df
    )


if __name__ == "__main__":
    sys.exit(main())
