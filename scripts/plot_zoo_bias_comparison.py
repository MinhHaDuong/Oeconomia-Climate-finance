"""Bias comparison figure: biased vs debiased raw divergence series.

Plots the raw `value` column (not Z-score) for one method, overlaying the
biased series (equal_n=False) against the debiased series (equal_n=True).
One panel per call, one method per figure.

Usage::

    uv run python scripts/plot_zoo_bias_comparison.py \\
        --method S2_energy \\
        --input content/tables/tab_div_S2_energy.csv \\
        --biased-csv content/tables/tab_div_biased_S2_energy.csv \\
        --output content/figures/fig_zoo_bias_S2_energy.png
"""

import argparse
import os

import matplotlib.pyplot as plt
import pandas as pd
from pipeline_io import save_figure
from script_io_args import parse_io_args, validate_io


def _load_series(csv_path: str, window_val: int) -> pd.DataFrame:
    """Load CSV and return rows for the chosen window, sorted by year."""
    df = pd.read_csv(csv_path)
    # window column may be int or string after CSV roundtrip — coerce to int
    df["window"] = pd.to_numeric(df["window"], errors="coerce")
    subset = df[df["window"] == window_val].copy()
    subset = subset.sort_values("year")
    return subset


def _pick_window(csv_path: str) -> int:
    """Return the smallest integer window value present in the CSV."""
    df = pd.read_csv(csv_path)
    df["window"] = pd.to_numeric(df["window"], errors="coerce")
    windows = sorted(df["window"].dropna().unique().astype(int))
    if not windows:
        raise ValueError(f"No numeric window values found in {csv_path}")
    # Prefer window=3 if available, else fall back to smallest
    return 3 if 3 in windows else windows[0]


def main() -> None:
    io_args, extra = parse_io_args()
    validate_io(output=io_args.output, inputs=io_args.input)

    parser = argparse.ArgumentParser(description="Zoo bias comparison figure")
    parser.add_argument("--method", required=True, help="Method name (e.g. S2_energy)")
    parser.add_argument(
        "--biased-csv",
        required=True,
        help="Path to biased divergence table (equal_n=False)",
    )
    args = parser.parse_args(extra)

    # Validate biased CSV exists
    if not os.path.exists(args.biased_csv):
        raise FileNotFoundError(f"Biased CSV not found: {args.biased_csv}")

    debiased_path = io_args.input[0]
    biased_path = args.biased_csv

    # Pick window (prefer w=3 if available)
    window = _pick_window(debiased_path)

    df_deb = _load_series(debiased_path, window)
    df_bias = _load_series(biased_path, window)

    if df_deb.empty:
        raise ValueError(
            f"No rows for window={window} in debiased CSV: {debiased_path}"
        )
    if df_bias.empty:
        raise ValueError(f"No rows for window={window} in biased CSV: {biased_path}")

    # ── Plot ──────────────────────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(7, 3.5))

    color_deb = "#1f77b4"  # blue — debiased
    color_bias = "#d62728"  # red  — biased

    ax.plot(
        df_bias["year"],
        df_bias["value"],
        color=color_bias,
        linewidth=1.4,
        linestyle="-",
        label=f"Biased (equal_n=False), w={window}",
    )
    ax.plot(
        df_deb["year"],
        df_deb["value"],
        color=color_deb,
        linewidth=1.4,
        linestyle="--",
        label=f"Debiased (equal_n=True), w={window}",
    )

    # Shade the gap between series where years align
    merged = pd.merge(
        df_bias[["year", "value"]].rename(columns={"value": "v_bias"}),
        df_deb[["year", "value"]].rename(columns={"value": "v_deb"}),
        on="year",
    ).sort_values("year")
    if not merged.empty:
        ax.fill_between(
            merged["year"],
            merged["v_deb"],
            merged["v_bias"],
            alpha=0.2,
            color="#888888",
            label="Bias magnitude",
        )

    ax.set_xlabel("Year")
    ax.set_ylabel("Raw divergence value")
    ax.set_title(
        f"{args.method}: biased vs debiased divergence (w={window})",
        fontsize=10,
    )
    ax.legend(fontsize=8, frameon=False)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    fig.tight_layout()

    stem = os.path.splitext(io_args.output)[0]
    save_figure(fig, stem, dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    main()
