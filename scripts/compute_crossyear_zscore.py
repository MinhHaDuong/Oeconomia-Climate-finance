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
    records = []
    for window, grp in df.groupby("window", sort=False):
        grp = grp.sort_values("year").copy()
        vals = grp["value"].astype(float)
        mean_d = vals.mean()
        std_d = vals.std()  # ddof=1 (pandas default)
        if std_d == 0 or pd.isna(std_d):
            z = pd.Series([float("nan")] * len(grp), index=grp.index)
        else:
            z = (vals - mean_d) / std_d
        for _, row in grp.iterrows():
            records.append(
                {
                    "method": method,
                    "year": int(row["year"]),
                    "window": str(window),
                    "value": float(row["value"])
                    if pd.notna(row["value"])
                    else float("nan"),
                    "z_score": float(z.loc[row.name])
                    if pd.notna(z.loc[row.name])
                    else float("nan"),
                }
            )
    return pd.DataFrame(
        records, columns=["method", "year", "window", "value", "z_score"]
    )


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
    input_path = f"content/tables/tab_div_{method}.csv"

    validate_io(output=io_args.output)

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

    log.info("Loaded %d rows, %d unique windows", len(raw), raw["window"].nunique())

    result = compute_crossyear_zscores(raw, method)

    # Validate against schema before writing.
    CrossyearZscoreSchema.validate(result)
    log.info("Schema validation passed (%d rows)", len(result))

    save_csv(result, io_args.output)


if __name__ == "__main__":
    sys.exit(main())
