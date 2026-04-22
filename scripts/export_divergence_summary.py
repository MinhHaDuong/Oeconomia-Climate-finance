"""Export divergence summary table joining point estimates, bootstrap CIs, and null model (ticket 0047).

Joins three sources by (year, window):
- Divergence CSV (point estimates)
- Bootstrap CSV (replicates -> median, q025, q975)
- Null model CSV (p-values)

Usage:
    uv run python scripts/export_divergence_summary.py \
        --div-csv content/tables/tab_div_S2_energy.csv \
        --boot-csv content/tables/tab_boot_S2_energy.csv \
        --null-csv content/tables/tab_null_S2_energy.csv \
        --method S2_energy \
        --output content/tables/tab_divergence_summary.csv
"""

import argparse

import numpy as np
import pandas as pd
from schemas import DivergenceSummarySchema
from script_io_args import parse_io_args, validate_io
from utils import get_logger

log = get_logger("export_divergence_summary")


def build_summary(div_df, null_df, boot_df, method, subsample_df=None):
    """Build summary table from three (or four) sources.

    Parameters
    ----------
    div_df : pd.DataFrame
        Divergence point estimates (year, window, hyperparams, value).
    null_df : pd.DataFrame
        Null model results (year, window, p_value, ...).
    boot_df : pd.DataFrame
        Bootstrap replicates (method, year, window, replicate, value).
    method : str
        Method name to label the output.
    subsample_df : pd.DataFrame, optional
        Subsampling replicates (method, year, window, replicate, value).
        When provided, z_trim_lo / z_trim_hi / z_median_subsample /
        n_subsamples are derived from subsampling Z-scores.  When absent,
        those four columns are NaN.

    Returns
    -------
    pd.DataFrame
        Summary with columns matching DivergenceSummarySchema.

    """
    # Aggregate divergence: take mean value per (year, window) if duplicates
    div_agg = (
        div_df.groupby(["year", "window"], as_index=False)
        .agg({"value": "mean", "hyperparams": "first"})
        .rename(columns={"value": "point_estimate"})
    )

    # Aggregate bootstrap: compute quantiles per (year, window)
    boot_agg = boot_df.groupby(["year", "window"], as_index=False)["value"].agg(
        boot_median="median",
        boot_q025=lambda x: float(np.nanquantile(x, 0.025)),
        boot_q975=lambda x: float(np.nanquantile(x, 0.975)),
    )

    # Forward z_score and p_value from null model (Z > 2 is the paper's
    # primary threshold; p-value alone loses the direction/magnitude)
    null_cols = null_df[["year", "window", "z_score", "p_value"]].copy()

    # Ensure consistent types for joining
    div_agg["year"] = div_agg["year"].astype(int)
    div_agg["window"] = div_agg["window"].astype(str)
    boot_agg["year"] = boot_agg["year"].astype(int)
    boot_agg["window"] = boot_agg["window"].astype(str)
    null_cols["year"] = null_cols["year"].astype(int)
    null_cols["window"] = null_cols["window"].astype(str)

    # Join all three
    result = div_agg.merge(boot_agg, on=["year", "window"], how="left")
    result = result.merge(null_cols, on=["year", "window"], how="left")

    # Add method and significant flag
    result["method"] = method
    result["significant"] = result["p_value"] < 0.05

    # Subsample ribbon: z_trim_lo / z_trim_hi / z_median_subsample / n_subsamples
    if subsample_df is not None and len(subsample_df) > 0:
        sub_agg = _aggregate_subsample_ribbon(subsample_df, null_df)
        sub_agg["year"] = sub_agg["year"].astype(int)
        sub_agg["window"] = sub_agg["window"].astype(str)
        result = result.merge(sub_agg, on=["year", "window"], how="left")
    else:
        result["z_trim_lo"] = np.nan
        result["z_trim_hi"] = np.nan
        result["z_median_subsample"] = np.nan
        result["n_subsamples"] = np.nan

    # Reorder columns to match schema
    result = result[
        [
            "method",
            "year",
            "window",
            "hyperparams",
            "point_estimate",
            "boot_median",
            "boot_q025",
            "boot_q975",
            "z_score",
            "p_value",
            "significant",
            "z_trim_lo",
            "z_trim_hi",
            "z_median_subsample",
            "n_subsamples",
        ]
    ]

    return result


def _aggregate_subsample_ribbon(subsample_df, null_df):
    """Derive z_trim_lo, z_trim_hi, z_median_subsample, n_subsamples per cell.

    Converts each subsampling replicate value to a Z-score using the
    per-cell null_mean / null_std from null_df, then trims the top and
    bottom 2 replicates (equivalent to 10th/90th percentile for R=20).
    """
    null_cols = null_df
    has_null_stats = (
        "null_mean" in null_cols.columns and "null_std" in null_cols.columns
    )

    sub = subsample_df.copy()
    sub["year"] = sub["year"].astype(int)
    sub["window"] = sub["window"].astype(str)

    rows = []
    for (y, w), grp in sub.groupby(["year", "window"]):
        null_row = null_cols[
            (null_cols["year"].astype(int) == y)
            & (null_cols["window"].astype(str) == str(w))
        ]
        if null_row.empty or not has_null_stats:
            continue
        null_mean = float(null_row["null_mean"].iloc[0])
        null_std = float(null_row["null_std"].iloc[0])
        if null_std == 0 or np.isnan(null_std):
            continue

        z_replicates = (grp["value"].values - null_mean) / null_std
        z_sorted = np.sort(z_replicates)
        n = len(z_sorted)
        trim = 2
        if n <= 2 * trim:
            z_trimmed = z_sorted
        else:
            z_trimmed = z_sorted[trim:-trim]

        rows.append(
            {
                "year": y,
                "window": str(w),
                "z_trim_lo": float(z_trimmed[0]),
                "z_trim_hi": float(z_trimmed[-1]),
                "z_median_subsample": float(np.median(z_trimmed)),
                "n_subsamples": n,
            }
        )

    if not rows:
        return pd.DataFrame(
            columns=[
                "year",
                "window",
                "z_trim_lo",
                "z_trim_hi",
                "z_median_subsample",
                "n_subsamples",
            ]
        )
    return pd.DataFrame(rows)


def main():
    io_args, extra = parse_io_args()
    validate_io(output=io_args.output)

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--div-csv", required=True, help="Divergence point estimates CSV"
    )
    parser.add_argument("--boot-csv", required=True, help="Bootstrap replicates CSV")
    parser.add_argument("--null-csv", required=True, help="Null model CSV")
    parser.add_argument("--method", required=True, help="Method name")
    parser.add_argument(
        "--subsample-csv",
        default=None,
        help="Optional: subsampling replicates CSV (tab_subsample_{method}.csv) for ribbon",
    )
    args = parser.parse_args(extra)

    div_df = pd.read_csv(args.div_csv)
    boot_df = pd.read_csv(args.boot_csv)
    null_df = pd.read_csv(args.null_csv)
    subsample_df = pd.read_csv(args.subsample_csv) if args.subsample_csv else None

    log.info(
        "Loaded: div=%d rows, boot=%d rows, null=%d rows, subsample=%s",
        len(div_df),
        len(boot_df),
        len(null_df),
        f"{len(subsample_df)} rows" if subsample_df is not None else "not provided",
    )

    result = build_summary(
        div_df, null_df, boot_df, method=args.method, subsample_df=subsample_df
    )

    # Validate contract
    DivergenceSummarySchema.validate(result)

    result.to_csv(io_args.output, index=False)
    log.info("Saved summary (%d rows) -> %s", len(result), io_args.output)


if __name__ == "__main__":
    main()
