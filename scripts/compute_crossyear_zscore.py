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
from typing import Optional

import pandas as pd
from pipeline_io import save_csv
from pipeline_loaders import load_analysis_config
from schemas import CrossyearZscoreSchema
from script_io_args import parse_io_args, validate_io
from utils import get_logger

log = get_logger("compute_crossyear_zscore")


def _subsample_percentiles(
    subsample_df: pd.DataFrame, trim: int = 2
) -> dict[tuple[int, str], tuple[float, float]]:
    """Compute trimmed-range bounds per (year, window) from subsample replicates.

    Drops `trim` extreme replicates from each tail and returns the remaining
    min/max — an order-statistic range, not a fixed-percentile interval. The
    resulting percentile coverage depends on R: with R=20 trim=2 it spans
    roughly Q10/Q90; with R=10 trim=2, ≈ Q20/Q80.

    Returns (NaN, NaN) when a (year, window) group has no usable replicates,
    and the un-trimmed min/max when R ≤ 2*trim.

    Returns {(year, window): (value_lo, value_hi)}.
    """
    result: dict[tuple[int, str], tuple[float, float]] = {}
    for (y, w), grp in subsample_df.groupby(["year", "window"]):
        vals = grp["value"].dropna().sort_values().values
        if len(vals) == 0:
            result[(int(y), str(w))] = (float("nan"), float("nan"))
        elif len(vals) <= 2 * trim:
            result[(int(y), str(w))] = (float(vals[0]), float(vals[-1]))
        else:
            trimmed = vals[trim : len(vals) - trim]
            result[(int(y), str(w))] = (float(trimmed[0]), float(trimmed[-1]))
    return result


def compute_crossyear_zscores(
    df: pd.DataFrame,
    method: str,
    subsample_df: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """Compute cross-year Z-scores for all windows in df.

    Parameters
    ----------
    df : pd.DataFrame
        Raw divergence data with columns year, window, value (plus any others).
    method : str
        Method name, written into the output 'method' column.
    subsample_df : pd.DataFrame, optional
        Subsampling replicates (from compute_divergence_subsampled.py) with
        columns year, window, replicate, value.  When provided, derives
        z_lo/z_hi ribbon bounds using the same μ/σ as z_score.

    Returns
    -------
    pd.DataFrame
        Schema: method, year, window, value, z_score, z_lo, z_hi.
        z_lo/z_hi are NaN when subsample_df is absent or has no data for a cell.

    """
    trim = 2
    if subsample_df is not None:
        try:
            cfg = load_analysis_config()
            trim = cfg["divergence"].get("subsample_trim", 2)
        except (FileNotFoundError, KeyError) as exc:
            log.warning(
                "Falling back to default subsample trim=%s; could not read "
                "divergence.subsample_trim from analysis config: %s",
                trim,
                exc,
            )

    pctiles = (
        _subsample_percentiles(subsample_df, trim=trim)
        if subsample_df is not None
        else {}
    )

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
            z_lo_series = pd.Series([float("nan")] * len(grp), index=grp.index)
            z_hi_series = pd.Series([float("nan")] * len(grp), index=grp.index)
        else:
            z = (vals - mean_d) / std_d
            z_lo_vals = []
            z_hi_vals = []
            window = keys[0] if isinstance(keys, tuple) else keys
            for _, row in grp.iterrows():
                key = (int(row["year"]), str(window))
                if key in pctiles:
                    vlo, vhi = pctiles[key]
                    z_lo_vals.append((vlo - mean_d) / std_d)
                    z_hi_vals.append((vhi - mean_d) / std_d)
                else:
                    z_lo_vals.append(float("nan"))
                    z_hi_vals.append(float("nan"))
            z_lo_series = pd.Series(z_lo_vals, index=grp.index)
            z_hi_series = pd.Series(z_hi_vals, index=grp.index)

        window = keys[0] if isinstance(keys, tuple) else keys
        grp = grp.copy()
        grp["z_score"] = z
        grp["z_lo"] = z_lo_series
        grp["z_hi"] = z_hi_series
        grp["window"] = str(window)
        per_hp.append(grp[["year", "window", "value", "z_score", "z_lo", "z_hi"]])

    combined = pd.concat(per_hp, ignore_index=True)

    agg = (
        combined.groupby(["year", "window"], sort=True)
        .agg(
            value=("value", "mean"),
            z_score=("z_score", "mean"),
            z_lo=("z_lo", "mean"),
            z_hi=("z_hi", "mean"),
        )
        .reset_index()
    )
    agg.insert(0, "method", method)
    return agg[["method", "year", "window", "value", "z_score", "z_lo", "z_hi"]]


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
    parser.add_argument(
        "--subsample-csv",
        default=None,
        help="Path to tab_subsample_{method}.csv for replication ribbon (ticket 0105).",
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

    subsample_df = None
    if args.subsample_csv:
        try:
            subsample_df = pd.read_csv(args.subsample_csv)
            log.info(
                "Loaded %d subsample rows from %s",
                len(subsample_df),
                args.subsample_csv,
            )
        except FileNotFoundError:
            log.warning(
                "Subsample file not found: %s — ribbon will be NaN", args.subsample_csv
            )

    result = compute_crossyear_zscores(raw, method, subsample_df=subsample_df)

    # Validate against schema before writing.
    CrossyearZscoreSchema.validate(result)
    log.info("Schema validation passed (%d rows)", len(result))

    save_csv(result, io_args.output)


if __name__ == "__main__":
    sys.exit(main())
