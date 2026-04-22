"""Empirical check: cross-year Z-score vs permutation p-value agreement.

Reads tab_crossyear_S2_energy.csv and tab_null_S2_energy.csv, computes
the Spearman rank correlation between |Z| and -log10(p_value) across
(year, window) cells, and prints the result.

This is an analysis-only script: it prints to stdout, produces no output file.
If the null table does not exist (compute_null_model has not been run), it
exits with a clear message.

Usage:
    uv run python scripts/analyze_zscore_vs_pvalue.py
    uv run python scripts/analyze_zscore_vs_pvalue.py \\
        --crossyear path/to/tab_crossyear_S2_energy.csv \\
        --null path/to/tab_null_S2_energy.csv
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from utils import get_logger

log = get_logger("analyze_zscore_vs_pvalue")

# Default paths relative to the repo tables directory
_DEFAULT_TABLES = Path(__file__).parent.parent / "content" / "tables"
_DEFAULT_CROSSYEAR = _DEFAULT_TABLES / "tab_crossyear_S2_energy.csv"
_DEFAULT_NULL = _DEFAULT_TABLES / "tab_null_S2_energy.csv"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Spearman ρ between |cross-year Z| and -log10(permutation p)"
    )
    parser.add_argument(
        "--crossyear",
        default=str(_DEFAULT_CROSSYEAR),
        help="Path to tab_crossyear_S2_energy.csv",
    )
    parser.add_argument(
        "--null",
        default=str(_DEFAULT_NULL),
        help="Path to tab_null_S2_energy.csv",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    crossyear_path = Path(args.crossyear)
    null_path = Path(args.null)

    if not crossyear_path.exists():
        sys.exit(f"Cross-year table not found: {crossyear_path}")
    if not null_path.exists():
        sys.exit(
            f"Null table not found: {null_path}\n"
            "Run `make null-model` on padme to generate it."
        )

    log.info("Loading %s", crossyear_path)
    df_z = pd.read_csv(crossyear_path)

    log.info("Loading %s", null_path)
    df_null = pd.read_csv(null_path)

    # Identify the Z-score column (cross-year table)
    z_col = next(
        (c for c in df_z.columns if c.lower() in ("z", "zscore", "z_score")), None
    )
    if z_col is None:
        # Fall back: pick the first numeric column that is not year/window
        numeric_cols = [c for c in df_z.columns if c not in ("year", "window")]
        z_col = numeric_cols[0] if numeric_cols else None
    if z_col is None:
        sys.exit(
            f"Cannot identify Z-score column in {crossyear_path}. Columns: {list(df_z.columns)}"
        )
    log.info("Using Z-score column: %s", z_col)

    # Identify the p-value column (null table)
    p_col = next(
        (c for c in df_null.columns if "pval" in c.lower() or c.lower() == "p"), None
    )
    if p_col is None:
        sys.exit(
            f"Cannot identify p-value column in {null_path}. Columns: {list(df_null.columns)}"
        )
    log.info("Using p-value column: %s", p_col)

    # Merge on (year, window) if present, else on index
    merge_keys = [
        c for c in ("year", "window") if c in df_z.columns and c in df_null.columns
    ]
    if merge_keys:
        merged = pd.merge(df_z, df_null, on=merge_keys, suffixes=("_z", "_null"))
    else:
        log.warning("No common merge keys (year/window); aligning by row position")
        merged = df_z.copy()
        merged[p_col] = df_null[p_col].values[: len(merged)]

    abs_z = merged[z_col].abs()
    p_vals = merged[p_col]

    # Drop rows where p is 0 (would give -log10 = inf) or NaN
    valid = (p_vals > 0) & p_vals.notna() & abs_z.notna()
    n_total = len(merged)
    n_valid = valid.sum()
    log.info("Valid cells: %d / %d", n_valid, n_total)

    if n_valid < 10:
        sys.exit(f"Too few valid cells ({n_valid}) to compute rank correlation.")

    log_p = -np.log10(p_vals[valid].values)
    rho, pvalue = spearmanr(abs_z[valid].values, log_p)

    print(
        f"\nSpearman ρ(|Z_cross-year|, -log10(p_perm)) = {rho:.3f}  (p={pvalue:.3e}, n={n_valid})"
    )

    if rho < 0.5:
        print(
            "Low rank correlation: cross-year Z and permutation p give DIVERGENT rankings.\n"
            "The non-stationarity bias is empirically significant for S2_energy.\n"
            "Consider including the scatter plot in the prose."
        )
    elif rho > 0.8:
        print(
            "High rank correlation: Z and null-p broadly agree for S2_energy.\n"
            "The trend is weak relative to noise for this method/window combination.\n"
            "Theoretical mismatch is real but practically muted here."
        )
    else:
        print(
            "Moderate rank correlation: partial agreement between Z and null-p.\n"
            "Non-stationarity creates detectable but not severe distortion."
        )


if __name__ == "__main__":
    main()
