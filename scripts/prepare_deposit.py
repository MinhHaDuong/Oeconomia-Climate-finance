"""Prepare data files for the Zenodo deposit.

Reads extended_works.csv (which has quality flags) and writes
climate_finance_corpus.csv with:
- Abstract column dropped (publisher redistribution restrictions)
- Individual flag columns replaced by is_flagged/is_protected/flag_reason
- Column from_scispsace renamed to from_scispace if present
- Intermediate columns (doi_norm, etc.) dropped

Usage:
    uv run python scripts/prepare_deposit.py [--out-dir DIR]
"""

import argparse
import os
import sys

import pandas as pd

from utils import CATALOGS_DIR, get_logger

log = get_logger("prepare_deposit")

# Individual flag columns to collapse into is_flagged + flag_reason
FLAG_COLUMNS = [
    "missing_metadata",
    "no_abstract_irrelevant",
    "title_blacklist",
    "citation_isolated_old",
    "semantic_outlier",
    "llm_irrelevant",
]

# Columns to drop from the deposit (intermediate or restricted)
COLUMNS_TO_DROP = [
    "abstract",       # publisher redistribution restrictions
    "doi_norm",       # intermediate
    "action",         # redundant with is_flagged/is_protected
]

DEPOSIT_RENAMES = {"from_scispsace": "from_scispace"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out-dir",
        default=os.path.join(CATALOGS_DIR, "deposit"),
        help="Output directory for deposit files",
    )
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    # --- Read extended_works.csv (has quality flags) ---
    extended_path = os.path.join(CATALOGS_DIR, "extended_works.csv")
    log.info("Reading %s", extended_path)
    df = pd.read_csv(extended_path)
    n_total = len(df)
    log.info("Read %d rows, %d columns", n_total, len(df.columns))

    # --- Compute is_flagged and flag_reason from individual flags ---
    flag_cols_present = [c for c in FLAG_COLUMNS if c in df.columns]
    if flag_cols_present:
        df["is_flagged"] = df[flag_cols_present].any(axis=1)
        # Build flag_reason as comma-separated list of triggered flags
        df["flag_reason"] = df[flag_cols_present].apply(
            lambda row: ",".join(c for c in flag_cols_present if row[c]),
            axis=1,
        )
        df.loc[~df["is_flagged"], "flag_reason"] = ""
        log.info("Computed is_flagged from %d flag columns", len(flag_cols_present))

    # --- Rename protected → is_protected, keep protect_reason ---
    if "protected" in df.columns:
        df = df.rename(columns={"protected": "is_protected"})
    if "protect_reason" in df.columns:
        df = df.rename(columns={"protect_reason": "protection_reason"})

    # --- Drop columns ---
    to_drop = COLUMNS_TO_DROP + flag_cols_present
    dropped = [c for c in to_drop if c in df.columns]
    if dropped:
        df = df.drop(columns=dropped)
        log.info("Dropped %d columns: %s", len(dropped), dropped)

    # --- Rename legacy typo column ---
    renames = {k: v for k, v in DEPOSIT_RENAMES.items() if k in df.columns}
    if renames:
        df = df.rename(columns=renames)
        log.info("Renamed columns: %s", renames)

    # --- Write ---
    out_path = os.path.join(args.out_dir, "climate_finance_corpus.csv")
    df.to_csv(out_path, index=False)
    log.info("Wrote %s (%d rows, %d columns)", out_path, n_total, len(df.columns))

    # --- Verify ---
    errors = []
    if "abstract" in df.columns:
        errors.append("abstract column still present")
    if "from_scispsace" in df.columns:
        errors.append("from_scispsace typo still present")
    if "is_flagged" not in df.columns:
        errors.append("is_flagged column missing")
    if "is_protected" not in df.columns:
        errors.append("is_protected column missing")

    n_flagged = df["is_flagged"].sum() if "is_flagged" in df.columns else 0
    n_protected = df["is_protected"].sum() if "is_protected" in df.columns else 0
    n_removed = ((df["is_flagged"]) & (~df["is_protected"])).sum()
    n_kept = n_total - n_removed
    log.info("Flagged: %d, Protected: %d, Removed: %d, Kept: %d",
             n_flagged, n_protected, n_removed, n_kept)

    if errors:
        for e in errors:
            log.error(e)
        sys.exit(1)

    log.info("Deposit files ready in %s", args.out_dir)


if __name__ == "__main__":
    main()
