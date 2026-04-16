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


def build_summary(div_df, null_df, boot_df, method):
    """Build summary table from three sources.

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

    # Select p_value from null model
    null_cols = null_df[["year", "window", "p_value"]].copy()

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
            "p_value",
            "significant",
        ]
    ]

    return result


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
    args = parser.parse_args(extra)

    div_df = pd.read_csv(args.div_csv)
    boot_df = pd.read_csv(args.boot_csv)
    null_df = pd.read_csv(args.null_csv)

    log.info(
        "Loaded: div=%d rows, boot=%d rows, null=%d rows",
        len(div_df),
        len(boot_df),
        len(null_df),
    )

    result = build_summary(div_df, null_df, boot_df, method=args.method)

    # Validate contract
    DivergenceSummarySchema.validate(result)

    result.to_csv(io_args.output, index=False)
    log.info("Saved summary (%d rows) -> %s", len(result), io_args.output)


if __name__ == "__main__":
    main()
