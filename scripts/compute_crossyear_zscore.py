"""Compute cross-year Z-scores for one divergence method.

For each unique window value in tab_div_{method}.csv, standardise the
divergence series D(t, w) across years:

    Z(t, w) = (D(t, w) - mean_t D(·, w)) / std_t D(·, w)

Output columns: method, year, window, value, z_score

Cumulative-window methods (G3_coupling_age, G4_cross_tradition, G7_disruption)
have a single window="cumulative" group; the same groupby loop handles them
automatically — no special branch required.

Usage::

    uv run python scripts/compute_crossyear_zscore.py \\
        --method S2_energy \\
        --output content/tables/tab_crossyear_S2_energy.csv
"""

import argparse
import re
import sys

import pandas as pd
from pipeline_io import save_csv
from schemas import CrossyearZscoreSchema
from script_io_args import parse_io_args, validate_io
from utils import get_logger

log = get_logger("compute_crossyear_zscore")


def compute_crossyear_zscores(df: pd.DataFrame, method: str) -> pd.DataFrame:
    """Compute cross-year Z-scores for all windows in df.

    Parameters
    ----------
    df : pd.DataFrame
        Raw divergence data with columns year, window, value (plus any others).
    method : str
        Method name, written into the output 'method' column.

    Returns
    -------
    pd.DataFrame
        Schema: method (str), year (int), window (str), value (float),
        z_score (float).  z_score is NaN when std == 0 or value is NaN.

    """
    # Group by (window, hyperparams) so each hyperparameter setting gets its own
    # Z-score series. Then aggregate across hyperparams per (year, window) by
    # taking the mean, so the output has exactly one row per (year, window).
    group_keys = ["window"]
    if "hyperparams" in df.columns:
        group_keys.append("hyperparams")

    per_hp: list[pd.DataFrame] = []
    for keys, grp in df.groupby(group_keys, sort=False, dropna=False):
        grp = grp.sort_values("year").copy()
        vals = grp["value"].astype(float)
        mean_d = vals.mean()
        std_d = vals.std()
        if std_d == 0 or pd.isna(std_d):
            z = pd.Series([float("nan")] * len(grp), index=grp.index)
        else:
            z = (vals - mean_d) / std_d
        window = keys[0] if isinstance(keys, tuple) else keys
        grp = grp.copy()
        grp["z_score"] = z
        grp["window"] = str(window)
        per_hp.append(grp[["year", "window", "value", "z_score"]])

    combined = pd.concat(per_hp, ignore_index=True)

    # Average across hyperparameter settings for each (year, window).
    agg = (
        combined.groupby(["year", "window"], sort=True)
        .agg(value=("value", "mean"), z_score=("z_score", "mean"))
        .reset_index()
    )
    agg.insert(0, "method", method)
    return agg[["method", "year", "window", "value", "z_score"]]


def main() -> None:
    io_args, extra = parse_io_args()

    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument(
        "--method",
        required=True,
        help="Method name, e.g. S2_energy",
    )
    parser.add_argument(
        "--metric",
        default=None,
        help=(
            "Filter to rows where hyperparams contains metric=<value>. "
            "Used for L2 (resonance) to align observed statistic with null model."
        ),
    )
    args = parser.parse_args(extra)

    method = args.method
    input_path = (
        io_args.input[0] if io_args.input else f"content/tables/tab_div_{method}.csv"
    )

    validate_io(output=io_args.output, inputs=io_args.input)

    log.info("Reading %s", input_path)
    try:
        raw = pd.read_csv(input_path, dtype=str)
    except FileNotFoundError:
        log.error("Input file not found: %s", input_path)
        sys.exit(1)

    # Keep only the columns we need; coerce numeric types.
    for col in ("year", "window", "value"):
        if col not in raw.columns:
            log.error("Missing column '%s' in %s", col, input_path)
            sys.exit(1)

    raw["year"] = pd.to_numeric(raw["year"], errors="coerce")
    raw["value"] = pd.to_numeric(raw["value"], errors="coerce")
    raw = raw.dropna(subset=["year"])
    raw["year"] = raw["year"].astype(int)

    # Apply metric filter before aggregation (e.g. L2: resonance-only).
    if args.metric:
        if "hyperparams" not in raw.columns:
            log.error("--metric requires a 'hyperparams' column in %s", input_path)
            sys.exit(1)
        pattern = r"(?:^|,)metric=" + re.escape(args.metric) + r"(?:,|$)"
        mask = raw["hyperparams"].str.contains(pattern, regex=True, na=False)
        raw = raw[mask]
        if raw.empty:
            log.error("No rows match --metric %s in %s", args.metric, input_path)
            sys.exit(1)
        log.info("Filtered to metric=%s: %d rows remain", args.metric, len(raw))

    log.info("Loaded %d rows, %d unique windows", len(raw), raw["window"].nunique())

    result = compute_crossyear_zscores(raw, method)

    # Validate against schema before writing.
    CrossyearZscoreSchema.validate(result)
    log.info("Schema validation passed (%d rows)", len(result))

    save_csv(result, io_args.output)


if __name__ == "__main__":
    sys.exit(main())
